"""The ``@toggle`` and ``@toggle_async`` decorators.

The .NET source gates methods with AspectInjector, which weaves the toggle check
directly into the decorated method's IL at compile time. Python has no IL-weaving
equivalent, so the faithful substitute is a decorator that wraps the function and
performs the same check at call time. The behaviour matches the woven aspect:

  * the toggle key defaults to the decorated function's own name;
  * when the toggle is off, the sync decorator returns ``None`` (the type
    default) and the async decorator returns an awaitable that resolves to
    ``None`` (never a bare ``None`` that would break ``await``).

The wrapper is tagged with ``_ftrio_toggle_key`` so ``FeatureToggle`` can detect
decoration, the Python stand-in for ``GetCustomAttribute<Toggle>()``.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, overload

from .provider import ToggleParserProvider

_SyncFunc = TypeVar("_SyncFunc", bound=Callable[..., Any])
_AsyncFunc = TypeVar("_AsyncFunc", bound=Callable[..., Awaitable[Any]])

_TOGGLE_KEY_MARKER = "_ftrio_toggle_key"


@overload
def toggle(key: _SyncFunc) -> _SyncFunc: ...
@overload
def toggle(key: str | None = None) -> Callable[[_SyncFunc], _SyncFunc]: ...


def toggle(key: str | Callable[..., Any] | None = None) -> Any:
    """Gate a synchronous function on a toggle, keyed by its own name by default.

    Usable bare (``@toggle``) or with an explicit key (``@toggle("MyKey")``). When
    the resolved toggle is off the wrapped function is not called and ``None`` is
    returned, mirroring the .NET aspect returning the type default.
    """
    # Support bare @toggle (decorator applied directly to the function).
    if callable(key):
        return _build_sync_wrapper(key, key.__name__)

    def decorator(decorated_function: _SyncFunc) -> _SyncFunc:
        resolved_key = key if key is not None else decorated_function.__name__
        return _build_sync_wrapper(decorated_function, resolved_key)

    return decorator


@overload
def toggle_async(key: _AsyncFunc) -> _AsyncFunc: ...
@overload
def toggle_async(key: str | None = None) -> Callable[[_AsyncFunc], _AsyncFunc]: ...


def toggle_async(key: str | Callable[..., Any] | None = None) -> Any:
    """Gate an async function on a toggle, keyed by its own name by default.

    Like ``@toggle`` but for coroutine functions: when off it returns an awaitable
    resolving to ``None``, so callers can ``await`` the result safely whether the
    toggle is on or off.
    """
    if callable(key):
        return _build_async_wrapper(key, key.__name__)

    def decorator(decorated_function: _AsyncFunc) -> _AsyncFunc:
        resolved_key = key if key is not None else decorated_function.__name__
        return _build_async_wrapper(decorated_function, resolved_key)

    return decorator


def _build_sync_wrapper(
    decorated_function: Callable[..., Any], resolved_key: str
) -> Any:
    @functools.wraps(decorated_function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if ToggleParserProvider.get_instance().get_toggle_status(resolved_key):
            return decorated_function(*args, **kwargs)
        return None

    setattr(wrapper, _TOGGLE_KEY_MARKER, resolved_key)
    return wrapper


async def _resolved_none() -> None:
    """An awaitable that immediately resolves to ``None`` (the off-path result)."""
    return None


def _build_async_wrapper(
    decorated_function: Callable[..., Awaitable[Any]], resolved_key: str
) -> Any:
    # The wrapper is a plain function (not ``async def``) so the gating check runs
    # synchronously at call time, mirroring the .NET woven Around advice: a missing
    # key or unparseable value raises at the call site, not as a faulted awaitable.
    # When on it returns the inner coroutine; when off it returns an awaitable that
    # resolves to None, so callers can ``await`` the result either way.
    @functools.wraps(decorated_function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if ToggleParserProvider.get_instance().get_toggle_status(resolved_key):
            return decorated_function(*args, **kwargs)
        return _resolved_none()

    setattr(wrapper, _TOGGLE_KEY_MARKER, resolved_key)
    return wrapper


def get_toggle_key_marker(candidate: object) -> str | None:
    """Return the toggle key a callable was decorated with, or ``None``.

    This is how ``FeatureToggle`` detects ``@toggle`` decoration without importing
    decorator internals, mirroring the reflection-based attribute lookup in .NET.
    """
    return getattr(candidate, _TOGGLE_KEY_MARKER, None)
