"""Ambient, process-global provider of the active toggle parser.

The .NET source models this as a ``static`` class. The faithful Python port is a
module-level holder: ``ToggleParserProvider`` is a namespace over module state,
not something you instantiate. It is deliberately process-global ambient state,
exactly like the C# static, because the ``@toggle`` decorators have no other way
to reach the configured parser at call time.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .interfaces import ToggleParser
from .parsers.app_settings_toggle_parser import AppSettingsToggleParser

if TYPE_CHECKING:
    from .builder import ToggleParserBuilder

_configured_parser: ToggleParser | None = None


class ToggleParserProvider:
    """Static-style accessor for the ambient ``ToggleParser``.

    Defaults to an ``AppSettingsToggleParser`` (reading appsettings.json from the
    working directory). Replace it at application startup via ``configure`` or one
    of the builder entry points.
    """

    @staticmethod
    def get_instance() -> ToggleParser:
        """Return the configured parser, lazily defaulting to appsettings.json."""
        global _configured_parser
        if _configured_parser is None:
            _configured_parser = AppSettingsToggleParser()
        return _configured_parser

    @staticmethod
    def configure(parser: ToggleParser) -> None:
        """Install ``parser`` as the ambient parser for all gated calls."""
        global _configured_parser
        if parser is None:
            raise ValueError("parser must not be None")
        _configured_parser = parser

    @staticmethod
    def builder() -> ToggleParserBuilder:
        """Return a fresh builder for fluent construction of a parser."""
        from .builder import ToggleParserBuilder

        return ToggleParserBuilder()

    @staticmethod
    def configure_builder(configure: Callable[[ToggleParserBuilder], object]) -> None:
        """Build a parser via a configuration callback and install it.

        Equivalent to creating a builder, chaining methods on it inside
        ``configure``, then passing ``build()`` to ``configure``.
        """
        from .builder import ToggleParserBuilder

        builder = ToggleParserBuilder()
        configure(builder)
        ToggleParserProvider.configure(builder.build())

    @staticmethod
    def reset() -> None:
        """Clear the ambient parser so the next access re-creates the default.

        Not present in the .NET source; added so tests can isolate ambient state
        between cases. Documented as additive in PORTING_NOTES.md.
        """
        global _configured_parser
        _configured_parser = None
