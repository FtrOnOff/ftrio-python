"""Built-in toggle decision strategies.

Each strategy recognises one grammar of raw toggle value and decides on/off for
it. ``BooleanStrategy`` is the universal fallback; the rest add richer targeting.
"""

from __future__ import annotations

from .ab_test_strategy import ABTestStrategy, compute_bucket
from .attribute_rule_strategy import AttributeRuleStrategy
from .blue_green_strategy import BlueGreenStrategy
from .boolean_strategy import BooleanStrategy
from .percentage_rollout_strategy import PercentageRolloutStrategy
from .user_targeting_strategy import UserTargetingStrategy

__all__ = [
    "ABTestStrategy",
    "AttributeRuleStrategy",
    "BlueGreenStrategy",
    "BooleanStrategy",
    "PercentageRolloutStrategy",
    "UserTargetingStrategy",
    "compute_bucket",
]
