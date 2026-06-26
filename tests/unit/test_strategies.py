"""Port of StrategyTests.cs: per-strategy can_handle / should_execute behaviour."""

from __future__ import annotations

import random

import pytest

from ftrio.exceptions import ToggleParsedOutOfRangeError
from ftrio.strategies import BlueGreenStrategy, BooleanStrategy, PercentageRolloutStrategy

# ── BooleanStrategy ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["true", "True", "TRUE", "false", "False", "FALSE", "1", "0"])
def test_boolean_strategy_can_handle_returns_true_for_valid_boolean_values(value):
    assert BooleanStrategy().can_handle(value) is True


@pytest.mark.parametrize("value", ["yes", "no", "ASDF", "50%", "blue", ""])
def test_boolean_strategy_can_handle_returns_false_for_non_boolean_values(value):
    assert BooleanStrategy().can_handle(value) is False


@pytest.mark.parametrize("value", ["true", "True", "TRUE", "1"])
def test_boolean_strategy_should_execute_returns_true_for_truthy_values(value):
    assert BooleanStrategy().should_execute("key", value) is True


@pytest.mark.parametrize("value", ["false", "False", "FALSE", "0"])
def test_boolean_strategy_should_execute_returns_false_for_falsy_values(value):
    assert BooleanStrategy().should_execute("key", value) is False


# ── PercentageRolloutStrategy ────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["0%", "50%", "100%", "  25%  "])
def test_percentage_rollout_strategy_can_handle_returns_true_for_percentage_values(value):
    assert PercentageRolloutStrategy().can_handle(value) is True


@pytest.mark.parametrize("value", ["true", "blue", "50", "ASDF"])
def test_percentage_rollout_strategy_can_handle_returns_false_for_non_percentage_values(value):
    assert PercentageRolloutStrategy().can_handle(value) is False


def test_percentage_rollout_strategy_should_execute_always_returns_false_at_zero_percent():
    strategy = PercentageRolloutStrategy()
    for _ in range(100):
        assert strategy.should_execute("key", "0%") is False


def test_percentage_rollout_strategy_should_execute_always_returns_true_at_one_hundred_percent():
    strategy = PercentageRolloutStrategy()
    for _ in range(100):
        assert strategy.should_execute("key", "100%") is True


def test_percentage_rollout_strategy_should_execute_returns_mix_of_true_and_false_at_fifty_percent():
    random.seed(20240626)
    strategy = PercentageRolloutStrategy()
    results = [strategy.should_execute("key", "50%") for _ in range(1000)]
    assert any(results), "Expected at least one true in 1000 trials at 50%"
    assert any(not result for result in results), "Expected at least one false in 1000 trials at 50%"


@pytest.mark.parametrize("value", ["101%", "-1%", "abc%"])
def test_percentage_rollout_strategy_should_execute_throws_out_of_range_for_invalid_values(value):
    with pytest.raises(ToggleParsedOutOfRangeError):
        PercentageRolloutStrategy().should_execute("key", value)


# ── BlueGreenStrategy (explicit slots) ───────────────────────────────────────


def test_blue_green_strategy_can_handle_returns_true_for_known_slot():
    strategy = BlueGreenStrategy("blue", "blue", "green")
    assert strategy.can_handle("blue") is True
    assert strategy.can_handle("green") is True


def test_blue_green_strategy_can_handle_returns_false_for_unknown_slot():
    strategy = BlueGreenStrategy("blue", "blue", "green")
    assert strategy.can_handle("canary") is False
    assert strategy.can_handle("true") is False


def test_blue_green_strategy_can_handle_is_case_insensitive():
    strategy = BlueGreenStrategy("blue", "blue", "green")
    assert strategy.can_handle("Blue") is True
    assert strategy.can_handle("GREEN") is True


def test_blue_green_strategy_should_execute_returns_true_when_current_slot_matches():
    strategy = BlueGreenStrategy("blue", "blue", "green")
    assert strategy.should_execute("key", "blue") is True


def test_blue_green_strategy_should_execute_returns_false_when_current_slot_does_not_match():
    strategy = BlueGreenStrategy("blue", "blue", "green")
    assert strategy.should_execute("key", "green") is False


def test_blue_green_strategy_should_execute_is_case_insensitive():
    strategy = BlueGreenStrategy("blue", "blue", "green")
    assert strategy.should_execute("key", "Blue") is True
    assert strategy.should_execute("key", "BLUE") is True


def test_blue_green_strategy_should_execute_works_with_three_or_more_slots():
    strategy = BlueGreenStrategy("canary", "blue", "green", "canary")
    assert strategy.should_execute("key", "blue") is False
    assert strategy.should_execute("key", "green") is False
    assert strategy.should_execute("key", "canary") is True


def test_blue_green_strategy_can_handle_ignores_whitespace():
    strategy = BlueGreenStrategy("blue", "blue", "green")
    assert strategy.can_handle("  blue  ") is True


# ── BlueGreenStrategy (config-driven, hot-reload) ────────────────────────────


def test_blue_green_strategy_config_driven_can_handle_recognises_known_slots(test_app_settings_dir):
    strategy = BlueGreenStrategy.from_config(test_app_settings_dir)
    assert strategy.can_handle("blue") is True
    assert strategy.can_handle("green") is True


def test_blue_green_strategy_config_driven_can_handle_returns_false_for_unknown_slot(test_app_settings_dir):
    strategy = BlueGreenStrategy.from_config(test_app_settings_dir)
    assert strategy.can_handle("canary") is False


def test_blue_green_strategy_config_driven_should_execute_returns_true_for_current_slot(test_app_settings_dir):
    strategy = BlueGreenStrategy.from_config(test_app_settings_dir)
    assert strategy.should_execute("key", "blue") is True


def test_blue_green_strategy_config_driven_should_execute_returns_false_for_inactive_slot(test_app_settings_dir):
    strategy = BlueGreenStrategy.from_config(test_app_settings_dir)
    assert strategy.should_execute("key", "green") is False


def test_blue_green_strategy_config_driven_missing_config_can_handle_returns_false(tmp_path):
    strategy = BlueGreenStrategy.from_config(str(tmp_path))
    assert strategy.can_handle("blue") is False
