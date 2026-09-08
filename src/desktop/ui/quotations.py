"""Quotations and Orders Master 3-Panel Management Widgets with Accordion Sidebars."""

import logging
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import or_, select

from src.core.models import Quotation
from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.services.excel_exporter import ExcelExporter
from src.desktop.services.quotation_save_service import QuotationSaveService
from src.desktop.services.quotation_service import QuotationService
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.filterable_table import (
    FilterableTableView,
    value_matches_filter,
)
from src.desktop.ui.components.layout_hint_helper import register_layout_hint
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.dialogs.transaction_document_dialog import TransactionDocumentDialog
from src.desktop.ui.widgets.action_bar_widget import ActionBarWidget
from src.desktop.ui.widgets.export_widget import ExportWidget
from src.desktop.ui.widgets.filter_widget import FilterWidget
from src.desktop.ui.widgets.pagination_widget import PaginationWidget

logger = logging.getLogger(__name__)

# "Yeni / Düzenle" akışında yeni DocumentDetailScreen VARSAYILAN.
# Eski TransactionDocumentDialog'a dönmek için: ortam değişkeni TOYA_OLD_DOC_DIALOG=1
_OLD_DIALOG_FORCED = os.environ.get("TOYA_OLD_DOC_DIALOG", "").strip().lower() in (
    "1", "true", "yes", "on",
)
USE_NEW_DOCUMENT_SCREEN = not _OLD_DIALOG_FORCED
logger.info(
    "Belge detay ekranı: %s",
    "YENİ (DocumentDetailScreen)" if USE_NEW_DOCUMENT_SCREEN else "ESKİ (TransactionDocumentDialog, TOYA_OLD_DOC_DIALOG)",
)


