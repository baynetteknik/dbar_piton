"""TOYA ERP - CariDurumWidget: seçili carinin künyesi ve borç / alacak durumu.

"Bakiyeyi Tutara Aktar" düğmesi, carinin güncel TL bakiyesini (borç + / alacak −) `bakiye_aktar_requested`
sinyaliyle bildirir; tutarı yazma işi kalemler tablosundadır.

    w = CariDurumWidget(); w.set_customer({"code": "C1", "name": "ACME"}, bakiye_tl=1250.0)
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


def fmt_tl(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class CariDurumWidget(QFrame):
    bakiye_aktar_requested = pyqtSignal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CariDurum")
        self.setStyleSheet("#CariDurum { background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; }")
        self._bakiye = 0.0
        self._var = False
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(4)
        t = QLabel("CARİ DURUMU")
        t.setStyleSheet("font-size:10px; font-weight:800; color:#1e3a8a; letter-spacing:1px;")
        self.lbl_cari = QLabel("Satır seçin")
        self.lbl_cari.setStyleSheet("font-size:12px; font-weight:700; color:#0f172a;")
        self.lbl_cari.setWordWrap(True)
        self.lbl_vergi = QLabel("")
        self.lbl_vergi.setStyleSheet("font-size:10px; color:#64748b;")
        self.lbl_bakiye = QLabel("")
        self.lbl_bakiye.setStyleSheet("font-size:14px; font-weight:800; color:#475569;")
        self.btn_aktar = QPushButton("⤵ Bakiyeyi Tutara Aktar")
        self.btn_aktar.setEnabled(False)
        self.btn_aktar.setStyleSheet(
            "QPushButton { background:#2563eb; color:white; border:1px solid #1d4ed8; border-radius:6px;"
            " padding:5px 10px; font-size:11px; font-weight:700; }"
            " QPushButton:hover { background:#1d4ed8; } QPushButton:disabled { background:#e2e8f0; color:#94a3b8; border-color:#e2e8f0; }")
        self.btn_aktar.clicked.connect(lambda: self.bakiye_aktar_requested.emit(self._bakiye))
        for w in (t, self.lbl_cari, self.lbl_vergi, self.lbl_bakiye, self.btn_aktar):
            v.addWidget(w)
        v.addStretch()

    def set_customer(self, cari: dict | None, bakiye_tl: float = 0.0) -> None:
        self._var = cari is not None
        self._bakiye = bakiye_tl if cari else 0.0
        if not cari:
            self.lbl_cari.setText("Satır seçin")
            self.lbl_vergi.setText("")
            self.lbl_bakiye.setText("")
            self.btn_aktar.setEnabled(False)
            return
        self.lbl_cari.setText(f"{cari.get('code', '')}  {cari.get('name', '')}".strip())
        self.lbl_vergi.setText(" · ".join(x for x in (cari.get("tax_office"), cari.get("tax_no")) if x))
        if abs(bakiye_tl) < 0.005:
            durum, renk = "Bakiye yok", "#475569"
        elif bakiye_tl > 0:
            durum, renk = "Borçlu", "#dc2626"
        else:
            durum, renk = "Alacaklı", "#16a34a"
        self.lbl_bakiye.setText(f"{fmt_tl(abs(bakiye_tl))} TL ({durum})")
        self.lbl_bakiye.setStyleSheet(f"font-size:14px; font-weight:800; color:{renk};")
        self.btn_aktar.setEnabled(abs(bakiye_tl) >= 0.005)

    def clear(self) -> None:
        self.set_customer(None)
