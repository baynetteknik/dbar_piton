"""
TOYA ERP - CurrencyPickerDialog

Döviz kodu/isim/sembolün serbest metinle elden yazılması yerine, sabit
ISO 4217 kataloğundan (bkz. `currency_catalog.py`) aranıp seçilmesini sağlayan
paylaşılan diyalog. Hem "Yeni Döviz Ekle" hem ilk kurulum döviz seçimi bu
diyaloğun üzerine kuruludur.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.services.currency_catalog import CURRENCY_CATALOG, CurrencyInfo


class CurrencyPickerDialog(QDialog):
    """Aranabilir, tekil seçimli döviz listesi — bayrak + kod + isim + sembol."""

    def __init__(self, parent=None, *, exclude_codes: set[str] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Döviz Seç")
        apply_light_dialog_style(self)
        self.resize(380, 480)
        self._exclude = {c.upper() for c in (exclude_codes or set())}
        self._selected: CurrencyInfo | None = None

        lyt = QVBoxLayout(self)
        self.txt_ara = QLineEdit()
        self.txt_ara.setPlaceholderText("Kod veya isimle ara... (ör. USD, Euro)")
        self.txt_ara.textChanged.connect(self._populate)
        lyt.addWidget(self.txt_ara)

        self.lst = QListWidget()
        self.lst.itemDoubleClicked.connect(lambda _it: self._accept())
        lyt.addWidget(self.lst, 1)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        lyt.addWidget(box)

        self._populate("")
        self.txt_ara.setFocus()

    def _populate(self, query: str = "") -> None:
        self.lst.clear()
        q = query.strip().lower()
        for info in CURRENCY_CATALOG:
            if info.code in self._exclude:
                continue
            haystack = f"{info.code} {info.name}".lower()
            if q and q not in haystack:
                continue
            item = QListWidgetItem(f"{info.flag}  {info.code} — {info.name} ({info.symbol})")
            item.setData(Qt.ItemDataRole.UserRole, info)
            self.lst.addItem(item)
        if self.lst.count():
            self.lst.setCurrentRow(0)

    def _accept(self) -> None:
        item = self.lst.currentItem()
        if item is None:
            return
        self._selected = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def selected_currency(self) -> CurrencyInfo | None:
        return self._selected


def pick_currency(parent=None, *, exclude_codes: set[str] | None = None) -> CurrencyInfo | None:
    """Diyaloğu açar; seçilen `CurrencyInfo`'yu (ya da iptalde `None`) döner."""
    dlg = CurrencyPickerDialog(parent, exclude_codes=exclude_codes)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.selected_currency()
