"""
orders/views.py

DRF Views for Sales Orders: multi-item order creation, lifecycle transitions
(confirm, complete, cancel), and workspace-isolated querying.
"""

from django.shortcuts import get_object_or_404
from rest_framework import filters, generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Workspace, WorkspaceMembership
from accounts.permissions import get_user_membership
from inventory.exceptions import InsufficientStockError
from orders.exceptions import InvalidTransitionError
from orders.models import Order
from orders.serializers import OrderCreateSerializer, OrderSerializer


class WorkspaceContextMixin:
    """
    Mixin providing workspace resolution scoped strictly to the requesting user's memberships.
    Non-members receive 404 Not Found to guarantee absolute tenant isolation.
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


class OrderListCreateView(WorkspaceContextMixin, APIView):
    """
    GET  /api/workspaces/<workspace_id>/orders/ — List orders in workspace with filtering & search.
    POST /api/workspaces/<workspace_id>/orders/ — Create a pending order with multiple items.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, workspace_id):
        workspace = self.get_workspace()
        orders = Order.objects.filter(workspace=workspace).prefetch_related('items__product')

        # Filter by status: ?status=pending|confirmed|completed|cancelled
        order_status = request.query_params.get('status')
        if order_status:
            orders = orders.filter(status=order_status)

        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering in ('created_at', '-created_at', 'status', '-status'):
            orders = orders.order_by(ordering)
        else:
            orders = orders.order_by('-created_at')

        # Pagination
        from rest_framework.pagination import PageNumberPagination
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(orders, request)
        if page is not None:
            serializer = OrderSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, workspace_id):
        workspace = self.get_workspace()
        serializer = OrderCreateSerializer(
            data=request.data,
            context={'workspace': workspace, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )


class OrderDetailView(WorkspaceContextMixin, generics.RetrieveDestroyAPIView):
    """
    GET    /api/workspaces/<workspace_id>/orders/<pk>/ — Retrieve order details with items and total.
    DELETE /api/workspaces/<workspace_id>/orders/<pk>/ — Delete pending draft order (Owner only).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        workspace = self.get_workspace()
        return Order.objects.filter(workspace=workspace).prefetch_related('items__product')

    def perform_destroy(self, instance):
        workspace = self.get_workspace()
        self.check_owner_role(workspace)
        if instance.status != Order.STATUS_PENDING:
            raise ValidationError({
                'detail': f"Cannot delete order #{instance.pk} with status '{instance.status}'. "
                          "Only draft 'pending' orders can be deleted; use cancel for confirmed orders."
            })
        instance.delete()


class OrderConfirmView(WorkspaceContextMixin, APIView):
    """
    POST /api/workspaces/<workspace_id>/orders/<pk>/confirm/
    Transitions order from PENDING to CONFIRMED.
    Deducts stock atomically, creates 'sale' movement, and stamps snapshots.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, workspace_id, pk):
        workspace = self.get_workspace()
        order = get_object_or_404(Order, workspace=workspace, pk=pk)

        try:
            order.confirm(actor=request.user)
        except InvalidTransitionError as err:
            return Response({'detail': str(err)}, status=status.HTTP_400_BAD_REQUEST)
        except InsufficientStockError as err:
            return Response({'detail': str(err)}, status=status.HTTP_400_BAD_REQUEST)

        order.refresh_from_db()
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderCompleteView(WorkspaceContextMixin, APIView):
    """
    POST /api/workspaces/<workspace_id>/orders/<pk>/complete/
    Transitions order from CONFIRMED to COMPLETED (terminal state).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, workspace_id, pk):
        workspace = self.get_workspace()
        order = get_object_or_404(Order, workspace=workspace, pk=pk)

        try:
            order.complete(actor=request.user)
        except InvalidTransitionError as err:
            return Response({'detail': str(err)}, status=status.HTTP_400_BAD_REQUEST)

        order.refresh_from_db()
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)


class OrderCancelView(WorkspaceContextMixin, APIView):
    """
    POST /api/workspaces/<workspace_id>/orders/<pk>/cancel/
    Transitions order to CANCELLED.
    If CONFIRMED, restores stock and creates 'return' movements.
    If PENDING, does not change stock.
    Idempotent guard prevents duplicate cancellation.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, workspace_id, pk):
        workspace = self.get_workspace()
        order = get_object_or_404(Order, workspace=workspace, pk=pk)

        try:
            order.cancel(actor=request.user)
        except InvalidTransitionError as err:
            return Response({'detail': str(err)}, status=status.HTTP_400_BAD_REQUEST)

        order.refresh_from_db()
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)
