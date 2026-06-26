"""The explicit execute-if-on API (the .NET ``FeatureToggle<T>``)."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from .decorators import get_toggle_key_marker
from .enums import ToggleStatus
from .exceptions import ToggleAttributeMissingError
from .interfaces import ToggleParser
from .parsers.app_settings_toggle_parser import AppSettingsToggleParser


class FeatureToggle:
    """Runs a callable only when its toggle is on, returning the default otherwise.

    This is the explicit alternative to the ``@toggle`` decorator: instead of
    gating at definition time, you pass a callable to ``execute_method_if_toggle_on``
    and FeatureToggle decides whether to invoke it. The .NET type is generic
    (``FeatureToggle<T>``); Python duck-types return values, so the single
    non-generic class collapses the ``IFeatureToggle<T>`` interface and its
    implementation together.

    Key resolution mirrors the .NET ``ResolveToggleKey``: an explicit ``key_name``
    always wins; otherwise the callable must carry the ``@toggle`` marker and its
    key is used; if neither is present, ``ToggleAttributeMissingError`` is raised.
    """

    @staticmethod
    def _status_from_bool(active: bool) -> ToggleStatus:
        return ToggleStatus.ACTIVE if active else ToggleStatus.INACTIVE

    def get_toggle_state(self, parser: ToggleParser, toggle_key: str) -> ToggleStatus:
        """Return the toggle's state as a ``ToggleStatus`` via ``parser``."""
        return self._status_from_bool(parser.get_toggle_status(toggle_key))

    @staticmethod
    def _resolve_toggle_key(
        method_to_run: Callable[..., Any], key_name: str | None
    ) -> str:
        """Resolve the toggle key: explicit name, else the ``@toggle`` marker, else raise."""
        if key_name:
            return key_name

        marker_key = get_toggle_key_marker(method_to_run)
        if marker_key is None:
            method_name = getattr(method_to_run, "__name__", repr(method_to_run))
            raise ToggleAttributeMissingError(
                f"Method '{method_name}' has no [Toggle] attribute and no keyName was provided."
            )
        return marker_key

    def execute_method_if_toggle_on(
        self,
        method_to_run: Callable[..., Any],
        parser: ToggleParser | None = None,
        key_name: str | None = None,
    ) -> Any:
        """Invoke ``method_to_run`` if its toggle is on, else return ``None``.

        ``parser`` defaults to an ``AppSettingsToggleParser`` reading appsettings.json,
        matching the .NET default-construction overloads.
        """
        config_parser = parser if parser is not None else AppSettingsToggleParser()
        resolved_key = self._resolve_toggle_key(method_to_run, key_name)
        if self.get_toggle_state(config_parser, resolved_key) == ToggleStatus.ACTIVE:
            return method_to_run()
        return None

    async def execute_method_if_toggle_on_async(
        self,
        method_to_run: Callable[..., Awaitable[Any]],
        parser: ToggleParser | None = None,
        key_name: str | None = None,
    ) -> Any:
        """Await ``method_to_run`` if its toggle is on, else resolve to ``None``.

        Returns an awaitable in both cases so callers can ``await`` safely whether
        the toggle is on or off, mirroring the .NET ``Task.FromResult(default)``
        off-path semantics.
        """
        config_parser = parser if parser is not None else AppSettingsToggleParser()
        resolved_key = self._resolve_toggle_key(method_to_run, key_name)
        if self.get_toggle_state(config_parser, resolved_key) == ToggleStatus.ACTIVE:
            result = method_to_run()
            if inspect.isawaitable(result):
                return await result
            return result
        return None
