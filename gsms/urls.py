from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & Root
    path('', views.dashboard_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Point of Sale (POS) / Checkout
    path('pos/', views.pos_view, name='pos_view'),
    path('pos/checkout/', views.checkout_process_view, name='checkout_process'),
    path('pos/api/search/', views.api_search_products, name='api_search_products'),
    path('pos/receipt/<int:sale_id>/', views.receipt_view, name='receipt_view'),

    # Product & Inventory Management
    path('products/', views.product_list_view, name='product_list'),
    path('products/create/', views.product_create_view, name='product_create'),
    path('products/<int:product_id>/edit/', views.product_update_view, name='product_edit'),
    path('products/<int:product_id>/stock-in/', views.stock_in_view, name='stock_in'),
    path('products/<int:product_id>/stock-adjust/', views.stock_adjust_view, name='stock_adjust'),
    path('inventory/movements/', views.stock_movement_list_view, name='stock_movements'),

    # Supporting Entities
    path('categories/', views.category_list_view, name='category_list'),
    path('suppliers/', views.supplier_list_view, name='supplier_list'),
    path('customers/', views.customer_list_view, name='customer_list'),

    # Reports & Business Intelligence
    path('reports/sales/', views.sales_report_view, name='sales_report'),
    path('reports/inventory/', views.inventory_report_view, name='inventory_report'),

    # User Management (RBAC Admin)
    path('users/', views.user_list_view, name='user_list'),
    path('users/create/', views.user_create_view, name='user_create'),
    path('users/<int:user_id>/toggle/', views.user_toggle_status_view, name='user_toggle_status'),
]
