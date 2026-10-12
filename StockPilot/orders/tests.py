"""
orders/tests.py

Tests (14):
  1.  test_order_total_multiitem                 — 2 items x their prices sums correctly with Decimal
  2.  test_unit_price_is_server_side             — OrderItem.unit_price = product.price at confirm time
  3.  test_price_snapshot_immutable              — changing product.price after confirm does not change OrderItem.unit_price
  4.  test_name_snapshot_immutable               — changing product.name after confirm does not change OrderItem.product_name
  5.  test_sku_snapshot_immutable                — changing product.sku after confirm does not change OrderItem.product_sku
  6.  test_insufficient_stock_raises             — confirm with stock < qty raises InsufficientStockError; status stays pending
  7.  test_insufficient_stock_no_partial         — 2-item order, item 1 ok, item 2 short -> both stocks untouched (atomic rollback)
  8.  test_valid_transition_pending_confirmed    — order.confirm(actor) -> status == 'confirmed'
  9.  test_valid_transition_confirmed_completed  — order.complete(actor) -> status == 'completed'
  10. test_invalid_transition_pending_completed  — order.complete() on pending order -> InvalidTransitionError
  11. test_invalid_transition_completed_cancelled — order.cancel() on completed order -> InvalidTransitionError
  12. test_cancel_from_pending_no_stock_change   — cancel pending order -> stock unchanged, no InventoryMovement
  13. test_cancel_from_confirmed_restores_stock  — cancel confirmed order -> stock restored, return movement created
  14. test_cancellation_idempotency              — cancel already cancelled order -> InvalidTransitionError, no double-restore
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Workspace
from inventory.exceptions import InsufficientStockError
from inventory.models import InventoryMovement, Product
from orders.exceptions import InvalidTransitionError
from orders.models import Order, OrderItem

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username):
    return User.objects.create_user(username=username, password='testpass123')


def make_workspace(name, owner):
    return Workspace.objects.create(name=name, owner=owner)


def make_product(workspace, sku='SKU1', name='Product', price='10.00', stock=20):
    return Product.objects.create(
        workspace=workspace,
        name=name,
        sku=sku,
        price=Decimal(price),
        stock_quantity=stock,
    )


# ---------------------------------------------------------------------------
# Order Lifecycle & Pricing Tests
# ---------------------------------------------------------------------------

class OrderLifecycleAndPricingTests(TestCase):

    def setUp(self):
        self.user = make_user('order_user')
        self.workspace = make_workspace('Order WS', owner=self.user)
        self.product_a = make_product(
            self.workspace,
            sku='PROD-A',
            name='Product A',
            price='10.50',
            stock=15,
        )
        self.product_b = make_product(
            self.workspace,
            sku='PROD-B',
            name='Product B',
            price='5.25',
            stock=20,
        )

    # ------------------------------------------------------------------
    # 1. Server-side totals with Decimal
    # ------------------------------------------------------------------
    def test_order_total_multiitem(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=2)
        OrderItem.objects.create(order=order, product=self.product_b, quantity=3)

        # Before confirm, unit_price is None -> total is 0.00
        self.assertEqual(order.total, Decimal('0.00'))

        order.confirm(actor=self.user)
        order.refresh_from_db()

        # Expected: 2 * 10.50 (21.00) + 3 * 5.25 (15.75) = 36.75
        self.assertEqual(order.total, Decimal('36.75'))

    # ------------------------------------------------------------------
    # 2. Server-side unit price stamping
    # ------------------------------------------------------------------
    def test_unit_price_is_server_side(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        item = OrderItem.objects.create(order=order, product=self.product_a, quantity=2)

        self.assertIsNone(item.unit_price)

        order.confirm(actor=self.user)
        item.refresh_from_db()

        self.assertEqual(item.unit_price, Decimal('10.50'))

    # ------------------------------------------------------------------
    # 3. Price snapshot immutability
    # ------------------------------------------------------------------
    def test_price_snapshot_immutable(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        item = OrderItem.objects.create(order=order, product=self.product_a, quantity=2)
        order.confirm(actor=self.user)

        # Reprice product
        self.product_a.price = Decimal('99.99')
        self.product_a.save(update_fields=['price'])

        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal('10.50'))

    # ------------------------------------------------------------------
    # 4. Name snapshot immutability
    # ------------------------------------------------------------------
    def test_name_snapshot_immutable(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        item = OrderItem.objects.create(order=order, product=self.product_a, quantity=1)
        order.confirm(actor=self.user)

        self.product_a.name = 'Brand New Name'
        self.product_a.save(update_fields=['name'])

        item.refresh_from_db()
        self.assertEqual(item.product_name, 'Product A')

    # ------------------------------------------------------------------
    # 5. SKU snapshot immutability
    # ------------------------------------------------------------------
    def test_sku_snapshot_immutable(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        item = OrderItem.objects.create(order=order, product=self.product_a, quantity=1)
        order.confirm(actor=self.user)

        self.product_a.sku = 'PROD-A-NEW'
        self.product_a.save(update_fields=['sku'])

        item.refresh_from_db()
        self.assertEqual(item.product_sku, 'PROD-A')

    # ------------------------------------------------------------------
    # 6. Insufficient stock raises and does not change status
    # ------------------------------------------------------------------
    def test_insufficient_stock_raises(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=50)  # stock is 15

        with self.assertRaises(InsufficientStockError):
            order.confirm(actor=self.user)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING)

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 15)

    # ------------------------------------------------------------------
    # 7. Atomic rollback across multi-item orders on failure
    # ------------------------------------------------------------------
    def test_insufficient_stock_no_partial(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        # item 1 has enough stock (5 <= 15)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=5)
        # item 2 does not have enough stock (30 > 20)
        OrderItem.objects.create(order=order, product=self.product_b, quantity=30)

        with self.assertRaises(InsufficientStockError):
            order.confirm(actor=self.user)

        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(self.product_a.stock_quantity, 15)
        self.assertEqual(self.product_b.stock_quantity, 20)
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.assertEqual(InventoryMovement.objects.filter(order=order).count(), 0)

    # ------------------------------------------------------------------
    # 8. Valid transition: pending -> confirmed
    # ------------------------------------------------------------------
    def test_valid_transition_pending_confirmed(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=2)

        order.confirm(actor=self.user)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CONFIRMED)

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 13)

    # ------------------------------------------------------------------
    # 9. Valid transition: confirmed -> completed
    # ------------------------------------------------------------------
    def test_valid_transition_confirmed_completed(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=2)
        order.confirm(actor=self.user)

        order.complete(actor=self.user)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_COMPLETED)

        # No further stock deduction on completion
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 13)

    # ------------------------------------------------------------------
    # 10. Invalid transition: pending -> completed
    # ------------------------------------------------------------------
    def test_invalid_transition_pending_completed(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=2)

        with self.assertRaises(InvalidTransitionError):
            order.complete(actor=self.user)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING)

    # ------------------------------------------------------------------
    # 11. Invalid transition: completed -> cancelled
    # ------------------------------------------------------------------
    def test_invalid_transition_completed_cancelled(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=2)
        order.confirm(actor=self.user)
        order.complete(actor=self.user)

        with self.assertRaises(InvalidTransitionError):
            order.cancel(actor=self.user)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_COMPLETED)

    # ------------------------------------------------------------------
    # 12. Cancel from pending: no stock change
    # ------------------------------------------------------------------
    def test_cancel_from_pending_no_stock_change(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=3)

        order.cancel(actor=self.user)
        order.refresh_from_db()

        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 15)
        self.assertEqual(InventoryMovement.objects.filter(order=order).count(), 0)

    # ------------------------------------------------------------------
    # 13. Cancel from confirmed: restores stock and creates return movement
    # ------------------------------------------------------------------
    def test_cancel_from_confirmed_restores_stock(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=3)
        order.confirm(actor=self.user)

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 12)

        order.cancel(actor=self.user)
        order.refresh_from_db()

        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 15)

        return_movements = InventoryMovement.objects.filter(
            order=order, movement_type=InventoryMovement.MOVEMENT_RETURN
        )
        self.assertEqual(return_movements.count(), 1)
        movement = return_movements.first()
        self.assertEqual(movement.quantity, 3)
        self.assertEqual(movement.resulting_stock, 15)

    # ------------------------------------------------------------------
    # 14. Cancellation idempotency
    # ------------------------------------------------------------------
    def test_cancellation_idempotency(self):
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=2)
        order.confirm(actor=self.user)
        order.cancel(actor=self.user)

        with self.assertRaises(InvalidTransitionError):
            order.cancel(actor=self.user)

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 15)

        # Verify exactly one RETURN movement exists
        return_movements = InventoryMovement.objects.filter(
            order=order, movement_type=InventoryMovement.MOVEMENT_RETURN
        )
        self.assertEqual(return_movements.count(), 1)

    def test_cancellation_idempotency_with_concurrent_stale_instance(self):
        """
        Verify that even if an in-memory instance has status='confirmed' (stale instance / race condition),
        cancelling when the DB record is already cancelled raises InvalidTransitionError
        and NEVER restores inventory twice or appends duplicate return movements.
        """
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        OrderItem.objects.create(order=order, product=self.product_a, quantity=4)
        order.confirm(actor=self.user)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 11)  # 15 - 4

        # Load a second instance while still confirmed in memory
        stale_order_instance = Order.objects.get(pk=order.pk)
        self.assertEqual(stale_order_instance.status, Order.STATUS_CONFIRMED)

        # Cancel via first instance
        order.cancel(actor=self.user)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 15)  # Restored to 15

        # Attempt cancel via second instance that still has .status == 'confirmed' in memory
        with self.assertRaises(InvalidTransitionError):
            stale_order_instance.cancel(actor=self.user)

        # Verify stock was restored EXACTLY once and not twice (would be 19 if restored twice)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 15)

        # Verify return movements count is strictly 1
        return_movements = InventoryMovement.objects.filter(
            order=order, movement_type=InventoryMovement.MOVEMENT_RETURN
        )
        self.assertEqual(return_movements.count(), 1)

    # ------------------------------------------------------------------
    # 15. Pending estimated pricing & confirmation lock test
    # ------------------------------------------------------------------
    def test_pending_order_estimated_total_and_confirmation_pricing(self):
        """
        Verify:
        - Pending order of 2 units at $599 each has estimated total $1,198.
        - Its locked total remains $0 while pending.
        - Confirmation stamps the price and produces a final total of $1,198.
        - Changing the catalog price after confirmation does not alter the confirmed total.
        """
        mouse = Product.objects.create(
            workspace=self.workspace,
            name="Wireless Mouse",
            sku="WM-599",
            price=Decimal("599.00"),
            stock_quantity=10,
        )
        order = Order.objects.create(workspace=self.workspace, created_by=self.user)
        item = OrderItem.objects.create(order=order, product=mouse, quantity=2)

        # Pending state checks
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.assertIsNone(item.unit_price)
        self.assertEqual(item.line_total, Decimal('0.00'))
        self.assertEqual(item.estimated_line_total, Decimal('1198.00'))
        self.assertEqual(order.total, Decimal('0.00'))
        self.assertEqual(order.estimated_total, Decimal('1198.00'))

        # Confirm order
        order.confirm(actor=self.user)
        order.refresh_from_db()
        item.refresh_from_db()

        self.assertEqual(order.status, Order.STATUS_CONFIRMED)
        self.assertEqual(item.unit_price, Decimal('599.00'))
        self.assertEqual(item.line_total, Decimal('1198.00'))
        self.assertEqual(item.estimated_line_total, Decimal('1198.00'))
        self.assertEqual(order.total, Decimal('1198.00'))
        self.assertEqual(order.estimated_total, Decimal('1198.00'))

        # Alter catalog price
        mouse.price = Decimal("899.00")
        mouse.save(update_fields=['price'])

        order.refresh_from_db()
        item.refresh_from_db()

        self.assertEqual(item.unit_price, Decimal('599.00'))
        self.assertEqual(item.line_total, Decimal('1198.00'))
        self.assertEqual(item.estimated_line_total, Decimal('1198.00'))
        self.assertEqual(order.total, Decimal('1198.00'))
        self.assertEqual(order.estimated_total, Decimal('1198.00'))
