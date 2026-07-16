import os
import shutil
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableView, QTabWidget, QMessageBox, QComboBox, QFormLayout, QGroupBox,
    QHeaderView, QDialog, QFileDialog, QMenu
)
from PyQt6.QtCore import QAbstractTableModel, Qt, pyqtSignal, QModelIndex, QThreadPool
from PyQt6.QtGui import QFont, QAction, QPixmap

from src.core.models import Product, Order, Site, Category
from src.desktop.core.workers import SyncWorker
from src.core.sync.pull_engine import PullEngine
from src.core.sync.push_engine import PushEngine
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.adapters.woocommerce.woocommerce_client import WooCommerceClient
from src.adapters.woocommerce.woocommerce_adapter import WooCommerceAdapter
from src.core.security.keyring_store import get_api_key
from src.adapters.mappers import map_remote_to_product, map_remote_to_order


class ProductTableModel(QAbstractTableModel):
    """SQL LIMIT/OFFSET ve dinamik filtreleme/sıralama yeteneğine sahip, bellek dostu özel masaüstü tablo veri modeli."""

    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
        self.headers = [
            self.tr("ID"),
            self.tr("Stok Kodu (SKU)"),
            self.tr("Ürün Adı"),
            self.tr("Referans Fiyat"),
            self.tr("Stok"),
            self.tr("Özel Kod"),
            self.tr("Kategori")
        ]
        self.page_size = 50
        self.cache = {}
        
        # Filtre ve Sıralama Parametreleri
        self.search_text = ""
        self.category_filter = -1
        self.sort_col = 0
        self.sort_order = Qt.SortOrder.AscendingOrder
        
        self.total_count = 0
        self.refresh_count()

    def refresh_count(self):
        query = self.db.query(Product).filter(Product.is_deleted == False)
        if self.search_text:
            query = query.filter(
                (Product.name.like(f"%{self.search_text}%")) |
                (Product.sku.like(f"%{self.search_text}%"))
            )
        if self.category_filter != -1:
            query = query.filter(Product.category_id == self.category_filter)
            
        self.total_count = query.count()
        self.cache.clear()

    def rowCount(self, parent=QModelIndex()):
        return self.total_count

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def _load_row(self, row_idx):
        """İstenen satırı cache'de yoksa veritabanından lazy-loading mantığıyla çeker."""
        if row_idx in self.cache:
            return self.cache[row_idx]
            
        # İlgili sayfayı toplu olarak çek
        page_idx = (row_idx // self.page_size) * self.page_size
        query = self.db.query(Product).filter(Product.is_deleted == False)
        
        if self.search_text:
            query = query.filter(
                (Product.name.like(f"%{self.search_text}%")) |
                (Product.sku.like(f"%{self.search_text}%"))
            )
        if self.category_filter != -1:
            query = query.filter(Product.category_id == self.category_filter)
            
        # Sıralama
        sort_attr = Product.id
        if self.sort_col == 1:
            sort_attr = Product.sku
        elif self.sort_col == 2:
            sort_attr = Product.name
        elif self.sort_col == 3:
            sort_attr = Product.base_price
        elif self.sort_col == 4:
            sort_attr = Product.stock
        elif self.sort_col == 5:
            sort_attr = Product.custom_code
            
        if self.sort_order == Qt.SortOrder.DescendingOrder:
            query = query.order_by(sort_attr.desc())
        else:
            query = query.order_by(sort_attr.asc())
            
        page_products = query.limit(self.page_size).offset(page_idx).all()
        for idx, prod in enumerate(page_products):
            self.cache[page_idx + idx] = prod
            
        return self.cache.get(row_idx)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < self.total_count):
            return None

        product = self._load_row(index.row())
        if not product:
            return None
            
        col = index.column()

        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if col == 0:
                return str(product.id)
            elif col == 1:
                return product.sku
            elif col == 2:
                return product.name
            elif col == 3:
                return product.base_price if role == Qt.ItemDataRole.EditRole else f"{product.base_price:.2f} TL"
            elif col == 4:
                return product.stock if role == Qt.ItemDataRole.EditRole else str(product.stock)
            elif col == 5:
                return product.custom_code or ""
            elif col == 6:
                return product.category.name if product.category else "-"
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.headers[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        # SKU, İsim, Fiyat, Stok ve Özel Kod hücreleri inline düzenlenebilir
        if index.column() in (1, 2, 3, 4, 5):
            return Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole:
            product = self._load_row(index.row())
            if not product:
                return False
                
            col = index.column()
            try:
                if col == 1:
                    product.sku = str(value).strip()
                elif col == 2:
                    product.name = str(value).strip()
                elif col == 3:
                    product.base_price = float(value)
                elif col == 4:
                    product.stock = int(value)
                elif col == 5:
                    product.custom_code = str(value).strip()
                    
                self.db.commit()
                self.dataChanged.emit(index, index, [role])
                return True
            except Exception as e:
                self.db.rollback()
                return False
        return False

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        self.sort_col = column
        self.sort_order = order
        self.cache.clear()
        self.layoutChanged.emit()

    def set_filters(self, search_text, category_id):
        self.layoutAboutToBeChanged.emit()
        self.search_text = search_text
        self.category_filter = category_id
        self.refresh_count()
        self.layoutChanged.emit()


class ProductDetailDialog(QDialog):
    """Ürün düzenleme ve resim yönetimi için detay penceresi."""

    def __init__(self, db_session, product_id=None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.product_id = product_id
        self.image_dest_path = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(self.tr("Ürün Detay Kartı"))
        self.resize(500, 600)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        
        form_group = QGroupBox(self.tr("Ürün Bilgileri"))
        form_layout = QFormLayout(form_group)
        
        self.sku_input = QLineEdit()
        self.name_input = QLineEdit()
        self.desc_input = QLineEdit()
        self.price_input = QLineEdit()
        self.stock_input = QLineEdit()
        self.code_input = QLineEdit()
        
        self.cat_combo = QComboBox()
        self.load_categories()
        
        form_layout.addRow(self.tr("Stok Kodu (SKU):"), self.sku_input)
        form_layout.addRow(self.tr("Ürün Adı:"), self.name_input)
        form_layout.addRow(self.tr("Açıklama:"), self.desc_input)
        form_layout.addRow(self.tr("Kategori:"), self.cat_combo)
        form_layout.addRow(self.tr("Referans Fiyat (TL):"), self.price_input)
        form_layout.addRow(self.tr("Stok Miktarı:"), self.stock_input)
        form_layout.addRow(self.tr("Özel Kod:"), self.code_input)
        
        main_layout.addWidget(form_group)
        
        # Resim Önizleme Bölümü
        img_group = QGroupBox(self.tr("Ürün Resmi"))
        img_layout = QHBoxLayout(img_group)
        
        self.img_label = QLabel()
        self.img_label.setFixedSize(120, 120)
        self.img_label.setStyleSheet("border: 1px dashed #7f8c8d; background-color: #f5f6fa;")
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_label.setText(self.tr("Resim Yok"))
        
        img_btn_layout = QVBoxLayout()
        self.select_img_btn = QPushButton(self.tr("Resim Seç..."))
        self.select_img_btn.clicked.connect(self.select_image)
        self.remove_img_btn = QPushButton(self.tr("Resmi Kaldır"))
        self.remove_img_btn.clicked.connect(self.remove_image)
        
        img_btn_layout.addWidget(self.select_img_btn)
        img_btn_layout.addWidget(self.remove_img_btn)
        img_btn_layout.addStretch()
        
        img_layout.addWidget(self.img_label)
        img_layout.addLayout(img_btn_layout)
        
        main_layout.addWidget(img_group)
        
        # Kaydet/Kapat Butonları
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton(self.tr("Kaydet"))
        self.save_btn.clicked.connect(self.save_product)
        self.save_btn.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 6px;")
        
        self.cancel_btn = QPushButton(self.tr("Kapat"))
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)
        
        if self.product_id:
            self.load_product_data()

    def load_categories(self):
        self.cat_combo.clear()
        self.cat_combo.addItem(self.tr("Kategorisiz"), -1)
        categories = self.db.query(Category).all()
        for cat in categories:
            self.cat_combo.addItem(cat.name, cat.id)

    def load_product_data(self):
        prod = self.db.query(Product).filter(Product.id == self.product_id).first()
        if prod:
            self.sku_input.setText(prod.sku)
            self.name_input.setText(prod.name)
            self.desc_input.setText(prod.description or "")
            self.price_input.setText(str(prod.base_price))
            self.stock_input.setText(str(prod.stock))
            self.code_input.setText(prod.custom_code or "")
            
            if prod.category_id:
                idx = self.cat_combo.findData(prod.category_id)
                self.cat_combo.setCurrentIndex(idx)
                
            if prod.image_path and os.path.exists(prod.image_path):
                self.show_image(prod.image_path)
                self.image_dest_path = prod.image_path

    def show_image(self, path):
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            self.img_label.setPixmap(pixmap.scaled(self.img_label.size(), Qt.AspectRatioMode.KeepAspectRatio))
        else:
            self.img_label.setText(self.tr("Resim Yok"))

    def select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, self.tr("Resim Dosyası Seçin"), "", "Images (*.png *.jpg *.jpeg *.webp)")
        if file_path:
            # data/images/ dizinini oluştur
            img_dir = Path("data/images")
            img_dir.mkdir(parents=True, exist_ok=True)
            
            # Resmi hedef dizine kopyala
            dest_file = img_dir / Path(file_path).name
            try:
                shutil.copy(file_path, dest_file)
                self.image_dest_path = str(dest_file)
                self.show_image(self.image_dest_path)
            except Exception as e:
                QMessageBox.critical(self, self.tr("Hata"), f"Resim kopyalanamadı: {str(e)}")

    def remove_image(self):
        self.image_dest_path = None
        self.img_label.clear()
        self.img_label.setText(self.tr("Resim Yok"))

    def save_product(self):
        sku = self.sku_input.text().strip()
        name = self.name_input.text().strip()
        if not sku or not name:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Stok kodu (SKU) ve Ürün Adı zorunludur."))
            return
            
        try:
            price = float(self.price_input.text()) if self.price_input.text() else 0.0
            stock = int(self.stock_input.text()) if self.stock_input.text() else 0
        except ValueError:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Fiyat ve Stok sayısal olmalıdır."))
            return
            
        cat_id = self.cat_combo.currentData()
        if cat_id == -1:
            cat_id = None
            
        try:
            if self.product_id:
                prod = self.db.query(Product).filter(Product.id == self.product_id).first()
            else:
                prod = Product()
                self.db.add(prod)
                
            prod.sku = sku
            prod.name = name
            prod.description = self.desc_input.text().strip()
            prod.base_price = price
            prod.stock = stock
            prod.custom_code = self.code_input.text().strip()
            prod.category_id = cat_id
            prod.image_path = self.image_dest_path
            
            self.db.commit()
            self.accept()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, self.tr("Hata"), f"Kayıt sırasında hata oluştu: {str(e)}")


