"""TOYA ERP - Kasa / banka hareket fişi servisi.

Fiş (`FinansFis`) satırları (`FinansHareket`) kasa ya da banka hesabına para girişi/çıkışı doğurur. Yön türden belli olur:
tahsilat / gelen havale-EFT / açılış → GİRİŞ; tediye / giden havale-EFT → ÇIKIŞ; virman → `hesap`tan çıkar, `karşı hesap`a girer.
Carili satır (tahsilat, tediye, havale, EFT) cari defterinde de karşılığını üretir (`CariHareket`, kaynak='finans'); satır
düzenlenince/gizlenince cari karşılığı da izler. Silme = gizleme (fiziksel silme yok). Açılış bakiyesi kartta değil, "açılış" satırında girilir."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, or_, select

from src.core.models import CariHareket, Customer, FinansFis, FinansHareket, FinansHesap
from src.desktop.services import money_service, numara_servisi, sayi_bicimi
from src.desktop.services.cari_hareket_service import (
    CariHareketError,
    CariHareketService,
)

#: tür -> (etiket, yön, grup, carili). Virman'da yön "cikis"tır (karşı hesaba girer).
TURLER: dict[str, tuple[str, str, str, bool]] = {
    "kasa_tahsilat": ("Kasa Tahsilat", "giris", "kasa", True),
    "kasa_tediye": ("Kasa Tediye", "cikis", "kasa", True),
    "kasa_acilis": ("Kasa Açılış", "giris", "kasa", False),
    "kasa_virman": ("Kasa Virman", "cikis", "kasa", False),
    "havale_gelen": ("Gelen Havale", "giris", "banka", True),
    "havale_giden": ("Giden Havale", "cikis", "banka", True),
    "eft_gelen": ("Gelen EFT", "giris", "banka", True),
    "eft_giden": ("Giden EFT", "cikis", "banka", True),
    "banka_virman": ("Banka Virman", "cikis", "banka", False),
    "banka_acilis": ("Banka Açılış", "giris", "banka", False),
}
GRUPLAR = {"kasa": "Kasa", "banka": "Banka"}
#: Fiş başlığındaki fiş türü listesi (grup bazında).
FIS_TIPLERI: dict[str, dict[str, str]] = {g: {k: v[0] for k, v in TURLER.items() if v[2] == g} for g in GRUPLAR}
#: Grubun kabul ettiği hesap türleri.
GRUP_HESAP_TURLERI = {"kasa": ("kasa",), "banka": ("banka", "pos", "kredi_karti")}
_TUM_HESAPLAR = ("kasa", "banka", "pos", "kredi_karti")
_FIS_ONEK = {"kasa": "K", "banka": "B"}


def virman_mi(tur: str) -> bool:
    return tur.endswith("_virman")


def cari_yonu(tur: str) -> str:
    """Carili satırın cari defterindeki karşılığı: giren para = tahsilat, çıkan para = ödeme."""
    return "tahsilat" if TURLER[tur][1] == "giris" else "odeme"


class FinansFisError(ValueError):
    """Doğrulama hatası; mesaj kullanıcıya gösterilebilir."""


@dataclass
class FinansFiltre:
    grup: str | None = None
    arama: str = ""
    hesap_id: int | None = None
    tur: str | None = None
    tarih_bas: date | None = None
    tarih_bit: date | None = None


@dataclass
class FinansOzeti:
    adet: int = 0
    giris_tl: float = 0.0
    cikis_tl: float = 0.0


class FinansFisService:
    def __init__(self, db) -> None:
        self.db = db
        self._cari = CariHareketService(db)

    # ---- yardımcılar -------------------------------------------------------
    def hesaplar(self, grup: str, sadece_aktif: bool = True) -> list[FinansHesap]:
        stmt = select(FinansHesap).where(FinansHesap.is_deleted == False, FinansHesap.tur.in_(GRUP_HESAP_TURLERI[grup]))  # noqa: E712
        if sadece_aktif:
            stmt = stmt.where(FinansHesap.aktif == True)  # noqa: E712
        return list(self.db.scalars(stmt.order_by(FinansHesap.kod)))

    def sonraki_fis_no(self, grup: str) -> str:
        """Bir sonraki boş fiş numarası (numara şablonundan; bkz. `numara_servisi`)."""
        return numara_servisi.fis_onizle(self.db, f"{grup}_fis")

    def _hesap_kontrol(self, hesap_id, izinli: tuple[str, ...], para: str, ad: str) -> FinansHesap:
        h = self.db.get(FinansHesap, hesap_id) if hesap_id else None
        if h is None or h.is_deleted:
            raise FinansFisError(f"{ad} seçilmelidir.")
        if h.tur not in izinli:
            raise FinansFisError(f"'{h.ad}' bu fiş türünde kullanılamaz ({ad} bir {' / '.join(izinli)} hesabı olmalı).")
        if h.doviz_kisitli and (h.para_birimi or "TRY").upper() != para:
            raise FinansFisError(f"'{h.ad}' hesabı yalnızca {h.para_birimi} ile işlem kabul eder (satır dövizi {para}).")
        return h

    def _kur(self, para: str, kur, tarih=None) -> float:
        if para == money_service.yerel_para(self.db):
            return 1.0
        if kur and float(kur) > 0:
            return float(kur)
        try:
            return float(money_service.kur_bul(self.db, para, tarih))
        except money_service.UnknownCurrencyError as e:
            raise FinansFisError(str(e)) from e

    # ---- satır -----------------------------------------------------------------
    def _satir_yaz(self, h: FinansHareket, v: dict, grup: str, fis: FinansFis) -> None:
        tur = v.get("tur")
        if tur not in TURLER or TURLER[tur][2] != grup:
            raise FinansFisError("Geçersiz hareket türü.")
        etiket, yon, _g, carili = TURLER[tur]
        tutar = float(v.get("tutar") or 0)
        if tutar <= 0:
            raise FinansFisError("Tutar sıfırdan büyük olmalıdır.")
        para = (v.get("para_birimi") or money_service.yerel_para(self.db)).upper()
        kur = self._kur(para, v.get("kur"), v.get("tarih") or fis.tarih)
        hesap = self._hesap_kontrol(v.get("hesap_id"), GRUP_HESAP_TURLERI[grup], para, f"{GRUPLAR[grup]} hesabı")
        karsi = None
        if virman_mi(tur):
            karsi = self._hesap_kontrol(v.get("karsi_hesap_id"), _TUM_HESAPLAR, para, "Karşı hesap")
            if karsi.id == hesap.id:
                raise FinansFisError("Virmanda çıkış ve giriş hesabı aynı olamaz.")
        cid = v.get("customer_id") if carili else None
        if cid and (self.db.get(Customer, cid) is None):
            raise FinansFisError("Cari bulunamadı.")
        h.fis_id, h.tur, h.yon = fis.id, tur, yon
        h.tarih = v.get("tarih") or fis.tarih
        h.hesap_id, h.karsi_hesap_id, h.customer_id = hesap.id, karsi.id if karsi else None, cid or None
        h.belge_no = (v.get("belge_no") or "").strip() or None
        h.aciklama = (v.get("aciklama") or "").strip() or None
        h.para_birimi, h.kur, h.tutar = para, kur, tutar
        h.tutar_tl = round(tutar * kur, sayi_bicimi.hane("tutar"))
        self._cari_karsiligi(h, hesap, grup, tur, v)

    def _cari_karsiligi(self, h: FinansHareket, hesap: FinansHesap, grup: str, tur: str, v: dict) -> None:
        """Carili satır için cari defterindeki karşılığı üretir/günceller; cari kalktıysa karşılığı gizler."""
        mevcut = self.db.get(CariHareket, h.cari_hareket_id) if h.cari_hareket_id else None
        if not h.customer_id:
            if mevcut is not None and not mevcut.is_deleted:
                mevcut.is_deleted = True
            h.cari_hareket_id = None
            return
        yeni = mevcut is None or mevcut.is_deleted
        c = CariHareket(kaynak="finans") if yeni else mevcut
        try:
            self._cari._hazirla(c, {"customer_id": h.customer_id, "tur": cari_yonu(tur), "tutar": h.tutar, "para_birimi": h.para_birimi,
                                    "kur": h.kur, "tarih": h.tarih, "belge_no": h.belge_no, "aciklama": h.aciklama})
        except CariHareketError as e:
            raise FinansFisError(str(e)) from e
        c.odeme_araci, c.hesap, c.fin_hesap_id = grup, hesap.ad, None      # hesap etkisi FinansHareket'ten gelir (çift sayım yok)
        if yeni:
            self.db.add(c)
            self.db.flush()
        else:
            c.version_id = (c.version_id or 1) + 1
        h.cari_hareket_id = c.id

    # ---- fiş ---------------------------------------------------------------------
    def fis_kaydet(self, baslik: dict, satirlar: list[dict], fis_id: int | None = None) -> FinansFis:
        grup = baslik.get("grup") or "kasa"
        if grup not in GRUPLAR:
            raise FinansFisError("Geçersiz fiş grubu.")
        if not satirlar:
            raise FinansFisError("Fişte en az bir satır olmalıdır.")
        try:
            if fis_id:
                fis = self.db.get(FinansFis, fis_id)
                if fis is None or fis.is_deleted:
                    raise FinansFisError("Fiş bulunamadı.")
                if fis.kilitli and baslik.get("kilitli", True):
                    raise FinansFisError("Fiş kilitli; değiştirmek için önce kilidi kaldırın.")
                grup = fis.grup
            else:
                fis = FinansFis(grup=grup)
            fis.fis_no = (baslik.get("fis_no") or "").strip() or self.sonraki_fis_no(grup)
            numara_servisi.fis_kullanildi(self.db, f"{grup}_fis", fis.fis_no)
            fis.tarih = baslik.get("tarih") or date.today()
            fis.saat = baslik.get("saat") or datetime.now().strftime("%H:%M:%S")
            for alan in ("belge_no", "sube", "ozel_kod", "yetki_kodu", "aciklama1", "aciklama2", "aciklama3"):
                setattr(fis, alan, (baslik.get(alan) or "").strip() or None)
            fis.varsayilan_tur = baslik.get("varsayilan_tur") or next(iter(FIS_TIPLERI[grup]))
            fis.kilitli = bool(baslik.get("kilitli"))
            if fis_id is None:
                self.db.add(fis)
            self.db.flush()
            mevcut = {h.id: h for h in self.db.scalars(
                select(FinansHareket).where(FinansHareket.fis_id == fis.id, FinansHareket.is_deleted == False))}  # noqa: E712
            kalan = set()
            for sira, v in enumerate(satirlar, start=1):
                v = dict(v)
                sid = v.pop("id", None)
                no = v.pop("_satir", None) or sira
                try:
                    if sid and sid in mevcut:
                        h = mevcut[sid]
                        kalan.add(sid)
                        h.version_id = (h.version_id or 1) + 1
                    else:
                        h = FinansHareket()
                    self._satir_yaz(h, v, grup, fis)
                    if not (sid and sid in mevcut):
                        self.db.add(h)
                    h.satir_no = no
                except (FinansFisError, CariHareketError) as e:
                    raise FinansFisError(f"Satır {no}: {e}") from e
            for sid, h in mevcut.items():
                if sid not in kalan:
                    self._gizle_satir(h)
            self.db.commit()
            return fis
        except Exception:
            self.db.rollback()
            raise

    def _gizle_satir(self, h: FinansHareket) -> None:
        h.is_deleted = True
        c = self.db.get(CariHareket, h.cari_hareket_id) if h.cari_hareket_id else None
        if c is not None:
            c.is_deleted = True

    def fis_getir(self, fis_id: int) -> tuple[FinansFis, list[FinansHareket]]:
        fis = self.db.get(FinansFis, fis_id)
        if fis is None or fis.is_deleted:
            raise FinansFisError("Fiş bulunamadı.")
        satirlar = list(self.db.scalars(select(FinansHareket).where(FinansHareket.fis_id == fis_id, FinansHareket.is_deleted == False)  # noqa: E712
                                        .order_by(FinansHareket.satir_no, FinansHareket.id)))
        return fis, satirlar

    def fis_gizle(self, fis_id: int) -> None:
        """Fişi, satırlarını ve cari karşılıklarını görünümden kaldırır (fiziksel silme yok)."""
        fis, satirlar = self.fis_getir(fis_id)
        if fis.kilitli:
            raise FinansFisError("Fiş kilitli; önce kilidi kaldırın.")
        fis.is_deleted = True
        for h in satirlar:
            self._gizle_satir(h)
        numara_servisi.fis_silindi(self.db, f"{fis.grup}_fis", fis.fis_no)   # son numaraysa geri verilir
        self.db.commit()

    # ---- okuma -------------------------------------------------------------------
    def _where(self, f: FinansFiltre):
        c = [FinansHareket.is_deleted == False]  # noqa: E712
        if f.grup:                                  # grubun türleri + bu gruptaki hesaba GİREN virmanlar
            c.append(or_(FinansHareket.tur.in_([k for k, v in TURLER.items() if v[2] == f.grup]),
                         FinansHareket.karsi_hesap_id.in_(select(FinansHesap.id).where(FinansHesap.tur.in_(GRUP_HESAP_TURLERI[f.grup])))))
        if f.hesap_id:
            c.append(or_(FinansHareket.hesap_id == f.hesap_id, FinansHareket.karsi_hesap_id == f.hesap_id))
        if f.tur:
            c.append(FinansHareket.tur == f.tur)
        if f.tarih_bas:
            c.append(FinansHareket.tarih >= f.tarih_bas)
        if f.tarih_bit:
            c.append(FinansHareket.tarih <= f.tarih_bit)
        if f.arama.strip():
            q = f"%{f.arama.strip()}%"
            c.append(or_(FinansHareket.belge_no.ilike(q), FinansHareket.aciklama.ilike(q),
                         FinansHareket.fis_id.in_(select(FinansFis.id).where(FinansFis.fis_no.ilike(q))),
                         FinansHareket.hesap_id.in_(select(FinansHesap.id).where(or_(FinansHesap.ad.ilike(q), FinansHesap.kod.ilike(q)))),
                         FinansHareket.customer_id.in_(select(Customer.id).where(or_(Customer.fullname.ilike(q), Customer.customer_code.ilike(q))))))
        return c

    def list(self, f: FinansFiltre, page: int = 1, per_page: int = 25) -> tuple[list[FinansHareket], int]:
        where = self._where(f)
        total = self.db.scalar(select(func.count()).select_from(FinansHareket).where(*where)) or 0
        stmt = (select(FinansHareket).where(*where).order_by(FinansHareket.tarih.desc(), FinansHareket.id.desc())
                .offset((max(page, 1) - 1) * per_page).limit(per_page))
        return list(self.db.scalars(stmt)), total

    def ozet(self, f: FinansFiltre) -> FinansOzeti:
        """Filtreye uyan hareketlerin TL karşılığı toplamı. Virman iç transfer olduğundan giriş/çıkışa katılmaz."""
        o = FinansOzeti()
        for h in self.db.scalars(select(FinansHareket).where(*self._where(f))):
            o.adet += 1
            if virman_mi(h.tur):
                continue
            if h.yon == "giris":
                o.giris_tl += h.tutar_tl
            else:
                o.cikis_tl += h.tutar_tl
        return o
