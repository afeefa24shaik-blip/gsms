import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings


class UserRole(models.TextChoices):
    ADMIN = 'Admin', 'Admin'
    MANAGER = 'Manager', 'Manager'
    SALES_STAFF = 'Sales Staff', 'Sales Staff'
    INVENTORY_STAFF = 'Inventory Staff', 'Inventory Staff'


class User(AbstractUser):
    """
    Custom User entity extending Django's AbstractUser.
    Primary key: user_id
    Role-Based Access Control (RBAC): Admin, Manager, Sales Staff (Cashier), Inventory Staff.
    """
    user_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150, verbose_name="Full Name")
    email = models.EmailField(unique=True, verbose_name="Email Address")
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.SALES_STAFF,
        verbose_name="System Role",
        help_text="Designates permission tier across POS, Inventory, and Analytics."
    )
    active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Designates whether this user account is active."
    )

    REQUIRED_FIELDS = ['name', 'email']

    class Meta:
        db_table = 'gsms_users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['user_id']

    def save(self, *args, **kwargs):
        # Keep active and is_active in sync
        self.is_active = self.active
        if not self.name and (self.first_name or self.last_name):
            self.name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)

    @property
    def is_admin_role(self):
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_manager_role(self):
        return self.role in [UserRole.ADMIN, UserRole.MANAGER] or self.is_superuser

    @property
    def is_sales_role(self):
        return self.role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.SALES_STAFF] or self.is_superuser

    @property
    def is_inventory_role(self):
        return self.role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.INVENTORY_STAFF] or self.is_superuser

    def __str__(self):
        return f"{self.name or self.username} ({self.role})"


class Category(models.Model):
    """
    Product Category entity (e.g., Toys, Mugs, Handmade Crafts, Greeting Cards, Souvenirs).
    """
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, verbose_name="Category Name")
    description = models.TextField(blank=True, verbose_name="Description")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gsms_categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def product_count(self):
        return self.products.filter(active=True).count()


class Supplier(models.Model):
    """
    Supplier entity for stocking and replenishment.
    """
    supplier_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150, verbose_name="Supplier Name")
    phone = models.CharField(max_length=30, verbose_name="Phone Number")
    email = models.EmailField(verbose_name="Email Address")
    address = models.TextField(blank=True, verbose_name="Physical Address")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gsms_suppliers'
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Customer(models.Model):
    """
    Customer entity for tracking sales history, loyalty, and contact details.
    """
    customer_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150, verbose_name="Customer Name")
    phone = models.CharField(max_length=30, verbose_name="Phone Number")
    email = models.EmailField(blank=True, null=True, verbose_name="Email (Optional)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'gsms_customers'
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - {self.phone}"


class Product(models.Model):
    """
    Product entity representing inventory items in the Gift Shop.
    Tracks SKU/code, pricing, stock count, and low-stock reorder thresholds.
    """
    product_id = models.AutoField(primary_key=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        db_column='category_id',
        verbose_name="Category"
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        db_column='supplier_id',
        verbose_name="Primary Supplier"
    )
    code = models.CharField(max_length=50, unique=True, verbose_name="Product SKU / Barcode")
    name = models.CharField(max_length=200, verbose_name="Product Name")
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Cost Price"
    )
    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Selling Price"
    )
    stock_qty = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Stock Quantity"
    )
    reorder_level = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        verbose_name="Reorder Level (Alert Threshold)"
    )
    active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'gsms_products'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
            models.Index(fields=['stock_qty']),
        ]

    def __str__(self):
        return f"[{self.code}] {self.name} (${self.selling_price})"

    @property
    def is_low_stock(self):
        """Returns True if stock quantity is at or below the reorder alert level."""
        return self.stock_qty <= self.reorder_level

    @property
    def is_out_of_stock(self):
        return self.stock_qty <= 0

    @property
    def profit_margin(self):
        """Computes markup profit per unit."""
        return self.selling_price - self.cost_price


class SaleStatus(models.TextChoices):
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'
    REFUNDED = 'refunded', 'Refunded'


