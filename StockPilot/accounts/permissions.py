"""
accounts/permissions.py

Custom DRF permissions for multi-tenant workspace isolation and role authorization.
"""

from rest_framework import permissions
from accounts.models import Workspace, WorkspaceMembership


def get_user_membership(user, workspace):
    """
    Returns the WorkspaceMembership instance for the given user and workspace,
    or None if the user is not a member.
    """
    if not user or not user.is_authenticated or not workspace:
        return None
    return WorkspaceMembership.objects.filter(workspace=workspace, user=user).first()


class IsWorkspaceMember(permissions.BasePermission):
    """
    Allows access only to authenticated users who are active members of the workspace.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        workspace = obj if isinstance(obj, Workspace) else getattr(obj, 'workspace', None)
        if not workspace:
            return False

        return WorkspaceMembership.objects.filter(workspace=workspace, user=request.user).exists()


class IsWorkspaceOwner(permissions.BasePermission):
    """
    Allows access only to users who hold the 'owner' role within the workspace.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        workspace = obj if isinstance(obj, Workspace) else getattr(obj, 'workspace', None)
        if not workspace:
            return False

        membership = get_user_membership(request.user, workspace)
        return membership is not None and membership.role == WorkspaceMembership.ROLE_OWNER
