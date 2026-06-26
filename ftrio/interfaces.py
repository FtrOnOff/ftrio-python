"""Abstract base classes for the FtrIO extension points.

These resolve the C# ``I``-prefix interfaces into Python ABCs. The rename table
(see PORTING_NOTES.md) drops the ``I`` prefix; ``IToggleParser`` becomes
``ToggleParser`` here and the concrete .NET ``ToggleParser`` is renamed to
``AppSettingsToggleParser`` so interface and implementation no longer collide.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ToggleParser(ABC):
    """Resolves a toggle key to an on/off decision.

    This is the central abstraction: decorators, the builder, the provider, and
    the composite parser all program against it. ``get_override`` has a default
    implementation returning ``None`` so most parsers need not care about
    per-user overrides; only the appsettings-backed parsers implement it.
    """

    @abstractmethod
    def get_toggle_status(self, toggle: str) -> bool:
        """Return whether the named toggle is currently on."""

    @abstractmethod
    def parse_bool_value_from_source(self, status: str) -> bool:
        """Interpret a raw source value as a boolean on/off decision."""

    def get_override(self, toggle_key: str, user_id: str) -> bool | None:
        """Return an explicit per-user override, or ``None`` if none exists.

        Default implementation returns ``None``; parsers that read an overrides
        section from configuration replace this with a real lookup.
        """
        return None


class ToggleDecisionStrategy(ABC):
    """Decides on/off for raw values of a particular shape.

    Strategies are tried in registration order; the first whose ``can_handle``
    returns true owns the decision. This is how FtrIO supports many value
    grammars (percentages, slots, A/B buckets) behind one parser.
    """

    @abstractmethod
    def can_handle(self, raw_value: str) -> bool:
        """Return whether this strategy recognises the shape of ``raw_value``."""

    @abstractmethod
    def should_execute(self, toggle_key: str, raw_value: str) -> bool:
        """Return the on/off decision for a value this strategy can handle."""


class ToggleValueProvider(ABC):
    """Source of raw, unparsed toggle values from any backing store.

    Implement this to feed toggle state from somewhere other than
    appsettings.json (environment variables, an HTTP endpoint, Azure App Config).
    The raw string is handed to the strategy chain by ``StrategyToggleParser``.
    """

    @abstractmethod
    def get_raw_value(self, key: str) -> str | None:
        """Return the raw value for ``key``, or ``None`` if not present here."""


class ToggleBuffer(ABC):
    """Receives toggle value updates from providers for eventual flush to disk.

    Staged values accumulate in memory and are committed to appsettings.json on a
    flush interval, keeping appsettings.json the single on-disk source of truth so
    reads survive a provider going offline.
    """

    @abstractmethod
    def stage(self, key: str, raw_value: str) -> None:
        """Stage a toggle value update; last write before flush wins. Thread-safe."""