class Sale(models.Model):
    """
    Sale entity recording master transaction metadata, cashier, customer, and financials.
    """
    sale_id = models.AutoField(primary_key=True)
    transaction_no = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        verbose_name="Transaction Number"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sales',
        db_column='user_id',
        verbose_name="Cashier / Sales Staff"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        db_column='customer_id',
        verbose_name="Customer (Optional)"
    )
    sale_date = models.DateTimeField(default=timezone.now, verbose_name="Sale Date")
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Subtotal"
    )
    discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Discount Amount"
    )
    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Grand Total"
    )
    status = models.CharField(
        max_length=20,
        choices=SaleStatus.choices,
        default=SaleStatus.COMPLETED,
        verbose_name="Sale Status"
    )

    class Meta:
        db_table = 'gsms_sales'
        verbose_name = 'Sale'
        verbose_name_plural = 'Sales'
        ordering = ['-sale_date']
        indexes = [
            models.Index(fields=['transaction_no']),
            models.Index(fields=['sale_date']),
        ]

    def __str__(self):
        return f"{self.transaction_no} - ${self.total} ({self.status})"

    @staticmethod
    def generate_transaction_no():
        date_str = timezone.now().strftime('%Y%m%d')
        unique_token = uuid.uuid4().hex[:6].upper()
        return f"GSMS-{date_str}-{unique_token}"


class SaleItem(models.Model):
    """
    Line item for each sale.
    Enforces historical unit_price locking at checkout time so future product price
    changes do not alter past financial audits.
    """
    sale_item_id = models.AutoField(primary_key=True)
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='items',
        db_column='sale_id',
        verbose_name="Sale Reference"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='sale_items',
        db_column='product_id',
        verbose_name="Product"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Quantity"
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Unit Price (Locked)"
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Line Total"
    )

    class Meta:
        db_table = 'gsms_sale_items'
        verbose_name = 'Sale Item'
        verbose_name_plural = 'Sale Items'
        ordering = ['sale_item_id']

    def save(self, *args, **kwargs):
        # Always recalculate line total before saving
        self.line_total = (Decimal(self.quantity) * Decimal(self.unit_price)).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} x {self.quantity} @ ${self.unit_price}"


class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    CARD = 'card', 'Credit/Debit Card'
    MOBILE = 'mobile', 'Mobile Wallet'
    OTHER = 'other', 'Other'


class PaymentStatus(models.TextChoices):
    PAID = 'paid', 'Paid'
    PENDING = 'pending', 'Pending'
    REFUNDED = 'refunded', 'Refunded'


class Payment(models.Model):
    """
    Payment entity recording tender method, amount, and reconciliation status.
    """
    payment_id = models.AutoField(primary_key=True)
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='payments',
        db_column='sale_id',
        verbose_name="Sale Reference"
    )
    method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="Payment Method"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Tendered Amount"
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PAID,
        verbose_name="Payment Status"
    )
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="Payment Date")

    class Meta:
        db_table = 'gsms_payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-payment_date']

    def __str__(self):
        return f"Payment #{self.payment_id} for {self.sale.transaction_no}: ${self.amount} via {self.method}"


class MovementType(models.TextChoices):
    RECEIVED = 'received', 'Received (Restock)'
    SOLD = 'sold', 'Sold (POS Checkout)'
    RETURNED = 'returned', 'Returned (Customer Return)'
    ADJUSTED = 'adjusted', 'Adjusted (Audit / Damage)'


class StockMovement(models.Model):
    """
    Audit log tracking all changes in inventory levels.
    Logs who changed what, why, when, and by how many units.
    """
    movement_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='stock_movements',
        db_column='product_id',
        verbose_name="Product"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='stock_movements',
        db_column='user_id',
        verbose_name="Action Taken By"
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
        verbose_name="Movement Type"
    )
    quantity = models.IntegerField(
        help_text="Signed quantity (+ for addition, - for reduction)",
        verbose_name="Quantity Delta"
    )
    date = models.DateTimeField(default=timezone.now, verbose_name="Movement Timestamp")
    reason = models.CharField(max_length=255, blank=True, verbose_name="Audit Reason / Note")

    class Meta:
        db_table = 'gsms_stock_movements'
        verbose_name = 'Stock Movement'
        verbose_name_plural = 'Stock Movements'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['movement_type']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        sign = "+" if self.quantity > 0 else ""
        return f"[{self.date.strftime('%Y-%m-%d %H:%M')}] {self.product.name} {sign}{self.quantity} ({self.movement_type})"
