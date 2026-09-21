"""TOYA ERP - StokDurumWidget: seçili stok kartının künyesi ve stok durumu (toplam ve seçili depo bakiyesi).

    w = StokDurumWidget(); w.set_urun({"code": "P1", "name": "Vida", "unit": "Adet", "min_stock": 5}, toplam=12, depo="A", depo_bakiye=7)
Kritik seviyenin (min. stok) altındaki toplam stok turuncu görünür."""

from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout


def _miktar(v: float) -> str:
    return f"{v:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".").rstrip("0").rstrip(",") or "0"


class StokDurumWidget(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("StokDurum")
        self.setStyleSheet("#StokDurum { background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(4)
        t = QLabel("STOK DURUMU")
        t.setStyleSheet("font-size:10px; font-weight:800; color:#1e3a8a; letter-spacing:1px;")
        self.lbl_urun = QLabel("Satır seçin")
        self.lbl_urun.setStyleSheet("font-size:12px; font-weight:700; color:#0f172a;")
        self.lbl_urun.setWordWrap(True)
        self.lbl_toplam = QLabel("")
        self.lbl_depo = QLabel("")
        self.lbl_fiyat = QLabel("")
        for w in (self.lbl_toplam, self.lbl_depo, self.lbl_fiyat):
            w.setStyleSheet("font-size:11px; color:#334155;")
        for w in (t, self.lbl_urun, self.lbl_toplam, self.lbl_depo, self.lbl_fiyat):
            v.addWidget(w)
        v.addStretch()

    def set_urun(self, urun: dict | None, toplam: float = 0.0, depo: str = "", depo_bakiye: float = 0.0) -> None:
        if not urun:
            self.clear()
            return
        self.lbl_urun.setText(f"{urun.get('code', '')}  {urun.get('name', '')}".strip())
        birim = urun.get("unit", "")
        kritik = toplam <= float(urun.get("min_stock") or 0) and float(urun.get("min_stock") or 0) > 0
        renk = "#ea580c" if kritik else "#16a34a" if toplam > 0 else "#dc2626"
        self.lbl_toplam.setText(f"Toplam stok: <b>{_miktar(toplam)} {birim}</b>" + (" ⚠ kritik seviye" if kritik else ""))
        self.lbl_toplam.setStyleSheet(f"font-size:12px; color:{renk};")
        self.lbl_depo.setText(f"Depo {depo}: <b>{_miktar(depo_bakiye)} {birim}</b>" if depo else "")
        pf = float(urun.get("purchase_price") or 0)
        sf = float(urun.get("price") or 0)
        self.lbl_fiyat.setText(f"Alış: {pf:,.2f}  ·  Satış: {sf:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    def clear(self) -> None:
        self.lbl_urun.setText("Satır seçin")
        for w in (self.lbl_toplam, self.lbl_depo, self.lbl_fiyat):
            w.setText("")
