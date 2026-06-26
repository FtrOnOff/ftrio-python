"""Port of ContextStrategyTests.cs: user targeting, attribute rules, A/B testing."""

from __future__ import annotations

import random

import pytest

from ftrio.strategies import ABTestStrategy, AttributeRuleStrategy, UserTargetingStrategy
from tests.conftest import FakeContextAccessor


def _with_user(user_id: str) -> FakeContextAccessor:
    return FakeContextAccessor(user_id)


def _with_attribute(name: str, value: str) -> FakeContextAccessor:
    return FakeContextAccessor("user-1", {name: value})


def _no_context() -> FakeContextAccessor:
    return FakeContextAccessor(None)


# ── UserTargetingStrategy.can_handle ─────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    ["users:alice,bob", "users:single", "users:alice, bob, charlie", "USERS:alice"],
)
def test_user_targeting_strategy_can_handle_returns_true_for_users_prefix(value):
    assert UserTargetingStrategy(_no_context()).can_handle(value) is True


@pytest.mark.parametrize(
    "value",
    ["true", "20%", "ab:50", "attribute:plan equals premium", "blue", ""],
)
def test_user_targeting_strategy_can_handle_returns_false_for_non_users_values(value):
    assert UserTargetingStrategy(_no_context()).can_handle(value) is False


# ── UserTargetingStrategy.should_execute ─────────────────────────────────────


def test_user_targeting_strategy_should_execute_returns_true_when_user_is_in_list():
    strategy = UserTargetingStrategy(_with_user("alice"))
    assert strategy.should_execute("key", "users:alice,bob,charlie") is True


def test_user_targeting_strategy_should_execute_returns_false_when_user_is_not_in_list():
    strategy = UserTargetingStrategy(_with_user("dave"))
    assert strategy.should_execute("key", "users:alice,bob,charlie") is False


def test_user_targeting_strategy_should_execute_is_case_insensitive():
    strategy = UserTargetingStrategy(_with_user("Alice"))
    assert strategy.should_execute("key", "users:ALICE,bob") is True


def test_user_targeting_strategy_should_execute_trims_whitespace_from_list():
    strategy = UserTargetingStrategy(_with_user("alice"))
    assert strategy.should_execute("key", "users:alice , bob , charlie") is True


def test_user_targeting_strategy_should_execute_returns_false_when_no_user_context():
    strategy = UserTargetingStrategy(_no_context())
    assert strategy.should_execute("key", "users:alice,bob") is False


def test_user_targeting_strategy_should_execute_returns_false_for_empty_list():
    strategy = UserTargetingStrategy(_with_user("alice"))
    assert strategy.should_execute("key", "users:") is False


def test_user_targeting_strategy_should_execute_returns_false_for_single_other_user():
    strategy = UserTargetingStrategy(_with_user("dave"))
    assert strategy.should_execute("key", "users:alice") is False


# ── AttributeRuleStrategy.can_handle ─────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "attribute:plan equals premium",
        "attribute:country notEquals US",
        "attribute:email startsWith admin",
        "attribute:email endsWith @company.com",
        "attribute:email contains +beta",
        "attribute:plan in premium,enterprise",
        "attribute:country notIn US,CA",
        "ATTRIBUTE:plan EQUALS premium",
    ],
)
def test_attribute_rule_strategy_can_handle_returns_true_for_valid_attribute_rules(value):
    assert AttributeRuleStrategy(_no_context()).can_handle(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "true",
        "20%",
        "ab:50",
        "users:alice",
        "attribute:plan",
        "attribute:plan equalsXYZ premium",
        "",
    ],
)
def test_attribute_rule_strategy_can_handle_returns_false_for_non_attribute_rules(value):
    assert AttributeRuleStrategy(_no_context()).can_handle(value) is False


# ── AttributeRuleStrategy.should_execute (all seven operators) ───────────────


def test_attribute_rule_strategy_equals_returns_true_on_match():
    assert AttributeRuleStrategy(_with_attribute("plan", "premium")).should_execute(
        "key", "attribute:plan equals premium"
    ) is True


def test_attribute_rule_strategy_equals_returns_false_on_mismatch():
    assert AttributeRuleStrategy(_with_attribute("plan", "free")).should_execute(
        "key", "attribute:plan equals premium"
    ) is False


def test_attribute_rule_strategy_equals_is_case_insensitive():
    assert AttributeRuleStrategy(_with_attribute("plan", "PREMIUM")).should_execute(
        "key", "attribute:plan equals premium"
    ) is True


