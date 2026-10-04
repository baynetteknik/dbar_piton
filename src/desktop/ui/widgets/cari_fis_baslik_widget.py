"""TOYA ERP - CariFisBaslikWidget: cari hesap fişinin başlık bilgileri (fiş no, tarih, saat, belge no, şube, kodlar).

Fiş türü yalnızca yeni eklenen satırın varsayılan türüdür; her satır kendi türünü taşır.

    w = CariFisBaslikWidget(); w.tur_changed.connect(...); w.get_data(); w.set_data({...}); w.clear()
"""

from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
)

from src.desktop.services.cari_hareket_service import FIS_TIPLERI
from src.desktop.ui.components.grid_delegates import apply_calendar_style

_LBL = "font-size:11px; font-weight:600; color:#475569;"
_FIELD = ("QLineEdit, QComboBox, QDateEdit { border:1px solid #cbd5e1; border-radius:4px; padding:3px 6px;"
          " background:white; color:#0f172a; font-size:11px; }"
          " QLineEdit:read-only { background:#f1f5f9; color:#64748b; }"
          " QComboBox { combobox-popup: 0; }")


class CariFisBaslikWidget(QFrame):
    tur_changed = pyqtSignal(str)
    bitti = pyqtSignal()          # son alanda Enter: odak kalemlere geçsin
    data_changed = pyqtSignal()

    def __init__(self, parent=None, tipler: dict[str, str] | None = None) -> None:
        super().__init__(parent)
        self._tipler = tipler or FIS_TIPLERI          # fiş türleri (varsayılan: cari); stok vb. kendi listesini verir
        self.setObjectName("CariFisBaslik")
        self.setStyleSheet("#CariFisBaslik { background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; }" + _FIELD)
        g = QGridLayout(self)
        g.setContentsMargins(10, 8, 10, 8)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(6)

        self.cmb_tur = QComboBox()
        for k, etiket in self._tipler.items():
            self.cmb_tur.addItem(etiket, k)
        self.cmb_tur.setToolTip("Fiş türü; yeni satırın başlangıç türünü belirler. Her satırın türü ayrıca değiştirilebilir.")
        self.txt_fis_no = QLineEdit()
        self.txt_fis_no.setPlaceholderText("Otomatik")
        self.dt_tarih = QDateEdit(QDate.currentDate())
        apply_calendar_style(self.dt_tarih)          # takvimli seçici, okunaklı açık renkler
        self.dt_tarih.setDisplayFormat("dd.MM.yyyy")
        self.txt_saat = QLineEdit(datetime.now().strftime("%H:%M:%S"))
        self.txt_saat.setReadOnly(True)
        self.txt_saat.setFocusPolicy(Qt.FocusPolicy.NoFocus)      # Tab akışında atlanır
        self.txt_belge_no = QLineEdit()
        self.txt_sube = QLineEdit()
        self.txt_ozel_kod = QLineEdit()
        self.txt_yetki = QLineEdit()
        self.chk_kilitli = QCheckBox("Kilitli")

        def lbl(t: str) -> QLabel:
            x = QLabel(t)
            x.setStyleSheet(_LBL)
            return x

        g.addWidget(lbl("Fiş Türü"), 0, 0); g.addWidget(self.cmb_tur, 0, 1)
        g.addWidget(lbl("Fiş No"), 1, 0); g.addWidget(self.txt_fis_no, 1, 1)
        g.addWidget(lbl("Tarih"), 0, 2); g.addWidget(self.dt_tarih, 0, 3)
        g.addWidget(lbl("Saat"), 1, 2); g.addWidget(self.txt_saat, 1, 3)
        g.addWidget(lbl("Belge No"), 0, 4); g.addWidget(self.txt_belge_no, 0, 5)
        g.addWidget(lbl("Şube"), 1, 4); g.addWidget(self.txt_sube, 1, 5)
        g.addWidget(lbl("Özel Kod"), 0, 6); g.addWidget(self.txt_ozel_kod, 0, 7)
        g.addWidget(lbl("Yetki Kodu"), 1, 6); g.addWidget(self.txt_yetki, 1, 7)
        g.addWidget(self.chk_kilitli, 0, 8, 2, 1)
        g.setColumnStretch(9, 1)

        self.cmb_tur.currentIndexChanged.connect(lambda _i: self.tur_changed.emit(self.tur()))
        # Enter: bir sonraki alana; son alanda kalemlere
        for w in (self.txt_fis_no, self.txt_belge_no, self.txt_sube, self.txt_ozel_kod):
            w.returnPressed.connect(self.focusNextChild)
        self.txt_yetki.returnPressed.connect(self.bitti)
        for w in (self.txt_fis_no, self.txt_belge_no, self.txt_sube, self.txt_ozel_kod, self.txt_yetki):
            w.textChanged.connect(self.data_changed)
        self.dt_tarih.dateChanged.connect(lambda _d: self.data_changed.emit())
        self.chk_kilitli.toggled.connect(lambda _b: self.data_changed.emit())

    def tur(self) -> str:
        return self.cmb_tur.currentData()

    def tarih(self) -> date:
        return self.dt_tarih.date().toPyDate()

    def get_data(self) -> dict:
        return {
            "varsayilan_tur": self.tur(), "fis_no": self.txt_fis_no.text().strip(), "tarih": self.tarih(),
            "saat": self.txt_saat.text(), "belge_no": self.txt_belge_no.text().strip(),
            "sube": self.txt_sube.text().strip(), "ozel_kod": self.txt_ozel_kod.text().strip(),
            "yetki_kodu": self.txt_yetki.text().strip(), "kilitli": self.chk_kilitli.isChecked(),
        }

    def set_data(self, d: dict) -> None:
        self.cmb_tur.setCurrentIndex(max(self.cmb_tur.findData(d.get("varsayilan_tur", next(iter(self._tipler)))), 0))
        self.txt_fis_no.setText(d.get("fis_no") or "")
        t = d.get("tarih")
        if t:
            self.dt_tarih.setDate(QDate(t.year, t.month, t.day))
        self.txt_saat.setText(d.get("saat") or "")
        self.txt_belge_no.setText(d.get("belge_no") or "")
        self.txt_sube.setText(d.get("sube") or "")
        self.txt_ozel_kod.setText(d.get("ozel_kod") or "")
        self.txt_yetki.setText(d.get("yetki_kodu") or "")
        self.chk_kilitli.setChecked(bool(d.get("kilitli")))

    def set_readonly(self, ro: bool) -> None:
        for w in (self.cmb_tur, self.dt_tarih, self.txt_fis_no, self.txt_belge_no, self.txt_sube, self.txt_ozel_kod, self.txt_yetki):
            w.setEnabled(not ro)

    def clear(self) -> None:
        self.set_data({"varsayilan_tur": next(iter(self._tipler)), "tarih": date.today(), "saat": datetime.now().strftime("%H:%M:%S")})
