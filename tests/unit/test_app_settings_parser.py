"""Port of FtrIoTests.cs (+ core AppSettingsToggleParser invariants).

Covers: missing file means everything on, missing key raises, unparseable value
raises, boolean parsing, and the FeatureToggle.get_toggle_state mapping that the
.NET FtrIoTests fixture exercises through a parser test double.
"""

from __future__ import annotations

import pytest

from ftrio.enums import ToggleStatus
from ftrio.exceptions import ToggleDoesNotExistError, ToggleParsedOutOfRangeError
from ftrio.feature_toggle import FeatureToggle
from ftrio.interfaces import ToggleParser
from ftrio.parsers import AppSettingsToggleParser


class _ToggleParserTestDouble(ToggleParser):
    """Resolves only the key ``"positive"`` as on (the .NET test double)."""

    def get_toggle_status(self, toggle: str) -> bool:
        return toggle == "positive"

    def parse_bool_value_from_source(self, status: str) -> bool:
        raise NotImplementedError


class _TestDataType:
    """A small reference type used to prove non-bool return defaults to None."""

    def __init__(self) -> None:
        self.happiness_is = "Happy"


def _always_return_true() -> bool:
    return True


def _always_return_fire() -> str:
    return "Fire"


def _always_return_new_test_data_type() -> _TestDataType:
    return _TestDataType()


# ── AppSettingsToggleParser invariants ───────────────────────────────────────


def test_missing_config_file_treats_every_toggle_as_on(tmp_path):
    parser = AppSettingsToggleParser(str(tmp_path))
    assert parser.toggle_config_tag_exists() is False
    assert parser.get_toggle_status("SomeMadeUpToggleThatHasNeverExisted") is True


def test_present_file_with_missing_key_raises_does_not_exist(test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    with pytest.raises(ToggleDoesNotExistError):
        parser.get_toggle_status("wewewewewewewewe")


def test_present_key_with_unparseable_value_raises_out_of_range(test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    with pytest.raises(ToggleParsedOutOfRangeError):
        parser.get_toggle_status("asdf")


def test_toggled_on_key_returns_true(test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.get_toggle_status("ButtonToggle") is True


def test_toggled_off_key_returns_false(test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.get_toggle_status("NotFinished") is False


@pytest.mark.parametrize("status", ["1", "true", "True", "TRUE"])
def test_parse_bool_value_from_source_truthy(status, test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.parse_bool_value_from_source(status) is True


@pytest.mark.parametrize("status", ["0", "false", "False", "FALSE"])
def test_parse_bool_value_from_source_falsy(status, test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.parse_bool_value_from_source(status) is False


def test_parse_bool_value_from_source_raises_for_unparseable(test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    with pytest.raises(ToggleParsedOutOfRangeError):
        parser.parse_bool_value_from_source("ASDF")


# ── FeatureToggle.get_toggle_state mapping ───────────────────────────────────


def test_successful_parse_returns_toggle_status_active():
    feature_toggle = FeatureToggle()
    assert feature_toggle.get_toggle_state(_ToggleParserTestDouble(), "positive") == ToggleStatus.ACTIVE


def test_unsuccessful_parse_returns_toggle_status_inactive():
    feature_toggle = FeatureToggle()
    assert (
        feature_toggle.get_toggle_state(_ToggleParserTestDouble(), "anythingElse")
        == ToggleStatus.INACTIVE
    )


def test_execute_func_when_toggle_active_returns_value():
    feature_toggle = FeatureToggle()
    result = feature_toggle.execute_method_if_toggle_on(
        _always_return_true, _ToggleParserTestDouble(), "positive"
    )
    assert result is True


def test_execute_func_when_toggle_inactive_returns_none():
    feature_toggle = FeatureToggle()
    result = feature_toggle.execute_method_if_toggle_on(
        _always_return_true, _ToggleParserTestDouble(), "anythingElse"
    )
    assert result is None


def test_execute_string_func_when_toggle_active_returns_value():
    feature_toggle = FeatureToggle()
    result = feature_toggle.execute_method_if_toggle_on(
        _always_return_fire, _ToggleParserTestDouble(), "positive"
    )
    assert result == "Fire"


def test_execute_reference_type_func_when_toggle_active_returns_value():
    feature_toggle = FeatureToggle()
    result = feature_toggle.execute_method_if_toggle_on(
        _always_return_new_test_data_type, _ToggleParserTestDouble(), "positive"
    )
    assert result.happiness_is == _TestDataType().happiness_is


def test_execute_reference_type_func_when_toggle_inactive_returns_none():
    feature_toggle = FeatureToggle()
    result = feature_toggle.execute_method_if_toggle_on(
        _always_return_new_test_data_type, _ToggleParserTestDouble(), "anythingElse"
    )
    assert result is None
