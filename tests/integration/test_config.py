"""Port of ConfigParserTests.cs (+ env overlay and reload-on-change behaviour)."""

from __future__ import annotations

import pytest

from ftrio.exceptions import ToggleDoesNotExistError, ToggleParsedOutOfRangeError
from ftrio.parsers import AppSettingsToggleParser

# ── Core ConfigParserTests behaviours ────────────────────────────────────────


def test_true_is_returned_for_toggled_on_item(test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.get_toggle_status("ButtonToggle") is True


def test_false_is_returned_for_toggled_off_item(test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    assert parser.get_toggle_status("NotFinished") is False


def test_out_of_range_for_unparseable_item(test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    with pytest.raises(ToggleParsedOutOfRangeError):
        parser.get_toggle_status("asdf")


def test_does_not_exist_for_unknown_item(test_app_settings_dir):
    parser = AppSettingsToggleParser(test_app_settings_dir)
    with pytest.raises(ToggleDoesNotExistError):
        parser.get_toggle_status("wewewewewewewewe")


def test_everything_treated_as_on_when_file_missing(tmp_path):
    parser = AppSettingsToggleParser(str(tmp_path))
    assert parser.toggle_config_tag_exists() is False
    assert parser.get_toggle_status("SomeMadeUpToggleThatHasNeverExisted") is True


# ── Environment overlay wins ─────────────────────────────────────────────────


def test_environment_overlay_value_wins_over_base(tmp_path):
    (tmp_path / "appsettings.json").write_text(
        '{"FtrIO":{"Environment":"Staging"},"Toggles":{"Feature":"false"}}', encoding="utf-8"
    )
    (tmp_path / "appsettings.Staging.json").write_text(
        '{"Toggles":{"Feature":"true"}}', encoding="utf-8"
    )
    parser = AppSettingsToggleParser(str(tmp_path))
    assert parser.get_toggle_status("Feature") is True


# ── Reload-on-change picks up live edits ─────────────────────────────────────


def test_reload_on_change_picks_up_live_edit(tmp_path):
    settings_path = tmp_path / "appsettings.json"
    settings_path.write_text(
        '{"FtrIO":{"ReloadOnChange":true},"Toggles":{"Live":"false"}}', encoding="utf-8"
    )
    parser = AppSettingsToggleParser(str(tmp_path))
    assert parser.get_toggle_status("Live") is False

    # Edit the file in place; with reload-on-change the next lookup must see it.
    settings_path.write_text(
        '{"FtrIO":{"ReloadOnChange":true},"Toggles":{"Live":"true"}}', encoding="utf-8"
    )
    assert parser.get_toggle_status("Live") is True


def test_reload_off_caches_and_ignores_live_edit(tmp_path):
    settings_path = tmp_path / "appsettings.json"
    settings_path.write_text(
        '{"FtrIO":{"ReloadOnChange":false},"Toggles":{"Cached":"false"}}', encoding="utf-8"
    )
    parser = AppSettingsToggleParser(str(tmp_path))
    assert parser.get_toggle_status("Cached") is False

    settings_path.write_text(
        '{"FtrIO":{"ReloadOnChange":false},"Toggles":{"Cached":"true"}}', encoding="utf-8"
    )
    # Reload is off, so the cached snapshot stands; the edit is not observed.
    assert parser.get_toggle_status("Cached") is False
