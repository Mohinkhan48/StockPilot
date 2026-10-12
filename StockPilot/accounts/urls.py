"""
accounts/urls.py

URL routes for authentication and workspace management.
"""

from django.urls import path
from accounts import views

urlpatterns = [
    # Auth endpoints
    path('auth/register/', views.RegisterView.as_view(), name='auth-register'),
    path('auth/login/', views.LoginView.as_view(), name='auth-login'),
    path('auth/logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('auth/me/', views.MeView.as_view(), name='auth-me'),

    # Workspace endpoints
    path('workspaces/', views.WorkspaceListCreateView.as_view(), name='workspace-list-create'),
    path('workspaces/<int:pk>/', views.WorkspaceDetailView.as_view(), name='workspace-detail'),
    path(
        'workspaces/<int:workspace_id>/members/',
        views.WorkspaceMemberListCreateView.as_view(),
        name='workspace-members',
    ),
    path(
        'workspaces/<int:workspace_id>/members/<int:user_id>/',
        views.WorkspaceMemberDetailView.as_view(),
        name='workspace-member-detail',
    ),
]
