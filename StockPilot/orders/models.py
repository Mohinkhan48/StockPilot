"""
orders/models.py

Order     — a sales order with a strict Pending → Confirmed → Completed lifecycle.
OrderItem — one line per product; stores immutable snapshots of name, SKU, and price.

Lifecycle
---------
  PENDING   → confirm()  → CONFIRMED  (stock deducted atomically)
  CONFIRMED → complete() → COMPLETED  (no stock change; goods have already left)
  PENDING   → cancel()   → CANCELLED  (no stock change; nothing was deducted)
  CONFIRMED → cancel()   → CANCELLED  (stock restored atomically)
  COMPLETED → (terminal)
  CANCELLED → (terminal)

Stock is deducted/restored inside transaction.atomic() with select_for_update()
to prevent concurrent confirms from over-selling.

Snapshots
---------
product_name, product_sku, unit_price on OrderItem are written by the server
inside confirm().  The client never provides these values.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q


# ---------------------------------------------------------------------------
# Workspace-scoped queryset
# ---------------------------------------------------------------------------

class WorkspaceScopedQuerySet(models.QuerySet):
    """Adds .for_workspace(ws) to filter to a single tenant."""

    def for_workspace(self, workspace):
        return self.filter(workspace=workspace)


# ---------------------------------------------------------------------------
# Order
# ---------------------------------------------------------------------------

class Order(models.Model):
    """
    A sales order.

    Status field is the single source of truth for where an order is in its
    lifecycle.  Direct assignment to .status is intentionally left possible
    for Django admin / shell use, but all application code should go through
    the service methods (confirm / complete / cancel).
    """

    STATUS_PENDING   = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING,   'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    # Maps current status → list of statuses it may legally transition to.
    VALID_TRANSITIONS = {
        STATUS_PENDING:   [STATUS_CONFIRMED, STATUS_CANCELLED],
        STATUS_CONFIRMED: [STATUS_COMPLETED, STATUS_CANCELLED],
        STATUS_COMPLETED: [],   # terminal — no further transitions allowed
        STATUS_CANCELLED: [],   # terminal — no further transitions allowed
    }

    workspace = models.ForeignKey(
        'accounts.Workspace',
        on_delete=models.CASCADE,
        related_name='orders',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = WorkspaceScopedQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.pk} [{self.status}] — {self.workspace}"

    # ------------------------------------------------------------------
    # Internal guard
    # ------------------------------------------------------------------

    def _assert_transition(self, target_status):
        """
        Raise InvalidTransitionError if moving to target_status is not allowed
        from the current status.
        """
        from orders.exceptions import InvalidTransitionError

        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if target_status not in allowed:
            raise InvalidTransitionError(
                order=self,
                from_status=self.status,
                to_status=target_status,
                allowed=allowed,
            )

    # ------------------------------------------------------------------
    # Computed properties (no extra DB columns)
    # ------------------------------------------------------------------

    @property
    def total(self):
        """
        Server-computed order total using Decimal arithmetic.
        Evaluates all OrderItems — avoid calling in loops; prefetch_related
        'items' first if you need totals for many orders.
        """
        return sum(
            (item.line_total for item in self.items.all()),
            Decimal('0.00'),
        )

    @property
    def estimated_total(self):
        """
        Server-computed estimated order total using Decimal arithmetic.
        For pending orders, sums estimated_line_total of each item using live product prices.
        For confirmed/completed/cancelled orders, returns the immutable final total.
        """
        if self.status != self.STATUS_PENDING:
            return self.total
        return sum(
            (item.estimated_line_total for item in self.items.all()),
            Decimal('0.00'),
        )

    # ------------------------------------------------------------------
    # Service methods
    # ------------------------------------------------------------------

    @transaction.atomic
    def confirm(self, actor):
        """
        Transition PENDING → CONFIRMED.

        For each OrderItem:
          1. Acquires a row-level lock on the Product row.
          2. Checks stock is sufficient; raises InsufficientStockError if not.
             The outer atomic() rolls back ALL stock changes if any item fails.
          3. Deducts stock and writes an InventoryMovement (type='sale').
          4. Stamps the immutable snapshots (name, SKU, unit_price) onto the item.

        All of the above or none of it — no partial deductions ever.
        """
        from inventory.exceptions import InsufficientStockError
        from inventory.models import InventoryMovement, Product

        if self.pk:
            locked_order = Order.objects.select_for_update().get(pk=self.pk)
            self.status = locked_order.status

        self._assert_transition(self.STATUS_CONFIRMED)

        # Lock products in consistent ascending PK order to prevent deadlocks across concurrent requests
        for item in self.items.select_related('product').order_by('product_id'):
            product = Product.objects.select_for_update().get(pk=item.product_id)

            if product.stock_quantity < item.quantity:
                raise InsufficientStockError(
                    product=product,
                    required=item.quantity,
                    available=product.stock_quantity,
                )

            new_stock = product.stock_quantity - item.quantity
            product.stock_quantity = new_stock
            product.save(update_fields=['stock_quantity', 'updated_at'])

            # Write the immutable snapshot — server-side only, never from client.
            item.product_name = product.name
            item.product_sku  = product.sku
            item.unit_price   = product.price   # Decimal from the DB row
            item.save(update_fields=['product_name', 'product_sku', 'unit_price'])

            # Append an audit movement.
            InventoryMovement.objects.create(
                product=product,
                movement_type=InventoryMovement.MOVEMENT_SALE,
                quantity=-item.quantity,        # negative = stock out
                resulting_stock=new_stock,
                notes=f"Order #{self.pk} confirmed",
                created_by=actor,
                order=self,
            )

        self.status = self.STATUS_CONFIRMED
        self.save(update_fields=['status', 'updated_at'])

    @transaction.atomic
    def complete(self, actor):
        """
        Transition CONFIRMED → COMPLETED.

        No stock change: goods left the warehouse when the order was confirmed.
        """
        if self.pk:
            locked_order = Order.objects.select_for_update().get(pk=self.pk)
            self.status = locked_order.status

        self._assert_transition(self.STATUS_COMPLETED)
        self.status = self.STATUS_COMPLETED
        self.save(update_fields=['status', 'updated_at'])

    @transaction.atomic
    def cancel(self, actor):
        """
        Transition PENDING → CANCELLED  or  CONFIRMED → CANCELLED.

        If the order was CONFIRMED, stock is restored for every item and a
        'return' movement is written.  If the order was only PENDING, no stock
        was ever deducted so nothing is restored.

        Idempotency: calling cancel() on a CANCELLED order raises
        InvalidTransitionError immediately — the stock is never restored twice.
        """
        from inventory.models import InventoryMovement, Product

        if self.pk:
            locked_order = Order.objects.select_for_update().get(pk=self.pk)
            self.status = locked_order.status

        self._assert_transition(self.STATUS_CANCELLED)

        if self.status == self.STATUS_CONFIRMED:
            # Lock products in consistent ascending PK order to prevent deadlocks across concurrent requests
            for item in self.items.select_related('product').order_by('product_id'):
                product = Product.objects.select_for_update().get(pk=item.product_id)
                new_stock = product.stock_quantity + item.quantity
                product.stock_quantity = new_stock
                product.save(update_fields=['stock_quantity', 'updated_at'])

                InventoryMovement.objects.create(
                    product=product,
                    movement_type=InventoryMovement.MOVEMENT_RETURN,
                    quantity=+item.quantity,     # positive = stock in
                    resulting_stock=new_stock,
                    notes=f"Order #{self.pk} cancelled",
                    created_by=actor,
                    order=self,
                )

        self.status = self.STATUS_CANCELLED
        self.save(update_fields=['status', 'updated_at'])


# ---------------------------------------------------------------------------
# OrderItem
# ---------------------------------------------------------------------------

class OrderItem(models.Model):
    """
    One line of an Order.

    Snapshot fields (product_name, product_sku, unit_price) are blank until
    the order is confirmed, at which point the server stamps them from the live
    Product row.  After that they are immutable historical records: renaming or
    repricing a product never changes past orders.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.PROTECT,   # preserve order history even if product is deleted
        related_name='order_items',
    )

    # ----- Immutable snapshots written by Order.confirm() -----
    product_name = models.CharField(max_length=255, blank=True)
    product_sku  = models.CharField(max_length=100, blank=True)
    unit_price   = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            # DB-level: unit_price, when set, must be non-negative.
            # NULL satisfies this constraint (NULL >= 0 → NULL, not a violation).
            models.CheckConstraint(
                check=Q(unit_price__gte=0),
                name='orderitem_price_nonneg',
            ),
            # DB-level: at least one unit per line item.
            models.CheckConstraint(
                check=Q(quantity__gte=1),
                name='orderitem_qty_positive',
            ),
        ]

    def __str__(self):
        label = self.product_name or str(self.product)
        return f"{label} × {self.quantity}"

    @property
    def line_total(self):
        """
        Decimal line total.  Returns 0.00 if unit_price has not yet been set
        (i.e. the order is still in PENDING state).
        """
        if self.unit_price is None:
            return Decimal('0.00')
        return self.unit_price * self.quantity

    @property
    def estimated_line_total(self):
        """
        Decimal estimated line total.
        If unit_price is already stamped (confirmed/completed/cancelled order),
        returns line_total.
        If pending, evaluates against the live server-side product price.
        Safely falls back to 0.00 if product is missing or product.price is None.
        """
        if self.unit_price is not None:
            return self.line_total
        try:
            if self.product and getattr(self.product, 'price', None) is not None:
                return self.product.price * self.quantity
        except Exception:
            pass
        return Decimal('0.00')
