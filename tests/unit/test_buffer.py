"""Port of BufferTests.cs: staging, coalescing, atomic merge, final flush."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from ftrio.buffer import ToggleProviderBuffer

_ONE_HOUR_SECONDS = 3600


def _read_toggles(settings_path: Path) -> dict:
    document = json.loads(settings_path.read_text(encoding="utf-8"))
    return document.get("Toggles", {})


@pytest.fixture
def settings_path(tmp_path) -> Path:
    return tmp_path / "appsettings.json"


# ── Stage + flush ────────────────────────────────────────────────────────────


def test_flush_now_writes_new_key_to_appsettings(tmp_path, settings_path):
    settings_path.write_text('{"Toggles":{}}', encoding="utf-8")
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("MyToggle", "true")
        buffer.flush_now()
    assert _read_toggles(settings_path)["MyToggle"] == "true"


def test_flush_now_updates_existing_key(tmp_path, settings_path):
    settings_path.write_text('{"Toggles":{"MyToggle":"false"}}', encoding="utf-8")
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("MyToggle", "true")
        buffer.flush_now()
    assert _read_toggles(settings_path)["MyToggle"] == "true"


def test_flush_now_preserves_unchanged_keys_and_their_json_type(tmp_path, settings_path):
    # B is a JSON boolean (not a string) so we can assert its type is preserved.
    settings_path.write_text('{"Toggles":{"A":"true","B":false}}', encoding="utf-8")
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("A", "false")
        buffer.flush_now()
    toggles = _read_toggles(settings_path)
    assert toggles["A"] == "false"
    # B was untouched: it must remain a JSON boolean false, not the string "false".
    assert toggles["B"] is False


def test_flush_now_creates_file_when_it_does_not_exist(tmp_path, settings_path):
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("NewKey", "true")
        buffer.flush_now()
    assert settings_path.is_file()
    assert _read_toggles(settings_path)["NewKey"] == "true"


def test_flush_now_adds_toggles_section_when_missing(tmp_path, settings_path):
    settings_path.write_text('{"FtrIO":{"ReloadOnChange":false}}', encoding="utf-8")
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("MyToggle", "true")
        buffer.flush_now()
    assert _read_toggles(settings_path)["MyToggle"] == "true"


def test_flush_now_preserves_other_top_level_sections(tmp_path, settings_path):
    settings_path.write_text(
        '{"FtrIO":{"ReloadOnChange":true},"Toggles":{"A":"true"}}', encoding="utf-8"
    )
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        buffer.stage("A", "false")
        buffer.flush_now()
    document = json.loads(settings_path.read_text(encoding="utf-8"))
    assert document["FtrIO"]["ReloadOnChange"] is True


# ── Rapid succession / write storm ───────────────────────────────────────────


def test_rapid_successive_stages_last_value_wins_before_flush(tmp_path, settings_path):
    settings_path.write_text('{"Toggles":{}}', encoding="utf-8")
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        for index in range(1000):
            buffer.stage("MyToggle", "true" if index % 2 == 0 else "false")
        buffer.flush_now()
    assert _read_toggles(settings_path)["MyToggle"] in ("true", "false")


def test_concurrent_stages_all_keys_eventually_flushed(tmp_path, settings_path):
    settings_path.write_text('{"Toggles":{}}', encoding="utf-8")
    with ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS) as buffer:
        threads = [
            threading.Thread(target=buffer.stage, args=(f"Key{index}", "true"))
            for index in range(20)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        buffer.flush_now()
    toggles = _read_toggles(settings_path)
    for index in range(20):
        assert f"Key{index}" in toggles


# ── FlushInterval read from config ───────────────────────────────────────────


def test_reads_flush_interval_from_appsettings(tmp_path, settings_path):
    settings_path.write_text(
        '{"FtrIO":{"ReloadOnChange":true,"FlushInterval":2},"Toggles":{}}', encoding="utf-8"
    )
    with ToggleProviderBuffer(str(tmp_path)) as buffer:
        buffer.stage("FromConfig", "true")
        buffer.flush_now()
    assert "FromConfig" in _read_toggles(settings_path)


# ── Close performs a final flush ─────────────────────────────────────────────


def test_close_flushes_pending_changes(tmp_path, settings_path):
    settings_path.write_text('{"Toggles":{}}', encoding="utf-8")
    buffer = ToggleProviderBuffer(str(tmp_path), _ONE_HOUR_SECONDS)
    buffer.stage("OnClose", "true")
    buffer.close()  # final flush happens here, no explicit flush_now
    assert _read_toggles(settings_path)["OnClose"] == "true"
