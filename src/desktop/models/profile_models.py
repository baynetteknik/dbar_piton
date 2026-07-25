"""Data models for View Profiles (v2.0.0)."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.desktop.models.virtual_column_model import VirtualColumn
from src.desktop.models.visual_rule_model import VisualRule


@dataclass
class ColumnGroup:
    """Represents a logical group of columns (e.g. Core Info, Custom Codes 1-20)."""

    id: str
    name: str
    is_collapsible: bool = True
    is_collapsed: bool = False
    columns: list[str] = field(default_factory=list)
    is_locked: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert ColumnGroup to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "is_collapsible": self.is_collapsible,
            "is_collapsed": self.is_collapsed,
            "columns": list(self.columns),
            "is_locked": self.is_locked,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColumnGroup":
        """Create ColumnGroup from dict."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            is_collapsible=data.get("is_collapsible", True),
            is_collapsed=data.get("is_collapsed", False),
            columns=list(data.get("columns", [])),
            is_locked=data.get("is_locked", False),
        )


@dataclass
class IndividualColumn:
    """Represents settings for a single column."""

    visible: bool = True
    width: int = 120
    order: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert IndividualColumn to dict."""
        return {
            "visible": self.visible,
            "width": self.width,
            "order": self.order,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndividualColumn":
        """Create IndividualColumn from dict."""
        return cls(
            visible=data.get("visible", True),
            width=data.get("width", 120),
            order=data.get("order", 0),
        )


@dataclass
class FrozenColumns:
    """Settings for frozen/sticky columns."""

    count: int = 0
    columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert FrozenColumns to dict."""
        return {
            "count": self.count,
            "columns": list(self.columns),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FrozenColumns":
        """Create FrozenColumns from dict."""
        return cls(
            count=data.get("count", 0),
            columns=list(data.get("columns", [])),
        )


@dataclass
class ColumnSettings:
    """Aggregated column settings container."""

    groups: list[ColumnGroup] = field(default_factory=list)
    individual_columns: dict[str, IndividualColumn] = field(default_factory=dict)
    frozen_columns: FrozenColumns = field(default_factory=FrozenColumns)

    def to_dict(self) -> dict[str, Any]:
        """Convert ColumnSettings to dict."""
        return {
            "groups": [g.to_dict() for g in self.groups],
            "individual_columns": {
                k: v.to_dict() for k, v in self.individual_columns.items()
            },
            "frozen_columns": self.frozen_columns.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColumnSettings":
        """Create ColumnSettings from dict."""
        groups = [ColumnGroup.from_dict(g) for g in data.get("groups", [])]
        indiv = {
            k: IndividualColumn.from_dict(v)
            for k, v in data.get("individual_columns", {}).items()
        }
        frozen = FrozenColumns.from_dict(data.get("frozen_columns", {}))
        return cls(groups=groups, individual_columns=indiv, frozen_columns=frozen)


@dataclass
class SummaryField:
    """Field definition for the footer summary bar."""

    id: str
    name: str
    aggregation: str  # sum, count, average, formula
    field: str | None = None
    formula: str | None = None
    format: str = "#,##0.00 ₺"

    def to_dict(self) -> dict[str, Any]:
        """Convert SummaryField to dict."""
        res: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "aggregation": self.aggregation,
            "format": self.format,
        }
        if self.field is not None:
            res["field"] = self.field
        if self.formula is not None:
            res["formula"] = self.formula
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SummaryField":
        """Create SummaryField from dict."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            aggregation=data.get("aggregation", "sum"),
            field=data.get("field"),
            formula=data.get("formula"),
            format=data.get("format", "#,##0.00 ₺"),
        )


@dataclass
class SummaryBarSettings:
    """Summary bar configuration."""

    is_enabled: bool = True
    fields: list[SummaryField] = field(default_factory=list)
    position: str = "bottom"

    def to_dict(self) -> dict[str, Any]:
        """Convert SummaryBarSettings to dict."""
        return {
            "is_enabled": self.is_enabled,
            "fields": [f.to_dict() for f in self.fields],
            "position": self.position,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SummaryBarSettings":
        """Create SummaryBarSettings from dict."""
        fields = [SummaryField.from_dict(f) for f in data.get("fields", [])]
        return cls(
            is_enabled=data.get("is_enabled", True),
            fields=fields,
            position=data.get("position", "bottom"),
        )


@dataclass
class ProfileMetadata:
    """Metadata for a View Profile."""

    id: str
    name: str
    table_id: str = "customers_table"
    profile_type: str = "user_defined"  # user_defined or system_default
    created_at: str = ""
    updated_at: str = ""
    is_active: bool = True

    def __post_init__(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now_iso
        if not self.updated_at:
            self.updated_at = now_iso

    def to_dict(self) -> dict[str, Any]:
        """Convert ProfileMetadata to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "table_id": self.table_id,
            "profile_type": self.profile_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProfileMetadata":
        """Create ProfileMetadata from dict."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            table_id=data.get("table_id", "customers_table"),
            profile_type=data.get("profile_type", "user_defined"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            is_active=data.get("is_active", True),
        )


@dataclass
class ThemeSetting:
    """Theme configuration for a profile."""

    variant: str = "custom"
    row_height: int = 30
    alternate_row_colors: bool = True
    alternate_colors: list[str] = field(
        default_factory=lambda: ["#ffffff", "#f8f9fa"],
    )
    header_color: str = "#e9ecef"
    header_text_color: str = "#212529"

    def to_dict(self) -> dict[str, Any]:
        """Convert ThemeSetting to dict."""
        return {
            "variant": self.variant,
            "row_height": self.row_height,
            "alternate_row_colors": self.alternate_row_colors,
            "alternate_colors": list(self.alternate_colors),
            "header_color": self.header_color,
            "header_text_color": self.header_text_color,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ThemeSetting":
        """Create ThemeSetting from dict."""
        return cls(
            variant=data.get("variant", "custom"),
            row_height=data.get("row_height", 30),
            alternate_row_colors=data.get("alternate_row_colors", True),
            alternate_colors=list(
                data.get("alternate_colors", ["#ffffff", "#f8f9fa"]),
            ),
            header_color=data.get("header_color", "#e9ecef"),
            header_text_color=data.get("header_text_color", "#212529"),
        )


@dataclass
class ViewProfile:
    """Complete View Profile Root Object (v2.0.0)."""

    version: str = "2.0.0"
    profile: ProfileMetadata = field(
        default_factory=lambda: ProfileMetadata(id="default", name="Varsayılan"),
    )
    column_settings: ColumnSettings = field(default_factory=ColumnSettings)
    visual_rules: list[VisualRule] = field(default_factory=list)
    virtual_columns: list[VirtualColumn] = field(default_factory=list)
    summary_bar: SummaryBarSettings = field(default_factory=SummaryBarSettings)
    filters: dict[str, Any] = field(
        default_factory=lambda: {"enabled": True, "presets": [], "quick_filters": []},
    )
    sorting: dict[str, Any] = field(
        default_factory=lambda: {"column": "", "order": "ascending", "multi_sort": []},
    )
    pagination: dict[str, Any] = field(
        default_factory=lambda: {"page_size": 50, "page_sizes": [20, 50, 100, 200]},
    )
    theme: ThemeSetting = field(default_factory=ThemeSetting)
    export_settings: dict[str, Any] = field(
        default_factory=lambda: {
            "pdf": {"orientation": "landscape", "page_size": "A4", "include_summary": True},
            "excel": {"auto_width": True, "freeze_panes": True, "include_formulas": False},
        },
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert ViewProfile to dictionary."""
        return {
            "version": self.version,
            "profile": self.profile.to_dict(),
            "column_settings": self.column_settings.to_dict(),
            "visual_rules": [r.to_dict() for r in self.visual_rules],
            "virtual_columns": [vc.to_dict() for vc in self.virtual_columns],
            "summary_bar": self.summary_bar.to_dict(),
            "filters": self.filters,
            "sorting": self.sorting,
            "pagination": self.pagination,
            "theme": self.theme.to_dict(),
            "export_settings": self.export_settings,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize ViewProfile to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ViewProfile":
        """Create ViewProfile instance from dictionary."""
        version = data.get("version", "2.0.0")
        profile_meta = ProfileMetadata.from_dict(data.get("profile", {}))
        col_settings = ColumnSettings.from_dict(data.get("column_settings", {}))
        visual_rules = [
            VisualRule.from_dict(r) for r in data.get("visual_rules", [])
        ]
        virtual_cols = [
            VirtualColumn.from_dict(vc) for vc in data.get("virtual_columns", [])
        ]
        summary_bar = SummaryBarSettings.from_dict(data.get("summary_bar", {}))
        filters = data.get("filters", {"enabled": True, "presets": [], "quick_filters": []})
        sorting = data.get("sorting", {"column": "", "order": "ascending", "multi_sort": []})
        pagination = data.get("pagination", {"page_size": 50, "page_sizes": [20, 50, 100, 200]})
        theme = ThemeSetting.from_dict(data.get("theme", {}))
        export_settings = data.get(
            "export_settings",
            {
                "pdf": {"orientation": "landscape", "page_size": "A4", "include_summary": True},
                "excel": {"auto_width": True, "freeze_panes": True, "include_formulas": False},
            },
        )

        return cls(
            version=version,
            profile=profile_meta,
            column_settings=col_settings,
            visual_rules=visual_rules,
            virtual_columns=virtual_cols,
            summary_bar=summary_bar,
            filters=filters,
            sorting=sorting,
            pagination=pagination,
            theme=theme,
            export_settings=export_settings,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ViewProfile":
        """Deserialize ViewProfile from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
