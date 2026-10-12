"""
inventory/exceptions.py

Custom exceptions for the inventory application.
"""


class InsufficientStockError(Exception):
    """
    Raised when a stock deduction would push stock_quantity below zero.

    Attributes:
        product  -- the Product instance that is short on stock
        required -- how many units were requested
        available -- how many units are actually in stock
    """

    def __init__(self, product, required, available):
        self.product = product
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient stock for '{product.name}' (SKU: {product.sku}). "
            f"Required: {required}, available: {available}."
        )
