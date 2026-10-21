from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from gsms.models import (
    Sale, SaleItem, Product, Customer, Payment, StockMovement,
    MovementType, SaleStatus, PaymentMethod, PaymentStatus
)


class SalesService:
    """
    Application / Business Logic Layer for Point of Sale (POS) and Checkout Operations.
    Enforces atomic transaction handling, stock deduction, price locking, and movement logging.
    """

    @classmethod
    def calculate_cart_totals(cls, items_data, discount=Decimal('0.00')):
        """
        Calculates line items totals, subtotal, discount, and grand total.
        items_data format: [{'product_id': int, 'quantity': int}, ...]
        Returns dict with breakdown and validated items.
        """
        discount = Decimal(str(discount or 0))
        if discount < Decimal('0.00'):
            raise ValidationError("Discount cannot be negative.")

        if not items_data:
            raise ValidationError("Cart cannot be empty.")

        subtotal = Decimal('0.00')
        parsed_items = []

        product_ids = [item['product_id'] for item in items_data]
        products_by_id = {p.product_id: p for p in Product.objects.filter(product_id__in=product_ids)}

        for item in items_data:
            pid = int(item['product_id'])
            qty = int(item['quantity'])

            if qty <= 0:
                raise ValidationError("Item quantity must be greater than zero.")

            product = products_by_id.get(pid)
            if not product:
                raise ValidationError(f"Product with ID #{pid} not found.")

            if not product.active:
                raise ValidationError(f"Product '{product.name}' is currently inactive and cannot be sold.")

            if product.stock_qty < qty:
                raise ValidationError(
                    f"Insufficient stock for '{product.name}'. Available: {product.stock_qty}, Requested: {qty}."
                )

            unit_price = Decimal(str(product.selling_price))
            line_total = (Decimal(qty) * unit_price).quantize(Decimal('0.01'))
            subtotal += line_total

            parsed_items.append({
                'product': product,
                'quantity': qty,
                'unit_price': unit_price,
                'line_total': line_total,
            })

        if discount > subtotal:
            raise ValidationError(
                f"Discount (${discount:.2f}) cannot exceed subtotal (${subtotal:.2f})."
            )

        total = (subtotal - discount).quantize(Decimal('0.01'))

        return {
            'items': parsed_items,
            'subtotal': subtotal.quantize(Decimal('0.01')),
            'discount': discount.quantize(Decimal('0.01')),
            'total': total,
        }

    @classmethod
    @transaction.atomic
    def process_checkout(cls, user, items_data, customer_id=None, discount=Decimal('0.00'), payment_method=PaymentMethod.CASH):
        """
        Processes checkout atomically:
        1. Acquires row locks (select_for_update) on products to guarantee concurrency safety.
        2. Validates available stock.
        3. Locks unit prices at point of sale.
        4. Creates Sale master record.
        5. Creates SaleItem child records.
        6. Deducts inventory stock quantity.
        7. Logs StockMovement audit record.
        8. Creates Payment record.
        """
        if not items_data:
            raise ValidationError("Cart cannot be empty.")

        discount = Decimal(str(discount or 0))
        if discount < Decimal('0.00'):
            raise ValidationError("Discount cannot be negative.")

        # Resolve customer if provided
        customer = None
        if customer_id:
            try:
                customer = Customer.objects.get(customer_id=customer_id)
            except Customer.DoesNotExist:
                raise ValidationError(f"Customer with ID #{customer_id} does not exist.")

        # Extract product IDs and lock rows
        product_ids = [int(item['product_id']) for item in items_data]
        # select_for_update locks the selected rows until transaction finishes
        locked_products = {
            p.product_id: p
            for p in Product.objects.select_for_update().filter(product_id__in=product_ids)
        }

        subtotal = Decimal('0.00')
        validated_items = []

        for item in items_data:
            pid = int(item['product_id'])
            qty = int(item['quantity'])

            if qty <= 0:
                raise ValidationError("Quantity for each item must be at least 1.")

            product = locked_products.get(pid)
            if not product:
                raise ValidationError(f"Product ID #{pid} does not exist.")

            if not product.active:
                raise ValidationError(f"Product '{product.name}' is inactive and cannot be sold.")

            if product.stock_qty < qty:
                raise ValidationError(
                    f"Insufficient stock for '{product.name}'. In stock: {product.stock_qty}, Requested: {qty}."
                )

            unit_price = Decimal(str(product.selling_price))
            line_total = (Decimal(qty) * unit_price).quantize(Decimal('0.01'))
            subtotal += line_total

            validated_items.append({
                'product': product,
                'quantity': qty,
                'unit_price': unit_price,
                'line_total': line_total,
            })

        if discount > subtotal:
            raise ValidationError(
                f"Discount (${discount:.2f}) cannot exceed subtotal (${subtotal:.2f})."
            )

        total = (subtotal - discount).quantize(Decimal('0.01'))

        # Create master Sale record
        sale = Sale.objects.create(
            transaction_no=Sale.generate_transaction_no(),
            user=user,
            customer=customer,
            sale_date=timezone.now(),
            subtotal=subtotal,
            discount=discount,
            total=total,
            status=SaleStatus.COMPLETED
        )

        # Create SaleItems, deduct inventory, and record stock movements
        for item in validated_items:
            product = item['product']
            qty = item['quantity']
            unit_price = item['unit_price']
            line_total = item['line_total']

            # 1. Create SaleItem (unit price locked)
            SaleItem.objects.create(
                sale=sale,
                product=product,
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total
            )

            # 2. Deduct inventory
            product.stock_qty -= qty
            product.save(update_fields=['stock_qty', 'updated_at'])

            # 3. Log StockMovement
            StockMovement.objects.create(
                product=product,
                user=user,
                movement_type=MovementType.SOLD,
                quantity=-qty,
                date=timezone.now(),
                reason=f"POS Sale #{sale.transaction_no}"
            )

        # Create Payment record
        Payment.objects.create(
            sale=sale,
            method=payment_method,
            amount=total,
            status=PaymentStatus.PAID,
            payment_date=timezone.now()
        )

        return sale

    @classmethod
    @transaction.atomic
    def cancel_or_refund_sale(cls, sale_id, user, reason="Customer Refund"):
        """
        Handles refund / cancellation of an existing sale:
        1. Restores product inventory stock.
        2. Logs StockMovement as 'returned'.
        3. Updates Sale status to 'refunded' or 'cancelled'.
        4. Updates Payment status.
        """
        sale = Sale.objects.select_for_update().get(sale_id=sale_id)
        if sale.status in [SaleStatus.REFUNDED, SaleStatus.CANCELLED]:
            raise ValidationError("Sale is already refunded or cancelled.")

        # Revert inventory for each item
        for item in sale.items.all():
            product = Product.objects.select_for_update().get(product_id=item.product_id)
            product.stock_qty += item.quantity
            product.save(update_fields=['stock_qty', 'updated_at'])

            StockMovement.objects.create(
                product=product,
                user=user,
                movement_type=MovementType.RETURNED,
                quantity=item.quantity,
                date=timezone.now(),
                reason=f"Refund for {sale.transaction_no}: {reason}"
            )

        sale.status = SaleStatus.REFUNDED
        sale.save(update_fields=['status'])

        sale.payments.update(status=PaymentStatus.REFUNDED)
        return sale
