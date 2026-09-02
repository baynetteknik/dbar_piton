"""
ToyaUI — Stok Kart Liste Ekranı (STKLIST001)
ListeŞablonu kullanır — quotations.py ve cari_list_screen.py ile aynı mimari.

Bağımlılıklar:
    - ActionBarWidget
    - FilterWidget  
    - PaginationWidget
    - ExportWidget
    - FilterableTableView
"""

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import Product
from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.managers.theme_manager import ThemeManager
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.components.layout_hint_helper import register_layout_hint
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.widgets.action_bar_widget import ActionBarWidget
from src.desktop.ui.widgets.export_widget import ExportWidget
from src.desktop.ui.widgets.filter_widget import FilterWidget
from src.desktop.ui.widgets.pagination_widget import PaginationWidget

logger = logging.getLogger(__name__)


class StokListScreen(ThreePanelBaseWidget):
    """
    Stok Kart Liste Ekranı — STKLIST001
    Teklif ve Cari ekranıyla aynı şablonu kullanır.
    """

    toast_requested = pyqtSignal(str, str)

    # Kısayol kodu
    SCREEN_ID = "STKLIST001"

    def __init__(self, db_session=None, company_id: int = 1, parent=None):
        self.company_id = company_id
        self.profile_key = "stok_list"
        self.current_page = 1
        self.per_page = 25
        self.total_records = 0
        self._products_cache: list = []

        super().__init__(
            db_session=db_session,
            profile_key=self.profile_key,
            module_name="Stok Yönetimi",
        )
        self.setObjectName("StokCanvas")
        register_layout_hint(self, "Stok Yönetimi", "Stok Kart Ana Ekranı")

    # ─────────────────────────────────────────────
    # SÜTUN TANIMLARI
    # ─────────────────────────────────────────────
    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return {
            0:  ("ID",           "id"),
            1:  ("Stok Kodu",    "sku"),
            2:  ("Barkod",       "barcode"),
            3:  ("Ürün Adı",     "name"),
            4:  ("Birim",        "unit"),
            5:  ("Kategori",     "category"),
            6:  ("Marka",        "brand"),
            7:  ("Alış Fiyatı",  "purchase_price"),
            8:  ("Satış Fiyatı", "sale_price"),
            9:  ("KDV %",        "vat_rate"),
            10: ("Stok",         "stock_quantity"),
            11: ("Krit. Stok",   "min_stock"),
            12: ("Durum",        "status"),
        }

    # ─────────────────────────────────────────────
    # ANA UI
    # ─────────────────────────────────────────────
    def init_base_ui(self):
        self.profile_manager = ProfileManager(profile_key=self.profile_key)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # ─── SOL PANEL — ActionBarWidget ───
        self.action_bar = ActionBarWidget(
            group_title="STOK İŞLEMLERİ",
            convert_label=None,           # Stok'ta dönüştür yok
            hide_buttons=["convert"],     # Dönüştür butonu gizli
            initial_open=False,
            panel_width=220,
            parent=self,
        )

        # Görünüm Profilleri akordiyonu ekle
        self.sec_profiles = CollapsibleSection("GÖRÜNÜM PROFİLLERİ", is_expanded=True)
        combo_style = "QComboBox { border:1px solid #cbd5e1; border-radius:4px; padding:2px 6px; font-size:11px; min-height:22px; }"
        self.combo_profiles = QComboBox()
        self.combo_profiles.setStyleSheet(combo_style)
        self.combo_profiles.currentTextChanged.connect(self._on_profile_changed)

        prof_btn_lyt = QHBoxLayout()
        prof_btn_lyt.setSpacing(4)
        btn_save_prof = QPushButton("💾 Kaydet")
        btn_save_prof.setStyleSheet("border:1px solid #cbd5e1; border-radius:4px; padding:4px 8px; font-size:11px;")
        btn_save_prof.clicked.connect(self.save_current_profile)
        btn_cols = QPushButton("⚙️ Sütunlar")
        btn_cols.setStyleSheet("border:1px solid #cbd5e1; border-radius:4px; padding:4px 8px; font-size:11px;")
        btn_cols.clicked.connect(self.open_column_manager)
        prof_btn_lyt.addWidget(btn_save_prof)
        prof_btn_lyt.addWidget(btn_cols)
        self.sec_profiles.add_widget(self.combo_profiles)
        self.sec_profiles.add_layout(prof_btn_lyt)

        self.action_bar.add_custom_section(self.sec_profiles)

        # Sinyal bağlantıları
        self.action_bar.new_clicked.connect(self.on_new_clicked)
        self.action_bar.edit_clicked.connect(self.on_edit_clicked)
        self.action_bar.duplicate_clicked.connect(self.on_duplicate_clicked)
        self.action_bar.delete_clicked.connect(self.on_delete_clicked)
        self.action_bar.bulk_delete_clicked.connect(self.on_bulk_delete_clicked)
        self.action_bar.passive_clicked.connect(self.on_passive_clicked)
        self.action_bar.excel_clicked.connect(self.on_excel_clicked)
        self.action_bar.refresh_clicked.connect(self.refresh_table)
        self.action_bar.close_clicked.connect(self.close_tab)

        main_layout.addWidget(self.action_bar)

        # ─── ORTA PANEL — Grid + Sayfalama ───
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(5, 0, 5, 0)
        center_layout.setSpacing(6)
        register_layout_hint(center_container, "Stok Yönetimi", "Orta Tablo Paneli")

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
        self.table_view.setSelectionBehavior(self.table_view.SelectionBehavior.SelectRows)
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

        # Sayfalama
        self.pagination = PaginationWidget(
            page_sizes=[25, 50, 100],
            parent=self,
        )
        self.pagination.page_changed.connect(self._on_page_changed)
        self.pagination.page_size_changed.connect(self._on_page_size_changed)
        center_layout.addWidget(self.pagination)

        main_layout.addWidget(center_container, 1)

        # ─── SAĞ PANEL — FilterWidget + ExportWidget ───
        self.filter_widget = FilterWidget(
            show_filters=["search", "status", "group"],
            status_options=["Tümü", "Sadece Aktifler", "Sadece Pasifler"],
            group_options=["Tümü", "Malzeme", "Hizmet", "Sarf Malzeme", "Demirbaş"],
            initial_open=False,
            panel_width=220,
            parent=self,
        )
        self.filter_widget.filter_changed.connect(self._on_filter_changed)
        self.filter_widget.filters_cleared.connect(self._on_filters_cleared)

        # Export widget'ı sağ panele ekle
        self.export_widget = ExportWidget(
            hide_buttons=["import_excel"],
            parent=self,
        )
        self.export_widget.export_excel_clicked.connect(self.on_excel_clicked)
        self.export_widget.export_pdf_clicked.connect(
            lambda: QMessageBox.information(self, "PDF", "PDF raporu hazırlanıyor..."),
        )
        self.filter_widget.add_custom_section(self.export_widget)

        main_layout.addWidget(self.filter_widget)

        # Paneller kapalı başlar, veriyi yükle
        self.left_panel = self.action_bar.edge_panel
        self.action_bar.close_panel()
        self.filter_widget.close_panel()
        self._load_profiles()

        # F5 kısayolu — en sona, layout bittikten sonra
        from PyQt6.QtGui import QKeySequence, QShortcut
        self.sc_refresh = QShortcut(QKeySequence("F5"), self)
        self.sc_refresh.activated.connect(self.refresh_table)

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

    def _on_profile_changed(self, name):
        p = self.profile_manager.get_profile(name)
        if p and hasattr(self, "filterable_table"):
            self.filterable_table.apply_view_profile(p)

    def save_current_profile(self):
        name = self.combo_profiles.currentText() or "Varsayılan"
        p = self.filterable_table.get_current_view_as_profile(name)
        self.profile_manager.save_profile(name, p)
        QMessageBox.information(self, "Profil", f"'{name}' kaydedildi.")

    def open_column_manager(self):
        self.filterable_table.open_column_manager_dialog()

    def close_tab(self):
        parent = self.parentWidget()
        while parent and not hasattr(parent, "removeTab"):
            parent = parent.parentWidget()
        if parent:
            idx = parent.indexOf(self) if hasattr(parent, "indexOf") else parent.currentIndex()
            if idx > 0:
                parent.removeTab(idx)

    # ─────────────────────────────────────────────
    # SAYFALAMA
    # ─────────────────────────────────────────────
    def _on_page_changed(self, page: int):
        self.current_page = page
        self.refresh_table()

    def _on_page_size_changed(self, size: int):
        self.per_page = size
        self.current_page = 1
        self.refresh_table()

    # ─────────────────────────────────────────────
    # FİLTRE
    # ─────────────────────────────────────────────
    def _on_filter_changed(self, filters: dict):
        self.current_page = 1
        self.refresh_table()

    def _on_filters_cleared(self):
        self.current_page = 1
        self.refresh_table()

    def _get_filters(self) -> dict:
        if hasattr(self, "filter_widget"):
            return self.filter_widget.get_filters()
        return {}

    # ─────────────────────────────────────────────
    # VERİ YÜKLEMESİ
    # ─────────────────────────────────────────────
    def refresh_table(self):
        self.table_model.removeRows(0, self.table_model.rowCount())
        filters = self._get_filters()

        if not self.db:
            self._load_demo_data()
            return

        try:
            stmt = select(Product).where(Product.is_deleted == False)

            # Arama filtresi
            search = filters.get("search", "").strip()
            if search:
                stmt = stmt.where(
                    Product.name.ilike(f"%{search}%") |
                    Product.sku.ilike(f"%{search}%") |
                    Product.barcode.ilike(f"%{search}%"),
                )

            # Durum filtresi
            durum = filters.get("status", "Tümü")
            if durum == "Sadece Aktifler":
                if hasattr(Product, "is_active"):
                    stmt = stmt.where(Product.is_active == True)
            elif durum == "Sadece Pasifler":
                if hasattr(Product, "is_active"):
                    stmt = stmt.where(Product.is_active == False)

            # Kategori filtresi
            grup = filters.get("group", "Tümü")
            if grup != "Tümü" and hasattr(Product, "category"):
                stmt = stmt.where(Product.category == grup)

            stmt = stmt.order_by(Product.name)
            records = self.db.scalars(stmt).all()
            self._products_cache = records
            self.total_records = len(records)

            # Sayfalama güncelle
            if hasattr(self, "pagination"):
                self.pagination.set_total(self.total_records)

            # DB varsa ama kayıt yoksa demo göster
            if self.total_records == 0:
                self._load_demo_data()
                return

            start = (self.current_page - 1) * self.per_page
            page_records = records[start:start + self.per_page]

            for p in page_records:
                durum_txt = "Aktif" if getattr(p, "is_active", True) else "Pasif"
                stok = float(getattr(p, "stock_quantity", 0) or 0)
                min_stok = float(getattr(p, "min_stock", 0) or 0)

                row = [
                    QStandardItem(str(p.id)),
                    QStandardItem(p.sku or ""),
                    QStandardItem(getattr(p, "barcode", "") or ""),
                    QStandardItem(p.name or ""),
                    QStandardItem(getattr(p, "unit", "Adet") or "Adet"),
                    QStandardItem(getattr(p, "category", "") or ""),
                    QStandardItem(getattr(p, "brand", "") or ""),
                    QStandardItem(f"{float(getattr(p, 'purchase_price', 0) or 0):,.2f} ₺"),
                    QStandardItem(f"{float(p.sale_price or 0):,.2f} ₺"),
                    QStandardItem(f"% {int(getattr(p, 'vat_rate', 20) or 20)}"),
                    QStandardItem(f"{stok:,.2f}"),
                    QStandardItem(f"{min_stok:,.2f}"),
                    QStandardItem(durum_txt),
                ]

                # Kritik stok uyarısı — kırmızı
                if stok <= min_stok and min_stok > 0:
                    for item in row:
                        item.setForeground(Qt.GlobalColor.red)

                # Pasif — gri
                if not getattr(p, "is_active", True):
                    for item in row:
                        item.setForeground(Qt.GlobalColor.gray)

                self.table_model.appendRow(row)

        except Exception as e:
            logger.error(f"Stok listesi yüklenirken hata: {e}")
            QMessageBox.warning(self, "Hata", f"Veriler yüklenemedi:\n{e}")

    def _load_demo_data(self):
        """DB varsa ama kayıt yoksa demo verisi göster."""
        demo = [
            ("1", "STK-001", "8697240000008", "VGA Sinyal Uzatma Kablosu 5M",
             "Metre", "Elektronik", "Baynet", "95,00 ₺", "150,00 ₺", "% 20", "42,00", "10,00", "Aktif"),
            ("2", "STK-002", "8697240000009", "Tükenmez Kalem Mavi 0.7mm",
             "Adet", "Kırtasiye", "-", "8,00 ₺", "15,00 ₺", "% 20", "180,00", "50,00", "Aktif"),
            ("3", "STK-003", "8697240000010", "A4 Fotokopi Kağıdı 80gr",
             "Paket", "Kırtasiye", "-", "75,00 ₺", "120,00 ₺", "% 20", "5,00", "20,00", "Aktif"),
            ("4", "HZM-001", "", "Teknik Servis Hizmeti",
             "Hizmet", "Hizmet", "-", "250,00 ₺", "450,00 ₺", "% 20", "999,00", "0,00", "Aktif"),
        ]
        for row_data in demo:
            items = [QStandardItem(v) for v in row_data]
            # Demo satırlar soluk gri
            for item in items:
                item.setForeground(Qt.GlobalColor.gray)
            # Kritik stok kontrolü (stok=5, min=20)
            if float(row_data[10].replace(",", ".")) <= float(row_data[11].replace(",", ".")):
                for item in items:
                    item.setForeground(Qt.GlobalColor.red)
            self.table_model.appendRow(items)

        self.total_records = len(demo)
        if hasattr(self, "pagination"):
            self.pagination.set_total(self.total_records)

    # ─────────────────────────────────────────────
    # SEÇİM
    # ─────────────────────────────────────────────
    def get_selected_id(self) -> int | None:
        sel = self.table_view.selectionModel().selectedRows()
        if not sel:
            return None
        item = self.table_model.item(sel[0].row(), 0)
        return int(item.text()) if item and item.text().isdigit() else None

    def get_selected_product(self):
        pid = self.get_selected_id()
        if not pid or not self.db:
            return None
        return self.db.get(Product, pid)

    def on_selection_changed(self):
        has = self.get_selected_id() is not None
        if hasattr(self, "action_bar"):
            self.action_bar.btn_edit.setEnabled(has)
            self.action_bar.btn_delete.setEnabled(has)
            self.action_bar.btn_duplicate.setEnabled(has)
            self.action_bar.btn_passive.setEnabled(has)

    # ─────────────────────────────────────────────
    # CRUD İŞLEMLERİ
    # ─────────────────────────────────────────────
    def on_new_clicked(self):
        try:
            from src.desktop.ui.stok_kart_dialog import StokKartDialog
            dlg = StokKartDialog(
                db_session=self.db,
                company_id=self.company_id,
                parent=self,
            )
            if dlg.exec():
                self.refresh_table()
                self.toast_requested.emit("Yeni stok kartı eklendi.", "success")
        except Exception as e:
            logger.error(f"Stok dialog açılırken hata: {e}")
            QMessageBox.critical(self, "Hata", f"Form açılamadı:\n{e}")

    def on_edit_clicked(self):
        pid = self.get_selected_id()
        if not pid:
            QMessageBox.information(self, "Uyarı", "Düzenlenecek stok kartını seçin.")
            return
        try:
            from src.desktop.ui.stok_kart_dialog import StokKartDialog
            dlg = StokKartDialog(
                db_session=self.db,
                company_id=self.company_id,
                product_id=pid,
                parent=self,
            )
            if dlg.exec():
                self.refresh_table()
                self.toast_requested.emit("Stok kartı güncellendi.", "success")
        except Exception as e:
            logger.error(f"Stok dialog açılırken hata: {e}")
            QMessageBox.critical(self, "Hata", f"Form açılamadı:\n{e}")

    def on_duplicate_clicked(self):
        product = self.get_selected_product()
        if not product:
            QMessageBox.information(self, "Uyarı", "Kopyalanacak stok kartı seçin.")
            return
        try:
            new_p = Product()
            for col in Product.__table__.columns:
                if col.name not in ("id", "created_at", "updated_at"):
                    setattr(new_p, col.name, getattr(product, col.name, None))
            new_p.sku = (product.sku or "") + "-KOPYA"
            new_p.name = (product.name or "") + " (Kopya)"
            self.db.add(new_p)
            self.db.commit()
            self.refresh_table()
            self.toast_requested.emit("Stok kartı kopyalandı.", "info")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", str(e))

    def on_delete_clicked(self):
        product = self.get_selected_product()
        if not product:
            QMessageBox.information(self, "Uyarı", "Silinecek stok kartı seçin.")
            return
        reply = QMessageBox.question(
            self, "Silme Onayı",
            f"'{product.name}' stok kartı silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                product.is_deleted = True
                self.db.commit()
                self.refresh_table()
                self.toast_requested.emit("Stok kartı silindi.", "warning")
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Hata", str(e))

    def on_bulk_delete_clicked(self):
        sel = self.table_view.selectionModel().selectedRows()
        if not sel:
            return
        reply = QMessageBox.question(
            self, "Toplu Sil",
            f"{len(sel)} stok kartı silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for idx in sel:
                    item = self.table_model.item(idx.row(), 0)
                    if item and item.text().isdigit():
                        p = self.db.get(Product, int(item.text()))
                        if p:
                            p.is_deleted = True
                self.db.commit()
                self.refresh_table()
                self.toast_requested.emit(f"{len(sel)} stok kartı silindi.", "warning")
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Hata", str(e))

    def on_passive_clicked(self):
        product = self.get_selected_product()
        if not product:
            QMessageBox.information(self, "Uyarı", "Bir stok kartı seçin.")
            return
        if not hasattr(product, "is_active"):
            QMessageBox.warning(self, "Uyarı", "Model güncellenmesi gerekiyor — is_active alanı eksik.")
            return
        try:
            product.is_active = not product.is_active
            self.db.commit()
            durum = "Aktif" if product.is_active else "Pasif"
            self.refresh_table()
            self.toast_requested.emit(f"'{product.name}' → {durum}", "info")
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", str(e))

    def on_excel_clicked(self):
        try:
            import openpyxl
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self, "Excel Kaydet", "stok_listesi.xlsx", "Excel (*.xlsx)",
            )
            if not path:
                return
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Stok Listesi"
            headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
            ws.append(headers)
            for r in range(self.table_model.rowCount()):
                ws.append([self.table_model.item(r, c).text()
                           for c in range(self.table_model.columnCount())])
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
        index = self.table_view.indexAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())

        act_new = QAction("➕ Yeni Stok Kartı", self)
        act_new.triggered.connect(self.on_new_clicked)
        menu.addAction(act_new)

        if index.isValid():
            self.table_view.selectRow(index.row())
            act_edit = QAction("✏️ Düzenle", self)
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
