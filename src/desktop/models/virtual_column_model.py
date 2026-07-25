"""Data models for virtual computed columns."""

from dataclasses import dataclass
from typing import Any


@dataclass
class VirtualColumn:
    """Represents a computed virtual column definition."""

    id: str
    name: str
    formula: str
    data_type: str = "decimal"  # decimal, percentage, boolean, string
    format: str = "#,##0.00 ₺"
    is_visible: bool = True
    order: int = 99

    def to_dict(self) -> dict[str, Any]:
        """Convert virtual column instance to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "formula": self.formula,
            "data_type": self.data_type,
            "format": self.format,
            "is_visible": self.is_visible,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VirtualColumn":
        """Create VirtualColumn instance from dictionary."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            formula=data.get("formula", ""),
            data_type=data.get("data_type", "decimal"),
            format=data.get("format", "#,##0.00 ₺"),
            is_visible=data.get("is_visible", True),
            order=data.get("order", 99),
        )
