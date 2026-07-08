"""Port of ProviderTests.cs: env-var, composite, and HTTP value sourcing."""

from __future__ import annotations

import os
import time

import pytest

from ftrio.exceptions import ToggleDoesNotExistError, ToggleParsedOutOfRangeError
from ftrio.interfaces import ToggleBuffer, ToggleParser, ToggleValueProvider
from ftrio.parsers import (
    CompositeToggleParser,
    EnvironmentVariableToggleParser,
    StrategyToggleParser,
)
from ftrio.providers import HttpToggleParser
from ftrio.strategies import PercentageRolloutStrategy


class _SpyToggleBuffer(ToggleBuffer):
    """Records staged values for assertion (the .NET ``SpyToggleBuffer``)."""

    def __init__(self) -> None:
        self.staged: dict[str, str] = {}

    def stage(self, key: str, raw_value: str) -> None:
        self.staged[key] = raw_value


class _StubToggleParser(ToggleParser):
    """Resolves only known keys; raises missing-key otherwise (the .NET stub)."""

    def __init__(self, values: dict[str, bool]) -> None:
        self._values = values

    def get_toggle_status(self, toggle: str) -> bool:
        if toggle in self._values:
            return self._values[toggle]
        raise ToggleDoesNotExistError()

    def parse_bool_value_from_source(self, status: str) -> bool:
        raise NotImplementedError


@pytest.fixture
def clean_env_var():
    """Set and reliably unset env vars used within a single test."""
    keys_to_clear: list[str] = []

    def _set(name: str, value: str) -> None:
        keys_to_clear.append(name)
        os.environ[name] = value

    yield _set

    for name in keys_to_clear:
        os.environ.pop(name, None)


# ── EnvironmentVariableToggleParser (standalone mode) ────────────────────────


def test_env_var_standalone_returns_true_when_env_var_is_true(clean_env_var):
    clean_env_var("FTRIO__Toggles__EnvTrue", "true")
    assert EnvironmentVariableToggleParser().get_toggle_status("EnvTrue") is True


def test_env_var_standalone_returns_false_when_env_var_is_false(clean_env_var):
    clean_env_var("FTRIO__Toggles__EnvFalse", "false")
    assert EnvironmentVariableToggleParser().get_toggle_status("EnvFalse") is False


def test_env_var_standalone_raises_does_not_exist_when_key_missing():
    with pytest.raises(ToggleDoesNotExistError):
        EnvironmentVariableToggleParser().get_toggle_status("xyzzy_missing_key")


def test_env_var_standalone_raises_out_of_range_for_invalid_value(clean_env_var):
    clean_env_var("FTRIO__Toggles__EnvInvalid", "ASDF")
    with pytest.raises(ToggleParsedOutOfRangeError):
        EnvironmentVariableToggleParser().get_toggle_status("EnvInvalid")


def test_env_var_standalone_supports_custom_prefix(clean_env_var):
    clean_env_var("MYAPP_SendEmail", "true")
    assert EnvironmentVariableToggleParser("MYAPP_").get_toggle_status("SendEmail") is True


# ── EnvironmentVariableToggleParser (buffer mode) ────────────────────────────


def test_env_var_buffer_mode_stages_all_matching_env_vars(clean_env_var):
    clean_env_var("FTRIO__Toggles__BufA", "true")
    clean_env_var("FTRIO__Toggles__BufB", "false")
    spy = _SpyToggleBuffer()
    with EnvironmentVariableToggleParser(buffer=spy):
        # Assert case-insensitively: Windows uppercases env-var names at the OS
        # boundary, so the staged key is BUFA/BUFB there and BufA/BufB on Linux.
        staged_case_insensitive = {key.lower(): value for key, value in spy.staged.items()}
        assert staged_case_insensitive["bufa"] == "true"
        assert staged_case_insensitive["bufb"] == "false"


def test_env_var_buffer_mode_does_not_stage_unrelated_env_vars(clean_env_var):
    clean_env_var("FTRIO__Toggles__Relevant", "true")
    clean_env_var("OTHER_PREFIX_Key", "true")
    spy = _SpyToggleBuffer()
    with EnvironmentVariableToggleParser(buffer=spy):
        # Case-insensitive: the OS may uppercase the staged key on Windows.
        staged_case_insensitive = {key.lower(): value for key, value in spy.staged.items()}
        assert "relevant" in staged_case_insensitive
        # The unrelated OTHER_PREFIX_Key does not start with the prefix under any
        # casing, so it derives no matching key and must be absent.
        assert "other_prefix_key" not in staged_case_insensitive


# ── CompositeToggleParser ────────────────────────────────────────────────────


def test_composite_uses_first_parser_that_has_the_key():
    first = _StubToggleParser({"KeyA": True})
    second = _StubToggleParser({"KeyA": False})
    assert CompositeToggleParser(first, second).get_toggle_status("KeyA") is True


def test_composite_falls_through_to_next_parser_when_key_missing():
    first = _StubToggleParser({})
    second = _StubToggleParser({"KeyB": True})
    assert CompositeToggleParser(first, second).get_toggle_status("KeyB") is True


