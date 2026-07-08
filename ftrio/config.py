"""appsettings.json loading that replicates the .NET configuration behaviour.

The .NET source leans on ``Microsoft.Extensions.Configuration`` with a bootstrap
pass (read FtrIO settings) followed by a live pass (read toggles, with the
environment overlay and reload-on-change applied). We replicate the *behaviour*,
not the library:

  * Colon-delimited key access (``FtrIO:BlueGreen:CurrentSlot``) over a flattened
    view of the JSON, exactly like ``IConfiguration`` indexers.
  * JSON booleans stringify to ``"true"``/``"false"`` so the downstream
    string-based strategy and boolean parsing keep working unchanged.
  * Environment overlay: ``appsettings.{Environment}.json`` layered on top of the
    base file, overlay keys winning.
  * Reload-on-change: when enabled, the files are re-read on each lookup so live
    edits take effect without a restart (the playground depends on this).

The environment names ``ASPNETCORE_ENVIRONMENT`` and ``DOTNET_ENVIRONMENT`` are
kept verbatim for cross-runtime parity; ``FTRIO_ENVIRONMENT`` is accepted as an
additive Python-native alias.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_APP_SETTINGS_FILE_NAME = "appsettings.json"
_DEFAULT_FLUSH_INTERVAL_SECONDS = 5


def _stringify_configuration_value(value: Any) -> str | None:
    """Render a JSON scalar the way ``IConfiguration`` would expose it as a string.

    Booleans become ``"true"``/``"false"`` (lower-cased per the spec; every
    downstream comparison is case-insensitive so this matches .NET behaviour),
    numbers become their text form, and JSON ``null`` is treated as absent.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _flatten_into(
    flattened: dict[str, str], current_path: str, node: Any
) -> None:
    """Flatten nested JSON into colon-delimited keys, mirroring IConfiguration."""
    if isinstance(node, dict):
        for child_key, child_value in node.items():
            child_path = f"{current_path}:{child_key}" if current_path else str(child_key)
            _flatten_into(flattened, child_path, child_value)
    elif isinstance(node, list):
        for index, child_value in enumerate(node):
            child_path = f"{current_path}:{index}" if current_path else str(index)
            _flatten_into(flattened, child_path, child_value)
    else:
        stringified = _stringify_configuration_value(node)
        if stringified is not None:
            flattened[current_path] = stringified


def _read_json_file(file_path: Path) -> dict[str, Any]:
    """Read and parse a JSON file, returning an empty mapping if it is absent."""
    if not file_path.is_file():
        return {}
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_environment_from_file(base_path: str) -> str | None:
    """Return ``FtrIO:Environment`` from the base appsettings.json only.

    The buffer's write target deliberately ignores ``ASPNETCORE_ENVIRONMENT`` and
    friends: on a server where that variable is set for unrelated reasons, the
    buffer must still write to appsettings.json. Only an explicit in-file setting
    redirects the write, so this reads the base file and nothing else.
    """
    settings_path = Path(base_path) / _APP_SETTINGS_FILE_NAME
    if not settings_path.is_file():
        return None
    try:
        document = _read_json_file(settings_path)
    except (json.JSONDecodeError, OSError):
        return None
    environment = document.get("FtrIO", {}).get("Environment")
    if isinstance(environment, str) and len(environment) > 0:
        return environment
    return None


def read_flush_interval_seconds(base_path: str) -> int:
    """Return ``FtrIO:FlushInterval`` (seconds) from the base file, defaulting to 5."""
    settings_path = Path(base_path) / _APP_SETTINGS_FILE_NAME
    if not settings_path.is_file():
        return _DEFAULT_FLUSH_INTERVAL_SECONDS
    try:
        document = _read_json_file(settings_path)
    except (json.JSONDecodeError, OSError):
        return _DEFAULT_FLUSH_INTERVAL_SECONDS
    flush_interval = document.get("FtrIO", {}).get("FlushInterval")
    if isinstance(flush_interval, bool):
        return _DEFAULT_FLUSH_INTERVAL_SECONDS
    if isinstance(flush_interval, int):
        return flush_interval
    return _DEFAULT_FLUSH_INTERVAL_SECONDS


