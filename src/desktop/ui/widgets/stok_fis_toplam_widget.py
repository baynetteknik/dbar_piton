"""TOYA ERP - StokFisToplamWidget: stok fişi satırlarının birim bazında giriş / çıkış / transfer / sayılan miktar ve tutar toplamları.

    w.update_totals({"Adet": (giris, cikis, transfer, sayilan, tutar)})"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QLabel, QTableWidgetItem, QVBoxLayout

from src.desktop.core.grid_presets import GRID_PRESETS, register_preset
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.widgets.money_edit import bicimle

PRESET_ID = "dbgrid_stok_fis_toplam"
_LABELS = ["BİRİM", "GİRİŞ", "ÇIKIŞ", "TRANSFER", "SAYILAN", "TUTAR"]
_WIDTHS = [0.14, 0.18, 0.18, 0.18, 0.16, 0.16]


class StokFisToplamWidget(QFrame):
    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        if PRESET_ID not in GRID_PRESETS:
            register_preset(PRESET_ID, _LABELS, _WIDTHS, ["C", "R", "R", "R", "R", "R"], name="Stok Fiş Toplamları")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        t = QLabel("TOPLAMLAR")
        t.setStyleSheet("font-size:10px; font-weight:800; color:#1e3a8a; letter-spacing:1px;")
        v.addWidget(t)
        self.grid = AppGrid(PRESET_ID)
        if db_session is not None:
            self.grid.enable_layout_persistence(db_session)
        v.addWidget(self.grid, 1)

    def update_totals(self, totals: dict[str, tuple[float, float, float, float, float]]) -> None:
        g = self.grid
        g.setRowCount(0)
        for birim, (gir, cik, tra, say, tut) in sorted(totals.items()):
            self._row([birim, bicimle(gir, 3), bicimle(cik, 3), bicimle(tra, 3), bicimle(say, 3), bicimle(tut, 2)])
        if totals:
            self._row(["TOPLAM", "", "", "", "", bicimle(sum(t[4] for t in totals.values()), 2)], bold=True)

    def _row(self, cells: list[str], bold: bool = False) -> None:
        g = self.grid
        r = g.rowCount()
        g.insertRow(r)
        g.setRowHeight(r, g.effective_row_height)
        for c, text in enumerate(cells):
            it = QTableWidgetItem(text)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            it.setTextAlignment((Qt.AlignmentFlag.AlignCenter if c == 0 else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter)
            if bold:
                f = QFont(it.font())
                f.setBold(True)
                it.setFont(f)
            g.setItem(r, c, it)

    def clear(self) -> None:
        self.grid.setRowCount(0)
