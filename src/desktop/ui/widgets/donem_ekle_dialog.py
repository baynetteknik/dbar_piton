"""TOYA ERP - DonemEkleDialog: Dönem tanımı ekleme/düzenleme popup'ı.

Kayıt ekleme ve düzenleme işlemlerini takvim destekli modern popup ile yönetir.
Varsayılan olarak bilgisayarın geçerli yılına göre 01.01.YYYY - 31.12.YYYY aralığı
ve yıl adı hazır getirilir. Dönemde hareket varsa tarih alanları güvenli şekilde kilitlenir.
"""

from __future__ import annotations

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.components.grid_delegates import apply_calendar_style

_FORMAT = "dd.MM.yyyy"


class DonemEkleDialog(QDialog):
    def __init__(
        self,
        deger: dict | None = None,
        has_movements: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dönem Tanımı")
        self.setMinimumWidth(380)
        apply_light_dialog_style(self)

        current_year = QDate.currentDate().year()

        f = QFormLayout()
        self.txt_ad = QLineEdit()
        self.txt_ad.setPlaceholderText("ör. 2026, 2026-Ç1, Ocak 2026")
        self.txt_ad.setText(str(current_year))

        self.dt_baslangic = QDateEdit(QDate(current_year, 1, 1))
        self.dt_baslangic.setDisplayFormat(_FORMAT)
        apply_calendar_style(self.dt_baslangic)

        self.dt_bitis = QDateEdit(QDate(current_year, 12, 31))
        self.dt_bitis.setDisplayFormat(_FORMAT)
        apply_calendar_style(self.dt_bitis)

        self.chk_aktif = QCheckBox("Aktif (Açık Dönem)")
        self.chk_aktif.setChecked(True)

        if has_movements:
            info = QLabel(
                "⚠️ Bu döneme ait hareket/işlem kayıtları bulunmaktadır.\n"
                "Mali bütünlük için başlangıç/bitiş tarihleri ve dönem kodu kilitlenmiştir.",
            )
            info.setWordWrap(True)
            info.setStyleSheet(
                "color: #b45309; background: #fef3c7; border: 1px solid #fde68a; "
                "padding: 6px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;",
            )
            f.addRow(info)
            self.txt_ad.setEnabled(False)
            self.dt_baslangic.setEnabled(False)
            self.dt_bitis.setEnabled(False)

        f.addRow("Dönem Adı / Kodu *", self.txt_ad)
        f.addRow("Başlangıç Tarihi", self.dt_baslangic)
        f.addRow("Bitiş Tarihi", self.dt_bitis)
        f.addRow("", self.chk_aktif)

        lyt = QVBoxLayout(self)
        lyt.addLayout(f)
        bar = QHBoxLayout()
        bar.addStretch()
        b_kaydet, b_iptal = QPushButton("💾 Kaydet"), QPushButton("✖ Vazgeç")
        b_kaydet.setDefault(True)
        bar.addWidget(b_kaydet)
        bar.addWidget(b_iptal)
        lyt.addLayout(bar)
        b_kaydet.clicked.connect(self.accept)
        b_iptal.clicked.connect(self.reject)

        if deger:
            self.txt_ad.setText(deger.get("ad") or "")
            d1 = QDate.fromString((deger.get("baslangic") or "").strip(), _FORMAT)
            if d1.isValid():
                self.dt_baslangic.setDate(d1)
            d2 = QDate.fromString((deger.get("bitis") or "").strip(), _FORMAT)
            if d2.isValid():
                self.dt_bitis.setDate(d2)
            self.chk_aktif.setChecked(
                str(deger.get("aktif", "")).strip().lower() in ("evet", "true", "1", "aktif"),
            )

    def deger(self) -> dict:
        return {
            "ad": self.txt_ad.text().strip(),
            "baslangic": self.dt_baslangic.date().toString(_FORMAT),
            "bitis": self.dt_bitis.date().toString(_FORMAT),
            "aktif": "Evet" if self.chk_aktif.isChecked() else "Hayır",
        }
