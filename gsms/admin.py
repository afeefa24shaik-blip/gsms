from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Category, Product, Supplier, Customer,
    Sale, SaleItem, Payment, StockMovement
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('user_id', 'username', 'name', 'email', 'role', 'active', 'is_staff')
    list_filter = ('role', 'active', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('GSMS Role & Permissions', {'fields': ('role', 'name', 'active')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('GSMS Role & Permissions', {'fields': ('role', 'name', 'email', 'active')}),
    )
    search_fields = ('username', 'name', 'email')
    ordering = ('user_id',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('category_id', 'name', 'created_at')
    search_fields = ('name',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('supplier_id', 'name', 'phone', 'email', 'created_at')
    search_fields = ('name', 'phone', 'email')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_id', 'name', 'phone', 'email', 'created_at')
    search_fields = ('name', 'phone', 'email')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'code', 'name', 'category', 'cost_price', 'selling_price', 'stock_qty', 'reorder_level', 'active')
    list_filter = ('category', 'active')
    search_fields = ('code', 'name')
    list_editable = ('selling_price', 'reorder_level')


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('unit_price', 'line_total')


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('sale_id', 'transaction_no', 'user', 'customer', 'sale_date', 'subtotal', 'discount', 'total', 'status')
    list_filter = ('status', 'sale_date')
    search_fields = ('transaction_no', 'customer__name', 'user__username')
    inlines = [SaleItemInline, PaymentInline]
    readonly_fields = ('transaction_no', 'sale_date', 'subtotal', 'discount', 'total')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('movement_id', 'product', 'movement_type', 'quantity', 'user', 'date', 'reason')
    list_filter = ('movement_type', 'date')
    search_fields = ('product__name', 'product__code', 'reason')
    readonly_fields = ('date',)
