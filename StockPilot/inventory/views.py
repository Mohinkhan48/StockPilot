"""
inventory/views.py

DRF Views for Product catalog management, stock adjustments, low-stock reporting, and movement audit logs.
"""

from django.db import IntegrityError, models
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import filters, generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Workspace, WorkspaceMembership
from accounts.permissions import get_user_membership
from inventory.exceptions import InsufficientStockError
from inventory.models import InventoryMovement, Product
from inventory.serializers import (
    InventoryMovementSerializer,
    ProductSerializer,
    RestockSerializer,
    StockAdjustmentSerializer,
)


class WorkspaceContextMixin:
    """
    Mixin providing safe workspace resolution scoped strictly to the requesting user's memberships.
    Non-members receive 404 Not Found to prevent tenant discovery.
    """

    def get_workspace(self):
        workspace_id = self.kwargs.get('workspace_id')
        return get_object_or_404(
            Workspace.objects.filter(memberships__user=self.request.user),
            pk=workspace_id,
        )

    def check_owner_role(self, workspace):
        membership = get_user_membership(self.request.user, workspace)
        if not membership or membership.role != WorkspaceMembership.ROLE_OWNER:
            raise PermissionDenied("Only workspace owners have permission to perform this action.")


# ---------------------------------------------------------------------------
# Product Views
# ---------------------------------------------------------------------------

class ProductListCreateView(WorkspaceContextMixin, generics.ListCreateAPIView):
    """
    GET  /api/workspaces/<workspace_id>/products/ — List workspace products (with search, filtering, ordering).
    POST /api/workspaces/<workspace_id>/products/ — Create a new product in the workspace.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'sku', 'description']
    ordering_fields = ['name', 'sku', 'price', 'stock_quantity', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        workspace = self.get_workspace()
        qs = Product.objects.filter(workspace=workspace)

        # Optional filter: ?is_active=true / false
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            if is_active.lower() in ('true', '1'):
                qs = qs.filter(is_active=True)
            elif is_active.lower() in ('false', '0'):
                qs = qs.filter(is_active=False)

        # Optional filter: ?low_stock=true
        low_stock = self.request.query_params.get('low_stock')
        if low_stock is not None and low_stock.lower() in ('true', '1'):
            qs = qs.filter(stock_quantity__lte=models.F('low_stock_threshold'), is_active=True)

        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['workspace'] = self.get_workspace()
        return context

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError({
                'sku': 'A product with this SKU already exists in this workspace.'
            })


class ProductDetailView(WorkspaceContextMixin, generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/workspaces/<workspace_id>/products/<pk>/ — Retrieve product details.
    PUT    /api/workspaces/<workspace_id>/products/<pk>/ — Full update.
    PATCH  /api/workspaces/<workspace_id>/products/<pk>/ — Partial update (including deactivation).
    DELETE /api/workspaces/<workspace_id>/products/<pk>/ — Delete product (Owner only).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer

    def get_queryset(self):
        workspace = self.get_workspace()
        return Product.objects.filter(workspace=workspace)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['workspace'] = self.get_workspace()
        return context

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError({
                'sku': 'A product with this SKU already exists in this workspace.'
            })

    def perform_destroy(self, instance):
        workspace = self.get_workspace()
        self.check_owner_role(workspace)
        instance.delete()


class LowStockProductsView(WorkspaceContextMixin, generics.ListAPIView):
    """
    GET /api/workspaces/<workspace_id>/products/low-stock/
    Lists active products whose stock_quantity is <= low_stock_threshold.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'sku', 'description']
    ordering_fields = ['stock_quantity', 'low_stock_threshold', 'name', 'price']
    ordering = ['stock_quantity']

    def get_queryset(self):
        workspace = self.get_workspace()
        return Product.objects.filter(
            workspace=workspace,
            is_active=True,
            stock_quantity__lte=models.F('low_stock_threshold'),
        )


# ---------------------------------------------------------------------------
# Inventory Operations Views
# ---------------------------------------------------------------------------

