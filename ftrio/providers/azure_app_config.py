"""Azure App Configuration toggle provider (optional ``ftrio[azure]`` extra)."""

from __future__ import annotations

import logging
from types import TracebackType

from .._periodic import RepeatingTimer
from ..interfaces import ToggleBuffer

_DEFAULT_KEY_PREFIX = "FtrIO:Toggles:"
_DEFAULT_POLL_INTERVAL_SECONDS = 30.0
_logger = logging.getLogger(__name__)


def _require_azure_sdk():
    """Import the Azure SDK lazily, raising an actionable error if it is absent.

    The SDK is an optional dependency: importing only when the provider is used
    means the rest of FtrIO stays dependency-free and the error surfaces with
    install guidance exactly when someone actually reaches for this provider.
    """
    try:
        from azure.data.appconfiguration import (  # type: ignore[import-not-found]
            ConfigurationClient,
            SettingSelector,
        )
    except ImportError as import_error:  # pragma: no cover - exercised without the SDK
        raise ImportError(
            "AzureAppConfigToggleParser requires the 'azure-appconfiguration' package. "
            "Install it with: pip install 'ftrio[azure]'"
        ) from import_error
    return ConfigurationClient, SettingSelector


class AzureAppConfigToggleParser:
    """Polls Azure App Configuration for toggle values and stages them to a buffer.

    appsettings.json is the source of truth for reads, so a transient Azure
    failure leaves the last flushed state in place (fail-safe). Keys are read
    under ``{key_prefix}{toggle_name}`` (default prefix ``FtrIO:Toggles:``); values
    use the same raw formats as appsettings.json and are decided by the strategy
    chain at read time, not at fetch time.
    """

    def __init__(
        self,
        connection_string: str,
        buffer: ToggleBuffer,
        key_prefix: str = _DEFAULT_KEY_PREFIX,
        label: str | None = None,
        poll_interval_seconds: float | None = None,
    ) -> None:
        configuration_client_cls, _ = _require_azure_sdk()
        self._client = configuration_client_cls.from_connection_string(connection_string)
        self._buffer = buffer
        self._key_prefix = key_prefix
        self._label = label
        interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else _DEFAULT_POLL_INTERVAL_SECONDS
        )
        self._timer = RepeatingTimer(interval, self._poll, fire_immediately=True)

    def _poll(self) -> None:
        """Fetch matching settings and stage each toggle; swallow all errors."""
        try:
            _, setting_selector_cls = _require_azure_sdk()
            selector = setting_selector_cls(
                key_filter=self._key_prefix + "*",
                label_filter=self._label if self._label is not None else "\0",
            )
            for setting in self._client.list_configuration_settings(selector):
                toggle_name = setting.key[len(self._key_prefix):]
                if toggle_name:
                    self._buffer.stage(toggle_name, setting.value or "")
        except Exception:
            # Transient Azure failure: last flushed state in appsettings.json
            # persists. Logged at debug so the fail-safe path stays observable.
            _logger.debug("Azure App Config poll failed; serving last flushed state.", exc_info=True)

    def close(self) -> None:
        """Stop polling (the Pythonic stand-in for Dispose)."""
        self._timer.stop()

    def __enter__(self) -> AzureAppConfigToggleParser:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
