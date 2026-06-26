"""Enumerations used by the toggle decision API."""

from __future__ import annotations

from enum import Enum


class ToggleStatus(Enum):
    """The resolved state of a toggle.

    Kept as a distinct type (rather than a bare bool) so the explicit-execution
    API can express intent at call sites: ``Active`` means run the gated method,
    ``Inactive`` means skip it. Mirrors the .NET ``ToggleStatus`` enum.
    """

    ACTIVE = "Active"
    INACTIVE = "Inactive"
