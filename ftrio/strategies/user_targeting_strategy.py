"""Explicit user-list targeting (``"users:alice,bob"``)."""

from __future__ import annotations

from ..context import FtrIOContextAccessor
from ..interfaces import ToggleDecisionStrategy


class UserTargetingStrategy(ToggleDecisionStrategy):
    """Gates a toggle on for an explicit allow-list of user ids.

    Useful for dogfooding or staged rollouts to named accounts. With no current
    user (a background job, say) the toggle is off: there is nobody to match
    against the list, so it fails closed.
    """

    def __init__(self, context_accessor: FtrIOContextAccessor) -> None:
        self._context_accessor = context_accessor

    def can_handle(self, raw_value: str) -> bool:
        """Recognise the case-insensitive ``users:`` prefix."""
        return raw_value.lower().startswith("users:")

    def should_execute(self, toggle_key: str, raw_value: str) -> bool:
        """Return on when the current user id is in the comma-separated list."""
        current_user_id = self._context_accessor.get_user_id()
        if current_user_id is None:
            return False

        allowed_user_ids = [
            entry.strip().lower()
            for entry in raw_value[len("users:"):].split(",")
            if entry.strip()
        ]
        return current_user_id.lower() in allowed_user_ids