def test_attribute_rule_strategy_not_equals_returns_true_when_different():
    assert AttributeRuleStrategy(_with_attribute("plan", "free")).should_execute(
        "key", "attribute:plan notEquals premium"
    ) is True


def test_attribute_rule_strategy_not_equals_returns_false_when_same():
    assert AttributeRuleStrategy(_with_attribute("plan", "premium")).should_execute(
        "key", "attribute:plan notEquals premium"
    ) is False


def test_attribute_rule_strategy_starts_with_returns_true_on_match():
    assert AttributeRuleStrategy(_with_attribute("email", "admin@example.com")).should_execute(
        "key", "attribute:email startsWith admin"
    ) is True


def test_attribute_rule_strategy_starts_with_returns_false_on_mismatch():
    assert AttributeRuleStrategy(_with_attribute("email", "user@example.com")).should_execute(
        "key", "attribute:email startsWith admin"
    ) is False


def test_attribute_rule_strategy_ends_with_returns_true_on_match():
    assert AttributeRuleStrategy(_with_attribute("email", "alice@company.com")).should_execute(
        "key", "attribute:email endsWith @company.com"
    ) is True


def test_attribute_rule_strategy_ends_with_returns_false_on_mismatch():
    assert AttributeRuleStrategy(_with_attribute("email", "alice@other.com")).should_execute(
        "key", "attribute:email endsWith @company.com"
    ) is False


def test_attribute_rule_strategy_contains_returns_true_on_match():
    assert AttributeRuleStrategy(_with_attribute("email", "alice+beta@example.com")).should_execute(
        "key", "attribute:email contains +beta"
    ) is True


def test_attribute_rule_strategy_contains_returns_false_on_mismatch():
    assert AttributeRuleStrategy(_with_attribute("email", "alice@example.com")).should_execute(
        "key", "attribute:email contains +beta"
    ) is False


def test_attribute_rule_strategy_in_returns_true_when_attribute_in_list():
    assert AttributeRuleStrategy(_with_attribute("plan", "enterprise")).should_execute(
        "key", "attribute:plan in premium,enterprise"
    ) is True


def test_attribute_rule_strategy_in_returns_false_when_attribute_not_in_list():
    assert AttributeRuleStrategy(_with_attribute("plan", "free")).should_execute(
        "key", "attribute:plan in premium,enterprise"
    ) is False


def test_attribute_rule_strategy_in_is_case_insensitive():
    assert AttributeRuleStrategy(_with_attribute("plan", "ENTERPRISE")).should_execute(
        "key", "attribute:plan in premium,enterprise"
    ) is True


def test_attribute_rule_strategy_not_in_returns_true_when_attribute_not_in_list():
    assert AttributeRuleStrategy(_with_attribute("country", "IE")).should_execute(
        "key", "attribute:country notIn US,CA"
    ) is True


def test_attribute_rule_strategy_not_in_returns_false_when_attribute_in_list():
    assert AttributeRuleStrategy(_with_attribute("country", "US")).should_execute(
        "key", "attribute:country notIn US,CA"
    ) is False


def test_attribute_rule_strategy_returns_false_when_attribute_not_on_context():
    assert AttributeRuleStrategy(_no_context()).should_execute(
        "key", "attribute:plan equals premium"
    ) is False


def test_attribute_rule_strategy_returns_false_for_malformed_rule():
    assert AttributeRuleStrategy(_with_attribute("plan", "premium")).should_execute(
        "key", "attribute:plan"
    ) is False


# ── ABTestStrategy.can_handle ────────────────────────────────────────────────


@pytest.mark.parametrize("value", ["ab:0", "ab:50", "ab:100", "AB:33"])
def test_ab_test_strategy_can_handle_returns_true_for_valid_ab_values(value):
    assert ABTestStrategy(_no_context()).can_handle(value) is True


@pytest.mark.parametrize(
    "value", ["ab:101", "ab:-1", "ab:abc", "20%", "true", "users:alice", ""]
)
def test_ab_test_strategy_can_handle_returns_false_for_invalid_ab_values(value):
    assert ABTestStrategy(_no_context()).can_handle(value) is False


@pytest.mark.parametrize("value", ["ab:50:round2", "ab:0:salt", "ab:100:my-experiment"])
def test_ab_test_strategy_can_handle_returns_true_for_salted_ab_values(value):
    assert ABTestStrategy(FakeContextAccessor("user-1")).can_handle(value) is True


