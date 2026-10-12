"""
inventory/urls.py

URL patterns for products, stock adjustments, low-stock reporting, and movement audit logs.
"""

from django.urls import path
from inventory import views

urlpatterns = [
    # Low-stock endpoint (listed before <int:pk>)
    path(
        'workspaces/<int:workspace_id>/products/low-stock/',
        views.LowStockProductsView.as_view(),
        name='workspace-products-low-stock',
    ),

    # Product list and creation
    path(
        'workspaces/<int:workspace_id>/products/',
        views.ProductListCreateView.as_view(),
        name='workspace-products',
    ),

    # Product detail, update, delete
    path(
        'workspaces/<int:workspace_id>/products/<int:pk>/',
        views.ProductDetailView.as_view(),
        name='workspace-product-detail',
    ),

    # Restock & manual stock adjustments
    path(
        'workspaces/<int:workspace_id>/products/<int:pk>/restock/',
        views.ProductRestockView.as_view(),
        name='workspace-product-restock',
    ),
    path(
        'workspaces/<int:workspace_id>/products/<int:pk>/adjust/',
        views.ProductAdjustmentView.as_view(),
        name='workspace-product-adjust',
    ),

    # Movements audit trail
    path(
        'workspaces/<int:workspace_id>/products/<int:pk>/movements/',
        views.ProductMovementsView.as_view(),
        name='workspace-product-movements',
    ),
    path(
        'workspaces/<int:workspace_id>/inventory/movements/',
        views.WorkspaceMovementsView.as_view(),
        name='workspace-inventory-movements',
    ),
    path(
        'workspaces/<int:workspace_id>/inventory/stats/',
        views.WorkspaceInventoryStatsView.as_view(),
        name='workspace-inventory-stats',
    ),
]
