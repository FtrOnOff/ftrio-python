"""Probabilistic percentage rollouts (``"20%"``)."""

from __future__ import annotations

import random

from ..exceptions import ToggleParsedOutOfRangeError
from ..interfaces import ToggleDecisionStrategy


class PercentageRolloutStrategy(ToggleDecisionStrategy):
    """Gates a toggle on for a random fraction of calls.

    This is non-deterministic by design, matching .NET's ``Random.Shared``: each
    call rolls independently, so a "50%" toggle is on for roughly half of calls
    rather than a fixed set of users. Tests assert distribution and bounds, never
    a single exact outcome.
    """

    def can_handle(self, raw_value: str) -> bool:
        """Recognise values whose trailing (right-trimmed) character is ``%``."""
        return raw_value.rstrip().endswith("%")

    def should_execute(self, toggle_key: str, raw_value: str) -> bool:
        """Roll against the numeric prefix; out-of-range values are an error."""
        percentage_text = raw_value.rstrip("%").strip()
        try:
            rollout_percentage = float(percentage_text)
        except ValueError as parse_error:
            raise ToggleParsedOutOfRangeError() from parse_error

        if rollout_percentage < 0 or rollout_percentage > 100:
            raise ToggleParsedOutOfRangeError()

        return random.random() * 100 < rollout_percentage
