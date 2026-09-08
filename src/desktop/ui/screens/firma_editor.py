"""
TOYA ERP - Firma (Şirket) Tanım Editörü

`DefinitionEditorScreen` yapılandırmasıyla kurulan tam ekran firma kartı.
Alan grupları Wolvox "Şirket Kayıt İşlemleri" / DIA "Firma Detayı" ile
uyumludur. Kayıt/okuma `CompanyService` üzerinden yapılır.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QMessageBox, QVBoxLayout

from src.desktop.services.company_service import CompanyService
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen

COMPANY_TYPES = ["Şahıs", "Tüzel", "Limited Şirket", "Anonim Şirket", "Kooperatif", "Diğer"]
CURRENCIES = ["TRY", "USD", "EUR", "GBP"]

FIRMA_TABS: list[dict] = [
    {
        "title": "Kimlik",
        "fields": [
            {"key": "code", "label": "Firma Kodu", "type": "text",
             "required": True, "lock_on_edit": True, "placeholder": "örn. 000"},
            {"key": "short_name", "label": "Kısa Ad", "type": "text", "required": True},
            {"key": "title", "label": "Resmi / Ticari Ünvan", "type": "text"},
            {"key": "company_type", "label": "Şirket Tipi", "type": "combo",
             "options": COMPANY_TYPES},
            {"key": "tax_office", "label": "Vergi Dairesi", "type": "text"},
            {"key": "tax_office_code", "label": "V.D. Kodu", "type": "text"},
            {"key": "tax_number", "label": "Vergi No / TCKN", "type": "text"},
            {"key": "mersis_no", "label": "MERSİS No", "type": "text"},
            {"key": "trade_registry_no", "label": "Ticaret Sicil No", "type": "text"},
            {"key": "nace_code", "label": "NACE / Faaliyet Kodu", "type": "text"},
            {"key": "sgk_no", "label": "SGK İşyeri Sicil No", "type": "text"},
            {"key": "founded_at", "label": "Kuruluş Tarihi", "type": "text",
             "placeholder": "GG.AA.YYYY"},
        ],
    },
    {
        "title": "Adres & İletişim",
        "fields": [
            {"key": "address", "label": "Açık Adres", "type": "multiline"},
            {"key": "district", "label": "İlçe", "type": "text"},
            {"key": "city", "label": "İl", "type": "text"},
            {"key": "postal_code", "label": "Posta Kodu", "type": "text"},
            {"key": "country", "label": "Ülke", "type": "text"},
            {"key": "phone1", "label": "Telefon 1", "type": "text"},
            {"key": "phone2", "label": "Telefon 2", "type": "text"},
            {"key": "fax", "label": "Faks", "type": "text"},
            {"key": "email", "label": "Genel E-Posta", "type": "text"},
            {"key": "accounting_email", "label": "Muhasebe / e-Fatura E-Posta", "type": "text"},
            {"key": "website", "label": "Web Sitesi", "type": "text"},
            {"key": "kep_address", "label": "KEP Adresi", "type": "text"},
        ],
    },
    {
        "title": "Yetkili",
        "fields": [
            {"key": "authorized_person", "label": "Yetkili Ad Soyad", "type": "text"},
            {"key": "authorized_title", "label": "Ünvanı", "type": "text"},
            {"key": "authorized_phone", "label": "Yetkili Telefon", "type": "text"},
        ],
    },
    {
        "title": "Banka Hesapları",
        "fields": [
            {"key": "bank_accounts", "label": "Banka Hesapları", "type": "subtable",
             "columns": [
                 {"key": "banka", "label": "Banka"},
                 {"key": "sube", "label": "Şube"},
                 {"key": "hesap_no", "label": "Hesap No"},
                 {"key": "iban", "label": "IBAN"},
                 {"key": "para_birimi", "label": "Para Birimi"},
             ]},
        ],
    },
    {
        "title": "e-Belge",
        "fields": [
            {"key": "e_invoice_enabled", "label": "e-Fatura Mükellefi", "type": "bool",
             "text": "Evet"},
            {"key": "e_archive_enabled", "label": "e-Arşiv Mükellefi", "type": "bool",
             "text": "Evet"},
            {"key": "e_dispatch_enabled", "label": "e-İrsaliye Mükellefi", "type": "bool",
             "text": "Evet"},
            {"key": "gib_alias", "label": "GİB Etiketi / Alias", "type": "text"},
            {"key": "integrator", "label": "Entegratör", "type": "text"},
        ],
    },
    {
        "title": "Varsayılanlar & Görsel",
        "fields": [
            {"key": "default_currency", "label": "Varsayılan Para Birimi", "type": "combo",
             "options": CURRENCIES},
            {"key": "default_vat_rate", "label": "Varsayılan KDV %", "type": "int",
             "min": 0, "max": 100},
            {"key": "fiscal_year_start", "label": "Mali Yıl Başı", "type": "text",
             "placeholder": "GG.AA"},
            {"key": "logo_base64", "label": "Logo (baskı)", "type": "image"},
            {"key": "stamp_base64", "label": "Kaşe / İmza", "type": "image"},
            {"key": "notes", "label": "Not", "type": "multiline"},
            {"key": "is_active", "label": "Aktif", "type": "bool", "text": "Aktif"},
        ],
    },
]


class FirmaEditorDialog(QDialog):
    """Firma editörünü maksimize bir dialog içinde açar."""

    def __init__(self, db_session=None, company_id: int | None = None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.company_id = company_id
        self.service = CompanyService(db_session=db_session)
        self.saved_company_id: int | None = None

        self.setWindowTitle("Firma Detayı")
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)

        self.editor = DefinitionEditorScreen(title="Firma Detayı", tabs=FIRMA_TABS, parent=self)
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self.reject)
        self.editor.saved.connect(self._on_save)

        if company_id:
            company = self.service.get(company_id)
            if company:
                self.editor.set_data(self.service.to_dict(company), is_edit=True)
        else:
            self.editor.set_data(CompanyService.blank_company(), is_edit=False)

        self.showMaximized()

    def _on_save(self, payload: dict):
        res = self.service.save(payload, company_id=self.company_id)
        if not res.success:
            QMessageBox.critical(self, "Kayıt Hatası", res.error or "Firma kaydedilemedi.")
            return
        self.saved_company_id = res.company_id
        QMessageBox.information(self, "Kaydedildi", f"Firma kaydedildi: {res.code}")
        self.accept()
