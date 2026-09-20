"""
TOYA ERP - Firma (Şirket) Tanım Editörü

`DefinitionEditorScreen` (tpl.card.001 v2 — çok kolonlu bölümlü düzen) ile
Cari/Stok Kartı ile aynı kalıpta kurulan tam ekran firma kartı: numaralı
bölümler, sol panelde "BÖLÜMLER" nav listesi gizli (sekmeler zaten aynı
gezinmeyi sağlıyor) — yalnızca "İŞLEMLER" grubu altında her bölümün kendi
hızlı ekleme butonu (Dönem / Yetkili / Ortak / Banka Hesabı), sağda "Ara"
(arama) ve "Yazdır & Aktarım" (Excel/PDF/İçe Aktar/Rapor) panelleri —
`FilterWidget` + `ExportWidget` bileşenlerinden kurulur, altta VAZGEÇ /
KAYDET (+ Kaydet ve Yeni).

Dönemler, Yetkililer, Ortaklar ve Banka Hesapları artık çoklu kayıt destekleyen
"subtable" alanlarıdır (`DefinitionEditorScreen._SubTableField` — belge kalem/
masraf gridleriyle aynı standart `FilterableTableView` çekirdeğini kullanır);
modelde JSON metin (`periods_json`, `authorized_persons_json`,
`partners_json`, `bank_accounts_json`) olarak saklanır.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox, QVBoxLayout

from src.desktop.services.company_service import CompanyService
from src.desktop.services.currency_catalog import CURRENCY_CODES
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
from src.desktop.ui.widgets.export_widget import ExportWidget
from src.desktop.ui.widgets.filter_widget import FilterWidget

logger = logging.getLogger(__name__)

COMPANY_TYPES = ["Şahıs", "Tüzel", "Limited Şirket", "Anonim Şirket", "Kooperatif", "Diğer"]
#: Henüz hiç döviz tanımlanmamışsa (Genel Ayarlar > Döviz & Kur boşsa) "Döviz
#: Birimi" combosunun düşeceği yedek liste — ISO 4217 kataloğunun tamamı (bkz.
#: `currency_catalog.py`), en sık kullanılanlar (TRY/USD/EUR/GBP) başta.
CURRENCIES = CURRENCY_CODES

# Çoklu kayıt alanları: {form_key: (Excel sayfa adı, [{"key","label"}...])}
_GRID_GROUPS: dict[str, tuple[str, list[dict]]] = {
    "periods": ("Dönemler", [
        {"key": "ad", "label": "Dönem Adı"},
        {"key": "baslangic", "label": "Başlangıç Tarihi"},
        {"key": "bitis", "label": "Bitiş Tarihi"},
        {"key": "aktif", "label": "Aktif (Evet/Hayır)"},
    ]),
    "authorized_persons": ("Yetkililer", [
        {"key": "ad_soyad", "label": "Ad Soyad"},
        {"key": "unvan", "label": "Ünvanı"},
        {"key": "telefon", "label": "Telefon"},
        {"key": "e_posta", "label": "E-Posta"},
    ]),
    "partners": ("Ortaklar", [
        {"key": "ad_soyad", "label": "Ad Soyad"},
        {"key": "tc_vergi_no", "label": "TC / Vergi No"},
        {"key": "pay_orani", "label": "Pay Oranı (%)"},
        {"key": "gorev", "label": "Görevi"},
    ]),
    "bank_accounts": ("Banka Hesapları", [
        {"key": "banka", "label": "Banka"},
        {"key": "sube", "label": "Şube"},
        {"key": "hesap_no", "label": "Hesap No"},
        {"key": "iban", "label": "IBAN"},
        {"key": "para_birimi", "label": "Para Birimi"},
    ]),
}


def _build_firma_tabs(db_session) -> list[dict]:
    """Para Birimi alanı Döviz Tanımları'nda (Genel Ayarlar > Şirket
    Tanımları) kayıtlı aktif dövizleri dinamik olarak listeler."""

    def _load_active_currencies() -> list[str]:
        if not db_session:
            return CURRENCIES
        try:
            from sqlalchemy import select
            from src.core.models import Currency
            codes = db_session.scalars(
                select(Currency.code).where(
                    Currency.is_deleted == False, Currency.is_active == True,  # noqa: E712
                ).order_by(Currency.code),
            ).all()
            return list(codes) or CURRENCIES
        except Exception:  # noqa: BLE001
            return CURRENCIES

    return [
        {
            "title": "Kimlik",
            "bands": [
                {"sections": [
                    {"title": "1. Firma Kimliği", "columns": 2, "stretch": 6, "fields": [
                        {"key": "code", "label": "Firma Kodu", "type": "text",
                         "required": True, "lock_on_edit": True, "placeholder": "örn. 000"},
                        {"key": "company_type", "label": "Şirket Tipi", "type": "combo",
                         "options": COMPANY_TYPES},
                        {"key": "short_name", "label": "Kısa Ad", "type": "text",
                         "required": True},
                        {"key": "default_currency", "label": "Döviz Birimi", "type": "combo",
                         "options_provider": _load_active_currencies},
                        {"key": "title", "label": "Resmi / Ticari Ünvan", "type": "text",
                         "span": 2},
                        {"key": "notes", "label": "Not", "type": "multiline", "span": 2,
                         "height": 50},
                    ]},
                    {"title": "2. Vergi & Sicil Bilgileri", "columns": 2, "stretch": 6,
                     "fields": [
                        {"key": "tax_office", "label": "Vergi Dairesi", "type": "text"},
                        {"key": "tax_office_code", "label": "V.D. Kodu", "type": "text"},
                        {"key": "tax_number", "label": "Vergi No / TCKN", "type": "text"},
                        {"key": "mersis_no", "label": "MERSİS No", "type": "text"},
                        {"key": "trade_registry_no", "label": "Ticaret Sicil No", "type": "text"},
                        {"key": "nace_code", "label": "NACE / Faaliyet Kodu", "type": "text"},
                        {"key": "sgk_no", "label": "SGK İşyeri Sicil No", "type": "text"},
                        {"key": "founded_at", "label": "Kuruluş Tarihi", "type": "text",
                         "placeholder": "GG.AA.YYYY"},
                    ]},
                ]},
                {"sections": [
                    {"title": "3. Dönemler", "columns": 1, "fields": [
                        {"key": "periods", "label": "Dönemler", "type": "subtable",
                         "columns": _GRID_GROUPS["periods"][1]},
                    ]},
                ]},
                {"sections": [
                    {"title": "4. Logo & Kaşe / İmza", "columns": 2, "fields": [
                        {"key": "logo_base64", "label": "Logo (baskı)", "type": "image"},
                        {"key": "stamp_base64", "label": "Kaşe / İmza", "type": "image"},
                    ]},
                ]},
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
            "title": "Yetkililer, Ortaklar, e-Belge & Banka",
            "bands": [
                {"sections": [
                    {"title": "1. Yetkililer", "columns": 1, "fields": [
                        {"key": "authorized_persons", "label": "Yetkililer", "type": "subtable",
                         "columns": _GRID_GROUPS["authorized_persons"][1]},
                    ]},
                ]},
                {"sections": [
                    {"title": "2. Ortaklar", "columns": 1, "fields": [
                        {"key": "partners", "label": "Ortaklar", "type": "subtable",
                         "columns": _GRID_GROUPS["partners"][1]},
                    ]},
                ]},
                {"sections": [
                    {"title": "3. e-Belge", "columns": 2, "fields": [
                        {"key": "e_invoice_enabled", "label": "e-Fatura Mükellefi", "type": "bool",
                         "text": "Evet"},
                        {"key": "e_archive_enabled", "label": "e-Arşiv Mükellefi", "type": "bool",
                         "text": "Evet"},
                        {"key": "e_dispatch_enabled", "label": "e-İrsaliye Mükellefi", "type": "bool",
                         "text": "Evet"},
                        {"key": "gib_alias", "label": "GİB Etiketi / Alias", "type": "text"},
                        {"key": "integrator", "label": "Entegratör", "type": "text", "span": 2},
                    ]},
                ]},
                {"sections": [
                    {"title": "4. Banka Hesapları", "columns": 1, "fields": [
                        {"key": "bank_accounts", "label": "Banka Hesapları", "type": "subtable",
                         "columns": _GRID_GROUPS["bank_accounts"][1]},
                    ]},
                ]},
            ],
        },
    ]


# Geriye dönük uyumluluk — dinamik döviz listesi olmadan sekme şeması.
FIRMA_TABS: list[dict] = _build_firma_tabs(None)


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

        self.side_panel = self._build_side_panel()

        self.editor = DefinitionEditorScreen(
            title="Firma Detayı",
            tabs=_build_firma_tabs(db_session),
            code_field="code",
            title_field="short_name",
            header_extra_field="company_type",
            status_field="is_active",
            nav_sidebar=True,
            show_section_nav=False,
            enable_save_and_new=True,
            summary_widget=self.side_panel,
            right_panel_width=250,
            left_panel_width=190,
            extra_actions=[
                {"label": "➕ Yeni Dönem", "callback": lambda: self._add_row("periods")},
                {"label": "➕ Yeni Yetkili", "callback": lambda: self._add_row("authorized_persons")},
                {"label": "➕ Yeni Ortak", "callback": lambda: self._add_row("partners")},
                {"label": "➕ Yeni Banka Hesabı", "callback": lambda: self._add_row("bank_accounts")},
            ],
            parent=self,
        )
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self.reject)
        self.editor.saved.connect(self._on_save)
        self.editor.saved_and_new.connect(self._on_save_and_new)

        if company_id:
            company = self.service.get(company_id)
            if company:
                self.editor.set_data(self.service.to_dict(company), is_edit=True)
        else:
            self.editor.set_data(CompanyService.blank_company(), is_edit=False)

        self.showMaximized()

    # ------------------------------------------------------------------
    def _build_side_panel(self) -> FilterWidget:
        """Sağ sidebar: Ara (FilterWidget) + Yazdır/Dışa-İçe Aktar (ExportWidget) —
        ikisi de paylaşılan, diğer ekranlarda da kullanılan widget'lardan gelir."""
        panel = FilterWidget(
            group_title="ARA", show_filters=["search"], initial_open=True, panel_width=220,
        )
        panel.search_box.setPlaceholderText("Dönem / Yetkili / Ortak / Banka ara...")
        panel.filter_changed.connect(lambda f: self._apply_quick_search(f.get("search", "")))
        panel.filters_cleared.connect(lambda: self._apply_quick_search(""))

        self.export_widget = ExportWidget(group_title="YAZDIR & AKTARIM", initial_open=True)
        self.export_widget.print_clicked.connect(self._on_print)
        self.export_widget.export_pdf_clicked.connect(self._on_export_pdf)
        self.export_widget.export_excel_clicked.connect(self._on_export_excel)
        self.export_widget.import_excel_clicked.connect(self._on_import_excel)
        self.export_widget.report_clicked.connect(self._on_report)
        panel.add_custom_section(self.export_widget)
        return panel

    def _grid_widget(self, key: str):
        return self.editor._widgets.get(key)  # noqa: SLF001

    def _add_row(self, key: str) -> None:
        w = self._grid_widget(key)
        if w:
            w._add_row({})  # noqa: SLF001

    def _apply_quick_search(self, text: str) -> None:
        """Arama kutusundaki metni Dönem/Yetkili/Ortak/Banka Hesabı grid'lerinin
        tamamında filtre olarak uygular (satırların hepsini tarayıp eşleşmeyeni gizler)."""
        text = (text or "").strip().lower()
        for key in _GRID_GROUPS:
            w = self._grid_widget(key)
            if not w:
                continue
            model = w.model
            for r in range(model.rowCount()):
                cells = " ".join(
                    (model.item(r, c).text() if model.item(r, c) else "")
                    for c in range(1, model.columnCount())
                ).lower()
                w.grid.table_view.setRowHidden(r, bool(text) and text not in cells)

    # ------------------------------------------------------------------
    def _on_print(self) -> None:
        QMessageBox.information(self, "Yazdır", "Firma kartı yazdırma özelliği hazırlanıyor.")

    def _on_export_pdf(self) -> None:
        QMessageBox.information(self, "PDF", "Firma kartını PDF olarak kaydetme özelliği hazırlanıyor.")

    def _on_report(self) -> None:
        QMessageBox.information(self, "Rapor", "Detaylı firma raporu hazırlanıyor.")

    def _on_export_excel(self) -> None:
        """Dönemler, Yetkililer, Ortaklar ve Banka Hesapları listelerini tek bir
        çok sayfalı Excel dosyasına aktarır."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel'e Aktar", "firma_listeleri.xlsx", "Excel Dosyası (*.xlsx)",
        )
        if not path:
            return
        try:
            from openpyxl import Workbook
            wb = Workbook()
            wb.remove(wb.active)
            for key, (sheet_name, columns) in _GRID_GROUPS.items():
                w = self._grid_widget(key)
                if not w:
                    continue
                ws = wb.create_sheet(sheet_name)
                ws.append([c["label"] for c in columns])
                for rec in w.value():
                    ws.append([rec.get(c["key"], "") for c in columns])
            wb.save(path)
            QMessageBox.information(self, "Dışa Aktarıldı", f"Listeler dışa aktarıldı:\n{path}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Firma listeleri Excel'e aktarılamadı")
            QMessageBox.critical(self, "Hata", f"Dışa aktarma başarısız: {exc}")

    def _on_import_excel(self) -> None:
        """Kullanıcının seçtiği listeye (Dönemler/Yetkililer/Ortaklar/Banka
        Hesapları) bir Excel dosyasından satır ekler."""
        labels = [group[0] for group in _GRID_GROUPS.values()]
        keys = list(_GRID_GROUPS.keys())
        choice, ok = QInputDialog.getItem(
            self, "İçe Aktar", "Hangi listeye aktarılsın?", labels, 0, False,
        )
        if not ok or not choice:
            return
        key = keys[labels.index(choice)]
        _, columns = _GRID_GROUPS[key]
        path, _ = QFileDialog.getOpenFileName(
            self, f"{choice} - Excel'den İçe Aktar", "", "Excel Dosyası (*.xlsx)",
        )
        if not path:
            return
        w = self._grid_widget(key)
        if not w:
            return
        try:
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))
            added = 0
            for row in rows:
                if not any(row):
                    continue
                rec = {c["key"]: ("" if v is None else str(v))
                       for c, v in zip(columns, row)}
                w._add_row(rec)  # noqa: SLF001
                added += 1
            QMessageBox.information(self, "İçe Aktarıldı", f"{choice}: {added} satır eklendi.")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Excel'den içe aktarma başarısız")
            QMessageBox.critical(self, "Hata", f"İçe aktarma başarısız: {exc}")

    # ------------------------------------------------------------------
    def _save_payload(self, payload: dict):
        res = self.service.save(payload, company_id=self.company_id)
        if not res.success:
            QMessageBox.critical(self, "Kayıt Hatası", res.error or "Firma kaydedilemedi.")
            return None
        self.saved_company_id = res.company_id
        return res

    def _on_save(self, payload: dict):
        res = self._save_payload(payload)
        if res is None:
            return
        QMessageBox.information(self, "Kaydedildi", f"Firma kaydedildi: {res.code}")
        self.accept()

    def _on_save_and_new(self, payload: dict):
        res = self._save_payload(payload)
        if res is None:
            return
        code = res.code
        self.company_id = None
        self.saved_company_id = None
        self.editor.set_data(CompanyService.blank_company(), is_edit=False)
        QMessageBox.information(
            self, "Kaydedildi", f"Firma kaydedildi: {code}. Yeni kart için form temizlendi.",
        )
