"""
accounts/models.py

Workspace — the top-level data-isolation boundary.
Every product, order, and inventory movement belongs to exactly one workspace.

WorkspaceMembership — links a Django auth.User to a Workspace with a role.
Roles: 'owner' (full control) or 'staff' (day-to-day operations).
"""

from django.conf import settings
from django.db import models


class Workspace(models.Model):
    """
    A tenant boundary.  All data is scoped to a workspace so that users in
    workspace A can never see data from workspace B.
    """

    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,          # cannot delete a user who owns a workspace
        related_name='owned_workspaces',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class WorkspaceMembership(models.Model):
    """
    Records which user belongs to which workspace and in what capacity.
    A user can belong to many workspaces, but only once per workspace.
    """

    ROLE_OWNER = 'owner'
    ROLE_STAFF = 'staff'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_STAFF, 'Staff'),
    ]

    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspace_memberships',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # DB-level guarantee: one membership record per (workspace, user) pair.
            models.UniqueConstraint(
                fields=['workspace', 'user'],
                name='unique_workspace_user',
            ),
        ]
        ordering = ['workspace', 'user']

    def __str__(self):
        return f"{self.user} — {self.workspace} ({self.role})"
