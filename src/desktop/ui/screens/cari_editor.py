"""
TOYA ERP - Cari (Müşteri / Tedarikçi) Kart Editörü

`DefinitionEditorScreen` yapılandırmasıyla kurulan tam ekran cari kartı.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QMessageBox, QVBoxLayout

from src.desktop.services.customer_service import CustomerService
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen

GROUPS = ["Müşteri", "Tedarikçi", "Müşteri + Tedarikçi", "Personel", "Diğer"]

CARI_TABS: list[dict] = [
    {
        "title": "Genel",
        "fields": [
            {"key": "customer_code", "label": "Cari Kodu", "type": "text",
             "lock_on_edit": True, "placeholder": "boş bırakılırsa otomatik"},
            {"key": "fullname", "label": "Ünvan / Ad Soyad", "type": "text",
             "required": True},
            {"key": "nickname", "label": "Kısa Ad / Takma Ad", "type": "text"},
            {"key": "group_name", "label": "Cari Grubu", "type": "combo",
             "options": GROUPS},
            {"key": "sub_group_1", "label": "Alt Grup 1", "type": "text"},
            {"key": "sub_group_2", "label": "Alt Grup 2", "type": "text"},
            {"key": "authorized_person", "label": "Yetkili Kişi", "type": "text"},
            {"key": "is_active", "label": "Aktif", "type": "bool", "text": "Aktif"},
        ],
    },
    {
        "title": "İletişim",
        "fields": [
            {"key": "phone", "label": "Telefon 1", "type": "text"},
            {"key": "phone2", "label": "Telefon 2", "type": "text"},
            {"key": "phone_home", "label": "Ev Telefonu", "type": "text"},
            {"key": "fax", "label": "Faks", "type": "text"},
            {"key": "email", "label": "E-Posta", "type": "text"},
            {"key": "website", "label": "Web Sitesi", "type": "text"},
        ],
    },
    {
        "title": "Adres",
        "fields": [
            {"key": "address", "label": "Adres 1", "type": "multiline"},
            {"key": "address2", "label": "Adres 2 (Sevk)", "type": "multiline"},
            {"key": "district", "label": "İlçe", "type": "text"},
            {"key": "city", "label": "İl", "type": "text"},
            {"key": "region", "label": "Bölge", "type": "text"},
            {"key": "postcode", "label": "Posta Kodu", "type": "text"},
            {"key": "country", "label": "Ülke", "type": "text"},
        ],
    },
    {
        "title": "Vergi & e-Belge",
        "fields": [
            {"key": "tax_office", "label": "Vergi Dairesi", "type": "text"},
            {"key": "tax_number", "label": "Vergi No / TCKN", "type": "text"},
            {"key": "efatura_user", "label": "e-Fatura Kullanıcı", "type": "text"},
            {"key": "efatura_mailbox", "label": "e-Fatura Posta Kutusu (Etiket)", "type": "text"},
        ],
    },
    {
        "title": "Özel Kodlar & Notlar",
        "fields": [
            {"key": "special_code_1", "label": "Özel Kod 1", "type": "text"},
            {"key": "special_code_2", "label": "Özel Kod 2", "type": "text"},
            {"key": "special_code_3", "label": "Özel Kod 3", "type": "text"},
            {"key": "notes", "label": "Notlar", "type": "multiline"},
        ],
    },
]


class CariEditorDialog(QDialog):
    def __init__(self, db_session=None, customer_id: int | None = None,
                 company_id: int | None = None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.customer_id = customer_id
        self.service = CustomerService(db_session, company_id=company_id)
        self.saved_customer_id: int | None = None

        self.setWindowTitle("Cari Kartı")
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        self.editor = DefinitionEditorScreen(title="Cari Kartı", tabs=CARI_TABS, parent=self)
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self.reject)
        self.editor.saved.connect(self._on_save)

        if customer_id:
            c = self.service.get(customer_id)
            if c:
                self.editor.set_data(self.service.to_dict(c), is_edit=True)
        else:
            self.editor.set_data(CustomerService.blank_customer(), is_edit=False)

        self.showMaximized()

    def _on_save(self, payload: dict):
        res = self.service.save(payload, customer_id=self.customer_id)
        if not res.success:
            QMessageBox.critical(self, "Kayıt Hatası", res.error or "Cari kaydedilemedi.")
            return
        self.saved_customer_id = res.customer_id
        QMessageBox.information(self, "Kaydedildi", f"Cari kaydedildi: {payload['fullname']}")
        self.accept()
