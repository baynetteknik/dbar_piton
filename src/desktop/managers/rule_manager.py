"""Rule Manager for Visual Formatting.

Evaluates visual formatting rules against row items ordered by rule priority.
"""

import logging
from typing import Any

from src.desktop.models.visual_rule_model import VisualRule

logger = logging.getLogger(__name__)


class RuleManager:
    """Evaluates VisualRules against row data to determine applicable row/cell styles."""

    @classmethod
    def evaluate_rules(
        cls, rules: list[VisualRule], row_data: dict[str, Any],
    ) -> VisualRule | None:
        """Evaluates rules sorted by priority and returns the first matching rule.

        Args:
            rules: List of VisualRule instances.
            row_data: Dictionary representing row data fields.

        Returns:
            The highest priority matching VisualRule or None.
        """
        sorted_rules = sorted(rules, key=lambda r: r.priority)
        for rule in sorted_rules:
            if cls._check_condition(rule.condition, row_data):
                return rule
        return None

    @classmethod
    def _check_condition(cls, condition: Any, row_data: dict[str, Any]) -> bool:
        field_name = condition.field
        operator = condition.operator
        target_val = condition.value

        if field_name not in row_data:
            return False

        cell_val = row_data[field_name]

        # Numeric conversion attempt
        try:
            num_cell = float(cell_val)
            num_target = float(target_val)
            is_numeric = True
        except (ValueError, TypeError):
            is_numeric = False

        if operator == "less_than":
            if is_numeric:
                return num_cell < num_target
            return str(cell_val) < str(target_val)

        elif operator == "greater_than":
            if is_numeric:
                return num_cell > num_target
            return str(cell_val) > str(target_val)

        elif operator == "equals":
            if is_numeric:
                return num_cell == num_target
            return str(cell_val).lower() == str(target_val).lower()

        elif operator == "not_equals":
            if is_numeric:
                return num_cell != num_target
            return str(cell_val).lower() != str(target_val).lower()

        elif operator == "contains":
            return str(target_val).lower() in str(cell_val).lower()

        return False
