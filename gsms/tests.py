from decimal import Decimal
from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.urls import reverse

from gsms.models import (
    User, UserRole, Category, Supplier, Customer, Product,
    Sale, SaleItem, Payment, StockMovement, MovementType, PaymentMethod, SaleStatus
)
from gsms.services import SalesService, InventoryService


class CartAndSalesBusinessLogicTests(TestCase):
    """
    Unit & Integration Tests for SalesService business logic:
    - Cart subtotal, discount, and grand total calculations
    - Stock quantity availability enforcement
    - Atomic checkout commit & inventory deduction
    - Unit price locking at moment of sale
    """

    def setUp(self):
        # Create staff user
        self.cashier = User.objects.create_user(
            username='testcashier',
            name='Test Cashier',
            email='cashier@test.com',
            password='password123',
            role=UserRole.SALES_STAFF
        )

        # Create category and supplier
        self.category = Category.objects.create(name='Souvenirs', description='Gifts')
        self.supplier = Supplier.objects.create(
            name='Artisan Co', phone='555-0100', email='artisan@test.com'
        )

        # Create products
        self.product_mug = Product.objects.create(
            code='TEST-MUG-1',
            name='Ceramic Mug',
            category=self.category,
            supplier=self.supplier,
            cost_price=Decimal('5.00'),
            selling_price=Decimal('15.00'),
            stock_qty=10,
            reorder_level=3
        )
        self.product_pen = Product.objects.create(
            code='TEST-PEN-1',
            name='Brass Pen',
            category=self.category,
            supplier=self.supplier,
            cost_price=Decimal('2.00'),
            selling_price=Decimal('8.00'),
            stock_qty=2,  # Low stock
            reorder_level=5
        )
        self.product_out_of_stock = Product.objects.create(
            code='TEST-OOS-1',
            name='Out of Stock Globe',
            category=self.category,
            supplier=self.supplier,
            cost_price=Decimal('10.00'),
            selling_price=Decimal('25.00'),
            stock_qty=0,
            reorder_level=2
        )

        self.customer = Customer.objects.create(
            name='Alice Reader', phone='555-9988', email='alice@test.com'
        )

    def test_calculate_cart_totals_valid(self):
        """Tests standard cart breakdown calculation."""
        items_data = [
            {'product_id': self.product_mug.product_id, 'quantity': 2}, # 2 * 15.00 = 30.00
            {'product_id': self.product_pen.product_id, 'quantity': 1}, # 1 * 8.00 = 8.00
        ]
        breakdown = SalesService.calculate_cart_totals(items_data, discount=Decimal('5.00'))

        self.assertEqual(breakdown['subtotal'], Decimal('38.00'))
        self.assertEqual(breakdown['discount'], Decimal('5.00'))
        self.assertEqual(breakdown['total'], Decimal('33.00'))
        self.assertEqual(len(breakdown['items']), 2)

    def test_discount_cannot_exceed_subtotal(self):
        """Verifies discount validation fails when discount > subtotal."""
        items_data = [{'product_id': self.product_mug.product_id, 'quantity': 1}]
        with self.assertRaises(ValidationError) as ctx:
            SalesService.calculate_cart_totals(items_data, discount=Decimal('50.00'))
        self.assertIn("cannot exceed subtotal", str(ctx.exception))

    def test_negative_discount_rejected(self):
        """Verifies negative discounts raise ValidationError."""
        items_data = [{'product_id': self.product_mug.product_id, 'quantity': 1}]
        with self.assertRaises(ValidationError) as ctx:
            SalesService.calculate_cart_totals(items_data, discount=Decimal('-5.00'))
        self.assertIn("Discount cannot be negative", str(ctx.exception))

    def test_insufficient_stock_prevents_checkout(self):
        """
        Stock availability validation:
        Ensures customer cannot purchase more items than available in stock.
        """
        # Product pen only has 2 units in stock
        items_data = [{'product_id': self.product_pen.product_id, 'quantity': 5}]

        with self.assertRaises(ValidationError) as ctx:
            SalesService.process_checkout(
                user=self.cashier,
                items_data=items_data,
                customer_id=self.customer.customer_id
            )
        self.assertIn("Insufficient stock", str(ctx.exception))

        # Verify stock was not changed
        self.product_pen.refresh_from_db()
        self.assertEqual(self.product_pen.stock_qty, 2)
        # Verify no sale was committed
        self.assertEqual(Sale.objects.count(), 0)

    def test_out_of_stock_item_rejected(self):
        """Verifies an out-of-stock item cannot be purchased."""
        items_data = [{'product_id': self.product_out_of_stock.product_id, 'quantity': 1}]
        with self.assertRaises(ValidationError):
            SalesService.process_checkout(
                user=self.cashier,
                items_data=items_data
            )

    def test_atomic_checkout_success_and_stock_deduction(self):
        """
        Verifies complete checkout flow:
        - Sale master record created
        - SaleItem line item created
        - Stock quantity deducted
        - StockMovement audit log created
        - Payment record created
        """
        initial_stock = self.product_mug.stock_qty # 10
        qty_to_buy = 3

        items_data = [{'product_id': self.product_mug.product_id, 'quantity': qty_to_buy}]
        sale = SalesService.process_checkout(
            user=self.cashier,
            items_data=items_data,
            customer_id=self.customer.customer_id,
            discount=Decimal('2.00'),
            payment_method=PaymentMethod.CASH
        )

        self.assertIsNotNone(sale.sale_id)
        self.assertTrue(sale.transaction_no.startswith("GSMS-"))
        self.assertEqual(sale.subtotal, Decimal('45.00'))
        self.assertEqual(sale.discount, Decimal('2.00'))
        self.assertEqual(sale.total, Decimal('43.00'))
        self.assertEqual(sale.status, SaleStatus.COMPLETED)

        # 1. Verify stock deduction
        self.product_mug.refresh_from_db()
        self.assertEqual(self.product_mug.stock_qty, initial_stock - qty_to_buy) # 7

        # 2. Verify StockMovement audit log
        movement = StockMovement.objects.filter(product=self.product_mug, movement_type=MovementType.SOLD).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity, -qty_to_buy)
        self.assertEqual(movement.user, self.cashier)

        # 3. Verify Payment
        payment = Payment.objects.filter(sale=sale).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal('43.00'))
        self.assertEqual(payment.method, PaymentMethod.CASH)

    def test_price_locking_preserves_historical_records(self):
        """
        Verifies that when a product's price is updated in the catalog,
        past sale items retain their locked purchase price.
        """
        items_data = [{'product_id': self.product_mug.product_id, 'quantity': 1}]
        sale = SalesService.process_checkout(
            user=self.cashier,
            items_data=items_data
        )

        sale_item = sale.items.first()
        self.assertEqual(sale_item.unit_price, Decimal('15.00'))

        # Now change the product's price in the store
        self.product_mug.selling_price = Decimal('35.00')
        self.product_mug.save()

        # Re-fetch sale item from database
        sale_item.refresh_from_db()
        self.assertEqual(sale_item.unit_price, Decimal('15.00'))
        self.assertEqual(sale_item.line_total, Decimal('15.00'))


