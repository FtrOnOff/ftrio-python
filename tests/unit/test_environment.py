"""Port of EnvironmentTests.cs: env overlay resolution for parser and buffer."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ftrio.buffer import ToggleProviderBuffer
from ftrio.parsers import AppSettingsToggleParser

_ONE_HOUR_SECONDS = 3600


def _read_toggles(settings_path: Path) -> dict:
    document = json.loads(settings_path.read_text(encoding="utf-8"))
    return document.get("Toggles", {})


def _has_toggle(settings_path: Path, key: str) -> bool:
    if not settings_path.is_file():
        return False
    document = json.loads(settings_path.read_text(encoding="utf-8"))
    return key in document.get("Toggles", {})


@pytest.fixture(autouse=True)
def clear_environment_env_vars():
    """Ensure the .NET environment variables do not leak between tests."""
    saved = {
        name: os.environ.pop(name, None)
        for name in ("ASPNETCORE_ENVIRONMENT", "DOTNET_ENVIRONMENT", "FTRIO_ENVIRONMENT")
    }
    yield
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


@pytest.fixture
def base_settings(tmp_path) -> Path:
    return tmp_path / "appsettings.json"


# ── AppSettingsToggleParser ──────────────────────────────────────────────────


def test_parser_returns_base_value_when_no_environment_set(tmp_path, base_settings):
    base_settings.write_text('{"Toggles":{"MyToggle":"true"}}', encoding="utf-8")
    assert AppSettingsToggleParser(str(tmp_path)).get_toggle_status("MyToggle") is True


def test_parser_env_file_overrides_base_when_ftrio_environment_set(tmp_path, base_settings):
    base_settings.write_text(
        '{"FtrIO":{"Environment":"Staging"},"Toggles":{"MyToggle":"true"}}', encoding="utf-8"
    )
    (tmp_path / "appsettings.Staging.json").write_text(
        '{"Toggles":{"MyToggle":"false"}}', encoding="utf-8"
    )
    assert AppSettingsToggleParser(str(tmp_path)).get_toggle_status("MyToggle") is False


def test_parser_falls_back_to_base_when_key_missing_from_env_file(tmp_path, base_settings):
    base_settings.write_text(
        '{"FtrIO":{"Environment":"Staging"},"Toggles":{"Base":"true","Override":"false"}}',
        encoding="utf-8",
    )
    (tmp_path / "appsettings.Staging.json").write_text(
        '{"Toggles":{"Override":"true"}}', encoding="utf-8"
    )
    parser = AppSettingsToggleParser(str(tmp_path))
    assert parser.get_toggle_status("Base") is True
    assert parser.get_toggle_status("Override") is True


def test_parser_reads_environment_from_aspnetcore_env_var(tmp_path, base_settings):
    base_settings.write_text('{"Toggles":{"MyToggle":"true"}}', encoding="utf-8")
    (tmp_path / "appsettings.Production.json").write_text(
        '{"Toggles":{"MyToggle":"false"}}', encoding="utf-8"
    )
    os.environ["ASPNETCORE_ENVIRONMENT"] = "Production"
    assert AppSettingsToggleParser(str(tmp_path)).get_toggle_status("MyToggle") is False


def test_parser_reads_environment_from_dotnet_env_var(tmp_path, base_settings):
    base_settings.write_text('{"Toggles":{"MyToggle":"true"}}', encoding="utf-8")
    (tmp_path / "appsettings.Development.json").write_text(
        '{"Toggles":{"MyToggle":"false"}}', encoding="utf-8"
    )
    os.environ["DOTNET_ENVIRONMENT"] = "Development"
    assert AppSettingsToggleParser(str(tmp_path)).get_toggle_status("MyToggle") is False


def test_parser_ftrio_environment_takes_precedence_over_env_var(tmp_path, base_settings):
    base_settings.write_text(
        '{"FtrIO":{"Environment":"Staging"},"Toggles":{"MyToggle":"true"}}', encoding="utf-8"
    )
    (tmp_path / "appsettings.Staging.json").write_text(
        '{"Toggles":{"MyToggle":"false"}}', encoding="utf-8"
    )
    (tmp_path / "appsettings.Production.json").write_text(
        '{"Toggles":{"MyToggle":"true"}}', encoding="utf-8"
    )
    os.environ["ASPNETCORE_ENVIRONMENT"] = "Production"
    assert AppSettingsToggleParser(str(tmp_path)).get_toggle_status("MyToggle") is False


# ── ToggleProviderBuffer ─────────────────────────────────────────────────────


def test_buffer_flushes_to_base_file_when_no_environment_set(tmp_path, base_settings):
    base_settings.write_text('{"Toggles":{}}', encoding="utf-8")
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("MyToggle", "true")
        buffer.flush_now()
    assert base_settings.is_file()
    assert _read_toggles(base_settings)["MyToggle"] == "true"


def test_buffer_flushes_to_env_file_when_ftrio_environment_set(tmp_path, base_settings):
    base_settings.write_text('{"FtrIO":{"Environment":"Staging"},"Toggles":{}}', encoding="utf-8")
    staging_path = tmp_path / "appsettings.Staging.json"
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("MyToggle", "true")
        buffer.flush_now()
    assert staging_path.is_file()
    assert not _has_toggle(base_settings, "MyToggle")
    assert _read_toggles(staging_path)["MyToggle"] == "true"


def test_buffer_flushes_to_base_file_even_when_aspnetcore_env_var_set(tmp_path, base_settings):
    base_settings.write_text('{"Toggles":{}}', encoding="utf-8")
    os.environ["ASPNETCORE_ENVIRONMENT"] = "Production"
    production_path = tmp_path / "appsettings.Production.json"
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("MyToggle", "true")
        buffer.flush_now()
    assert not production_path.is_file()
    assert _read_toggles(base_settings)["MyToggle"] == "true"


def test_buffer_env_file_preserves_existing_keys(tmp_path, base_settings):
    base_settings.write_text('{"FtrIO":{"Environment":"Staging"}}', encoding="utf-8")
    staging_path = tmp_path / "appsettings.Staging.json"
    staging_path.write_text('{"Toggles":{"Existing":"false"}}', encoding="utf-8")
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("New", "true")
        buffer.flush_now()
    toggles = _read_toggles(staging_path)
    assert "Existing" in toggles
    assert toggles["New"] == "true"
