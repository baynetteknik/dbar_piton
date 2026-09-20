"""
TOYA ERP - Döviz Kuru Kaynak Servisi

Genel Ayarlar > Döviz & Kur panelinde seçilen kaynaktan (TCMB resmi XML,
kullanıcının verdiği serbest piyasa XML adresi veya tamamen manuel giriş)
güncel kurları çeker; hem "güncel kur" olarak `Currency.rate`'e (bu tablo
`HareketFinansWidget._load_from_db()` üzerinden Teklif/Fatura/İrsaliye gibi
tüm fiş ekranlarına otomatik yansır) hem de gün bazlı geçmiş olarak
`CurrencyRateHistory`'ye yazar. Böylece Döviz & Kur paneli belirli bir
tarihteki (veya tarih aralığındaki) kurları görüntüleyebilir/yazdırabilir.
"""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import requests
from sqlalchemy import select

from src.core.models import Currency, CurrencyRateHistory
from src.desktop.services.settings_store import get_json, get_setting, set_setting

logger = logging.getLogger(__name__)

#: TCMB'nin günlük resmi döviz kuru XML'i — "TCMB" kaynağı seçildiğinde adres
#: kullanıcıdan istenmez, sabit bu adrese (veya geçmiş tarih isteniyorsa
#: `tcmb_url_for_date`'in ürettiği arşiv adresine) gidilir.
TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"

SOURCE_TCMB = "tcmb"
SOURCE_SERBEST = "serbest"
SOURCE_MANUEL = "manuel"
SOURCE_LABELS = {
    SOURCE_TCMB: "TCMB (Resmi)",
    SOURCE_SERBEST: "Serbest Piyasa (Özel Adres/XML)",
    SOURCE_MANUEL: "Manuel Giriş",
}

KEY_SOURCE_TYPE = "doviz.kaynak_tipi"
KEY_SOURCE_URL = "doviz.kaynak_url"
KEY_LAST_UPDATE = "doviz.son_guncelleme"
KEY_LAST_ERROR = "doviz.son_hata"

#: Serbest Piyasa kaynak tanımları — [{"name": "Bankam XML", "url": "https://..."}]
#: (bkz. `SerbestPiyasaKaynakField` / `SerbestPiyasaYonetimDialog`).
KEY_SERBEST_SOURCES = "doviz.serbest_piyasa_kaynaklari"

REQUEST_TIMEOUT = 10

RateFull = dict[str, tuple[float | None, float | None]]  # {kod: (alış, satış)}


@dataclass
class RateFetchResult:
    success: bool
    rates: dict[str, float] = field(default_factory=dict)  # {"USD": 41.20, ...} — satış tercihli
    rates_full: RateFull = field(default_factory=dict)
    message: str = ""


# ─────────────────────────────────────────────
# Kaynak Ayarları
# ─────────────────────────────────────────────

def get_source_config(db) -> tuple[str, str]:
    """(kaynak_tipi, kaynak_url) döner — varsayılan TCMB."""
    kind = get_setting(db, KEY_SOURCE_TYPE, SOURCE_TCMB) or SOURCE_TCMB
    url = get_setting(db, KEY_SOURCE_URL, "") or ""
    return kind, url


def set_source_config(db, kind: str, url: str = "") -> None:
    set_setting(db, KEY_SOURCE_TYPE, kind)
    set_setting(db, KEY_SOURCE_URL, url)


def list_serbest_sources(db) -> list[dict]:
    """Kayıtlı Serbest Piyasa kaynaklarını döner: `[{"name": ..., "url": ...}, ...]`."""
    return get_json(db, KEY_SERBEST_SOURCES, []) or []


def save_serbest_sources(db, items: list[dict]) -> None:
    set_setting(db, KEY_SERBEST_SOURCES, json.dumps(items, ensure_ascii=False))


def tcmb_url_for_date(d: date) -> str:
    """TCMB arşiv adresi — geçmiş bir tarih için (bugün için `TCMB_URL` kullanılır)."""
    return f"https://www.tcmb.gov.tr/kurlar/{d.strftime('%Y%m')}/{d.strftime('%d%m%Y')}.xml"


# ─────────────────────────────────────────────
# XML Ayrıştırma
# ─────────────────────────────────────────────

