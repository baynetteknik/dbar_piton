"""TOYA ERP - CariFisKalemleriWidget: cari hesap fişi satır girişi (`FisKalemGrid` üzerine).

Her satırın cari, tür ve dövizi ayrıdır; yön türden belli olur (tahsilat/cari alacak → alacak, tediye/cari borç → borç).
Ödeme aracı "----" iken yalnızca cari hareketi girilir, kasa/banka etkilenmez. Araç Kasa / Banka / Kredi Kartı / POS
seçilirse Hesap, cari seçimi gibi bir liste ile seçilir (yalnız tahsilat ve tediye satırlarında).
Ortak davranış (klavye akışı, para/tarih/açılır liste editörleri, sütun kaydı) `FisKalemGrid`'den gelir.

Ek sinyal: `cari_selected(int | None)` (seçili satırın cari id'si).
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from sqlalchemy import select

from src.core.models import CariHareket, Currency, Customer
from src.desktop.services import money_service, sayi_bicimi
from src.desktop.services.cari_hareket_service import (
    FIS_SATIR_TURLERI,
    ODEME_ARACLARI,
    TURLER,
    arac_etiket,
)
from src.desktop.ui.widgets.cari_cell_delegate import CariCellDelegate
from src.desktop.ui.widgets.fis_kalem_grid import (  # noqa: F401
    FisKalemGrid,
    KolonTanimi,
    fmt_num,
    parse_date,
    parse_num,
)

PRESET_ID = "dbgrid_cari_fis_kalem"
ARAC_YOK = "----"                       # kasa/banka etkilenmez; yalnızca cari hareketi

KOLONLAR = [
    KolonTanimi("sn", "SN", 0.03, "C", tam_ad="SIRA NO"),
    KolonTanimi("tur", "TÜR", 0.09, "L", "combo"),
    KolonTanimi("kod", "CARİ KODU", 0.09, "L", "lookup"),
    KolonTanimi("unvan", "ÜNVAN", 0.14, "L", "lookup", nav_atla=True),
    KolonTanimi("not", "NOT", 0.11, "L"),
    KolonTanimi("tutar", "TUTAR", 0.08, "R", "para", ondalik="tutar"),
    KolonTanimi("doviz", "DVZ", 0.05, "C", "combo", tam_ad="DÖVİZ"),
    KolonTanimi("kur", "KUR", 0.06, "R", "para", ondalik="kur"),
    KolonTanimi("yerel", "YEREL TUTAR", 0.09, "R", "readonly"),
    KolonTanimi("vade", "VADE", 0.07, "C", "tarih"),
    KolonTanimi("makbuz", "MAKBUZ", 0.06, "L"),
    KolonTanimi("arac", "ARAÇ", 0.06, "L", "combo"),
    KolonTanimi("hesap", "HESAP", 0.07, "L", "readonly"),
]
COLS = [k.baslik for k in KOLONLAR]
C_SIRA, C_TUR, C_KOD, C_UNVAN, C_NOT, C_TUTAR, C_DOVIZ, C_KUR, C_YEREL, C_VADE, C_MAKBUZ, C_ARAC, C_HESAP = range(13)

_TUR_ETIKET = {k: v[0] for k, v in TURLER.items()}
_TUR_ANAHTAR = {v: k for k, v in _TUR_ETIKET.items()}
_ARAC_ANAHTAR = {v: k for k, v in ODEME_ARACLARI.items()}
_ODEME_TURLERI = ("tahsilat", "odeme")
_YON_ROLE = Qt.ItemDataRole.UserRole + 1


class CariFisKalemleriWidget(FisKalemGrid):
    PRESET_ID = PRESET_ID
    PRESET_AD = "Cari Fiş Kalemleri"
    KOLONLAR = KOLONLAR

    cari_selected = pyqtSignal(object)

    def __init__(self, db_session=None, parent=None) -> None:
        self._varsayilan_tur = "tahsilat"
        self._katalog: list[dict] | None = None
        self._para_kodlari: list[str] | None = None
        super().__init__(db_session, parent)
        self.satir_secildi.connect(self._emit_cari)
        self.grid.cellDoubleClicked.connect(self._on_double_click)
        QShortcut(QKeySequence("F4"), self.grid, activated=self._f4)

    # ---- FisKalemGrid kancaları ----------------------------------------------
    def lookup_delegate(self, key: str):
        return CariCellDelegate(self, self.grid)                 # yazdıkça listeler + büyüteç

    def combo_secenekleri(self, key: str) -> list[str]:
        if key == "tur":
            return [_TUR_ETIKET[k] for k in FIS_SATIR_TURLERI]
        if key == "doviz":
            return self.para_kodlari()
        return [ARAC_YOK] + list(ODEME_ARACLARI.values())

    def varsayilan_degerler(self) -> dict[str, str]:
        return {"tur": _TUR_ETIKET[self._varsayilan_tur], "doviz": self.yerel_para(), "kur": fmt_num(1.0, "kur"),
                "vade": self._tarih.strftime("%d.%m.%Y"), "arac": ARAC_YOK}

    def bos_mu(self, r: int) -> bool:
        return not self.text(r, "kod") and self.sayi(r, "tutar") == 0 and not self.text(r, "not")

    def satir_bayraklari(self, r: int) -> None:
        """Araç yalnız tahsilat ve tediyede açık; diğer türlerde soluk ve salt okunur."""
        ro = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        odeme = _TUR_ANAHTAR.get(self.text(r, "tur")) in _ODEME_TURLERI
        arac_it = self.item(r, "arac")
        arac_it.setFlags(ro | Qt.ItemFlag.ItemIsEditable if odeme else ro)
        arac_it.setForeground(QBrush(QColor("#0f172a" if odeme else "#94a3b8")))

    def ekstra_baglam_eylemleri(self) -> list[tuple]:
        return [("🔎 Cari Seç (F4)", lambda: self.cari_sec(self.grid.currentRow())),
                ("🏦 Hesap Seç", lambda: self.hesap_sec(self.grid.currentRow()))]

    def set_defaults(self, tur: str | None = None, tarih: date | None = None, **kwargs) -> None:
        """Yeni satırların başlangıç türü ve vadesi (fiş başlığından gelir)."""
        if tur:
            self._varsayilan_tur = tur
        super().set_defaults(tarih=tarih)

    def hucre_degisti(self, r: int, key: str) -> None:
        hesap_ac = False
        if key == "tur":
            if _TUR_ANAHTAR.get(self.text(r, "tur")) not in _ODEME_TURLERI:
                self._hesabi_temizle(r, araci_da=True)
            self.satir_bayraklari(r)
        elif key == "kod":
            self._kod_cozumle(r)
        elif key == "unvan":
            self._unvan_cozumle(r)
        elif key == "doviz":
            self._kur_getir(r)
        elif key == "arac":
            self._hesabi_temizle(r)
            hesap_ac = self.text(r, "arac") != ARAC_YOK
        if key in ("tutar", "kur", "doviz", "kod"):
            self._hesapla(r)
        if key == "vade" and self.text(r, "vade") and parse_date(self.text(r, "vade")) is None:
            self.set_text(r, "vade", self._tarih.strftime("%d.%m.%Y"))
            self.message.emit("Vade tarihi gg.aa.yyyy biçiminde olmalıdır.")
        if hesap_ac:
            self.grid.suspend_navigation()                       # hesap listesi kapanana dek klavye akışı bekler
            QTimer.singleShot(0, lambda: self.hesap_sec(r, arac_iptalinde_sifirla=True))

    # ---- katalog / seçenekler ---------------------------------------------
    def yerel_para(self) -> str:
        """Şirketin çalışma (yerel) para birimi; ilk kullanımda okunur (bkz. `money_service.yerel_para`)."""
        k = getattr(self, "_yerel_kod", None)
        if k is None:
            k = self._yerel_kod = money_service.yerel_para(self.db) if self.db is not None else "TRY"
        return k

    def para_kodlari(self) -> list[str]:
        if self._para_kodlari is None:
            kodlar = [self.yerel_para()]
            if self.db is not None:
                for c in self.db.scalars(select(Currency).where(Currency.is_deleted == False, Currency.is_active == True)):  # noqa: E712
                    if c.code.upper() not in kodlar:
                        kodlar.append(c.code.upper())
            self._para_kodlari = kodlar
        return self._para_kodlari

    def katalog(self) -> list[dict]:
        if self._katalog is None:
            self._katalog = []
            if self.db is not None:
                for c in self.db.scalars(select(Customer).where(Customer.is_deleted == False).order_by(Customer.fullname)):  # noqa: E712
                    self._katalog.append({"id": c.id, "code": c.customer_code or f"CAR-{c.id}", "name": c.fullname or "",
                                          "tax_office": c.tax_office or "", "tax_no": c.tax_number or "", "city": ""})
        return self._katalog

    def cari_bul(self, customer_id: int) -> dict | None:
        return next((c for c in self.katalog() if c["id"] == customer_id), None)

    # ---- cari / hesap seçimi -----------------------------------------------
    def _hesabi_temizle(self, r: int, araci_da: bool = False) -> None:
        self.set_text(r, "hesap", "")
        self.set_kimlik(r, "hesap", None)
        if araci_da:
            self.set_text(r, "arac", ARAC_YOK)

    def _kod_cozumle(self, r: int) -> None:
        kod = self.text(r, "kod")
        if not kod:
            self.set_kimlik(r, "kod", None)
            self.set_text(r, "unvan", "")
            return
        eslesen = next((c for c in self.katalog() if c["code"].lower() == kod.lower()), None)
        if eslesen:
            self._cari_yaz(r, eslesen)
        else:
            self.set_kimlik(r, "kod", None)
            self.set_text(r, "unvan", "")
            QTimer.singleShot(0, lambda: self.cari_sec(r, ilk_arama=kod))

    def _cari_yaz(self, r: int, cari: dict) -> None:
        self.set_text(r, "kod", cari["code"])
        self.set_kimlik(r, "kod", cari["id"])
        self.set_text(r, "unvan", cari["name"])

    def cari_yaz(self, r: int, cari: dict) -> None:
        """Seçilen cariyi satıra yazar ve satırın türevlerini (boş satır, toplam, cari durumu) günceller."""
        self._cari_yaz(r, cari)
        self._sondaki_bos_satir()
        self._emit_cari(r)
        self.totals_changed.emit()

    def _unvan_cozumle(self, r: int) -> None:
        """Ünvan hücresine yazılan tam ad bir cariyle eşleşirse o cari seçilir; değilse eski değere dönülür ve liste açılır."""
        ad = self.text(r, "unvan")
        if not ad:
            self.set_kimlik(r, "kod", None)
            self.set_text(r, "kod", "")
            return
        eslesen = next((c for c in self.katalog() if c["name"].lower() == ad.lower()), None)
        if eslesen:
            self._cari_yaz(r, eslesen)
            return
        cid = self.kimlik(r, "kod")
        onceki = self.cari_bul(cid) if cid else None
        self.set_text(r, "unvan", onceki["name"] if onceki else "")
        QTimer.singleShot(0, lambda: self.cari_sec(r, ilk_arama=ad))

    def cari_sec_liste(self, ilk_arama: str = "") -> dict | None:
        """Tam cari seçim listesi (büyüteç / F4); seçilen cari sözlüğünü ya da None döner."""
        if self.db is None:
            return None
        from src.desktop.ui.widgets.cari_kunye_widget import CariSecimDialog
        dlg = CariSecimDialog(customers=self.katalog(), db_session=self.db, parent=self)
        if ilk_arama:
            dlg.txt_search.setText(ilk_arama)
        secilen: list[dict] = []
        dlg.customer_selected.connect(secilen.append)
        dlg.exec()
        return secilen[0] if secilen else None

    def cari_sec(self, r: int, ilk_arama: str = "") -> None:
        if r < 0 or r >= self.grid.rowCount():
            return
        cari = self.cari_sec_liste(ilk_arama)
        if cari is not None:
            self.cari_yaz(r, cari)
        elif ilk_arama:
            self.set_text(r, "kod", "")

    def hesap_sec(self, r: int, arac_iptalinde_sifirla: bool = False) -> None:
        """Satırın ödeme aracına uygun finans hesabını cari seçimi gibi bir listeden seçtirir."""
        if r < 0 or r >= self.grid.rowCount() or self.db is None:
            return
        arac = _ARAC_ANAHTAR.get(self.text(r, "arac"))
        if not arac:
            self.message.emit("Hesap seçmek için önce ödeme aracını (Kasa / Banka / Kredi Kartı / POS) seçin.")
            return
        from src.desktop.ui.widgets.finans_hesap_widgets import FinansHesapSecimDialog
        dlg = FinansHesapSecimDialog(self.db, tur=arac, parent=self)
        dlg.exec()
        try:
            if dlg.secilen:
                self.set_text(r, "hesap", dlg.secilen["ad"])
                self.set_kimlik(r, "hesap", dlg.secilen["id"])
            elif arac_iptalinde_sifirla and not self.kimlik(r, "hesap"):
                self.set_text(r, "arac", ARAC_YOK)      # hesap seçilmedi: yalnızca cari hareketi
        finally:
            self.grid.resume_navigation()

    def _on_double_click(self, r: int, c: int) -> None:
        if c == C_HESAP:                 # cari hücreleri çift tıkla yazılır (yazdıkça listeler); liste büyüteç / F4 ile açılır
            self.hesap_sec(r)

    def _f4(self) -> None:
        r, c = self.grid.currentRow(), self.grid.currentColumn()
        self.hesap_sec(r) if c == C_HESAP else self.cari_sec(r)

    # ---- kur / tutar ---------------------------------------------------------
    def _kur_getir(self, r: int) -> None:
        para = self.text(r, "doviz") or self.yerel_para()
        try:
            kur = money_service.kur_bul(self.db, para, self._tarih) if self.db is not None else 1.0          # fiş tarihinin kuru
        except money_service.UnknownCurrencyError:
            kur = 0.0
            self.message.emit(f"{para} için kur tanımlı değil; kuru elle girin.")
        self.set_text(r, "kur", fmt_num(kur, "kur"))

    def _hesapla(self, r: int) -> None:
        tutar, kur = self.sayi(r, "tutar"), self.sayi(r, "kur")
        if self.text(r, "doviz") in ("", self.yerel_para()):
            kur = 1.0
        self.set_text(r, "kur", fmt_num(kur, "kur"))
        if tutar:
            self.set_text(r, "tutar", fmt_num(tutar))
        self.set_text(r, "yerel", fmt_num(round(tutar * kur, sayi_bicimi.hane("tutar"))) if tutar else "")

    def _emit_cari(self, r: int) -> None:
        cid = self.kimlik(r, "kod") if 0 <= r < self.grid.rowCount() else None
        self.cari_selected.emit(cid)

    # ---- dışa açılan işlemler ---------------------------------------------
    def secili_cari_id(self) -> int | None:
        r = self.grid.currentRow()
        return self.kimlik(r, "kod") if r >= 0 else None

    def bakiyeyi_tutara_aktar(self, bakiye_tl: float) -> None:
        """Seçili satırın tutarını carinin |bakiye| değerine (satırın dövizinde) ayarlar. Satır tahsilat/tediye ise
        tür bakiyeyi kapatan yöne çevrilir: bakiye borç → tahsilat, alacak → tediye."""
        r = self.grid.currentRow()
        if r < 0 or abs(bakiye_tl) < 0.005 or not self.text(r, "doviz"):
            return
        kur = self.sayi(r, "kur") or 1.0
        if _TUR_ANAHTAR.get(self.text(r, "tur")) in _ODEME_TURLERI:
            self.set_text(r, "tur", _TUR_ETIKET["tahsilat" if bakiye_tl > 0 else "odeme"])
        self.set_text(r, "tutar", fmt_num(abs(bakiye_tl) / kur))
        self._hesapla(r)
        self._sondaki_bos_satir()
        self.totals_changed.emit()

    def secili_satirlari_sil(self) -> None:
        super().secili_satirlari_sil()
        self.cari_selected.emit(None)

    def load(self, satirlar: list[CariHareket]) -> None:
        self._busy = True
        self.grid.setRowCount(0)
        self._busy = False
        for h in satirlar:
            c = h.customer
            r = self.add_row({
                "tur": _TUR_ETIKET[h.tur], "kod": c.customer_code or f"CAR-{c.id}", "unvan": c.fullname,
                "not": h.aciklama or "", "tutar": fmt_num(h.tutar), "doviz": h.para_birimi, "kur": fmt_num(h.kur, "kur"),
                "yerel": fmt_num(h.tutar_tl), "vade": h.vade.strftime("%d.%m.%Y") if h.vade else "",
                "makbuz": h.belge_no or "", "arac": arac_etiket(h.odeme_araci) or ARAC_YOK, "hesap": h.hesap or ""})
            self.set_kimlik(r, "tur", h.id)
            self.set_kimlik(r, "kod", h.customer_id)
            if TURLER[h.tur][1] is None:
                self._busy = True
                self.item(r, "tur").setData(h.yon, _YON_ROLE)      # yalnız eski döviz cinsli kayıtlar
                self._busy = False
            if h.fin_hesap_id:
                self.set_kimlik(r, "hesap", h.fin_hesap_id)
        self.add_row()
        self.totals_changed.emit()

    def rows(self) -> list[dict]:
        """Dolu satırlar (kaydedilecek sözlükler). `_satir` ekrandaki satır numarasıdır (hata mesajı için)."""
        out = []
        for r in range(self.grid.rowCount()):
            if self.bos_mu(r):
                continue
            tur = _TUR_ANAHTAR.get(self.text(r, "tur"), "tahsilat")
            d = {
                "_satir": r + 1, "id": self.kimlik(r, "tur"), "customer_id": self.kimlik(r, "kod"), "tur": tur,
                "tutar": self.sayi(r, "tutar"), "para_birimi": self.text(r, "doviz") or self.yerel_para(),
                "kur": self.sayi(r, "kur") or 1.0, "aciklama": self.text(r, "not"),
                "vade": parse_date(self.text(r, "vade")), "belge_no": self.text(r, "makbuz"),
                "odeme_araci": _ARAC_ANAHTAR.get(self.text(r, "arac")), "fin_hesap_id": self.kimlik(r, "hesap"),
            }
            if TURLER[tur][1] is None:
                d["yon"] = self.item(r, "tur").data(_YON_ROLE) or "borc"
            out.append(d)
        return out

    def totals(self) -> dict[str, tuple[float, float, float, float]]:
        """{döviz: (borç, alacak, yerel borç, yerel alacak)}"""
        out: dict[str, list[float]] = {}
        for r in range(self.grid.rowCount()):
            tutar = self.sayi(r, "tutar")
            if not tutar:
                continue
            tur = _TUR_ANAHTAR.get(self.text(r, "tur"), "tahsilat")
            yon = TURLER[tur][1] or self.item(r, "tur").data(_YON_ROLE) or "borc"
            t = out.setdefault(self.text(r, "doviz") or self.yerel_para(), [0.0, 0.0, 0.0, 0.0])
            i = 0 if yon == "borc" else 1
            t[i] += tutar
            t[i + 2] += self.sayi(r, "yerel")
        return {k: tuple(v) for k, v in out.items()}
