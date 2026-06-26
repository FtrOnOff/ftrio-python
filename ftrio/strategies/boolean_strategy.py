"""The always-present fallback strategy for plain boolean toggle values."""

from __future__ import annotations

from ..interfaces import ToggleDecisionStrategy


class BooleanStrategy(ToggleDecisionStrategy):
    """Handles plain ``true``/``false``/``1``/``0`` values.

    This is the baseline grammar every FtrIO deployment understands. It is
    appended automatically as the last link in any strategy chain so existing
    boolean config keeps working no matter what richer strategies precede it.
    """

    def can_handle(self, raw_value: str) -> bool:
        """Recognise case-insensitive ``true``/``false`` and the digits ``1``/``0``."""
        return (
            raw_value.lower() in ("true", "false")
            or raw_value == "1"
            or raw_value == "0"
        )

    def should_execute(self, toggle_key: str, raw_value: str) -> bool:
        """Return on for ``true``/``1`` (case-insensitive on ``true``)."""
        return raw_value.lower() == "true" or raw_value == "1"
