"""StyledItemDelegate for conditional visual formatting rules."""

import logging
from typing import Any

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from src.desktop.managers.rule_manager import RuleManager
from src.desktop.models.visual_rule_model import VisualRule

logger = logging.getLogger(__name__)


class ProfileStyleDelegate(QStyledItemDelegate):
    """Custom delegate that paints cells according to active VisualRules."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules: list[VisualRule] = []
        self.field_mapping: dict[int, str] = {}  # col_idx -> field_name

    def set_rules(self, rules: list[VisualRule], field_mapping: dict[int, str]):
        """Sets active rules and column index mapping."""
        self.rules = rules
        self.field_mapping = field_mapping

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex,
    ):
        """Paints cell with conditional background, text color, font weight and icon."""
        if not self.rules or not index.isValid():
            super().paint(painter, option, index)
            return

        row_data = self._extract_row_data(index)
        matching_rule = RuleManager.evaluate_rules(self.rules, row_data)

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
