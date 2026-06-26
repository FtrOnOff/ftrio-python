"""Deployment-slot gating (``"blue"`` / ``"green"``)."""

from __future__ import annotations

from ..config import AppSettingsConfiguration, default_base_path
from ..interfaces import ToggleDecisionStrategy


class BlueGreenStrategy(ToggleDecisionStrategy):
    """Gates a toggle by matching its value against the active deployment slot.

    Two construction modes mirror the .NET overloads:

      * config-driven: read ``FtrIO:BlueGreen:CurrentSlot`` and ``KnownSlots`` from
        appsettings.json, honouring reload-on-change so editing the file flips the
        active slot without a restart;
      * explicit: pass the current slot and known slots directly, useful for tests
        and programmatic wiring.

    A toggle whose value is a known slot is "on" only when that slot is the
    current one, so the same config drives traffic to whichever colour is live.
    """

    def __init__(
        self,
        current_slot: str | None = None,
        *known_slots: str,
        base_path: str | None = None,
        config_driven: bool = False,
    ) -> None:
        """Construct in explicit or config-driven mode.

        Explicit mode is the default: ``BlueGreenStrategy("blue", "blue", "green")``.
        Config-driven mode is selected with ``config_driven=True`` (optionally with
        a ``base_path``), matching the .NET parameterless / base-path constructors.
        Passing neither a slot nor ``config_driven`` resolves config against the
        default base path, mirroring ``new BlueGreenStrategy()``.
        """
        use_config = config_driven or base_path is not None or current_slot is None
        if use_config:
            resolved_base_path = base_path if base_path is not None else default_base_path()
            self._configuration: AppSettingsConfiguration | None = AppSettingsConfiguration(
                resolved_base_path
            )
            self._fixed_current_slot: str | None = None
            self._fixed_known_slots: set[str] | None = None
        else:
            self._configuration = None
            self._fixed_current_slot = current_slot
            self._fixed_known_slots = {slot.lower() for slot in known_slots}

    @classmethod
    def from_config(cls, base_path: str | None = None) -> BlueGreenStrategy:
        """Construct a config-driven strategy reading from ``base_path``."""
        return cls(base_path=base_path, config_driven=True)

    @property
    def _current_slot(self) -> str | None:
        if self._configuration is not None:
            return self._configuration.get_value("FtrIO:BlueGreen:CurrentSlot")
        return self._fixed_current_slot

    @property
    def _known_slots(self) -> set[str]:
        if self._configuration is not None:
            raw_known_slots = self._configuration.get_value("FtrIO:BlueGreen:KnownSlots")
            if not raw_known_slots:
                return set()
            return {
                entry.strip().lower()
                for entry in raw_known_slots.split(",")
                if entry.strip()
            }
        return self._fixed_known_slots if self._fixed_known_slots is not None else set()

    def can_handle(self, raw_value: str) -> bool:
        """Recognise values that name a known slot (case-insensitive, trimmed)."""
        return raw_value.strip().lower() in self._known_slots

    def should_execute(self, toggle_key: str, raw_value: str) -> bool:
        """Return on when the value names the currently active slot."""
        current_slot = self._current_slot
        if current_slot is None:
            return False
        return raw_value.strip().lower() == current_slot.strip().lower()
