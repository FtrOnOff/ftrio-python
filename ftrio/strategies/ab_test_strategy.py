"""Deterministic per-user A/B bucketing (``"ab:50"`` or ``"ab:50:round2"``)."""

from __future__ import annotations

import hashlib
import random

from ..context import FtrIOContextAccessor
from ..interfaces import ToggleDecisionStrategy


def compute_bucket(user_id: str, toggle_key: str, salt: str = "") -> int:
    """Return a stable 0-99 bucket for a user/key (and optional salt).

    The algorithm must match the .NET implementation byte for byte so the same
    user buckets identically across runtimes: SHA-256 of ``user:key`` (or
    ``user:key:salt``), then the first four bytes read as a little-endian signed
    32-bit integer, absolute value modulo 100. This is what makes an A/B
    assignment stable and reproducible rather than a per-call coin flip.
    """
    hash_input = f"{user_id}:{toggle_key}:{salt}" if salt else f"{user_id}:{toggle_key}"
    digest = hashlib.sha256(hash_input.encode("utf-8")).digest()
    # .NET: BitConverter.ToInt32(hashBytes, 0) reads the first four bytes as a
    # little-endian signed Int32.
    signed_int32 = int.from_bytes(digest[:4], byteorder="little", signed=True)
    return abs(signed_int32) % 100


class ABTestStrategy(ToggleDecisionStrategy):
    """Assigns users to treatment/control by a stable hash bucket.

    With a current user, the bucket is deterministic: the same user and key (and
    salt) always land in the same bucket, so a user's experience does not flicker
    between requests. Without a user id, it falls back to a probabilistic per-call
    roll, matching the .NET behaviour for context-free callers.
    """

    def __init__(self, context_accessor: FtrIOContextAccessor) -> None:
        self._context_accessor = context_accessor

    def can_handle(self, raw_value: str) -> bool:
        """Recognise ``ab:<pct>`` where ``<pct>`` is an integer in ``[0, 100]``."""
        if not raw_value.lower().startswith("ab:"):
            return False
        first_segment = raw_value[3:].split(":", 1)[0]
        try:
            parsed_percentage = int(first_segment)
        except ValueError:
            return False
        return 0 <= parsed_percentage <= 100

    def should_execute(self, toggle_key: str, raw_value: str) -> bool:
        """Bucket the current user, or roll probabilistically with no user id."""
        rollout_percentage, bucketing_salt = self._parse_value(raw_value)
        current_user_id = self._context_accessor.get_user_id()

        if current_user_id is None:
            return random.randrange(100) < rollout_percentage

        return compute_bucket(current_user_id, toggle_key, bucketing_salt) < rollout_percentage

    @staticmethod
    def _parse_value(raw_value: str) -> tuple[int, str]:
        """Split ``ab:<pct>[:<salt>]`` into its percentage and salt."""
        value_segments = raw_value[3:].split(":", 1)
        try:
            rollout_percentage = int(value_segments[0])
        except ValueError:
            rollout_percentage = 0
        bucketing_salt = value_segments[1] if len(value_segments) > 1 else ""
        return rollout_percentage, bucketing_salt
