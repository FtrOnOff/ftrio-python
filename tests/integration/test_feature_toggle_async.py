"""Port of FeatureToggleAsyncIntegrationTests.cs: @toggle_async and async API."""

from __future__ import annotations

import asyncio

import pytest

from ftrio import toggle_async
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
    ToggleParserProvider.configure(AppSettingsToggleParser(TEST_APP_SETTINGS_DIR))
    yield


def _test_parser() -> AppSettingsToggleParser:
    return AppSettingsToggleParser(TEST_APP_SETTINGS_DIR)


async def _async_no_toggle_marker() -> bool:
    await asyncio.sleep(0)
    return True


@toggle_async
async def fake_async_method_toggled_on() -> bool:
    await asyncio.sleep(0)
    return True


@toggle_async
async def fake_async_method_toggled_off() -> bool:
    await asyncio.sleep(0)
    return True


@toggle_async
async def fake_async_void_method_toggled_off() -> None:
    await asyncio.sleep(0)


@toggle_async
async def fake_async_method_with_missing_key() -> bool:
    await asyncio.sleep(0)
    return True


@toggle_async
async def fake_async_method_with_unparseable_value() -> bool:
    await asyncio.sleep(0)
    return True


# ── execute_method_if_toggle_on_async (no result) ────────────────────────────


@pytest.mark.asyncio
async def test_execute_async_runs_method_when_toggle_on():
    ran = False

    async def body() -> None:
        nonlocal ran
        await asyncio.sleep(0)
        ran = True

    await FeatureToggle().execute_method_if_toggle_on_async(body, _test_parser(), "FakeTrue")
    assert ran is True


@pytest.mark.asyncio
async def test_execute_async_skips_method_when_toggle_off():
    ran = False

    async def body() -> None:
        nonlocal ran
        await asyncio.sleep(0)
        ran = True

    await FeatureToggle().execute_method_if_toggle_on_async(body, _test_parser(), "FakeFalse")
    assert ran is False


@pytest.mark.asyncio
async def test_execute_async_returns_awaitable_resolving_to_none_when_off():
    async def body() -> None:
        await asyncio.sleep(0)

    result = await FeatureToggle().execute_method_if_toggle_on_async(
        body, _test_parser(), "FakeFalse"
    )
    assert result is None


@pytest.mark.asyncio
async def test_execute_async_raises_missing_attribute_when_no_marker_and_no_key():
    with pytest.raises(ToggleAttributeMissingError):
        await FeatureToggle().execute_method_if_toggle_on_async(_async_no_toggle_marker)


# ── execute_method_if_toggle_on_async (with result) ──────────────────────────


@pytest.mark.asyncio
async def test_execute_async_with_result_returns_value_when_on():
    async def body() -> bool:
        await asyncio.sleep(0)
        return True

    result = await FeatureToggle().execute_method_if_toggle_on_async(
        body, _test_parser(), "FakeTrue"
    )
    assert result is True


@pytest.mark.asyncio
async def test_execute_async_with_result_returns_none_when_off():
    async def body() -> bool:
        await asyncio.sleep(0)
        return True

    result = await FeatureToggle().execute_method_if_toggle_on_async(
        body, _test_parser(), "FakeFalse"
    )
    assert result is None


# ── @toggle_async decorator (direct call) ────────────────────────────────────


@pytest.mark.asyncio
async def test_toggle_async_runs_when_toggled_on():
    assert await fake_async_method_toggled_on() is True


@pytest.mark.asyncio
async def test_toggle_async_returns_awaitable_none_when_toggled_off():
    # Body returns True, but the toggle is off: awaiting must yield None, not raise.
    assert await fake_async_method_toggled_off() is None


@pytest.mark.asyncio
async def test_toggle_async_void_returns_awaitable_none_when_off():
    # Awaiting an off void-coroutine must not raise.
    assert await fake_async_void_method_toggled_off() is None


# ── Exception parity with sync paths ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_execute_async_raises_does_not_exist_for_missing_key():
    async def body() -> None:
        await asyncio.sleep(0)

    with pytest.raises(ToggleDoesNotExistError):
        await FeatureToggle().execute_method_if_toggle_on_async(
            body, _test_parser(), "KeyThatDoesNotExist"
        )


@pytest.mark.asyncio
async def test_execute_async_raises_out_of_range_for_unparseable_value():
    async def body() -> None:
        await asyncio.sleep(0)

    with pytest.raises(ToggleParsedOutOfRangeError):
        await FeatureToggle().execute_method_if_toggle_on_async(body, _test_parser(), "asdf")


def test_toggle_async_decorator_raises_does_not_exist_for_missing_key():
    # The gating check runs synchronously before the coroutine starts, so the
    # exception surfaces at call time rather than as a faulted awaitable. This is
    # a plain (non-async) test for exactly that reason.
    with pytest.raises(ToggleDoesNotExistError):
        fake_async_method_with_missing_key()


def test_toggle_async_decorator_raises_out_of_range_for_unparseable_value():
    with pytest.raises(ToggleParsedOutOfRangeError):
        fake_async_method_with_unparseable_value()
