"""
orders/serializers.py

DRF serializers for Sales Orders and Order Items with strict server-authoritative
pricing, workspace product validation, and immutable snapshots.
"""

from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from accounts.serializers import UserSerializer
from inventory.models import Product
from orders.models import Order, OrderItem

FORBIDDEN_CLIENT_PRICING_FIELDS = {
    'unit_price',
    'price',
    'product_name',
    'name',
    'product_sku',
    'sku',
    'line_total',
    'total',
    'estimated_total',
    'estimated_line_total',
    'live_product_price',
}


class OrderItemCreateSerializer(serializers.Serializer):
    """
    Accepts only product_id and quantity from client.
    Strictly rejects any client-submitted pricing, snapshot, or total fields.
    """
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data):
        # Reject unexpected pricing / total fields
        for field in FORBIDDEN_CLIENT_PRICING_FIELDS:
            if field in data:
                raise serializers.ValidationError({
                    field: f"Unexpected field '{field}'. Client cannot submit pricing, snapshot, or total fields."
                })
        return super().to_internal_value(data)


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Read-only representation of an OrderItem with snapshot fields, estimated pricing, and line_total.
    """
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    live_product_name = serializers.CharField(source='product.name', read_only=True)
    live_product_sku = serializers.CharField(source='product.sku', read_only=True)
    live_product_price = serializers.SerializerMethodField()
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    estimated_line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    def get_live_product_price(self, obj):
        try:
            if obj.product and getattr(obj.product, 'price', None) is not None:
                return str(obj.product.price)
        except Exception:
            pass
        return None

    class Meta:
        model = OrderItem
        fields = [
            'id',
            'product_id',
            'live_product_name',
            'live_product_sku',
            'live_product_price',
            'product_name',
            'product_sku',
            'unit_price',
            'quantity',
            'line_total',
            'estimated_line_total',
        ]
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):
    """
    Validates and creates an Order with multiple OrderItems.
    Enforces that every product belongs to the authorized workspace and is active.
    """
    items = OrderItemCreateSerializer(many=True, required=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def to_internal_value(self, data):
        for field in FORBIDDEN_CLIENT_PRICING_FIELDS:
            if field in data:
                raise serializers.ValidationError({
                    field: f"Unexpected field '{field}'. Client cannot submit order totals or pricing."
                })
        return super().to_internal_value(data)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("An order must contain at least one item.")

        workspace = self.context.get('workspace')
        seen_product_ids = set()
        validated_items = []

        for item_data in items:
            product_id = item_data['product_id']
            if product_id in seen_product_ids:
                raise serializers.ValidationError(
                    f"Duplicate product #{product_id} in order. Consolidate quantities into a single item."
                )
            seen_product_ids.add(product_id)

            # Verify product belongs to authorized workspace
            product = Product.objects.filter(pk=product_id, workspace=workspace).first()
            if not product:
                raise serializers.ValidationError(
                    f"Product #{product_id} does not exist in this workspace."
                )

            # Verify product is active
            if not product.is_active:
                raise serializers.ValidationError(
                    f"Product '{product.name}' (SKU: {product.sku}) is inactive and cannot be ordered."
                )

            validated_items.append({
                'product': product,
                'quantity': item_data['quantity'],
            })

        self.context['validated_product_items'] = validated_items
        return items

    @transaction.atomic
    def create(self, validated_data):
        workspace = self.context['workspace']
        user = self.context['request'].user
        notes = validated_data.get('notes', '')
        product_items = self.context['validated_product_items']

        order = Order.objects.create(
            workspace=workspace,
            created_by=user,
            notes=notes,
            status=Order.STATUS_PENDING,
        )

        for item in product_items:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
            )

        return order


class OrderSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for Orders including line items and server-computed total.
    """
    created_by = UserSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    estimated_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    workspace_name = serializers.CharField(source='workspace.name', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id',
            'workspace',
            'workspace_name',
            'created_by',
            'status',
            'notes',
            'items',
            'total',
            'estimated_total',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
