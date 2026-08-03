"""Quotations and Orders DIA-Style 3-Panel Management Widgets."""

import logging
import os
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QStandardItem, QStandardItemModel
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
from src.desktop.services.excel_exporter import ExcelExporter
from src.desktop.services.quotation_service import QuotationService
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.dialogs.quotation_edit_dialog import QuotationEditDialog

logger = logging.getLogger(__name__)


class BaseQuotationOrderWidget(QWidget):
    """Base class for DIA-style 3-Panel Quotations and Orders management widgets."""

    status_message = pyqtSignal(str)

    def __init__(self, db_session=None, quotation_type: str = "Quotation", profile_key: str = "quotations"):
        super().__init__()
        self.db = db_session
        self.quotation_type = quotation_type
        self.profile_key = profile_key
        self.service = QuotationService(self.db)

        # Pagination & Filtering
        self.current_page = 1
        self.per_page = 25
        self.total_records = 0

        self.setObjectName("QuotationCanvas")
        self.init_ui()

    def toolbar_btn_style(self, bg_color="#ffffff", text_color="#1e293b"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{ background-color: #f1f5f9; }}
            QPushButton:disabled {{ color: #94a3b8; background-color: #f8fafc; border-color: #e2e8f0; }}
        """

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # ----------------------------------------------------
        # 1. SOL PANEL (EdgeTriggeredPanel) - ARAMA VE FİLTRE
        # ----------------------------------------------------
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)

        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: transparent; border: none;")
        filter_lyt = QVBoxLayout(filter_frame)
        filter_lyt.setContentsMargins(0, 0, 0, 0)
        filter_lyt.setSpacing(8)

        lbl_search = QLabel("Arama:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Hızlı ara...")
        self.search_box.textChanged.connect(self.on_filter_changed)
        filter_lyt.addWidget(lbl_search)
        filter_lyt.addWidget(self.search_box)

        lbl_status = QLabel("Durum Filtresi:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["Tümü", "Taslak (Draft)", "Gönderildi (Sent)", "Onaylandı (Accepted)", "Reddedildi (Rejected)", "Dönüştürüldü (Converted)"])
        self.cmb_status.currentTextChanged.connect(self.on_filter_changed)
        filter_lyt.addWidget(lbl_status)
        filter_lyt.addWidget(self.cmb_status)

        btn_clear = QPushButton("🗑️ Filtreleri Temizle")
        btn_clear.setStyleSheet("border: 1px solid #cbd5e1; background: white; padding: 4px; border-radius: 4px;")
        btn_clear.clicked.connect(self.clear_filters)
        filter_lyt.addWidget(btn_clear)

        filter_lyt.addStretch()
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        left_scroll.setWidget(filter_frame)
        self.left_panel.set_content(left_scroll)
        main_layout.addWidget(self.left_panel)

        # ----------------------------------------------------
        # 2. ORTA PANEL: TABLO VE SAYFALAMA
        # ----------------------------------------------------
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)

        self.headers_dict = {
            0: (self.tr("ID"), "id"),
            1: (self.tr("Numara"), "quotation_number"),
            2: (self.tr("Başlık"), "title"),
            3: (self.tr("Müşteri / Cari"), "customer_name"),
            4: (self.tr("Tutar"), "grand_total"),
            5: (self.tr("Para Birimi"), "currency"),
            6: (self.tr("Durum"), "status"),
            7: (self.tr("Tarih"), "issue_date"),
        }

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
        # 3. SAĞ PANEL (EdgeTriggeredPanel) - EYLEMLER VE TOOLBAR
        # ----------------------------------------------------
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_content = QWidget()
        right_lyt = QVBoxLayout(right_content)
        right_lyt.setContentsMargins(4, 4, 4, 4)
        right_lyt.setSpacing(8)

        # 1. Grup: Veri İşlemleri
        grp_data = QFrame()
        grp_data.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_data_lyt = QVBoxLayout(grp_data)
        grp_data_lyt.setContentsMargins(4, 6, 4, 6)
        grp_data_lyt.setSpacing(4)

        lbl_grp_data = QLabel("VERİ İŞLEMLERİ")
        lbl_grp_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_data.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 9px;")
        grp_data_lyt.addWidget(lbl_grp_data)

        title_new = "➕ Yeni Teklif Ekle" if self.quotation_type == "Quotation" else "➕ Yeni Sipariş Ekle"
        self.btn_new = QPushButton(title_new)
        self.btn_new.setStyleSheet(self.toolbar_btn_style("#3b82f6", "#ffffff"))
        self.btn_new.clicked.connect(self.on_new_clicked)

        self.btn_edit = QPushButton("✏️ Değiştir / Düzenle")
        self.btn_edit.setStyleSheet(self.toolbar_btn_style())
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self.on_edit_clicked)

        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setStyleSheet(self.toolbar_btn_style())
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self.on_delete_clicked)

        self.btn_duplicate = QPushButton("📋 Kopyala")
        self.btn_duplicate.setStyleSheet(self.toolbar_btn_style())
        self.btn_duplicate.setEnabled(False)
        self.btn_duplicate.clicked.connect(self.on_duplicate_clicked)

        convert_title = "🔄 Siparişe Dönüştür" if self.quotation_type == "Quotation" else "🔄 Faturaya Dönüştür"
        self.btn_convert = QPushButton(convert_title)
        self.btn_convert.setStyleSheet(self.toolbar_btn_style())
        self.btn_convert.setEnabled(False)
        self.btn_convert.clicked.connect(self.on_convert_clicked)

        self.btn_excel = QPushButton("📊 Excel'e Aktar")
        self.btn_excel.setStyleSheet(self.toolbar_btn_style("#10b981", "#ffffff"))
        self.btn_excel.setEnabled(False)
        self.btn_excel.clicked.connect(self.on_excel_clicked)

        grp_data_lyt.addWidget(self.btn_new)
        grp_data_lyt.addWidget(self.btn_edit)
        grp_data_lyt.addWidget(self.btn_delete)
        grp_data_lyt.addWidget(self.btn_duplicate)
        grp_data_lyt.addWidget(self.btn_convert)
        grp_data_lyt.addWidget(self.btn_excel)

        right_lyt.addWidget(grp_data)

        # 2. Grup: Görünüm & Sistem
        grp_view = QFrame()
        grp_view.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_view_lyt = QVBoxLayout(grp_view)
        grp_view_lyt.setContentsMargins(4, 6, 4, 6)
        grp_view_lyt.setSpacing(4)

        lbl_grp_view = QLabel("GÖRÜNÜM")
        lbl_grp_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_view.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 9px;")
        grp_view_lyt.addWidget(lbl_grp_view)

        btn_refresh = QPushButton("🔄 Tabloyu Yenile")
        btn_refresh.setStyleSheet(self.toolbar_btn_style())
        btn_refresh.clicked.connect(self.refresh_table)

        btn_cols = QPushButton("⚙️ Kolonları Yapılandır")
        btn_cols.setStyleSheet(self.toolbar_btn_style())
        btn_cols.clicked.connect(self.filterable_table.open_column_manager_dialog)

        grp_view_lyt.addWidget(btn_refresh)
        grp_view_lyt.addWidget(btn_cols)
        right_lyt.addWidget(grp_view)

        right_lyt.addStretch()
        right_scroll.setWidget(right_content)
        self.right_panel.set_content(right_scroll)
        main_layout.addWidget(self.right_panel)

        self.refresh_table()

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
                (Quotation.customer_name_free.ilike(f"%{search_txt}%"))
            )

        st_filter = self.cmb_status.currentText()
        if st_filter != "Tümü":
            st_key = st_filter.split()[0].lower()
            stmt = stmt.where(Quotation.status == st_key)

        records = self.db.scalars(stmt).all()
        self.total_records = len(records)

        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        self.lbl_page_info.setText(f"Sayfa {self.current_page} / {total_pages} (Toplam: {self.total_records})")

        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        page_records = records[start_idx:end_idx]

        for q in page_records:
            id_item = QStandardItem(str(q.id))
            num_item = QStandardItem(q.quotation_number)
            num_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

            title_item = QStandardItem(q.title or "")
            cust_name = q.customer.fullname if q.customer else (q.customer_name_free or "-")
            cust_item = QStandardItem(cust_name)

            total_item = QStandardItem(f"{q.grand_total:,.2f}")
            curr_item = QStandardItem(q.currency or "TRY")
            status_item = QStandardItem(q.status)

            date_str = q.issue_date.strftime("%d.%m.%Y") if hasattr(q.issue_date, "strftime") else str(q.issue_date)
            date_item = QStandardItem(date_str)

            id_item.setData(q.id, Qt.ItemDataRole.UserRole)
            self.table_model.appendRow([id_item, num_item, title_item, cust_item, total_item, curr_item, status_item, date_item])

    def get_selected_id(self) -> int | None:
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return None
        item = self.table_model.item(indexes[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def on_selection_changed(self):
        has_sel = bool(self.table_view.selectionModel().selectedRows())
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        self.btn_duplicate.setEnabled(has_sel)
        self.btn_convert.setEnabled(has_sel)
        self.btn_excel.setEnabled(has_sel)

    def on_new_clicked(self):
        dlg = QuotationEditDialog(self.db, document_kind=self.quotation_type, parent=self)
        if dlg.exec():
            self.refresh_table()

    def on_edit_clicked(self):
        q_id = self.get_selected_id()
        if not q_id:
            return
        dlg = QuotationEditDialog(self.db, quotation_id=q_id, document_kind=self.quotation_type, parent=self)
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
        act_cols = QAction("⚙️ Kolon Yapılandır", self)
        act_cols.triggered.connect(self.filterable_table.open_column_manager_dialog)
        menu.addAction(act_cols)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))


class QuotationsWidget(BaseQuotationOrderWidget):
    """Teklif Yönetimi Paneli (Quotation)."""

    def __init__(self, db_session=None):
        super().__init__(db_session=db_session, quotation_type="Quotation", profile_key="quotations")


class OrdersWidget(BaseQuotationOrderWidget):
    """Sipariş Yönetimi Paneli (Order)."""

    def __init__(self, db_session=None):
        super().__init__(db_session=db_session, quotation_type="Order", profile_key="orders")
