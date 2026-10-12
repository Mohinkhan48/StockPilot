"""
accounts/views.py

API views for user authentication and workspace multi-tenant management.
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Workspace, WorkspaceMembership
from accounts.permissions import get_user_membership
from accounts.serializers import (
    AddMemberSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserSerializer,
    WorkspaceMembershipSerializer,
    WorkspaceSerializer,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Authentication Views
# ---------------------------------------------------------------------------

class RegisterView(APIView):
    """
    POST /api/auth/register/
    Registers a new user and returns their authentication token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, token = serializer.save()
        return Response(
            {
                'token': token.key,
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """
    POST /api/auth/login/
    Authenticates username & password and returns an auth token.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token = serializer.validated_data['token']
        return Response(
            {
                'token': token.key,
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Revokes the current authentication token.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, 'auth_token'):
            request.user.auth_token.delete()
        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)


class MeView(APIView):
    """
    GET /api/auth/me/
    Returns current authenticated user details and active workspaces.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user_workspaces = Workspace.objects.filter(memberships__user=request.user).distinct()
        return Response(
            {
                'user': UserSerializer(request.user).data,
                'workspaces': WorkspaceSerializer(
                    user_workspaces, many=True, context={'request': request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Workspace Views
# ---------------------------------------------------------------------------

class WorkspaceListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/workspaces/     — List workspaces the user is a member of.
    POST /api/workspaces/     — Create a new workspace (creator becomes owner).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkspaceSerializer

    def get_queryset(self):
        # Strict isolation: only return workspaces where request.user has a membership
        return Workspace.objects.filter(memberships__user=self.request.user).distinct()


class WorkspaceDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/workspaces/<id>/ — Retrieve workspace details (members only).
    PUT    /api/workspaces/<id>/ — Update workspace (owners only).
    PATCH  /api/workspaces/<id>/ — Partial update workspace (owners only).
    DELETE /api/workspaces/<id>/ — Delete workspace (owners only).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WorkspaceSerializer

    def get_queryset(self):
        # Strict isolation: return 404 if the user is not a member of the workspace
        return Workspace.objects.filter(memberships__user=self.request.user).distinct()

    def check_owner_permission(self, instance):
        membership = get_user_membership(self.request.user, instance)
        if not membership or membership.role != WorkspaceMembership.ROLE_OWNER:
            raise PermissionDenied("Only workspace owners can modify or delete a workspace.")

    def perform_update(self, serializer):
        self.check_owner_permission(serializer.instance)
        serializer.save()

    def perform_destroy(self, instance):
        self.check_owner_permission(instance)
        instance.delete()


class WorkspaceMemberListCreateView(APIView):
    """
    GET  /api/workspaces/<id>/members/ — List all members of a workspace.
    POST /api/workspaces/<id>/members/ — Add a member to the workspace (owners only).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_workspace(self, workspace_id):
        return get_object_or_404(
            Workspace.objects.filter(memberships__user=self.request.user),
            pk=workspace_id,
        )

    def get(self, request, workspace_id):
        workspace = self.get_workspace(workspace_id)
        memberships = workspace.memberships.select_related('user').all()
        serializer = WorkspaceMembershipSerializer(memberships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, workspace_id):
        workspace = self.get_workspace(workspace_id)
        membership = get_user_membership(request.user, workspace)
        if not membership or membership.role != WorkspaceMembership.ROLE_OWNER:
            raise PermissionDenied("Only workspace owners can add new members.")

        serializer = AddMemberSerializer(
            data=request.data,
            context={'workspace': workspace, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        new_membership = serializer.save()
        return Response(
            WorkspaceMembershipSerializer(new_membership).data,
            status=status.HTTP_201_CREATED,
        )


class WorkspaceMemberDetailView(APIView):
    """
    DELETE /api/workspaces/<workspace_id>/members/<user_id>/ — Remove a member from the workspace (owners only).
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, workspace_id, user_id):
        workspace = get_object_or_404(
            Workspace.objects.filter(memberships__user=request.user),
            pk=workspace_id,
        )
        current_membership = get_user_membership(request.user, workspace)
        if not current_membership or current_membership.role != WorkspaceMembership.ROLE_OWNER:
            raise PermissionDenied("Only workspace owners can remove members.")

        # Target user to remove
        target_user = get_object_or_404(User, pk=user_id)
        if target_user == workspace.owner:
            raise ValidationError({'detail': 'Cannot remove the primary workspace owner.'})

        target_membership = get_object_or_404(
            WorkspaceMembership,
            workspace=workspace,
            user=target_user,
        )
        target_membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
