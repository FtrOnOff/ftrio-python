"""Attribute-based targeting rules (``"attribute:plan equals premium"``)."""

from __future__ import annotations

from ..context import FtrIOContextAccessor
from ..interfaces import ToggleDecisionStrategy

# Operator order matters: ``can_handle`` and the parser scan this list looking for
# the first " operator " marker, so the wording is matched exactly as the .NET
# source declares it. All matching is case-insensitive at comparison time.
_OPERATORS: tuple[str, ...] = (
    "equals",
    "notEquals",
    "startsWith",
    "endsWith",
    "contains",
    "in",
    "notIn",
)


class AttributeRuleStrategy(ToggleDecisionStrategy):
    """Gates a toggle on a comparison against a named context attribute.

    Rules read ``attribute:<name> <operator> <expected>``. The strategy resolves
    the attribute from the supplied context accessor; a missing attribute means
    "do not match" rather than an error, so toggles fail closed for contexts that
    lack the attribute.
    """

    def __init__(self, context_accessor: FtrIOContextAccessor) -> None:
        self._context_accessor = context_accessor

    def can_handle(self, raw_value: str) -> bool:
        """Recognise an ``attribute:`` prefix containing a padded operator marker."""
        if not raw_value.lower().startswith("attribute:"):
            return False
        lowered = raw_value.lower()
        return any(
            f" {candidate_operator.lower()} " in lowered
            for candidate_operator in _OPERATORS
        )

    def should_execute(self, toggle_key: str, raw_value: str) -> bool:
        """Evaluate the rule against the current context's attribute value."""
        parsed_rule = self._try_parse_rule(raw_value)
        if parsed_rule is None:
            return False
        attribute_name, comparison_operator, expected_value = parsed_rule

        attribute_value = self._context_accessor.get_attribute(attribute_name)
        if attribute_value is None:
            return False

        normalized_operator = comparison_operator.lower()
        attribute_value_lower = attribute_value.lower()
        expected_value_lower = expected_value.lower()

        if normalized_operator == "equals":
            return attribute_value_lower == expected_value_lower
        if normalized_operator == "notequals":
            return attribute_value_lower != expected_value_lower
        if normalized_operator == "startswith":
            return attribute_value_lower.startswith(expected_value_lower)
        if normalized_operator == "endswith":
            return attribute_value_lower.endswith(expected_value_lower)
        if normalized_operator == "contains":
            return expected_value_lower in attribute_value_lower
        if normalized_operator == "in":
            return attribute_value_lower in self._split_expected_list(expected_value)
        if normalized_operator == "notin":
            return attribute_value_lower not in self._split_expected_list(expected_value)
        return False

    @staticmethod
    def _split_expected_list(expected_value: str) -> list[str]:
        """Split a comma list into trimmed, lower-cased entries for membership tests."""
        return [
            entry.strip().lower()
            for entry in expected_value.split(",")
            if entry.strip()
        ]

    @staticmethod
    def _try_parse_rule(raw_value: str) -> tuple[str, str, str] | None:
        """Split a rule into (attribute_name, operator, expected_value).

        Returns ``None`` for a malformed rule (no recognised operator marker), so
        the caller can fail closed exactly as the .NET ``TryParseRule`` does.
        """
        rule_body = raw_value[len("attribute:"):].strip()
        lowered_body = rule_body.lower()

        for candidate_operator in _OPERATORS:
            operator_marker = f" {candidate_operator.lower()} "
            operator_index = lowered_body.find(operator_marker)
            if operator_index < 0:
                continue
            attribute_name = rule_body[:operator_index].strip()
            expected_value = rule_body[operator_index + len(operator_marker):].strip()
            return attribute_name, candidate_operator, expected_value

        return None