class InventoryServiceTests(TestCase):
    """
    Tests for inventory restock, manual adjustment, and threshold alerts.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='invstaff', role=UserRole.INVENTORY_STAFF, email='inv@test.com'
        )
        self.category = Category.objects.create(name='Toys')
        self.product = Product.objects.create(
            code='SKU-TOY-1',
            name='Plush Bear',
            category=self.category,
            cost_price=Decimal('10.00'),
            selling_price=Decimal('20.00'),
            stock_qty=5,
            reorder_level=5
        )

    def test_low_stock_property(self):
        """Verifies is_low_stock property flags products at or below reorder level."""
        self.assertTrue(self.product.is_low_stock)

        self.product.stock_qty = 6
        self.product.save()
        self.assertFalse(self.product.is_low_stock)

        self.product.stock_qty = 5
        self.product.save()
        self.assertTrue(self.product.is_low_stock)

    def test_record_stock_in(self):
        """Verifies restock increment and audit log."""
        InventoryService.record_stock_in(
            product_id=self.product.product_id,
            quantity=15,
            user=self.user,
            reason="Shipment PO-4402"
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_qty, 20)

        movement = StockMovement.objects.filter(product=self.product, movement_type=MovementType.RECEIVED).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity, 15)

    def test_adjust_stock(self):
        """Verifies physical count audit adjustment and delta logging."""
        InventoryService.adjust_stock(
            product_id=self.product.product_id,
            new_quantity=3,
            user=self.user,
            reason="Physical audit - 2 items damaged"
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_qty, 3)

        movement = StockMovement.objects.filter(product=self.product, movement_type=MovementType.ADJUSTED).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity, -2) # Delta: 3 - 5 = -2


class RBACViewAccessTests(TestCase):
    """
    Tests Role-Based Access Control on Views:
    Admin, Manager, Sales Staff, and Inventory Staff permissions.
    """

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_u', role=UserRole.ADMIN, email='a@t.com', password='pass'
        )
        self.sales = User.objects.create_user(
            username='sales_u', role=UserRole.SALES_STAFF, email='s@t.com', password='pass'
        )
        self.inventory = User.objects.create_user(
            username='inv_u', role=UserRole.INVENTORY_STAFF, email='i@t.com', password='pass'
        )

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_sales_staff_can_access_pos(self):
        self.client.login(username='sales_u', password='pass')
        response = self.client.get(reverse('pos_view'))
        self.assertEqual(response.status_code, 200)

    def test_sales_staff_cannot_access_user_management(self):
        """Sales staff should be denied access to RBAC user administration."""
        self.client.login(username='sales_u', password='pass')
        response = self.client.get(reverse('user_list'))
        # Should redirect back to dashboard with message
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_admin_can_access_user_management(self):
        self.client.login(username='admin_u', password='pass')
        response = self.client.get(reverse('user_list'))
        self.assertEqual(response.status_code, 200)
