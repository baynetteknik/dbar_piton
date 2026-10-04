"""TOYA ERP - StokFisKalemleriWidget: stok hareket fişi satır girişi (`FisKalemGrid` üzerine).

Her satırın türü (giriş / çıkış / transfer / sayım / açılış) ve deposu ayrıdır. Stok kodu ya da barkod yazılınca stok kartı
bulunur; yazdıkça listeler, büyüteç (F4) tam stok seçim listesini açar. Birim ve maliyet fiyatı karttan gelir. Hedef depo yalnız
transfer satırlarında açıktır. Ortak davranış (klavye akışı, para/açılır liste editörleri, sütun kaydı) `FisKalemGrid`'den gelir.

Ek sinyal: `urun_secildi(int | None)` (seçili satırın stok kartı id'si).
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from sqlalchemy import select

from src.core.models import Product, StokHareket
from src.desktop.services import sayi_bicimi
from src.desktop.services.stok_fis_service import TURLER
from src.desktop.ui.widgets.fis_kalem_grid import FisKalemGrid, KolonTanimi, fmt_num
from src.desktop.ui.widgets.lookup_cell_delegate import LookupCellDelegate

PRESET_ID = "dbgrid_stok_fis_kalem"
KOLONLAR = [
    KolonTanimi("sn", "SN", 0.03, "C", tam_ad="SIRA NO"),
    KolonTanimi("tur", "TÜR", 0.09, "L", "combo"),
    KolonTanimi("kod", "STOK KODU", 0.10, "L", "lookup"),
    KolonTanimi("ad", "STOK ADI", 0.21, "L", "lookup", nav_atla=True),
    KolonTanimi("depo", "DEPO", 0.06, "C", "combo"),
    KolonTanimi("hedef", "HEDEF", 0.06, "C", "combo", tam_ad="HEDEF DEPO"),
    KolonTanimi("miktar", "MİKTAR", 0.08, "R", "para", ondalik="miktar"),
    KolonTanimi("birim", "BİRİM", 0.05, "C", "readonly"),
    KolonTanimi("fiyat", "B.FİYAT", 0.08, "R", "para", ondalik="fiyat", tam_ad="BİRİM FİYAT"),
    KolonTanimi("tutar", "TUTAR", 0.09, "R", "readonly"),
    KolonTanimi("not", "NOT", 0.15, "L"),
]
S_SN, S_TUR, S_KOD, S_AD, S_DEPO, S_HEDEF, S_MIKTAR, S_BIRIM, S_FIYAT, S_TUTAR, S_NOT = range(11)

_TUR_ETIKET = {k: v[0] for k, v in TURLER.items()}
_TUR_ANAHTAR = {v: k for k, v in _TUR_ETIKET.items()}


def miktar_metni(v: float) -> str:
    return fmt_num(v, "miktar")


class StokFisKalemleriWidget(FisKalemGrid):
    PRESET_ID = PRESET_ID
    PRESET_AD = "Stok Fiş Kalemleri"
    KOLONLAR = KOLONLAR

    urun_secildi = pyqtSignal(object)

    def __init__(self, db_session=None, depolar: list[tuple[int, str, str]] | None = None, parent=None) -> None:
        self._depolar = depolar or []                       # [(id, kod, ad)]
        self._kod_id = {k: i for i, k, _a in self._depolar}
        self._id_kod = {i: k for i, k, _a in self._depolar}
        self._varsayilan_tur = "giris"
        self._varsayilan_depo: int | None = self._depolar[0][0] if self._depolar else None
        self._varsayilan_hedef: int | None = None
        self._katalog: list[dict] | None = None
        super().__init__(db_session, parent)
        self.satir_secildi.connect(self._emit_urun)
        QShortcut(QKeySequence("F4"), self.grid, activated=lambda: self.urun_sec(self.grid.currentRow()))

    # ---- FisKalemGrid kancaları ----------------------------------------------
    def lookup_delegate(self, key: str):
        return LookupCellDelegate(self.grid, katalog=lambda: self.katalog(), sec=lambda r, u: self.urun_yaz(r, u),
                                  liste=lambda t: self.urun_sec_liste(t), kod_kolonu=S_KOD, ipucu="Stok seçim listesi (F4)")

    def combo_secenekleri(self, key: str) -> list[str]:
        if key == "tur":
            return list(_TUR_ETIKET.values())
        kodlar = [k for _i, k, _a in self._depolar]
        return kodlar if key == "depo" else [""] + kodlar

    def varsayilan_degerler(self) -> dict[str, str]:
        transfer = self._varsayilan_tur == "transfer"
        return {"tur": _TUR_ETIKET[self._varsayilan_tur], "depo": self._id_kod.get(self._varsayilan_depo, ""),
                "hedef": self._id_kod.get(self._varsayilan_hedef, "") if transfer else ""}

    def bos_mu(self, r: int) -> bool:
        return not self.text(r, "kod") and self.sayi(r, "miktar") == 0 and not self.text(r, "not")

    def satir_bayraklari(self, r: int) -> None:
        """Hedef depo yalnız transfer satırında açık; diğer türlerde soluk ve salt okunur."""
        ro = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        transfer = _TUR_ANAHTAR.get(self.text(r, "tur")) == "transfer"
        it = self.item(r, "hedef")
        it.setFlags(ro | Qt.ItemFlag.ItemIsEditable if transfer else ro)
        it.setForeground(QBrush(QColor("#0f172a" if transfer else "#94a3b8")))

    def ekstra_baglam_eylemleri(self) -> list[tuple]:
        return [("🔎 Stok Seç (F4)", lambda: self.urun_sec(self.grid.currentRow()))]

    def set_defaults(self, tur: str | None = None, tarih: date | None = None, depo_id: int | None = None,
                     hedef_depo_id: int | None = None, **kwargs) -> None:
        """Yeni satırların başlangıç türü / deposu / vadesi (fiş başlığından gelir)."""
        if tur:
            self._varsayilan_tur = tur
        if depo_id is not None:
            self._varsayilan_depo = depo_id
        if hedef_depo_id is not None or tur:
            self._varsayilan_hedef = hedef_depo_id if hedef_depo_id is not None else self._varsayilan_hedef
        super().set_defaults(tarih=tarih)

    def hucre_degisti(self, r: int, key: str) -> None:
        if key == "tur":
            if _TUR_ANAHTAR.get(self.text(r, "tur")) != "transfer":
                self.set_text(r, "hedef", "")
            self.satir_bayraklari(r)
        elif key == "kod":
            self._kod_cozumle(r)
        elif key == "ad":
            self._ad_cozumle(r)
        if key in ("miktar", "fiyat", "kod", "tur"):
            self._hesapla(r)

    # ---- katalog -----------------------------------------------------------------
    def katalog(self) -> list[dict]:
        if self._katalog is None:
            self._katalog = []
            if self.db is not None:
                for p in self.db.scalars(select(Product).where(Product.is_deleted == False).order_by(Product.name)):  # noqa: E712
                    self._katalog.append({"id": p.id, "code": p.sku, "name": p.name or "", "barcode": p.barcode or "",
                                          "unit": p.unit or "Adet", "purchase_price": float(p.purchase_price or 0),
                                          "price": float(p.sale_price or 0), "stock": p.stock or 0,
                                          "min_stock": float(p.min_stock or 0)})
        return self._katalog

    def yenile_katalog(self) -> None:
        self._katalog = None

    def urun_bul(self, product_id: int) -> dict | None:
        return next((u for u in self.katalog() if u["id"] == product_id), None)

    # ---- ürün seçimi -------------------------------------------------------------
    def _kod_cozumle(self, r: int) -> None:
        kod = self.text(r, "kod")
        if not kod:
            self.set_kimlik(r, "kod", None)
            for k in ("ad", "birim", "fiyat"):
                self.set_text(r, k, "")
            return
        e = next((u for u in self.katalog() if u["code"].lower() == kod.lower() or (u["barcode"] and u["barcode"].lower() == kod.lower())), None)
        if e:
            self._urun_yaz(r, e)
        else:
            self.set_kimlik(r, "kod", None)
            self.set_text(r, "ad", "")
            QTimer.singleShot(0, lambda: self.urun_sec(r, ilk_arama=kod))

    def _ad_cozumle(self, r: int) -> None:
        ad = self.text(r, "ad")
        if not ad:
            self.set_kimlik(r, "kod", None)
            self.set_text(r, "kod", "")
            return
        e = next((u for u in self.katalog() if u["name"].lower() == ad.lower()), None)
        if e:
            self._urun_yaz(r, e)
            return
        pid = self.kimlik(r, "kod")
        onceki = self.urun_bul(pid) if pid else None
        self.set_text(r, "ad", onceki["name"] if onceki else "")
        QTimer.singleShot(0, lambda: self.urun_sec(r, ilk_arama=ad))

    def _urun_yaz(self, r: int, u: dict) -> None:
        self.set_text(r, "kod", u["code"])
        self.set_kimlik(r, "kod", u["id"])
        self.set_text(r, "ad", u["name"])
        self.set_text(r, "birim", u["unit"])
        if not self.sayi(r, "fiyat"):
            self.set_text(r, "fiyat", fmt_num(u["purchase_price"], "fiyat") if u["purchase_price"] else "")

    def urun_yaz(self, r: int, u: dict) -> None:
        """Seçilen stok kartını satıra yazar ve satırın türevlerini (tutar, boş satır, toplam, özet) günceller."""
        self._urun_yaz(r, u)
        self._hesapla(r)
        self._sondaki_bos_satir()
        self._emit_urun(r)
        self.totals_changed.emit()

    def urun_sec_liste(self, ilk_arama: str = "") -> dict | None:
        """Tam stok seçim listesi (büyüteç / F4); seçilen kart sözlüğünü ya da None döner."""
        if self.db is None:
            return None
        from src.desktop.ui.widgets.hareket_kalemleri_widget import StokSecimDialog
        dlg = StokSecimDialog(products=self.katalog(), parent=self)
        if ilk_arama and hasattr(dlg, "txt_search"):
            dlg.txt_search.setText(ilk_arama)
        secilen: list[dict] = []
        dlg.product_selected.connect(secilen.append)
        dlg.exec()
        return secilen[0] if secilen else None

    def urun_sec(self, r: int, ilk_arama: str = "") -> None:
        if r < 0 or r >= self.grid.rowCount():
            return
        u = self.urun_sec_liste(ilk_arama)
        if u is not None:
            self.urun_yaz(r, u)
        elif ilk_arama:
            self.set_text(r, "kod", "")

    def _hesapla(self, r: int) -> None:
        m, f = self.sayi(r, "miktar"), self.sayi(r, "fiyat")
        if m:
            self.set_text(r, "miktar", miktar_metni(m))
        self.set_text(r, "tutar", fmt_num(round(m * f, sayi_bicimi.hane("tutar"))) if m and f else "")

    def _emit_urun(self, r: int) -> None:
        pid = self.kimlik(r, "kod") if 0 <= r < self.grid.rowCount() else None
        self.urun_secildi.emit(pid)

    def secili_depo_id(self) -> int | None:
        r = self.grid.currentRow()
        return self._kod_id.get(self.text(r, "depo")) if r >= 0 else None

    def secili_urun_id(self) -> int | None:
        r = self.grid.currentRow()
        return self.kimlik(r, "kod") if r >= 0 else None

    def secili_satirlari_sil(self) -> None:
        super().secili_satirlari_sil()
        self.urun_secildi.emit(None)

    # ---- veri --------------------------------------------------------------------
    def load(self, hareketler: list[StokHareket]) -> None:
        self._busy = True
        self.grid.setRowCount(0)
        self._busy = False
        for h in hareketler:
            p = h.product
            r = self.add_row({
                "tur": _TUR_ETIKET[h.tur], "kod": p.sku, "ad": p.name or "", "depo": self._id_kod.get(h.depo_id, ""),
                "hedef": self._id_kod.get(h.hedef_depo_id, "") if h.hedef_depo_id else "", "miktar": miktar_metni(h.miktar),
                "birim": h.birim or p.unit or "Adet", "fiyat": fmt_num(h.birim_fiyat, "fiyat") if h.birim_fiyat else "",
                "tutar": fmt_num(h.tutar) if h.tutar else "", "not": h.aciklama or ""})
            self.set_kimlik(r, "tur", h.id)
            self.set_kimlik(r, "kod", h.product_id)
        self.add_row()
        self.totals_changed.emit()

    def rows(self) -> list[dict]:
        """Dolu satırlar (kaydedilecek sözlükler). `_satir` ekrandaki satır numarasıdır (hata mesajı için)."""
        out = []
        for r in range(self.grid.rowCount()):
            if self.bos_mu(r):
                continue
            out.append({
                "_satir": r + 1, "id": self.kimlik(r, "tur"), "product_id": self.kimlik(r, "kod"),
                "tur": _TUR_ANAHTAR.get(self.text(r, "tur"), "giris"), "miktar": self.sayi(r, "miktar"),
                "depo_id": self._kod_id.get(self.text(r, "depo")), "hedef_depo_id": self._kod_id.get(self.text(r, "hedef")),
                "birim": self.text(r, "birim") or None, "birim_fiyat": self.sayi(r, "fiyat"), "aciklama": self.text(r, "not"),
            })
        return out

    def totals(self) -> dict[str, tuple[float, float, float, float, float]]:
        """{birim: (giriş, çıkış, transfer, sayılan, tutar)}"""
        out: dict[str, list[float]] = {}
        for r in range(self.grid.rowCount()):
            m = self.sayi(r, "miktar")
            if not m:
                continue
            t = out.setdefault(self.text(r, "birim") or "Adet", [0.0] * 5)
            tur = _TUR_ANAHTAR.get(self.text(r, "tur"), "giris")
            t[{"giris": 0, "acilis": 0, "cikis": 1, "transfer": 2, "sayim": 3}[tur]] += m
            t[4] += self.sayi(r, "tutar")
        return {k: tuple(v) for k, v in out.items()}
