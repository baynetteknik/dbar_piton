"""
TOYA ERP - Cari (Müşteri / Tedarikçi) Kart Editörü

`DefinitionEditorScreen` (tpl.card.001 v2 — çok kolonlu bölümlü düzen) ile
Stok Kartı ile aynı kalıpta kurulan tam ekran cari kartı: numaralı bölümler,
sol panelde "BÖLÜMLER" nav listesi gizli (sekmeler zaten aynı gezinmeyi
sağlıyor) — yalnızca "İŞLEMLER" (Alan Adlarını Düzenle menüsü, Cari
Grupları) ve "RAPORLAR" (Hareketler, Ekstre) grupları gösterilir, sağda
"Özet Bilgi" paneli (Güncel Bakiye + fotoğraf), altta VAZGEÇ / KAYDET (+
Kaydet ve Yeni).

Kategorizasyon (Cari Grubu / Alt Grup 1-2 / Bölge) Stok'taki Kategorizasyon
bölümüyle aynı mantıkla `catalog_search` alanlarından kurulur — serbest
metin yerine paylaşılan, düzenlenebilir bir listeden seçilir.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QMessageBox, QVBoxLayout
from sqlalchemy import select

from src.core.models import PaymentPlan, Quotation
from src.desktop.services.customer_service import CustomerService
from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
from src.desktop.ui.widgets.card_summary_panel import CardSummaryPanel
from src.desktop.ui.widgets.catalog_picker import open_catalog_picker
from src.desktop.ui.widgets.recent_activity_widget import RecentActivityWidget

_BELGE_STIL = {
    "Quotation": ("Teklif", "📄", "#9333ea", "#f3e8ff"),
    "Order": ("Sipariş", "📦", "#d97706", "#fef3c7"),
    "Invoice": ("Fatura", "🧾", "#16a34a", "#dcfce7"),
}

GROUPS = ["Müşteri", "Tedarikçi", "Müşteri + Tedarikçi", "Personel", "Diğer"]
CUSTOMER_TYPES = ["Müşteri", "Tedarikçi", "Personel", "Diğer"]
CURRENCIES = ["TRY", "USD", "EUR", "GBP"]
_NO_PLAN = "— Yok —"


def _fmt_money(v) -> str:
    try:
        return f"{float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "0,00"


def _build_tabs(
    payment_plan_names: list[str], *, db_session=None, section_refs: dict | None = None,
) -> list[dict]:
    refs = section_refs if section_refs is not None else {}
    section_kategorizasyon = {
        "title": "2. Kategorizasyon", "columns": 2, "stretch": 5,
        "editable_labels": {"scope": "cari.kategori", "db_session": db_session,
                             "hide_button": True},
        "fields": [
            {"key": "group_name", "label": "Cari Grubu", "type": "catalog_search",
             "catalog_key": "cari.grup", "db_session": db_session, "defaults": GROUPS,
             "catalog_title": "Cari Grubu - Kayıtlı Değerler"},
            {"key": "sub_group_1", "label": "Alt Grup 1", "type": "catalog_search",
             "catalog_key": "cari.alt_grup1", "db_session": db_session,
             "catalog_title": "Alt Grup 1 - Kayıtlı Değerler"},
            {"key": "sub_group_2", "label": "Alt Grup 2", "type": "catalog_search",
             "catalog_key": "cari.alt_grup2", "db_session": db_session,
             "catalog_title": "Alt Grup 2 - Kayıtlı Değerler"},
            {"key": "region", "label": "Bölge", "type": "catalog_search",
             "catalog_key": "cari.bolge", "db_session": db_session,
             "catalog_title": "Bölge - Kayıtlı Değerler"},
        ],
    }
    section_finans = {
        "title": "6. Finans & Risk", "columns": 3, "stretch": 1,
        "editable_labels": {"scope": "cari.finans", "db_session": db_session,
                             "hide_button": True},
        "fields": [
            {"key": "currency", "label": "Para Birimi", "type": "combo",
             "options": CURRENCIES},
            {"key": "payment_plan_name", "label": "Ödeme Planı", "type": "combo",
             "options": [_NO_PLAN, *payment_plan_names]},
            {"key": "risk_limit", "label": "Risk Limiti", "type": "number", "suffix": "₺"},
            {"key": "default_discount", "label": "Varsayılan İskonto", "type": "number",
             "suffix": "%", "max": 100.0},
            {"key": "balance", "label": "Güncel Bakiye (salt-okunur)", "type": "number",
             "suffix": "₺", "readonly": True, "min": -1e12},
        ],
    }
    refs["kategorizasyon"] = section_kategorizasyon
    refs["finans"] = section_finans
    return [
        {
            "title": "Genel Bilgiler",
            "bands": [
                {"sections": [
                    {"title": "1. Cari Kimliği", "columns": 2, "stretch": 7, "fields": [
                        {"key": "customer_code", "label": "Cari Kodu", "type": "text",
                         "lock_on_edit": True, "placeholder": "boş bırakılırsa otomatik"},
                        {"key": "customer_type", "label": "Cari Tipi", "type": "combo",
                         "options": CUSTOMER_TYPES},
                        {"key": "fullname", "label": "Ünvan / Ad Soyad", "type": "multiline",
                         "span": 2, "required": True, "height": 44},
                        {"key": "nickname", "label": "Kısa Ad / Takma Ad", "type": "text"},
                        {"key": "authorized_person", "label": "Yetkili Kişi", "type": "text"},
                    ]},
                    section_kategorizasyon,
                ]},
                {"sections": [
                    {"title": "3. İletişim", "columns": 3, "fields": [
                        {"key": "phone", "label": "Telefon 1", "type": "text"},
                        {"key": "phone2", "label": "Telefon 2", "type": "text"},
                        {"key": "phone_home", "label": "Ev Telefonu", "type": "text"},
                        {"key": "fax", "label": "Faks", "type": "text"},
                        {"key": "email", "label": "E-Posta", "type": "text"},
                        {"key": "website", "label": "Web Sitesi", "type": "text"},
                    ]},
                ]},
                {"sections": [
                    {"title": "4. Özel Kodlar", "columns": 3, "fields": [
                        {"key": "special_code_1", "label": "Özel Kod 1", "type": "text"},
                        {"key": "special_code_2", "label": "Özel Kod 2", "type": "text"},
                        {"key": "special_code_3", "label": "Özel Kod 3", "type": "text"},
                    ]},
                ]},
                {"sections": [
                    {"title": "5. Vergi & e-Belge", "columns": 2, "stretch": 1, "fields": [
                        {"key": "tax_office", "label": "Vergi Dairesi", "type": "text"},
                        {"key": "tax_number", "label": "Vergi No / TCKN", "type": "text"},
                        {"key": "is_efatura", "label": "e-Fatura Mükellefi", "type": "bool",
                         "text": "e-Fatura"},
                        {"key": "efatura_user", "label": "e-Fatura Kullanıcı", "type": "text"},
                        {"key": "efatura_mailbox", "label": "e-Fatura Posta Kutusu (Etiket)",
                         "type": "text", "span": 2},
                    ]},
                    section_finans,
                ]},
            ],
        },
        {
            "title": "Adres",
            "bands": [
                {"sections": [
                    {"title": "Adres Bilgileri", "columns": 2, "fields": [
                        {"key": "address", "label": "Adres 1", "type": "multiline", "span": 2},
                        {"key": "address2", "label": "Adres 2 (Sevk)", "type": "multiline",
                         "span": 2},
                        {"key": "district", "label": "İlçe", "type": "text"},
                        {"key": "city", "label": "İl", "type": "text"},
                        {"key": "postcode", "label": "Posta Kodu", "type": "text"},
                        {"key": "country", "label": "Ülke", "type": "text"},
                    ]},
                ]},
            ],
        },
        {
            "title": "Notlar",
            "bands": [
                {"sections": [
                    {"title": "Notlar", "columns": 1, "fields": [
                        {"key": "notes", "label": "Notlar", "type": "multiline", "height": 120},
                    ]},
                ]},
            ],
        },
    ]


# Geriye dönük uyumluluk — dinamik seçenekler olmadan sekme şeması.
CARI_TABS = _build_tabs([])


class CariEditorDialog(QDialog):
    def __init__(self, db_session=None, customer_id: int | None = None,
                 company_id: int | None = None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.customer_id = customer_id
        self.service = CustomerService(db_session, company_id=company_id)
        self.saved_customer_id: int | None = None

        self._plans = self._load_payment_plans()          # {ad: id}
        self._plan_name_by_id = {v: k for k, v in self._plans.items()}

        self.has_saved: bool = False

        self.setWindowTitle("Cari Kartı")
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)

        self.summary = CardSummaryPanel(
            title="Özet Bilgi", image_key="photo_path", image_size=(180, 120),
        )
        self.summary.set_updater(self._update_summary)

        self._section_refs: dict = {}
        self.editor = DefinitionEditorScreen(
            title="Cari Kartı",
            tabs=_build_tabs(list(self._plans.keys()), db_session=self.db,
                              section_refs=self._section_refs),
            code_field="customer_code",
            title_field="fullname",
            header_extra_field="customer_type",
            status_field="is_active",
            nav_sidebar=True,
            show_section_nav=False,
            enable_save_and_new=True,
            summary_widget=self.summary,
            right_panel_width=228,
            left_panel_width=185,
            extra_actions=[
                {"label": "✏ Alan Adlarını Düzenle", "menu": [
                    {"label": "Kategoriler", "callback": self._edit_kategori_labels},
                    {"label": "Finans & Risk", "callback": self._edit_finans_labels},
                ]},
                {"label": "🏷 Cari Grupları", "callback": self._manage_cari_gruplari},
                {"label": "📊 Hareketler", "callback": self._open_ekstre,
                 "enabled_on_edit": True, "group": "raporlar"},
                {"label": "📜 Ekstre", "callback": self._open_ekstre,
                 "enabled_on_edit": True, "group": "raporlar"},
            ],
            parent=self,
        )
        lyt.addWidget(self.editor)
        self.editor.closed.connect(self._on_close_requested)
        self.editor.saved.connect(self._on_save)
        self.editor.saved_and_new.connect(self._on_save_and_new)

        self.recent_activity = RecentActivityWidget(title="SON CARİ İŞLEMLERİ")
        lyt.addWidget(self.recent_activity)

        if customer_id:
            c = self.service.get(customer_id)
            if c:
                d = self.service.to_dict(c)
                d["payment_plan_name"] = self._plan_name_by_id.get(
                    c.payment_plan_id, _NO_PLAN,
                )
                self.editor.set_data(d, is_edit=True)
                self.summary.set_image_value(d.get("photo_path"))
        else:
            self.editor.set_data(CustomerService.blank_customer(), is_edit=False)

        self._load_recent_activity()
        self.showMaximized()
        from src.desktop.ui.components.window_fit_helper import zorla_ilk_yerlesim
        zorla_ilk_yerlesim(self)

    # ------------------------------------------------------------------
    def _load_recent_activity(self) -> None:
        """Alt şeritte cariye ait son 5 teklif/sipariş/fatura belgesini gösterir."""
        cid = self.saved_customer_id or self.customer_id
        if not (self.db and cid):
            self.recent_activity.set_items([])
            return
        try:
            rows = self.db.scalars(
                select(Quotation).where(
                    Quotation.customer_id == cid,
                    Quotation.is_deleted == False,  # noqa: E712
                ).order_by(Quotation.issue_date.desc().nullslast()).limit(5),
            ).all()
        except Exception:  # noqa: BLE001
            rows = []

        items = []
        for q in rows:
            etiket, icon, accent, badge_bg = _BELGE_STIL.get(
                q.quotation_type, (q.quotation_type or "Belge", "📄", "#2563eb", "#eff6ff"),
            )
            dt = q.issue_date or q.date
            tarih = dt.strftime("%d.%m.%Y") if dt else ""
            items.append({
                "title": f"{etiket} {q.quotation_number or ''}".strip(),
                "value": f"{_fmt_money(q.grand_total)} ₺  ({tarih})",
                "icon": icon,
                "accent": accent,
                "badge_bg": badge_bg,
            })
        self.recent_activity.set_items(items)

    # ------------------------------------------------------------------
    def _load_payment_plans(self) -> dict[str, int]:
        if not self.db:
            return {}
        try:
            rows = self.db.scalars(
                select(PaymentPlan).where(PaymentPlan.is_deleted == False),  # noqa: E712
            ).all()
            out: dict[str, int] = {}
            for r in rows:
                out[(r.description or r.code or f"Plan {r.id}")] = r.id
            return out
        except Exception:  # noqa: BLE001
            return {}

    def _update_summary(self, d: dict) -> None:
        self.summary.set_kpi("Güncel Bakiye", f"{_fmt_money(d.get('balance'))} ₺")
        plan = d.get("payment_plan_name") or _NO_PLAN
        self.summary.set_rows([
            ("Risk Limiti", f"{_fmt_money(d.get('risk_limit'))} ₺"),
            ("Ödeme Planı", plan if plan != _NO_PLAN else "—"),
            ("Varsayılan İskonto", f"%{_fmt_money(d.get('default_discount'))}"),
        ])

    def _manage_cari_gruplari(self):
        open_catalog_picker(self, self.db, "cari.grup", "", defaults=GROUPS,
                             title="Cari Grupları")

    def _edit_kategori_labels(self):
        section = self._section_refs.get("kategorizasyon")
        if section:
            self.editor._edit_section_labels(section, section["editable_labels"])  # noqa: SLF001

    def _edit_finans_labels(self):
        section = self._section_refs.get("finans")
        if section:
            self.editor._edit_section_labels(section, section["editable_labels"])  # noqa: SLF001

    def _open_ekstre(self):
        if not self.saved_customer_id and not self.customer_id:
            QMessageBox.information(self, "Ekstre", "Önce cariyi kaydedin.")
            return
        from src.desktop.ui.widgets.cari_ekstre_dialog import CariEkstreDialog
        CariEkstreDialog(
            db_session=self.db,
            customer_id=self.saved_customer_id or self.customer_id,
            parent=self,
        ).exec()

    # ------------------------------------------------------------------
    def _on_close_requested(self):
        if self.has_saved:
            self.accept()
        else:
            self.reject()

    def closeEvent(self, event):  # noqa: N802
        if self.has_saved:
            self.setResult(QDialog.DialogCode.Accepted)
        super().closeEvent(event)

    # ------------------------------------------------------------------
    def _save_payload(self, payload: dict):
        """Payload'ı servise kaydeder; başarılıysa `CustomerSaveResult`,
        değilse hata mesajı gösterip `None` döndürür."""
        plan_name = payload.pop("payment_plan_name", _NO_PLAN)
        payload["payment_plan_id"] = self._plans.get(plan_name)
        payload.pop("balance", None)  # bakiye salt-okunur; karttan yazılmaz
        img = self.summary.image_value()
        if img is not None:
            payload["photo_path"] = img

        res = self.service.save(payload, customer_id=self.customer_id)
        if not res.success:
            QMessageBox.critical(self, "Kayıt Hatası", res.error or "Cari kaydedilemedi.")
            return None
        self.saved_customer_id = res.customer_id
        self.has_saved = True
        return res

    def _on_save(self, payload: dict):
        res = self._save_payload(payload)
        if res is None:
            return
        QMessageBox.information(self, "Kaydedildi", f"Cari kaydedildi: {payload['fullname']}")
        self.accept()

    def _on_save_and_new(self, payload: dict):
        res = self._save_payload(payload)
        if res is None:
            return
        name = payload["fullname"]
        # Yeni kayıt için formu temizle; pencere açık kalır.
        self.customer_id = None
        self.saved_customer_id = None
        self.summary.set_image_value(None)
        self.editor.set_data(CustomerService.blank_customer(), is_edit=False)
        self.recent_activity.set_items([])
        QMessageBox.information(
            self, "Kaydedildi", f"Cari kaydedildi: {name}. Yeni kart için form temizlendi.",
        )
