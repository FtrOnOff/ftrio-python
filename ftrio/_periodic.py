"""Internal helper: a cancellable repeating timer.

The .NET source uses ``System.Threading.Timer`` for periodic polling and flushing.
This module provides the Python stand-in: a daemon thread that invokes a callback
on a fixed interval until cancelled. It is private (leading underscore) and not
part of the public API; it exists only so the buffer and polling providers share
one correct timer implementation rather than each rolling their own.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

_logger = logging.getLogger(__name__)


class RepeatingTimer:
    """Invokes a callback every ``interval_seconds`` until stopped.

    The first invocation happens after one interval, matching the .NET
    ``new Timer(callback, null, interval, interval)`` shape used in the source.
    Callback exceptions are swallowed so a single failure does not kill the timer
    thread; the providers it drives are all fail-safe by design.
    """

    def __init__(
        self,
        interval_seconds: float,
        callback: Callable[[], None],
        *,
        fire_immediately: bool = False,
    ) -> None:
        self._interval_seconds = interval_seconds
        self._callback = callback
        self._fire_immediately = fire_immediately
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        if self._fire_immediately:
            self._invoke_callback_safely()
        while not self._stop_event.wait(self._interval_seconds):
            self._invoke_callback_safely()

    def _invoke_callback_safely(self) -> None:
        try:
            self._callback()
        except Exception:
            # Polling/flush callbacks are fail-safe; never let one stop the timer.
            # Surface the detail at debug level so an operator can opt in to it
            # (per-logger level control) without the failure becoming fatal.
            _logger.debug("Repeating timer callback raised; continuing.", exc_info=True)

    def stop(self) -> None:
        """Signal the timer thread to stop and wait briefly for it to finish."""
        self._stop_event.set()
        self._thread.join(timeout=self._interval_seconds + 1.0)
