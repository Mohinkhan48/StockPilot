"""
accounts/tests.py

Tests (5):
  1. test_workspace_isolation_products    — for_workspace() never leaks across tenants
  2. test_workspace_isolation_orders      — same for orders queryset
  3. test_workspace_isolation_movements   — movements scoped via product's workspace
  4. test_unique_membership_per_user      — duplicate membership raises IntegrityError
  5. test_owner_protect_on_user_delete    — deleting a workspace owner raises ProtectedError
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from accounts.models import Workspace, WorkspaceMembership
from inventory.models import InventoryMovement, Product
from orders.models import Order

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username):
    return User.objects.create_user(username=username, password='testpass123')


def make_workspace(name, owner):
    return Workspace.objects.create(name=name, owner=owner)


def make_product(workspace, sku='SKU1', stock=20):
    return Product.objects.create(
        workspace=workspace, name=f'Product {sku}', sku=sku,
        price='9.99', stock_quantity=stock,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class WorkspaceIsolationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user_a  = make_user('alice')
        cls.user_b  = make_user('bob')
        cls.ws_a    = make_workspace('Workspace A', owner=cls.user_a)
        cls.ws_b    = make_workspace('Workspace B', owner=cls.user_b)
        cls.prod_a  = make_product(cls.ws_a, sku='AAA', stock=10)
        cls.prod_b  = make_product(cls.ws_b, sku='BBB', stock=10)

    # ------------------------------------------------------------------
    # 1. Product isolation
    # ------------------------------------------------------------------

    def test_workspace_isolation_products(self):
        """for_workspace(ws_a) must return ws_a's products and nothing from ws_b."""
        qs = Product.objects.for_workspace(self.ws_a)
        self.assertIn(self.prod_a, qs)
        self.assertNotIn(self.prod_b, qs)

    # ------------------------------------------------------------------
    # 2. Order isolation
    # ------------------------------------------------------------------

    def test_workspace_isolation_orders(self):
        """for_workspace(ws_a) must return ws_a's orders and nothing from ws_b."""
        order_a = Order.objects.create(workspace=self.ws_a, created_by=self.user_a)
        order_b = Order.objects.create(workspace=self.ws_b, created_by=self.user_b)

        qs = Order.objects.for_workspace(self.ws_a)
        self.assertIn(order_a, qs)
        self.assertNotIn(order_b, qs)

    # ------------------------------------------------------------------
    # 3. Movement isolation (via product__workspace)
    # ------------------------------------------------------------------

    def test_workspace_isolation_movements(self):
        """Movements for ws_a products must not include movements for ws_b products."""
        self.prod_a.restock(5, actor=self.user_a)
        self.prod_b.restock(5, actor=self.user_b)

        ws_a_movement_ids = set(
            InventoryMovement.objects
            .filter(product__workspace=self.ws_a)
            .values_list('id', flat=True)
        )
        ws_b_movement_ids = set(
            InventoryMovement.objects
            .filter(product__workspace=self.ws_b)
            .values_list('id', flat=True)
        )
        self.assertTrue(ws_a_movement_ids.isdisjoint(ws_b_movement_ids),
                        "Movements leaked across workspaces.")

    # ------------------------------------------------------------------
    # 4. Duplicate membership constraint
    # ------------------------------------------------------------------

    def test_unique_membership_per_user(self):
        """Adding the same user to the same workspace twice raises IntegrityError."""
        WorkspaceMembership.objects.create(
            workspace=self.ws_a, user=self.user_b, role=WorkspaceMembership.ROLE_STAFF
        )
        with self.assertRaises(IntegrityError):
            WorkspaceMembership.objects.create(
                workspace=self.ws_a, user=self.user_b, role=WorkspaceMembership.ROLE_STAFF
            )

    # ------------------------------------------------------------------
    # 5. Owner-protect: cannot delete user who owns a workspace
    # ------------------------------------------------------------------

    def test_owner_protect_on_user_delete(self):
        """Deleting a user who owns a workspace must raise ProtectedError."""
        with self.assertRaises(ProtectedError):
            self.user_a.delete()
