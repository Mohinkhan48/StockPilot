"""
orders/test_api.py

Automated REST API tests for Stage 3 Sales Orders and Order Items:
  - Multi-item order creation
  - Rejection of client-submitted prices, snapshots, and totals (server-authoritative)
  - Verification that ordered products belong strictly to the authorized workspace and are active
  - Server-side Decimal calculation of line totals and order totals
  - Immutable snapshots stamped at confirmation time
  - Atomic stock deduction and InventoryMovement generation on confirm
  - Atomic rollback on insufficient stock
  - Lifecycle state machine (Pending -> Confirmed -> Completed)
  - Cancellation from Pending (no stock change) vs Confirmed (stock restored)
  - Cancellation idempotency
  - Workspace isolation and tenant protection (404 for non-members)
  - Owner / Staff role permissions
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from accounts.models import Workspace, WorkspaceMembership
from inventory.models import InventoryMovement, Product
from orders.models import Order, OrderItem

User = get_user_model()


class BaseOrderApiTestCase(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(username='order_owner', password='Password123!')
        self.staff = User.objects.create_user(username='order_staff', password='Password123!')
        self.outsider = User.objects.create_user(username='order_outsider', password='Password123!')

        self.owner_token = Token.objects.create(user=self.owner)
        self.staff_token = Token.objects.create(user=self.staff)
        self.outsider_token = Token.objects.create(user=self.outsider)

        # Workspace A
        self.ws_a = Workspace.objects.create(name="Alpha Logistics", owner=self.owner)
        WorkspaceMembership.objects.create(
            workspace=self.ws_a, user=self.owner, role=WorkspaceMembership.ROLE_OWNER
        )
        WorkspaceMembership.objects.create(
            workspace=self.ws_a, user=self.staff, role=WorkspaceMembership.ROLE_STAFF
        )

        # Workspace B
        self.ws_b = Workspace.objects.create(name="Beta Retail", owner=self.outsider)
        WorkspaceMembership.objects.create(
            workspace=self.ws_b, user=self.outsider, role=WorkspaceMembership.ROLE_OWNER
        )

        # Products in Workspace A
        self.prod_a1 = Product.objects.create(
            workspace=self.ws_a,
            name="Laptop Stand",
            sku="STAND-01",
            price=Decimal("25.00"),
            stock_quantity=10,
        )
        self.prod_a2 = Product.objects.create(
            workspace=self.ws_a,
            name="Wireless Mouse",
            sku="MOUSE-02",
            price=Decimal("15.50"),
            stock_quantity=20,
        )

        # Inactive product in Workspace A
        self.prod_inactive = Product.objects.create(
            workspace=self.ws_a,
            name="Discontinued Cable",
            sku="CABLE-DISC",
            price=Decimal("5.00"),
            stock_quantity=50,
            is_active=False,
        )

        # Product in Workspace B
        self.prod_b1 = Product.objects.create(
            workspace=self.ws_b,
            name="Beta Monitor",
            sku="MON-01",
            price=Decimal("200.00"),
            stock_quantity=5,
        )


class OrderCreationAndValidationApiTests(BaseOrderApiTestCase):

    def test_create_order_multi_item_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        data = {
            'notes': 'Urgent customer order',
            'items': [
                {'product_id': self.prod_a1.id, 'quantity': 2},
                {'product_id': self.prod_a2.id, 'quantity': 3},
            ],
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], Order.STATUS_PENDING)
        self.assertEqual(len(response.data['items']), 2)
        # Pending orders have not stamped prices yet -> total is 0.00
        self.assertEqual(Decimal(str(response.data['total'])), Decimal('0.00'))
        # Estimated total must reflect server-side product prices: 2 * 25.00 + 3 * 15.50 = 96.50
        self.assertEqual(Decimal(str(response.data['estimated_total'])), Decimal('96.50'))
        self.assertEqual(Decimal(str(response.data['items'][0]['estimated_line_total'])), Decimal('50.00'))
        self.assertEqual(Decimal(str(response.data['items'][1]['estimated_line_total'])), Decimal('46.50'))

    def test_reject_client_submitted_pricing_in_items(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        data = {
            'items': [
                {
                    'product_id': self.prod_a1.id,
                    'quantity': 1,
                    'unit_price': '1.00',  # Client trying to hack price
                }
            ],
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_client_submitted_order_total(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        data = {
            'total': '5.00',  # Client trying to submit order total
            'items': [{'product_id': self.prod_a1.id, 'quantity': 1}],
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_client_submitted_estimated_pricing_fields(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        # Attempt to forge estimated_total
        res1 = self.client.post(url, {
            'estimated_total': '9.99',
            'items': [{'product_id': self.prod_a1.id, 'quantity': 1}],
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempt to forge estimated_line_total
        res2 = self.client.post(url, {
            'items': [{'product_id': self.prod_a1.id, 'quantity': 1, 'estimated_line_total': '9.99'}],
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_inactive_product(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        data = {
            'items': [{'product_id': self.prod_inactive.id, 'quantity': 1}],
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('items', response.data)

    def test_reject_product_from_another_workspace(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        data = {
            'items': [
                {'product_id': self.prod_b1.id, 'quantity': 1}  # Belongs to Workspace B!
            ],
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_duplicate_product_lines(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        data = {
            'items': [
                {'product_id': self.prod_a1.id, 'quantity': 1},
                {'product_id': self.prod_a1.id, 'quantity': 2},
            ],
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_empty_items(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        response = self.client.post(url, {'items': []}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OrderConfirmationAndSnapshotsApiTests(BaseOrderApiTestCase):

    def setUp(self):
        super().setUp()
        # Create a pending order
        self.order = Order.objects.create(workspace=self.ws_a, created_by=self.staff)
        self.item1 = OrderItem.objects.create(order=self.order, product=self.prod_a1, quantity=2)
        self.item2 = OrderItem.objects.create(order=self.order, product=self.prod_a2, quantity=3)

    def test_confirm_order_calculates_decimal_totals_and_snapshots(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Order.STATUS_CONFIRMED)

        # Expected total: 2 * 25.00 (50.00) + 3 * 15.50 (46.50) = 96.50
        self.assertEqual(Decimal(str(response.data['total'])), Decimal('96.50'))

        # Verify snapshots
        self.item1.refresh_from_db()
        self.assertEqual(self.item1.product_name, 'Laptop Stand')
        self.assertEqual(self.item1.product_sku, 'STAND-01')
        self.assertEqual(self.item1.unit_price, Decimal('25.00'))
        self.assertEqual(self.item1.line_total, Decimal('50.00'))

        # Verify stock deducted
        self.prod_a1.refresh_from_db()
        self.prod_a2.refresh_from_db()
        self.assertEqual(self.prod_a1.stock_quantity, 8)   # 10 - 2
        self.assertEqual(self.prod_a2.stock_quantity, 17)  # 20 - 3

        # Verify audit movements
        m1 = InventoryMovement.objects.filter(product=self.prod_a1, order=self.order).first()
        self.assertIsNotNone(m1)
        self.assertEqual(m1.movement_type, InventoryMovement.MOVEMENT_SALE)
        self.assertEqual(m1.quantity, -2)
        self.assertEqual(m1.resulting_stock, 8)

    def test_snapshots_remain_immutable_after_product_updates(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        self.client.post(url)

        # Update product price, name, and SKU
        self.prod_a1.price = Decimal('999.99')
        self.prod_a1.name = 'Super Ultra Stand'
        self.prod_a1.sku = 'STAND-ULTRA'
        self.prod_a1.save()

        # Order item snapshot must remain untouched
        self.item1.refresh_from_db()
        self.assertEqual(self.item1.unit_price, Decimal('25.00'))
        self.assertEqual(self.item1.product_name, 'Laptop Stand')
        self.assertEqual(self.item1.product_sku, 'STAND-01')

    def test_pending_order_599_mouse_pricing_and_confirmation_lifecycle(self):
        """
        Requirements test:
        - Pending order of 2 units at $599 each has estimated total $1,198.
        - Its locked total remains $0 while pending.
        - Confirmation stamps the price and produces a final total of $1,198.
        - Changing the catalog price after confirmation does not alter the confirmed total.
        """
        mouse = Product.objects.create(
            workspace=self.ws_a,
            name="Wireless Mouse Pro",
            sku="WM-599-LIFECYCLE",
            price=Decimal("599.00"),
            stock_quantity=10,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        orders_url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})

        # 1. Create order: 2 units at $599
        create_res = self.client.post(orders_url, {
            'items': [{'product_id': mouse.id, 'quantity': 2}],
            'notes': 'Test 2 units at 599',
        }, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        order_id = create_res.data['id']

        # 2. Check pending state via API
        self.assertEqual(create_res.data['status'], Order.STATUS_PENDING)
        self.assertEqual(Decimal(str(create_res.data['total'])), Decimal('0.00'))
        self.assertEqual(Decimal(str(create_res.data['estimated_total'])), Decimal('1198.00'))
        item_data = create_res.data['items'][0]
        self.assertIsNone(item_data['unit_price'])
        self.assertEqual(Decimal(str(item_data['line_total'])), Decimal('0.00'))
        self.assertEqual(Decimal(str(item_data['estimated_line_total'])), Decimal('1198.00'))
        self.assertEqual(Decimal(str(item_data['live_product_price'])), Decimal('599.00'))

        # Also verify via GET order detail
        detail_url = reverse('workspace-order-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': order_id})
        pending_detail = self.client.get(detail_url)
        self.assertEqual(pending_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(pending_detail.data['total'])), Decimal('0.00'))
        self.assertEqual(Decimal(str(pending_detail.data['estimated_total'])), Decimal('1198.00'))

        # 3. Confirm order
        confirm_url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': order_id})
        confirm_res = self.client.post(confirm_url)
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)
        self.assertEqual(confirm_res.data['status'], Order.STATUS_CONFIRMED)
        self.assertEqual(Decimal(str(confirm_res.data['total'])), Decimal('1198.00'))
        self.assertEqual(Decimal(str(confirm_res.data['estimated_total'])), Decimal('1198.00'))
        self.assertEqual(Decimal(str(confirm_res.data['items'][0]['unit_price'])), Decimal('599.00'))
        self.assertEqual(Decimal(str(confirm_res.data['items'][0]['line_total'])), Decimal('1198.00'))

        # 4. Alter catalog price after confirmation
        mouse.price = Decimal("899.00")
        mouse.save(update_fields=['price'])

        # 5. Fetch confirmed order again; verify immutable total of $1,198
        confirmed_detail = self.client.get(detail_url)
        self.assertEqual(confirmed_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(str(confirmed_detail.data['total'])), Decimal('1198.00'))
        self.assertEqual(Decimal(str(confirmed_detail.data['estimated_total'])), Decimal('1198.00'))
        self.assertEqual(Decimal(str(confirmed_detail.data['items'][0]['unit_price'])), Decimal('599.00'))
        self.assertEqual(Decimal(str(confirmed_detail.data['items'][0]['line_total'])), Decimal('1198.00'))

    def test_confirm_fails_atomically_on_insufficient_stock(self):
        # Request 15 units of prod_a1 (only 10 in stock)
        OrderItem.objects.create(order=self.order, product=self.prod_a1, quantity=13)  # total needed: 15 > 10

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Status must still be pending
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PENDING)

        # Stock must remain completely unchanged
        self.prod_a1.refresh_from_db()
        self.prod_a2.refresh_from_db()
        self.assertEqual(self.prod_a1.stock_quantity, 10)
        self.assertEqual(self.prod_a2.stock_quantity, 20)

        # No movement records created
        self.assertEqual(InventoryMovement.objects.filter(order=self.order).count(), 0)


class OrderLifecycleAndCancellationApiTests(BaseOrderApiTestCase):

    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(workspace=self.ws_a, created_by=self.staff)
        OrderItem.objects.create(order=self.order, product=self.prod_a1, quantity=2)

    def test_complete_confirmed_order_success(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        confirm_url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        self.client.post(confirm_url)

        complete_url = reverse('workspace-order-complete', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        response = self.client.post(complete_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Order.STATUS_COMPLETED)

    def test_cannot_complete_pending_order(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        complete_url = reverse('workspace-order-complete', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        response = self.client.post(complete_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_pending_order_no_stock_change(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        cancel_url = reverse('workspace-order-cancel', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Order.STATUS_CANCELLED)

        self.prod_a1.refresh_from_db()
        self.assertEqual(self.prod_a1.stock_quantity, 10)
        self.assertEqual(InventoryMovement.objects.filter(order=self.order).count(), 0)

    def test_cancel_confirmed_order_restores_stock_and_creates_movement(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        confirm_url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        self.client.post(confirm_url)
        self.prod_a1.refresh_from_db()
        self.assertEqual(self.prod_a1.stock_quantity, 8)

        cancel_url = reverse('workspace-order-cancel', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Order.STATUS_CANCELLED)

        # Stock fully restored
        self.prod_a1.refresh_from_db()
        self.assertEqual(self.prod_a1.stock_quantity, 10)

        # Return movement created
        return_m = InventoryMovement.objects.filter(
            order=self.order, movement_type=InventoryMovement.MOVEMENT_RETURN
        ).first()
        self.assertIsNotNone(return_m)
        self.assertEqual(return_m.quantity, 2)
        self.assertEqual(return_m.resulting_stock, 10)

    def test_cancellation_idempotency_blocks_repeat(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        cancel_url = reverse('workspace-order-cancel', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        self.client.post(cancel_url)

        # Second cancel attempt must return 400
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_confirmed_order_twice_restores_stock_exactly_once_api(self):
        """
        Verify via API:
        1. Confirm order (deducts stock).
        2. First cancel succeeds (200 OK, stock restored).
        3. Second cancel fails (400 Bad Request, stock untouched).
        4. Exactly 1 return movement exists, stock remains restored exactly once.
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        confirm_url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        confirm_res = self.client.post(confirm_url)
        self.assertEqual(confirm_res.status_code, status.HTTP_200_OK)

        # Stock deducted: 10 - 2 = 8 for prod_a1
        self.prod_a1.refresh_from_db()
        self.assertEqual(self.prod_a1.stock_quantity, 8)

        cancel_url = reverse('workspace-order-cancel', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})

        # First cancellation call
        res1 = self.client.post(cancel_url)
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data['status'], Order.STATUS_CANCELLED)

        # Stock restored to 10
        self.prod_a1.refresh_from_db()
        self.assertEqual(self.prod_a1.stock_quantity, 10)

        # Second cancellation call (must return 400 Bad Request)
        res2 = self.client.post(cancel_url)
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', res2.data)

        # Stock MUST NOT be restored twice (must still be 10, not 12)
        self.prod_a1.refresh_from_db()
        self.assertEqual(self.prod_a1.stock_quantity, 10)

        # Inventory movements must contain exactly 1 return
        return_movements = InventoryMovement.objects.filter(
            order=self.order, movement_type=InventoryMovement.MOVEMENT_RETURN
        )
        self.assertEqual(return_movements.count(), 1)

    def test_completed_order_cannot_be_cancelled(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        confirm_url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        self.client.post(confirm_url)
        complete_url = reverse('workspace-order-complete', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        self.client.post(complete_url)

        cancel_url = reverse('workspace-order-cancel', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order.id})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OrderWorkspaceIsolationAndRoleApiTests(BaseOrderApiTestCase):

    def setUp(self):
        super().setUp()
        self.order_a = Order.objects.create(workspace=self.ws_a, created_by=self.staff)

    def test_cross_workspace_access_returns_404(self):
        # Outsider (member of ws_b, NOT ws_a) attempts to list ws_a orders -> 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_workspace_confirm_returns_404(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order_a.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_delete_draft_order(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        url = reverse('workspace-order-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order_a.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Order.objects.filter(pk=self.order_a.id).exists())

    def test_staff_cannot_delete_order(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        url = reverse('workspace-order-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': self.order_a.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Order.objects.filter(pk=self.order_a.id).exists())

    def test_cross_workspace_order_id_in_own_workspace_url_returns_404(self):
        # Create an order in Workspace B
        order_b = Order.objects.create(workspace=self.ws_b, created_by=self.outsider)

        # Staff in Workspace A attempts to access order_b using Workspace A's URL -> 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')

        # 1. Detail GET
        detail_url = reverse('workspace-order-detail', kwargs={'workspace_id': self.ws_a.id, 'pk': order_b.id})
        res_get = self.client.get(detail_url)
        self.assertEqual(res_get.status_code, status.HTTP_404_NOT_FOUND)

        # 2. Confirm POST
        confirm_url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_a.id, 'pk': order_b.id})
        res_confirm = self.client.post(confirm_url)
        self.assertEqual(res_confirm.status_code, status.HTTP_404_NOT_FOUND)

        # 3. Complete POST
        complete_url = reverse('workspace-order-complete', kwargs={'workspace_id': self.ws_a.id, 'pk': order_b.id})
        res_complete = self.client.post(complete_url)
        self.assertEqual(res_complete.status_code, status.HTTP_404_NOT_FOUND)

        # 4. Cancel POST
        cancel_url = reverse('workspace-order-cancel', kwargs={'workspace_id': self.ws_a.id, 'pk': order_b.id})
        res_cancel = self.client.post(cancel_url)
        self.assertEqual(res_cancel.status_code, status.HTTP_404_NOT_FOUND)

        # 5. Delete DELETE
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        res_del = self.client.delete(detail_url)
        self.assertEqual(res_del.status_code, status.HTTP_404_NOT_FOUND)

    def test_outsider_cannot_access_ws_a_order_via_ws_b_url(self):
        # Outsider (member of ws_b) attempts to access order_a using Workspace B's URL -> 404
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')

        # 1. Detail GET
        detail_url = reverse('workspace-order-detail', kwargs={'workspace_id': self.ws_b.id, 'pk': self.order_a.id})
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)

        # 2. Confirm POST
        confirm_url = reverse('workspace-order-confirm', kwargs={'workspace_id': self.ws_b.id, 'pk': self.order_a.id})
        self.assertEqual(self.client.post(confirm_url).status_code, status.HTTP_404_NOT_FOUND)

        # 3. Complete POST
        complete_url = reverse('workspace-order-complete', kwargs={'workspace_id': self.ws_b.id, 'pk': self.order_a.id})
        self.assertEqual(self.client.post(complete_url).status_code, status.HTTP_404_NOT_FOUND)

        # 4. Cancel POST
        cancel_url = reverse('workspace-order-cancel', kwargs={'workspace_id': self.ws_b.id, 'pk': self.order_a.id})
        self.assertEqual(self.client.post(cancel_url).status_code, status.HTTP_404_NOT_FOUND)

        # 5. Delete DELETE
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_404_NOT_FOUND)

    def test_order_list_and_filter_strict_workspace_isolation(self):
        order_b = Order.objects.create(workspace=self.ws_b, created_by=self.outsider, status=Order.STATUS_PENDING)

        # Staff in ws_a only sees order_a, never order_b
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        ws_a_url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_a.id})
        res_a = self.client.get(ws_a_url)
        self.assertEqual(res_a.status_code, status.HTTP_200_OK)
        results_a = res_a.data['results'] if 'results' in res_a.data else res_a.data
        ids_a = [o['id'] for o in results_a]
        self.assertIn(self.order_a.id, ids_a)
        self.assertNotIn(order_b.id, ids_a)

        # Outsider in ws_b only sees order_b, never order_a
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        ws_b_url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_b.id})
        res_b = self.client.get(ws_b_url)
        self.assertEqual(res_b.status_code, status.HTTP_200_OK)
        results_b = res_b.data['results'] if 'results' in res_b.data else res_b.data
        ids_b = [o['id'] for o in results_b]
        self.assertIn(order_b.id, ids_b)
        self.assertNotIn(self.order_a.id, ids_b)

    def test_order_creation_rejects_foreign_workspace_product_in_ws_b(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.outsider_token.key}')
        ws_b_orders_url = reverse('workspace-orders', kwargs={'workspace_id': self.ws_b.id})
        # Attempt to create an order in ws_b using prod_a1 (which belongs to ws_a)
        response = self.client.post(ws_b_orders_url, {
            'items': [{'product_id': self.prod_a1.id, 'quantity': 1}],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('items', response.data)
