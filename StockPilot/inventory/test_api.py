"""
inventory/test_api.py

Automated REST API tests for Stage 2 Product and Inventory management:
  - Product CRUD, pagination, search, ordering, and deactivation
  - SKU uniqueness within a workspace vs allowed across workspaces
  - Decimal price, stock, and low-stock threshold validations
  - Atomic restock and manual stock adjustments with select_for_update locking
  - Atomic rollback (no movements created on failure)
  - Low-stock query filtering
  - Append-only inventory movements audit log
  - Cross-workspace isolation (returns 404 for non-members)
  - Role-based permissions (Owner vs Staff)
  - Inventory boundary validations (restock/adjust zero, negative, exact-zero result)
  - Workspace-scoped aggregate stats endpoint (total_products, total_stock_units, etc.)
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from accounts.models import Workspace, WorkspaceMembership
from inventory.models import InventoryMovement, Product

User = get_user_model()


class BaseInventoryApiTestCase(APITestCase):

    def setUp(self):
        # Create Owner and Staff users
        self.owner = User.objects.create_user(username='owner_user', password='Password123!')
        self.staff = User.objects.create_user(username='staff_user', password='Password123!')
        self.outsider = User.objects.create_user(username='outsider_user', password='Password123!')

        self.owner_token = Token.objects.create(user=self.owner)
        self.staff_token = Token.objects.create(user=self.staff)
        self.outsider_token = Token.objects.create(user=self.outsider)

        # Workspace A
        self.ws_a = Workspace.objects.create(name="Alpha Workspace", owner=self.owner)
        WorkspaceMembership.objects.create(
            workspace=self.ws_a, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        WorkspaceMembership.objects.create(
            workspace=self.ws_a, user=self.staff, role=WorkspaceMembership.ROLE_STAFF
        )

        # Workspace B (owned by outsider)
        self.ws_b = Workspace.objects.create(name="Beta Workspace", owner=self.outsider)
        WorkspaceMembership.objects.create(
            workspace=self.ws_b, user=self.outsider, role=WorkspaceMembership.ROLE_OWNER
        )

        # Base Product in Workspace A
        self.product_a = Product.objects.create(
            workspace=self.ws_a,
            name="Alpha Widget",
            sku="WIDGET-001",
            price=Decimal("19.99"),
            stock_quantity=20,
            low_stock_threshold=10,
        )


class ProductCrudApiTests(BaseInventoryApiTestCase):

    def test_list_products_scoped_to_workspace(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['sku'], 'WIDGET-001')

    def test_create_product_success_with_initial_movement(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        data = {
            'name': 'Bravo Gadget',
            'sku': 'GADGET-002',
            'description': 'A high performance gadget',
            'price': '49.95',
            'stock_quantity': 15,
            'low_stock_threshold': 5,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Bravo Gadget')
        self.assertEqual(response.data['stock_quantity'], 15)

        # Audit ledger must record initial stock
        product = Product.objects.get(sku='GADGET-002', workspace=self.ws_a)
        movement = InventoryMovement.objects.filter(product=product).first()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.movement_type, InventoryMovement.MOVEMENT_RESTOCK)
        self.assertEqual(movement.quantity, 15)
        self.assertEqual(movement.resulting_stock, 15)

    def test_create_product_ignores_client_supplied_workspace_payload(self):
        # Client tries to inject workspace_id of Workspace B while calling Workspace A
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        data = {
            'workspace': self.ws_b.id,
            'name': 'Injected Gadget',
            'sku': 'INJECT-001',
            'price': '10.00',
            'stock_quantity': 5,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        product = Product.objects.get(sku='INJECT-001')
        self.assertEqual(product.workspace, self.ws_a)  # Scoped to URL workspace, not injected id

    def test_retrieve_product_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Alpha Widget')

    def test_update_product_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        data = {'name': 'Alpha Widget Pro', 'price': '24.99'}
        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.name, 'Alpha Widget Pro')
        self.assertEqual(self.product_a.price, Decimal('24.99'))

    def test_deactivate_product(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        response = self.client.patch(url, {'is_active': False})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product_a.refresh_from_db()
        self.assertFalse(self.product_a.is_active)

    def test_owner_can_delete_product(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        url = reverse('workspace-product-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(pk=self.product_a.id).exists())

    def test_staff_cannot_delete_product(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Product.objects.filter(pk=self.product_a.id).exists())


class ProductValidationApiTests(BaseInventoryApiTestCase):

    def test_duplicate_sku_in_same_workspace_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        data = {
            'name': 'Duplicate SKU Product',
            'sku': 'WIDGET-001',  # already exists in ws_a
            'price': '15.00',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('sku', response.data)

    def test_same_sku_across_different_workspaces_allowed(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_b.id})
        data = {
            'name': 'Beta Version of Widget',
            'sku': 'WIDGET-001',  # same SKU, but in ws_b!
            'price': '22.00',
            'stock_quantity': 10,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Product.objects.filter(workspace=self.ws_b, sku='WIDGET-001').exists())

    def test_negative_price_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        data = {'name': 'Bad Price', 'sku': 'NEG-PR', 'price': '-10.00'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_stock_quantity_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        data = {'name': 'Bad Stock', 'sku': 'NEG-STK', 'price': '10.00', 'stock_quantity': -5}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_low_stock_threshold_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        data = {'name': 'Bad Threshold', 'sku': 'NEG-TH', 'price': '10.00', 'low_stock_threshold': -2}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class InventoryRestockAndAdjustmentApiTests(BaseInventoryApiTestCase):

    def test_restock_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-restock', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        data = {'quantity': 10, 'notes': 'Weekly restock delivery'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stock_quantity'], 30)

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 30)

        movement = InventoryMovement.objects.filter(product=self.product_a, movement_type='restock').last()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.resulting_stock, 30)
        self.assertEqual(movement.created_by, self.staff)

    def test_restock_negative_or_zero_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-restock', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        response = self.client.post(url, {'quantity': 0})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response_neg = self.client.post(url, {'quantity': -5})
        self.assertEqual(response_neg.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stock_adjustment_positive(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-adjust', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        data = {'quantity': 5, 'notes': 'Found extra units during stock take'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stock_quantity'], 25)

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 25)

    def test_stock_adjustment_negative_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-adjust', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        data = {'quantity': -5, 'notes': 'Damaged boxes discarded'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stock_quantity'], 15)

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 15)

    def test_stock_adjustment_insufficient_stock_rejected_with_rollback(self):
        # Product A has 20 units; attempting to deduct 25
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-adjust', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        initial_movement_count = InventoryMovement.objects.filter(product=self.product_a).count()

        data = {'quantity': -25, 'notes': 'Write off 25 units'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Stock remains unchanged
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 20)

        # No movement record was created
        current_movement_count = InventoryMovement.objects.filter(product=self.product_a).count()
        self.assertEqual(current_movement_count, initial_movement_count)

    def test_stock_adjustment_missing_notes_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-adjust', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        data = {'quantity': 2, 'notes': ''}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LowStockAndAuditApiTests(BaseInventoryApiTestCase):

    def test_low_stock_endpoint_filters_correctly(self):
        # Create product with stock <= low_stock_threshold (stock 5 <= threshold 10)
        low_product = Product.objects.create(
            workspace=self.ws_a,
            name="Low Stock Item",
            sku="LOW-001",
            price=Decimal('5.00'),
            stock_quantity=5,
            low_stock_threshold=10,
            is_active=True,
        )
        # Create inactive low stock product (should be omitted)
        Product.objects.create(
            workspace=self.ws_a,
            name="Inactive Low Item",
            sku="INACT-001",
            price=Decimal('5.00'),
            stock_quantity=2,
            low_stock_threshold=10,
            is_active=False,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-products-low-stock', kwargs={'workspace_id': self.ws_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data['results'] if 'results' in response.data else response.data
        skus = [p['sku'] for p in results]
        self.assertIn('LOW-001', skus)
        self.assertNotIn('WIDGET-001', skus)  # stock 20 > 10
        self.assertNotIn('INACT-001', skus)   # inactive

    def test_product_movements_endpoint(self):
        self.product_a.restock(5, notes="First restock", actor=self.owner)
        self.product_a.adjust_stock(-2, notes="Damage adjust", actor=self.staff)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-movements', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data['results'] if 'results' in response.data else response.data
        self.assertEqual(len(results), 2)

    def test_workspace_movements_endpoint(self):
        self.product_a.restock(10, notes="Restock batch", actor=self.owner)

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-inventory-movements', kwargs={'workspace_id': self.ws_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data['results'] if 'results' in response.data else response.data
        self.assertTrue(len(results) >= 1)


class WorkspaceIsolationAndAuthApiTests(BaseInventoryApiTestCase):

    def test_unauthorized_access_rejected(self):
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_workspace_access_returns_404(self):
        # Outsider is NOT in Workspace A; attempts to view Workspace A's products -> 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_workspace_product_detail_returns_404(self):
        # Outsider attempts to access product in Workspace A -> 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        url = reverse('workspace-product-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_workspace_restock_returns_404(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        url = reverse('workspace-product-restock', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        response = self.client.post(url, {'quantity': 10})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_workspace_product_id_in_own_workspace_url_returns_404(self):
        # Outsider is a member of ws_b, but attempts to query product_a (which belongs to ws_a)
        # using the ws_b URL. Must return 404 Not Found (cannot bypass workspace scoping).
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')

        # 1. Detail GET
        detail_url = reverse('workspace-product-detail', kwargs={'workspace_id': self.ws_b.id, 'pk': self.product_a.id})
        res_get = self.client.get(detail_url)
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        # 2. Update PUT / PATCH
        res_put = self.client.put(detail_url, {'name': 'Hacked', 'sku': 'HACK', 'price': '1.00'})
        self.assertEqual(res_put.status_code, status.HTTP_404_NOT_FOUND)

        res_patch = self.client.patch(detail_url, {'name': 'Hacked'})
        self.assertEqual(res_patch.status_code, status.HTTP_404_NOT_FOUND)

        # 3. Delete DELETE
        res_del = self.client.delete(detail_url)
        self.assertEqual(res_del.status_code, status.HTTP_404_NOT_FOUND)

        # 4. Restock POST
        restock_url = reverse('workspace-product-restock', kwargs={'workspace_id': self.ws_b.id, 'pk': self.product_a.id})
        res_restock = self.client.post(restock_url, {'quantity': 5})
        self.assertEqual(res_restock.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Adjust POST
        adjust_url = reverse('workspace-product-adjust', kwargs={'workspace_id': self.ws_b.id, 'pk': self.product_a.id})
        res_adjust = self.client.post(adjust_url, {'quantity': 2, 'notes': 'Tampering'})
        self.assertEqual(res_adjust.status_code, status.HTTP_404_NOT_FOUND)

        # 6. Product Movements GET
        movements_url = reverse('workspace-product-movements', kwargs={'workspace_id': self.ws_b.id, 'pk': self.product_a.id})
        res_movements = self.client.get(movements_url)
        self.assertEqual(res_movements.status_code, status.HTTP_404_NOT_FOUND)

    def test_search_and_filter_strict_workspace_isolation(self):
        # Create product in ws_b
        prod_b = Product.objects.create(
            workspace=self.ws_b,
            name="Beta Unique Gadget",
            sku="BETA-GADGET",
            price=Decimal('49.99'),
            stock_quantity=2,
            low_stock_threshold=5,
            is_active=True,
        )

        # Outsider searching in ws_b for 'Alpha' (from ws_a) gets 0 results
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        ws_b_list_url = reverse('workspace-products', kwargs={'workspace_id': self.ws_b.id})
        res = self.client.get(f"{ws_b_list_url}?search=Alpha")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data['results'] if 'results' in res.data else res.data
        self.assertEqual(len(results), 0)

        # Owner in ws_a searching for 'Beta' gets 0 results
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        ws_a_list_url = reverse('workspace-products', kwargs={'workspace_id': self.ws_a.id})
        res = self.client.get(f"{ws_a_list_url}?search=Beta")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data['results'] if 'results' in res.data else res.data
        self.assertEqual(len(results), 0)

        # Workspace movements filter by product_id does not leak foreign movements
        movements_url = reverse('workspace-inventory-movements', kwargs={'workspace_id': self.ws_b.id})
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        res_mov = self.client.get(f"{movements_url}?product_id={self.product_a.id}")
        self.assertEqual(res_mov.status_code, status.HTTP_200_OK)
        results_mov = res_mov.data['results'] if 'results' in res_mov.data else res_mov.data
        self.assertEqual(len(results_mov), 0)

    def test_delete_product_requires_owner_role(self):
        # Staff in ws_a attempts to delete product -> 403 Forbidden
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-product-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Product.objects.filter(pk=self.product_a.id).exists())

        # Owner in ws_a can delete product -> 204 No Content
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        res_owner = self.client.delete(url)
        self.assertEqual(res_owner.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(pk=self.product_a.id).exists())


# ---------------------------------------------------------------------------
# Inventory boundary regression tests (restock / adjust edge cases)
# ---------------------------------------------------------------------------

class InventoryBoundaryApiTests(BaseInventoryApiTestCase):
    """
    Verifies that the restock and adjust endpoints enforce valid quantity ranges
    and never produce negative stock, with no inventory movements on failure.
    """

    def _restock_url(self):
        return reverse('workspace-product-restock',
                       kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})

    def _adjust_url(self):
        return reverse('workspace-product-adjust',
                       kwargs={'workspace_id': self.ws_a.id, 'pk': self.product_a.id})

    # ------------------------------------------------------------------
    # Restock boundary cases
    # ------------------------------------------------------------------

    def test_restock_zero_rejected_and_no_movement(self):
        """quantity=0 must be rejected; no movement appended."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        before_count = InventoryMovement.objects.filter(product=self.product_a).count()
        res = self.client.post(self._restock_url(), {'quantity': 0})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 20)  # unchanged
        after_count = InventoryMovement.objects.filter(product=self.product_a).count()
        self.assertEqual(before_count, after_count)

    def test_restock_negative_rejected_and_no_movement(self):
        """quantity=-1 must be rejected; no movement appended."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        before_count = InventoryMovement.objects.filter(product=self.product_a).count()
        res = self.client.post(self._restock_url(), {'quantity': -1})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 20)  # unchanged
        after_count = InventoryMovement.objects.filter(product=self.product_a).count()
        self.assertEqual(before_count, after_count)

    def test_restock_large_positive_accepted(self):
        """Large positive quantity restocks correctly."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        res = self.client.post(self._restock_url(), {'quantity': 1000, 'notes': 'Bulk shipment'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 1020)

    # ------------------------------------------------------------------
    # Adjust boundary cases
    # ------------------------------------------------------------------

    def test_adjust_zero_rejected(self):
        """quantity=0 must be rejected by the serializer."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        res = self.client.post(self._adjust_url(), {'quantity': 0, 'notes': 'zero adjust'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 20)

    def test_adjust_to_exactly_zero_stock_accepted(self):
        """Adjusting by -20 when stock=20 must succeed and leave stock=0."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        res = self.client.post(self._adjust_url(),
                               {'quantity': -20, 'notes': 'Full write-off'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 0)
        # Exactly one movement created
        movement = InventoryMovement.objects.filter(
            product=self.product_a, movement_type=InventoryMovement.MOVEMENT_ADJUSTMENT
        ).last()
        self.assertIsNotNone(movement)
        self.assertEqual(movement.resulting_stock, 0)

    def test_adjust_below_zero_rejected_and_no_movement(self):
        """Adjusting by -21 when stock=20 must be rejected; stock stays 20 and no movement."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        before_count = InventoryMovement.objects.filter(product=self.product_a).count()
        res = self.client.post(self._adjust_url(),
                               {'quantity': -21, 'notes': 'Over-deduct'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 20)
        after_count = InventoryMovement.objects.filter(product=self.product_a).count()
        self.assertEqual(before_count, after_count)

    def test_adjust_missing_notes_rejected(self):
        """Notes field is mandatory; blank notes must be rejected."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        res = self.client.post(self._adjust_url(), {'quantity': 5, 'notes': ''})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('notes', res.data)

    def test_adjust_whitespace_only_notes_rejected(self):
        """Notes containing only whitespace must be rejected by the serializer."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        res = self.client.post(self._adjust_url(), {'quantity': 5, 'notes': '   '})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Workspace aggregate inventory stats endpoint
# ---------------------------------------------------------------------------

class InventoryStatsApiTests(BaseInventoryApiTestCase):
    """
    Verifies GET /api/workspaces/<id>/inventory/stats/ returns accurate
    workspace-scoped aggregates from a single DB query — never from a
    paginated products page.
    """

    def _stats_url(self, workspace_id=None):
        wid = workspace_id if workspace_id is not None else self.ws_a.id
        return reverse('workspace-inventory-stats', kwargs={'workspace_id': wid})

    def test_stats_correct_for_single_active_product(self):
        """Baseline: ws_a has 1 active product with stock=20."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        res = self.client.get(self._stats_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertEqual(data['total_products'], 1)
        self.assertEqual(data['total_active_products'], 1)
        self.assertEqual(data['total_stock_units'], 20)
        self.assertEqual(data['low_stock_count'], 0)  # 20 > threshold 10

    def test_stats_excludes_inactive_products_from_stock_sum(self):
        """
        Inactive products must NOT contribute to total_stock_units.
        total_products includes them; total_active_products excludes them.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        # Add inactive product with 999 units — must not appear in stock sum
        Product.objects.create(
            workspace=self.ws_a,
            name='Inactive Heap',
            sku='INACTIVE-HEAP',
            price='1.00',
            stock_quantity=999,
            is_active=False,
        )
        res = self.client.get(self._stats_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertEqual(data['total_products'], 2)          # active + inactive
        self.assertEqual(data['total_active_products'], 1)   # only the active one
        self.assertEqual(data['total_stock_units'], 20)      # inactive 999 NOT counted

    def test_stats_accurate_across_many_products_beyond_page_size(self):
        """
        Creates 30 additional active products (beyond the default page size of
        ~20) and verifies total_stock_units reflects all of them, not just page 1.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        extra_stock_per_product = 5
        n_extra = 30
        for i in range(n_extra):
            Product.objects.create(
                workspace=self.ws_a,
                name=f'Bulk Product {i:03}',
                sku=f'BULK-{i:03}',
                price='1.00',
                stock_quantity=extra_stock_per_product,
                is_active=True,
            )
        expected_stock = 20 + (n_extra * extra_stock_per_product)  # 20 + 150 = 170
        res = self.client.get(self._stats_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertEqual(data['total_products'], n_extra + 1)
        self.assertEqual(data['total_active_products'], n_extra + 1)
        self.assertEqual(data['total_stock_units'], expected_stock)

    def test_stats_low_stock_count_is_accurate(self):
        """Products at or below their threshold are counted correctly."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        # product_a: stock=20, threshold=10 — NOT low stock
        # Create 2 low-stock active products
        Product.objects.create(
            workspace=self.ws_a, name='Low A', sku='LW-A',
            price='5.00', stock_quantity=3, low_stock_threshold=10, is_active=True,
        )
        Product.objects.create(
            workspace=self.ws_a, name='Low B', sku='LW-B',
            price='5.00', stock_quantity=10, low_stock_threshold=10, is_active=True,  # exactly at threshold
        )
        # Inactive low-stock product — must NOT be counted
        Product.objects.create(
            workspace=self.ws_a, name='Inactive Low', sku='LW-INACT',
            price='5.00', stock_quantity=1, low_stock_threshold=10, is_active=False,
        )
        res = self.client.get(self._stats_url())
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertEqual(data['low_stock_count'], 2)  # Low A + Low B (inactive excluded)

    def test_stats_empty_workspace_returns_zeros(self):
        """A workspace with no products must return all zeros rather than None."""
        # Create a fresh workspace with no products
        empty_owner = self.owner.__class__.objects.create_user(
            username='empty_ws_owner', password='pass1234!'
        )
        from rest_framework.authtoken.models import Token
        empty_token = Token.objects.create(user=empty_owner)
        from accounts.models import WorkspaceMembership
        empty_ws = Workspace.objects.create(name='Empty WS', owner=empty_owner)
        WorkspaceMembership.objects.create(
            workspace=empty_ws, user=empty_owner, role=WorkspaceMembership.ROLE_OWNER
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {empty_token.key}')
        res = self.client.get(self._stats_url(workspace_id=empty_ws.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertEqual(data['total_products'], 0)
        self.assertEqual(data['total_active_products'], 0)
        self.assertEqual(data['total_stock_units'], 0)
        self.assertEqual(data['low_stock_count'], 0)

    def test_stats_workspace_isolation(self):
        """Stats from ws_a must not bleed into ws_b and vice versa."""
        # ws_b (outsider) has no products; ws_a has product_a with stock=20
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        res = self.client.get(self._stats_url(workspace_id=self.ws_b.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertEqual(data['total_products'], 0)
        self.assertEqual(data['total_stock_units'], 0)

    def test_stats_non_member_returns_404(self):
        """A non-member must receive 404, not any aggregate data."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        res = self.client.get(self._stats_url(workspace_id=self.ws_a.id))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_stats_unauthenticated_returns_401(self):
        """Unauthenticated requests must be rejected."""
        res = self.client.get(self._stats_url())
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
