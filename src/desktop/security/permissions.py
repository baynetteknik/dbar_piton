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
        ("print", "Yazdır / PDF"),
    ]),
    ("fatura", "Fatura", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("print", "Yazdır / PDF"), ("einvoice", "e-Fatura / e-Arşiv Gönder"),
    ]),
    ("cari", "Cari Kart", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("balance", "Bakiye / Ekstre"),
    ]),
    ("stok", "Stok Kartı", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("price", "Fiyat Değiştir"), ("movement", "Stok Hareketi"),
    ]),
    ("kasa", "Kasa", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("movement", "Kasa Hareketi"),
    ]),
    ("banka", "Banka & POS", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("movement", "Banka Hareketi"),
    ]),
    ("cek_senet", "Çek / Senet", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"),
        ("delete", "Sil"), ("movement", "İşlem / Tahsil"),
    ]),
    ("personel", "Personel", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"), ("delete", "Sil"),
    ]),
    ("gorev", "Görevler", [
        ("view", "Görüntüle"), ("create", "Yeni"), ("edit", "Düzenle"), ("delete", "Sil"),
    ]),
    ("doviz", "Döviz & Kur", [
        ("view", "Görüntüle"), ("fetch", "Kur Çek (TCMB/SP)"),
        ("edit_rates", "Kur Gir / Düzenle"), ("settings", "Kaynak Yönetimi"),
    ]),
    ("numara", "Belge & Seri Numaralandırma", [
        ("view", "Görüntüle"), ("create", "Yeni Seri"), ("edit", "Seri Düzenle"),
        ("delete", "Seri Sil"), ("reset_counter", "Sayaç Düzenle"),
        ("gaps", "Boşluk Analizi"),
    ]),
    ("yedekleme", "Yedekleme Merkezi", [
        ("view", "Görüntüle"), ("backup", "Yedek Al"), ("restore", "Geri Yükle"),
        ("settings", "Yedek Ayarları"),
    ]),
    ("portal", "Online Teklif Portalı", [
        ("view", "Görüntüle"), ("deploy", "Portal Dağıtım / FTP"),
        ("publish", "Teklif Yayınla"),
    ]),
    ("tasarimci", "Form / Ekran Tasarımcısı", [
        ("view", "Görüntüle"), ("create", "Yeni Tasarım"),
        ("edit", "Tasarım Düzenle"), ("delete", "Tasarım Sil"),
        ("export", "Şablon Dışa Aktar"),
    ]),
    ("belge_kilit", "Belge Kilitleme & İptal", [
        ("lock", "Belge Kilitle"), ("unlock", "Kilit Aç"), ("cancel", "Belge İptal Et"),
    ]),
    ("rapor", "Raporlar", [
        ("view", "Görüntüle"), ("export", "Dışa Aktar (Excel/PDF)"),
    ]),
    ("ayarlar", "Genel Ayarlar", [
        ("view", "Görüntüle"), ("firma", "Firma Tanımları"),
        ("numara", "Numara & Seri Yönetimi"),
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
            "stok.view", "doviz.view", "portal.publish", "rapor.view", "rapor.export",
            "gorev.view", "gorev.create", "gorev.edit",
        ],
        False,
    ),
    "Muhasebe": (
        "Fatura / cari / rapor işlemleri",
        [
            "fatura.view", "fatura.create", "fatura.edit", "fatura.print", "fatura.einvoice",
            "irsaliye.view", "irsaliye.print",
            "cari.view", "cari.create", "cari.edit", "cari.delete", "cari.balance",
            "kasa.view", "kasa.create", "kasa.edit", "kasa.delete", "kasa.movement",
            "banka.view", "banka.create", "banka.edit", "banka.delete", "banka.movement",
            "cek_senet.view", "cek_senet.create", "cek_senet.edit", "cek_senet.movement",
            "stok.view", "doviz.view", "doviz.fetch", "doviz.edit_rates",
            "numara.view", "rapor.view", "rapor.export",
            "gorev.view", "gorev.create", "gorev.edit",
        ],
        False,
    ),
    "Depo": (
        "İrsaliye ve stok hareketleri",
        [
            "irsaliye.view", "irsaliye.create", "irsaliye.edit", "irsaliye.print",
            "stok.view", "stok.movement", "siparis.view",
            "gorev.view", "gorev.create", "gorev.edit",
        ],
        False,
    ),
    "Salt Okunur": (
        "Yalnızca görüntüleme",
        [
            "teklif.view", "siparis.view", "irsaliye.view", "fatura.view",
            "cari.view", "stok.view", "kasa.view", "banka.view",
            "doviz.view", "rapor.view", "gorev.view",
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
