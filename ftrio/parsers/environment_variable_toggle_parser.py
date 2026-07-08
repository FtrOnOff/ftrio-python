"""Reads toggle values from environment variables, standalone or via a buffer."""

from __future__ import annotations

import os
from types import TracebackType

from .._periodic import RepeatingTimer
from ..exceptions import ToggleDoesNotExistError, ToggleParsedOutOfRangeError
from ..interfaces import ToggleBuffer, ToggleParser

_DEFAULT_PREFIX = "FTRIO__Toggles__"


class EnvironmentVariableToggleParser(ToggleParser):
    """Resolves toggles from environment variables in one of two modes.

    Standalone mode (the default) implements ``ToggleParser`` directly, resolving
    each toggle on demand; pair it with a ``CompositeToggleParser`` to let env vars
    override appsettings.json. Buffer mode snapshots all matching env vars into a
    ``ToggleBuffer`` so they flush to appsettings.json, optionally re-snapshotting
    on a poll interval to pick up runtime changes (e.g. mounted secrets).

    The .NET overloads (prefix-only vs buffer) become a single constructor with a
    keyword ``buffer`` argument (see PORTING_NOTES.md). The double-underscore
    default prefix follows the .NET configuration hierarchy convention.
    """

    def __init__(
        self,
        prefix: str = _DEFAULT_PREFIX,
        *,
        buffer: ToggleBuffer | None = None,
        poll_interval_seconds: float | None = None,
    ) -> None:
        self._prefix = prefix
        self._buffer = buffer
        self._timer: RepeatingTimer | None = None

        if buffer is not None:
            # Buffer mode: push a snapshot immediately, then poll if asked.
            self._push_snapshot()
            if poll_interval_seconds is not None:
                self._timer = RepeatingTimer(poll_interval_seconds, self._push_snapshot)

    def get_toggle_status(self, toggle: str) -> bool:
        """Resolve a single toggle from ``{prefix}{toggle}`` (standalone mode)."""
        raw_value = os.environ.get(self._prefix + toggle)
        if raw_value is None:
            raise ToggleDoesNotExistError()
        return self.parse_bool_value_from_source(raw_value)

    def parse_bool_value_from_source(self, status: str) -> bool:
        """Interpret ``true``/``1`` as on, ``false``/``0`` as off, else raise."""
        if status.lower() == "true" or status == "1":
            return True
        if status.lower() == "false" or status == "0":
            return False
        raise ToggleParsedOutOfRangeError()

    def _push_snapshot(self) -> None:
        """Stage every env var under the prefix to the buffer (buffer mode).

        The prefix is matched case-insensitively because some platforms (notably
        Windows) normalise environment variable names to uppercase, so a
        case-sensitive match would stage nothing there. The extracted toggle key
        is left in whatever case the OS provides; this is harmless because toggle
        keys are matched case-insensitively throughout FtrIO.
        """
        assert self._buffer is not None  # only called when in buffer mode
        lowered_prefix = self._prefix.lower()
        for environment_key, value in os.environ.items():
            if not environment_key.lower().startswith(lowered_prefix):
                continue
            # Slice by the real prefix length; the matched prefix is the same
            # length as self._prefix regardless of case.
            toggle_key = environment_key[len(self._prefix):]
            self._buffer.stage(toggle_key, value if value is not None else "")

    def close(self) -> None:
        """Stop the polling timer, if any (the Pythonic stand-in for Dispose)."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def __enter__(self) -> EnvironmentVariableToggleParser:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
