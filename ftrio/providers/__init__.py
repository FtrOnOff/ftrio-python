"""Optional value providers that feed a ``ToggleBuffer`` from external sources.

``HttpToggleParser`` uses only the standard library. ``AzureAppConfigToggleParser``
needs the ``ftrio[azure]`` extra and imports its SDK lazily, so importing this
package never requires the Azure dependency to be installed.
"""

from __future__ import annotations

from .azure_app_config import AzureAppConfigToggleParser
from .http import HttpToggleParser

__all__ = [
    "AzureAppConfigToggleParser",
    "HttpToggleParser",
]
