"""
TOYA ERP - Yetki Kapısı (Permission Gate) yardımcıları

UI öğelerini (buton, sekme, menü eylemi) aktif kullanıcının rol yetkilerine
göre etkin/pasif yapar. PermissionManager.role_changed sinyaline bağlanarak
kullanıcı/rol değişince canlı güncellenir.
"""

from __future__ import annotations

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QWidget

from src.desktop.managers.permission_manager import PermissionManager

#: Modül / menü adı  ->  gerekli yetki kodu
MODULE_PERMISSIONS: dict[str, str] = {
    # Teklif
    "Teklif Yönetimi": "teklif.view",
    "Teklifler": "teklif.view",
    "Açık Teklifler": "teklif.view",
    "Yeni Teklif Hazırla": "teklif.create",
    # Sipariş
    "Sipariş Yönetimi": "siparis.view",
    "Siparişler": "siparis.view",
    "Bekleyen Sipariş": "siparis.view",
    # Fatura
    "Faturalar": "fatura.view",
    "Hızlı Fatura": "fatura.create",
    "Bugün Ciro": "fatura.view",
    # Cari
    "Müşteriler & Cariler": "cari.view",
    "Cari": "cari.view",
    "Müşteriler": "cari.view",
    "Cari Bakiye": "cari.balance",
    "Cari Analiz": "cari.view",
    # Stok
    "Ürün Yönetimi": "stok.view",
    "Stok Kartları": "stok.view",
    "Fiyat Politikaları": "stok.price",
    "Fiyat Politikalari": "stok.price",
    # Finans (henüz PoC — muhasebe yetkisi gerektirir)
    "Kasa Yönetimi": "fatura.view",
    "Çek / Senet": "fatura.view",
    "Banka Hesapları": "fatura.view",
    # İnsan Kaynakları (henüz PoC)
    "Personel": "ayarlar.kullanici",
    # Raporlar / Ayarlar
    "İşlem Günlükleri": "ayarlar.sistem",
    "Genel Ayarlar": "ayarlar.view",
    "Sistem Ayarları": "ayarlar.view",
    "Ekran & Grid Tanımları": "ayarlar.sistem",
}


def can(perm_code: str | None) -> bool:
    """Aktif kullanıcı bu yetkiye sahip mi?"""
    return PermissionManager().has_permission(perm_code)


def module_permission(menu_name: str) -> str | None:
    return MODULE_PERMISSIONS.get(menu_name)


def gate(widget: QWidget | QAction, perm_code: str | None, *, hide: bool = False) -> None:
    """
    `widget`'ı yetkiye bağlar. Yetki yoksa disable (hide=True ise gizler).
    Rol değişince otomatik yeniden değerlendirilir.
    """
    if not perm_code:
        return
    pm = PermissionManager()

    def _apply():
        ok = pm.has_permission(perm_code)
        widget.setEnabled(ok)
        if hide:
            widget.setVisible(ok)

    _apply()
    # Aynı bağlantı iki kez kurulmasın diye tekil bağla
    try:
        pm.role_changed.connect(lambda *_: _apply())
    except Exception:  # noqa: BLE001
        pass


def gate_many(pairs: list[tuple[QWidget | QAction, str | None]], *, hide: bool = False) -> None:
    for w, code in pairs:
        gate(w, code, hide=hide)
