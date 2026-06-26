"""HTTP toggle provider: polls an endpoint and stages values to a buffer."""

from __future__ import annotations

import json
import logging
import urllib.request
from types import TracebackType

from .._periodic import RepeatingTimer
from ..interfaces import ToggleBuffer

_DEFAULT_POLL_INTERVAL_SECONDS = 30.0
_logger = logging.getLogger(__name__)


class HttpToggleParser:
    """Polls an HTTP endpoint for toggle values and stages them to a buffer.

    appsettings.json remains the source of truth for reads: if the endpoint is
    unreachable, the last flushed state is served from disk automatically, so any
    polling error is swallowed rather than propagated (fail-safe).

    The endpoint is expected to return the same JSON shape as appsettings.json::

        {"Toggles": {"SendWelcomeEmail": "true", "NewCheckout": "50%"}}

    Values are staged as raw strings; the strategy chain is applied later at read
    time, so percentage rollouts and slots still work. The core stays
    dependency-free by polling with the standard library ``urllib``.
    """

    def __init__(
        self,
        url: str,
        buffer: ToggleBuffer,
        poll_interval_seconds: float | None = None,
    ) -> None:
        self._url = url
        self._buffer = buffer
        interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else _DEFAULT_POLL_INTERVAL_SECONDS
        )
        # Fire immediately so the first push happens at startup, then on interval.
        self._timer = RepeatingTimer(interval, self._poll, fire_immediately=True)

    def _poll(self) -> None:
        """Fetch the endpoint and stage each toggle; swallow all errors (fail-safe)."""
        try:
            with urllib.request.urlopen(self._url) as response:  # noqa: S310 (controlled URL)
                if getattr(response, "status", 200) >= 400:
                    return
                payload = response.read()
            document = json.loads(payload)
            toggles = document.get("Toggles")
            if not isinstance(toggles, dict):
                # Malformed response: skip rather than discard existing state.
                _logger.debug("HTTP response from %s had no Toggles object; skipping.", self._url)
                return
            for toggle_name, raw_value in toggles.items():
                self._buffer.stage(toggle_name, _stringify(raw_value))
        except Exception:
            # Provider offline or transient error: last flushed state persists in
            # appsettings.json, so no action is needed here. Logged at debug so the
            # fail-safe path is observable when an operator turns the level up.
            _logger.debug("Polling %s failed; serving last flushed state.", self._url, exc_info=True)

    def close(self) -> None:
        """Stop polling (the Pythonic stand-in for Dispose)."""
        self._timer.stop()

    def __enter__(self) -> HttpToggleParser:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def _stringify(raw_value: object) -> str:
    """Render a JSON value as the raw string the buffer expects."""
    if isinstance(raw_value, bool):
        return "true" if raw_value else "false"
    if isinstance(raw_value, str):
        return raw_value
    return str(raw_value)