# ── ABTestStrategy.should_execute ────────────────────────────────────────────


def test_ab_test_strategy_should_execute_always_returns_false_at_zero_percent():
    strategy = ABTestStrategy(_with_user("alice"))
    for index in range(100):
        assert strategy.should_execute(f"key{index}", "ab:0") is False


def test_ab_test_strategy_should_execute_always_returns_true_at_one_hundred_percent():
    strategy = ABTestStrategy(_with_user("alice"))
    for index in range(100):
        assert strategy.should_execute(f"key{index}", "ab:100") is True


def test_ab_test_strategy_should_execute_is_deterministic_for_same_user_and_key():
    strategy = ABTestStrategy(_with_user("alice"))
    first = strategy.should_execute("NewCheckoutFlow", "ab:50")
    for _ in range(20):
        assert strategy.should_execute("NewCheckoutFlow", "ab:50") == first


def test_ab_test_strategy_should_execute_different_keys_give_independent_assignments():
    strategy = ABTestStrategy(_with_user("alice"))
    results = [strategy.should_execute(f"toggle{index}", "ab:50") for index in range(50)]
    assert any(results), "Expected at least one true across different keys"
    assert any(not result for result in results), "Expected at least one false across different keys"


def test_ab_test_strategy_should_execute_different_users_can_get_different_assignments():
    results = [
        ABTestStrategy(_with_user(f"user-{index}")).should_execute("FeatureX", "ab:50")
        for index in range(100)
    ]
    assert any(results), "Expected at least one user in treatment group"
    assert any(not result for result in results), "Expected at least one user in control group"


def test_ab_test_strategy_should_execute_with_no_user_context_does_not_throw():
    strategy = ABTestStrategy(_no_context())
    for _ in range(20):
        strategy.should_execute("key", "ab:50")


def test_ab_test_strategy_should_execute_with_no_user_context_produces_both_outcomes_at_fifty_percent():
    random.seed(20240626)
    strategy = ABTestStrategy(_no_context())
    results = [strategy.should_execute("key", "ab:50") for _ in range(1000)]
    assert any(results), "Expected at least one true in 1000 probabilistic trials"
    assert any(not result for result in results), "Expected at least one false in 1000 probabilistic trials"


def test_ab_test_strategy_same_user_different_toggles_may_differ():
    strategy = ABTestStrategy(_with_user("alice"))
    strategy.should_execute("ToggleA", "ab:50")
    strategy.should_execute("ToggleB", "ab:50")


# ── ABTestStrategy salt support ──────────────────────────────────────────────


def test_ab_test_strategy_salt_is_deterministic_for_same_user_key_and_salt():
    strategy = ABTestStrategy(FakeContextAccessor("alice"))
    first = strategy.should_execute("MyToggle", "ab:50:round1")
    for _ in range(20):
        assert strategy.should_execute("MyToggle", "ab:50:round1") == first


def test_ab_test_strategy_different_salts_can_produce_different_assignments():
    user_ids = [f"user-{index}" for index in range(100)]
    results_round1 = [
        ABTestStrategy(FakeContextAccessor(user_id)).should_execute("Toggle", "ab:50:round1")
        for user_id in user_ids
    ]
    results_round2 = [
        ABTestStrategy(FakeContextAccessor(user_id)).should_execute("Toggle", "ab:50:round2")
        for user_id in user_ids
    ]
    assert results_round1 != results_round2, "Different salts should produce different assignments"


def test_ab_test_strategy_salt_always_false_at_zero_percent():
    strategy = ABTestStrategy(FakeContextAccessor("alice"))
    for index in range(50):
        assert strategy.should_execute(f"key{index}", "ab:0:anysalt") is False


def test_ab_test_strategy_salt_always_true_at_one_hundred_percent():
    strategy = ABTestStrategy(FakeContextAccessor("alice"))
    for index in range(50):
        assert strategy.should_execute(f"key{index}", "ab:100:anysalt") is True


def test_ab_test_strategy_no_salt_behaves_deterministically():
    strategy = ABTestStrategy(FakeContextAccessor("alice"))
    first = strategy.should_execute("NewCheckoutFlow", "ab:50")
    for _ in range(20):
        assert strategy.should_execute("NewCheckoutFlow", "ab:50") == first
