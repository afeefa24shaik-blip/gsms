import json
from decimal import Decimal
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    User, Product, Category, Supplier, Customer,
    Sale, SaleItem, Payment, StockMovement,
    UserRole, MovementType, PaymentMethod, SaleStatus
)
from .forms import (
    LoginForm, ProductForm, CategoryForm, SupplierForm, CustomerForm,
    StockInForm, StockAdjustmentForm, UserCreationCustomForm, SalesReportFilterForm
)
from .services import SalesService, InventoryService, ReportService
from .decorators import (
    role_required, admin_required, manager_required,
    sales_required, inventory_required
)


# =====================================================================
# AUTHENTICATION & USER MANAGEMENT
# =====================================================================

def login_view(request):
    """
    Renders login page and authenticates users via username or email.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data['user']
            login(request, user)
            messages.success(request, f"Welcome back, {user.name or user.username}! Logged in as {user.role}.")
            next_url = request.GET.get('next') or 'dashboard'
            return redirect(next_url)
    else:
        form = LoginForm()

    return render(request, 'gsms/auth/login.html', {'form': form})


@login_required
def logout_view(request):
    """
    Terminates user session and redirects to login screen.
    """
    user_name = request.user.name or request.user.username
    logout(request)
    messages.info(request, f"Goodbye {user_name}! You have been securely logged out.")
    return redirect('login')


@login_required
@admin_required
def user_list_view(request):
    """
    Lists system users with their assigned roles and statuses (Admin only).
    """
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'gsms/users/user_list.html', {'users': users})


@login_required
@admin_required
def user_create_view(request):
    """
    Allows Admin to create new staff members with role assignment.
    """
    if request.method == 'POST':
        form = UserCreationCustomForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Staff member '{user.name}' ({user.role}) created successfully.")
            return redirect('user_list')
    else:
        form = UserCreationCustomForm()

    return render(request, 'gsms/users/user_form.html', {'form': form, 'title': 'Register New Employee'})


@login_required
@admin_required
@require_POST
def user_toggle_status_view(request, user_id):
    """
    Toggles user active status (Admin only).
    """
    target_user = get_object_or_404(User, user_id=user_id)
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('user_list')

    target_user.active = not target_user.active
    target_user.save()
    status_str = "activated" if target_user.active else "deactivated"
    messages.success(request, f"User {target_user.username} has been {status_str}.")
    return redirect('user_list')


# =====================================================================
# DASHBOARD
# =====================================================================

@login_required
def dashboard_view(request):
    """
    Main Executive & Operational Dashboard tailored to user roles.
    Presents sales velocity, revenue metrics, stock threshold alerts, and charts.
    """
    metrics = ReportService.get_dashboard_metrics()
    low_stock_products = InventoryService.get_low_stock_products()[:8]
    inventory_summary = InventoryService.get_inventory_summary()

    context = {
        'metrics': metrics,
        'low_stock_products': low_stock_products,
        'inventory_summary': inventory_summary,
        'daily_trends_json': json.dumps(metrics['daily_trends']),
    }
    return render(request, 'gsms/dashboard/dashboard.html', context)


# =====================================================================
# POINT OF SALE (POS) / BILLING & CHECKOUT
# =====================================================================

@login_required
@sales_required
def pos_view(request):
    """
    Core POS / Billing screen for high-efficiency cashier checkout.
    Provides fast product search, stock limit checks, discount application,
    quick customer selection, and payment tendering.
    """
    categories = Category.objects.all().order_by('name')
    customers = Customer.objects.all().order_by('name')
    # Preload top active products for quick tap
    quick_products = Product.objects.filter(active=True).select_related('category').order_by('name')[:30]

    context = {
        'categories': categories,
        'customers': customers,
        'quick_products': quick_products,
        'payment_methods': PaymentMethod.choices,
    }
    return render(request, 'gsms/pos/billing.html', context)


@login_required
@sales_required
@require_GET
def api_search_products(request):
    """
    AJAX endpoint for instant product search by code, name, or category in POS.
    """
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category_id')

    qs = Product.objects.filter(active=True)

    if category_id:
        qs = qs.filter(category_id=category_id)

    if query:
        qs = qs.filter(
            models.Q(code__icontains=query) |
            models.Q(name__icontains=query) |
            models.Q(category__name__icontains=query)
        )

    products = qs.select_related('category')[:25]
    results = [
        {
            'product_id': p.product_id,
            'code': p.code,
            'name': p.name,
            'category': p.category.name if p.category else '',
            'selling_price': float(p.selling_price),
            'stock_qty': p.stock_qty,
            'is_low_stock': p.is_low_stock,
            'is_out_of_stock': p.is_out_of_stock,
        }
        for p in products
    ]
    return JsonResponse({'results': results})


@login_required
@sales_required
@require_POST
def checkout_process_view(request):
    """
    Processes checkout submissions (supporting JSON payloads or form submissions).
    Calls SalesService.process_checkout to guarantee atomic transaction handling.
    """
    try:
        # Check if request has JSON payload
        if request.content_type == 'application/json':
            payload = json.loads(request.body.decode('utf-8'))
        else:
            payload = {
                'items': json.loads(request.POST.get('items_json', '[]')),
                'customer_id': request.POST.get('customer_id') or None,
                'discount': request.POST.get('discount', '0.00'),
                'payment_method': request.POST.get('payment_method', PaymentMethod.CASH),
            }

        items_data = payload.get('items', [])
        customer_id = payload.get('customer_id') or None
        discount = Decimal(str(payload.get('discount', '0.00') or 0))
        payment_method = payload.get('payment_method', PaymentMethod.CASH)

        # Execute business logic in service layer
        sale = SalesService.process_checkout(
            user=request.user,
            items_data=items_data,
            customer_id=customer_id,
            discount=discount,
            payment_method=payment_method
        )

        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'sale_id': sale.sale_id,
                'transaction_no': sale.transaction_no,
                'total': float(sale.total),
                'receipt_url': f"/pos/receipt/{sale.sale_id}/"
            })
        else:
            messages.success(request, f"Transaction {sale.transaction_no} completed successfully!")
            return redirect('receipt_view', sale_id=sale.sale_id)

    except ValidationError as e:
        error_msg = e.messages[0] if hasattr(e, 'messages') else str(e)
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
        messages.error(request, f"Checkout Failed: {error_msg}")
        return redirect('pos_view')
    except Exception as e:
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        messages.error(request, f"Unexpected error during checkout: {str(e)}")
        return redirect('pos_view')


@login_required
def receipt_view(request, sale_id):
    """
    Renders receipt view optimized for on-screen viewing and clean thermal/A4 printing.
    """
    sale = get_object_or_404(
        Sale.objects.select_related('user', 'customer').prefetch_related('items__product', 'payments'),
        sale_id=sale_id
    )
    payment = sale.payments.first()

    context = {
        'sale': sale,
        'items': sale.items.all(),
        'payment': payment,
    }
    return render(request, 'gsms/pos/receipt.html', context)


# =====================================================================
# PRODUCT & INVENTORY MANAGEMENT
# =====================================================================

@login_required
@inventory_required
def product_list_view(request):
    """
    Lists products with live inventory levels, low-stock warnings, and search filters.
    """
    category_id = request.GET.get('category')
    filter_status = request.GET.get('status')
    search_query = request.GET.get('search', '').strip()

    products = Product.objects.select_related('category', 'supplier').all()

    if category_id:
        products = products.filter(category_id=category_id)

    if filter_status == 'low_stock':
        products = products.filter(stock_qty__lte=models.F('reorder_level'), stock_qty__gt=0)
    elif filter_status == 'out_of_stock':
        products = products.filter(stock_qty__lte=0)
    elif filter_status == 'active':
        products = products.filter(active=True)
    elif filter_status == 'inactive':
        products = products.filter(active=False)

    if search_query:
        products = products.filter(
            models.Q(name__icontains=search_query) |
            models.Q(code__icontains=search_query)
        )

    categories = Category.objects.all()

    context = {
        'products': products.order_by('name'),
        'categories': categories,
        'selected_category': int(category_id) if category_id else None,
        'selected_status': filter_status,
        'search_query': search_query,
    }
    return render(request, 'gsms/products/product_list.html', context)


@login_required
@manager_required
def product_create_view(request):
    """
    Create a new product catalog item.
    """
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            # If initial stock was given, log initial movement
            if product.stock_qty > 0:
                StockMovement.objects.create(
                    product=product,
                    user=request.user,
                    movement_type=MovementType.RECEIVED,
                    quantity=product.stock_qty,
                    date=timezone.now(),
                    reason="Initial Stock Onboarding"
                )
            messages.success(request, f"Product '{product.name}' created successfully.")
            return redirect('product_list')
    else:
        form = ProductForm()

    return render(request, 'gsms/products/product_form.html', {'form': form, 'title': 'Add New Gift Item'})


@login_required
@manager_required
def product_update_view(request, product_id):
    """
    Edit existing product details.
    """
    product = get_object_or_404(Product, product_id=product_id)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.name}' updated successfully.")
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)

    return render(request, 'gsms/products/product_form.html', {'form': form, 'title': f'Edit {product.name}', 'product': product})


@login_required
@inventory_required
def stock_in_view(request, product_id):
    """
    Receives restock shipment for a product.
    """
    product = get_object_or_404(Product, product_id=product_id)
    if request.method == 'POST':
        form = StockInForm(request.POST)
        if form.is_valid():
            qty = form.cleaned_data['quantity']
            supplier = form.cleaned_data['supplier']
            cost = form.cleaned_data['cost_price']
            reason = form.cleaned_data['reason']

            InventoryService.record_stock_in(
                product_id=product.product_id,
                quantity=qty,
                user=request.user,
                supplier_id=supplier.supplier_id if supplier else None,
                cost_price=cost,
                reason=reason
            )
            messages.success(request, f"Successfully restocked +{qty} units of '{product.name}'. New stock: {product.stock_qty + qty}")
            return redirect('product_list')
    else:
        form = StockInForm(initial={'cost_price': product.cost_price, 'supplier': product.supplier})

    return render(request, 'gsms/products/stock_in.html', {'form': form, 'product': product})


@login_required
@inventory_required
def stock_adjust_view(request, product_id):
    """
    Audit adjustment for stock counts.
    """
    product = get_object_or_404(Product, product_id=product_id)
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            new_qty = form.cleaned_data['new_quantity']
            reason = form.cleaned_data['reason']

            InventoryService.adjust_stock(
                product_id=product.product_id,
                new_quantity=new_qty,
                user=request.user,
                reason=reason
            )
            messages.success(request, f"Stock for '{product.name}' updated to {new_qty} units.")
            return redirect('product_list')
    else:
        form = StockAdjustmentForm(initial={'new_quantity': product.stock_qty})

    return render(request, 'gsms/products/stock_adjust.html', {'form': form, 'product': product})


@login_required
@inventory_required
def stock_movement_list_view(request):
    """
    Displays full audit history of all inventory movements.
    """
    movements = StockMovement.objects.select_related('product', 'user').all().order_by('-date')[:100]
    return render(request, 'gsms/inventory/movement_list.html', {'movements': movements})


# =====================================================================
# CATEGORIES & SUPPLIERS & CUSTOMERS
# =====================================================================

@login_required
@inventory_required
def category_list_view(request):
    categories = Category.objects.all().order_by('name')
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "New category added successfully.")
            return redirect('category_list')
    else:
        form = CategoryForm()

    return render(request, 'gsms/categories/category_list.html', {'categories': categories, 'form': form})


@login_required
@inventory_required
def supplier_list_view(request):
    suppliers = Supplier.objects.all().order_by('name')
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "New supplier added successfully.")
            return redirect('supplier_list')
    else:
        form = SupplierForm()

    return render(request, 'gsms/suppliers/supplier_list.html', {'suppliers': suppliers, 'form': form})


@login_required
@sales_required
def customer_list_view(request):
    customers = Customer.objects.all().order_by('name')
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': True, 'customer_id': customer.customer_id, 'name': customer.name, 'phone': customer.phone})
            messages.success(request, "Customer saved successfully.")
            return redirect('customer_list')
    else:
        form = CustomerForm()

    return render(request, 'gsms/customers/customer_list.html', {'customers': customers, 'form': form})


# =====================================================================
# REPORTS & ANALYTICS
# =====================================================================

@login_required
@manager_required
def sales_report_view(request):
    """
    Comprehensive sales report with date range filters, staff breakdown, and tender metrics.
    """
    form = SalesReportFilterForm(request.GET or None)
    start_date = None
    end_date = None
    cashier_id = None

    if form.is_valid():
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        cashier = form.cleaned_data.get('cashier')
        if cashier:
            cashier_id = cashier.user_id

    report_data = ReportService.get_sales_report(
        start_date=start_date,
        end_date=end_date,
        user_id=cashier_id
    )

    context = {
        'form': form,
        'report': report_data,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'gsms/reports/sales_report.html', context)


@login_required
@manager_required
def inventory_report_view(request):
    """
    Inventory valuation, low stock and stock health report.
    """
    summary = InventoryService.get_inventory_summary()
    low_stock_products = InventoryService.get_low_stock_products()
    all_products = Product.objects.select_related('category', 'supplier').all().order_by('stock_qty')

    context = {
        'summary': summary,
        'low_stock_products': low_stock_products,
        'all_products': all_products,
    }
    return render(request, 'gsms/reports/inventory_report.html', context)
