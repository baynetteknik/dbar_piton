"""TOYA ERP - StokFisBaslikWidget: stok hareket fişinin başlığı (cari fiş başlığına depo alanları eklenmiş hâli).

Fiş türü, fiş no, tarih, saat, belge no, özel kod, yetki kodu, kilitli + **Depo** ve **Hedef Depo** (transfer için).
`get_data()` ek olarak `depo_id` / `hedef_depo_id` döndürür. Şube alanı stokta kullanılmaz (gizlenir)."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QLabel

from src.desktop.services.stok_fis_service import FIS_TIPLERI
from src.desktop.ui.widgets.cari_fis_baslik_widget import _LBL, CariFisBaslikWidget


class StokFisBaslikWidget(CariFisBaslikWidget):
    depo_changed = pyqtSignal()

    def __init__(self, depolar: list[tuple[int, str, str]], parent=None) -> None:
        """`depolar`: [(id, kod, ad), ...]"""
        super().__init__(parent, tipler=FIS_TIPLERI)
        self._depolar = depolar
        self.txt_sube.hide()
        for i in range(self.layout().count()):
            w = self.layout().itemAt(i).widget()
            if isinstance(w, QLabel) and w.text() == "Şube":
                w.hide()
        g = self.layout()
        self.cmb_depo, self.cmb_hedef = QComboBox(), QComboBox()
        for cmb in (self.cmb_depo, self.cmb_hedef):
            cmb.setStyleSheet("combobox-popup: 0;")
        for did, kod, ad in depolar:
            self.cmb_depo.addItem(f"{kod} — {ad}", did)
        self.cmb_hedef.addItem("----", None)
        for did, kod, ad in depolar:
            self.cmb_hedef.addItem(f"{kod} — {ad}", did)
        l1, l2 = QLabel("Depo"), QLabel("Hedef Depo")
        for x in (l1, l2):
            x.setStyleSheet(_LBL)
        g.addWidget(l1, 0, 9); g.addWidget(self.cmb_depo, 0, 10)
        g.addWidget(l2, 1, 9); g.addWidget(self.cmb_hedef, 1, 10)
        g.setColumnStretch(9, 0)
        g.setColumnStretch(11, 1)
        self.cmb_depo.currentIndexChanged.connect(lambda _i: (self.depo_changed.emit(), self.data_changed.emit()))
        self.cmb_hedef.currentIndexChanged.connect(lambda _i: (self.depo_changed.emit(), self.data_changed.emit()))

    def get_data(self) -> dict:
        d = super().get_data()
        d["depo_id"] = self.cmb_depo.currentData()
        d["hedef_depo_id"] = self.cmb_hedef.currentData()
        return d

    def set_data(self, d: dict) -> None:
        super().set_data(d)
        if hasattr(self, "cmb_depo"):
            self.cmb_depo.setCurrentIndex(max(self.cmb_depo.findData(d.get("depo_id")), 0))
            self.cmb_hedef.setCurrentIndex(max(self.cmb_hedef.findData(d.get("hedef_depo_id")), 0))

    def depo_kodu(self, depo_id) -> str:
        return next((k for i, k, _a in self._depolar if i == depo_id), "")

    def set_readonly(self, ro: bool) -> None:
        super().set_readonly(ro)
        self.cmb_depo.setEnabled(not ro)
        self.cmb_hedef.setEnabled(not ro)
