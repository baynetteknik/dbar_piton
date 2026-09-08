"""
TOYA ERP - Yetki Kataloğu (Permission Catalog)

Sistemde tanımlanabilir tüm yetkilerin tek kaynağı. Rol editöründeki yetki
ağacı ve PermissionManager.has_permission(...) bu kataloğa dayanır.

Yetki kodu biçimi: "<modul>.<eylem>"  (örn. "teklif.create")
Özel kod "*"  -> tüm yetkiler.
"""

from __future__ import annotations

# (modül_kodu, modül_adı, [(eylem_kodu, eylem_adı), ...])
PERMISSION_GROUPS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("teklif", "Teklif", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("print", "Yazdır / PDF"), ("send", "Gönder / E-Posta"),
        ("convert", "Siparişe Dönüştür"),
    ]),
    ("siparis", "Sipariş", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("print", "Yazdır / PDF"), ("convert", "Faturaya Dönüştür"),
    ]),
    ("irsaliye", "İrsaliye", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"), ("delete", "Sil"),
    ]),
    ("fatura", "Fatura", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("einvoice", "e-Fatura Gönder"),
    ]),
    ("cari", "Cari Kart", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("balance", "Bakiye / Ekstre"),
    ]),
    ("stok", "Stok Kartı", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("price", "Fiyat Değiştir"), ("movement", "Stok Hareketi"),
    ]),
    ("rapor", "Raporlar", [
        ("view", "Görüntüle"), ("export", "Dışa Aktar (Excel/PDF)"),
    ]),
    ("ayarlar", "Genel Ayarlar", [
        ("view", "Görüntüle"), ("firma", "Firma Tanımları"),
        ("kullanici", "Kullanıcı & Yetki"), ("tanimlar", "Tüm Tanımlar"),
        ("sistem", "Sistem / Git"),
    ]),
]

#: Tüm geçerli yetki kodları
ALL_PERMISSIONS: list[str] = [
    f"{mod}.{act}"
    for mod, _mod_name, actions in PERMISSION_GROUPS
    for act, _act_name in actions
]

#: Uygulamayla birlikte gelen varsayılan roller.
#: {rol_adı: (açıklama, yetki_listesi, is_system)}
DEFAULT_ROLES: dict[str, tuple[str, list[str], bool]] = {
    "Yönetici": ("Tüm yetkiler", ["*"], True),
    "Satış": (
        "Teklif / sipariş / cari işlemleri",
        [
            "teklif.view", "teklif.create", "teklif.edit", "teklif.print",
            "teklif.send", "teklif.convert",
            "siparis.view", "siparis.create", "siparis.edit", "siparis.print",
            "cari.view", "cari.create", "cari.edit", "cari.balance",
            "stok.view", "rapor.view", "rapor.export",
        ],
        False,
    ),
    "Muhasebe": (
        "Fatura / cari / rapor işlemleri",
        [
            "fatura.view", "fatura.create", "fatura.edit", "fatura.einvoice",
            "irsaliye.view",
            "cari.view", "cari.create", "cari.edit", "cari.delete", "cari.balance",
            "stok.view", "rapor.view", "rapor.export",
        ],
        False,
    ),
    "Depo": (
        "İrsaliye ve stok hareketleri",
        [
            "irsaliye.view", "irsaliye.create", "irsaliye.edit",
            "stok.view", "stok.movement", "siparis.view",
        ],
        False,
    ),
    "Salt Okunur": (
        "Yalnızca görüntüleme",
        [
            "teklif.view", "siparis.view", "irsaliye.view", "fatura.view",
            "cari.view", "stok.view", "rapor.view",
        ],
        False,
    ),
}


def permission_label(code: str) -> str:
    """'teklif.create' -> 'Teklif › Yeni'"""
    if code == "*":
        return "Tüm Yetkiler"
    mod, _, act = code.partition(".")
    for m, m_name, actions in PERMISSION_GROUPS:
        if m == mod:
            for a, a_name in actions:
                if a == act:
                    return f"{m_name} › {a_name}"
            return f"{m_name} › {act}"
    return code
