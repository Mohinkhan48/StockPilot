"""
inventory/serializers.py

DRF serializers for Product catalog, stock adjustments, and inventory movement audit logs.
"""

from decimal import Decimal
from django.db import transaction, IntegrityError
from rest_framework import serializers

from accounts.serializers import UserSerializer
from inventory.models import InventoryMovement, Product


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for Product model with workspace-scoped SKU validation.
    """

    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'name',
            'sku',
            'description',
            'price',
            'stock_quantity',
            'low_stock_threshold',
            'is_active',
            'is_low_stock',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'is_low_stock', 'created_at', 'updated_at']

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Product name cannot be blank.")
        return value.strip()

    def validate_sku(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("SKU cannot be blank.")
        return value.strip()

    def validate_price(self, value):
        if value < Decimal('0.00'):
            raise serializers.ValidationError("Price must be a non-negative decimal value.")
        return value

    def validate_stock_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock quantity cannot be negative.")
        return value

    def validate_low_stock_threshold(self, value):
        if value < 0:
            raise serializers.ValidationError("Low-stock threshold cannot be negative.")
        return value

    def validate(self, attrs):
        workspace = self.context.get('workspace')
        sku = attrs.get('sku', getattr(self.instance, 'sku', None))

        if workspace and sku:
            qs = Product.objects.filter(workspace=workspace, sku__iexact=sku)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'sku': f"A product with SKU '{sku}' already exists in this workspace."
                })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        workspace = self.context['workspace']
        request = self.context.get('request')
        actor = request.user if request and request.user.is_authenticated else None

        initial_stock = validated_data.get('stock_quantity', 0)

        product = Product.objects.create(workspace=workspace, **validated_data)

        # Record initial stock in the audit ledger if > 0
        if initial_stock > 0:
            InventoryMovement.objects.create(
                product=product,
                movement_type=InventoryMovement.MOVEMENT_RESTOCK,
                quantity=initial_stock,
                resulting_stock=initial_stock,
                notes="Initial stock upon product creation",
                created_by=actor,
            )

        return product


class RestockSerializer(serializers.Serializer):
    """
    Validates restock payload. Requires a positive quantity.
    """
    quantity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class StockAdjustmentSerializer(serializers.Serializer):
    """
    Validates manual stock adjustment payload.
    Quantity can be positive or negative (non-zero).
    Notes/reason is mandatory.
    """
    quantity = serializers.IntegerField()
    notes = serializers.CharField(required=True, allow_blank=False, min_length=3)

    def validate_quantity(self, value):
        if value == 0:
            raise serializers.ValidationError("Adjustment quantity cannot be zero.")
        return value

    def validate_notes(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("A reason/note is required for stock adjustments.")
        return value.strip()


class InventoryMovementSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for the append-only InventoryMovement ledger.
    """
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = InventoryMovement
        fields = [
            'id',
            'product',
            'product_name',
            'product_sku',
            'movement_type',
            'quantity',
            'resulting_stock',
            'notes',
            'created_by',
            'order',
            'created_at',
        ]
        read_only_fields = fields
