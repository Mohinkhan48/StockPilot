"""
orders/urls.py

URL patterns for sales orders and order lifecycle transitions.
"""

from django.urls import path
from orders import views

urlpatterns = [
    # Orders list and create
    path(
        'workspaces/<int:workspace_id>/orders/',
        views.OrderListCreateView.as_view(),
        name='workspace-orders',
    ),

    # Order detail & draft deletion
    path(
        'workspaces/<int:workspace_id>/orders/<int:pk>/',
        views.OrderDetailView.as_view(),
        name='workspace-order-detail',
    ),

    # Order lifecycle actions
    path(
        'workspaces/<int:workspace_id>/orders/<int:pk>/confirm/',
        views.OrderConfirmView.as_view(),
        name='workspace-order-confirm',
    ),
    path(
        'workspaces/<int:workspace_id>/orders/<int:pk>/complete/',
        views.OrderCompleteView.as_view(),
        name='workspace-order-complete',
    ),
    path(
        'workspaces/<int:workspace_id>/orders/<int:pk>/cancel/',
        views.OrderCancelView.as_view(),
        name='workspace-order-cancel',
    ),
]
