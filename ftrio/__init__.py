"""FtrIO: feature toggles for Python, ported from the .NET FtrIO library.

Decorate a method with ``@toggle`` to gate it by its own name, add a matching key
to the ``Toggles`` section of ``appsettings.json``, and the method runs only when
the toggle is on. Richer decisions (percentage rollouts, A/B buckets, deployment
slots, user/attribute targeting, per-user overrides) are layered in through the
strategy chain via ``ToggleParserBuilder``.
"""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _read_installed_version

from .buffer import ToggleProviderBuffer
from .builder import ToggleParserBuilder
from .context import FtrIOContextAccessor
from .decorators import toggle, toggle_async
from .enums import ToggleStatus
from .exceptions import (
    ToggleAttributeMissingError,
    ToggleDoesNotExistError,
    ToggleParsedOutOfRangeError,
)
from .feature_toggle import FeatureToggle
from .interfaces import (
    ToggleBuffer,
    ToggleDecisionStrategy,
    ToggleParser,
    ToggleValueProvider,
)
from .override_resolver import OverrideResolver
from .parsers import (
    AppSettingsToggleParser,
    CompositeToggleParser,
    EnvironmentVariableToggleParser,
    StrategyToggleParser,
)
from .provider import ToggleParserProvider
from .strategies import (
    ABTestStrategy,
    AttributeRuleStrategy,
    BlueGreenStrategy,
    BooleanStrategy,
    PercentageRolloutStrategy,
    UserTargetingStrategy,
    compute_bucket,
)

__all__ = [
    # Decorators and explicit API
    "toggle",
    "toggle_async",
    "FeatureToggle",
    # Provider singleton + builder
    "ToggleParserProvider",
    "ToggleParserBuilder",
    # Enums
    "ToggleStatus",
    # Context protocol + ABCs
    "FtrIOContextAccessor",
    "ToggleParser",
    "ToggleDecisionStrategy",
    "ToggleValueProvider",
    "ToggleBuffer",
    # Parsers
    "AppSettingsToggleParser",
    "StrategyToggleParser",
    "EnvironmentVariableToggleParser",
    "CompositeToggleParser",
    # Override resolver + buffer
    "OverrideResolver",
    "ToggleProviderBuffer",
    # Strategies
    "BooleanStrategy",
    "PercentageRolloutStrategy",
    "AttributeRuleStrategy",
    "UserTargetingStrategy",
    "ABTestStrategy",
    "BlueGreenStrategy",
    "compute_bucket",
    # Exceptions
    "ToggleDoesNotExistError",
    "ToggleParsedOutOfRangeError",
    "ToggleAttributeMissingError",
]

# Single source of truth for the version is pyproject.toml; expose it here by
# reading the installed package metadata so there is only one place to bump.
try:
    __version__ = _read_installed_version("ftrio")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0.0.0+unknown"

# Library code attaches a NullHandler so it emits nothing by default, leaving the
# host application in full control of verbosity: it can redirect FtrIO logs to a
# file and raise or lower the level per component (e.g. logging.getLogger("ftrio.buffer"))
# without any code change here. This is the standard library-logging contract.
logging.getLogger(__name__).addHandler(logging.NullHandler())
