"""Seçili kalemin stok durumunu (eldeki / rezerv / kullanılabilir) gösteren küçük etiket."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel
from sqlalchemy import select

from src.core.models import Product
from src.desktop.services import sayi_bicimi
from src.desktop.services.belge_hareket_service import kullanilabilir_stok


class KullanilabilirStokEtiketi(QLabel):
    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.setStyleSheet("font-size:11px;font-weight:600;color:#0f766e;")
        self.setToolTip("Kullanılabilir stok = eldeki stok − aktif sipariş rezervleri")
        self.temizle()

    def temizle(self) -> None:
        self.setText("")
        self.hide()

    def goster(self, stok_kodu: str) -> None:
        kod = (stok_kodu or "").strip()
        if self.db is None or not kod:
            return self.temizle()
        try:
            p = self.db.scalars(select(Product).where(Product.sku == kod, Product.is_deleted == False)).first()  # noqa: E712
            if p is None:
                return self.temizle()
            h = sayi_bicimi.hane("miktar")
            eldeki, kullanilabilir = float(p.stock or 0), kullanilabilir_stok(self.db, p.id)
        except Exception:
            return self.temizle()
        self.setText(f"📦 Eldeki {eldeki:,.{h}f} · Rezerv {eldeki - kullanilabilir:,.{h}f} · Kullanılabilir {kullanilabilir:,.{h}f}")
        self.show()
