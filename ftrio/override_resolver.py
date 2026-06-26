"""Resolves per-user overrides by combining a context accessor with a config reader."""

from __future__ import annotations

from .context import FtrIOContextAccessor
from .interfaces import ToggleParser


class OverrideResolver:
    """Looks up an explicit per-user override for the current context.

    A thin collaborator: it pairs "who is the current user" (the context accessor)
    with "what override is configured for that user" (a config-reading parser).
    Callers never construct it directly; ``StrategyToggleParser`` builds one when
    a context accessor is supplied, which is why overrides only apply in the
    context-aware configuration.
    """

    def __init__(
        self, context_accessor: FtrIOContextAccessor, config_reader: ToggleParser
    ) -> None:
        self._context_accessor = context_accessor
        self._config_reader = config_reader

    def get_override(self, toggle_key: str) -> bool | None:
        """Return the override for the current user, or ``None`` if none applies.

        Returns ``None`` when there is no current user: with nobody to key the
        override on, there is nothing to resolve.
        """
        user_id = self._context_accessor.get_user_id()
        if user_id is None:
            return None
        return self._config_reader.get_override(toggle_key, user_id)
