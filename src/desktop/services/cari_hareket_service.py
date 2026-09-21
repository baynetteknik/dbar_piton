"""TOYA ERP - Cari hareket defteri servisi.

Bakiye = borç − alacak (TL karşılığı). Silme yalnızca görünümden kaldırır (is_deleted)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, or_, select

from src.core.models import CariFis, CariHareket, Customer, FinansHesap
from src.desktop.services import money_service

# tür kodu -> (etiket, yön). "doviz" yönü kayıtta kullanıcı tarafından seçilir.
TURLER: dict[str, tuple[str, str | None]] = {
    "tahsilat": ("Tahsilat", "alacak"),
    "odeme": ("Ödeme (Tediye)", "borc"),
    "borc_dekontu": ("Cari Borç", "borc"),
    "alacak_dekontu": ("Cari Alacak", "alacak"),
    "virman_borc": ("Virman Borç", "borc"),
    "virman_alacak": ("Virman Alacak", "alacak"),
    "acilis_borc": ("Açılış Borç", "borc"),
    "acilis_alacak": ("Açılış Alacak", "alacak"),
    "doviz": ("Döviz Cinsli Hareket", None),     # eski kayıtlar; fişte döviz satır bazındadır, yeni satırda seçilmez
}
#: Fiş satırında seçilebilen türler (döviz cinsli tür artık satırın dövizi ile karşılanır).
FIS_SATIR_TURLERI: list[str] = [k for k in TURLER if k != "doviz"]
#: Fiş başlığındaki fiş türü -> yeni satırın başlangıç türü.
FIS_TIPLERI: dict[str, str] = {
    "tahsilat": "Tahsilat Fişi", "odeme": "Tediye Fişi", "borc_dekontu": "Cari Borç Fişi",
    "alacak_dekontu": "Cari Alacak Fişi", "virman_borc": "Virman Fişi", "acilis_borc": "Açılış Fişi",
}
#: Ödeme aracı = kasa/banka etkisi; boş ("----") ise yalnızca cari hareketi girilir.
ODEME_ARACLARI: dict[str, str] = {"kasa": "Kasa", "banka": "Banka", "kredi_karti": "Kredi Kartı", "pos": "POS"}
_ARAC_ESKI = {"nakit": "Nakit", "cek": "Çek", "senet": "Senet"}      # eski kayıtların gösterimi için


def arac_etiket(kod: str | None) -> str:
    return ODEME_ARACLARI.get(kod or "") or _ARAC_ESKI.get(kod or "", "")
YONLER = {"borc": "Borç", "alacak": "Alacak"}


class CariHareketError(ValueError):
    """Doğrulama hatası; mesaj kullanıcıya gösterilebilir."""


@dataclass
class HareketFiltre:
    arama: str = ""
    customer_id: int | None = None
    tur: str | None = None
    para_birimi: str | None = None
    tarih_bas: date | None = None
    tarih_bit: date | None = None
    haric_fis_id: int | None = None      # bu fişin satırları hesaba katılmaz (fişi düzenlerken cari durumu için)


@dataclass
class HareketOzeti:
    adet: int = 0
    borc: float = 0.0
    alacak: float = 0.0

    @property
    def bakiye(self) -> float:
        return self.borc - self.alacak


class CariHareketService:
    def __init__(self, db) -> None:
        self.db = db

    # ---- yazma -------------------------------------------------------------
    def _hazirla(self, h: CariHareket, v: dict) -> None:
        tur = v.get("tur", h.tur)
        if tur not in TURLER:
            raise CariHareketError("Geçersiz hareket türü.")
        cid = v.get("customer_id", h.customer_id)
        if not cid or self.db.get(Customer, cid) is None:
            raise CariHareketError("Cari seçilmelidir.")
        tutar = float(v.get("tutar", h.tutar) or 0)
        if tutar <= 0:
            raise CariHareketError("Tutar sıfırdan büyük olmalıdır.")
        yon = TURLER[tur][1] or v.get("yon", h.yon)
        if yon not in YONLER:
            raise CariHareketError("Döviz cinsli harekette yön (Borç/Alacak) seçilmelidir.")
        para = (v.get("para_birimi", h.para_birimi) or "TRY").upper()
        kur = v.get("kur")
        if para == "TRY":
            kur = 1.0
        elif not kur or float(kur) <= 0:
            try:
                kur = money_service.get_rate(self.db, para)
            except money_service.UnknownCurrencyError as e:
                raise CariHareketError(str(e)) from e
        kur = float(kur)
        h.customer_id, h.tur, h.yon = cid, tur, yon
        h.tarih = v.get("tarih", h.tarih) or date.today()
        h.belge_no = (v.get("belge_no", h.belge_no) or "").strip() or None
        h.aciklama = (v.get("aciklama", h.aciklama) or "").strip() or None
        if "odeme_araci" in v or "fin_hesap_id" in v:
            self._finans_hesabi_yaz(h, tur, v.get("odeme_araci"), v.get("fin_hesap_id"), para)
        h.vade = v.get("vade", h.vade)
        h.para_birimi, h.kur, h.tutar = para, kur, tutar
        h.tutar_tl = round(tutar * kur, 2)

    def _finans_hesabi_yaz(self, h: CariHareket, tur: str, arac: str | None, hesap_id: int | None, para: str = "TRY") -> None:
        """Ödeme aracı seçildiyse (yalnız tahsilat/ödeme) o türde bir finans hesabı zorunludur; boşsa kasa/banka etkilenmez."""
        if not arac or tur not in ("tahsilat", "odeme"):
            h.odeme_araci = h.fin_hesap_id = h.hesap = None
            return
        if arac not in ODEME_ARACLARI:
            raise CariHareketError("Geçersiz ödeme aracı.")
        hesap = self.db.get(FinansHesap, hesap_id) if hesap_id else None
        if hesap is None or hesap.is_deleted or hesap.tur != arac:
            raise CariHareketError(f"{ODEME_ARACLARI[arac]} hesabı seçilmelidir.")
        if hesap.doviz_kisitli and (hesap.para_birimi or "TRY").upper() != para:
            raise CariHareketError(f"'{hesap.ad}' hesabı yalnızca {hesap.para_birimi} ile işlem kabul eder (satır dövizi {para}).")
        h.odeme_araci, h.fin_hesap_id, h.hesap = arac, hesap.id, hesap.ad

    def create(self, **v) -> CariHareket:
        h = CariHareket(kaynak="manuel")
        self._hazirla(h, v)
        self.db.add(h)
        self.db.commit()
        return h

    def update(self, hareket_id: int, **v) -> CariHareket:
        h = self.db.get(CariHareket, hareket_id)
        if h is None or h.is_deleted:
            raise CariHareketError("Hareket bulunamadı.")
        self._hazirla(h, v)
        h.version_id = (h.version_id or 1) + 1
        self.db.commit()
        return h

    # ---- fiş ---------------------------------------------------------------
    def sonraki_fis_no(self) -> str:
        """Mevcut en büyük sayısal fiş numarasının bir fazlası (6 haneli)."""
        en_buyuk = 0
        for (no,) in self.db.execute(select(CariFis.fis_no)):
            if str(no).isdigit():
                en_buyuk = max(en_buyuk, int(no))
        return f"{en_buyuk + 1:06d}"

    def fis_kaydet(self, baslik: dict, satirlar: list[dict], fis_id: int | None = None) -> CariFis:
        """Fişi ve satırlarını tek işlemde kaydeder. Satır sözlüğünde `id` varsa güncellenir, yoksa eklenir;
        fişte artık bulunmayan eski satırlar gizlenir. Hata olursa hiçbir şey yazılmaz."""
        if not satirlar:
            raise CariHareketError("Fişte en az bir satır olmalıdır.")
        if baslik.get("varsayilan_tur", "tahsilat") not in TURLER:
            raise CariHareketError("Geçersiz fiş türü.")
        try:
            if fis_id:
                fis = self.db.get(CariFis, fis_id)
                if fis is None or fis.is_deleted:
                    raise CariHareketError("Fiş bulunamadı.")
                if fis.kilitli and baslik.get("kilitli", True):
                    raise CariHareketError("Fiş kilitli; değiştirmek için önce kilidi kaldırın.")
            else:
                fis = CariFis()
            fis.fis_no = (baslik.get("fis_no") or "").strip() or self.sonraki_fis_no()
            fis.tarih = baslik.get("tarih") or date.today()
            fis.saat = baslik.get("saat") or datetime.now().strftime("%H:%M:%S")
            for alan in ("belge_no", "sube", "ozel_kod", "yetki_kodu", "aciklama1", "aciklama2", "aciklama3"):
                setattr(fis, alan, (baslik.get(alan) or "").strip() or None)
            fis.varsayilan_tur = baslik.get("varsayilan_tur", "tahsilat")
            fis.kilitli = bool(baslik.get("kilitli"))
            if fis_id is None:
                self.db.add(fis)
            self.db.flush()

            mevcut = {h.id: h for h in self.db.scalars(
                select(CariHareket).where(CariHareket.fis_id == fis.id, CariHareket.is_deleted == False))}  # noqa: E712
            kalan = set()
            virman = [0.0, 0.0]
            for sira, v in enumerate(satirlar, start=1):
                v = dict(v, tarih=v.get("tarih") or fis.tarih)
                sid = v.pop("id", None)
                no = v.pop("_satir", None) or sira      # ekrandaki satır numarası (hata mesajı ve sıralama)
                try:
                    if sid and sid in mevcut:
                        h = mevcut[sid]
                        self._hazirla(h, v)
                        h.version_id = (h.version_id or 1) + 1
                        kalan.add(sid)
                    else:
                        h = CariHareket(kaynak="fis", fis_id=fis.id)
                        self._hazirla(h, v)
                        self.db.add(h)
                    h.satir_no = no
                    if h.tur.startswith("virman"):
                        virman[0 if h.yon == "borc" else 1] += h.tutar_tl
                except CariHareketError as e:
                    raise CariHareketError(f"Satır {no}: {e}") from e
            if abs(virman[0] - virman[1]) > 0.01:
                raise CariHareketError("Virman fişinde borç ve alacak toplamları eşit olmalıdır.")
            for sid, h in mevcut.items():
                if sid not in kalan:
                    h.is_deleted = True
            self.db.commit()
            return fis
        except Exception:
            self.db.rollback()
            raise

    def fis_getir(self, fis_id: int) -> tuple[CariFis, list[CariHareket]]:
        fis = self.db.get(CariFis, fis_id)
        if fis is None or fis.is_deleted:
            raise CariHareketError("Fiş bulunamadı.")
        satirlar = list(self.db.scalars(
            select(CariHareket).where(CariHareket.fis_id == fis_id, CariHareket.is_deleted == False)  # noqa: E712
            .order_by(CariHareket.satir_no, CariHareket.id)))
        return fis, satirlar

    def fis_gizle(self, fis_id: int) -> None:
        """Fişi ve satırlarını görünümden kaldırır (fiziksel silme yok)."""
        fis, satirlar = self.fis_getir(fis_id)
        if fis.kilitli:
            raise CariHareketError("Fiş kilitli; önce kilidi kaldırın.")
        fis.is_deleted = True
        for h in satirlar:
            h.is_deleted = True
        self.db.commit()

    def hide(self, ids: list[int]) -> int:
        """Silme = gizleme: kayıtlar fiziksel olarak kalır."""
        n = 0
        for i in ids:
            h = self.db.get(CariHareket, i)
            if h is not None and not h.is_deleted:
                h.is_deleted = True
                n += 1
        self.db.commit()
        return n

    # ---- okuma -------------------------------------------------------------
    def _where(self, f: HareketFiltre):
        c = [CariHareket.is_deleted == False]  # noqa: E712
        if f.customer_id:
            c.append(CariHareket.customer_id == f.customer_id)
        if f.tur:
            c.append(CariHareket.tur == f.tur)
        if f.para_birimi:
            c.append(CariHareket.para_birimi == f.para_birimi)
        if f.tarih_bas:
            c.append(CariHareket.tarih >= f.tarih_bas)
        if f.tarih_bit:
            c.append(CariHareket.tarih <= f.tarih_bit)
        if f.haric_fis_id:
            c.append(or_(CariHareket.fis_id.is_(None), CariHareket.fis_id != f.haric_fis_id))
        if f.arama.strip():
            q = f"%{f.arama.strip()}%"
            c.append(or_(
                CariHareket.belge_no.ilike(q), CariHareket.aciklama.ilike(q), CariHareket.hesap.ilike(q),
                CariHareket.customer_id.in_(select(Customer.id).where(
                    or_(Customer.fullname.ilike(q), Customer.customer_code.ilike(q)))),
            ))
        return c

    def list(self, f: HareketFiltre, page: int = 1, per_page: int = 25) -> tuple[list[CariHareket], int]:
        where = self._where(f)
        total = self.db.scalar(select(func.count()).select_from(CariHareket).where(*where)) or 0
        stmt = (select(CariHareket).where(*where)
                .order_by(CariHareket.tarih.desc(), CariHareket.id.desc())
                .offset((max(page, 1) - 1) * per_page).limit(per_page))
        return list(self.db.scalars(stmt)), total

    def ozet(self, f: HareketFiltre) -> HareketOzeti:
        where = self._where(f)
        o = HareketOzeti()
        for yon, toplam, adet in self.db.execute(
            select(CariHareket.yon, func.coalesce(func.sum(CariHareket.tutar_tl), 0.0), func.count())
            .where(*where).group_by(CariHareket.yon)
        ):
            o.adet += adet
            if yon == "borc":
                o.borc = float(toplam)
            else:
                o.alacak = float(toplam)
        return o

    def cari_bakiye(self, customer_id: int, haric_fis_id: int | None = None) -> float:
        return self.ozet(HareketFiltre(customer_id=customer_id, haric_fis_id=haric_fis_id)).bakiye

    def ekstre(self, customer_id: int, bas: date | None = None, bit: date | None = None) -> list[dict]:
        """Tarih sırasıyla yürüyen bakiyeli ekstre satırları."""
        f = HareketFiltre(customer_id=customer_id, tarih_bas=bas, tarih_bit=bit)
        rows = list(self.db.scalars(select(CariHareket).where(*self._where(f))
                                    .order_by(CariHareket.tarih, CariHareket.id)))
        bakiye, out = 0.0, []
        for h in rows:
            borc = h.tutar_tl if h.yon == "borc" else 0.0
            alacak = h.tutar_tl if h.yon == "alacak" else 0.0
            bakiye += borc - alacak
            out.append({"hareket": h, "borc": borc, "alacak": alacak, "bakiye": bakiye})
        return out
