"""TOYA ERP - StokFisToplamWidget: stok fişi satırlarının birim bazında giriş / çıkış / transfer / sayılan miktar ve tutar toplamları.

    w.update_totals({"Adet": (giris, cikis, transfer, sayilan, tutar)})"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QStandardItem
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from src.desktop.ui.components.entry_table_view import standart_grid
from src.desktop.services import sayi_bicimi
from src.desktop.ui.widgets.money_edit import bicimle

PRESET_ID = "dbgrid_stok_fis_toplam"
_LABELS = ["BİRİM", "GİRİŞ", "ÇIKIŞ", "TRANSFER", "SAYILAN", "TUTAR"]
_WIDTHS = [0.14, 0.18, 0.18, 0.18, 0.16, 0.16]


class StokFisToplamWidget(QFrame):
    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        t = QLabel("TOPLAMLAR")
        t.setStyleSheet("font-size:10px; font-weight:800; color:#1e3a8a; letter-spacing:1px;")
        v.addWidget(t)
        self.entry = standart_grid(PRESET_ID, [(f"c{i}", e) for i, e in enumerate(_LABELS)])
        self.grid = self.entry.table_view
        v.addWidget(self.entry, 1)
        self._oranli = True
        self._genislik_uygulaniyor = False
        self.grid.horizontalHeader().sectionResized.connect(self._sutun_boyutlandi)

    def _sutun_boyutlandi(self, *_args) -> None:
        if not self._genislik_uygulaniyor:
            self._oranli = False

    def _oranli_genislik(self) -> None:
        if not self._oranli:
            return
        width = max(self.grid.viewport().width(), 300)
        self._genislik_uygulaniyor = True
        try:
            for column, ratio in enumerate(_WIDTHS):
                self.grid.setColumnWidth(column, max(40, int(width * ratio / sum(_WIDTHS))))
        finally:
            self._genislik_uygulaniyor = False

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self._oranli_genislik)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._oranli_genislik()

    def update_totals(self, totals: dict[str, tuple[float, float, float, float, float]]) -> None:
        g = self.grid
        g.setRowCount(0)
        hm, ht = sayi_bicimi.hane("miktar"), sayi_bicimi.hane("tutar")
        for birim, (gir, cik, tra, say, tut) in sorted(totals.items()):
            self._row([birim, bicimle(gir, hm), bicimle(cik, hm), bicimle(tra, hm), bicimle(say, hm), bicimle(tut, ht)])
        if totals:
            self._row(["TOPLAM", "", "", "", "", bicimle(sum(t[4] for t in totals.values()), ht)], bold=True)

    def _row(self, cells: list[str], bold: bool = False) -> None:
        g = self.grid
        r = g.rowCount()
        g.insertRow(r)
        g.setRowHeight(r, g.effective_row_height)
        for c, text in enumerate(cells):
            it = QStandardItem(text)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            it.setTextAlignment((Qt.AlignmentFlag.AlignCenter if c == 0 else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter)
            if bold:
                f = QFont(it.font())
                f.setBold(True)
                it.setFont(f)
            g.setItem(r, c, it)

    def clear(self) -> None:
        self.grid.setRowCount(0)
