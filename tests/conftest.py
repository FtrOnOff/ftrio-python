"""Shared pytest fixtures and helpers for the FtrIO test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from ftrio.context import FtrIOContextAccessor
from ftrio.provider import ToggleParserProvider

# Directory holding the test appsettings.json (mirrors the .NET FtrIOTests config).
TEST_APP_SETTINGS_DIR = str(Path(__file__).resolve().parent)


class FakeContextAccessor:
    """Configurable context accessor test double (the .NET ``FakeAccessor``).

    Satisfies ``FtrIOContextAccessor`` structurally; returns the configured user
    id and attribute values without any request dependency.
    """

    def __init__(
        self, user_id: str | None = None, attributes: dict[str, str] | None = None
    ) -> None:
        self._user_id = user_id
        self._attributes = attributes or {}

    def get_user_id(self) -> str | None:
        return self._user_id

    def get_attribute(self, name: str) -> str | None:
        return self._attributes.get(name)


# Confirm the double genuinely satisfies the protocol (structural check).
assert isinstance(FakeContextAccessor(), FtrIOContextAccessor)


@pytest.fixture
def test_app_settings_dir() -> str:
    """Return the directory containing the test appsettings.json."""
    return TEST_APP_SETTINGS_DIR


@pytest.fixture(autouse=True)
def reset_ambient_provider():
    """Reset the process-global provider between tests so they stay isolated."""
    ToggleParserProvider.reset()
    yield
    ToggleParserProvider.reset()
