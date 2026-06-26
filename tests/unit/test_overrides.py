"""Port of OverrideTests.cs: override resolution and precedence over strategies."""

from __future__ import annotations

from ftrio.override_resolver import OverrideResolver
from ftrio.parsers import AppSettingsToggleParser, StrategyToggleParser
from ftrio.strategies import PercentageRolloutStrategy
from tests.conftest import FakeContextAccessor


class _FakeOverrideParser:
    """Test double exposing only ``get_override`` from a fixed map."""

    def __init__(self, overrides: dict[tuple[str, str], bool]) -> None:
        self._overrides = overrides

    def get_toggle_status(self, toggle: str) -> bool:
        raise NotImplementedError

    def parse_bool_value_from_source(self, status: str) -> bool:
        raise NotImplementedError

    def get_override(self, toggle_key: str, user_id: str) -> bool | None:
        return self._overrides.get((toggle_key, user_id))


def _build_resolver(
    accessor: FakeContextAccessor, overrides: dict[tuple[str, str], bool] | None = None
) -> OverrideResolver:
    return OverrideResolver(accessor, _FakeOverrideParser(overrides or {}))


# ── OverrideResolver ─────────────────────────────────────────────────────────


def test_override_resolver_returns_true_when_override_is_true():
    resolver = _build_resolver(FakeContextAccessor("alice"), {("MyToggle", "alice"): True})
    assert resolver.get_override("MyToggle") is True


def test_override_resolver_returns_false_when_override_is_false():
    resolver = _build_resolver(FakeContextAccessor("alice"), {("MyToggle", "alice"): False})
    assert resolver.get_override("MyToggle") is False


def test_override_resolver_returns_none_when_no_override_for_user():
    resolver = _build_resolver(FakeContextAccessor("bob"), {("MyToggle", "alice"): True})
    assert resolver.get_override("MyToggle") is None


def test_override_resolver_returns_none_when_no_override_for_key():
    resolver = _build_resolver(FakeContextAccessor("alice"), {("OtherToggle", "alice"): True})
    assert resolver.get_override("MyToggle") is None


def test_override_resolver_returns_none_when_no_user_context():
    resolver = _build_resolver(FakeContextAccessor(None), {("MyToggle", "alice"): True})
    assert resolver.get_override("MyToggle") is None


def test_override_resolver_returns_none_when_no_overrides_exist():
    resolver = _build_resolver(FakeContextAccessor("alice"))
    assert resolver.get_override("MyToggle") is None


# ── AppSettingsToggleParser.get_override ─────────────────────────────────────


def test_app_settings_parser_get_override_returns_false_for_explicit_false_override(
    test_app_settings_dir,
):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.get_override("FakeTrue", "user-override-off") is False


def test_app_settings_parser_get_override_returns_true_for_explicit_true_override(
    test_app_settings_dir,
):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.get_override("FakeFalse", "user-override-on") is True


def test_app_settings_parser_get_override_returns_none_when_key_has_no_overrides(
    test_app_settings_dir,
):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.get_override("ButtonToggle", "anyone") is None


def test_app_settings_parser_get_override_returns_none_when_user_not_in_override_list(
    test_app_settings_dir,
):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.get_override("FakeTrue", "unknown-user") is None


# ── StrategyToggleParser override precedence ─────────────────────────────────


def test_strategy_parser_override_wins_over_boolean_strategy_true(test_app_settings_dir):
    parser = StrategyToggleParser.with_context_accessor(
        FakeContextAccessor("user-override-off"), base_path=test_app_settings_dir
    )
    assert parser.get_toggle_status("FakeTrue") is False


def test_strategy_parser_override_wins_over_boolean_strategy_false(test_app_settings_dir):
    parser = StrategyToggleParser.with_context_accessor(
        FakeContextAccessor("user-override-on"), base_path=test_app_settings_dir
    )
    assert parser.get_toggle_status("FakeFalse") is True


def test_strategy_parser_override_does_not_affect_other_users(test_app_settings_dir):
    parser = StrategyToggleParser.with_context_accessor(
        FakeContextAccessor("other-user"), base_path=test_app_settings_dir
    )
    assert parser.get_toggle_status("FakeTrue") is True
    assert parser.get_toggle_status("FakeFalse") is False


def test_strategy_parser_without_override_resolver_behaves_normally(test_app_settings_dir):
    parser = StrategyToggleParser(base_path=test_app_settings_dir)
    assert parser.get_toggle_status("FakeTrue") is True
    assert parser.get_toggle_status("FakeFalse") is False


def test_strategy_parser_override_wins_over_percentage_strategy(test_app_settings_dir):
    # StrategyPercentageAlwaysOn is "100%", but the override forces it off for
    # "locked-out-user".
    parser = StrategyToggleParser.with_context_accessor(
        FakeContextAccessor("locked-out-user"),
        PercentageRolloutStrategy(),
        base_path=test_app_settings_dir,
    )
    assert parser.get_toggle_status("StrategyPercentageAlwaysOn") is False
