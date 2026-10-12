from django.contrib import admin

from orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model  = OrderItem
    extra  = 0
    fields = ('product', 'product_name', 'product_sku', 'unit_price', 'quantity')
    readonly_fields = ('product_name', 'product_sku', 'unit_price')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display  = ('id', 'workspace', 'created_by', 'status', 'created_at', 'updated_at')
    list_filter   = ('status', 'workspace')
    search_fields = ('id', 'workspace__name', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at')
    inlines       = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display  = ('order', 'product', 'product_name', 'product_sku',
                     'unit_price', 'quantity')
    search_fields = ('product__sku', 'product_name', 'product_sku')
    readonly_fields = ('product_name', 'product_sku', 'unit_price')