def test_composite_raises_does_not_exist_when_all_parsers_miss_key():
    composite = CompositeToggleParser(_StubToggleParser({}), _StubToggleParser({}))
    with pytest.raises(ToggleDoesNotExistError):
        composite.get_toggle_status("Missing")


def test_composite_raises_value_error_when_no_parsers_provided():
    with pytest.raises(ValueError):
        CompositeToggleParser()


# ── HttpToggleParser stages to buffer ────────────────────────────────────────


def _wait_for_stage(spy: _SpyToggleBuffer, key: str, timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while key not in spy.staged and time.monotonic() < deadline:
        time.sleep(0.02)


@pytest.fixture
def fake_http_server():
    """Spin up a localhost HTTP server returning canned JSON for the poller."""
    import http.server
    import threading

    servers: list[http.server.HTTPServer] = []

    def _start(body: str, status: int = 200) -> str:
        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 (http.server API)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))

            def log_message(self, *args):  # silence test server logging
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        host, port = server.server_address
        return f"http://{host}:{port}/toggles"

    yield _start

    for server in servers:
        server.shutdown()


def test_http_stages_true_value_to_buffer(fake_http_server):
    spy = _SpyToggleBuffer()
    url = fake_http_server('{"Toggles":{"SendWelcomeEmail":"true"}}')
    with HttpToggleParser(url, spy):
        _wait_for_stage(spy, "SendWelcomeEmail")
    assert spy.staged["SendWelcomeEmail"] == "true"


def test_http_stages_false_value_to_buffer(fake_http_server):
    spy = _SpyToggleBuffer()
    url = fake_http_server('{"Toggles":{"NewCheckout":"false"}}')
    with HttpToggleParser(url, spy):
        _wait_for_stage(spy, "NewCheckout")
    assert spy.staged["NewCheckout"] == "false"


def test_http_stages_raw_percentage_value_to_buffer(fake_http_server):
    spy = _SpyToggleBuffer()
    url = fake_http_server('{"Toggles":{"Rollout":"50%"}}')
    with HttpToggleParser(url, spy):
        _wait_for_stage(spy, "Rollout")
    assert spy.staged["Rollout"] == "50%"


def test_http_stages_multiple_toggles_to_buffer(fake_http_server):
    spy = _SpyToggleBuffer()
    url = fake_http_server('{"Toggles":{"A":"true","B":"false","C":"blue"}}')
    with HttpToggleParser(url, spy):
        _wait_for_stage(spy, "C")
    assert spy.staged["A"] == "true"
    assert spy.staged["B"] == "false"
    assert spy.staged["C"] == "blue"


def test_http_does_not_throw_when_endpoint_returns_error(fake_http_server):
    spy = _SpyToggleBuffer()
    url = fake_http_server("{}", status=500)
    with HttpToggleParser(url, spy):
        time.sleep(0.1)
    assert spy.staged == {}


def test_http_does_not_stage_when_response_has_no_toggles_property(fake_http_server):
    spy = _SpyToggleBuffer()
    url = fake_http_server('{"NotToggles":{"Key":"true"}}')
    with HttpToggleParser(url, spy):
        time.sleep(0.2)
    assert spy.staged == {}


# ── StrategyToggleParser value sourcing via a ToggleValueProvider ─────────────


class _DictValueProvider(ToggleValueProvider):
    """A ToggleValueProvider backed by an in-memory map (for the provider path)."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get_raw_value(self, key: str) -> str | None:
        return self._values.get(key)


def test_strategy_parser_sources_raw_values_from_value_provider():
    parser = StrategyToggleParser.with_provider(
        _DictValueProvider({"FromProvider": "true"})
    )
    assert parser.get_toggle_status("FromProvider") is True


def test_strategy_parser_provider_path_applies_strategies():
    parser = StrategyToggleParser.with_provider(
        _DictValueProvider({"Rollout": "100%"}), PercentageRolloutStrategy()
    )
    assert parser.get_toggle_status("Rollout") is True


def test_strategy_parser_provider_path_raises_does_not_exist_for_missing_key():
    parser = StrategyToggleParser.with_provider(_DictValueProvider({}))
    with pytest.raises(ToggleDoesNotExistError):
        parser.get_toggle_status("Missing")


def test_strategy_parser_provider_path_raises_out_of_range_for_unhandled_value():
    parser = StrategyToggleParser.with_provider(_DictValueProvider({"Weird": "ASDF"}))
    with pytest.raises(ToggleParsedOutOfRangeError):
        parser.get_toggle_status("Weird")


def test_strategy_parser_parse_bool_value_from_source_uses_strategy_chain():
    parser = StrategyToggleParser(PercentageRolloutStrategy())
    assert parser.parse_bool_value_from_source("true") is True
    assert parser.parse_bool_value_from_source("100%") is True
    with pytest.raises(ToggleParsedOutOfRangeError):
        parser.parse_bool_value_from_source("ASDF")
