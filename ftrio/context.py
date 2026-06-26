"""Structural contract for supplying per-request user context to FtrIO.

The .NET source models this as ``IFtrIOContextAccessor``. FtrIO calls these
methods on objects the *consumer* supplies, so a structural ``Protocol`` is the
right fit in Python: any object with the two methods satisfies the contract,
no explicit inheritance required.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class FtrIOContextAccessor(Protocol):
    """Supplies the current user id and named attributes for context-aware toggles.

    Implementations are provided by the host application (e.g. wrapping an HTTP
    request, or a simulated accessor in tests). Returning ``None`` from either
    method means "no context available" (for instance a background job), and the
    context-aware strategies treat that as "do not match".
    """

    def get_user_id(self) -> str | None:
        """Return the unique identifier for the current user or request context.

        Returns ``None`` when no context is available; strategies that key off the
        user id treat that as a non-match rather than an error.
        """
        ...

    def get_attribute(self, name: str) -> str | None:
        """Return the value of a named attribute for the current context.

        For example ``get_attribute("plan")`` might return ``"premium"``. Returns
        ``None`` if the attribute is not available for the current context.
        """
        ...
