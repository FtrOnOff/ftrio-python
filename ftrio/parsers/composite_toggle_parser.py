"""Chains multiple parsers with first-wins fallthrough."""

from __future__ import annotations

from ..exceptions import ToggleDoesNotExistError
from ..interfaces import ToggleParser


class CompositeToggleParser(ToggleParser):
    """Tries several parsers in order; the first to resolve a key wins.

    A parser "misses" only by raising ``ToggleDoesNotExistError``; any other
    outcome (including a resolved ``False``) is a hit and stops the search. This
    is what lets you layer sources, e.g. env-var overrides, then a remote
    provider, then appsettings.json as the durable fallback. If every parser
    misses, the missing-key exception is re-raised so the caller still sees it.
    """

    def __init__(self, *parsers: ToggleParser) -> None:
        if not parsers:
            raise ValueError("At least one parser must be specified.")
        self._parsers = parsers

    def get_toggle_status(self, toggle: str) -> bool:
        """Return the first parser's decision; fall through on a missing key."""
        for parser in self._parsers:
            try:
                return parser.get_toggle_status(toggle)
            except ToggleDoesNotExistError:
                continue
        raise ToggleDoesNotExistError()

    def parse_bool_value_from_source(self, status: str) -> bool:
        """Delegate raw-value parsing to the first parser in the chain."""
        return self._parsers[0].parse_bool_value_from_source(status)
