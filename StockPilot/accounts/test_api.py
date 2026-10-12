"""
accounts/test_api.py

Automated REST API tests for:
  - Authentication (register, login, logout, me, invalid credentials)
  - Unauthorized access (missing token, invalid token -> 401)
  - Workspace management & isolation (cross-tenant invisibility -> 404)
  - Role permissions & member management (owner vs staff -> 403/200)
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from accounts.models import Workspace, WorkspaceMembership

User = get_user_model()


class AuthApiTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='existinguser',
            email='existing@example.com',
            password='Password123!',
        )
        self.token, _ = Token.objects.get_or_create(user=self.user)

    def test_register_success(self):
        url = reverse('auth-register')
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'StrongPassword123!',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['username'], 'newuser')
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_duplicate_username(self):
        url = reverse('auth-register')
        data = {
            'username': 'existinguser',
            'password': 'StrongPassword123!',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_success(self):
        url = reverse('auth-login')
        data = {
            'username': 'existinguser',
            'password': 'Password123!',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['token'], self.token.key)
        self.assertEqual(response.data['user']['username'], 'existinguser')

    def test_login_invalid_credentials(self):
        url = reverse('auth-login')
        data = {
            'username': 'existinguser',
            'password': 'WrongPassword!',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout(self):
        url = reverse('auth-logout')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Token is deleted
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())

        # Subsequent request with old token is rejected
        me_response = self.client.get(reverse('auth-me'))
        self.assertEqual(me_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_endpoint(self):
        url = reverse('auth-me')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'existinguser')
        self.assertIn('workspaces', response.data)

    def test_unauthorized_access_missing_token(self):
        url = reverse('workspace-list-create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthorized_access_invalid_token(self):
        url = reverse('workspace-list-create')
        self.client.credentials(HTTP_AUTHORIZATION='Token invalidtoken12345')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class WorkspaceApiTests(APITestCase):

    def setUp(self):
        self.user_a = User.objects.create_user(username='alice', password='Password123!')
        self.user_b = User.objects.create_user(username='bob', password='Password123!')
        self.user_c = User.objects.create_user(username='charlie', password='Password123!')

        self.token_a = Token.objects.create(user=self.user_a)
        self.token_b = Token.objects.create(user=self.user_b)
        self.token_c = Token.objects.create(user=self.user_c)

        # Alice creates Workspace A
        self.ws_a = Workspace.objects.create(name="Alice's Workspace", owner=self.user_a)
        WorkspaceMembership.objects.create(
            workspace=self.ws_a,
            user=self.user_a,
            role=WorkspaceMembership.ROLE_OWNER,
        )

        # Bob creates Workspace B
        self.ws_b = Workspace.objects.create(name="Bob's Workspace", owner=self.user_b)
        WorkspaceMembership.objects.create(
            workspace=self.ws_b,
            user=self.user_b,
            role=WorkspaceMembership.ROLE_OWNER,
        )

    def test_create_workspace_auto_assigns_owner_membership(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_c.key}')
        url = reverse('workspace-list-create')
        data = {'name': 'Charlie Startup'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Charlie Startup')
        self.assertEqual(response.data['role'], 'owner')

        # Check DB
        ws_id = response.data['id']
        membership = WorkspaceMembership.objects.get(workspace_id=ws_id, user=self.user_c)
        self.assertEqual(membership.role, WorkspaceMembership.ROLE_OWNER)

    def test_workspace_isolation_list(self):
        # Alice only sees Workspace A, not Workspace B
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        response = self.client.get(reverse('workspace-list-create'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Results may be paginated or direct list depending on configuration
        results = response.data['results'] if 'results' in response.data else response.data
        workspace_ids = [w['id'] for w in results]
        self.assertIn(self.ws_a.id, workspace_ids)
        self.assertNotIn(self.ws_b.id, workspace_ids)

    def test_workspace_isolation_detail_cross_tenant_returns_404(self):
        # Alice tries to get Bob's workspace -> must return 404 (not leak existence)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        url = reverse('workspace-detail', kwargs={'pk': self.ws_b.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_workspace_isolation_members_cross_tenant_returns_404(self):
        # Alice tries to view Bob's workspace members -> must return 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token_a.key}')
        url = reverse('workspace-members', kwargs={'workspace_id': self.ws_b.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class WorkspaceRolePermissionTests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(username='owner_user', password='Password123!')
        self.staff = User.objects.create_user(username='staff_user', password='Password123!')
        self.outsider = User.objects.create_user(username='outsider_user', password='Password123!')

        self.owner_token = Token.objects.create(user=self.owner)
        self.staff_token = Token.objects.create(user=self.staff)
        self.outsider_token = Token.objects.create(user=self.outsider)

        self.workspace = Workspace.objects.create(name="Team Workspace", owner=self.owner)
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.owner,
            role=WorkspaceMembership.ROLE_OWNER,
        )
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.staff,
            role=WorkspaceMembership.ROLE_STAFF,
        )

    def test_owner_can_update_workspace(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        url = reverse('workspace-detail', kwargs={'pk': self.workspace.id})
        response = self.client.patch(url, {'name': 'Updated Team Workspace'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.name, 'Updated Team Workspace')

    def test_staff_cannot_update_workspace(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-detail', kwargs={'pk': self.workspace.id})
        response = self.client.patch(url, {'name': 'Hacked Workspace'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.name, 'Team Workspace')

    def test_staff_cannot_delete_workspace(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-detail', kwargs={'pk': self.workspace.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Workspace.objects.filter(id=self.workspace.id).exists())

    def test_owner_can_add_staff_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        url = reverse('workspace-members', kwargs={'workspace_id': self.workspace.id})
        data = {'username': 'outsider_user', 'role': 'staff'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=self.outsider,
                role=WorkspaceMembership.ROLE_STAFF,
            ).exists()
        )

    def test_staff_cannot_add_members(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-members', kwargs={'workspace_id': self.workspace.id})
        data = {'username': 'outsider_user', 'role': 'staff'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_add_duplicate_member_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        url = reverse('workspace-members', kwargs={'workspace_id': self.workspace.id})
        data = {'username': 'staff_user', 'role': 'staff'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_nonexistent_user_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        url = reverse('workspace-members', kwargs={'workspace_id': self.workspace.id})
        data = {'username': 'ghost_user_does_not_exist', 'role': 'staff'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_remove_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        url = reverse(
            'workspace-member-detail',
            kwargs={'workspace_id': self.workspace.id, 'user_id': self.staff.id},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=self.staff,
            ).exists()
        )

    def test_staff_cannot_remove_member(self):
        # Create third member
        WorkspaceMembership.objects.create(
            workspace=self.workspace,
            user=self.outsider,
            role=WorkspaceMembership.ROLE_STAFF,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse(
            'workspace-member-detail',
            kwargs={'workspace_id': self.workspace.id, 'user_id': self.outsider.id},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_cannot_remove_themselves_as_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        url = reverse(
            'workspace-member-detail',
            kwargs={'workspace_id': self.workspace.id, 'user_id': self.owner.id},
        )
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=self.owner,
            ).exists()
        )