class ProductRestockView(WorkspaceContextMixin, APIView):
    """
    POST /api/workspaces/<workspace_id>/products/<pk>/restock/
    Restocks product by positive quantity.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, workspace_id, pk):
        workspace = self.get_workspace()
        product = get_object_or_404(Product, workspace=workspace, pk=pk)

        serializer = RestockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data['quantity']
        notes = serializer.validated_data.get('notes', '')

        try:
            product.restock(quantity=quantity, notes=notes, actor=request.user)
        except ValueError as err:
            return Response({'detail': str(err)}, status=status.HTTP_400_BAD_REQUEST)

        product.refresh_from_db()
        return Response(
            ProductSerializer(product, context={'workspace': workspace}).data,
            status=status.HTTP_200_OK,
        )


class ProductAdjustmentView(WorkspaceContextMixin, APIView):
    """
    POST /api/workspaces/<workspace_id>/products/<pk>/adjust/
    Adjusts stock quantity (+ or -) with mandatory explanation.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, workspace_id, pk):
        workspace = self.get_workspace()
        product = get_object_or_404(Product, workspace=workspace, pk=pk)

        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data['quantity']
        notes = serializer.validated_data['notes']

        try:
            product.adjust_stock(quantity=quantity, notes=notes, actor=request.user)
        except (ValueError, InsufficientStockError) as err:
            return Response({'detail': str(err)}, status=status.HTTP_400_BAD_REQUEST)

        product.refresh_from_db()
        return Response(
            ProductSerializer(product, context={'workspace': workspace}).data,
            status=status.HTTP_200_OK,
        )


class ProductMovementsView(WorkspaceContextMixin, generics.ListAPIView):
    """
    GET /api/workspaces/<workspace_id>/products/<pk>/movements/
    Lists append-only movements audit trail for a specific product.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InventoryMovementSerializer

    def get_queryset(self):
        workspace = self.get_workspace()
        product = get_object_or_404(Product, workspace=workspace, pk=self.kwargs.get('pk'))
        return product.movements.all().order_by('-created_at')


class WorkspaceMovementsView(WorkspaceContextMixin, generics.ListAPIView):
    """
    GET /api/workspaces/<workspace_id>/inventory/movements/
    Lists all inventory movements across the workspace with filtering.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InventoryMovementSerializer

    def get_queryset(self):
        workspace = self.get_workspace()
        qs = InventoryMovement.objects.filter(product__workspace=workspace).order_by('-created_at')

        # Optional filter: ?movement_type=restock|sale|adjustment|return
        movement_type = self.request.query_params.get('movement_type')
        if movement_type:
            qs = qs.filter(movement_type=movement_type)

        # Optional filter: ?product_id=<id>
        product_id = self.request.query_params.get('product_id')
        if product_id:
            qs = qs.filter(product_id=product_id)

        return qs


class WorkspaceInventoryStatsView(WorkspaceContextMixin, APIView):
    """
    GET /api/workspaces/<workspace_id>/inventory/stats/

    Returns workspace-scoped aggregate metrics computed by the database in a
    single query — never derived from a paginated products page.

    Response fields:
      total_products        — count of all products (active + inactive)
      total_active_products — count of is_active=True products
      total_stock_units     — sum of stock_quantity for active products only
      low_stock_count       — active products at or below their low_stock_threshold
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, workspace_id):
        workspace = self.get_workspace()

        agg = Product.objects.filter(workspace=workspace).aggregate(
            total_products=Count('id'),
            total_active_products=Count('id', filter=Q(is_active=True)),
            total_stock_units=Sum(
                'stock_quantity',
                filter=Q(is_active=True),
                default=0,
            ),
            low_stock_count=Count(
                'id',
                filter=Q(
                    is_active=True,
                    stock_quantity__lte=models.F('low_stock_threshold'),
                ),
            ),
        )

        return Response({
            'total_products':        agg['total_products'],
            'total_active_products': agg['total_active_products'],
            'total_stock_units':     agg['total_stock_units'],
            'low_stock_count':       agg['low_stock_count'],
        })
