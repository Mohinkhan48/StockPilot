"""
inventory/tests.py

Tests (8):
  1. test_sku_unique_within_workspace     — duplicate SKU in same workspace → IntegrityError
  2. test_sku_unique_across_workspaces    — same SKU in different workspaces → allowed
  3. test_price_nonneg_constraint         — negative price → IntegrityError (CHECK constraint)
  4. test_stock_nonneg_field              — negative stock_quantity → ValidationError
  5. test_low_stock_threshold_default     — default threshold is 10
  6. test_movement_append_only            — updating an existing movement → ValueError
  7. test_movement_resulting_stock        — resulting_stock equals product stock after restock
  8. test_concurrent_stock_deduction      — two threads confirm same product; only one wins
"""

import threading
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.test import TestCase, TransactionTestCase

from accounts.models import Workspace
from inventory.exceptions import InsufficientStockError
from inventory.models import InventoryMovement, Product
from orders.models import Order, OrderItem

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def make_user(username):
    return User.objects.create_user(username=username, password='testpass123')


def make_workspace(name, owner):
    return Workspace.objects.create(name=name, owner=owner)


def make_product(workspace, sku='SKU1', price='10.00', stock=20):
    return Product.objects.create(
        workspace=workspace, name=f'Product {sku}', sku=sku,
        price=price, stock_quantity=stock,
    )


# ---------------------------------------------------------------------------
# Standard tests (use TestCase — each test runs in a rolled-back transaction)
# ---------------------------------------------------------------------------

class ProductConstraintTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user  = make_user('carol')
        cls.ws    = make_workspace('Main WS', owner=cls.user)
        cls.ws2   = make_workspace('Second WS', owner=cls.user)

    # ------------------------------------------------------------------
    # 1. SKU unique within workspace
    # ------------------------------------------------------------------

    def test_sku_unique_within_workspace(self):
        """
        Two products with the same SKU in the same workspace must violate
        the unique_workspace_sku DB constraint.
        """
        make_product(self.ws, sku='DUPE')
        with self.assertRaises(IntegrityError):
            make_product(self.ws, sku='DUPE')

    # ------------------------------------------------------------------
    # 2. SKU unique across workspaces — cross-tenant SKU reuse is allowed
    # ------------------------------------------------------------------

    def test_sku_unique_across_workspaces(self):
        """
        The same SKU may exist in two different workspaces without error.
        """
        p1 = make_product(self.ws,  sku='SHARED')
        p2 = make_product(self.ws2, sku='SHARED')
        self.assertNotEqual(p1.pk, p2.pk)

    # ------------------------------------------------------------------
    # 3. Price non-negative (DB CHECK constraint)
    # ------------------------------------------------------------------

    def test_price_nonneg_constraint(self):
        """
        Attempting to save a product with a negative price must be rejected
        by the database-level CHECK constraint.
        """
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                workspace=self.ws, name='Bad Price', sku='NEG-PRICE',
                price=Decimal('-0.01'), stock_quantity=0,
            )

    # ------------------------------------------------------------------
    # 4. Stock non-negative (model field validation)
    # ------------------------------------------------------------------

    def test_stock_nonneg_field(self):
        """
        PositiveIntegerField rejects negative stock at the Python validation layer.
        """
        p = Product(
            workspace=self.ws, name='Bad Stock', sku='NEG-STOCK',
            price='5.00', stock_quantity=-1,
        )
        with self.assertRaises(ValidationError):
            p.full_clean()

    # ------------------------------------------------------------------
    # 5. Low-stock threshold default
    # ------------------------------------------------------------------

    def test_low_stock_threshold_default(self):
        """A freshly created product has low_stock_threshold == 10."""
        p = make_product(self.ws, sku='NEWPROD', stock=50)
        self.assertEqual(p.low_stock_threshold, 10)

    # ------------------------------------------------------------------
    # 6. Movement append-only
    # ------------------------------------------------------------------

    def test_movement_append_only(self):
        """
        Calling .save() on an existing InventoryMovement must raise ValueError.
        """
        p = make_product(self.ws, sku='AUDIT', stock=5)
        p.restock(10, actor=self.user)
        movement = InventoryMovement.objects.filter(product=p).first()

        self.assertIsNotNone(movement.pk, "Movement was not created.")
        with self.assertRaises(ValueError):
            movement.notes = 'Tampered!'
            movement.save()

    # ------------------------------------------------------------------
    # 7. resulting_stock accuracy after restock
    # ------------------------------------------------------------------

    def test_movement_resulting_stock(self):
        """
        After a restock, the movement's resulting_stock must equal the
        product's new stock_quantity.
        """
        p = make_product(self.ws, sku='RESULT', stock=5)
        p.restock(15, notes='first shipment', actor=self.user)

        p.refresh_from_db()
        movement = InventoryMovement.objects.filter(product=p).latest('created_at')

        self.assertEqual(movement.resulting_stock, 20,
                         "resulting_stock should be 5 + 15 = 20.")
        self.assertEqual(p.stock_quantity, 20,
                         "Product.stock_quantity should be updated to 20.")
        self.assertEqual(movement.resulting_stock, p.stock_quantity,
                         "resulting_stock and stock_quantity must agree.")


# ---------------------------------------------------------------------------
# Concurrency test — requires real DB transactions, not savepoints
# ---------------------------------------------------------------------------

class ConcurrentStockDeductionTest(TransactionTestCase):
    """
    TransactionTestCase (not TestCase) is required here because each thread
    must open its own real DB transaction.  TestCase wraps everything in a
    single transaction/savepoint which prevents proper lock testing.
    """

    def test_concurrent_stock_deduction(self):
        """
        Two threads both try to confirm orders that together exceed available
        stock.  Exactly one should succeed; the other must raise
        InsufficientStockError and leave stock unchanged.

        Setup: product has stock=5.  Order A needs 4 units, Order B needs 4 units.
        Only one confirm can succeed (5 - 4 = 1 left; second needs 4 → fails).
        """
        user = make_user('concuser')
        ws   = make_workspace('Conc WS', owner=user)
        product = make_product(ws, sku='CONC', stock=5)

        order_a = Order.objects.create(workspace=ws, created_by=user)
        OrderItem.objects.create(order=order_a, product=product, quantity=4)

        order_b = Order.objects.create(workspace=ws, created_by=user)
        OrderItem.objects.create(order=order_b, product=product, quantity=4)

        successes = []
        failures  = []

        def try_confirm(order):
            try:
                order.confirm(actor=user)
                successes.append(order.pk)
            except InsufficientStockError:
                failures.append(order.pk)
            except Exception as exc:
                failures.append(f"unexpected: {exc}")
            finally:
                # Each thread must close its own DB connection.
                connection.close()

        t1 = threading.Thread(target=try_confirm, args=(order_a,))
        t2 = threading.Thread(target=try_confirm, args=(order_b,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(successes), 1, f"Expected 1 success, got: {successes}")
        self.assertEqual(len(failures),  1, f"Expected 1 failure, got: {failures}")

        # Stock must be 1 (5 - 4), not 0 or negative.
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 1,
                         f"Expected stock=1 after one deduction, got {product.stock_quantity}.")
