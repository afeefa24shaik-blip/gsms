"""
Seed command for Gift Shop Management System.
Populates role users, categories, suppliers, customers, products, and sample sales.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from gsms.models import (
    User, UserRole, Category, Supplier, Customer, Product,
    Sale, SaleItem, Payment, StockMovement, MovementType, PaymentMethod, PaymentStatus
)
from gsms.services import SalesService


class Command(BaseCommand):
    help = 'Seeds initial gift shop demo data including staff roles, catalog, and transactions'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding GSMS demo data..."))

        # 1. Create Users for all RBAC Roles
        users_spec = [
            {'username': 'admin', 'name': 'Eleanor Vance (Admin)', 'email': 'admin@luxegifts.com', 'role': UserRole.ADMIN, 'is_staff': True, 'is_superuser': True},
            {'username': 'manager', 'name': 'Marcus Brody (Store Manager)', 'email': 'manager@luxegifts.com', 'role': UserRole.MANAGER, 'is_staff': True, 'is_superuser': False},
            {'username': 'cashier', 'name': 'Chloe Bennet (Sales Cashier)', 'email': 'cashier@luxegifts.com', 'role': UserRole.SALES_STAFF, 'is_staff': False, 'is_superuser': False},
            {'username': 'inventory', 'name': 'David Miller (Inventory Specialist)', 'email': 'inventory@luxegifts.com', 'role': UserRole.INVENTORY_STAFF, 'is_staff': False, 'is_superuser': False},
        ]

        created_users = {}
        for udata in users_spec:
            user, created = User.objects.get_or_create(
                username=udata['username'],
                defaults={
                    'name': udata['name'],
                    'email': udata['email'],
                    'role': udata['role'],
                    'is_staff': udata['is_staff'],
                    'is_superuser': udata['is_superuser'],
                    'active': True
                }
            )
            # Standard password for demo accounts
            user.set_password(f"{udata['username']}123")
            user.save()
            created_users[udata['username']] = user
            status_text = "Created" if created else "Updated"
            self.stdout.write(f"  - {status_text} user: {user.username} ({user.role})")

        # 2. Create Categories
        categories_data = [
            ("Ceramic Mugs & Drinkware", "Handmade glazed mugs, tumblers, and artisan tea sets"),
            ("Artisan Candles & Scents", "Organic soy wax scented candles and room diffusers"),
            ("Souvenirs & Keepsakes", "Local city snow globes, engraved magnets, and enamel pins"),
            ("Plush Toys & Figurines", "Hand-stitched teddy bears and novelty mini figurines"),
            ("Handmade Greeting Cards", "Letterpress and foil-stamped greeting cards with envelopes"),
            ("Jewelry & Accessories", "Handcrafted sterling silver pendants, charm bracelets, and leather keychains"),
        ]
        created_categories = {}
        for name, desc in categories_data:
            cat, _ = Category.objects.get_or_create(name=name, defaults={'description': desc})
            created_categories[name] = cat

        # 3. Create Suppliers
        suppliers_data = [
            ("Artisan Pottery Guild", "+1 (555) 234-5678", "orders@potteryguild.com", "45 Clay Street, Portland, OR"),
            ("AromaCraft Botanicals", "+1 (555) 345-6789", "sales@aromacraft.com", "88 Lavender Way, Seattle, WA"),
            ("Keepsake Souvenirs Co.", "+1 (555) 456-7890", "info@keepsakes.com", "12 Landmark Blvd, Chicago, IL"),
            ("CuddleCraft Toys Ltd.", "+1 (555) 567-8901", "distrib@cuddlecraft.com", "77 Plush Lane, Denver, CO"),
        ]
        created_suppliers = []
        for sname, sphone, semail, saddr in suppliers_data:
            sup, _ = Supplier.objects.get_or_create(
                name=sname,
                defaults={'phone': sphone, 'email': semail, 'address': saddr}
            )
            created_suppliers.append(sup)

        # 4. Create Customers
        customers_data = [
            ("Sophia Adams", "+1 (555) 111-2233", "sophia.adams@example.com"),
            ("Liam Wilson", "+1 (555) 222-3344", "liam.w@example.com"),
            ("Emma Watson", "+1 (555) 333-4455", "emma.watson@example.com"),
            ("Noah Taylor", "+1 (555) 444-5566", None),
        ]
        created_customers = []
        for cname, cphone, cemail in customers_data:
            cust, _ = Customer.objects.get_or_create(
                name=cname,
                phone=cphone,
                defaults={'email': cemail}
            )
            created_customers.append(cust)

        # 5. Create Products
        products_data = [
            {
                'code': 'SKU-MUG-001',
                'name': 'Midnight Glaze Artisan Ceramic Mug',
                'category': created_categories["Ceramic Mugs & Drinkware"],
                'supplier': created_suppliers[0],
                'cost_price': Decimal('8.50'),
                'selling_price': Decimal('22.00'),
                'stock_qty': 45,
                'reorder_level': 10,
            },
            {
                'code': 'SKU-MUG-002',
                'name': 'Pastel Speckle Espresso Cup Set (Pair)',
                'category': created_categories["Ceramic Mugs & Drinkware"],
                'supplier': created_suppliers[0],
                'cost_price': Decimal('12.00'),
                'selling_price': Decimal('28.50'),
                'stock_qty': 8,  # Low stock!
                'reorder_level': 10,
            },
            {
                'code': 'SKU-CNDL-101',
                'name': 'Smoked Amber & Sandalwood Soy Candle',
                'category': created_categories["Artisan Candles & Scents"],
                'supplier': created_suppliers[1],
                'cost_price': Decimal('6.00'),
                'selling_price': Decimal('18.00'),
                'stock_qty': 30,
                'reorder_level': 8,
            },
            {
                'code': 'SKU-CNDL-102',
                'name': 'French Lavender & Wild Fig Aromatherapy Candle',
                'category': created_categories["Artisan Candles & Scents"],
                'supplier': created_suppliers[1],
                'cost_price': Decimal('7.00'),
                'selling_price': Decimal('19.50'),
                'stock_qty': 4,  # Low stock!
                'reorder_level': 6,
            },
            {
                'code': 'SKU-SVN-201',
                'name': 'Gilded Skyline Snow Globe',
                'category': created_categories["Souvenirs & Keepsakes"],
                'supplier': created_suppliers[2],
                'cost_price': Decimal('11.00'),
                'selling_price': Decimal('29.00'),
                'stock_qty': 18,
                'reorder_level': 5,
            },
            {
                'code': 'SKU-SVN-202',
                'name': 'Vintage Brass Compass Keychain',
                'category': created_categories["Souvenirs & Keepsakes"],
                'supplier': created_suppliers[2],
                'cost_price': Decimal('3.50'),
                'selling_price': Decimal('12.00'),
                'stock_qty': 60,
                'reorder_level': 15,
            },
            {
                'code': 'SKU-TOY-301',
                'name': 'Heritage Stitched Velvet Bear (Brown)',
                'category': created_categories["Plush Toys & Figurines"],
                'supplier': created_suppliers[3],
                'cost_price': Decimal('14.00'),
                'selling_price': Decimal('34.00'),
                'stock_qty': 12,
                'reorder_level': 5,
            },
            {
                'code': 'SKU-TOY-302',
                'name': 'Hand-Carved Wooden Music Box (Forest Melody)',
                'category': created_categories["Plush Toys & Figurines"],
                'supplier': created_suppliers[3],
                'cost_price': Decimal('18.00'),
                'selling_price': Decimal('42.00'),
                'stock_qty': 0,  # Out of stock!
                'reorder_level': 5,
            },
            {
                'code': 'SKU-CRD-401',
                'name': 'Gold Foil Botanical Birthday Greeting Card',
                'category': created_categories["Handmade Greeting Cards"],
                'supplier': created_suppliers[2],
                'cost_price': Decimal('1.20'),
                'selling_price': Decimal('5.50'),
                'stock_qty': 120,
                'reorder_level': 25,
            },
            {
                'code': 'SKU-JWL-501',
                'name': 'Hand-Hammered Silver Teardrop Necklace',
                'category': created_categories["Jewelry & Accessories"],
                'supplier': created_suppliers[0],
                'cost_price': Decimal('22.00'),
                'selling_price': Decimal('58.00'),
                'stock_qty': 15,
                'reorder_level': 5,
            },
        ]

        created_products = []
        for pdata in products_data:
            p, created = Product.objects.get_or_create(
                code=pdata['code'],
                defaults=pdata
            )
            created_products.append(p)
            if created and p.stock_qty > 0:
                StockMovement.objects.create(
                    product=p,
                    user=created_users['admin'],
                    movement_type=MovementType.RECEIVED,
                    quantity=p.stock_qty,
                    date=timezone.now(),
                    reason="Initial Catalog Stocking"
                )

        # 6. Create Initial Demo Sales via SalesService
        self.stdout.write("  - Creating sample completed checkout transactions...")
        cashier_user = created_users['cashier']

        sample_transactions = [
            {
                'items': [
                    {'product_id': created_products[0].product_id, 'quantity': 1},
                    {'product_id': created_products[2].product_id, 'quantity': 2},
                ],
                'customer_id': created_customers[0].customer_id,
                'discount': Decimal('5.00'),
                'payment_method': PaymentMethod.CARD,
            },
            {
                'items': [
                    {'product_id': created_products[4].product_id, 'quantity': 1},
                    {'product_id': created_products[5].product_id, 'quantity': 1},
                    {'product_id': created_products[8].product_id, 'quantity': 2},
                ],
                'customer_id': created_customers[1].customer_id,
                'discount': Decimal('0.00'),
                'payment_method': PaymentMethod.CASH,
            },
            {
                'items': [
                    {'product_id': created_products[6].product_id, 'quantity': 1},
                ],
                'customer_id': None,
                'discount': Decimal('0.00'),
                'payment_method': PaymentMethod.MOBILE,
            },
        ]

        for s_spec in sample_transactions:
            sale = SalesService.process_checkout(
                user=cashier_user,
                items_data=s_spec['items'],
                customer_id=s_spec['customer_id'],
                discount=s_spec['discount'],
                payment_method=s_spec['payment_method']
            )
            self.stdout.write(f"    * Generated Sale {sale.transaction_no} (${sale.total})")

        self.stdout.write(self.style.SUCCESS("Demo data successfully seeded for LuxeGifts Studio & Boutique!"))
