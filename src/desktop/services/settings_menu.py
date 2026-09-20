"""
TOYA ERP - Genel Ayarlar Menü Kodları, Arama ve Sıralama Kalıcılığı

Her menü, her işlem (eylem) ve sağ paneldeki her bölüm bir KOD taşır:
    grup          sys.set.10          (Şirket Tanımları)
    menü          sys.set.105         (Çalışma Dönemi)
    menü işlemi   sys.set.105.01      (o menünün 1. işlemi)
    sağ bölüm     sys.rp.02           (Filtreleme & Arama)
    sağ işlem     sys.rp.02.01
Arama kod ve isme göre çalışır; Türkçe harfler duyarsızdır ("sirket" → "ŞİRKET", "105" → sys.set.105).
Sağ panel bölüm sıralaması kullanıcıya göre saklanır (sürükle-bırak sonucu).
"""

from __future__ import annotations

import json
from typing import Iterable

from src.desktop.services.settings_store import get_setting, set_setting

SCREEN_CODE = "sys.set.001"

#: grup adı → grup kodu
GROUP_CODES: dict[str, str] = {
    "ŞİRKET TANIMLARI": "sys.set.10",
    "KULLANICI & YETKİ": "sys.set.20",
    "FİNANS TANIMLARI": "sys.set.30",
    "STOK TANIMLARI": "sys.set.40",
    "CARİ TANIMLARI": "sys.set.50",
    "SİSTEM": "sys.set.60",
}

#: panel_id → menü kodu
ITEM_CODES: dict[str, str] = {
    "firma_bilgileri": "sys.set.101", "sube_tanimlari": "sys.set.102", "depo_tanimlari": "sys.set.103",
    "doviz_kur": "sys.set.104", "calisma_donemi": "sys.set.105",
    "kullanicilar": "sys.set.201", "roller": "sys.set.202", "yetkiler": "sys.set.203",
    "odeme_planlari": "sys.set.301", "fiyat_listeleri": "sys.set.302",
    "stok_kategoriler": "sys.set.401", "stok_markalar": "sys.set.402", "birim_tanimlari": "sys.set.403",
    "stok_ozel_alanlar": "sys.set.404",
    "cari_gruplari": "sys.set.501", "cari_ozel_alanlar": "sys.set.502",
    "cms_baglantilari": "sys.set.601", "eposta_smtp": "sys.set.602", "online_portal": "sys.set.603",
    "portal_yayin": "sys.set.604", "yedek_merkezi": "sys.set.605", "portal_yedek": "sys.set.606",
    "guvenlik": "sys.set.607", "sayi_bicimi": "sys.set.608", "gorunum_profilleri": "sys.set.609",
    "ekran_grid": "sys.set.610", "surum_git": "sys.set.611",
}

#: sağ panel bölüm anahtarı → (kod, varsayılan başlık)
SIDEBAR_SECTIONS: dict[str, tuple[str, str]] = {
    "islemler": ("sys.rp.01", "İŞLEMLER"),
    "filtre": ("sys.rp.02", "FİLTRE & ARAMA"),
    "yazdir": ("sys.rp.03", "YAZDIR & AKTAR"),
    "hizli": ("sys.rp.04", "HIZLI İŞLEMLER"),
    "doviz": ("sys.rp.05", "DÖVİZ İŞLEMLERİ"),
    "kur_rapor": ("sys.rp.06", "KUR RAPORLARI"),
    "git_baglanti": ("sys.rp.07", "GİT BAĞLANTISI"),
}
DEFAULT_SIDEBAR_ORDER = list(SIDEBAR_SECTIONS)

KEY_CODE_MODE = "ui.genel_ayarlar.kod_gosterim"
#: kod gösterim modları: ipucu = yalnızca üzerine gelince (varsayılan), rozet = adın altında, gizli = hiç
CODE_MODES = (("ipucu", "💬 İpucu"), ("rozet", "🏷 Rozet"), ("gizli", "🚫 Gizli"))
KEY_SIDEBAR_ORDER = "ui.genel_ayarlar.sag_panel_sirasi"

_FOLD = str.maketrans({"İ": "i", "I": "i", "ı": "i", "Ç": "c", "ç": "c", "Ğ": "g", "ğ": "g",
                       "Ö": "o", "ö": "o", "Ş": "s", "ş": "s", "Ü": "u", "ü": "u"})


def fold(text: str) -> str:
    """Büyük/küçük harf ve Türkçe karakter duyarsız karşılaştırma biçimi."""
    return (text or "").translate(_FOLD).lower()


def matches(query: str, *fields: str) -> bool:
    """Sorgunun HER kelimesi alanlardan en az birinde geçiyorsa True. Boş sorgu her şeyle eşleşir."""
    words = fold(query).split()
    if not words:
        return True
    hay = " | ".join(fold(f) for f in fields if f)
    return all(w in hay for w in words)


def item_code(panel_id: str) -> str:
    return ITEM_CODES.get(panel_id, "")


def action_code(panel_id: str, index: int) -> str:
    """Menünün `index`. (1'den başlar) işleminin kodu; menü kodu yoksa boş."""
    base = item_code(panel_id)
    return f"{base}.{index:02d}" if base else ""


def with_code(text: str, code: str, show: bool = True) -> str:
    return f"{text}  [{code}]" if (show and code) else text


def normalize_order(saved: Iterable[str] | None, available: Iterable[str] = DEFAULT_SIDEBAR_ORDER) -> list[str]:
    """Kayıtlı sırayı geçerli anahtarlara uygular: bilinmeyenler atılır, eksik (yeni) bölümler sona eklenir."""
    avail = list(available)
    out: list[str] = []
    for k in saved or []:
        if k in avail and k not in out:
            out.append(k)
    out += [k for k in avail if k not in out]   # kayıtta olmayan (yeni) bölümler sona eklenir
    return out


class SidebarOrderStore:
    """Sağ panel bölüm sırasını (kullanıcıya göre) ayarlarda saklar."""

    def __init__(self, db, user: str = "") -> None:
        self.db = db
        self.key = KEY_SIDEBAR_ORDER + (f".{user}" if user else "")

    def load(self) -> list[str]:
        raw = get_setting(self.db, self.key, "") or ""
        try:
            data = json.loads(raw) if raw else []
        except ValueError:
            data = []
        return normalize_order(data if isinstance(data, list) else [])

    def save(self, order: list[str]) -> None:
        set_setting(self.db, self.key, json.dumps(normalize_order(order), ensure_ascii=False))

    def reset(self) -> None:
        set_setting(self.db, self.key, "")


def code_mode(db) -> str:
    v = get_setting(db, KEY_CODE_MODE, "ipucu") or "ipucu"
    return v if v in dict(CODE_MODES) else "ipucu"


def set_code_mode(db, mode: str) -> None:
    set_setting(db, KEY_CODE_MODE, mode if mode in dict(CODE_MODES) else "ipucu")


def tooltip(name: str, code: str, mode: str = "ipucu", extra: str = "") -> str:
    """Üzerine gelince görünen ipucu (zengin metin). Mod 'gizli' ise kod yazılmaz."""
    head = f"<b>[{code}]</b>&nbsp;&nbsp;{name}" if (code and mode != "gizli") else name
    return head + (f"<br><i>{extra}</i>" if extra else "")