class ResourcesWidget(QWidget):
    """Ürünlerin listelendiği, sütunların özelleştirilebildiği ve asenkron senkronize edildiği DataGrid."""

    sync_started = pyqtSignal(str)
    sync_finished = pyqtSignal(str)

    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
        self.threadpool = QThreadPool.globalInstance()
        self.hidden_columns = set()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)

        # Başlık ve Üst Butonlar
        top_layout = QHBoxLayout()
        title_lbl = QLabel(self.tr("Ürün Veri Yönetimi (DataGrid)"))
        title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_lbl.setStyleSheet("color: #2c3e50;")
        
        self.pull_btn = QPushButton(self.tr("🔄 Uzak Sistemden Çek (Pull)"))
        self.pull_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.pull_btn.clicked.connect(self.trigger_pull)
        
        self.push_btn = QPushButton(self.tr("🚀 Uzak Sisteme Gönder (Push)"))
        self.push_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        self.push_btn.clicked.connect(self.trigger_push)

        top_layout.addWidget(self.pull_btn)
        top_layout.addWidget(self.push_btn)
        top_layout.addStretch()
        top_layout.addWidget(title_lbl)
        layout.addLayout(top_layout)

        # Arama ve Hızlı Filtre Paneli
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)
        
        filter_layout.addWidget(QLabel(self.tr("Arama:")))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("İsim veya SKU arayın..."))
        self.search_input.textChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.search_input)
        
        filter_layout.addWidget(QLabel(self.tr("Kategori:")))
        self.cat_filter_combo = QComboBox()
        self.cat_filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.cat_filter_combo)
        
        self.add_prod_btn = QPushButton(self.tr("➕ Yeni Ürün Ekle"))
        self.add_prod_btn.clicked.connect(self.add_new_product)
        self.add_prod_btn.setStyleSheet("background-color: #00a8ff; color: white; padding: 6px; font-weight: bold;")
        
        self.import_prod_btn = QPushButton(self.tr("📥 İçe Aktar"))
        self.import_prod_btn.clicked.connect(self.open_import_dialog)
        self.import_prod_btn.setStyleSheet("background-color: #3b82f6; color: white; padding: 6px; font-weight: bold;")
        
        self.export_prod_btn = QPushButton(self.tr("📤 Dışa Aktar"))
        self.export_prod_btn.clicked.connect(self.export_products)
        self.export_prod_btn.setStyleSheet("background-color: #64748b; color: white; padding: 6px; font-weight: bold;")
        
        filter_layout.addWidget(self.add_prod_btn)
        filter_layout.addWidget(self.import_prod_btn)
        filter_layout.addWidget(self.export_prod_btn)
        
        layout.addLayout(filter_layout)

        # Tablo Görünümü
        self.prod_table = QTableView()
        self.prod_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.prod_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.prod_table.setSortingEnabled(True)
        
        self.prod_table.setStyleSheet("""
            QTableView {
                background-color: #ffffff;
                border: 1px solid #dcdde1;
                border-radius: 6px;
            }
        """)
        
        # Sütun Başlığı Sağ Tık Menüsü (Görünüm Özelleştirme)
        self.prod_table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.prod_table.horizontalHeader().customContextMenuRequested.connect(self.show_header_menu)
        
        # Çift Tıklama Düzenleme Tetikleyicisi
        self.prod_table.doubleClicked.connect(self.on_row_double_clicked)
        
        layout.addWidget(self.prod_table)
        
        self.load_categories_filter()
        self.refresh_products()
        self.load_view_settings()

    def load_categories_filter(self):
        self.cat_filter_combo.clear()
        self.cat_filter_combo.addItem(self.tr("Tümü"), -1)
        try:
            categories = self.db.query(Category).all()
            for cat in categories:
                self.cat_filter_combo.addItem(cat.name, cat.id)
        except Exception:
            pass

    def refresh_products(self):
        search_txt = self.search_input.text().strip()
        cat_id = self.cat_filter_combo.currentData() or -1
        
        self.prod_model = ProductTableModel(self.db)
        self.prod_model.set_filters(search_txt, cat_id)
        self.prod_table.setModel(self.prod_model)
        
        self.apply_hidden_columns()

    def on_filter_changed(self):
        self.refresh_products()

    def on_row_double_clicked(self, index):
        # Eğer çift tıklanan sütun inline düzenlenebilir bir alan değilse Detay Dialog'unu aç
        if index.column() in (0, 6):
            product_id = int(self.prod_model.data(self.prod_model.index(index.row(), 0)))
            dialog = ProductDetailDialog(self.db, product_id, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh_products()

    def add_new_product(self):
        dialog = ProductDetailDialog(self.db, None, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_products()

    def open_import_dialog(self):
        from src.desktop.ui.import_dialog import ExcelImportDialog
        dialog = ExcelImportDialog(self.db, entity_type="product", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_products()

    def export_products(self):
        from src.core.importer import PRODUCT_FIELDS, export_to_excel_file
        file_path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Ürün Listesini Kaydet"), "urunler.xlsx",
            "Excel Dosyası (*.xlsx)"
        )
        if file_path:
            try:
                products = self.db.query(Product).filter(Product.is_deleted == False).all()
                export_to_excel_file(file_path, PRODUCT_FIELDS, products)
                QMessageBox.information(self, self.tr("Başarılı"), self.tr("Ürün listesi başarıyla dışa aktarıldı."))
            except Exception as e:
                QMessageBox.critical(self, self.tr("Hata"), f"Dışa aktarım hatası: {e}")

    def show_header_menu(self, pos):
        menu = QMenu(self)
        for col_idx in range(self.prod_model.columnCount()):
            col_name = self.prod_model.headerData(col_idx, Qt.Orientation.Horizontal)
            action = QAction(col_name, menu, checkable=True)
            action.setChecked(col_idx not in self.hidden_columns)
            
            # Sütunun durumuna göre check işlemini ata
            def toggle_col(checked, idx=col_idx):
                if checked:
                    self.hidden_columns.discard(idx)
                else:
                    self.hidden_columns.add(idx)
                self.apply_hidden_columns()
                self.save_view_settings()
                
            action.triggered.connect(toggle_col)
            menu.addAction(action)
            
        menu.addSeparator()
        dia_action = QAction(self.tr("⚙️ Kolonları Yapılandır (DIA)"), menu)
        def open_dia_column_manager():
            from src.desktop.ui.column_manager import ColumnManagerDialog
            headers_dict = {}
            for idx in range(self.prod_model.columnCount()):
                headers_dict[idx] = (self.prod_model.headerData(idx, Qt.Orientation.Horizontal), "")
            dlg = ColumnManagerDialog(headers_dict, self.hidden_columns, "view_settings", self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.hidden_columns = dlg.get_hidden_columns()
                self.apply_hidden_columns()
        dia_action.triggered.connect(open_dia_column_manager)
        menu.addAction(dia_action)
        
        menu.exec(self.prod_table.horizontalHeader().mapToGlobal(pos))

    def apply_hidden_columns(self):
        for col_idx in range(self.prod_model.columnCount()):
            if col_idx in self.hidden_columns:
                self.prod_table.setColumnHidden(col_idx, True)
            else:
                self.prod_table.setColumnHidden(col_idx, False)

    def save_view_settings(self):
        # Sütun tercihlerini JSON formatında yerel veritabanına veya dosyaya kaydeder
        settings_path = Path("data/view_settings.json")
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(list(self.hidden_columns), f)
        except Exception:
            pass

    def load_view_settings(self):
        settings_path = Path("data/view_settings.json")
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    hidden = json.load(f)
                    self.hidden_columns = set(hidden)
                self.apply_hidden_columns()
            except Exception:
                pass

    def trigger_pull(self):
        def pull_action():
            sites = self.db.query(Site).filter(Site.is_active == True).all()
            total_added = 0
            total_updated = 0
            engine = PullEngine(self.db)
            
            for site in sites:
                api_key = get_api_key(site.api_key_account)
                if not api_key:
                    continue

                if site.cms_type == "dolibarr":
                    client = DolibarrClient(base_url=site.url, api_key=api_key)
                    adapter = DolibarrAdapter(site_id=site.id, client=client)
                elif site.cms_type == "woocommerce":
                    ck, cs = api_key.split(":", 1)
                    client = WooCommerceClient(base_url=site.url, consumer_key=ck, consumer_secret=cs)
                    adapter = WooCommerceAdapter(site_id=site.id, client=client)
                else:
                    continue

                added, updated = engine.pull_resource(
                    adapter=adapter,
                    fetch_method_name="fetch_products",
                    model_class=Product,
                    mapper_func=map_remote_to_product,
                    site_id=site.id
                )
                total_added += added
                total_updated += updated
            return total_added, total_updated

        worker = SyncWorker(pull_action)
        worker.signals.started.connect(lambda: self.on_sync_started("PULL"))
        worker.signals.finished.connect(lambda res: self.on_sync_finished("PULL", res))
        worker.signals.error.connect(lambda err: self.on_sync_error("PULL", err))
        self.threadpool.start(worker)

    def trigger_push(self):
        def push_action():
            engine = PushEngine(self.db)
            return engine.push_pending_changes()

        worker = SyncWorker(push_action)
        worker.signals.started.connect(lambda: self.on_sync_started("PUSH"))
        worker.signals.finished.connect(lambda res: self.on_sync_finished("PUSH", res))
        worker.signals.error.connect(lambda err: self.on_sync_error("PUSH", err))
        self.threadpool.start(worker)

    def on_sync_started(self, type_str):
        self.pull_btn.setEnabled(False)
        self.push_btn.setEnabled(False)
        self.sync_started.emit(self.tr(f"{type_str} senkronizasyonu arka planda başlatıldı..."))

    def on_sync_finished(self, type_str, result):
        self.pull_btn.setEnabled(True)
        self.push_btn.setEnabled(True)
        self.refresh_products()
        
        added, updated = result
        msg = self.tr(f"{type_str} senkronizasyonu başarıyla tamamlandı. İşlenen: {added} yeni, {updated} güncelleme.")
        self.sync_finished.emit(msg)
        QMessageBox.information(self, self.tr("Senkronizasyon Başarılı"), msg)

    def on_sync_error(self, type_str, err_msg):
        self.pull_btn.setEnabled(True)
        self.push_btn.setEnabled(True)
        self.sync_finished.emit(self.tr(f"{type_str} senkronizasyonu başarısız: {err_msg}"))
        QMessageBox.critical(self, self.tr("Hata"), f"{self.tr('Senkronizasyon sırasında hata oluştu')}:\n{err_msg}")
