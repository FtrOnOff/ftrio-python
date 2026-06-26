"""Port of FeatureToggleIntegrationTests.cs: @toggle gating and explicit API (sync).

The decorated fixtures use snake_case names, the idiomatic Python convention. The
toggle key derives from the function name, so the matching appsettings.json keys
are snake_case too: the "key == method name" contract holds in any language, and
the casing simply follows the language. The PascalCase in the .NET original was a
C# artifact, not part of the wire contract (which is the JSON shape, not the key
spelling).
"""

from __future__ import annotations

import pytest

from ftrio import toggle
from ftrio.decorators import get_toggle_key_marker
from ftrio.enums import ToggleStatus
from ftrio.exceptions import (
    ToggleAttributeMissingError,
    ToggleDoesNotExistError,
    ToggleParsedOutOfRangeError,
)
from ftrio.feature_toggle import FeatureToggle
from ftrio.parsers import AppSettingsToggleParser
from ftrio.provider import ToggleParserProvider
from tests.conftest import TEST_APP_SETTINGS_DIR


@pytest.fixture(autouse=True)
def configure_ambient_provider():
    """Point the ambient provider at the test appsettings for decorated calls."""
    ToggleParserProvider.configure(AppSettingsToggleParser(TEST_APP_SETTINGS_DIR))
    yield


def _test_parser() -> AppSettingsToggleParser:
    return AppSettingsToggleParser(TEST_APP_SETTINGS_DIR)


# ── @toggle-decorated functions (the AspectInjector stand-in) ────────────────


@toggle
def fake_method_that_returns_true() -> bool:
    return True


def fake_method_with_no_toggle_attribute() -> bool:
    return True


@toggle
def fake_auto_gated_method_toggled_on() -> bool:
    return True


@toggle
def fake_auto_gated_method_toggled_off() -> bool:
    return True


_void_method_ran = False


@toggle
def fake_auto_gated_void_method_toggled_off() -> None:
    global _void_method_ran
    _void_method_ran = True


# ── get_toggle_state mapping ─────────────────────────────────────────────────


def test_toggle_status_active_when_item_toggled_on():
    feature_toggle = FeatureToggle()
    assert feature_toggle.get_toggle_state(_test_parser(), "ButtonToggle") == ToggleStatus.ACTIVE


def test_toggle_status_inactive_when_item_toggled_off():
    feature_toggle = FeatureToggle()
    assert feature_toggle.get_toggle_state(_test_parser(), "NotFinished") == ToggleStatus.INACTIVE


def test_get_toggle_state_raises_out_of_range_for_unparseable_value():
    feature_toggle = FeatureToggle()
    with pytest.raises(ToggleParsedOutOfRangeError):
        feature_toggle.get_toggle_state(_test_parser(), "asdf")


def test_get_toggle_state_raises_does_not_exist_for_missing_key():
    feature_toggle = FeatureToggle()
    with pytest.raises(ToggleDoesNotExistError):
        feature_toggle.get_toggle_state(_test_parser(), "wewewewewewewewe")


# ── execute_method_if_toggle_on ──────────────────────────────────────────────


def test_execute_returns_true_when_key_toggled_on():
    feature_toggle = FeatureToggle()
    result = feature_toggle.execute_method_if_toggle_on(
        fake_method_that_returns_true, _test_parser(), "FakeTrue"
    )
    assert result is True


def test_execute_returns_none_when_key_toggled_off():
    feature_toggle = FeatureToggle()
    result = feature_toggle.execute_method_if_toggle_on(
        fake_method_that_returns_true, _test_parser(), "FakeFalse"
    )
    assert result is None


def test_execute_resolves_key_from_toggle_marker_when_no_key_given():
    # fake_method_that_returns_true carries the @toggle marker (key == its own
    # name), which maps to "true" in the test config.
    feature_toggle = FeatureToggle()
    result = feature_toggle.execute_method_if_toggle_on(fake_method_that_returns_true, _test_parser())
    assert result is True


def test_execute_raises_when_no_marker_and_no_key():
    feature_toggle = FeatureToggle()
    with pytest.raises(ToggleAttributeMissingError):
        feature_toggle.execute_method_if_toggle_on(fake_method_with_no_toggle_attribute)


# ── Direct calls to @toggle-decorated functions ──────────────────────────────


def test_direct_call_to_decorated_function_runs_when_toggled_on():
    # No FeatureToggle involved: the decorator itself gates the call.
    assert fake_auto_gated_method_toggled_on() is True


def test_direct_call_to_decorated_function_returns_none_when_toggled_off():
    # The body would return True, but the toggle is off, so the decorator returns
    # None without invoking the body (the type default, as in .NET).
    assert fake_auto_gated_method_toggled_off() is None


def test_direct_call_to_decorated_void_function_is_skipped_when_toggled_off():
    global _void_method_ran
    _void_method_ran = False
    fake_auto_gated_void_method_toggled_off()
    assert _void_method_ran is False


# ── Decorator marker is detectable ───────────────────────────────────────────


def test_decorator_tags_wrapper_with_resolved_key():
    assert get_toggle_key_marker(fake_method_that_returns_true) == "fake_method_that_returns_true"
    assert get_toggle_key_marker(fake_method_with_no_toggle_attribute) is None


def test_explicit_key_decorator_uses_given_key():
    @toggle("CustomConfiguredKey")
    def some_function() -> bool:
        return True

    assert get_toggle_key_marker(some_function) == "CustomConfiguredKey"
