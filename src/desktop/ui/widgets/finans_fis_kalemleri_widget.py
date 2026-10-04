"""TOYA ERP - FinansFisKalemleriWidget: kasa / banka hareket fişi satır girişi (`FisKalemGrid` üzerine).

Cari fiş kalemleriyle aynı davranışı paylaşır (cari arama/büyüteç, döviz-kur-tutar hesabı, klavye akışı); farkları:
her satırın **hesabı** (kasa ya da banka) yazdıkça listelenen kod/ad hücreleriyle seçilir, yön türden belli olur
(tahsilat/gelen → giriş, tediye/giden → çıkış), carisi isteğe bağlıdır (yalnız tahsilat/tediye/havale/EFT satırında açık),
virman satırında **karşı hesap** açılır (çıkış `hesap`tan, giriş karşı hesaba). Hesap seçilince satırın dövizi hesabın
dövizine çekilir (tutar boşsa). Sütun tanımı ve ortak davranış `FisKalemGrid`'den gelir.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor

from src.core.models import FinansHareket
from src.desktop.services import finans_fis_service as fs
from src.desktop.ui.widgets.cari_fis_kalemleri_widget import CariFisKalemleriWidget
from src.desktop.ui.widgets.fis_kalem_grid import (  # noqa: F401
    KolonTanimi,
    fmt_num,
    parse_num,
)
from src.desktop.ui.widgets.lookup_cell_delegate import LookupCellDelegate

KOLONLAR = [
    KolonTanimi("sn", "SN", 0.03, "C", tam_ad="SIRA NO"),
    KolonTanimi("tur", "TÜR", 0.09, "L", "combo"),
    KolonTanimi("hkod", "HESAP KODU", 0.08, "L", "lookup"),
    KolonTanimi("had", "HESAP ADI", 0.10, "L", "lookup", nav_atla=True),
    KolonTanimi("kod", "CARİ KODU", 0.08, "L", "lookup"),
    KolonTanimi("unvan", "ÜNVAN", 0.11, "L", "lookup", nav_atla=True),
    KolonTanimi("tutar", "TUTAR", 0.08, "R", "para", ondalik="tutar"),
    KolonTanimi("doviz", "DVZ", 0.045, "C", "combo", tam_ad="DÖVİZ"),
    KolonTanimi("kur", "KUR", 0.055, "R", "para", ondalik="kur"),
    KolonTanimi("yerel", "YEREL TUTAR", 0.07, "R", "readonly"),
    KolonTanimi("not", "NOT", 0.07, "L"),
    KolonTanimi("makbuz", "MAKBUZ", 0.055, "L"),
    KolonTanimi("kkod", "KARŞI HESAP", 0.065, "L", "lookup", tam_ad="KARŞI HESAP KODU (virman)"),
    KolonTanimi("kad", "KARŞI HESAP ADI", 0.07, "L", "lookup", nav_atla=True),
]
_TERS = {"kasa_tahsilat": "kasa_tediye", "havale_gelen": "havale_giden", "eft_gelen": "eft_giden"}
_TERS.update({v: k for k, v in list(_TERS.items())})
_SOLUK, _NORMAL = QColor("#94a3b8"), QColor("#0f172a")


class FinansFisKalemleriWidget(CariFisKalemleriWidget):
    PRESET_AD = "Kasa / Banka Fiş Kalemleri"
    KOLONLAR = KOLONLAR

    def __init__(self, db_session=None, grup: str = "kasa", parent=None) -> None:
        self.grup = grup
        self.PRESET_ID = f"dbgrid_{grup}_fis_kalem"
        self._etiket = {k: v[0] for k, v in fs.TURLER.items() if v[2] == grup}
        self._anahtar = {v: k for k, v in self._etiket.items()}
        self._hesap_kat: dict[str, list[dict]] = {}
        self._varsayilan_hesap: dict | None = None
        super().__init__(db_session, parent)
        self._varsayilan_tur = next(iter(self._etiket))

    # ---- katalog -------------------------------------------------------------------
    def hesap_katalog(self, karsi: bool = False) -> list[dict]:
        anahtar = "karsi" if karsi else "hesap"
        if anahtar not in self._hesap_kat:
            lst: list[dict] = []
            if self.db is not None:
                from sqlalchemy import select

                from src.core.models import FinansHesap
                izinli = fs._TUM_HESAPLAR if karsi else fs.GRUP_HESAP_TURLERI[self.grup]
                for h in self.db.scalars(select(FinansHesap).where(FinansHesap.is_deleted == False, FinansHesap.aktif == True,  # noqa: E712
                                                                   FinansHesap.tur.in_(izinli)).order_by(FinansHesap.kod)):
                    lst.append({"id": h.id, "code": h.kod, "name": h.ad, "doviz": (h.para_birimi or self.yerel_para()).upper(),
                                "kisitli": bool(h.doviz_kisitli)})
            self._hesap_kat[anahtar] = lst
        return self._hesap_kat[anahtar]

    def hesap_liste(self, ilk_arama: str = "", karsi: bool = False) -> dict | None:
        if self.db is None:
            return None
        from src.desktop.ui.widgets.finans_hesap_widgets import FinansHesapSecimDialog
        tur = None if karsi or self.grup == "banka" else "kasa"
        dlg = FinansHesapSecimDialog(self.db, tur=tur, ilk_arama=ilk_arama, parent=self)
        dlg.exec()
        s = dlg.secilen
        return next((k for k in self.hesap_katalog(karsi) if s and k["id"] == s["id"]), None) if s else None

    def set_varsayilan_hesap(self, hesap_id: int | None) -> None:
        """Yeni satırların hesabı (kart ekranından açılınca seçili hesap; tek hesap varsa o)."""
        kat = self.hesap_katalog()
        self._varsayilan_hesap = next((h for h in kat if h["id"] == hesap_id), None) if hesap_id else (kat[0] if len(kat) == 1 else None)
        self._bos_satirlari_tazele()

    # ---- FisKalemGrid kancaları -------------------------------------------------------
    def lookup_delegate(self, key: str):
        if key in ("kod", "unvan"):
            return LookupCellDelegate(self.grid, katalog=lambda: self.katalog(), sec=lambda r, c: self.cari_yaz(r, c),
                                      liste=lambda t: self.cari_sec_liste(t), kod_kolonu=self.idx["kod"], ipucu="Cari seçim listesi (F4)")
        karsi = key in ("kkod", "kad")
        on = "k" if karsi else "h"
        return LookupCellDelegate(self.grid, katalog=lambda: self.hesap_katalog(karsi), sec=lambda r, c: self.hesap_yaz(r, c, on),
                                  liste=lambda t: self.hesap_liste(t, karsi), kod_kolonu=self.idx[f"{on}kod"], ipucu="Hesap seçim listesi (F4)")

    def combo_secenekleri(self, key: str) -> list[str]:
        return list(self._etiket.values()) if key == "tur" else self.para_kodlari()

    def varsayilan_degerler(self) -> dict[str, str]:
        v = {"tur": self._etiket.get(self._varsayilan_tur) or next(iter(self._etiket.values())), "doviz": self.yerel_para(), "kur": fmt_num(1.0, "kur")}
        if self._varsayilan_hesap:
            v.update(hkod=self._varsayilan_hesap["code"], had=self._varsayilan_hesap["name"])
            if self._varsayilan_hesap["doviz"] != self.yerel_para():
                v.update(doviz=self._varsayilan_hesap["doviz"])
        return v

    def add_row(self, degerler=None) -> int:
        r = super().add_row(degerler)
        if degerler is None and self._varsayilan_hesap:
            self.set_kimlik(r, "hkod", self._varsayilan_hesap["id"])
            if self._varsayilan_hesap["doviz"] != self.yerel_para():
                self._kur_getir(r)
        return r

    def bos_mu(self, r: int) -> bool:
        return not self.text(r, "kod") and self.sayi(r, "tutar") == 0 and not self.text(r, "not")

    def satir_bayraklari(self, r: int) -> None:
        """Cari yalnız carili türlerde, karşı hesap yalnız virmanda açık; diğerinde soluk ve salt okunur."""
        tur = self._anahtar.get(self.text(r, "tur"), "")
        carili = bool(tur) and fs.TURLER[tur][3]
        virman = bool(tur) and fs.virman_mi(tur)
        ro = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        for keys, acik in ((("kod", "unvan"), carili), (("kkod", "kad"), virman)):
            for k in keys:
                it = self.item(r, k)
                it.setFlags(ro | Qt.ItemFlag.ItemIsEditable if acik else ro)
                it.setForeground(QBrush(_NORMAL if acik else _SOLUK))

    def ekstra_baglam_eylemleri(self) -> list[tuple]:
        return [("🔎 Cari Seç (F4)", lambda: self.cari_sec(self.grid.currentRow())),
                ("🏦 Hesap Seç", lambda: self.hesap_sec(self.grid.currentRow()))]

    def hucre_degisti(self, r: int, key: str) -> None:
        if key == "tur":
            tur = self._anahtar.get(self.text(r, "tur"), "")
            if tur and not fs.TURLER[tur][3]:
                self.set_text(r, "kod", "")
                self.set_text(r, "unvan", "")
                self.set_kimlik(r, "kod", None)
            if tur and not fs.virman_mi(tur):
                for k in ("kkod", "kad"):
                    self.set_text(r, k, "")
                self.set_kimlik(r, "kkod", None)
            self.satir_bayraklari(r)
        elif key == "kod":
            self._kod_cozumle(r)
        elif key == "unvan":
            self._unvan_cozumle(r)
        elif key in ("hkod", "had", "kkod", "kad"):
            self._hesap_cozumle(r, key)
        elif key == "doviz":
            self._kur_getir(r)
        if key in ("tutar", "kur", "doviz", "kod"):
            self._hesapla(r)

    # ---- hesap seçimi --------------------------------------------------------------------
    def _hesap_cozumle(self, r: int, key: str) -> None:
        karsi = key in ("kkod", "kad")
        on = "k" if karsi else "h"
        kodk, adk = f"{on}kod", "kad" if karsi else "had"
        yazilan = self.text(r, key)
        if not yazilan:
            self.set_kimlik(r, kodk, None)
            self.set_text(r, kodk if key == adk else adk, "")
            return
        kat = self.hesap_katalog(karsi)
        alan = "code" if key == kodk else "name"
        eslesen = next((h for h in kat if h[alan].lower() == yazilan.lower()), None)
        if eslesen:
            self.hesap_yaz(r, eslesen, on)
            return
        onceki = next((h for h in kat if h["id"] == self.kimlik(r, kodk)), None)
        self.set_text(r, kodk, onceki["code"] if onceki else "")
        self.set_text(r, adk, onceki["name"] if onceki else "")
        QTimer.singleShot(0, lambda: self.hesap_sec(r, karsi=karsi, ilk_arama=yazilan))

    def hesap_yaz(self, r: int, h: dict, on: str = "h") -> None:
        kodk, adk = f"{on}kod", "kad" if on == "k" else "had"
        self.set_text(r, kodk, h["code"])
        self.set_text(r, adk, h["name"])
        self.set_kimlik(r, kodk, h["id"])
        if on == "h" and self.sayi(r, "tutar") == 0 and self.text(r, "doviz") != h["doviz"]:
            self.set_text(r, "doviz", h["doviz"])                    # hesabın dövizine çek (tutar girilmeden)
            self._kur_getir(r)
        self._sondaki_bos_satir()
        self.totals_changed.emit()

    def hesap_sec(self, r: int, karsi: bool = False, ilk_arama: str = "") -> None:
        if r < 0 or r >= self.grid.rowCount():
            return
        h = self.hesap_liste(ilk_arama, karsi)
        if h is not None:
            self.hesap_yaz(r, h, "k" if karsi else "h")

    def _on_double_click(self, r: int, c: int) -> None:      # hücreler yazdıkça listeler; liste büyüteç / F4 ile açılır
        return

    def _f4(self) -> None:
        r, c = self.grid.currentRow(), self.grid.currentColumn()
        if c in (self.idx["hkod"], self.idx["had"]):
            self.hesap_sec(r)
        elif c in (self.idx["kkod"], self.idx["kad"]):
            self.hesap_sec(r, karsi=True)
        else:
            self.cari_sec(r)

    # ---- cari durumu: bakiyeyi tutara aktar -------------------------------------------------
    def bakiyeyi_tutara_aktar(self, bakiye_tl: float) -> None:
        """Seçili satırın tutarını carinin |bakiye| değerine ayarlar; tür bakiyeyi kapatan yöne çevrilir
        (bakiye borç → tahsilat/gelen, alacak → tediye/giden)."""
        r = self.grid.currentRow()
        if r < 0 or abs(bakiye_tl) < 0.005 or not self.text(r, "doviz"):
            return
        tur = self._anahtar.get(self.text(r, "tur"), "")
        if tur in _TERS:
            giris = fs.TURLER[tur][1] == "giris"
            if giris != (bakiye_tl > 0):
                self.set_text(r, "tur", self._etiket[_TERS[tur]])
        kur = self.sayi(r, "kur") or 1.0
        self.set_text(r, "tutar", fmt_num(abs(bakiye_tl) / kur))
        self._hesapla(r)
        self._sondaki_bos_satir()
        self.totals_changed.emit()

    # ---- yükleme / okuma --------------------------------------------------------------------
    def load(self, satirlar: list[FinansHareket]) -> None:
        self._busy = True
        self.grid.setRowCount(0)
        self._busy = False
        for h in satirlar:
            c = h.customer
            d = {"tur": self._etiket.get(h.tur, h.tur), "hkod": h.hesap.kod, "had": h.hesap.ad,
                 "kod": (c.customer_code or f"CAR-{c.id}") if c else "", "unvan": c.fullname if c else "",
                 "tutar": fmt_num(h.tutar), "doviz": h.para_birimi, "kur": fmt_num(h.kur, "kur"), "yerel": fmt_num(h.tutar_tl),
                 "not": h.aciklama or "", "makbuz": h.belge_no or "",
                 "kkod": h.karsi_hesap.kod if h.karsi_hesap else "", "kad": h.karsi_hesap.ad if h.karsi_hesap else ""}
            r = self.add_row(d)
            self.set_kimlik(r, "tur", h.id)
            self.set_kimlik(r, "hkod", h.hesap_id)
            self.set_kimlik(r, "kod", h.customer_id)
            self.set_kimlik(r, "kkod", h.karsi_hesap_id)
        self.add_row()
        self.totals_changed.emit()

    def rows(self) -> list[dict]:
        out = []
        for r in range(self.grid.rowCount()):
            if self.bos_mu(r):
                continue
            out.append({
                "_satir": r + 1, "id": self.kimlik(r, "tur"), "tur": self._anahtar.get(self.text(r, "tur"), next(iter(self._etiket))),
                "hesap_id": self.kimlik(r, "hkod"), "karsi_hesap_id": self.kimlik(r, "kkod"), "customer_id": self.kimlik(r, "kod"),
                "tutar": self.sayi(r, "tutar"), "para_birimi": self.text(r, "doviz") or self.yerel_para(), "kur": self.sayi(r, "kur") or 1.0,
                "aciklama": self.text(r, "not"), "belge_no": self.text(r, "makbuz")})
        return out

    def totals(self) -> dict[str, tuple[float, float, float, float]]:
        """{döviz: (giriş, çıkış, yerel giriş, yerel çıkış)}; virman hem çıkış hem giriş sayılır (net 0)."""
        out: dict[str, list[float]] = {}
        for r in range(self.grid.rowCount()):
            tutar = self.sayi(r, "tutar")
            if not tutar:
                continue
            tur = self._anahtar.get(self.text(r, "tur"), next(iter(self._etiket)))
            t = out.setdefault(self.text(r, "doviz") or self.yerel_para(), [0.0, 0.0, 0.0, 0.0])
            yerel = self.sayi(r, "yerel")
            if fs.virman_mi(tur):
                t[0] += tutar
                t[1] += tutar
                t[2] += yerel
                t[3] += yerel
            elif fs.TURLER[tur][1] == "giris":
                t[0] += tutar
                t[2] += yerel
            else:
                t[1] += tutar
                t[3] += yerel
        return {k: tuple(v) for k, v in out.items()}
