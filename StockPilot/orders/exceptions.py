"""
orders/exceptions.py

Custom exceptions for the orders application.
"""


class InvalidTransitionError(Exception):
    """
    Raised when an Order.status change is not permitted by VALID_TRANSITIONS.

    Attributes:
        order      -- the Order instance
        from_status -- the current (source) status
        to_status   -- the requested (target) status
    """

    def __init__(self, order, from_status, to_status, allowed):
        self.order = order
        self.from_status = from_status
        self.to_status = to_status
        self.allowed = allowed
        super().__init__(
            f"Cannot transition Order #{order.pk} from '{from_status}' to '{to_status}'. "
            f"Allowed next states: {allowed or ['none — this is a terminal state']}."
        )