def _to_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(str(text).strip().replace(",", "."))
    except ValueError:
        return None


def _parse_tcmb_xml_full(xml_bytes: bytes) -> RateFull:
    """TCMB'nin ``<Tarih_Date><Currency Kod="USD">...<ForexBuying>/<ForexSelling>``
    şemasını {kod: (alış, satış)} olarak ayrıştırır."""
    root = ET.fromstring(xml_bytes)
    out: RateFull = {}
    for cur in root.findall("Currency"):
        kod = cur.get("Kod") or cur.get("CurrencyCode")
        if not kod:
            continue
        alis = _to_float(cur.findtext("ForexBuying"))
        satis = _to_float(cur.findtext("ForexSelling"))
        if alis is None and satis is None:
            continue
        out[kod.upper()] = (alis, satis)
    return out


def _parse_tcmb_xml(xml_bytes: bytes) -> dict[str, float]:
    """Geriye dönük uyumluluk: {kod: kur} düz sözlük — satış tercihli."""
    return _flatten(_parse_tcmb_xml_full(xml_bytes))


_CODE_ATTRS = ("Kod", "Code", "CurrencyCode", "kod", "code")
_ALIS_ATTRS = ("Alis", "Alış", "Buying", "alis", "buying")
_SATIS_ATTRS = ("Satis", "Satış", "Selling", "satis", "selling")
_VALUE_ATTRS = ("Deger", "Value", "Rate", "Kur", "deger", "value", "rate", "kur")


def _parse_generic_xml_full(xml_bytes: bytes) -> RateFull:
    """TCMB şeması dışındaki (serbest piyasa) adresler için toleranslı
    ayrıştırma: her elemanda bir "kod" özniteliği ile alış/satış (veya tek bir
    genel değer) arar. Beklenen en basit biçimler::

        <Kurlar>
            <Kur Kod="USD" Alis="41.10" Satis="41.25"/>
            <Kur Kod="EUR" Deger="44.10"/>  <!-- tek değer: hem alış hem satış -->
        </Kurlar>
    """
    root = ET.fromstring(xml_bytes)
    out: RateFull = {}
    for el in root.iter():
        kod = next((el.get(a) for a in _CODE_ATTRS if el.get(a)), None)
        if not kod:
            continue
        alis = _to_float(next((el.get(a) for a in _ALIS_ATTRS if el.get(a)), None))
        satis = _to_float(next((el.get(a) for a in _SATIS_ATTRS if el.get(a)), None))
        if alis is None and satis is None:
            single = _to_float(next((el.get(a) for a in _VALUE_ATTRS if el.get(a)), None))
            if single is None:
                single = _to_float((el.text or "").strip() or None)
            if single is None:
                continue
            alis = satis = single
        out[kod.upper()] = (alis, satis)
    return out


def _parse_generic_xml(xml_bytes: bytes) -> dict[str, float]:
    return _flatten(_parse_generic_xml_full(xml_bytes))


def _flatten(full: RateFull) -> dict[str, float]:
    out: dict[str, float] = {}
    for kod, (alis, satis) in full.items():
        val = satis if satis is not None else alis
        if val is not None:
            out[kod] = val
    return out


# ─────────────────────────────────────────────
# Kur Çekme
# ─────────────────────────────────────────────

