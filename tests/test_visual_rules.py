"""Unit tests for Visual Rules and RuleManager."""

import pytest
from src.desktop.managers.rule_manager import RuleManager
from src.desktop.models.visual_rule_model import (
    VisualRule,
    VisualRuleCondition,
    VisualRuleStyle,
)


def test_rule_manager_evaluation():
    """Test rule prioritization and evaluation against row data."""
    rule_high_priority = VisualRule(
        id="r1",
        name="High Priority Debt",
        priority=1,
        condition=VisualRuleCondition(field="bakiye", operator="less_than", value=0),
        style=VisualRuleStyle(background_color="#f8d7da", text_color="#721c24"),
    )

    rule_low_priority = VisualRule(
        id="r2",
        name="Low Priority Passive",
        priority=2,
        condition=VisualRuleCondition(field="durum", operator="equals", value="Pasif"),
        style=VisualRuleStyle(background_color="#fff3cd"),
    )

    rules = [rule_low_priority, rule_high_priority]

    # Row that matches both: bakiye < 0 AND durum == Pasif
    row_both = {"bakiye": -150.0, "durum": "Pasif"}
    matched = RuleManager.evaluate_rules(rules, row_both)

    assert matched is not None
    assert matched.id == "r1"  # Highest priority (1 < 2) should win

    # Row that only matches rule 2
    row_passive_only = {"bakiye": 100.0, "durum": "Pasif"}
    matched_passive = RuleManager.evaluate_rules(rules, row_passive_only)

    assert matched_passive is not None
    assert matched_passive.id == "r2"

    # Row that matches neither
    row_normal = {"bakiye": 500.0, "durum": "Aktif"}
    assert RuleManager.evaluate_rules(rules, row_normal) is None
