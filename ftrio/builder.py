"""Fluent builder for constructing a ``StrategyToggleParser``."""

from __future__ import annotations

from .context import FtrIOContextAccessor
from .interfaces import ToggleDecisionStrategy, ToggleValueProvider
from .parsers.strategy_toggle_parser import StrategyToggleParser
from .strategies.ab_test_strategy import ABTestStrategy
from .strategies.attribute_rule_strategy import AttributeRuleStrategy
from .strategies.blue_green_strategy import BlueGreenStrategy
from .strategies.percentage_rollout_strategy import PercentageRolloutStrategy
from .strategies.user_targeting_strategy import UserTargetingStrategy


class ToggleParserBuilder:
    """Builds a ``StrategyToggleParser`` from a readable chain of named methods.

    Each method returns ``self`` so calls chain fluently. ``BooleanStrategy`` is
    appended automatically by ``StrategyToggleParser``; never add it here.
    Strategy registration order is preserved, which matters because the parser
    uses first-match strategy selection.
    """

    def __init__(self) -> None:
        self._strategies: list[ToggleDecisionStrategy] = []
        self._context_accessor: FtrIOContextAccessor | None = None
        self._context_accessor_for_overrides: FtrIOContextAccessor | None = None
        self._base_path: str | None = None
        self._provider: ToggleValueProvider | None = None

    def with_user_targeting(
        self, context_accessor: FtrIOContextAccessor
    ) -> ToggleParserBuilder:
        """Add user-list targeting (``"users:alice,bob"``)."""
        self._context_accessor = context_accessor
        self._strategies.append(UserTargetingStrategy(context_accessor))
        return self

    def with_attribute_rules(
        self, context_accessor: FtrIOContextAccessor
    ) -> ToggleParserBuilder:
        """Add attribute-rule targeting (``"attribute:plan equals premium"``)."""
        self._context_accessor = context_accessor
        self._strategies.append(AttributeRuleStrategy(context_accessor))
        return self

    def with_ab_testing(
        self, context_accessor: FtrIOContextAccessor
    ) -> ToggleParserBuilder:
        """Add deterministic per-user A/B bucketing (``"ab:50"``)."""
        self._context_accessor = context_accessor
        self._strategies.append(ABTestStrategy(context_accessor))
        return self

    def with_context_strategies(
        self, context_accessor: FtrIOContextAccessor
    ) -> ToggleParserBuilder:
        """Add user targeting, attribute rules, and A/B in one call, same accessor."""
        self._context_accessor = context_accessor
        self._strategies.append(UserTargetingStrategy(context_accessor))
        self._strategies.append(AttributeRuleStrategy(context_accessor))
        self._strategies.append(ABTestStrategy(context_accessor))
        return self

    def with_percentage_rollout(self) -> ToggleParserBuilder:
        """Add probabilistic percentage rollouts (``"20%"``)."""
        self._strategies.append(PercentageRolloutStrategy())
        return self

    def with_blue_green(self) -> ToggleParserBuilder:
        """Add deployment-slot gating, reading the active slot from appsettings.json."""
        self._strategies.append(BlueGreenStrategy.from_config())
        return self

    def with_overrides(
        self, context_accessor: FtrIOContextAccessor | None = None
    ) -> ToggleParserBuilder:
        """Enable per-user overrides; checked before any strategy.

        Called without an accessor, it reuses the one already supplied to
        ``with_context_strategies`` / ``with_user_targeting`` / ``with_ab_testing``
        / ``with_attribute_rules`` and raises if none was registered. Called with
        an accessor, it uses that one explicitly.
        """
        if context_accessor is not None:
            self._context_accessor_for_overrides = context_accessor
            return self

        if self._context_accessor is None:
            raise ValueError(
                "with_overrides() requires an FtrIOContextAccessor. "
                "Call with_context_strategies, with_user_targeting, with_ab_testing, "
                "or with_attribute_rules before calling with_overrides(), or use "
                "with_overrides(context_accessor) to supply one explicitly."
            )
        self._context_accessor_for_overrides = self._context_accessor
        return self

    def with_strategy(
        self, strategy: ToggleDecisionStrategy
    ) -> ToggleParserBuilder:
        """Add a custom strategy. Tried in registration order; first match wins."""
        self._strategies.append(strategy)
        return self

    def with_base_path(self, base_path: str) -> ToggleParserBuilder:
        """Set a custom base path for appsettings.json resolution."""
        self._base_path = base_path
        return self

    def with_provider(
        self, provider: ToggleValueProvider
    ) -> ToggleParserBuilder:
        """Source raw values from a provider instead of appsettings.json.

        Mutually exclusive with ``with_base_path``.
        """
        self._provider = provider
        return self

    def build(self) -> StrategyToggleParser:
        """Construct the ``StrategyToggleParser`` from the current builder state."""
        strategies = tuple(self._strategies)

        if self._provider is not None:
            return StrategyToggleParser(
                *strategies,
                provider=self._provider,
                context_accessor=self._context_accessor_for_overrides,
            )

        return StrategyToggleParser(
            *strategies,
            base_path=self._base_path,
            context_accessor=self._context_accessor_for_overrides,
        )
