"""
TOYA ERP - Rapor ve Şablon Veri Modelleri (Schema Models)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PaperOrientation(str, Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class BandType(str, Enum):
    OVERLAY = "overlay"
    REPORT_TITLE = "report_title"
    PAGE_HEADER = "page_header"
    HEADER_GROUP = "header_group"
    GROUP_HEADER = "group_header"
    COLUMN_HEADER = "column_header"
    DETAIL_DATA = "detail_data"
    CHILD = "child"
    GROUP_FOOTER = "group_footer"
    COLUMN_FOOTER = "column_footer"
    REPORT_SUMMARY = "report_summary"
    PAGE_FOOTER = "page_footer"


class ItemType(str, Enum):
    TEXT = "text"
    LABEL = "label"
    DATA_FIELD = "data_field"
    EXPRESSION = "expression"
    IMAGE = "image"
    BARCODE = "barcode"
    LINE = "line"
    BOX = "box"
    RICHTEXT = "richtext"
    SUBREPORT = "subreport"
    SYSTEM_VAR = "system_var"


@dataclass
class PageConfig:
    """Sayfa boyutu ve kenar boşlukları (mm)."""
    size: str = "A4"
    orientation: PaperOrientation = PaperOrientation.PORTRAIT
    width_mm: float = 210.0
    height_mm: float = 297.0
    margin_top_mm: float = 10.0
    margin_bottom_mm: float = 10.0
    margin_left_mm: float = 10.0
    margin_right_mm: float = 10.0

    @property
    def printable_width_mm(self) -> float:
        return self.width_mm - (self.margin_left_mm + self.margin_right_mm)

    @property
    def printable_height_mm(self) -> float:
        return self.height_mm - (self.margin_top_mm + self.margin_bottom_mm)


@dataclass
class ItemConfig:
    """Bant içerisindeki görsel eleman."""
    id: str
    type: str = "text"
    text: str = ""
    field: str = ""
    expression: str = ""
    x_mm: float = 0.0
    y_mm: float = 0.0
    w_mm: float = 20.0
    h_mm: float = 8.0
    font_family: str = "Segoe UI"
    font_size: int = 9
    font_bold: bool = False
    font_italic: bool = False
    font_underline: bool = False
    text_color: str = "#000000"
    bg_color: str = ""
    align: str = "left"  # left, center, right, justify
    valign: str = "middle"  # top, middle, bottom
    border_top: bool = False
    border_bottom: bool = False
    border_left: bool = False
    border_right: bool = False
    border_width: float = 0.5
    border_color: str = "#CCCCCC"
    corner_radius: float = 0.0
    format: str = ""  # text, number, currency, date, percent
    format_mask: str = ""
    can_grow: bool = False
    can_shrink: bool = False
    word_wrap: bool = False
    barcode_format: str = "qrcode"  # qrcode, code128, ean13
    image_path: str = ""
    aspect_ratio: str = "keep"  # keep, stretch, center


@dataclass
class BandConfig:
    """Rapor bandı tanımı."""
    id: str
    type: str = "detail_data"
    height_mm: float = 10.0
    dataset: str = ""
    group_by: str = ""
    can_grow: bool = False
    can_shrink: bool = False
    keep_together: bool = False
    print_on_first_page: bool = True
    print_on_last_page: bool = True
    items: list[ItemConfig] = field(default_factory=list)


@dataclass
class ReportTemplate:
    """Komple Rapor / Form Şablonu."""
    template_id: str
    title: str
    schema_version: str = "2.0"
    template_type: str = "print_report"
    page: PageConfig = field(default_factory=PageConfig)
    bands: list[BandConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ReportTemplate:
        page_dict = d.get("page", {})
        page = PageConfig(
            size=page_dict.get("size", "A4"),
            orientation=PaperOrientation(page_dict.get("orientation", "portrait")),
            width_mm=float(page_dict.get("width_mm", 210.0)),
            height_mm=float(page_dict.get("height_mm", 297.0)),
            margin_top_mm=float(page_dict.get("margin_top_mm", 10.0)),
            margin_bottom_mm=float(page_dict.get("margin_bottom_mm", 10.0)),
            margin_left_mm=float(page_dict.get("margin_left_mm", 10.0)),
            margin_right_mm=float(page_dict.get("margin_right_mm", 10.0)),
        )

        bands = []
        for b in d.get("bands", []):
            items = []
            for itm in b.get("items", []):
                items.append(
                    ItemConfig(
                        id=itm.get("id", ""),
                        type=itm.get("type", "text"),
                        text=itm.get("text", ""),
                        field=itm.get("field", ""),
                        expression=itm.get("expression", ""),
                        x_mm=float(itm.get("x_mm", 0.0)),
                        y_mm=float(itm.get("y_mm", 0.0)),
                        w_mm=float(itm.get("w_mm", 20.0)),
                        h_mm=float(itm.get("h_mm", 8.0)),
                        font_family=itm.get("font_family", "Segoe UI"),
                        font_size=int(itm.get("font_size", 9)),
                        font_bold=bool(itm.get("font_bold", False)),
                        font_italic=bool(itm.get("font_italic", False)),
                        font_underline=bool(itm.get("font_underline", False)),
                        text_color=itm.get("text_color", "#000000"),
                        bg_color=itm.get("bg_color", ""),
                        align=itm.get("align", "left"),
                        valign=itm.get("valign", "middle"),
                        border_top=bool(itm.get("border_top", False)),
                        border_bottom=bool(itm.get("border_bottom", False)),
                        border_left=bool(itm.get("border_left", False)),
                        border_right=bool(itm.get("border_right", False)),
                        border_width=float(itm.get("border_width", 0.5)),
                        border_color=itm.get("border_color", "#CCCCCC"),
                        corner_radius=float(itm.get("corner_radius", 0.0)),
                        format=itm.get("format", ""),
                        format_mask=itm.get("format_mask", ""),
                        can_grow=bool(itm.get("can_grow", False)),
                        can_shrink=bool(itm.get("can_shrink", False)),
                        word_wrap=bool(itm.get("word_wrap", False)),
                        barcode_format=itm.get("barcode_format", "qrcode"),
                        image_path=itm.get("image_path", ""),
                        aspect_ratio=itm.get("aspect_ratio", "keep"),
                    )
                )
            bands.append(
                BandConfig(
                    id=b.get("id", ""),
                    type=b.get("type", "detail_data"),
                    height_mm=float(b.get("height_mm", 10.0)),
                    dataset=b.get("dataset", ""),
                    group_by=b.get("group_by", ""),
                    can_grow=bool(b.get("can_grow", False)),
                    can_shrink=bool(b.get("can_shrink", False)),
                    keep_together=bool(b.get("keep_together", False)),
                    print_on_first_page=bool(b.get("print_on_first_page", True)),
                    print_on_last_page=bool(b.get("print_on_last_page", True)),
                    items=items,
                )
            )

        return cls(
            template_id=d.get("template_id", "tpl_custom"),
            title=d.get("title", "Özel Şablon"),
            schema_version=d.get("schema_version", "2.0"),
            template_type=d.get("template_type", "print_report"),
            page=page,
            bands=bands,
        )
