from django.contrib import admin

from inventory.models import InventoryMovement, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ('sku', 'name', 'workspace', 'price', 'stock_quantity',
                     'low_stock_threshold', 'is_active', 'updated_at')
    list_filter   = ('workspace', 'is_active')
    search_fields = ('sku', 'name', 'workspace__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    """Movements are append-only — the admin shows them read-only."""
    list_display  = ('product', 'movement_type', 'quantity', 'resulting_stock',
                     'created_by', 'order', 'created_at')
    list_filter   = ('movement_type', 'product__workspace')
    search_fields = ('product__sku', 'product__name', 'notes')
    readonly_fields = (
        'product', 'movement_type', 'quantity', 'resulting_stock',
        'notes', 'created_by', 'created_at', 'order',
    )

    def has_add_permission(self, request):
        return False   # movements are created only through service methods

    def has_change_permission(self, request, obj=None):
        return False   # enforce append-only in admin as well