def fetch_rates(kind: str, url: str = "", for_date: date | None = None) -> RateFetchResult:
    """Seçilen kaynaktan kurları çeker. Manuel kaynakta ağ isteği yapılmaz.

    `for_date` verilip bugünden farklıysa ve kaynak TCMB ise, TCMB'nin arşiv
    adresi kullanılır (gerçek geçmiş tarih desteği). Serbest piyasa
    kaynaklarında tarih parametresi desteklenmez — genelde yalnızca güncel
    değer sunan bir sayfa/servis olacağından her tarih için aynı adresten en
    güncel değerler alınır (best-effort).
    """
    if kind == SOURCE_MANUEL:
        return RateFetchResult(
            success=True, message="Manuel kaynak seçili — otomatik çekim yapılmaz.",
        )

    if kind == SOURCE_TCMB:
        target_url = (
            tcmb_url_for_date(for_date)
            if for_date and for_date != date.today()
            else TCMB_URL
        )
    else:
        target_url = url.strip()

    if not target_url:
        return RateFetchResult(success=False, message="Kaynak adresi (URL) tanımlı değil.")

    try:
        resp = requests.get(target_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Döviz kuru kaynağına erişilemedi (%s): %s", target_url, exc)
        return RateFetchResult(success=False, message=f"Kaynağa erişilemedi: {exc}")

    try:
        full = _parse_tcmb_xml_full(resp.content) if kind == SOURCE_TCMB else {}
        if not full:
            full = _parse_generic_xml_full(resp.content)
    except ET.ParseError as exc:
        logger.warning("Döviz kuru XML ayrıştırılamadı: %s", exc)
        return RateFetchResult(success=False, message=f"XML ayrıştırılamadı: {exc}")

    if not full:
        return RateFetchResult(success=False, message="Kaynakta tanınabilir kur bulunamadı.")

    flat = _flatten(full)
    return RateFetchResult(success=True, rates=flat, rates_full=full, message=f"{len(flat)} kur alındı.")


def apply_rates_to_db(db, rates: dict[str, float]) -> int:
    """Çekilen (düz) kurları mevcut `Currency` kayıtlarına yazar.

    TRY her zaman 1.0 sabit kalır. Kod DB'de tanımlı değilse dokunulmaz —
    yeni bir döviz tanımlamak kullanıcının kararıdır, otomatik eklenmez.
    Güncellenen kayıt sayısını döner.
    """
    if not db or not rates:
        return 0
    updated = 0
    existing = db.scalars(
        select(Currency).where(Currency.is_deleted == False),  # noqa: E712
    ).all()
    for c in existing:
        code = (c.code or "").upper()
        if code == "TRY":
            continue
        if code in rates:
            c.rate = rates[code]
            updated += 1
    if updated:
        db.commit()
    return updated


# ─────────────────────────────────────────────
# Gün Bazlı Geçmiş (CurrencyRateHistory)
# ─────────────────────────────────────────────

def upsert_rate_history(
    db, rate_date: date, code: str, *,
    mb_alis: float | None = None, mb_satis: float | None = None,
    sp_alis: float | None = None, sp_satis: float | None = None,
    commit: bool = True,
) -> CurrencyRateHistory:
    """Aynı (tarih, kod) için tek kayıt olacak şekilde ekler/günceller.
    Verilmeyen (None) alanlara dokunulmaz."""
    code = code.upper()
    row = db.scalar(
        select(CurrencyRateHistory).where(
            CurrencyRateHistory.rate_date == rate_date,
            CurrencyRateHistory.code == code,
            CurrencyRateHistory.is_deleted == False,  # noqa: E712
        ),
    )
    if row is None:
        row = CurrencyRateHistory(rate_date=rate_date, code=code)
        db.add(row)
    if mb_alis is not None:
        row.mb_alis = mb_alis
    if mb_satis is not None:
        row.mb_satis = mb_satis
    if sp_alis is not None:
        row.sp_alis = sp_alis
    if sp_satis is not None:
        row.sp_satis = sp_satis
    if commit:
        db.commit()
    return row


def get_rate_history_range(
    db, date_from: date, date_to: date | None = None, code: str | None = None,
) -> list[CurrencyRateHistory]:
    date_to = date_to or date_from
    conditions = [
        CurrencyRateHistory.rate_date >= date_from,
        CurrencyRateHistory.rate_date <= date_to,
        CurrencyRateHistory.is_deleted == False,  # noqa: E712
    ]
    if code:
        conditions.append(CurrencyRateHistory.code == code.upper())
    return db.scalars(
        select(CurrencyRateHistory).where(*conditions).order_by(
            CurrencyRateHistory.rate_date, CurrencyRateHistory.code,
        ),
    ).all()


def delete_rate_history(
    db, date_from: date, date_to: date | None = None, code: str | None = None,
) -> int:
    """Belirli tarih / tarih aralığı (istenirse tek döviz ile sınırlı) için
    geçmiş kur kayıtlarını siler (soft-delete). Silinen kayıt sayısını döner."""
    rows = get_rate_history_range(db, date_from, date_to, code)
    for r in rows:
        r.is_deleted = True
    if rows:
        db.commit()
    return len(rows)


def _history_kwargs(kind: str, alis: float | None, satis: float | None) -> dict[str, float | None]:
    if kind == SOURCE_TCMB:
        return {"mb_alis": alis, "mb_satis": satis}
    if kind == SOURCE_SERBEST:
        return {"sp_alis": alis, "sp_satis": satis}
    return {}


def refresh_and_apply(db, for_date: date | None = None) -> RateFetchResult:
    """Ayarlarda kayıtlı kaynağı okur, kurları çeker; hem `Currency.rate`'i
    (güncel kur) hem `CurrencyRateHistory`'yi (gün bazlı) günceller.

    Sonucu ve son güncelleme zamanını/hatasını da ayarlara yazar — Döviz &
    Kur panelinde "Son Güncelleme" bilgisi olarak gösterilir.
    """
    kind, url = get_source_config(db)
    target_date = for_date or date.today()
    result = fetch_rates(kind, url, for_date=target_date)
    if result.success and result.rates:
        updated = apply_rates_to_db(db, result.rates)
        for code, (alis, satis) in result.rates_full.items():
            kwargs = _history_kwargs(kind, alis, satis)
            if kwargs:
                upsert_rate_history(db, target_date, code, commit=False, **kwargs)
        db.commit()
        result.message = (
            f"{updated} döviz kuru güncellendi ({target_date.strftime('%d.%m.%Y')})."
        )
        set_setting(db, KEY_LAST_UPDATE, datetime.now().strftime("%d.%m.%Y %H:%M:%S"))
        set_setting(db, KEY_LAST_ERROR, "")
    elif not result.success:
        set_setting(db, KEY_LAST_ERROR, result.message)
    return result


def bulk_fetch_range(db, date_from: date, date_to: date) -> RateFetchResult:
    """Tarih aralığındaki her gün için seçili kaynaktan kur çekip geçmişe yazar.

    Not: Serbest piyasa kaynakları genelde geçmişe dönük sorgu desteklemez;
    bu kaynak seçiliyken her gün için aynı (o anki) sayfa değerleri kullanılır
    — TCMB'de ise gerçek arşiv verisi (`tcmb_url_for_date`) kullanılır.
    """
    kind, url = get_source_config(db)
    if kind == SOURCE_MANUEL:
        return RateFetchResult(
            success=False, message="Manuel kaynakta toplu çekme yapılmaz; kurları elle girin.",
        )
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    gun_sayisi = 0
    guncellenen = 0
    hatalar: list[str] = []
    d = date_from
    while d <= date_to:
        result = fetch_rates(kind, url, for_date=d)
        if result.success and result.rates_full:
            for code, (alis, satis) in result.rates_full.items():
                kwargs = _history_kwargs(kind, alis, satis)
                if kwargs:
                    upsert_rate_history(db, d, code, commit=False, **kwargs)
            gun_sayisi += 1
            guncellenen += len(result.rates)
        else:
            hatalar.append(f"{d.strftime('%d.%m.%Y')}: {result.message}")
        d += timedelta(days=1)
    db.commit()

    set_setting(db, KEY_LAST_UPDATE, datetime.now().strftime("%d.%m.%Y %H:%M:%S"))
    set_setting(db, KEY_LAST_ERROR, "; ".join(hatalar[:5]) if hatalar else "")

    msg = f"{gun_sayisi} gün için kur çekildi ({guncellenen} kayıt)."
    if hatalar:
        msg += f" {len(hatalar)} günde hata oluştu."
    return RateFetchResult(success=gun_sayisi > 0, message=msg)


def startup_autofetch(db) -> RateFetchResult | None:
    """Uygulama açılışında BİR KEZ çağrılmalıdır: seçili kaynak manuel
    değilse ve bugün için henüz çekim yapılmadıysa otomatik günceller.
    Bugün için zaten bir güncelleme yapılmışsa (KEY_LAST_UPDATE bugünün
    tarihiyle başlıyorsa) tekrar ağ isteği yapmaz ve None döner."""
    kind, _ = get_source_config(db)
    if kind == SOURCE_MANUEL:
        return None
    last = get_setting(db, KEY_LAST_UPDATE)
    today_str = date.today().strftime("%d.%m.%Y")
    if last and last.startswith(today_str):
        return None
    return refresh_and_apply(db)
