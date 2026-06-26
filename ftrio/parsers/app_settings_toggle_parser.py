"""The default appsettings.json-backed parser (the .NET concrete ``ToggleParser``).

Renamed from ``ToggleParser`` to ``AppSettingsToggleParser`` so the name states
what it reads and no longer collides with the ``ToggleParser`` ABC.
"""

from __future__ import annotations

from ..config import AppSettingsConfiguration, app_settings_file_exists, default_base_path
from ..exceptions import ToggleDoesNotExistError, ToggleParsedOutOfRangeError
from ..interfaces import ToggleParser


class AppSettingsToggleParser(ToggleParser):
    """Reads toggle state from the ``Toggles`` section of appsettings.json.

    Three behaviours are load-bearing and deliberate:

      * No appsettings.json on disk at all means nothing has been toggled off, so
        every toggle reads on. This keeps a fresh app fully functional before any
        config exists rather than failing every gated call.
      * A present file with a missing key is an error (``ToggleDoesNotExistError``):
        the operator has a config file, so an unknown key is a mistake worth surfacing.
      * A present key with an uninterpretable value is also an error
        (``ToggleParsedOutOfRangeError``).
    """

    def __init__(self, base_path: str | None = None) -> None:
        resolved_base_path = base_path if base_path is not None else default_base_path()
        self._config_file_exists = app_settings_file_exists(resolved_base_path)
        self._configuration = (
            AppSettingsConfiguration(resolved_base_path)
            if self._config_file_exists
            else None
        )

    def toggle_config_tag_exists(self) -> bool:
        """Return whether an appsettings.json was found on disk at construction."""
        return self._config_file_exists

    def get_toggle_status(self, toggle: str) -> bool:
        """Resolve a toggle, treating a missing config file as "everything on"."""
        if not self._config_file_exists or self._configuration is None:
            # No appsettings.json on disk at all, so nothing has been explicitly
            # toggled off; everything should run.
            return True

        raw_value = self._configuration.get_value(f"Toggles:{toggle}")
        if raw_value is None:
            raise ToggleDoesNotExistError()

        return self.parse_bool_value_from_source(raw_value)

    def parse_bool_value_from_source(self, status: str) -> bool:
        """Interpret ``1``/``true`` as on, ``0``/``false`` as off, else raise."""
        if status == "1" or status.lower() == "true":
            return True
        if status == "0" or status.lower() == "false":
            return False
        raise ToggleParsedOutOfRangeError()

    def get_override(self, toggle_key: str, user_id: str) -> bool | None:
        """Return the ``TogglesOverrides:{key}:{userId}`` value as a bool, or ``None``."""
        if self._configuration is None:
            return None
        override_value = self._configuration.get_value(
            f"TogglesOverrides:{toggle_key}:{user_id}"
        )
        if override_value is None:
            return None
        if override_value.lower() == "true" or override_value == "1":
            return True
        if override_value.lower() == "false" or override_value == "0":
            return False
        return None
