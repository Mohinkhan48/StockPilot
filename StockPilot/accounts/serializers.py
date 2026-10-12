"""
accounts/serializers.py

DRF serializers for authentication, workspace management, and memberships.
"""

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from accounts.models import Workspace, WorkspaceMembership

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Public user representation.
    """

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class RegisterSerializer(serializers.Serializer):
    """
    Handles user registration, password hashing, and token issuance.
    """

    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        token, _ = Token.objects.get_or_create(user=user)
        return user, token


class LoginSerializer(serializers.Serializer):
    """
    Validates user credentials and retrieves or creates an auth token.
    """

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if not username or not password:
            raise serializers.ValidationError("Both username and password are required.")

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid username or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        token, _ = Token.objects.get_or_create(user=user)
        attrs['user'] = user
        attrs['token'] = token
        return attrs


class WorkspaceMembershipSerializer(serializers.ModelSerializer):
    """
    Serializes a user's membership and role in a workspace.
    """

    user = UserSerializer(read_only=True)

    class Meta:
        model = WorkspaceMembership
        fields = ['id', 'user', 'role', 'joined_at']
        read_only_fields = ['id', 'user', 'joined_at']


class WorkspaceSerializer(serializers.ModelSerializer):
    """
    Serializes Workspace data with tenant-specific user role context.
    """

    owner = UserSerializer(read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ['id', 'name', 'owner', 'role', 'created_at']
        read_only_fields = ['id', 'owner', 'role', 'created_at']

    def get_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        membership = obj.memberships.filter(user=request.user).first()
        return membership.role if membership else None

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        workspace = Workspace.objects.create(owner=user, **validated_data)
        # Automatically make the creator an owner member of the workspace
        WorkspaceMembership.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        return workspace


class AddMemberSerializer(serializers.Serializer):
    """
    Validates adding or inviting a user into a workspace with a role.
    """

    username = serializers.CharField(required=True)
    role = serializers.ChoiceField(
        choices=WorkspaceMembership.ROLE_CHOICES,
        default=WorkspaceMembership.ROLE_STAFF,
    )

    def validate_username(self, value):
        try:
            target_user = User.objects.get(username__iexact=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(f"User '{value}' does not exist.")

        workspace = self.context.get('workspace')
        if workspace and WorkspaceMembership.objects.filter(workspace=workspace, user=target_user).exists():
            raise serializers.ValidationError(f"User '{value}' is already a member of this workspace.")

        self.context['target_user'] = target_user
        return value

    def create(self, validated_data):
        workspace = self.context['workspace']
        target_user = self.context['target_user']
        role = validated_data.get('role', WorkspaceMembership.ROLE_STAFF)

        membership = WorkspaceMembership.objects.create(
            workspace=workspace,
            user=target_user,
            role=role,
        )
        return membership
