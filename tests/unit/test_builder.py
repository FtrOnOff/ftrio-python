"""Port of ToggleParserBuilderTests.cs: fluent chain wiring and override behaviour."""

from __future__ import annotations

import pytest

from ftrio import ToggleParserProvider
from ftrio.builder import ToggleParserBuilder
from ftrio.interfaces import ToggleDecisionStrategy
from ftrio.parsers import StrategyToggleParser
from tests.conftest import TEST_APP_SETTINGS_DIR, FakeContextAccessor


class _CustomStrategyTestDouble(ToggleDecisionStrategy):
    """A custom strategy used to prove with_strategy wires it into the chain."""

    def can_handle(self, raw_value: str) -> bool:
        return raw_value == "custom"

    def should_execute(self, toggle_key: str, raw_value: str) -> bool:
        return True


# ── build() returns a StrategyToggleParser for every configuration ───────────


def test_build_returns_strategy_parser_when_no_strategies_added():
    assert isinstance(ToggleParserBuilder().build(), StrategyToggleParser)


def test_build_returns_strategy_parser_with_percentage_rollout():
    assert isinstance(ToggleParserBuilder().with_percentage_rollout().build(), StrategyToggleParser)


def test_build_returns_strategy_parser_with_blue_green():
    assert isinstance(ToggleParserBuilder().with_blue_green().build(), StrategyToggleParser)


def test_build_returns_strategy_parser_with_user_targeting():
    result = ToggleParserBuilder().with_user_targeting(FakeContextAccessor()).build()
    assert isinstance(result, StrategyToggleParser)


def test_build_returns_strategy_parser_with_attribute_rules():
    result = ToggleParserBuilder().with_attribute_rules(FakeContextAccessor()).build()
    assert isinstance(result, StrategyToggleParser)


def test_build_returns_strategy_parser_with_ab_testing():
    result = ToggleParserBuilder().with_ab_testing(FakeContextAccessor()).build()
    assert isinstance(result, StrategyToggleParser)


def test_build_returns_strategy_parser_with_all_context_strategies():
    result = ToggleParserBuilder().with_context_strategies(FakeContextAccessor()).build()
    assert isinstance(result, StrategyToggleParser)


def test_build_returns_strategy_parser_with_custom_strategy():
    result = ToggleParserBuilder().with_strategy(_CustomStrategyTestDouble()).build()
    assert isinstance(result, StrategyToggleParser)


def test_build_returns_strategy_parser_with_overrides():
    result = ToggleParserBuilder().with_overrides(FakeContextAccessor()).build()
    assert isinstance(result, StrategyToggleParser)


def test_build_returns_strategy_parser_with_full_chain():
    accessor = FakeContextAccessor()
    result = (
        ToggleParserBuilder()
        .with_context_strategies(accessor)
        .with_percentage_rollout()
        .with_blue_green()
        .with_overrides(accessor)
        .build()
    )
    assert isinstance(result, StrategyToggleParser)


# ── Fluent chaining returns the same builder instance ────────────────────────


def test_builder_methods_return_same_instance_for_chaining():
    builder = ToggleParserBuilder()
    assert builder.with_percentage_rollout() is builder


def test_with_user_targeting_returns_same_instance():
    builder = ToggleParserBuilder()
    assert builder.with_user_targeting(FakeContextAccessor()) is builder


def test_with_blue_green_returns_same_instance():
    builder = ToggleParserBuilder()
    assert builder.with_blue_green() is builder


def test_with_overrides_returns_same_instance():
    builder = ToggleParserBuilder()
    assert builder.with_overrides(FakeContextAccessor()) is builder


# ── Provider entry points ────────────────────────────────────────────────────


def test_provider_builder_returns_builder_instance():
    assert isinstance(ToggleParserProvider.builder(), ToggleParserBuilder)


def test_provider_builder_returns_different_instance_each_call():
    assert ToggleParserProvider.builder() is not ToggleParserProvider.builder()


def test_configure_builder_installs_built_parser():
    ToggleParserProvider.configure_builder(
        lambda builder: builder.with_percentage_rollout().with_blue_green()
    )
    assert isinstance(ToggleParserProvider.get_instance(), StrategyToggleParser)


# ── with_overrides() accessor-capture and error behaviour ────────────────────


def test_with_overrides_no_argument_returns_builder_when_accessor_registered():
    builder = ToggleParserBuilder().with_context_strategies(FakeContextAccessor())
    assert builder.with_overrides() is builder


def test_with_overrides_no_argument_raises_when_no_accessor_registered():
    with pytest.raises(ValueError):
        ToggleParserBuilder().with_overrides()


def test_build_with_overrides_via_no_argument_overload():
    accessor = FakeContextAccessor()
    result = (
        ToggleParserBuilder().with_context_strategies(accessor).with_overrides().build()
    )
    assert isinstance(result, StrategyToggleParser)


def test_with_user_targeting_captures_accessor_for_later_with_overrides():
    accessor = FakeContextAccessor()
    result = ToggleParserBuilder().with_user_targeting(accessor).with_overrides().build()
    assert isinstance(result, StrategyToggleParser)


def test_with_ab_testing_captures_accessor_for_later_with_overrides():
    accessor = FakeContextAccessor()
    result = ToggleParserBuilder().with_ab_testing(accessor).with_overrides().build()
    assert isinstance(result, StrategyToggleParser)


def test_with_attribute_rules_captures_accessor_for_later_with_overrides():
    accessor = FakeContextAccessor()
    result = ToggleParserBuilder().with_attribute_rules(accessor).with_overrides().build()
    assert isinstance(result, StrategyToggleParser)


# ── Built parser applies overrides at runtime ────────────────────────────────


def test_built_parser_applies_override_via_explicit_accessor():
    accessor = FakeContextAccessor("user-override-off")
    parser = (
        ToggleParserBuilder()
        .with_base_path(TEST_APP_SETTINGS_DIR)
        .with_overrides(accessor)
        .build()
    )
    assert parser.get_toggle_status("FakeTrue") is False


def test_built_parser_applies_override_via_no_argument_overload():
    accessor = FakeContextAccessor("user-override-off")
    parser = (
        ToggleParserBuilder()
        .with_base_path(TEST_APP_SETTINGS_DIR)
        .with_user_targeting(accessor)
        .with_overrides()
        .build()
    )
    assert parser.get_toggle_status("FakeTrue") is False


def test_built_parser_leaves_value_unchanged_for_user_without_override():
    accessor = FakeContextAccessor("other-user")
    parser = (
        ToggleParserBuilder()
        .with_base_path(TEST_APP_SETTINGS_DIR)
        .with_overrides(accessor)
        .build()
    )
    assert parser.get_toggle_status("FakeTrue") is True


# ── BooleanStrategy auto-append (the always-present fallback) ─────────────────


def test_boolean_strategy_is_auto_appended_so_plain_booleans_resolve():
    # With no boolean strategy explicitly added, plain true/false must still work.
    parser = ToggleParserBuilder().with_base_path(TEST_APP_SETTINGS_DIR).build()
    assert parser.get_toggle_status("FakeTrue") is True
    assert parser.get_toggle_status("FakeFalse") is False
