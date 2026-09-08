"""StyledItemDelegate for conditional visual formatting rules."""

import logging
from typing import Any

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

from src.desktop.managers.rule_manager import RuleManager
from src.desktop.models.visual_rule_model import VisualRule

logger = logging.getLogger(__name__)


class ProfileStyleDelegate(QStyledItemDelegate):
    """Custom delegate that paints cells according to active VisualRules."""

    #: İşaretli satırların arka plan tonu ve gösterge işareti
    MARKED_ROW_BG = QColor("#fef9c3")  # açık sarı (DIA seçili satır tonu)
    MARKED_PREFIX = "› "  # "› "

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules: list[VisualRule] = []
        self.field_mapping: dict[int, str] = {}  # col_idx -> field_name
        self.marked_rows: set[int] = set()
        self.marked_select_column: int | None = None

    def set_rules(self, rules: list[VisualRule], field_mapping: dict[int, str]):
        """Sets active rules and column index mapping."""
        self.rules = rules
        self.field_mapping = field_mapping

    def set_marked_rows(self, rows: set[int], select_column: int | None = None):
        """İşaretli (checkbox ile seçili) satır kümesini ayarlar."""
        self.marked_rows = set(rows)
        self.marked_select_column = select_column

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex,
    ):
        """Paints cell with conditional background, text color, font weight and icon."""
        if not index.isValid():
            super().paint(painter, option, index)
            return

        is_marked = index.row() in self.marked_rows

        if not self.rules and not is_marked:
            super().paint(painter, option, index)
            return

        row_data = self._extract_row_data(index) if self.rules else {}
        matching_rule = RuleManager.evaluate_rules(self.rules, row_data) if self.rules else None

        if is_marked and not matching_rule:
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            if not (opt.state & QStyle.StateFlag.State_Selected):
                opt.backgroundBrush = self.MARKED_ROW_BG
            if index.column() == self.marked_select_column and opt.text:
                opt.text = f"{self.MARKED_PREFIX}{opt.text}"
            super().paint(painter, opt, index)
            return

        if matching_rule:
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)

            style = matching_rule.style
            if style.background_color:
                opt.backgroundBrush = QColor(style.background_color)

            if style.text_color:
                opt.palette.setColor(opt.palette.ColorRole.Text, QColor(style.text_color))

            if style.font_weight == "bold":
                opt.font.setFontWeight(QFont.Weight.Bold)

            if style.icon:
                text = str(opt.text)
                opt.text = f"{style.icon} {text}"

            super().paint(painter, opt, index)
        else:
            super().paint(painter, option, index)

    def _extract_row_data(self, index: QModelIndex) -> dict[str, Any]:
        model = index.model()
        row = index.row()
        data: dict[str, Any] = {}

        if not model:
            return data

        column_count = model.columnCount()
        for col in range(column_count):
            field_name = self.field_mapping.get(col, f"col_{col}")
            idx = model.index(row, col)
            val = model.data(idx, Qt.ItemDataRole.DisplayRole)
            data[field_name] = val

        return data
