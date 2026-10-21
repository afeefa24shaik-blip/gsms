from decimal import Decimal
from django.db import transaction, models
from django.core.exceptions import ValidationError
from django.utils import timezone
from gsms.models import Product, StockMovement, MovementType, Supplier


class InventoryService:
    """
    Application / Business Logic Layer for Inventory and Stock Movements.
    Enforces atomic stock changes, validations, and comprehensive audit trail logging.
    """

    @classmethod
    @transaction.atomic
    def record_stock_in(cls, product_id, quantity, user, supplier_id=None, cost_price=None, reason="Stock In / Shipment Received"):
        """
        Receives new inventory from a supplier and increments stock quantity.
        """
        if quantity <= 0:
            raise ValidationError("Stock quantity received must be greater than zero.")

        product = Product.objects.select_for_update().get(product_id=product_id)

        if supplier_id:
            try:
                supplier = Supplier.objects.get(supplier_id=supplier_id)
                product.supplier = supplier
            except Supplier.DoesNotExist:
                pass

        if cost_price is not None:
            cost_price = Decimal(str(cost_price))
            if cost_price < Decimal('0.00'):
                raise ValidationError("Cost price cannot be negative.")
            product.cost_price = cost_price

        product.stock_qty += quantity
        product.save()

        StockMovement.objects.create(
            product=product,
            user=user,
            movement_type=MovementType.RECEIVED,
            quantity=quantity,
            date=timezone.now(),
            reason=reason or f"Restocked +{quantity} units"
        )
        return product

    @classmethod
    @transaction.atomic
    def adjust_stock(cls, product_id, new_quantity, user, reason):
        """
        Adjusts inventory quantity (e.g. following physical count audit, damaged items, breakage).
        """
        if new_quantity < 0:
            raise ValidationError("Stock quantity cannot be negative.")

        if not reason or not reason.strip():
            raise ValidationError("An audit reason is required for manual stock adjustments.")

        product = Product.objects.select_for_update().get(product_id=product_id)
        delta = new_quantity - product.stock_qty

        if delta == 0:
            return product

        product.stock_qty = new_quantity
        product.save(update_fields=['stock_qty', 'updated_at'])

        StockMovement.objects.create(
            product=product,
            user=user,
            movement_type=MovementType.ADJUSTED,
            quantity=delta,
            date=timezone.now(),
            reason=reason.strip()
        )
        return product

    @classmethod
    def get_low_stock_products(cls):
        """
        Returns all active products where stock_qty <= reorder_level.
        """
        return Product.objects.filter(
            active=True,
            stock_qty__lte=models.F('reorder_level')
        ).select_related('category', 'supplier').order_by('stock_qty')

    @classmethod
    def get_inventory_summary(cls):
        """
        Calculates aggregate inventory valuation and alerts for dashboard and inventory reports.
        """
        products = Product.objects.filter(active=True)
        total_items = products.count()
        total_units = sum(p.stock_qty for p in products)
        total_cost_valuation = sum(Decimal(p.stock_qty) * p.cost_price for p in products)
        total_retail_valuation = sum(Decimal(p.stock_qty) * p.selling_price for p in products)
        low_stock_count = products.filter(stock_qty__lte=models.F('reorder_level'), stock_qty__gt=0).count()
        out_of_stock_count = products.filter(stock_qty__lte=0).count()

        return {
            'total_items': total_items,
            'total_units': total_units,
            'total_cost_valuation': total_cost_valuation,
            'total_retail_valuation': total_retail_valuation,
            'expected_profit': total_retail_valuation - total_cost_valuation,
            'low_stock_count': low_stock_count,
            'out_of_stock_count': out_of_stock_count,
        }
