"""Parser that routes raw values through a chain of decision strategies."""

from __future__ import annotations

from ..config import AppSettingsConfiguration, app_settings_file_exists, default_base_path
from ..context import FtrIOContextAccessor
from ..exceptions import ToggleDoesNotExistError, ToggleParsedOutOfRangeError
from ..interfaces import ToggleDecisionStrategy, ToggleParser, ToggleValueProvider
from ..override_resolver import OverrideResolver
from ..strategies.boolean_strategy import BooleanStrategy
from .app_settings_toggle_parser import AppSettingsToggleParser


class StrategyToggleParser(ToggleParser):
    """Resolves toggles by trying a chain of strategies against the raw value.

    ``BooleanStrategy`` is always appended as the final fallback so plain
    ``true``/``false`` config keeps working under any chain. Raw values come from
    either appsettings.json (default) or an injected ``ToggleValueProvider``.

    The .NET type exposes this through a matrix of constructor overloads. Python
    has no overloads, so construction is a single keyword-driven constructor plus
    classmethods (see PORTING_NOTES.md); the four meaningful shapes are:
    strategies only, with a context accessor, with a base path, and with a value
    provider, each optionally context-aware for overrides.
    """

    def __init__(
        self,
        *strategies: ToggleDecisionStrategy,
        context_accessor: FtrIOContextAccessor | None = None,
        base_path: str | None = None,
        provider: ToggleValueProvider | None = None,
    ) -> None:
        self._strategies = self._build_strategy_chain(strategies)
        self._provider = provider

        if provider is not None:
            # Provider variant: overrides resolve against the default appsettings.json
            # location, and reads never touch the config file directly.
            self._overrides = (
                OverrideResolver(context_accessor, AppSettingsToggleParser())
                if context_accessor is not None
                else None
            )
            self._config_file_exists = True
            self._configuration: AppSettingsConfiguration | None = None
            return

        resolved_base_path = base_path if base_path is not None else default_base_path()

        # Overrides are an internal concern: when a context accessor is supplied we
        # build the resolver here, pointed at the same appsettings.json the strategy
        # chain reads from. Callers never construct OverrideResolver themselves.
        self._overrides = (
            OverrideResolver(context_accessor, AppSettingsToggleParser(resolved_base_path))
            if context_accessor is not None
            else None
        )

        self._config_file_exists = app_settings_file_exists(resolved_base_path)
        self._configuration = (
            AppSettingsConfiguration(resolved_base_path)
            if self._config_file_exists
            else None
        )

    @classmethod
    def with_context_accessor(
        cls,
        context_accessor: FtrIOContextAccessor | None,
        *strategies: ToggleDecisionStrategy,
        base_path: str | None = None,
    ) -> StrategyToggleParser:
        """Build a parser whose overrides resolve against the current context."""
        return cls(*strategies, context_accessor=context_accessor, base_path=base_path)

    @classmethod
    def with_provider(
        cls,
        provider: ToggleValueProvider,
        *strategies: ToggleDecisionStrategy,
        context_accessor: FtrIOContextAccessor | None = None,
    ) -> StrategyToggleParser:
        """Build a parser that sources raw values from a ``ToggleValueProvider``."""
        return cls(
            *strategies, provider=provider, context_accessor=context_accessor
        )

    def get_toggle_status(self, toggle: str) -> bool:
        """Resolve a toggle: override first, then raw value, then first-match strategy."""
        # Overrides win unconditionally before any strategy is consulted.
        if self._overrides is not None:
            override_value = self._overrides.get_override(toggle)
            if override_value is not None:
                return override_value

        if self._provider is not None:
            raw_value = self._provider.get_raw_value(toggle)
            if raw_value is None:
                raise ToggleDoesNotExistError()
        else:
            if not self._config_file_exists or self._configuration is None:
                return True
            raw_value = self._configuration.get_value(f"Toggles:{toggle}")
            if raw_value is None:
                raise ToggleDoesNotExistError()

        matching_strategy = self._first_matching_strategy(raw_value)
        if matching_strategy is None:
            raise ToggleParsedOutOfRangeError()
        return matching_strategy.should_execute(toggle, raw_value)

    def parse_bool_value_from_source(self, status: str) -> bool:
        """Resolve a raw value through the chain without a toggle key."""
        matching_strategy = self._first_matching_strategy(status)
        if matching_strategy is None:
            raise ToggleParsedOutOfRangeError()
        return matching_strategy.should_execute("", status)

    def get_override(self, toggle_key: str, user_id: str) -> bool | None:
        """Return the configured override value for ``toggle_key``/``user_id``."""
        if self._configuration is None:
            return None
        override_value = self._configuration.get_value(
            f"TogglesOverrides:{toggle_key}:{user_id}"
        )
        if override_value is None:
            return None
        if override_value.lower() == "true" or override_value == "1":
            return True
        if override_value.lower() == "false" or override_value == "0":
            return False
        return None

    def _first_matching_strategy(
        self, raw_value: str
    ) -> ToggleDecisionStrategy | None:
        """Return the first strategy whose ``can_handle`` accepts the value."""
        for strategy in self._strategies:
            if strategy.can_handle(raw_value):
                return strategy
        return None

    @staticmethod
    def _build_strategy_chain(
        strategies: tuple[ToggleDecisionStrategy, ...],
    ) -> list[ToggleDecisionStrategy]:
        """Append ``BooleanStrategy`` as the final fallback if not already present."""
        strategy_chain = list(strategies)
        if not any(isinstance(strategy, BooleanStrategy) for strategy in strategy_chain):
            strategy_chain.append(BooleanStrategy())
        return strategy_chain
