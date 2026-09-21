"""TOYA ERP - CariFisToplamWidget: fiş satırlarının döviz bazında borç / alacak / bakiye toplamları.

    w.update_totals({"TRY": (borc, alacak, borc_tl, alacak_tl), "USD": (...)})
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import QFrame, QLabel, QTableWidgetItem, QVBoxLayout

from src.desktop.core.grid_presets import GRID_PRESETS, register_preset
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.widgets.cari_durum_widget import fmt_tl

PRESET_ID = "dbgrid_cari_fis_toplam"
_LABELS = ["DÖVİZ", "BORÇ", "ALACAK", "BAKİYE", "Y. BORÇ", "Y. ALACAK", "Y. BAKİYE", "B/A"]
_WIDTHS = [0.12, 0.14, 0.14, 0.14, 0.13, 0.13, 0.13, 0.07]


def _bakiye_yon(v: float) -> str:
    return "" if abs(v) < 0.005 else "(B)" if v > 0 else "(A)"


class CariFisToplamWidget(QFrame):
    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        if PRESET_ID not in GRID_PRESETS:
            register_preset(PRESET_ID, _LABELS, _WIDTHS, ["C", "R", "R", "R", "R", "R", "R", "C"], name="Cari Fiş Toplamları")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        t = QLabel("TOPLAMLAR")
        t.setStyleSheet("font-size:10px; font-weight:800; color:#1e3a8a; letter-spacing:1px;")
        v.addWidget(t)
        self.grid = AppGrid(PRESET_ID)
        if db_session is not None:
            self.grid.enable_layout_persistence(db_session)      # sütun sırası / görünürlük / genişlik kalıcı
        v.addWidget(self.grid, 1)

    def update_totals(self, totals: dict[str, tuple[float, float, float, float]]) -> None:
        g = self.grid
        g.setRowCount(0)
        top = [0.0, 0.0]
        for para, (borc, alacak, borc_tl, alacak_tl) in sorted(totals.items()):
            self._row([para, fmt_tl(borc), fmt_tl(alacak), fmt_tl(abs(borc - alacak)), fmt_tl(borc_tl), fmt_tl(alacak_tl),
                       fmt_tl(abs(borc_tl - alacak_tl)), _bakiye_yon(borc - alacak)])
            top[0] += borc_tl
            top[1] += alacak_tl
        if totals:
            self._row(["TOPLAM", "", "", "", fmt_tl(top[0]), fmt_tl(top[1]), fmt_tl(abs(top[0] - top[1])),
                       _bakiye_yon(top[0] - top[1])], bold=True)

    def _row(self, cells: list[str], bold: bool = False) -> None:
        g = self.grid
        r = g.rowCount()
        g.insertRow(r)
        g.setRowHeight(r, g.effective_row_height)
        for c, text in enumerate(cells):
            it = QTableWidgetItem(text)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            it.setTextAlignment((Qt.AlignmentFlag.AlignCenter if c in (0, 7) else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter)
            if bold:
                f = QFont(it.font())
                f.setBold(True)
                it.setFont(f)
            if c == 7 and text:
                it.setForeground(QBrush(QColor("#dc2626" if text == "(B)" else "#16a34a")))
            g.setItem(r, c, it)

    def clear(self) -> None:
        self.grid.setRowCount(0)