def _resolve_active_environment(base_document: dict[str, Any]) -> str | None:
    """Resolve the active environment using the .NET precedence order.

    ``FtrIO:Environment`` in the base file wins; then ``ASPNETCORE_ENVIRONMENT``;
    then ``DOTNET_ENVIRONMENT``; then the additive ``FTRIO_ENVIRONMENT`` alias.
    """
    in_file = base_document.get("FtrIO", {}).get("Environment")
    if isinstance(in_file, str) and in_file:
        return in_file
    return (
        os.environ.get("ASPNETCORE_ENVIRONMENT")
        or os.environ.get("DOTNET_ENVIRONMENT")
        or os.environ.get("FTRIO_ENVIRONMENT")
    )


class AppSettingsConfiguration:
    """A flattened, colon-addressable view of appsettings.json plus its overlay.

    Construction performs the bootstrap pass (determine reload-on-change and the
    active environment from the base file). Subsequent ``get_value`` calls read
    the live view: cached when reload-on-change is off, re-read from disk on every
    access when it is on, so live edits are picked up without a restart.
    """

    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path)
        self._base_file_path = self._base_path / _APP_SETTINGS_FILE_NAME

        # Bootstrap pass: read FtrIO settings from the base file only, exactly as
        # the .NET source builds a throwaway configuration first.
        try:
            bootstrap_document = _read_json_file(self._base_file_path)
        except (json.JSONDecodeError, OSError):
            bootstrap_document = {}

        reload_setting = bootstrap_document.get("FtrIO", {}).get("ReloadOnChange")
        self._reload_on_change = (
            isinstance(reload_setting, bool) and reload_setting
        ) or (isinstance(reload_setting, str) and reload_setting.lower() == "true")

        self._environment = _resolve_active_environment(bootstrap_document)

        # When reload-on-change is off, snapshot once and serve from the snapshot.
        self._cached_view: dict[str, str] | None = (
            None if self._reload_on_change else self._load_flattened_view()
        )

    @property
    def base_path(self) -> str:
        """The directory appsettings.json is resolved against."""
        return str(self._base_path)

    @property
    def environment(self) -> str | None:
        """The active environment resolved during the bootstrap pass."""
        return self._environment

    def _load_flattened_view(self) -> dict[str, str]:
        """Build the flattened key/value view from the base file plus overlay."""
        flattened: dict[str, str] = {}
        _flatten_into(flattened, "", _read_json_file_or_empty(self._base_file_path))

        if self._environment is not None:
            overlay_path = (
                self._base_path / f"appsettings.{self._environment}.json"
            )
            overlay: dict[str, str] = {}
            _flatten_into(overlay, "", _read_json_file_or_empty(overlay_path))
            # Overlay keys win, matching IConfiguration layer precedence.
            flattened.update(overlay)

        return flattened

    def _current_view(self) -> dict[str, str]:
        """Return the live flattened view, re-reading when reload-on-change is on."""
        if self._reload_on_change:
            return self._load_flattened_view()
        assert self._cached_view is not None  # set in __init__ when reload is off
        return self._cached_view

    def get_value(self, colon_key: str) -> str | None:
        """Return the value at a colon-delimited key, or ``None`` if absent.

        Keys are matched case-insensitively, mirroring
        ``Microsoft.Extensions.Configuration`` whose ``ConfigurationKeyComparer`` is
        ``OrdinalIgnoreCase``. This is the cross-language conformance contract (see the
        ftrio-conformance suite, resolution case ``boolean_key_case_insensitive_match``):
        a lookup of ``Toggles:newcheckout`` resolves a config key ``Toggles:NewCheckout``.
        An exact match is preferred first as a fast path; only on a miss do we scan for a
        case-insensitive match.
        """
        view = self._current_view()
        exact = view.get(colon_key)
        if exact is not None:
            return exact
        lowered_key = colon_key.lower()
        for candidate_key, candidate_value in view.items():
            if candidate_key.lower() == lowered_key:
                return candidate_value
        return None


def _read_json_file_or_empty(file_path: Path) -> dict[str, Any]:
    """Read JSON, swallowing parse/IO errors into an empty mapping.

    Mirrors the .NET ``optional: true`` semantics: a malformed or missing layer
    contributes nothing rather than bringing the whole lookup down.
    """
    try:
        return _read_json_file(file_path)
    except (json.JSONDecodeError, OSError):
        return {}


def app_settings_file_exists(base_path: str) -> bool:
    """Return whether ``appsettings.json`` exists in ``base_path``."""
    return (Path(base_path) / _APP_SETTINGS_FILE_NAME).is_file()


def default_base_path() -> str:
    """Return the default base path for appsettings.json resolution.

    The .NET source defaults to ``AppContext.BaseDirectory``; the closest faithful
    Python equivalent is the current working directory.
    """
    return os.getcwd()
