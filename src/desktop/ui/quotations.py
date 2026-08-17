"""Quotations and Orders Master 3-Panel Management Widgets with Accordion Sidebars."""

import logging
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import Quotation
from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.services.excel_exporter import ExcelExporter
from src.desktop.services.quotation_service import QuotationService
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.dia_3_panel_base import DIA3PanelBaseWidget
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.components.layout_hint_helper import register_layout_hint
from src.desktop.ui.dialogs.transaction_document_dialog import TransactionDocumentDialog

logger = logging.getLogger(__name__)


class BaseQuotationOrderWidget(DIA3PanelBaseWidget):
    """Base class for DIA-style 3-Panel Quotations and Orders management widgets."""

    status_message = pyqtSignal(str)

    def __init__(self, db_session=None, quotation_type: str = "Quotation", profile_key: str = "quotations"):
        self.quotation_type = quotation_type
        self.service = QuotationService(db_session)
        self.profile_key = profile_key

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
            0: (self.tr("Seç"), "select"),
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
        # 1. SOL PANEL (EdgeTriggeredPanel) - PROFİLLER & AKSİYONLAR
        # ----------------------------------------------------
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)
        register_layout_hint(self.left_panel, module_label, "Sol Kart İşlemleri Paneli")

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        left_frame = QFrame()
        left_frame.setStyleSheet("background-color: transparent; border: none;")
        left_lyt = QVBoxLayout(left_frame)
        left_lyt.setContentsMargins(0, 0, 0, 0)
        left_lyt.setSpacing(8)

        # 1. GRUP: GÖRÜNÜM PROFİLLERİ (Açılır/Kapanır Akordiyon)
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
        left_lyt.addWidget(self.sec_profiles)

        # 2. GRUP: EVRAK İŞLEMLERİ (Açılır/Kapanır Akordiyon)
        action_title = "TEKLİF İŞLEMLERİ" if self.quotation_type == "Quotation" else "SİPARİŞ İŞLEMLERİ"
        self.sec_doc_actions = CollapsibleSection(action_title, is_expanded=True)
        self.sec_doc_actions.setObjectName("cmp.act.001")

        self.btn_new = QPushButton("➕ Yeni (F3)")
        self.btn_new.setObjectName("act.add.001")
        self.btn_new.setToolTip("[act.add.001] Yeni Kayıt Ekle (F3)")
        self.btn_new.setShortcut("F3")
        self.btn_new.setStyleSheet(self.toolbar_btn_style())
        self.btn_new.clicked.connect(self.on_new_clicked)

        self.btn_edit = QPushButton("✏️ Değiştir (F4)")
        self.btn_edit.setObjectName("act.edt.001")
        self.btn_edit.setToolTip("[act.edt.001] Seçili Kaydı Değiştir (F4)")
        self.btn_edit.setShortcut("F4")
        self.btn_edit.setStyleSheet(self.toolbar_btn_style())
        self.btn_edit.clicked.connect(self.on_edit_clicked)

        self.btn_duplicate = QPushButton("📋 Kopyala")
        self.btn_duplicate.setObjectName("act.dup.001")
        self.btn_duplicate.setToolTip("[act.dup.001] Kaydı Kopyala")
        self.btn_duplicate.setStyleSheet(self.toolbar_btn_style())
        self.btn_duplicate.clicked.connect(self.on_duplicate_clicked)

        self.btn_delete = QPushButton("❌ Sil (Del)")
        self.btn_delete.setObjectName("act.del.001")
        self.btn_delete.setToolTip("[act.del.001] Seçili Kaydı Sil (Del)")
        self.btn_delete.setStyleSheet(self.toolbar_btn_style())
        self.btn_delete.clicked.connect(self.on_delete_clicked)

        conv_label = "🔄 Siparişe Dönüştür" if self.quotation_type == "Quotation" else "🔄 Faturaya Dönüştür"
        self.btn_convert = QPushButton(conv_label)
        self.btn_convert.setObjectName("act.cnv.001")
        self.btn_convert.setToolTip(f"[act.cnv.001] {conv_label}")
        self.btn_convert.setStyleSheet(self.toolbar_btn_style())
        self.btn_convert.clicked.connect(self.on_convert_clicked)

        self.btn_excel = QPushButton("🖨️ Yazdır / Excel (F9)")
        self.btn_excel.setObjectName("act.xls.001")
        self.btn_excel.setToolTip("[act.xls.001] Yazdır veya Excel'e Aktar (F9)")
        self.btn_excel.setStyleSheet(self.toolbar_btn_style())
        self.btn_excel.clicked.connect(self.on_excel_clicked)

        btn_close = QPushButton("🚪 Kapat")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                border: 1px solid #fca5a5;
                border-radius: 6px;
                padding: 4px 8px;
                font-family: 'Segoe UI';
                font-size: 11px;
                color: #991b1b;
                font-weight: bold;
                text-align: center;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #fca5a5; }
        """)
        btn_close.clicked.connect(self.close_tab)

        self.sec_doc_actions.add_widget(self.btn_new)
        self.sec_doc_actions.add_widget(self.btn_edit)
        self.sec_doc_actions.add_widget(self.btn_duplicate)
        self.sec_doc_actions.add_widget(self.btn_delete)
        self.sec_doc_actions.add_widget(self.btn_convert)
        self.sec_doc_actions.add_widget(self.btn_excel)
        self.sec_doc_actions.add_widget(btn_close)
        left_lyt.addWidget(self.sec_doc_actions)
        left_lyt.addStretch()

        left_scroll.setWidget(left_frame)
        self.left_panel.set_content(left_scroll)
        main_layout.addWidget(self.left_panel)

        # ----------------------------------------------------
        # 2. ORTA PANEL: TABLO VE SAYFALAMA
        # ----------------------------------------------------
        center_container = QWidget()
        register_layout_hint(center_container, module_label, "Orta Tablo Paneli")
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(5, 0, 5, 0)
        center_layout.setSpacing(6)

        # Profil çubuğu kaldırıldı (enable_profile_bar=False)
        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key=self.profile_key,
            enable_profile_bar=False,
            parent=self,
        )
        self.table_view = self.filterable_table.table_view
        self.table_model = QStandardItemModel(self)
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
        self.table_model.setHorizontalHeaderLabels(headers)
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

        # Sayfalama (Pagination) Barı
        self.pagination_layout = QHBoxLayout()
        self.pagination_layout.setContentsMargins(0, 4, 0, 0)
        self.pagination_layout.setSpacing(6)

        self.btn_first_page = QPushButton("⏮️")
        self.btn_first_page.clicked.connect(self.go_to_first_page)
        self.btn_prev_page = QPushButton("⬅️")
        self.btn_prev_page.clicked.connect(self.go_to_prev_page)

        self.lbl_page_info = QLabel("Sayfa 1 / 1")
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #475569;")

        self.btn_next_page = QPushButton("➡️")
        self.btn_next_page.clicked.connect(self.go_to_next_page)
        self.btn_last_page = QPushButton("⏭️")
        self.btn_last_page.clicked.connect(self.go_to_last_page)

        self.combo_page_size = QComboBox()
        self.combo_page_size.addItems(["25 kayıt", "50 kayıt", "100 kayıt"])
        self.combo_page_size.currentTextChanged.connect(self.on_page_size_changed)

        for btn in [self.btn_first_page, self.btn_prev_page, self.btn_next_page, self.btn_last_page]:
            btn.setStyleSheet("QPushButton { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background: white; }")

        self.pagination_layout.addWidget(self.btn_first_page)
        self.pagination_layout.addWidget(self.btn_prev_page)
        self.pagination_layout.addWidget(self.lbl_page_info)
        self.pagination_layout.addWidget(self.btn_next_page)
        self.pagination_layout.addWidget(self.btn_last_page)
        self.pagination_layout.addStretch()
        self.pagination_layout.addWidget(QLabel("Adet:"))
        self.pagination_layout.addWidget(self.combo_page_size)

        center_layout.addLayout(self.pagination_layout)
        main_layout.addWidget(center_container, 1)

        # ----------------------------------------------------
        # 3. SAĞ PANEL (EdgeTriggeredPanel) - FİLTRELER & DOSYA
        # ----------------------------------------------------
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)
        register_layout_hint(self.right_panel, module_label, "Sağ Filtreler ve Dosya Paneli")

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_frame = QFrame()
        right_frame.setStyleSheet("background-color: transparent; border: none;")
        right_lyt = QVBoxLayout(right_frame)
        right_lyt.setContentsMargins(0, 0, 0, 0)
        right_lyt.setSpacing(8)

        # 1. GRUP: FİLTRELER (Açılır/Kapanır Akordiyon)
        self.sec_filters = CollapsibleSection("FİLTRELER", is_expanded=True)

        lbl_search = QLabel("Ünvan / Fiş No:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Hızlı ara...")
        self.search_box.textChanged.connect(self.on_filter_changed)
        self.search_box.setStyleSheet(combo_style)
        self.sec_filters.add_widget(lbl_search)
        self.sec_filters.add_widget(self.search_box)

        lbl_status = QLabel("Durum:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["Tümü", "Taslak (Draft)", "Gönderildi (Sent)", "Onaylandı (Accepted)", "Reddedildi (Rejected)", "Dönüştürüldü (Converted)"])
        self.cmb_status.currentTextChanged.connect(self.on_filter_changed)
        self.cmb_status.setStyleSheet(combo_style)
        self.sec_filters.add_widget(lbl_status)
        self.sec_filters.add_widget(self.cmb_status)

        btn_clear = QPushButton("🗑️ Filtreleri Temizle")
        btn_clear.setStyleSheet("border: 1px solid #cbd5e1; background: white; padding: 6px; border-radius: 4px; font-weight: 600; font-size: 11px;")
        btn_clear.clicked.connect(self.clear_filters)
        self.sec_filters.add_widget(btn_clear)
        right_lyt.addWidget(self.sec_filters)

        # 2. GRUP: DOSYA & AKTARIM (Açılır/Kapanır Akordiyon)
        self.sec_sync = CollapsibleSection("DOSYA & AKTARIM", is_expanded=True)

        btn_export = QPushButton("📤 Dışa Aktar (Excel)")
        btn_export.setStyleSheet(self.toolbar_btn_style())
        btn_export.clicked.connect(self.on_excel_clicked)

        btn_report = QPushButton("📊 Detaylı Rapor Al")
        btn_report.setStyleSheet(self.toolbar_btn_style())
        btn_report.clicked.connect(lambda: QMessageBox.information(self, "Rapor", "Evrak icmal ve detay raporu üretiliyor..."))

        self.sec_sync.add_widget(btn_export)
        self.sec_sync.add_widget(btn_report)
        right_lyt.addWidget(self.sec_sync)
        right_lyt.addStretch()

        right_scroll.setWidget(right_frame)
        self.right_panel.set_content(right_scroll)
        main_layout.addWidget(self.right_panel)

        # Sidebar profilleri yükle
        self.load_sidebar_profiles()

        # Konumlandırmaları Overlay modda ilklendir
        self.left_panel.close_panel()
        self.right_panel.close_panel()
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
        if parent_tab and hasattr(parent_tab, "currentIndex") and hasattr(parent_tab, "removeTab"):
            parent_tab.removeTab(parent_tab.currentIndex())

    def clear_filters(self):
        self.search_box.clear()
        self.cmb_status.setCurrentIndex(0)
        self.current_page = 1
        self.refresh_table()

    def on_filter_changed(self):
        self.current_page = 1
        self.refresh_table()

    def on_page_size_changed(self, text: str):
        try:
            self.per_page = int(text.split()[0])
            self.current_page = 1
            self.refresh_table()
        except Exception:
            pass

    def go_to_first_page(self):
        self.current_page = 1
        self.refresh_table()

    def go_to_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_table()

    def go_to_next_page(self):
        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_table()

    def go_to_last_page(self):
        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        self.current_page = total_pages
        self.refresh_table()

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
            self.lbl_page_info.setText(f"Sayfa 1 / 1 (Toplam: {self.total_records})")
            return

        stmt = select(Quotation).where(
            Quotation.quotation_type == self.quotation_type,
            Quotation.is_deleted == False,
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
        self.total_records = len(records)

        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        self.lbl_page_info.setText(f"Sayfa {self.current_page} / {total_pages} (Toplam: {self.total_records})")

        start = (self.current_page - 1) * self.per_page
        end = start + self.per_page
        page_records = records[start:end]

        for q in page_records:
            cust_name = q.customer.fullname if q.customer else (q.customer_name_free or "-")
            c_date = q.created_at.strftime("%d.%m.%Y") if q.created_at else "-"
            v_date = q.valid_until.strftime("%d.%m.%Y") if q.valid_until else "-"

            chk_item = QStandardItem("")
            chk_item.setCheckable(True)
            chk_item.setCheckState(Qt.CheckState.Unchecked)

            id_item = QStandardItem(str(q.id))
            id_item.setData(int(q.id), Qt.ItemDataRole.UserRole)

            tot_item = QStandardItem(f"{float(q.grand_total or 0):,.2f} ₺")
            tot_item.setData(float(q.grand_total or 0), Qt.ItemDataRole.UserRole)

            row = [
                chk_item,
                id_item,
                QStandardItem(q.quotation_number or "-"),
                QStandardItem(q.title or "-"),
                QStandardItem(cust_name),
                QStandardItem(c_date),
                QStandardItem(v_date),
                tot_item,
                QStandardItem(q.currency or "TRY"),
                QStandardItem(q.status or "draft"),
            ]
            self.table_model.appendRow(row)

    def get_selected_id(self) -> int | None:
        sel = self.table_view.selectionModel().selectedRows()
        if not sel:
            return None
        row = sel[0].row()
        item = self.table_model.item(row, 1)  # 1. sütun ID'dir
        return int(item.text()) if item and item.text().isdigit() else None

    def on_selection_changed(self):
        has_sel = self.get_selected_id() is not None
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        self.btn_duplicate.setEnabled(has_sel)
        self.btn_convert.setEnabled(has_sel)
        self.btn_excel.setEnabled(has_sel)

    def on_new_clicked(self):
        initial_idx = 5 if self.quotation_type == "Quotation" else 7
        dlg = TransactionDocumentDialog(self.db, company_id=1, initial_type_idx=initial_idx, parent=self)
        if dlg.exec():
            self.refresh_table()

    def on_edit_clicked(self):
        q_id = self.get_selected_id()
        initial_idx = 5 if self.quotation_type == "Quotation" else 7
        dlg = TransactionDocumentDialog(self.db, company_id=1, doc_id=q_id, initial_type_idx=initial_idx, parent=self)
        if dlg.exec():
            self.refresh_table()

    def on_delete_clicked(self):
        q_id = self.get_selected_id()
        if not q_id or not self.db:
            return
        confirm = QMessageBox.question(
            self,
            "Silme Onayı",
            "Seçili kaydı silmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            q = self.service.get_quotation(q_id)
            if q:
                q.is_deleted = True
                self.db.commit()
                QMessageBox.information(self, "Başarılı", "Kayıt silindi.")
                self.refresh_table()

    def on_duplicate_clicked(self):
        q_id = self.get_selected_id()
        if not q_id:
            return
        new_q = self.service.duplicate_quotation(q_id)
        if new_q:
            QMessageBox.information(self, "Başarılı", f"Kayıt kopyalandı: '{new_q.quotation_number}'")
            self.refresh_table()

    def on_convert_clicked(self):
        q_id = self.get_selected_id()
        if not q_id:
            return
        if self.quotation_type == "Quotation":
            if self.service.convert_to_order(q_id):
                QMessageBox.information(self, "Başarılı", "Teklif başarıyla Siparişe dönüştürüldü.")
                self.refresh_table()
        else:
            q = self.service.get_quotation(q_id)
            if q:
                q.status = "converted"
                self.db.commit()
                QMessageBox.information(self, "Başarılı", "Sipariş Faturaya dönüştürüldü.")
                self.refresh_table()

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

    def show_context_menu(self, pos):
        index = self.table_view.indexAt(pos)
        menu = QMenu(self)

        act_new = QAction("➕ Ekle", self)
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

        menu.addSeparator()
        act_sel_all = QAction("☑️ Tüm Satırları Seç", self)
        act_sel_all.triggered.connect(self.select_all_rows)
        menu.addAction(act_sel_all)

        act_desel_all = QAction("⬜ Tüm Seçimleri Kaldır", self)
        act_desel_all.triggered.connect(self.deselect_all_rows)
        menu.addAction(act_desel_all)

        menu.addSeparator()
        act_cols = QAction("⚙️ Kolon Yapılandır", self)
        act_cols.triggered.connect(self.filterable_table.open_column_manager_dialog)
        menu.addAction(act_cols)

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
