"""TOYA ERP - Belge / fiş numara servisi (tek sahip).

Her belge ve fişin numarası buradan gelir; ekranlar ve servisler kendi numara üretmez. Numara bir ŞABLONDAN üretilir:

    {YYYY} yıl (4 hane)   {YY} yıl (2 hane)   {MM} ay   {####} sıra numarası (# sayısı = hane)   diğer karakterler aynen

    "FAT{YYYY}{#########}" → FAT2026000000001 (GİB e-fatura numarası biçimi: 3 harf + yıl + 9 hane)
    "TEK-{YYYY}-{#####}"   → TEK-2026-00001

Sıra numarası şablondaki dönem belirteçlerine göre sıfırlanır ({MM} varsa aylık, yalnız {YYYY}/{YY} varsa yıllık, yoksa hiç).
Şablonlar `system_settings`'te `numara.sablon.<kod>` anahtarıyla tutulur; yoksa `VARSAYILANLAR` kullanılır (Genel Ayarlar'dan değişir).

Sayaç (`NumaraSayac`) yalnız bir İPUCUDUR. Gerçek çakışma denetimi `mevcut_mu(numara)` ile yapılır: önerilen numara kullanımdaysa
bir sonrakine geçilir; böylece elle girilen, içe aktarılan ya da eski numaralar sistemi bozmaz. Elle girilen şablona uyan numara
`kullanildi` ile sayacı ilerletir. Silinen SON numara `birak` ile geri verilir (arada silinmiş boşluklar da atlanır); resmi (e-Devlet)
işaretli belgede çağıran taraf `birak` çağırmaz: GİB numarası bir kez verildi mi yeniden kullanılamaz."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select

from src.core.models import DocumentSeries, NumaraSayac
from src.desktop.services import settings_store

#: kod -> varsayılan şablon. Belge kodları `belge_turu`, alış yönü için `<belge_turu>_alis`; fiş kodları aşağıdadır.
VARSAYILANLAR: dict[str, str] = {
    "talep": "TLP-{YYYY}-{#####}", "teklif": "TEK-{YYYY}-{#####}", "siparis": "SIP-{YYYY}-{#####}",
    "irsaliye": "IRS{YYYY}{#########}", "fatura": "FAT{YYYY}{#########}", "iade_fatura": "IAD{YYYY}{#########}",
    "talep_alis": "ATL-{YYYY}-{#####}", "teklif_alis": "ATK-{YYYY}-{#####}", "siparis_alis": "ASP-{YYYY}-{#####}",
    "irsaliye_alis": "AIR{YYYY}{#########}", "fatura_alis": "AFT{YYYY}{#########}", "iade_fatura_alis": "AIA{YYYY}{#########}",
    "cari_fis": "{######}", "kasa_fis": "K{######}", "banka_fis": "B{######}", "stok_fis": "{######}",
}
ADLAR: dict[str, str] = {
    "talep": "Talep (satış)", "teklif": "Teklif (satış)", "siparis": "Sipariş (alınan)", "irsaliye": "Satış irsaliyesi", "fatura": "Satış faturası",
    "iade_fatura": "Satış iade faturası", "talep_alis": "Talep (alış)", "teklif_alis": "Teklif (alınan)", "siparis_alis": "Sipariş (verilen)",
    "irsaliye_alis": "Alış irsaliyesi", "fatura_alis": "Alış faturası", "iade_fatura_alis": "Alış iade faturası",
    "cari_fis": "Cari fişi", "kasa_fis": "Kasa fişi", "banka_fis": "Banka fişi", "stok_fis": "Stok fişi",
}
_ANAHTAR = "numara.sablon."
_BELIRTEC = re.compile(r"\{(YYYY|YY|MM|DD|SERI|SUBE|#+)\}")


class SablonHatasi(ValueError):  # noqa: N818
    """Geçersiz numara şablonu; mesaj kullanıcıya gösterilebilir."""


def kod_belge(belge_turu: str, yon: str | None = "satis") -> str:
    return belge_turu if (yon or "satis") != "alis" else f"{belge_turu}_alis"


def dogrula(sablon: str) -> None:
    """Şablonda tam bir {#…} sıra belirteci olmalı; geçersiz süslü parantez kalmamalı."""
    sayac = [m.group(1) for m in _BELIRTEC.finditer(sablon) if m.group(1).startswith("#")]
    if len(sayac) != 1:
        raise SablonHatasi("Şablonda tam olarak bir sıra belirteci olmalıdır (ör. {#####}).")
    if re.search(r"[{}]", _BELIRTEC.sub("", sablon)):
        raise SablonHatasi("Şablonda tanınmayan süslü parantez var. Kullanılabilenler: {YYYY} {YY} {MM} {DD} {SERI} {SUBE} {#####}.")
    if len(sablon) > 30:
        raise SablonHatasi("Üretilen numara uzunluğu 30 karakteri aşabilir; şablonu kısaltın.")


def validate_gib_format(gib_prefix: str, sablon: str) -> tuple[bool, str]:
    """GİB e-Fatura / e-Belge standart format denetimi (3 karakter kod + 4 karakter yıl + 9 karakter sıra = 16 karakter)."""
    prefix = (gib_prefix or "").strip().upper()
    if len(prefix) != 3 or not prefix.isalnum():
        return False, "GİB Birim Kodu tam olarak 3 alfanümerik karakter (örn. EFA, EAR) olmalıdır."
    try:
        sample = uret(sablon, date(2026, 1, 1), 1, seri=prefix)
    except Exception as e:
        return False, f"Şablon hatası: {e}"
    if len(sample) != 16:
        return False, f"GİB e-Belge standardı tam 16 karakter olmalıdır; üretilen örnek '{sample}' ({len(sample)} karakter)."
    if not sample.startswith(prefix):
        return False, f"Üretilen e-Belge numarası GİB birim kodu '{prefix}' ile başlamalıdır."
    return True, ""


def _seri_ayari_anahtari(kod: str, company_id: int | None = None, seri_kodu: str | None = None) -> str:
    if company_id is None and not seri_kodu:
        return _ANAHTAR + kod
    comp = f"c{company_id}" if company_id is not None else "c0"
    ser = f"s{seri_kodu}" if seri_kodu else "s0"
    return f"{_ANAHTAR}{comp}.{ser}.{kod}"


def sablon(db, kod: str, company_id: int | None = None, seri_kodu: str | None = None) -> str:
    # 1. First check DocumentSeries table if company_id or seri_kodu specified
    if db is not None:
        try:
            stmt = select(DocumentSeries).where(DocumentSeries.belge_turu == kod, DocumentSeries.is_active == True)
            if company_id is not None:
                stmt = stmt.where((DocumentSeries.company_id == company_id) | (DocumentSeries.company_id.is_(None)))
            if seri_kodu:
                stmt = stmt.where(DocumentSeries.seri_kodu == seri_kodu)
            else:
                stmt = stmt.order_by(DocumentSeries.is_default.desc(), DocumentSeries.id)
            ds = db.scalars(stmt).first()
            if ds and ds.sablon:
                return ds.sablon
        except Exception:
            pass

    # 2. Check settings_store (supports legacy & company keys)
    if company_id is not None or seri_kodu:
        key = _seri_ayari_anahtari(kod, company_id, seri_kodu)
        ozel_seri = (settings_store.get_setting(db, key, "") or "").strip()
        if ozel_seri:
            return ozel_seri

    if kod not in VARSAYILANLAR:
        raise SablonHatasi(f"Bilinmeyen numara kodu: {kod}")
    ozel = (settings_store.get_setting(db, _ANAHTAR + kod, "") or "").strip()
    return ozel or VARSAYILANLAR[kod]


def sablon_kaydet(db, kod: str, deger: str, company_id: int | None = None, seri_kodu: str | None = None) -> None:
    """Boş değer varsayılana döner. Geçersiz şablonda `SablonHatasi`."""
    deger = (deger or "").strip()
    if deger:
        dogrula(deger)
    key = _seri_ayari_anahtari(kod, company_id, seri_kodu)
    settings_store.set_setting(db, key, deger, commit=True)


def _tarih(t) -> date:
    if isinstance(t, datetime):
        return t.date()
    return t or date.today()


def donem_anahtari(sab: str, t) -> str:
    t = _tarih(t)
    if "{MM}" in sab:
        return f"{t.year:04d}-{t.month:02d}"
    if "{YYYY}" in sab or "{YY}" in sab:
        return f"{t.year:04d}"
    return "-"


def uret(sab: str, t, sayi: int, seri: str = "", sube: str = "") -> str:
    t = _tarih(t)

    def yerine(m: re.Match) -> str:
        b = m.group(1)
        if b == "YYYY":
            return f"{t.year:04d}"
        if b == "YY":
            return f"{t.year % 100:02d}"
        if b == "MM":
            return f"{t.month:02d}"
        if b == "DD":
            return f"{t.day:02d}"
        if b == "SERI":
            return seri or ""
        if b == "SUBE":
            return sube or ""
        return f"{sayi:0{len(b)}d}"
    return _BELIRTEC.sub(yerine, sab)


def _cozumle(sab: str, numara: str) -> tuple[str, int] | None:
    """Numarayı şablona göre çözer: (dönem anahtarı, sıra). Uymuyorsa None."""
    desen, son = "", 0
    for m in _BELIRTEC.finditer(sab):
        desen += re.escape(sab[son:m.start()])
        b = m.group(1)
        if b == "YYYY":
            desen += r"(?P<y>\d{4})"
        elif b == "YY":
            desen += r"(?P<yy>\d{2})"
        elif b == "MM":
            desen += r"(?P<m>\d{2})"
        elif b == "DD":
            desen += r"(?P<d>\d{2})"
        elif b == "SERI":
            desen += r"(?P<seri>[A-Za-z0-9_-]*)"
        elif b == "SUBE":
            desen += r"(?P<sube>[A-Za-z0-9_-]*)"
        else:
            desen += rf"(?P<s>\d{{{len(b)},}})"
        son = m.end()
    desen += re.escape(sab[son:])
    e = re.fullmatch(desen, numara or "")
    if e is None:
        return None
    g = e.groupdict()
    yil = int(g["y"]) if g.get("y") else (2000 + int(g["yy"]) if g.get("yy") else None)
    if "{MM}" in sab:
        donem = f"{yil or 0:04d}-{int(g['m']):02d}"
    elif yil is not None:
        donem = f"{yil:04d}"
    else:
        donem = "-"
    return donem, int(g["s"])


def _sayac_kodu(kod: str, company_id: int | None = None, seri_kodu: str | None = None) -> str:
    if company_id is None and not seri_kodu:
        return kod
    comp = f"c{company_id}" if company_id is not None else "c0"
    ser = f"s{seri_kodu}" if seri_kodu else "s0"
    return f"{kod}:{comp}:{ser}"


def _sayac(db, kod: str, donem: str, olustur: bool, company_id: int | None = None, seri_kodu: str | None = None) -> NumaraSayac | None:
    if db is None:
        return None
    full_kod = _sayac_kodu(kod, company_id, seri_kodu)
    s = db.scalar(select(NumaraSayac).where(NumaraSayac.kod == full_kod, NumaraSayac.donem == donem))
    if s is None and (company_id is not None or seri_kodu):
        # Fallback to base code if specific company/series counter doesn't exist yet
        s = db.scalar(select(NumaraSayac).where(NumaraSayac.kod == kod, NumaraSayac.donem == donem))
    if s is None and olustur:
        s = NumaraSayac(kod=full_kod, donem=donem, son_sayi=0)
        db.add(s)
        db.flush()
    return s


def onizle(db, kod: str, tarih=None, mevcut_mu: Callable[[str], bool] | None = None, company_id: int | None = None, seri_kodu: str | None = None, sube: str = "") -> str:
    """Bir sonraki boş numara (sayaç ilerletilmez). Kullanımdaki numaralar atlanır."""
    sab = sablon(db, kod, company_id=company_id, seri_kodu=seri_kodu)
    donem = donem_anahtari(sab, tarih)
    s = _sayac(db, kod, donem, olustur=False, company_id=company_id, seri_kodu=seri_kodu)
    n = (s.son_sayi if s else 0) + 1
    for _ in range(100_000):
        aday = uret(sab, tarih, n, seri=seri_kodu or "", sube=sube)
        if mevcut_mu is None or not mevcut_mu(aday):
            return aday
        n += 1
    raise SablonHatasi("Boş numara bulunamadı; şablonu ya da hane sayısını gözden geçirin.")


def kullanildi(db, kod: str, numara: str, company_id: int | None = None, seri_kodu: str | None = None) -> None:
    """Bir numara kullanıldı (elle girilmiş olabilir): şablona uyuyorsa sayacı gerekirse ilerletir."""
    sab = sablon(db, kod, company_id=company_id, seri_kodu=seri_kodu)
    c = _cozumle(sab, numara)
    if c is None:
        return
    donem, sayi = c
    s = _sayac(db, kod, donem, olustur=True, company_id=company_id, seri_kodu=seri_kodu)
    if s and sayi > s.son_sayi:
        s.son_sayi = sayi
        db.flush()


def al(db, kod: str, tarih=None, mevcut_mu: Callable[[str], bool] | None = None, company_id: int | None = None, seri_kodu: str | None = None, sube: str = "") -> str:
    """Bir sonraki boş numarayı verir ve sayacı ilerletir (çağıran işlemin transaction'ında; commit çağırana aittir)."""
    numara = onizle(db, kod, tarih, mevcut_mu, company_id=company_id, seri_kodu=seri_kodu, sube=sube)
    kullanildi(db, kod, numara, company_id=company_id, seri_kodu=seri_kodu)
    return numara


def birak(db, kod: str, numara: str, mevcut_mu: Callable[[str], bool] | None = None, company_id: int | None = None, seri_kodu: str | None = None, sube: str = "") -> bool:
    """Silinen belgenin numarasını, SON numara ise geri verir (sayaç bir önceki KULLANIMDAKİ numaraya iner). Son değilse False.
    `mevcut_mu`, silinen numaranın kendisi için artık False dönmelidir (çağıran silmeyi/yeniden adlandırmayı önce yapar)."""
    sab = sablon(db, kod, company_id=company_id, seri_kodu=seri_kodu)
    c = _cozumle(sab, numara)
    if c is None:
        return False
    donem, sayi = c
    s = _sayac(db, kod, donem, olustur=False, company_id=company_id, seri_kodu=seri_kodu)
    if s is None or s.son_sayi != sayi:
        return False
    yil = int(donem[:4]) if donem != "-" else 2000
    ay = int(donem[5:7]) if len(donem) == 7 else 1
    n = sayi - 1
    while n > 0 and mevcut_mu is not None and not mevcut_mu(uret(sab, date(yil, ay, 1), n, seri=seri_kodu or "", sube=sube)):
        n -= 1                                            # arada silinmiş boşlukları da geri al
    s.son_sayi = max(n, 0)
    db.flush()
    return True


@dataclass
class Onizleme:
    kod: str
    ad: str
    sablon: str
    ornek: str
    ozel: bool


def ozet(db, tarih=None, company_id: int | None = None) -> list[Onizleme]:
    """Ayar ekranı için: her kodun şablonu ve bir sonraki numara örneği (sayaca bakmadan 1. numara)."""
    out = []
    for kod in VARSAYILANLAR:
        sab = sablon(db, kod, company_id=company_id)
        out.append(Onizleme(kod, ADLAR[kod], sab, uret(sab, tarih or date.today(), 1), sab != VARSAYILANLAR[kod]))
    return out


# ---- Belge & Seri Yönetimi (DocumentSeries CRUD) -------------------------------------------------------------
def list_series(db, company_id: int | None = None, belge_turu: str | None = None) -> list[DocumentSeries]:
    """Tanımlı serileri firma ve belge türüne göre listeler."""
    if db is None:
        return []
    stmt = select(DocumentSeries)
    if company_id is not None:
        stmt = stmt.where((DocumentSeries.company_id == company_id) | (DocumentSeries.company_id.is_(None)))
    if belge_turu:
        stmt = stmt.where(DocumentSeries.belge_turu == belge_turu)
    stmt = stmt.order_by(DocumentSeries.belge_turu, DocumentSeries.is_default.desc(), DocumentSeries.seri_kodu)
    return list(db.scalars(stmt).all())


def get_series(db, series_id: int) -> DocumentSeries | None:
    if db is None:
        return None
    return db.get(DocumentSeries, series_id)


def get_default_series(db, belge_turu: str, company_id: int | None = None) -> DocumentSeries | None:
    if db is None:
        return None
    stmt = select(DocumentSeries).where(
        DocumentSeries.belge_turu == belge_turu,
        DocumentSeries.is_active == True,  # noqa: E712
    )
    if company_id is not None:
        stmt = stmt.where((DocumentSeries.company_id == company_id) | (DocumentSeries.company_id.is_(None)))
    stmt = stmt.order_by(DocumentSeries.is_default.desc(), DocumentSeries.id)
    return db.scalars(stmt).first()


def save_series(db, data: dict, series_id: int | None = None) -> DocumentSeries:
    """Yeni seri ekler veya mevcut seriyi günceller."""
    belge_turu = (data.get("belge_turu") or "").strip()
    seri_kodu = (data.get("seri_kodu") or "").strip().upper()
    sablon_val = (data.get("sablon") or "").strip()
    is_efatura = bool(data.get("is_efatura", False))
    gib_prefix = (data.get("gib_prefix") or seri_kodu).strip().upper()

    if not belge_turu:
        raise SablonHatasi("Belge türü seçilmelidir.")
    if not seri_kodu:
        raise SablonHatasi("Seri kodu girilmelidir (örn. A, FAT, EAR).")
    if not sablon_val:
        # e-Fatura ise varsayılan GİB şablonu
        sablon_val = "{SERI}{YYYY}{#########}" if is_efatura else VARSAYILANLAR.get(belge_turu, "{SERI}-{YYYY}-{#####}")

    dogrula(sablon_val)

    if is_efatura:
        ok, err = validate_gib_format(gib_prefix, sablon_val)
        if not ok:
            raise SablonHatasi(err)

    company_id = data.get("company_id")
    is_default = bool(data.get("is_default", False))

    is_new = False
    if series_id:
        ds = db.get(DocumentSeries, series_id)
        if not ds:
            raise SablonHatasi("Güncellenecek seri bulunamadı.")
    else:
        ds = DocumentSeries()
        is_new = True

    if is_default:
        # Unset other defaults for same company and document type
        stmt = select(DocumentSeries).where(
            DocumentSeries.belge_turu == belge_turu,
            DocumentSeries.company_id == company_id,
        )
        for other in db.scalars(stmt).all():
            if other.id != series_id:
                other.is_default = False

    ds.company_id = company_id
    ds.belge_turu = belge_turu
    ds.seri_kodu = seri_kodu
    ds.seri_adi = data.get("seri_adi") or None
    ds.sablon = sablon_val
    ds.baslangic_no = int(data.get("baslangic_no", 1))
    ds.is_default = is_default
    ds.is_active = bool(data.get("is_active", True))
    ds.is_efatura = is_efatura
    ds.efatura_turu = data.get("efatura_turu") or None
    ds.gib_prefix = gib_prefix if is_efatura else None
    ds.entegrator_kodu = data.get("entegrator_kodu") or None

    if is_new:
        db.add(ds)

    db.flush()
    db.commit()
    return ds


def delete_series(db, series_id: int) -> bool:
    """Seriyi siler."""
    ds = db.get(DocumentSeries, series_id)
    if not ds:
        return False
    db.delete(ds)
    db.commit()
    return True


def ensure_default_series(db, company_id: int | None = None) -> list[DocumentSeries]:
    """Bir firma için standart varsayılan serileri otomatik oluşturur (idempotent)."""
    if db is None:
        return []
    created = []
    defaults = [
        ("teklif", "TEK", "Satış Teklifi Standart", "TEK-{YYYY}-{#####}", False, None, None),
        ("siparis", "SIP", "Satış Siparişi Standart", "SIP-{YYYY}-{#####}", False, None, None),
        ("irsaliye", "IRS", "Satış İrsaliyesi Standart", "IRS{YYYY}{#########}", False, None, None),
        ("fatura", "FAT", "e-Fatura Satış Serisi", "{SERI}{YYYY}{#########}", True, "e-fatura", "FAT"),
        ("fatura", "EAR", "e-Arşiv Fatura Serisi", "{SERI}{YYYY}{#########}", True, "e-arsiv", "EAR"),
        ("iade_fatura", "IAD", "Satış İade Faturası", "IAD{YYYY}{#########}", False, None, None),
        ("cari_fis", "CF", "Cari Fişi Serisi", "{######}", False, None, None),
        ("kasa_fis", "KF", "Kasa Fişi Serisi", "K{######}", False, None, None),
        ("banka_fis", "BF", "Banka Fişi Serisi", "B{######}", False, None, None),
        ("stok_fis", "SF", "Stok Fişi Serisi", "{######}", False, None, None),
    ]
    for b_turu, s_kodu, s_adi, sab, is_e, e_tur, gib in defaults:
        stmt = select(DocumentSeries).where(
            DocumentSeries.company_id == company_id,
            DocumentSeries.belge_turu == b_turu,
            DocumentSeries.seri_kodu == s_kodu,
        )
        existing = db.scalars(stmt).first()
        if not existing:
            # Check if any default exists for this type
            has_default = db.scalar(
                select(DocumentSeries.id).where(
                    DocumentSeries.company_id == company_id,
                    DocumentSeries.belge_turu == b_turu,
                    DocumentSeries.is_default == True,  # noqa: E712
                ),
            ) is not None
            ds = DocumentSeries(
                company_id=company_id,
                belge_turu=b_turu,
                seri_kodu=s_kodu,
                seri_adi=s_adi,
                sablon=sab,
                baslangic_no=1,
                son_numara=0,
                is_default=(not has_default),
                is_active=True,
                is_efatura=is_e,
                efatura_turu=e_tur,
                gib_prefix=gib,
            )
            db.add(ds)
            created.append(ds)
    if created:
        db.flush()
        db.commit()
    return created


def find_number_gaps(db, kod: str, company_id: int | None = None, seri_kodu: str | None = None, yil: int | None = None) -> list[dict]:
    """Müteselsil sıra denetimi / Boşluk analizi:
    Verilen belge/fiş türünde ve dönemde kayıtlı numaraları inceler, atlanan veya silinen sıra numaralarını döner.
    """
    if db is None:
        return []
    sab = sablon(db, kod, company_id=company_id, seri_kodu=seri_kodu)
    yil_val = yil or date.today().year

    # 1. Fetch numbers from DB
    used_numbers: list[str] = []
    if kod in _FIS_MODELLERI:
        from src.core import models
        model = getattr(models, _FIS_MODELLERI[kod])
        stmt = select(model.fis_no).where(model.is_deleted == False)  # noqa: E712
        used_numbers = [str(r) for r in db.scalars(stmt).all() if r]
    else:
        from src.core.models import Quotation
        belge_t = kod.replace("_alis", "")
        yon = "alis" if kod.endswith("_alis") else "satis"
        stmt = select(Quotation.quotation_number).where(
            Quotation.belge_turu == belge_t,
            Quotation.yon == yon,
        )
        if company_id is not None:
            stmt = stmt.where((Quotation.company_id == company_id) | (Quotation.company_id.is_(None)))
        used_numbers = [str(r) for r in db.scalars(stmt).all() if r and "~sil" not in str(r)]

    # 2. Parse numbers
    sequences: list[int] = []
    for num in used_numbers:
        c = _cozumle(sab, num)
        if c:
            donem, seq = c
            if donem == "-" or str(yil_val) in donem:
                sequences.append(seq)

    if not sequences:
        return []

    sequences = sorted(set(sequences))
    min_seq = 1
    max_seq = max(sequences)

    gaps = []
    seq_set = set(sequences)
    for expected in range(min_seq, max_seq + 1):
        if expected not in seq_set:
            sample = uret(sab, date(yil_val, 1, 1), expected, seri=seri_kodu or "")
            gaps.append({
                "seq": expected,
                "missing_number": sample,
                "donem": str(yil_val),
            })

    return gaps


# ---- belge / fiş kolaylıkları ------------------------------------------------------------------------------------
def _belge_var_mi(db) -> Callable[[str], bool]:
    from src.core.models import Quotation
    return lambda n: db.scalar(select(Quotation.id).where(Quotation.quotation_number == n)) is not None      # silinenler de dahil (unique)


def belge_onizle(db, belge_turu: str, yon: str | None = "satis", tarih=None, company_id: int | None = None, seri_kodu: str | None = None, sube: str = "") -> str:
    return onizle(db, kod_belge(belge_turu, yon), tarih, _belge_var_mi(db), company_id=company_id, seri_kodu=seri_kodu, sube=sube)


def belge_numarasi(db, belge_turu: str, yon: str | None = "satis", tarih=None, company_id: int | None = None, seri_kodu: str | None = None, sube: str = "") -> str:
    """Belge (teklif/sipariş/irsaliye/fatura…) için sonraki numara; sayaç ilerler."""
    return al(db, kod_belge(belge_turu, yon), tarih, _belge_var_mi(db), company_id=company_id, seri_kodu=seri_kodu, sube=sube)


def belge_kullanildi(db, belge_turu: str, yon: str | None, numara: str, company_id: int | None = None, seri_kodu: str | None = None) -> None:
    kullanildi(db, kod_belge(belge_turu, yon), numara, company_id=company_id, seri_kodu=seri_kodu)


def belge_silindi(db, q, company_id: int | None = None, seri_kodu: str | None = None) -> bool:
    """Silinen (gizlenen) belge SON numaraysa numarayı geri verir; belge numarası unique olduğundan silinen kayıt `<no>~sil<id>` adını alır.
    Resmi (e-Devlet / GİB) işaretli belgede geri verilmez. Numara geri verildiyse True."""
    if getattr(q, "resmi_gonderildi", False) or not q.quotation_number:
        return False
    kod, eski = kod_belge(q.belge_turu or "teklif", q.yon), q.quotation_number
    comp_id = company_id or getattr(q, "company_id", None)
    if not birak(db, kod, eski, _belge_var_mi(db), company_id=comp_id, seri_kodu=seri_kodu):
        return False
    q.quotation_number = f"{eski}~sil{q.id}"
    q.notes = ((q.notes or "") + f"\n[Silindi; numara serbest bırakıldı: {eski}]").strip()
    db.flush()
    return True


_FIS_MODELLERI = {"cari_fis": "CariFis", "kasa_fis": "FinansFis", "banka_fis": "FinansFis", "stok_fis": "StokFis"}


def _fis_var_mi(db, kod: str) -> Callable[[str], bool]:
    from src.core import models
    model = getattr(models, _FIS_MODELLERI[kod])
    return lambda n: db.scalar(select(model.id).where(model.fis_no == n, model.is_deleted == False)) is not None  # noqa: E712


def fis_onizle(db, kod: str, tarih=None, company_id: int | None = None, seri_kodu: str | None = None, sube: str = "") -> str:
    return onizle(db, kod, tarih, _fis_var_mi(db, kod), company_id=company_id, seri_kodu=seri_kodu, sube=sube)


def fis_kullanildi(db, kod: str, numara: str, company_id: int | None = None, seri_kodu: str | None = None) -> None:
    kullanildi(db, kod, numara, company_id=company_id, seri_kodu=seri_kodu)


def fis_silindi(db, kod: str, numara: str, company_id: int | None = None, seri_kodu: str | None = None, sube: str = "") -> bool:
    """Silinen fiş SON numaraysa geri verilir (fiş silme = gizleme; çağıran `is_deleted` yaptıktan sonra çağırır)."""
    return birak(db, kod, numara, _fis_var_mi(db, kod), company_id=company_id, seri_kodu=seri_kodu, sube=sube)
