"""
TOYA ERP - Cari Hesap Liste Ekranı (CAKALST001)
ToyaUI Master Şablonu:
DIA3PanelBaseWidget + ActionBarWidget + FilterWidget + PaginationWidget + ExportWidget

Kullanım:
    widget = CariListScreen(db_session=db, company_id=1)
"""

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import Customer
from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.dia_3_panel_base import DIA3PanelBaseWidget
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.components.layout_hint_helper import register_layout_hint
from src.desktop.ui.widgets.action_bar_widget import ActionBarWidget
from src.desktop.ui.widgets.export_widget import ExportWidget
from src.desktop.ui.widgets.filter_widget import FilterWidget
from src.desktop.ui.widgets.pagination_widget import PaginationWidget

logger = logging.getLogger(__name__)


class CariListScreen(DIA3PanelBaseWidget):
    """Cari Hesap Liste Ekranı — CAKALST001

    ToyaUI 3 panelli master şablon ve atomik widget'ları kullanır.
    """

    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, company_id: int = 1, parent=None):
        self.company_id = company_id
        self.profile_key = "cari_list"
        self.current_page = 1
        self.per_page = 25
        self.total_records = 0

        super().__init__(
            db_session=db_session,
            profile_key=self.profile_key,
            module_name="Müşteriler & Cariler",
        )
        self.setObjectName("CariCanvas")
        register_layout_hint(self, "Müşteriler & Cariler", "Cari Hesap Ana Ekranı")

    # ─────────────────────────────────────────────
    # SÜTUN TANIMLARI
    # ─────────────────────────────────────────────
    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return {
            0: ("ID", "id"),
            1: (self.tr("Cari Kodu"), "customer_code"),
            2: (self.tr("Ticari Ünvan"), "fullname"),
            3: (self.tr("Vergi Dairesi"), "tax_office"),
            4: (self.tr("Vergi No / TCKN"), "tax_number"),
            5: (self.tr("Telefon"), "phone"),
            6: (self.tr("E-Posta"), "email"),
            7: (self.tr("Adres"), "address"),
            8: (self.tr("Durum"), "status"),
            9: (self.tr("Mecra"), "group_name"),
            10: (self.tr("Grubu"), "sub_group_1"),
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
            QPushButton:disabled {{ color: #94a3b8; background-color: #f8fafc; }}
        """

    # ─────────────────────────────────────────────
    # ANA UI KURULUMU
    # ─────────────────────────────────────────────
    def init_base_ui(self):
        self.profile_manager = ProfileManager(profile_key=self.profile_key)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

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
            }
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
        """

        # ─────────────────────────────────────────
        # 1. SOL PANEL — CARİ İŞLEMLERİ (ActionBarWidget)
        # ─────────────────────────────────────────
        self.action_bar = ActionBarWidget(
            group_title="CARİ İŞLEMLERİ",
            show_buttons=["new", "edit", "duplicate", "delete", "passive", "excel", "refresh", "close"],
            initial_open=False,
            panel_width=220,
            parent=self,
        )
        self.left_panel = self.action_bar.edge_panel
        register_layout_hint(self.left_panel, "Müşteriler & Cariler", "Sol Cari İşlemleri Paneli")

        # Sinyal bağlantıları
        self.action_bar.new_clicked.connect(self.on_new_clicked)
        self.action_bar.edit_clicked.connect(self.on_edit_clicked)
        self.action_bar.duplicate_clicked.connect(self.on_duplicate_clicked)
        self.action_bar.delete_clicked.connect(self.on_delete_clicked)
        self.action_bar.passive_clicked.connect(self.on_passive_clicked)
        self.action_bar.excel_clicked.connect(self.on_excel_clicked)
        self.action_bar.refresh_clicked.connect(self.refresh_table)
        self.action_bar.close_clicked.connect(self.close_tab)

        # Geriye dönük buton referansları
        self.btn_new = self.action_bar.btn_new
        self.btn_edit = self.action_bar.btn_edit
        self.btn_duplicate = self.action_bar.btn_duplicate
        self.btn_delete = self.action_bar.btn_delete
        self.btn_passive = self.action_bar.btn_passive
        self.btn_excel = self.action_bar.btn_excel
        self.btn_refresh = self.action_bar.btn_refresh

        # GRUP 2: GÖRÜNÜM PROFİLLERİ (Sol Panele Ek Akordiyon Olarak Eklenir)
        self.sec_profiles = CollapsibleSection("GÖRÜNÜM PROFİLLERİ", is_expanded=True)

        lbl_prof = QLabel("Aktif Profil:")
        lbl_prof.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.combo_profiles = QComboBox()
        self.combo_profiles.setStyleSheet(combo_style)
        self.combo_profiles.currentTextChanged.connect(self._on_profile_changed)

        prof_btn_lyt = QHBoxLayout()
        prof_btn_lyt.setSpacing(4)
        btn_save_prof = QPushButton("💾 Kaydet")
        btn_save_prof.setStyleSheet(self.toolbar_btn_style())
        btn_save_prof.clicked.connect(self.save_current_profile)
        btn_cols = QPushButton("⚙️ Sütunlar")
        btn_cols.setStyleSheet(self.toolbar_btn_style())
        btn_cols.clicked.connect(self.open_column_manager)
        prof_btn_lyt.addWidget(btn_save_prof)
        prof_btn_lyt.addWidget(btn_cols)

        self.sec_profiles.add_widget(lbl_prof)
        self.sec_profiles.add_widget(self.combo_profiles)
        self.sec_profiles.add_layout(prof_btn_lyt)
        self.action_bar.add_custom_section(self.sec_profiles)

        main_layout.addWidget(self.action_bar)

        # ─────────────────────────────────────────
        # 2. ORTA PANEL — TABLO + SAYFALAMA (PaginationWidget)
        # ─────────────────────────────────────────
        center_container = QWidget()
        register_layout_hint(center_container, "Müşteriler & Cariler", "Orta Tablo Paneli")
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(5, 0, 5, 0)
        center_layout.setSpacing(6)

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

        # Bağımsız Sayfalama Barı (PaginationWidget)
        self.pagination_widget = PaginationWidget(page_sizes=[25, 50, 100], parent=self)
        self.pagination_widget.page_changed.connect(self._on_page_index_changed)
        self.pagination_widget.page_size_changed.connect(self._on_page_size_val_changed)

        # Geriye dönük sayfalama referansları
        self.lbl_page = self.pagination_widget.lbl_page_info
        self.lbl_page_info = self.pagination_widget.lbl_page_info
        self.combo_page_size = self.pagination_widget.combo_page_size
        self.btn_first = self.pagination_widget.btn_first_page
        self.btn_prev = self.pagination_widget.btn_prev_page
        self.btn_next = self.pagination_widget.btn_next_page
        self.btn_last = self.pagination_widget.btn_last_page

        center_layout.addWidget(self.pagination_widget)
        main_layout.addWidget(center_container, 1)

        # ─────────────────────────────────────────
        # 3. SAĞ PANEL — FİLTRELER & DOSYA (FilterWidget & ExportWidget)
        # ─────────────────────────────────────────
        self.filter_widget = FilterWidget(
            group_title="FİLTRELER",
            show_filters=["search", "status", "group"],
            status_options=["Tümü", "Sadece Aktifler", "Sadece Pasifler"],
            group_options=["Tümü", "Müşteriler", "Tedarikçiler", "Personel"],
            initial_open=False,
            panel_width=220,
            parent=self,
        )
        self.right_panel = self.filter_widget.edge_panel
        register_layout_hint(self.right_panel, "Müşteriler & Cariler", "Sağ Filtreler ve Dosya Paneli")

        self.filter_widget.filter_changed.connect(lambda _: self._on_filter_changed())
        self.filter_widget.filters_cleared.connect(self.clear_filters)

        # Geriye dönük filtre referansları
        self.search_box = self.filter_widget.search_box
        self.cmb_status = self.filter_widget.cmb_status
        self.cmb_group = self.filter_widget.cmb_group
        self.sec_filters = self.filter_widget.sec_filters

        # GRUP 2: DOSYA & AKTARIM (ExportWidget)
        self.export_widget = ExportWidget(
            group_title="DOSYA & AKTARIM",
            show_buttons=["export_excel", "report"],
            initial_open=True,
            parent=self,
        )
        self.export_widget.export_excel_clicked.connect(self.on_excel_clicked)
        self.export_widget.report_clicked.connect(
            lambda: QMessageBox.information(self, "Rapor", "Cari hesap ekstresi üretiliyor..."),
        )
        self.sec_export = self.export_widget.section

        self.filter_widget.add_custom_section(self.export_widget)
        main_layout.addWidget(self.filter_widget)

        # Profilleri yükle, panelleri kapat, tabloyu doldur
        self._load_profiles()

        # F5 kısayolu — en sona, layout bittikten sonra
        from PyQt6.QtGui import QKeySequence, QShortcut
        self.sc_refresh = QShortcut(QKeySequence("F5"), self)
        self.sc_refresh.activated.connect(self.refresh_table)

        self.left_panel.close_panel()
        self.right_panel.close_panel()
        self.refresh_table()

    # ─────────────────────────────────────────────
    # PROFİL YÖNETİMİ
    # ─────────────────────────────────────────────
    def _load_profiles(self):
        if not hasattr(self, "combo_profiles"):
            return
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()
        profiles = self.profile_manager.load_profiles()
        for name in profiles.keys():
            self.combo_profiles.addItem(name)
        active = self.profile_manager.get_active_profile_name()
        idx = self.combo_profiles.findText(active)
        if idx >= 0:
            self.combo_profiles.setCurrentIndex(idx)
        self.combo_profiles.blockSignals(False)

    def _on_profile_changed(self, profile_name):
        if not profile_name:
            return
        p = self.profile_manager.get_profile(profile_name)
        if p and hasattr(self, "filterable_table"):
            self.filterable_table.apply_view_profile(p)

    def save_current_profile(self):
        active_name = self.combo_profiles.currentText() or "Varsayılan"
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

    # ─────────────────────────────────────────────
    # SAYFALAMA
    # ─────────────────────────────────────────────
    def _on_page_index_changed(self, page: int):
        self.current_page = page
        self.refresh_table()

    def _on_page_size_val_changed(self, page_size: int):
        self.per_page = page_size
        self.current_page = 1
        self.refresh_table()

    def _go_page(self, direction: str):
        if hasattr(self, "pagination_widget"):
            if direction == "first":
                self.pagination_widget.go_to_first_page()
            elif direction == "prev":
                self.pagination_widget.go_to_prev_page()
            elif direction == "next":
                self.pagination_widget.go_to_next_page()
            elif direction == "last":
                self.pagination_widget.go_to_last_page()
        else:
            total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
            if direction == "first":
                self.current_page = 1
            elif direction == "prev" and self.current_page > 1:
                self.current_page -= 1
            elif direction == "next" and self.current_page < total_pages:
                self.current_page += 1
            elif direction == "last":
                self.current_page = total_pages
            self.refresh_table()

    def _on_page_size_changed(self, text: str):
        try:
            self.per_page = int(text.split()[0])
            self.current_page = 1
            self.refresh_table()
        except Exception:
            pass

    # ─────────────────────────────────────────────
    # FİLTRE
    # ─────────────────────────────────────────────
    def _on_filter_changed(self):
        self.current_page = 1
        if hasattr(self, "pagination_widget"):
            self.pagination_widget.set_current_page(1)
        self.refresh_table()

    def clear_filters(self):
        if hasattr(self, "filter_widget") and self.filter_widget.get_filters():
            self.filter_widget.clear_filters()
        else:
            if hasattr(self, "search_box"):
                self.search_box.clear()
            if hasattr(self, "cmb_status"):
                self.cmb_status.setCurrentIndex(0)
            if hasattr(self, "cmb_group"):
                self.cmb_group.setCurrentIndex(0)
            self.current_page = 1
            if hasattr(self, "pagination_widget"):
                self.pagination_widget.reset()
            self.refresh_table()

    # ─────────────────────────────────────────────
    # VERİ YÜKLEMESİ
    # ─────────────────────────────────────────────
    def refresh_table(self):
        self.table_model.removeRows(0, self.table_model.rowCount())

        if not self.db:
            # Demo verisi
            demo = [
                ("996", "24M2", "24 METREKARE", "ZİNCİRLİKUYU VD.", "", "", "", "GÜLBAHAR MAH.", "Aktif", "LOCAL", ""),
                ("995", "2ELPARCA", "2 NCI EL PARCA", "", "", "", "", "", "Aktif", "LOCAL", ""),
                ("994", "4MDITALLDON", "4M DİJİTAL", "MALTEPE VD.", "0012227185", "", "", "MUSTAFA KEMA.", "Pasif", "LOCAL", ""),
            ]
            for row in demo:
                self.table_model.appendRow([QStandardItem(v) for v in row])
            self.total_records = len(demo)
            if hasattr(self, "pagination_widget"):
                self.pagination_widget.set_total(self.total_records)
                self.pagination_widget.set_current_page(self.current_page)
            elif hasattr(self, "lbl_page"):
                self.lbl_page.setText(f"Sayfa 1 / 1 (Toplam: {self.total_records})")
            return

        try:
            stmt = select(Customer).where(Customer.is_deleted == False)

            # Şirket filtresi — alan adı kontrolü
            if hasattr(Customer, "company_id"):
                stmt = stmt.where(Customer.company_id == self.company_id)

            # Arama filtresi
            search = self.search_box.text().strip()
            if search:
                stmt = stmt.where(
                    Customer.fullname.ilike(f"%{search}%") |
                    Customer.customer_code.ilike(f"%{search}%") |
                    Customer.tax_number.ilike(f"%{search}%"),
                )

            # Durum filtresi
            durum = self.cmb_status.currentText()
            if durum == "Sadece Aktifler":
                stmt = stmt.where(Customer.status == 1)
            elif durum == "Sadece Pasifler":
                stmt = stmt.where(Customer.status == 0)

            # Grup filtresi
            grup = self.cmb_group.currentText()
            if grup == "Müşteriler":
                stmt = stmt.where(Customer.group_name.ilike("%müşteri%") | Customer.sub_group_1.ilike("%müşteri%"))
            elif grup == "Tedarikçiler":
                stmt = stmt.where(Customer.group_name.ilike("%tedarikçi%") | Customer.sub_group_1.ilike("%tedarikçi%"))
            elif grup == "Personel":
                stmt = stmt.where(Customer.group_name.ilike("%personel%") | Customer.sub_group_1.ilike("%personel%"))


            stmt = stmt.order_by(Customer.fullname)
            records = self.db.scalars(stmt).all()
            self.total_records = len(records)

            if hasattr(self, "pagination_widget"):
                self.pagination_widget.set_total(self.total_records)
                self.pagination_widget.set_current_page(self.current_page)
            elif hasattr(self, "lbl_page"):
                total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
                self.lbl_page.setText(f"Sayfa {self.current_page} / {total_pages} (Toplam: {self.total_records})")

            start = (self.current_page - 1) * self.per_page
            page_records = records[start:start + self.per_page]

            for c in page_records:
                durum_txt = "Aktif" if getattr(c, "status", 1) else "Pasif"
                row = [
                    QStandardItem(str(c.id)),
                    QStandardItem(c.customer_code or ""),
                    QStandardItem(c.fullname or ""),
                    QStandardItem(getattr(c, "tax_office", "") or ""),
                    QStandardItem(c.tax_number or ""),
                    QStandardItem(c.phone or ""),
                    QStandardItem(getattr(c, "email", "") or ""),
                    QStandardItem(getattr(c, "address", "") or ""),
                    QStandardItem(durum_txt),
                    QStandardItem(getattr(c, "group_name", "") or ""),
                    QStandardItem(getattr(c, "sub_group_1", "") or ""),
                ]
                # Koşullu renklendirme: Pasif = gri
                if not getattr(c, "status", 1):
                    for item in row:
                        item.setForeground(Qt.GlobalColor.gray)
                self.table_model.appendRow(row)

        except Exception as e:
            logger.error(f"Cari listesi yüklenirken hata: {e}")
            QMessageBox.warning(self, "Hata", f"Veriler yüklenirken hata oluştu:\n{e}")

    # ─────────────────────────────────────────────
    # SEÇİM
    # ─────────────────────────────────────────────
    def get_selected_id(self) -> int | None:
        sel = self.table_view.selectionModel().selectedRows()
        if not sel:
            return None
        item = self.table_model.item(sel[0].row(), 0)
        return int(item.text()) if item and item.text().isdigit() else None

    def get_selected_customer(self):
        cid = self.get_selected_id()
        if not cid or not self.db:
            return None
        return self.db.get(Customer, cid)

    def on_selection_changed(self):
        has_sel = self.get_selected_id() is not None
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        self.btn_duplicate.setEnabled(has_sel)
        self.btn_passive.setEnabled(has_sel)

    # ─────────────────────────────────────────────
    # CRUD İŞLEMLERİ
    # ─────────────────────────────────────────────
    def on_new_clicked(self):
        try:
            from src.desktop.ui.customers import CustomerDialog
            dlg = CustomerDialog(
                db_session=self.db,
                company_id=self.company_id,
                parent=self,
            )
            if dlg.exec():
                self.refresh_table()
                self.toast_requested.emit("Yeni cari eklendi.", "success")
        except Exception as e:
            logger.error(f"Cari dialog açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Form açılamadı:\n{e}")

    def on_edit_clicked(self):
        cid = self.get_selected_id()
        if not cid:
            QMessageBox.information(self, "Uyarı", "Düzenlenecek cariyi seçin.")
            return
        try:
            from src.desktop.ui.customers import CustomerDialog
            dlg = CustomerDialog(
                db_session=self.db,
                company_id=self.company_id,
                customer_id=cid,
                parent=self,
            )
            if dlg.exec():
                self.refresh_table()
                self.toast_requested.emit("Cari güncellendi.", "success")
        except Exception as e:
            logger.error(f"Cari dialog açılamadı: {e}")
            QMessageBox.critical(self, "Hata", f"Form açılamadı:\n{e}")

    def on_duplicate_clicked(self):
        customer = self.get_selected_customer()
        if not customer:
            QMessageBox.information(self, "Uyarı", "Lütfen kopyalanacak cariyi seçin.")
            return
        try:
            new_c = Customer()
            for col in Customer.__table__.columns:
                if col.name not in ("id", "created_at", "updated_at"):
                    setattr(new_c, col.name, getattr(customer, col.name, None))
            new_c.customer_code = (customer.customer_code or "") + "-KOPYA"
            new_c.fullname = (customer.fullname or "") + " (Kopya)"
            self.db.add(new_c)
            self.db.commit()
            self.refresh_table()
            self.toast_requested.emit("Cari kopyalandı.", "info")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", str(e))

    def on_delete_clicked(self):
        customer = self.get_selected_customer()
        if not customer:
            QMessageBox.information(self, "Uyarı", "Lütfen silinecek cariyi seçin.")
            return
        reply = QMessageBox.question(
            self, "Silme Onayı",
            f"'{customer.fullname}' adlı cari silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                customer.is_deleted = True
                self.db.commit()
                self.refresh_table()
                self.toast_requested.emit("Cari silindi.", "warning")
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Hata", str(e))

    def on_passive_clicked(self):
        customer = self.get_selected_customer()
        if not customer:
            QMessageBox.information(self, "Uyarı", "Lütfen bir cari seçin.")
            return
        try:
            customer.status = 0 if getattr(customer, "status", 1) else 1
            self.db.commit()
            durum = "Aktif" if customer.status else "Pasif"
            self.refresh_table()
            self.toast_requested.emit(f"'{customer.fullname}' → {durum}", "info")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", str(e))

    def on_excel_clicked(self):
        try:
            import openpyxl
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "cari_listesi.xlsx", "Excel (*.xlsx)")
            if not path:
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Cari Listesi"
            headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
            ws.append(headers)
            for r in range(self.table_model.rowCount()):
                row = [self.table_model.item(r, c).text() for c in range(self.table_model.columnCount())]
                ws.append(row)
            wb.save(path)
            self.toast_requested.emit("Excel dışa aktarıldı.", "success")
        except ImportError:
            QMessageBox.warning(self, "Uyarı", "openpyxl bulunamadı.\npip install openpyxl")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    # ─────────────────────────────────────────────
    # SAĞ TIK MENÜSÜ
    # ─────────────────────────────────────────────
    def show_context_menu(self, pos):
        from src.desktop.managers.theme_manager import ThemeManager
        index = self.table_view.indexAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())

        act_new = QAction("➕ Yeni Cari", self)
        act_new.triggered.connect(self.on_new_clicked)
        menu.addAction(act_new)

        if index.isValid():
            self.table_view.selectRow(index.row())
            act_edit = QAction("✏️ Değiştir", self)
            act_edit.triggered.connect(self.on_edit_clicked)
            act_del = QAction("🗑️ Sil", self)
            act_del.triggered.connect(self.on_delete_clicked)
            act_dup = QAction("📋 Kopyala", self)
            act_dup.triggered.connect(self.on_duplicate_clicked)
            act_pas = QAction("⏸️ Pasife Al / Aktife Al", self)
            act_pas.triggered.connect(self.on_passive_clicked)
            menu.addAction(act_edit)
            menu.addAction(act_del)
            menu.addSeparator()
            menu.addAction(act_dup)
            menu.addAction(act_pas)

        self.filterable_table.add_column_actions_to_menu(menu)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))