class BaseQuotationOrderWidget(ThreePanelBaseWidget):
    """Base class for 3-Panel Quotations and Orders management widgets."""

    status_message = pyqtSignal(str)

    def __init__(self, db_session=None, quotation_type: str = "Quotation", profile_key: str = "quotations"):
        self.quotation_type = quotation_type
        self.service = QuotationService(db_session)
        self.profile_key = profile_key
        self.company_id = 1

        # Kayıt servisi
        self._save_service = QuotationSaveService(
            db_session=db_session,
            company_id=self.company_id,
        )

        module_label = "Teklif Yönetimi" if quotation_type == "Quotation" else "Sipariş Yönetimi"
        super().__init__(
            db_session=db_session,
            profile_key=profile_key,
            module_name=module_label,
        )
        self.setObjectName("QuotationCanvas")
        register_layout_hint(self, module_label, "Teklif / Sipariş Ana Ekranı")

    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return {
            0: ("☑", "select"),
            1: (self.tr("ID"), "id"),
            2: (self.tr("Evrak / Fiş No"), "quotation_number"),
            3: (self.tr("Belge Başlığı"), "title"),
            4: (self.tr("Müşteri / Cari"), "customer_name"),
            5: (self.tr("Tarih"), "issue_date"),
            6: (self.tr("Vade / Son Tarih"), "expiry_date"),
            7: (self.tr("Genel Toplam"), "grand_total"),
            8: (self.tr("Para Birimi"), "currency"),
            9: (self.tr("Durum"), "status"),
        }

    def toolbar_btn_style(self, bg_color="#ffffff", text_color="#1e293b"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{ background-color: #f1f5f9; }}
            QPushButton:disabled {{ color: #94a3b8; background-color: #f8fafc; border-color: #e2e8f0; }}
        """

    def init_base_ui(self):
        # Profil Yöneticisi
        self.profile_manager = ProfileManager(profile_key=self.profile_key)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        module_label = "Teklif Yönetimi" if getattr(self, "quotation_type", "") == "Quotation" else "Sipariş Yönetimi"

        combo_style = """
            QComboBox, QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                color: #0f172a;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #94a3b8;
                background-color: #ffffff;
                color: #0f172a;
                outline: none;
                padding: 2px 0px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 26px;
                padding: 4px 10px;
                background-color: #ffffff;
                color: #0f172a;
                border-radius: 0px;
            }
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
        """

        # ----------------------------------------------------
        # 1. SOL PANEL (ActionBarWidget & Görünüm Profilleri)
        # ----------------------------------------------------
        action_title = "TEKLİF İŞLEMLERİ" if self.quotation_type == "Quotation" else "SİPARİŞ İŞLEMLERİ"
        conv_label = "🔄 Siparişe Dönüştür" if self.quotation_type == "Quotation" else "🔄 Faturaya Dönüştür"

        self.action_bar = ActionBarWidget(
            group_title=action_title,
            convert_label=conv_label,
            hide_buttons=["bulk_delete", "passive"],
            initial_open=False,
            panel_width=220,
            parent=self,
        )
        self.left_panel = self.action_bar.edge_panel
        register_layout_hint(self.left_panel, module_label, "Sol Kart İşlemleri Paneli")

        # Aksiyon sinyal bağlantıları
        self.action_bar.new_clicked.connect(self.on_new_clicked)
        self.action_bar.edit_clicked.connect(self.on_edit_clicked)
        self.action_bar.duplicate_clicked.connect(self.on_duplicate_clicked)
        self.action_bar.delete_clicked.connect(self.on_delete_clicked)
        self.action_bar.convert_clicked.connect(self.on_convert_clicked)
        self.action_bar.excel_clicked.connect(self.on_excel_clicked)
        self.action_bar.refresh_clicked.connect(self.refresh_table)
        self.action_bar.close_clicked.connect(self.close_tab)

        # Geriye dönük buton referansları
        self.btn_new = self.action_bar.btn_new
        self.btn_edit = self.action_bar.btn_edit
        self.btn_duplicate = self.action_bar.btn_duplicate
        self.btn_delete = self.action_bar.btn_delete
        self.btn_convert = self.action_bar.btn_convert
        self.btn_excel = self.action_bar.btn_excel
        self.btn_refresh = self.action_bar.btn_refresh

        # 2. GRUP: GÖRÜNÜM PROFİLLERİ (Sol Panele Ek Akordiyon Olarak Eklenir)
        self.sec_profiles = CollapsibleSection("GÖRÜNÜM PROFİLLERİ", is_expanded=True)
        lbl_prof = QLabel("Aktif Profil:")
        lbl_prof.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.combo_sidebar_profiles = QComboBox()
        self.combo_sidebar_profiles.setStyleSheet(combo_style)
        self.combo_sidebar_profiles.currentTextChanged.connect(self._on_sidebar_profile_changed)

        prof_btn_lyt = QHBoxLayout()
        prof_btn_lyt.setSpacing(4)
        btn_save_prof = QPushButton("💾 Kaydet")
        btn_save_prof.setStyleSheet(self.toolbar_btn_style())
        btn_save_prof.clicked.connect(self.save_current_profile)
        btn_manage_prof = QPushButton("⚙️ Sütunlar")
        btn_manage_prof.setStyleSheet(self.toolbar_btn_style())
        btn_manage_prof.clicked.connect(self.open_column_manager)
        prof_btn_lyt.addWidget(btn_save_prof)
        prof_btn_lyt.addWidget(btn_manage_prof)

        self.sec_profiles.add_widget(lbl_prof)
        self.sec_profiles.add_widget(self.combo_sidebar_profiles)
        self.sec_profiles.add_layout(prof_btn_lyt)
        self.action_bar.add_custom_section(self.sec_profiles)

        main_layout.addWidget(self.action_bar)

        # ----------------------------------------------------
        # 2. ORTA PANEL: TABLO VE SAYFALAMA (PaginationWidget)
        # ----------------------------------------------------
        center_container = QWidget()
        register_layout_hint(center_container, module_label, "Orta Tablo Paneli")
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(5, 0, 5, 0)
        center_layout.setSpacing(6)

        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key=self.profile_key,
            enable_profile_bar=False,
            parent=self,
            select_column=0,
        )
        self.filterable_table.checked_rows_changed.connect(self._on_checked_rows_changed)
        # Grid üstündeki kolon filtre kutuları (örn. Genel Toplam'a ">100", "<=3000", "=1000")
        # — daha önce yalnızca sinyal yayıp hiçbir yere bağlanmıyordu, hiçbir etkisi yoktu.
        self.filterable_table.filter_changed.connect(lambda _f: self.on_filter_changed())
        self.table_view = self.filterable_table.table_view
        self.table_model = QStandardItemModel(self)
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
        self.table_model.setHorizontalHeaderLabels(headers)
        self.table_model.setHeaderData(0, Qt.Orientation.Horizontal, "Seçim Yapın", Qt.ItemDataRole.ToolTipRole)
        self.table_view.setModel(self.table_model)

        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSelectionBehavior(QHeaderView.SelectionBehavior.SelectRows)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_view.doubleClicked.connect(self.on_edit_clicked)

        self.table_view.setStyleSheet("""
            QTableView {
                border: 1px solid #cbd5e1;
                background-color: white;
                gridline-color: #f1f5f9;
                border-radius: 6px;
                font-family: 'Segoe UI';
                font-size: 12px;
                color: #334155;
            }
            QTableView::item { padding: 6px; }
            QTableView::item:selected {
                background-color: #eff6ff;
                color: #1d4ed8;
                font-weight: 600;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                padding: 8px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                font-weight: bold;
            }
        """)

        center_layout.addWidget(self.filterable_table, 1)

        # Bağımsız Sayfalama Barı (PaginationWidget)
        self.pagination_widget = PaginationWidget(page_sizes=[25, 50, 100], parent=self)
        self.pagination_widget.page_changed.connect(self._on_page_index_changed)
        self.pagination_widget.page_size_changed.connect(self._on_page_size_val_changed)

        # Geriye dönük uyumluluk referansları
        self.lbl_page_info = self.pagination_widget.lbl_page_info
        self.combo_page_size = self.pagination_widget.combo_page_size
        self.btn_first_page = self.pagination_widget.btn_first_page
        self.btn_prev_page = self.pagination_widget.btn_prev_page
        self.btn_next_page = self.pagination_widget.btn_next_page
        self.btn_last_page = self.pagination_widget.btn_last_page

        center_layout.addWidget(self.pagination_widget)
        main_layout.addWidget(center_container, 1)

        # ----------------------------------------------------
        # 3. SAĞ PANEL (FilterWidget & ExportWidget)
        # ----------------------------------------------------
        self.filter_widget = FilterWidget(
            group_title="FİLTRELER",
            show_filters=["search", "status"],
            status_options=[
                "Tümü",
                "Taslak (Draft)",
                "Gönderildi (Sent)",
                "Onaylandı (Accepted)",
                "Reddedildi (Rejected)",
                "Dönüştürüldü (Converted)",
            ],
            initial_open=False,
            panel_width=220,
            parent=self,
        )
        self.right_panel = self.filter_widget.edge_panel
        register_layout_hint(self.right_panel, module_label, "Sağ Filtreler ve Dosya Paneli")

        self.filter_widget.filter_changed.connect(lambda _: self.on_filter_changed())
        self.filter_widget.filters_cleared.connect(self.clear_filters)

        # Geriye dönük uyumluluk referansları
        self.search_box = self.filter_widget.search_box
        self.cmb_status = self.filter_widget.cmb_status
        self.sec_filters = self.filter_widget.sec_filters

        # 2. GRUP: DOSYA & AKTARIM (ExportWidget)
        self.export_widget = ExportWidget(
            group_title="DOSYA & AKTARIM",
            show_buttons=["print", "export_pdf", "export_excel", "report"],
            initial_open=True,
            parent=self,
        )
        self.export_widget.print_clicked.connect(self.on_print_clicked)
        self.export_widget.export_pdf_clicked.connect(self.on_bulk_pdf_clicked)
        self.export_widget.export_excel_clicked.connect(self.on_excel_clicked)
        self.export_widget.report_clicked.connect(
            lambda: QMessageBox.information(self, "Rapor", "Evrak icmal ve detay raporu üretiliyor..."),
        )
        self.sec_sync = self.export_widget.section
        self.filter_widget.add_custom_section(self.export_widget)

        # 3. GRUP: TOPLU İŞLEMLER (işaretli satırlara toplu yazdır / PDF / e-posta)
        self.sec_bulk = CollapsibleSection("TOPLU İŞLEMLER", is_expanded=True)
        self.lbl_bulk = QLabel("İşaretli belge yok")
        self.lbl_bulk.setStyleSheet("font-size:11px;color:#64748b;font-weight:600;")
        self.sec_bulk.add_widget(self.lbl_bulk)
        self._bulk_buttons = {}
        for key, text, slot in (
            ("print", "👁️ Seçilenleri Önizle", self.on_preview_clicked),
            ("print", "🖨️ Seçilenleri Yazdır", self.on_print_clicked),
            ("print", "📄 Seçilenleri PDF Kaydet", self.on_bulk_pdf_clicked),
            ("send", "✉️ Seçilenleri E-Posta Gönder", self.on_bulk_email_clicked),
        ):
            b = QPushButton(text)
            b.setStyleSheet(self.toolbar_btn_style())
            b.clicked.connect(slot)
            self.sec_bulk.add_widget(b)
            self._bulk_buttons[text] = (b, key)
        self.filter_widget.add_custom_section(self.sec_bulk)

        main_layout.addWidget(self.filter_widget)

        # Sidebar profilleri yükle
        self.load_sidebar_profiles()

        # Rol yetkilerine göre buton görünürlüğü
        self._apply_permissions()

        # F5 kısayolu — en sona, layout bittikten sonra
        from PyQt6.QtGui import QKeySequence, QShortcut
        self.sc_refresh = QShortcut(QKeySequence("F5"), self)
        self.sc_refresh.activated.connect(self.refresh_table)

        # Konumlandırmaları Overlay modda ilklendir
        self.left_panel.close_panel()
        self.right_panel.close_panel()
        self.refresh_table()

    def _on_page_index_changed(self, page: int):
        self.current_page = page
        self.refresh_table()

    def _on_page_size_val_changed(self, page_size: int):
        self.per_page = page_size
        self.current_page = 1
        self.refresh_table()


    def load_sidebar_profiles(self):
        if not hasattr(self, "combo_sidebar_profiles"):
            return
        self.combo_sidebar_profiles.blockSignals(True)
        self.combo_sidebar_profiles.clear()
        profiles = self.profile_manager.load_profiles()
        for name in profiles.keys():
            self.combo_sidebar_profiles.addItem(name)
        active = self.profile_manager.get_active_profile_name()
        idx = self.combo_sidebar_profiles.findText(active)
        if idx >= 0:
            self.combo_sidebar_profiles.setCurrentIndex(idx)
        self.combo_sidebar_profiles.blockSignals(False)

    def _on_sidebar_profile_changed(self, profile_name):
        if not profile_name:
            return
        p = self.profile_manager.get_profile(profile_name)
        if p and hasattr(self, "filterable_table"):
            self.filterable_table.apply_view_profile(p)

    def save_current_profile(self):
        active_name = self.combo_sidebar_profiles.currentText()
        if not active_name:
            active_name = "Varsayılan"
        current_p = self.filterable_table.get_current_view_as_profile(active_name)
        self.profile_manager.save_profile(active_name, current_p)
        QMessageBox.information(self, "Profil Kaydedildi", f"'{active_name}' görünüm profili kaydedildi.")

    def open_column_manager(self):
        self.filterable_table.open_column_manager_dialog()

    def close_tab(self):
        parent_tab = self.parentWidget()
        while parent_tab and not hasattr(parent_tab, "removeTab"):
            parent_tab = parent_tab.parentWidget()
        if parent_tab and hasattr(parent_tab, "removeTab"):
            cur_idx = parent_tab.indexOf(self) if hasattr(parent_tab, "indexOf") else parent_tab.currentIndex()
            if cur_idx > 0:
                parent_tab.removeTab(cur_idx)
            elif hasattr(parent_tab, "currentIndex") and parent_tab.currentIndex() > 0:
                parent_tab.removeTab(parent_tab.currentIndex())

    def clear_filters(self):

        if hasattr(self, "filter_widget") and self.filter_widget.get_filters():
            self.filter_widget.clear_filters()
        else:
            if hasattr(self, "search_box"):
                self.search_box.clear()
            if hasattr(self, "cmb_status"):
                self.cmb_status.setCurrentIndex(0)
            self.current_page = 1
            if hasattr(self, "pagination_widget"):
                self.pagination_widget.reset()
            self.refresh_table()

    def on_filter_changed(self):
        self.current_page = 1
        if hasattr(self, "pagination_widget"):
            self.pagination_widget.set_current_page(1)
        self.refresh_table()

    def on_page_size_changed(self, text: str):
        try:
            self.per_page = int(text.split()[0])
            self.current_page = 1
            self.refresh_table()
        except Exception:
            pass

    def go_to_first_page(self):
        if hasattr(self, "pagination_widget"):
            self.pagination_widget.go_to_first_page()
        else:
            self.current_page = 1
            self.refresh_table()

    def go_to_prev_page(self):
        if hasattr(self, "pagination_widget"):
            self.pagination_widget.go_to_prev_page()
        else:
            if self.current_page > 1:
                self.current_page -= 1
                self.refresh_table()

    def go_to_next_page(self):
        if hasattr(self, "pagination_widget"):
            self.pagination_widget.go_to_next_page()
        else:
            total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
            if self.current_page < total_pages:
                self.current_page += 1
                self.refresh_table()

    def go_to_last_page(self):
        if hasattr(self, "pagination_widget"):
            self.pagination_widget.go_to_last_page()
        else:
            total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
            self.current_page = total_pages
            self.refresh_table()

    def _row_field_values(self, q) -> dict:
        """Bir Quotation kaydından, hem grid hücrelerinde gösterilen hem de kolon
        filtrelerinde kıyaslanan alan değerlerini tek yerden üretir."""
        cust_name = q.customer.fullname if q.customer else (q.customer_name_free or "-")
        if q.issue_date:
            c_date = q.issue_date.strftime("%d.%m.%Y")
        elif q.date:
            c_date = q.date.strftime("%d.%m.%Y")
        elif q.created_at:
            c_date = q.created_at.strftime("%d.%m.%Y")
        else:
            c_date = "-"
        v_date = q.valid_until.strftime("%d.%m.%Y") if q.valid_until else "-"
        return {
            "id": q.id,
            "quotation_number": q.quotation_number or "-",
            "title": q.title or q.customer_name_free or "-",
            "customer_name": cust_name,
            "issue_date": c_date,
            "expiry_date": v_date,
            "grand_total": float(q.grand_total or 0),
            "currency": q.currency or "TRY",
            "status": q.status or "draft",
        }

    def _passes_column_filters(self, field_values: dict, column_filters: dict[str, str]) -> bool:
        """Grid üstündeki kolon filtre kutularının (fiyat sütununda ">100", "=1000",
        "<=3000" gibi operatörler dahil) hepsiyle eşleşiyor mu diye bakar."""
        return all(
            value_matches_filter(field_values.get(field), raw_text)
            for field, raw_text in column_filters.items()
        )

    def refresh_table(self):
        self.table_model.removeRows(0, self.table_model.rowCount())
        if not self.db:
            # Demo Satırları Ekle (Veritabanı boşsa bile kullanıcı görsün)
            demo_items = [
                ("1", "TEK-20260816001", "Yıllık Bakım Anlaşması", "TATU HIRDAVAT LTD.", "16.08.2026", "15.09.2026", "12.500,00 ₺", "TRY", "Onaylandı"),
                ("2", "SIP-20260816002", "VGA Kablo & Sarf Siparişi", "DENEME BİLİŞİM A.Ş.", "16.08.2026", "23.08.2026", "1.450,00 ₺", "TRY", "Taslak"),
            ] if self.quotation_type == "Quotation" else [
                ("1", "SIP-20260816001", "VGA Kablo & Sarf Siparişi", "TATU HIRDAVAT LTD.", "16.08.2026", "23.08.2026", "1.450,00 ₺", "TRY", "Onaylandı"),
                ("2", "SIP-20260816002", "Ofis Kırtasiye İhtiyacı", "DENEME BİLİŞİM A.Ş.", "16.08.2026", "30.08.2026", "8.900,00 ₺", "TRY", "Fatura Edildi"),
            ]
            for row_data in demo_items:
                chk = QStandardItem("")
                chk.setCheckable(True)
                chk.setCheckState(Qt.CheckState.Unchecked)
                items = [chk] + [QStandardItem(txt) for txt in row_data]
                self.table_model.appendRow(items)
            self.total_records = len(demo_items)
            if hasattr(self, "pagination_widget"):
                self.pagination_widget.set_total(self.total_records)
                self.pagination_widget.set_current_page(self.current_page)
            elif hasattr(self, "lbl_page_info"):
                self.lbl_page_info.setText(f"Sayfa 1 / 1 (Toplam: {self.total_records})")
            return

        if self.quotation_type == "Quotation":
            type_condition = or_(
                Quotation.quotation_type == "Quotation",
                Quotation.quotation_type == None,  # noqa: E711
                Quotation.quotation_type.ilike("%teklif%"),
            )
        elif self.quotation_type == "Order":
            type_condition = or_(
                Quotation.quotation_type == "Order",
                Quotation.quotation_type.ilike("%sipari%"),
            )
        else:
            type_condition = (Quotation.quotation_type == self.quotation_type)

        stmt = (
            select(Quotation)
            .where(
                type_condition,
                Quotation.is_deleted == False,  # noqa: E712
            )
            .order_by(Quotation.id.desc())
        )

        search_txt = self.search_box.text().strip().lower()
        if search_txt:
            stmt = stmt.where(
                (Quotation.title.ilike(f"%{search_txt}%")) |
                (Quotation.quotation_number.ilike(f"%{search_txt}%")) |
                (Quotation.customer_name_free.ilike(f"%{search_txt}%")),
            )

        st_filter = self.cmb_status.currentText()
        if st_filter != "Tümü":
            st_key = st_filter.split()[0].lower()
            stmt = stmt.where(Quotation.status == st_key)

        records = self.db.scalars(stmt).all()
        unfiltered_total = len(records)

        # Grid üstündeki kolon filtreleri (Evrak No, Genel Toplam ">100" vb.) — kayıtlar
        # zaten tek seferde belleğe alındığı için Python tarafında uygulanıyor.
        column_filters = {
            field: text
            for field, text in getattr(self.filterable_table, "filters", {}).items()
            if (text or "").strip()
        }
        rows = [(q, self._row_field_values(q)) for q in records]
        if column_filters:
            rows = [(q, fv) for q, fv in rows if self._passes_column_filters(fv, column_filters)]

        self.total_records = len(rows)

        if hasattr(self, "pagination_widget"):
            self.pagination_widget.set_total(self.total_records)
            self.pagination_widget.set_current_page(self.current_page)
        elif hasattr(self, "lbl_page_info"):
            total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
            self.lbl_page_info.setText(f"Sayfa {self.current_page} / {total_pages} (Toplam: {self.total_records})")


        # DB'de bu türe ait hiç kayıt yoksa demo verisi göster (kolon filtresi nedeniyle
        # 0 sonuç dönmesi farklıdır — o durumda kullanıcı gerçekten "sonuç yok" görmeli).
        if unfiltered_total == 0:
            demo_items = [
                ("1", "TEK-DEMO-001", "Örnek Teklif — Yeni kayıt eklemek için ➕ Yeni butonuna tıklayın", "Demo Müşteri A.Ş.", "27.08.2026", "26.09.2026", "10.000,00 ₺", "TRY", "draft"),
                ("2", "TEK-DEMO-002", "İkinci Örnek Teklif", "Test Cari Ltd.", "27.08.2026", "10.09.2026", "5.500,00 ₺", "TRY", "sent"),
            ] if self.quotation_type == "Quotation" else [
                ("1", "SIP-DEMO-001", "Örnek Sipariş — Yeni kayıt eklemek için ➕ Yeni butonuna tıklayın", "Demo Müşteri A.Ş.", "27.08.2026", "05.09.2026", "8.200,00 ₺", "TRY", "draft"),
                ("2", "SIP-DEMO-002", "İkinci Örnek Sipariş", "Test Cari Ltd.", "27.08.2026", "12.09.2026", "3.750,00 ₺", "TRY", "accepted"),
            ]
            for row_data in demo_items:
                chk = QStandardItem("")
                chk.setCheckable(True)
                chk.setCheckState(Qt.CheckState.Unchecked)
                items = [chk] + [QStandardItem(txt) for txt in row_data]
                for item in items:
                    item.setForeground(Qt.GlobalColor.gray)
                self.table_model.appendRow(items)
            return

        start = (self.current_page - 1) * self.per_page
        end = start + self.per_page
        page_rows = rows[start:end]

        for q, fv in page_rows:
            chk_item = QStandardItem("")
            chk_item.setCheckable(True)
            chk_item.setCheckState(Qt.CheckState.Unchecked)

            id_item = QStandardItem(str(fv["id"]))
            id_item.setData(int(fv["id"]), Qt.ItemDataRole.UserRole)

            tot_item = QStandardItem(f"{fv['grand_total']:,.2f} ₺")
            tot_item.setData(fv["grand_total"], Qt.ItemDataRole.UserRole)

            row = [
                chk_item,
                id_item,
                QStandardItem(fv["quotation_number"]),
                QStandardItem(fv["title"]),
                QStandardItem(fv["customer_name"]),
                QStandardItem(fv["issue_date"]),
                QStandardItem(fv["expiry_date"]),
                tot_item,
                QStandardItem(fv["currency"]),
                QStandardItem(fv["status"]),
            ]
            self.table_model.appendRow(row)

    def _get_selected_id(self) -> int | None:
        """Grid'de seçili satırın ID'sini döndür."""
        sel = self.table_view.selectionModel().selectedRows()
        if not sel:
            return None
        item = self.table_model.item(sel[0].row(), 1)  # 1. sütun ID'dir (0: checkbox)
        return int(item.text()) if item and item.text().isdigit() else None

    def get_selected_id(self) -> int | None:
        return self._get_selected_id()

    def on_selection_changed(self):
        has_sel = self._get_selected_id() is not None
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        self.btn_duplicate.setEnabled(has_sel)
        self.btn_convert.setEnabled(has_sel)
        self.btn_excel.setEnabled(has_sel)

    def _get_type_index(self) -> int:
        """Mevcut quotation_type'a göre cmb_doc_type index döndür."""
        type_map = {
            "Quotation": 5,   # TEKLİF: (1) VERİLEN SATIŞ TEKLİFİ
            "Order":     7,   # SİPARİŞ: (1) ALINAN MÜŞTERİ SİPARİŞİ
        }
        return type_map.get(self.quotation_type, 5)

    def _open_new_document_screen(self, doc_id=None):
        """Yeni DocumentDetailScreen'i maksimize dialog içinde açar."""
        from src.desktop.ui.screens.document_detail_screen import DocumentDetailScreen
        dlg = DocumentDetailScreen.open_as_dialog(
            parent=self,
            db_session=self.db,
            doc_id=doc_id,
            initial_type_idx=0,
            company_id=self.company_id,
        )
        dlg.screen.document_saved.connect(self._on_document_saved)
        dlg.exec()
        self.refresh_table()

    def on_new_clicked(self):
        if USE_NEW_DOCUMENT_SCREEN:
            self._open_new_document_screen(doc_id=None)
            return
        dlg = TransactionDocumentDialog(
            db_session=self.db,
            company_id=self.company_id,
            initial_type_idx=self._get_type_index(),
            parent=self,
        )
        # doc_id yok → yeni kayıt
        dlg.doc_id = None

        # YENİ — Widget'ları temizle
        if hasattr(dlg, "cari_widget"):
            dlg.cari_widget.clear()
        if hasattr(dlg, "belge_widget"):
            dlg.belge_widget.clear()

        dlg.document_saved.connect(self._on_document_saved)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_table()

    def on_edit_clicked(self):
        selected_id = self._get_selected_id()
        if not selected_id:
            QMessageBox.information(self, "Uyarı", "Düzenlenecek kaydı seçin.")
            return

        if USE_NEW_DOCUMENT_SCREEN:
            self._open_new_document_screen(doc_id=selected_id)
            return

        dlg = TransactionDocumentDialog(
            db_session=self.db,
            company_id=self.company_id,
            doc_id=selected_id,   # Düzenleme modu
            initial_type_idx=self._get_type_index(),
            parent=self,
        )
        # DB'den yükle
        svc = QuotationSaveService(db_session=self.db, company_id=self.company_id)
        svc.load_to_dialog(selected_id, dlg)

        dlg.document_saved.connect(self._on_document_saved)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_table()

    def _on_document_saved(self, data: dict):
        """Dialog kaydettikten sonra listeyi yenile."""
        self.refresh_table()
        teklif_no = data.get("quotation_number", "")
        if hasattr(self, "toast_requested"):
            self.toast_requested.emit(f"Kaydedildi: {teklif_no}", "success")
        elif hasattr(self, "status_message"):
            self.status_message.emit(f"Kaydedildi: {teklif_no}")

    def _on_checked_rows_changed(self, count: int):
        """İşaretli satır sayısı değiştiğinde aksiyon çubuğunu bilgilendir."""
        title = "TEKLİF İŞLEMLERİ" if self.quotation_type == "Quotation" else "SİPARİŞ İŞLEMLERİ"
        if count > 0:
            title = f"{title}  ·  {count} seçili"
        if hasattr(self, "action_bar") and hasattr(self.action_bar, "set_group_title"):
            self.action_bar.set_group_title(title)
        if hasattr(self, "lbl_bulk"):
            self.lbl_bulk.setText(
                f"{count} belge işaretli" if count else "İşaretli belge yok",
            )

    @property
    def _perm_prefix(self) -> str:
        return {"Quotation": "teklif", "Order": "siparis",
                "Invoice": "fatura"}.get(self.quotation_type, "teklif")

    def _apply_permissions(self) -> None:
        """Aktif kullanıcının rol yetkilerine göre aksiyon butonlarını ayarlar."""
        from src.desktop.security.gate import gate
        p = self._perm_prefix
        for btn, code in (
            (self.btn_new, f"{p}.create"),
            (self.btn_edit, f"{p}.edit"),
            (self.btn_duplicate, f"{p}.create"),
            (self.btn_delete, f"{p}.delete"),
            (self.btn_convert, f"{p}.convert"),
            (self.btn_excel, f"{p}.print"),
        ):
            gate(btn, code, hide=True)
        for text, (b, key) in getattr(self, "_bulk_buttons", {}).items():
            gate(b, f"{p}.{key}", hide=True)

    def _get_target_ids(self) -> list[int]:
        """Silme/işlem hedefi: önce işaretli satırlar, yoksa o an seçili satır."""
        checked = self.get_checked_ids()
        if checked:
            return checked
        one = self._get_selected_id()
        return [one] if one else []

    def on_delete_clicked(self):
        if not self.db:
            return
        target_ids = self._get_target_ids()
        if not target_ids:
            QMessageBox.information(self, "Uyarı", "Silmek için satır işaretleyin veya seçin.")
            return

        if len(target_ids) == 1:
            msg = "Seçili kaydı silmek istediğinizden emin misiniz?"
        else:
            msg = f"İşaretli {len(target_ids)} kaydı silmek istediğinizden emin misiniz?"
        confirm = QMessageBox.question(
            self,
            "Silme Onayı",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        for q_id in target_ids:
            q = self.service.get_quotation(q_id)
            if q:
                q.is_deleted = True
                deleted += 1
        if deleted:
            self.db.commit()
        QMessageBox.information(self, "Başarılı", f"{deleted} kayıt silindi.")
        self.refresh_table()

    def on_duplicate_clicked(self):
        q_id = self._get_selected_id()
        if not q_id:
            return
        new_q = self.service.duplicate_quotation(q_id)
        if new_q:
            QMessageBox.information(self, "Başarılı", f"Kayıt kopyalandı: '{new_q.quotation_number}'")
            self.refresh_table()

    def on_convert_clicked(self):
        selected_id = self._get_selected_id()
        if not selected_id:
            QMessageBox.information(self, "Uyarı", "Dönüştürülecek teklifi seçin.")
            return

        reply = QMessageBox.question(
            self,
            "Siparişe Dönüştür",
            "Seçili teklif siparişe dönüştürülecek. Devam?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        svc = QuotationSaveService(db_session=self.db, company_id=self.company_id)
        result = svc.convert_to_order(selected_id)

        if result.success:
            self.refresh_table()
            if hasattr(self, "toast_requested"):
                self.toast_requested.emit(
                    f"Sipariş oluşturuldu: {result.quotation_number}", "success",
                )
            elif hasattr(self, "status_message"):
                self.status_message.emit(f"Sipariş oluşturuldu: {result.quotation_number}")
        else:
            QMessageBox.critical(self, "Hata", result.error or "Dönüştürme başarısız.")

    def on_excel_clicked(self):
        q_id = self.get_selected_id()
        if not q_id:
            return
        q = self.service.get_quotation(q_id)
        if not q:
            return
        fpath, _ = QFileDialog.getSaveFileName(self, "Excel Olarak Kaydet", f"{q.quotation_number}.xlsx", "Excel Files (*.xlsx)")
        if fpath:
            if ExcelExporter.export_quotation_to_excel(fpath, q):
                QMessageBox.information(self, "Başarılı", f"Excel dosyası oluşturuldu:\n{fpath}")

    # ------------------------------------------------------------------
    # YAZDIRMA / BASKI  (tekli + çoklu)
    # ------------------------------------------------------------------
    def _print_service(self):
        from src.desktop.designer.services.teklif_print_service import (
            TeklifPrintService,
        )
        return TeklifPrintService(db_session=self.db)

    def on_preview_clicked(self):
        """İşaretli (yoksa seçili) belgeleri baskı önizlemede açar — çoklu ise art arda."""
        ids = self._get_target_ids()
        if not ids:
            QMessageBox.information(self, "Uyarı", "Önizlenecek belgeyi seçin veya işaretleyin.")
            return
        try:
            svc = self._print_service()
            if len(ids) == 1:
                svc.show_preview(ids[0], parent=self)
            else:
                svc.preview_many(ids, parent=self)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Baskı önizleme açılamadı")
            QMessageBox.critical(self, "Baskı Hatası", f"Önizleme açılamadı:\n{exc}")

    def on_print_clicked(self):
        """Yazdır — önizleme penceresini açar; kullanıcı oradan yazıcıya gönderir."""
        self.on_preview_clicked()

    def on_bulk_pdf_clicked(self):
        """İşaretli belgeleri tek PDF veya klasöre ayrı ayrı PDF olarak kaydeder (çoklu kaydetme)."""
        ids = self._get_target_ids()
        if not ids:
            QMessageBox.information(self, "Uyarı", "PDF için belgeyi seçin veya işaretleyin.")
            return
        try:
            svc = self._print_service()
            if len(ids) == 1:
                path, _ = QFileDialog.getSaveFileName(
                    self, "PDF Kaydet", f"belge_{ids[0]}.pdf", "PDF (*.pdf)",
                )
                if path and svc.export_pdf(path, ids[0]):
                    QMessageBox.information(self, "PDF", f"Kaydedildi:\n{path}")
                return
            box = QMessageBox(self)
            box.setWindowTitle("Toplu PDF")
            box.setText(f"{len(ids)} belge için PDF nasıl kaydedilsin?")
            b_single = box.addButton("Tek PDF Dosyası", QMessageBox.ButtonRole.AcceptRole)
            b_multi = box.addButton("Klasöre Ayrı Ayrı", QMessageBox.ButtonRole.AcceptRole)
            box.addButton("Vazgeç", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is b_single:
                path, _ = QFileDialog.getSaveFileName(
                    self, "Tek PDF Kaydet", "belgeler.pdf", "PDF (*.pdf)",
                )
                if path and svc.export_pdf_many(ids, path):
                    QMessageBox.information(
                        self, "PDF", f"{len(ids)} belge tek PDF'e kaydedildi:\n{path}",
                    )
            elif clicked is b_multi:
                folder = QFileDialog.getExistingDirectory(self, "PDF Klasörü Seç")
                if folder:
                    written = svc.export_each_pdf(ids, folder)
                    QMessageBox.information(
                        self, "PDF", f"{len(written)}/{len(ids)} PDF dosyası oluşturuldu:\n{folder}",
                    )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Toplu PDF hatası")
            QMessageBox.critical(self, "PDF Hatası", str(exc))

    def on_bulk_email_clicked(self):
        """İşaretli belgeleri PDF ekiyle carilerinin e-posta adresine gönderir (çoklu mail)."""
        ids = self._get_target_ids()
        if not ids:
            QMessageBox.information(self, "Uyarı", "E-posta için belgeyi seçin veya işaretleyin.")
            return
        if QMessageBox.question(
            self, "Toplu E-Posta",
            f"{len(ids)} belge, ilgili carinin e-posta adresine PDF ekiyle gönderilecek.\n\nDevam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            from src.desktop.reports.teklif_report_service import TeklifReportService
            rs = TeklifReportService(db_session=self.db, company_id=self.company_id)
            sent, failed = 0, []
            for tid in ids:
                try:
                    ok, info = rs.send_email(tid)
                    if ok:
                        sent += 1
                    else:
                        failed.append(f"#{tid}: {info}")
                except Exception as e:  # noqa: BLE001
                    failed.append(f"#{tid}: {e}")
            msg = f"{sent}/{len(ids)} belge gönderildi."
            if failed:
                msg += "\n\nGönderilemeyenler:\n" + "\n".join(failed[:10])
            QMessageBox.information(self, "Toplu E-Posta", msg)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Toplu e-posta hatası")
            QMessageBox.critical(self, "E-Posta Hatası", str(exc))

    def show_context_menu(self, pos):
        from src.desktop.managers.theme_manager import ThemeManager
        index = self.table_view.indexAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())

        act_new = QAction("➕ Yeni", self)
        act_new.triggered.connect(self.on_new_clicked)
        menu.addAction(act_new)

        if index.isValid():
            self.table_view.selectRow(index.row())

            act_edit = QAction("✏️ Değiştir / Düzenle", self)
            act_edit.triggered.connect(self.on_edit_clicked)

            act_del = QAction("🗑️ Sil", self)
            act_del.triggered.connect(self.on_delete_clicked)

            act_dup = QAction("📋 Kopyala", self)
            act_dup.triggered.connect(self.on_duplicate_clicked)

            conv_txt = "🔄 Siparişe Dönüştür" if self.quotation_type == "Quotation" else "🔄 Faturaya Dönüştür"
            act_conv = QAction(conv_txt, self)
            act_conv.triggered.connect(self.on_convert_clicked)

            act_xls = QAction("📊 Excel'e Aktar", self)
            act_xls.triggered.connect(self.on_excel_clicked)

            menu.addAction(act_edit)
            menu.addAction(act_del)
            menu.addSeparator()
            menu.addAction(act_dup)
            menu.addAction(act_conv)
            menu.addAction(act_xls)

        # ---- Yazdırma / Baskı (tekli + çoklu) ----
        checked = self.get_checked_ids()
        n = len(checked)
        menu.addSeparator()
        if n > 1:
            act_prev = QAction(f"👁️ Seçili {n} Belgeyi Önizle", self)
            act_prn = QAction(f"🖨️ Seçili {n} Belgeyi Yazdır", self)
            act_pdf = QAction(f"📄 Seçili {n} Belgeyi PDF Kaydet", self)
            act_mail = QAction(f"✉️ Seçili {n} Belgeyi E-Posta Gönder", self)
        else:
            act_prev = QAction("👁️ Önizle", self)
            act_prn = QAction("🖨️ Yazdır", self)
            act_pdf = QAction("📄 PDF Olarak Kaydet", self)
            act_mail = QAction("✉️ E-Posta Gönder", self)
        act_prev.triggered.connect(self.on_preview_clicked)
        act_prn.triggered.connect(self.on_print_clicked)
        act_pdf.triggered.connect(self.on_bulk_pdf_clicked)
        act_mail.triggered.connect(self.on_bulk_email_clicked)
        for a in (act_prev, act_prn, act_pdf, act_mail):
            a.setEnabled(bool(index.isValid() or checked))
            menu.addAction(a)

        menu.addSeparator()
        act_sel_all = QAction("☑️ Tüm Satırları Seç", self)
        act_sel_all.triggered.connect(self.select_all_rows)
        menu.addAction(act_sel_all)

        act_desel_all = QAction("⬜ Tüm Seçimleri Kaldır", self)
        act_desel_all.triggered.connect(self.deselect_all_rows)
        menu.addAction(act_desel_all)

        self.filterable_table.add_column_actions_to_menu(menu)

        # --- Yetkiye göre eylemleri kısıtla ---
        from src.desktop.security.gate import can
        p = self._perm_prefix
        _perm = {
            id(act_new): f"{p}.create",
            id(act_prev): f"{p}.print", id(act_prn): f"{p}.print",
            id(act_pdf): f"{p}.print", id(act_mail): f"{p}.send",
        }
        if index.isValid():
            _perm.update({
                id(act_edit): f"{p}.edit",
                id(act_del): f"{p}.delete", id(act_dup): f"{p}.create",
                id(act_conv): f"{p}.convert", id(act_xls): f"{p}.print",
            })
        for a in menu.actions():
            code = _perm.get(id(a))
            if code and not can(code):
                a.setVisible(False)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def select_all_rows(self):
        for r in range(self.table_model.rowCount()):
            item = self.table_model.item(r, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def deselect_all_rows(self):
        for r in range(self.table_model.rowCount()):
            item = self.table_model.item(r, 0)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)

    def get_checked_ids(self) -> list[int]:
        ids = []
        for r in range(self.table_model.rowCount()):
            chk_item = self.table_model.item(r, 0)
            if chk_item and chk_item.checkState() == Qt.CheckState.Checked:
                id_item = self.table_model.item(r, 1)
                if id_item and id_item.text().isdigit():
                    ids.append(int(id_item.text()))
        return ids


class QuotationsWidget(BaseQuotationOrderWidget):
    """Teklif Yönetimi Paneli (Quotation)."""

    def __init__(self, db_session=None):
        super().__init__(db_session=db_session, quotation_type="Quotation", profile_key="quotations")


class OrdersWidget(BaseQuotationOrderWidget):
    """Sipariş Yönetimi Paneli (Order)."""

    def __init__(self, db_session=None):
        super().__init__(db_session=db_session, quotation_type="Order", profile_key="orders")
