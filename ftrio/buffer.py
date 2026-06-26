"""Buffers provider toggle updates and flushes them atomically to appsettings.json."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from types import TracebackType
from typing import Any

from ._periodic import RepeatingTimer
from .config import read_environment_from_file, read_flush_interval_seconds
from .interfaces import ToggleBuffer

_APP_SETTINGS_FILE_NAME = "appsettings.json"
_logger = logging.getLogger(__name__)


class ToggleProviderBuffer(ToggleBuffer):
    """Accumulates staged toggle values and commits them to disk on an interval.

    appsettings.json is always the on-disk source of truth: if a provider goes
    offline, the last flushed state persists and the appsettings parser keeps
    serving from it. The design mirrors the .NET ``ToggleProviderBuffer`` closely
    because the concurrency details matter:

      * Staging collapses rapid updates to the same key (last write wins).
      * Only one flush runs at a time; if the timer fires mid-flush that tick is
        skipped (a non-blocking lock acquire, like ``Monitor.TryEnter``), and
        staged values simply wait for the next flush rather than being lost.
      * Writes are atomic (temp file then ``os.replace``) so a crash never leaves
        a half-written appsettings.json.
      * A failed write re-stages its drained values without clobbering newer ones.
      * ``close`` performs a final flush so nothing is lost on shutdown.
    """

    def __init__(
        self, base_path: str | None = None, flush_interval_seconds: float | None = None
    ) -> None:
        resolved_base_path = base_path if base_path is not None else os.getcwd()

        # The buffer writes to an env-specific file ONLY when FtrIO:Environment is
        # set in appsettings.json itself; ASPNETCORE_ENVIRONMENT and friends are
        # deliberately ignored here (the server's own file is its environment).
        environment = read_environment_from_file(resolved_base_path)
        settings_file_name = (
            f"appsettings.{environment}.json"
            if environment is not None
            else _APP_SETTINGS_FILE_NAME
        )
        self._settings_path = Path(resolved_base_path) / settings_file_name

        self._pending: dict[str, str] = {}
        self._staging_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._disposing = False

        interval = (
            flush_interval_seconds
            if flush_interval_seconds is not None
            else read_flush_interval_seconds(resolved_base_path)
        )
        self._timer = RepeatingTimer(interval, self._timer_flush)

    def stage(self, key: str, raw_value: str) -> None:
        """Stage a toggle value; the last write before a flush wins. Thread-safe."""
        with self._staging_lock:
            self._pending[key] = raw_value

    def flush_now(self) -> None:
        """Flush all staged changes immediately. Safe to call concurrently."""
        self._flush_core()

    def close(self) -> None:
        """Stop the timer and perform a final flush (the stand-in for Dispose)."""
        self._disposing = True
        self._timer.stop()
        self._flush_core()

    def __enter__(self) -> ToggleProviderBuffer:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _timer_flush(self) -> None:
        if self._disposing:
            return
        self._flush_core()

    def _flush_core(self) -> None:
        with self._staging_lock:
            if not self._pending:
                return

        # Try to take the write lock without blocking. If a flush is already
        # running, skip this tick; pending changes wait for the next flush.
        if not self._write_lock.acquire(blocking=False):
            return
        try:
            toggles_to_write = self._drain_pending()
            if not toggles_to_write:
                return

            try:
                existing_json = (
                    self._settings_path.read_text(encoding="utf-8")
                    if self._settings_path.is_file()
                    else "{}"
                )
                updated_json = self._merge_toggles(existing_json, toggles_to_write)
                self._write_atomically(updated_json)
            except Exception:
                # Write failed: re-stage the drained values so the next flush
                # retries them, without overwriting any newer value that arrived
                # during the failed write. Warn so a persistently failing flush
                # (e.g. a read-only volume) is visible to operators.
                _logger.warning(
                    "Flush to %s failed; re-staging %d toggle(s) for retry.",
                    self._settings_path,
                    len(toggles_to_write),
                    exc_info=True,
                )
                with self._staging_lock:
                    for pending_key, pending_value in toggles_to_write.items():
                        self._pending.setdefault(pending_key, pending_value)
        finally:
            self._write_lock.release()

    def _drain_pending(self) -> dict[str, str]:
        """Atomically remove and return all currently staged values."""
        with self._staging_lock:
            drained = dict(self._pending)
            self._pending.clear()
            return drained

    def _write_atomically(self, json_text: str) -> None:
        """Write to a sibling temp file then atomically replace the target."""
        temp_path = str(self._settings_path) + ".tmp"
        Path(temp_path).write_text(json_text, encoding="utf-8")
        # os.replace is atomic on POSIX and Windows and overwrites the target
        # whether or not it already exists.
        os.replace(temp_path, str(self._settings_path))

    @staticmethod
    def _merge_toggles(existing_json: str, updates: dict[str, str]) -> str:
        """Merge ``updates`` into the ``Toggles`` section, preserving everything else.

        Only the ``Toggles`` section is touched: other top-level sections and
        untouched toggles keep their original value and JSON type (a bool stays a
        bool). New toggle keys are appended. A missing ``Toggles`` section is
        created. Insertion order is preserved because Python dicts are ordered.
        """
        try:
            existing_document: dict[str, Any] = json.loads(existing_json)
        except json.JSONDecodeError:
            existing_document = {}
        if not isinstance(existing_document, dict):
            existing_document = {}

        toggles_section = existing_document.get("Toggles")
        if isinstance(toggles_section, dict):
            # Update existing keys in place (preserving position); append new ones.
            for update_key, update_value in updates.items():
                toggles_section[update_key] = update_value
        else:
            # No Toggles section yet: append one at the end of the document.
            existing_document["Toggles"] = dict(updates)

        return json.dumps(existing_document, indent=2)
