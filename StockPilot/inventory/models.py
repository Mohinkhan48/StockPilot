"""
inventory/models.py

Product         — a physical item tracked per workspace.
InventoryMovement — append-only audit ledger; every stock change creates a new row.

Stock strategy
--------------
Stock is deducted when an Order is *confirmed* (not when it is created).
Stock is restored when a confirmed Order is *cancelled*.
All changes go through select_for_update() inside transaction.atomic() so two
concurrent confirm requests cannot both read the same stale stock value.
"""

from django.conf import settings
from django.db import models, transaction
from django.db.models import Q


# ---------------------------------------------------------------------------
# Workspace-scoped queryset — reused by Product and available for extensions
# ---------------------------------------------------------------------------

class WorkspaceScopedQuerySet(models.QuerySet):
    """Adds .for_workspace(ws) to filter to a single tenant."""

    def for_workspace(self, workspace):
        return self.filter(workspace=workspace)

    def low_stock(self):
        return self.filter(stock_quantity__lte=models.F('low_stock_threshold'), is_active=True)


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class Product(models.Model):
    """
    A single stock-keeping unit within a workspace.

    Constraints
    -----------
    unique_workspace_sku  : SKU must be unique within a workspace (not globally).
    product_price_nonneg  : price may never be negative (DB-level CHECK).
    stock_quantity        : PositiveIntegerField maps to UNSIGNED INT in MySQL,
                            which rejects negative values at the database level.
    """

    workspace = models.ForeignKey(
        'accounts.Workspace',
        on_delete=models.CASCADE,
        related_name='products',
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = WorkspaceScopedQuerySet.as_manager()

    class Meta:
        constraints = [
            # Composite unique index: same SKU may exist in different workspaces.
            models.UniqueConstraint(
                fields=['workspace', 'sku'],
                name='unique_workspace_sku',
            ),
            # DB-level guard against negative prices (survives raw SQL / bulk ops).
            models.CheckConstraint(
                check=Q(price__gte=0),
                name='product_price_nonneg',
            ),
            # DB-level guard against negative stock quantities.
            models.CheckConstraint(
                check=Q(stock_quantity__gte=0),
                name='product_stock_nonneg',
            ),
            # DB-level guard against negative low-stock thresholds.
            models.CheckConstraint(
                check=Q(low_stock_threshold__gte=0),
                name='product_low_stock_threshold_nonneg',
            ),
        ]
        ordering = ['workspace', 'sku']

    def __str__(self):
        return f"[{self.sku}] {self.name}"

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_low_stock(self):
        """True when stock is at or below the low_stock_threshold."""
        return self.stock_quantity <= self.low_stock_threshold

    # ------------------------------------------------------------------
    # Service methods: restock & adjust_stock
    # ------------------------------------------------------------------

    @transaction.atomic
    def restock(self, quantity, notes='', actor=None):
        """
        Safely increase stock by *quantity* units.

        1. Locks the product row (select_for_update) to prevent races.
        2. Increments stock_quantity.
        3. Creates an InventoryMovement with movement_type='restock'.
        4. Refreshes self so the caller sees the updated stock.

        Returns the new stock level (int).
        """
        if quantity <= 0:
            raise ValueError(f"Restock quantity must be positive, got {quantity}.")

        # Lock the row so no other transaction can modify stock concurrently.
        locked = Product.objects.select_for_update().get(pk=self.pk)
        new_stock = locked.stock_quantity + quantity
        locked.stock_quantity = new_stock
        locked.save(update_fields=['stock_quantity', 'updated_at'])

        InventoryMovement.objects.create(
            product=locked,
            movement_type=InventoryMovement.MOVEMENT_RESTOCK,
            quantity=quantity,              # positive = stock in
            resulting_stock=new_stock,
            notes=notes,
            created_by=actor,
        )

        # Keep the caller's instance in sync.
        self.stock_quantity = new_stock
        return new_stock

    @transaction.atomic
    def adjust_stock(self, quantity, notes='', actor=None):
        """
        Safely adjust stock by *quantity* units (positive or negative).

        1. Locks the product row (select_for_update) to prevent races.
        2. Validates non-zero quantity and mandatory reason/note.
        3. Verifies resulting stock is non-negative (raises InsufficientStockError).
        4. Updates stock_quantity.
        5. Creates an InventoryMovement with movement_type='adjustment'.
        6. Keeps self synchronized.

        Returns the new stock level (int).
        """
        if quantity == 0:
            raise ValueError("Adjustment quantity cannot be zero.")
        if not notes or not str(notes).strip():
            raise ValueError("A reason/note is required for stock adjustments.")

        locked = Product.objects.select_for_update().get(pk=self.pk)
        new_stock = locked.stock_quantity + quantity
        if new_stock < 0:
            from inventory.exceptions import InsufficientStockError
            raise InsufficientStockError(
                product=locked,
                required=abs(quantity),
                available=locked.stock_quantity,
            )

        locked.stock_quantity = new_stock
        locked.save(update_fields=['stock_quantity', 'updated_at'])

        InventoryMovement.objects.create(
            product=locked,
            movement_type=InventoryMovement.MOVEMENT_ADJUSTMENT,
            quantity=quantity,
            resulting_stock=new_stock,
            notes=str(notes).strip(),
            created_by=actor,
        )

        self.stock_quantity = new_stock
        return new_stock


# ---------------------------------------------------------------------------
# InventoryMovement — append-only audit ledger
# ---------------------------------------------------------------------------

class InventoryMovement(models.Model):
    """
    One row per stock change.  Never updated, never deleted in normal use.

    Fields
    ------
    quantity        : signed integer — positive means stock IN, negative means OUT.
    resulting_stock : snapshot of Product.stock_quantity *after* this movement.
                      Makes the ledger self-contained without replaying history.
    order           : FK to orders.Order (nullable); links sale/return movements
                      back to the order that caused them.  Uses a lazy string
                      reference to avoid a circular import.
    """

    MOVEMENT_RESTOCK    = 'restock'
    MOVEMENT_SALE       = 'sale'
    MOVEMENT_ADJUSTMENT = 'adjustment'
    MOVEMENT_RETURN     = 'return'
    MOVEMENT_CHOICES = [
        (MOVEMENT_RESTOCK,    'Restock'),
        (MOVEMENT_SALE,       'Sale'),
        (MOVEMENT_ADJUSTMENT, 'Adjustment'),
        (MOVEMENT_RETURN,     'Return'),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='movements',
    )
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_CHOICES)
    quantity = models.IntegerField()               # positive = in, negative = out
    resulting_stock = models.PositiveIntegerField() # stock level AFTER this movement
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_movements',
    )
    created_at = models.DateTimeField(auto_now_add=True)  # immutable timestamp
    order = models.ForeignKey(
        'orders.Order',            # lazy string — avoids circular import with orders app
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_movements',
    )

    class Meta:
        ordering = ['product', 'created_at']

    def save(self, *args, **kwargs):
        """Enforce append-only behaviour: block updates to existing records."""
        if self.pk is not None:
            raise ValueError(
                "InventoryMovement records are immutable. "
                "Create a new corrective movement instead of editing this one."
            )
        super().save(*args, **kwargs)

    def __str__(self):
        sign = '+' if self.quantity >= 0 else ''
        return (
            f"{self.get_movement_type_display()} {sign}{self.quantity} "
            f"on {self.product} → stock={self.resulting_stock}"
        )
