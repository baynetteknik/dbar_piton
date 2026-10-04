"""TOYA ERP - CariFisToplamWidget: fiş satırlarının döviz bazında borç / alacak / bakiye toplamları.

    w.update_totals({"TRY": (borc, alacak, borc_tl, alacak_tl), "USD": (...)})
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont, QStandardItem
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from src.desktop.ui.components.entry_table_view import standart_grid
from src.desktop.ui.widgets.cari_durum_widget import fmt_tl

PRESET_ID = "dbgrid_cari_fis_toplam"
_LABELS = ["DÖVİZ", "BORÇ", "ALACAK", "BAKİYE", "Y. BORÇ", "Y. ALACAK", "Y. BAKİYE", "B/A"]
_WIDTHS = [0.12, 0.14, 0.14, 0.14, 0.13, 0.13, 0.13, 0.07]


def _bakiye_yon(v: float) -> str:
    return "" if abs(v) < 0.005 else "(B)" if v > 0 else "(A)"


class CariFisToplamWidget(QFrame):
    """Alt sınıflar `PRESET_ID`, `PRESET_AD`, `ETIKETLER` ve `YONLER` (pozitif/negatif bakiye işareti) ile başlığı özelleştirir."""
    PRESET_ID = PRESET_ID
    PRESET_AD = "Cari Fiş Toplamları"
    ETIKETLER = _LABELS
    YONLER = ("(B)", "(A)")
    RENKLER = ("#dc2626", "#16a34a")

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        t = QLabel("TOPLAMLAR")
        t.setStyleSheet("font-size:10px; font-weight:800; color:#1e3a8a; letter-spacing:1px;")
        v.addWidget(t)
        self.entry = standart_grid(self.PRESET_ID, [(f"c{i}", e) for i, e in enumerate(self.ETIKETLER)])
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

    def update_totals(self, totals: dict[str, tuple[float, float, float, float]]) -> None:
        g = self.grid
        g.setRowCount(0)
        top = [0.0, 0.0]
        for para, (borc, alacak, borc_tl, alacak_tl) in sorted(totals.items()):
            self._row([para, fmt_tl(borc), fmt_tl(alacak), fmt_tl(abs(borc - alacak)), fmt_tl(borc_tl), fmt_tl(alacak_tl),
                       fmt_tl(abs(borc_tl - alacak_tl)), self._yon(borc - alacak)])
            top[0] += borc_tl
            top[1] += alacak_tl
        if totals:
            self._row(["TOPLAM", "", "", "", fmt_tl(top[0]), fmt_tl(top[1]), fmt_tl(abs(top[0] - top[1])),
                       self._yon(top[0] - top[1])], bold=True)

    def _yon(self, v: float) -> str:
        return "" if abs(v) < 0.005 else self.YONLER[0] if v > 0 else self.YONLER[1]

    def _row(self, cells: list[str], bold: bool = False) -> None:
        g = self.grid
        r = g.rowCount()
        g.insertRow(r)
        g.setRowHeight(r, g.effective_row_height)
        for c, text in enumerate(cells):
            it = QStandardItem(text)
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            it.setTextAlignment((Qt.AlignmentFlag.AlignCenter if c in (0, 7) else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter)
            if bold:
                f = QFont(it.font())
                f.setBold(True)
                it.setFont(f)
            if c == 7 and text:
                it.setForeground(QBrush(QColor(self.RENKLER[0] if text == self.YONLER[0] else self.RENKLER[1])))
            g.setItem(r, c, it)

    def clear(self) -> None:
        self.grid.setRowCount(0)
