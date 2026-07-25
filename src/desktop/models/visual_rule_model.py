"""Data models for visual formatting rules."""

from dataclasses import dataclass
from typing import Any


@dataclass
class VisualRuleStyle:
    """Style configuration for visual formatting rules."""

    background_color: str | None = None
    text_color: str | None = None
    font_weight: str | None = None
    icon: str | None = None
    opacity: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert style instance to a dictionary."""
        result: dict[str, Any] = {}
        if self.background_color is not None:
            result["background_color"] = self.background_color
        if self.text_color is not None:
            result["text_color"] = self.text_color
        if self.font_weight is not None:
            result["font_weight"] = self.font_weight
        if self.icon is not None:
            result["icon"] = self.icon
        if self.opacity is not None:
            result["opacity"] = self.opacity
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualRuleStyle":
        """Create a VisualRuleStyle instance from a dictionary."""
        return cls(
            background_color=data.get("background_color"),
            text_color=data.get("text_color"),
            font_weight=data.get("font_weight"),
            icon=data.get("icon"),
            opacity=data.get("opacity"),
        )


@dataclass
class VisualRuleCondition:
    """Condition configuration for visual formatting rules."""

    field: str
    operator: str  # less_than, greater_than, equals, not_equals, contains
    value: Any

    def to_dict(self) -> dict[str, Any]:
        """Convert condition instance to a dictionary."""
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualRuleCondition":
        """Create a VisualRuleCondition instance from a dictionary."""
        return cls(
            field=data.get("field", ""),
            operator=data.get("operator", "equals"),
            value=data.get("value"),
        )


@dataclass
class VisualRule:
    """Complete visual rule data structure with priority."""

    id: str
    name: str
    priority: int
    condition: VisualRuleCondition
    style: VisualRuleStyle

    def to_dict(self) -> dict[str, Any]:
        """Convert rule instance to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority,
            "condition": self.condition.to_dict(),
            "style": self.style.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VisualRule":
        """Create a VisualRule instance from a dictionary."""
        condition_data = data.get("condition", {})
        style_data = data.get("style", {})
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            priority=data.get("priority", 99),
            condition=VisualRuleCondition.from_dict(condition_data),
            style=VisualRuleStyle.from_dict(style_data),
        )
