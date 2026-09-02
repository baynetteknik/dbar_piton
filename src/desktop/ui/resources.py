import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QPixmap, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.woocommerce.woocommerce_adapter import WooCommerceAdapter
from src.adapters.woocommerce.woocommerce_client import WooCommerceClient
from src.core.data_manager import DataManager
from src.core.importer import export_to_excel_file
from src.core.models import Category, Product, Site
from src.core.security.keyring_store import get_api_key
from src.core.sync.pull_engine import PullEngine
from src.core.sync.push_engine import PushEngine
from src.desktop.core.workers import SyncWorker
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.components.layout_hint_helper import register_layout_hint
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.import_dialog import ExcelImportDialog

logger = logging.getLogger(__name__)


def apply_combo_style(cmb: QComboBox, min_width: int = 150):
    """QComboBox bileşenlerine temiz, yüksek kontrastlı ve tam okunabilir popup stili uygular."""
    cmb.setMinimumWidth(min_width)
    cmb.setMaxVisibleItems(12)
    cmb.setStyleSheet("""
        QComboBox {
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            padding: 5px 10px;
            background-color: #ffffff;
            color: #0f172a;
            font-size: 12px;
            font-weight: 600;
        }
        QComboBox:hover {
            border-color: #2563eb;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border-left: 1px solid #cbd5e1;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
            background-color: #f8fafc;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #64748b;
            margin-top: 1px;
        }
        QComboBox QAbstractItemView {
            border: 1px solid #94a3b8;
            background-color: #ffffff;
            color: #0f172a;
            selection-background-color: #2563eb;
            selection-color: #ffffff;
            outline: none;
            padding: 2px 0px;
            font-size: 12px;
            font-weight: 500;
        }
        QComboBox QAbstractItemView::item {
            min-height: 28px;
            padding: 4px 10px;
            background-color: #ffffff;
            color: #0f172a;
            border: none;
            border-radius: 0px;
        }
        QComboBox QAbstractItemView::item:hover,
        QComboBox QAbstractItemView::item:selected {
            background-color: #2563eb;
            color: #ffffff;
        }
    """)


class ProductDetailDialog(QDialog):
    """3-panelli düzene uygun, 9 sekmeli, yüksek okunabilirlikli ve büyütülmüş görsele sahip Stok Kart Bilgileri Penceresi."""

    def __init__(self, db_session, company_id: int, product_id=None, remote_id=None, read_only=False, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.company_id = company_id
        self.product_id = product_id
        self.remote_id = remote_id
        self.read_only = read_only
        self.photo_path = None

        self.working_mode = DataManager.get_company_mode(self.db, self.company_id)

        if self.product_id or self.remote_id:
            self.setWindowTitle("Stok Kart Bilgileri - Düzenle" if not read_only else "Stok Kart Bilgileri - İncele")
        else:
            self.setWindowTitle("Stok Kart Bilgileri - Yeni Ekle")

        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint,
        )
        self.setMinimumWidth(980)
        self.setMinimumHeight(680)
        self.init_ui()
        self.showMaximized()

        if self.product_id or self.remote_id:
            self.load_product_data()

    def dia_btn_style(self, bg_color="#3b82f6", hover_color="#2563eb", text_color="#ffffff"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """

    def init_ui(self):
        main_dialog_layout = QVBoxLayout(self)
        main_dialog_layout.setContentsMargins(10, 10, 10, 10)
        main_dialog_layout.setSpacing(6)

        input_style = """
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 5px 8px;
                background-color: #f8fafc;
                color: #0f172a;
                font-size: 12px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                background-color: #ffffff;
            }
        """

        groupbox_style = """
            QGroupBox {
                font-weight: bold;
                font-size: 11px;
                color: #1e3a8a;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 14px;
                padding-top: 14px;
                padding-left: 8px;
                padding-right: 8px;
                padding-bottom: 8px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 6px;
                background-color: #ffffff;
                color: #1e3a8a;
                font-size: 11px;
                font-weight: bold;
            }
        """

        # Üst Parametre & Depo Barı
        top_bar_frame = QFrame()
        top_bar_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        top_bar_lyt = QHBoxLayout(top_bar_frame)
        top_bar_lyt.setContentsMargins(10, 6, 10, 6)
        top_bar_lyt.setSpacing(12)

        top_bar_lyt.addWidget(QLabel("Firma:"))
        self.cmb_site = QComboBox()
        apply_combo_style(self.cmb_site, min_width=280)
        self.load_sites_combo()
        top_bar_lyt.addWidget(self.cmb_site)

        btn_depo_stock = QPushButton("📁 Depo Miktarları")
        btn_depo_stock.setStyleSheet(self.dia_btn_style("#2563eb", "#1d4ed8"))
        top_bar_lyt.addWidget(btn_depo_stock)
        top_bar_lyt.addStretch()

        main_dialog_layout.addWidget(top_bar_frame)

        # Temel Kart Bilgileri Alanı (Stok Türü, Kodu, Açıklama, Durum)
        core_frame = QFrame()
        core_frame.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        core_lyt = QVBoxLayout(core_frame)
        core_lyt.setContentsMargins(10, 8, 10, 8)
        core_lyt.setSpacing(6)

        row1_lyt = QHBoxLayout()
        row1_lyt.setSpacing(12)

        lbl_type = QLabel("Stok Türü:")
        lbl_type.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 12px;")
        row1_lyt.addWidget(lbl_type)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["Ticari Mal (TOR)", "Hizmet", "Hammadde", "Yarı Mamul", "Mamul"])
        apply_combo_style(self.cmb_type, min_width=180)
        row1_lyt.addWidget(self.cmb_type)

        self.chk_locked = QCheckBox("Kilitli")
        self.chk_locked.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")
        row1_lyt.addWidget(self.chk_locked)

        row1_lyt.addStretch()

        lbl_status = QLabel("Durum:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 12px;")
        row1_lyt.addWidget(lbl_status)

        self.cmb_status = QComboBox()
        self.cmb_status.addItem("Aktif", 1)
        self.cmb_status.addItem("Pasif", 0)
        apply_combo_style(self.cmb_status, min_width=140)
        row1_lyt.addWidget(self.cmb_status)

        core_lyt.addLayout(row1_lyt)

        row2_lyt = QHBoxLayout()
        row2_lyt.setSpacing(12)

        lbl_sku = QLabel("Stok Kodu (SKU) *:")
        lbl_sku.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 12px;")
        row2_lyt.addWidget(lbl_sku)

        self.txt_sku = QLineEdit()
        self.txt_sku.setPlaceholderText("Örn: 0957-2119")
        self.txt_sku.setStyleSheet(input_style)
        row2_lyt.addWidget(self.txt_sku, 1)

        lbl_name = QLabel("Açıklama (Ürün Adı) *:")
        lbl_name.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 12px;")
        row2_lyt.addWidget(lbl_name)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Örn: HP 15 + 32 VOLT 563 MA ADAPTÖR")
        self.txt_name.setStyleSheet(input_style)
        row2_lyt.addWidget(self.txt_name, 2)

        core_lyt.addLayout(row2_lyt)
        main_dialog_layout.addWidget(core_frame)

        # 9 Sekmeli Ana Tab Yapısı
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::panel {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #475569;
                padding: 6px 12px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #1e3a8a;
                border-bottom: 2px solid white;
            }
        """)

        # ----------------------------------------------------
        # SEKME 1: 1. Genel (Scroll Area ile sığmama korumalı)
        # ----------------------------------------------------
        tab_gen_scroll = QScrollArea()
        tab_gen_scroll.setWidgetResizable(True)
        tab_gen_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        tab_general_content = QWidget()
        tab_gen_lyt = QVBoxLayout(tab_general_content)
        tab_gen_lyt.setContentsMargins(10, 10, 10, 10)
        tab_gen_lyt.setSpacing(10)

        # Üst Kısım: 2 Kolon Form + Sağ Büyütülmüş Fotoğraf Çerçevesi
        gen_top_lyt = QHBoxLayout()
        gen_top_lyt.setSpacing(12)

        # Sol Kolon: Kodlar & Özel Kodlar
        box_codes = QGroupBox("KODLAR & ÖZEL KODLAR")
        box_codes.setStyleSheet(groupbox_style)
        box_codes_lyt = QFormLayout(box_codes)
        box_codes_lyt.setSpacing(6)

        self.cmb_category = QComboBox()
        apply_combo_style(self.cmb_category, min_width=250)
        self.load_categories()

        self.txt_brand = QLineEdit()
        self.txt_brand.setStyleSheet(input_style)
        self.txt_auth_code = QLineEdit()
        self.txt_auth_code.setStyleSheet(input_style)
        self.txt_origin = QLineEdit()
        self.txt_origin.setStyleSheet(input_style)

        box_codes_lyt.addRow("Grup Kodu (Kategori):", self.cmb_category)
        box_codes_lyt.addRow("Marka:", self.txt_brand)
        box_codes_lyt.addRow("Yetki Kodu:", self.txt_auth_code)
        box_codes_lyt.addRow("Menşei:", self.txt_origin)

        gen_top_lyt.addWidget(box_codes, 1)

        # Orta Kolon: KDV & Fatura
        box_vat = QGroupBox("KDV & FATURA PARAMETRELERİ")
        box_vat.setStyleSheet(groupbox_style)
        box_vat_lyt = QFormLayout(box_vat)
        box_vat_lyt.setSpacing(6)

        self.txt_vat_rate = QLineEdit("20,00")
        self.txt_vat_rate.setStyleSheet(input_style)
        self.txt_vat_buy = QLineEdit("20,00")
        self.txt_vat_buy.setStyleSheet(input_style)
        self.txt_vat_wholesale = QLineEdit("20,00")
        self.txt_vat_wholesale.setStyleSheet(input_style)

        self.txt_custom_code = QLineEdit()
        self.txt_custom_code.setStyleSheet(input_style)

        box_vat_lyt.addRow("Satış KDV (%):", self.txt_vat_rate)
        box_vat_lyt.addRow("Alış KDV (%):", self.txt_vat_buy)
        box_vat_lyt.addRow("Toptan KDV (%):", self.txt_vat_wholesale)
        box_vat_lyt.addRow("Özel Kod / GÇB:", self.txt_custom_code)

        gen_top_lyt.addWidget(box_vat, 1)

        # Sağ Kolon: Büyütülmüş Fotoğraf / Resim Kutusu
        box_img = QGroupBox("ÜRÜN GÖRSELİ")
        box_img.setStyleSheet(groupbox_style)
        box_img_lyt = QVBoxLayout(box_img)

        self.lbl_image = QLabel("Görsel Yok")
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setFixedSize(220, 160)
        self.lbl_image.setStyleSheet("border: 1px dashed #cbd5e1; background-color: #f8fafc; color: #94a3b8; border-radius: 6px; font-weight: bold;")

        img_btn_lyt = QHBoxLayout()
        btn_browse_img = QPushButton("🖼️ Resim Seç")
        btn_browse_img.setStyleSheet(self.dia_btn_style("#3b82f6", "#2563eb"))
        btn_browse_img.clicked.connect(self.browse_image)

        btn_clear_img = QPushButton("🗑️ Kaldır")
        btn_clear_img.setStyleSheet(self.dia_btn_style("#ef4444", "#dc2626"))
        btn_clear_img.clicked.connect(self.clear_image)

        img_btn_lyt.addWidget(btn_browse_img)
        img_btn_lyt.addWidget(btn_clear_img)

        box_img_lyt.addWidget(self.lbl_image, 0, Qt.AlignmentFlag.AlignCenter)
        box_img_lyt.addLayout(img_btn_lyt)

        gen_top_lyt.addWidget(box_img, 0)
        tab_gen_lyt.addLayout(gen_top_lyt)

        # Alt Kısım: Birim ve Fiyat Tablosu (Ana Birim: AD)
        box_price = QGroupBox("ANA BİRİM & FİYAT TANIMLARI")
        box_price.setStyleSheet(groupbox_style)
        box_price_lyt = QVBoxLayout(box_price)
        box_price_lyt.setSpacing(6)

        unit_lyt = QHBoxLayout()
        unit_lyt.addWidget(QLabel("Ana Birim:"))
        self.cmb_unit = QComboBox()
        self.cmb_unit.addItems(["AD (Adet)", "KG (Kilogram)", "METRE", "PAKET", "KUTU"])
        apply_combo_style(self.cmb_unit, min_width=160)
        unit_lyt.addWidget(self.cmb_unit)

        unit_lyt.addSpacing(20)
        unit_lyt.addWidget(QLabel("Barkod:"))
        self.txt_barcode = QLineEdit()
        self.txt_barcode.setPlaceholderText("Barkod numarası...")
        self.txt_barcode.setStyleSheet(input_style)
        unit_lyt.addWidget(self.txt_barcode, 1)

        box_price_lyt.addLayout(unit_lyt)

        # Fiyat Girdileri (Alış / Satış)
        prices_form = QFormLayout()
        prices_form.setSpacing(6)

        self.txt_base_price = QLineEdit("0,0000")
        self.txt_base_price.setStyleSheet(input_style)
        self.txt_sell_price = QLineEdit("0,0000")
        self.txt_sell_price.setStyleSheet(input_style)
        self.txt_stock = QLineEdit("0")
        self.txt_stock.setStyleSheet(input_style)

        prices_form.addRow("ALIŞ FİYATI (TL):", self.txt_base_price)
        prices_form.addRow("SATIŞ FİYATI (TL):", self.txt_sell_price)
        prices_form.addRow("Stok Miktarı:", self.txt_stock)

        box_price_lyt.addLayout(prices_form)
        tab_gen_lyt.addWidget(box_price)

        tab_gen_scroll.setWidget(tab_general_content)
        self.tab_widget.addTab(tab_gen_scroll, "1. Genel")

        # Diğer 8 Sekme
        for title in ["2. Diğer", "3. Özel Vergi/Matrah", "4. Ek Malzemeler", "5. Alternatifler", "6. Not", "7. Ek Alanlar", "8. Raf Yeri", "9. Tedarikçi/Müşteri"]:
            dummy_widget = QWidget()
            dummy_lyt = QVBoxLayout(dummy_widget)
            dummy_lyt.setContentsMargins(16, 16, 16, 16)
            lbl_dummy = QLabel(f"{title} sekmesine ait parametreler buradan yönetilir.")
            lbl_dummy.setStyleSheet("color: #64748b; font-size: 12px;")
            dummy_lyt.addWidget(lbl_dummy)
            dummy_lyt.addStretch()
            self.tab_widget.addTab(dummy_widget, title)

        main_dialog_layout.addWidget(self.tab_widget, 1)

        # Alt Butonlar
        btn_box = QHBoxLayout()
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setStyleSheet(self.dia_btn_style("#3b82f6", "#2563eb"))
        self.btn_save.clicked.connect(self.save_product)

        self.btn_save_new = QPushButton("💾 Kaydet & Yeni")
        self.btn_save_new.setStyleSheet(self.dia_btn_style("#1e40af", "#1e3a8a"))
        self.btn_save_new.clicked.connect(self.save_and_new_product)

        self.btn_cancel = QPushButton("❌ Vazgeç")
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        if self.read_only:
            self.txt_sku.setReadOnly(True)
            self.txt_name.setReadOnly(True)
            self.txt_base_price.setReadOnly(True)
            self.txt_sell_price.setReadOnly(True)
            self.txt_stock.setReadOnly(True)
            self.cmb_status.setEnabled(False)
            self.cmb_type.setEnabled(False)
            self.btn_save.hide()
            self.btn_save_new.hide()

        btn_box.addStretch()
        btn_box.addWidget(self.btn_save)
        btn_box.addWidget(self.btn_save_new)
        btn_box.addWidget(self.btn_cancel)
        main_dialog_layout.addLayout(btn_box)

    def load_sites_combo(self):
        self.cmb_site.clear()
        try:
            sites = self.db.query(Site).filter(Site.is_active == True, Site.is_deleted == False).all()
            for site in sites:
                self.cmb_site.addItem(f"🏢 {site.name}", site.id)
            if self.company_id:
                idx = self.cmb_site.findData(self.company_id)
                if idx != -1:
                    self.cmb_site.setCurrentIndex(idx)
        except Exception as e:
            logger.error(f"Firma listesi yüklenemedi: {e}")

    def load_categories(self):
        self.cmb_category.clear()
        self.cmb_category.addItem("[Kategori Yok / Genel]", None)
        try:
            categories = self.db.query(Category).all()
            for cat in categories:
                self.cmb_category.addItem(cat.name, cat.id)
        except Exception as e:
            logger.error(f"Kategoriler yüklenemedi: {e}")

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Resim Seçin", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if file_path:
            self.photo_path = file_path
            pix = QPixmap(file_path)
            if not pix.isNull():
                self.lbl_image.setPixmap(pix.scaled(215, 155, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def clear_image(self):
        self.photo_path = None
        self.lbl_image.setText("Görsel Yok")

    def load_product_data(self):
        try:
            prod = self.db.query(Product).filter(Product.id == self.product_id).first()
            if prod:
                self.txt_sku.setText(prod.sku or "")
                self.txt_name.setText(prod.name or "")
                self.txt_base_price.setText(str(prod.base_price or 0.0))
                self.txt_sell_price.setText(str(prod.price or 0.0))
                self.txt_stock.setText(str(prod.stock or 0))
                self.txt_barcode.setText(prod.barcode or "")
                self.txt_custom_code.setText(prod.custom_code or "")

                idx = self.cmb_category.findData(prod.category_id)
                if idx != -1:
                    self.cmb_category.setCurrentIndex(idx)

                status_idx = self.cmb_status.findData(1 if (prod.status is None or prod.status == 1) else 0)
                if status_idx != -1:
                    self.cmb_status.setCurrentIndex(status_idx)

                if prod.image_path and os.path.exists(prod.image_path):
                    self.photo_path = prod.image_path
                    pix = QPixmap(prod.image_path)
                    if not pix.isNull():
                        self.lbl_image.setPixmap(pix.scaled(215, 155, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Stok kart bilgileri yüklenemedi: {e}")

    def save_product(self) -> bool:
        sku = self.txt_sku.text().strip()
        name = self.txt_name.text().strip()
        if not sku or not name:
            QMessageBox.warning(self, "Uyarı", "Stok Kodu (SKU) ve Açıklama (Ürün Adı) boş bırakılamaz.")
            return False

        try:
            base_price = float(self.txt_base_price.text().replace(",", "."))
            price = float(self.txt_sell_price.text().replace(",", "."))
            stock = int(self.txt_stock.text())
        except ValueError:
            QMessageBox.warning(self, "Uyarı", "Lütfen Fiyat ve Stok miktarı için geçerli sayılar girin.")
            return False

        cat_id = self.cmb_category.currentData()
        status_val = self.cmb_status.currentData()

        # Resim kaydetme işlemi
        saved_img_path = self.photo_path
        if self.photo_path and not self.photo_path.startswith("data/images"):
            img_dir = Path("data/images")
            img_dir.mkdir(parents=True, exist_ok=True)
            ext = Path(self.photo_path).suffix
            dest = img_dir / f"product_{sku}_{int(datetime.utcnow().timestamp())}{ext}"
            shutil.copy(self.photo_path, dest)
            saved_img_path = str(dest)

        try:
            if self.product_id:
                prod = self.db.query(Product).filter(Product.id == self.product_id).first()
                if prod:
                    prod.sku = sku
                    prod.name = name
                    prod.base_price = base_price
                    prod.price = price
                    prod.stock = stock
                    prod.category_id = cat_id
                    prod.status = status_val
                    prod.barcode = self.txt_barcode.text().strip()
                    prod.custom_code = self.txt_custom_code.text().strip()
                    if saved_img_path:
                        prod.image_path = saved_img_path
            else:
                prod = Product(
                    sku=sku,
                    name=name,
                    base_price=base_price,
                    price=price,
                    stock=stock,
                    category_id=cat_id,
                    status=status_val,
                    barcode=self.txt_barcode.text().strip(),
                    custom_code=self.txt_custom_code.text().strip(),
                    image_path=saved_img_path,
                )
                self.db.add(prod)

            self.db.commit()
            QMessageBox.information(self, "Başarılı", "Stok kart bilgileri kaydedildi.")
            self.accept()
            return True
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {e}")
            return False

    def save_and_new_product(self):
        self.txt_sell_price.setText("0,0000")
        self.txt_stock.setText("0")
        self.txt_barcode.clear()
        self.clear_image()


class ResourcesWidget(ThreePanelBaseWidget):
    """3-Panelli Düzen mimarisine ve gelişmiş stok kartı yönetim özelliklerine sahip Malzeme/Ürün Paneli."""

    products_updated = pyqtSignal()

    def __init__(self, db_session, company_id: int, parent=None):
        self.company_id = company_id
        self.active_sync_worker = None

        super().__init__(
            db_session=db_session,
            profile_key="resources",
            module_name="Stok / Malzeme Yönetimi",
            parent=parent,
        )
        register_layout_hint(self, "Stok Yönetimi", "Malzeme / Ürün Yönetim Paneli")

    def setup_headers_dict(self):
        return {
            0: ("Kart Kodu", "sku"),
            1: ("Açıklama", "name"),
            2: ("Türü", "custom_code"),
            3: ("Stok Miktarı", "stock"),
            4: ("Birim", "unit"),
            5: ("Alış Fiyatı", "base_price"),
            6: ("Satış Fiyatı", "price"),
            7: ("Kategori", "category_name"),
            8: ("Durum", "status"),
        }

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
        """

    def dia_btn_style(self, bg_color="#3b82f6", hover_color="#2563eb", text_color="#ffffff"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """

    def page_btn_style(self):
        return """
            QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
            QPushButton:disabled { background-color: #f1f5f9; color: #94a3b8; border-color: #e2e8f0; }
        """

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # Üst Depo & Filtre Barı (Görsel 1 Top Bar)
        top_bar_frame = QFrame()
        register_layout_hint(top_bar_frame, "Stok Yönetimi", "Üst Depo / Filtre Barı")
        top_bar_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        top_bar_lyt = QHBoxLayout(top_bar_frame)
        top_bar_lyt.setContentsMargins(10, 6, 10, 6)
        top_bar_lyt.setSpacing(12)

        top_bar_lyt.addWidget(QLabel("Firma:"))
        self.cmb_top_site = QComboBox()
        apply_combo_style(self.cmb_top_site, min_width=250)
        self.load_sites_top_combo()
        top_bar_lyt.addWidget(self.cmb_top_site)

        top_bar_lyt.addWidget(QLabel("Depo:"))
        self.cmb_top_depot = QComboBox()
        self.cmb_top_depot.addItem("10-MERKEZ DEPO", 10)
        apply_combo_style(self.cmb_top_depot, min_width=200)
        top_bar_lyt.addWidget(self.cmb_top_depot)

        top_bar_lyt.addWidget(QLabel("Tarih:"))
        self.date_top = QDateEdit(QDate.currentDate())
        self.date_top.setCalendarPopup(True)
        self.date_top.setStyleSheet("QDateEdit { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background-color: white; }")
        top_bar_lyt.addWidget(self.date_top)

        top_bar_lyt.addStretch()
        main_layout.addWidget(top_bar_frame)

        # Üç Panelli Düzen İçi Yatay Layout
        three_panel_layout = QHBoxLayout()
        three_panel_layout.setContentsMargins(0, 0, 0, 0)
        three_panel_layout.setSpacing(6)

        # SOL PANEL (EdgeTriggeredPanel)
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)
        register_layout_hint(self.left_panel, "Stok Yönetimi", "Sol Filtre Paneli")

        filter_content = QWidget()
        filter_lyt = QVBoxLayout(filter_content)
        filter_lyt.setContentsMargins(4, 4, 4, 4)
        filter_lyt.setSpacing(10)

        lbl_filter_title = QLabel("🔍 Filtre & Arama")
        lbl_filter_title.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 12px;")
        filter_lyt.addWidget(lbl_filter_title)

        lbl_search = QLabel("Kart Kodu / İsim Arama:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Hızlı arama yap...")
        self.txt_search.setStyleSheet("QLineEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background-color: white; font-size: 12px; }")
        self.txt_search.textChanged.connect(self.on_search_text_changed)
        filter_lyt.addWidget(lbl_search)
        filter_lyt.addWidget(self.txt_search)

        lbl_cat = QLabel("Kategori / Grup:")
        lbl_cat.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_cat = QComboBox()
        self.cmb_filter_cat.addItem("Tümü", None)
        self.load_filter_categories()
        apply_combo_style(self.cmb_filter_cat, min_width=200)
        self.cmb_filter_cat.currentIndexChanged.connect(self.on_filter_changed)
        filter_lyt.addWidget(lbl_cat)
        filter_lyt.addWidget(self.cmb_filter_cat)

        lbl_status = QLabel("Durum:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_status = QComboBox()
        self.cmb_filter_status.addItem("Tümü", -1)
        self.cmb_filter_status.addItem("Aktif", 1)
        self.cmb_filter_status.addItem("Pasif", 0)
        apply_combo_style(self.cmb_filter_status, min_width=140)
        self.cmb_filter_status.currentIndexChanged.connect(self.on_filter_changed)
        filter_lyt.addWidget(lbl_status)
        filter_lyt.addWidget(self.cmb_filter_status)
        filter_lyt.addStretch()

        self.left_panel.set_content(filter_content)
        three_panel_layout.addWidget(self.left_panel)

        # ORTA PANEL (DBGrid & Alt Buton Çubuğu & Sayfalama Barı)
        self.center_container = QWidget()
        center_lyt = QVBoxLayout(self.center_container)
        center_lyt.setContentsMargins(4, 0, 4, 0)
        center_lyt.setSpacing(8)

        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key="products",
            enable_profile_bar=False,
            parent=self,
        )
        self.table = self.filterable_table.table_view

        self.table_model = QStandardItemModel(self)
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
        self.table_model.setHorizontalHeaderLabels(headers)
        self.table.setModel(self.table_model)

        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setDefaultSectionSize(120)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.table.doubleClicked.connect(self.open_edit_product_dialog)

        self.table.setStyleSheet("""
            QTableView {
                border: 1px solid #cbd5e1;
                background-color: white;
                gridline-color: #f1f5f9;
                border-radius: 6px;
                font-size: 12px;
                color: #334155;
            }
            QTableView::item { padding: 6px; }
            QTableView::item:selected { background-color: #fef08a; color: #854d0e; font-weight: 600; }
            QHeaderView::section { background-color: #f8fafc; color: #475569; padding: 8px; border: none; border-right: 1px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; font-weight: bold; }
        """)
        center_lyt.addWidget(self.filterable_table, 1)

        # Alt İşlem Çubuğu ve Sayfalama Kontrolleri
        self.action_bar = QFrame()
        self.action_bar.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        action_bar_lyt = QHBoxLayout(self.action_bar)
        action_bar_lyt.setContentsMargins(8, 6, 8, 6)
        action_bar_lyt.setSpacing(8)

        self.btn_select = QPushButton("📌 Seç")
        self.btn_select.setStyleSheet(self.dia_btn_style("#2563eb", "#1d4ed8"))

        self.btn_add = QPushButton("➕ Ekle")
        self.btn_add.setStyleSheet(self.dia_btn_style("#3b82f6", "#2563eb"))
        self.btn_add.clicked.connect(self.open_add_product_dialog)

        self.btn_edit = QPushButton("✏️ Değiştir")
        self.btn_edit.setStyleSheet(self.dia_btn_style("#2563eb", "#1d4ed8"))
        self.btn_edit.clicked.connect(self.open_edit_product_dialog)

        self.btn_inspect = QPushButton("🔍 İncele")
        self.btn_inspect.setStyleSheet(self.dia_btn_style("#475569", "#334155"))
        self.btn_inspect.clicked.connect(self.inspect_product_dialog)

        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setStyleSheet(self.dia_btn_style("#ef4444", "#dc2626"))
        self.btn_delete.clicked.connect(self.delete_product)

        self.btn_print = QPushButton("🖨️ Yazdır")
        self.btn_print.setStyleSheet(self.dia_btn_style("#78350f", "#451a03"))

        self.btn_other = QPushButton("≡ Diğer")
        self.btn_other.setStyleSheet(self.dia_btn_style("#64748b", "#475569"))
        other_menu = QMenu(self)
        other_menu.addAction("🔄 Uzak Sistemden Çek (Pull)", self.trigger_pull)
        other_menu.addAction("🚀 Uzak Sisteme Gönder (Push)", self.trigger_push)
        other_menu.addSeparator()
        other_menu.addAction("📥 Excel İçe Aktar", self.open_import_dialog)
        other_menu.addAction("📤 Excel Dışa Aktar", self.export_products)
        self.btn_other.setMenu(other_menu)

        action_bar_lyt.addWidget(self.btn_select)
        action_bar_lyt.addWidget(self.btn_add)
        action_bar_lyt.addWidget(self.btn_edit)
        action_bar_lyt.addWidget(self.btn_inspect)
        action_bar_lyt.addWidget(self.btn_delete)
        action_bar_lyt.addWidget(self.btn_print)
        action_bar_lyt.addWidget(self.btn_other)

        action_bar_lyt.addStretch()

        # Sayfalama (Pagination) Kontrol Butonları ve Bilgisi
        self.btn_first_page = QPushButton("⏮")
        self.btn_first_page.setStyleSheet(self.page_btn_style())
        self.btn_first_page.clicked.connect(self.go_first_page)

        self.btn_prev_page = QPushButton("◀")
        self.btn_prev_page.setStyleSheet(self.page_btn_style())
        self.btn_prev_page.clicked.connect(self.go_prev_page)

        self.lbl_page_info = QLabel("Sayfa 1 / 1")
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px; padding: 0 4px;")

        self.btn_next_page = QPushButton("▶")
        self.btn_next_page.setStyleSheet(self.page_btn_style())
        self.btn_next_page.clicked.connect(self.go_next_page)

        self.btn_last_page = QPushButton("⏭")
        self.btn_last_page.setStyleSheet(self.page_btn_style())
        self.btn_last_page.clicked.connect(self.go_last_page)

        action_bar_lyt.addWidget(self.btn_first_page)
        action_bar_lyt.addWidget(self.btn_prev_page)
        action_bar_lyt.addWidget(self.lbl_page_info)
        action_bar_lyt.addWidget(self.btn_next_page)
        action_bar_lyt.addWidget(self.btn_last_page)

        # Sayfa Başına Kayıt Seçim Kutusu
        action_bar_lyt.addSpacing(6)
        action_bar_lyt.addWidget(QLabel("Sayfa Başı:"))
        self.cmb_page_size = QComboBox()
        self.cmb_page_size.addItem("25", 25)
        self.cmb_page_size.addItem("50", 50)
        self.cmb_page_size.addItem("100", 100)
        self.cmb_page_size.addItem("250", 250)
        self.cmb_page_size.addItem("Tümü", 0)
        self.cmb_page_size.setCurrentIndex(1)
        apply_combo_style(self.cmb_page_size, min_width=100)
        self.cmb_page_size.currentIndexChanged.connect(self.on_page_size_changed)
        action_bar_lyt.addWidget(self.cmb_page_size)

        action_bar_lyt.addSpacing(10)
        self.lbl_record_count = QLabel("Toplam Kayıt: 0")
        self.lbl_record_count.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        action_bar_lyt.addWidget(self.lbl_record_count)

        center_lyt.addWidget(self.action_bar)
        three_panel_layout.addWidget(self.center_container, 1)

        # SAĞ PANEL (EdgeTriggeredPanel)
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_content = QWidget()
        right_lyt = QVBoxLayout(right_content)
        right_lyt.setContentsMargins(4, 4, 4, 4)
        right_lyt.setSpacing(8)

        grp_prod = QFrame()
        grp_prod.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_prod_lyt = QVBoxLayout(grp_prod)
        grp_prod_lyt.setContentsMargins(6, 8, 6, 8)
        grp_prod_lyt.setSpacing(6)

        lbl_grp_prod = QLabel("STOK İŞLEMLERİ")
        lbl_grp_prod.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_prod.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_prod_lyt.addWidget(lbl_grp_prod)

        btn_r_add = QPushButton("➕ Yeni Stok Kartı")
        btn_r_add.setStyleSheet(self.toolbar_btn_style("#10b981", "#ffffff"))
        btn_r_add.clicked.connect(self.open_add_product_dialog)

        btn_r_edit = QPushButton("✏️ Değiştir")
        btn_r_edit.setStyleSheet(self.toolbar_btn_style())
        btn_r_edit.clicked.connect(self.open_edit_product_dialog)

        btn_r_inspect = QPushButton("🔍 İncele")
        btn_r_inspect.setStyleSheet(self.toolbar_btn_style())
        btn_r_inspect.clicked.connect(self.inspect_product_dialog)

        btn_r_delete = QPushButton("🗑️ Sil")
        btn_r_delete.setStyleSheet(self.toolbar_btn_style("#ef4444", "#ffffff"))
        btn_r_delete.clicked.connect(self.delete_product)

        grp_prod_lyt.addWidget(btn_r_add)
        grp_prod_lyt.addWidget(btn_r_edit)
        grp_prod_lyt.addWidget(btn_r_inspect)
        grp_prod_lyt.addWidget(btn_r_delete)
        right_lyt.addWidget(grp_prod)

        grp_sync = QFrame()
        grp_sync.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_sync_lyt = QVBoxLayout(grp_sync)
        grp_sync_lyt.setContentsMargins(6, 8, 6, 8)
        grp_sync_lyt.setSpacing(6)

        lbl_grp_sync = QLabel("SENK & DOSYA")
        lbl_grp_sync.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_sync.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_sync_lyt.addWidget(lbl_grp_sync)

        btn_r_pull = QPushButton("🔄 Çek (Pull)")
        btn_r_pull.setStyleSheet(self.toolbar_btn_style())
        btn_r_pull.clicked.connect(self.trigger_pull)

        btn_r_push = QPushButton("🚀 Gönder (Push)")
        btn_r_push.setStyleSheet(self.toolbar_btn_style())
        btn_r_push.clicked.connect(self.trigger_push)

        btn_r_import = QPushButton("📥 İçe Aktar")
        btn_r_import.setStyleSheet(self.toolbar_btn_style())
        btn_r_import.clicked.connect(self.open_import_dialog)

        btn_r_export = QPushButton("📤 Dışa Aktar")
        btn_r_export.setStyleSheet(self.toolbar_btn_style())
        btn_r_export.clicked.connect(self.export_products)

        grp_sync_lyt.addWidget(btn_r_pull)
        grp_sync_lyt.addWidget(btn_r_push)
        grp_sync_lyt.addWidget(btn_r_import)
        grp_sync_lyt.addWidget(btn_r_export)
        right_lyt.addWidget(grp_sync)

        grp_view = QFrame()
        grp_view.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_view_lyt = QVBoxLayout(grp_view)
        grp_view_lyt.setContentsMargins(6, 8, 6, 8)
        grp_view_lyt.setSpacing(6)

        lbl_grp_view = QLabel("GÖRÜNÜM")
        lbl_grp_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_view.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_view_lyt.addWidget(lbl_grp_view)

        btn_r_cols = QPushButton("⚙️ Kolonları Yapılandır")
        btn_r_cols.setStyleSheet(self.toolbar_btn_style())
        btn_r_cols.clicked.connect(self.filterable_table.open_column_manager_dialog)

        grp_view_lyt.addWidget(btn_r_cols)
        right_lyt.addWidget(grp_view)
        right_lyt.addStretch()

        right_scroll.setWidget(right_content)
        self.right_panel.set_content(right_scroll)
        three_panel_layout.addWidget(self.right_panel)

        main_layout.addLayout(three_panel_layout, 1)

    def load_sites_top_combo(self):
        self.cmb_top_site.clear()
        try:
            sites = self.db.query(Site).filter(Site.is_active == True, Site.is_deleted == False).all()
            for site in sites:
                self.cmb_top_site.addItem(f"🏢 {site.name}", site.id)
        except Exception as e:
            logger.error(f"Firma listesi yüklenemedi: {e}")

    def load_filter_categories(self):
        try:
            categories = self.db.query(Category).all()
            for cat in categories:
                self.cmb_filter_cat.addItem(cat.name, cat.id)
        except Exception as e:
            logger.error(f"Kategoriler yüklenemedi: {e}")

    def on_search_text_changed(self):
        self.current_page = 1
        self.load_products()

    def on_filter_changed(self):
        self.current_page = 1
        self.load_products()

    def on_page_size_changed(self):
        self.page_size = self.cmb_page_size.currentData()
        self.current_page = 1
        self.load_products()

    def go_first_page(self):
        if self.current_page > 1:
            self.current_page = 1
            self.load_products()

    def go_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_products()

    def go_next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_products()

    def go_last_page(self):
        if self.current_page < self.total_pages:
            self.current_page = self.total_pages
            self.load_products()

    def load_products(self):
        self.table_model.removeRows(0, self.table_model.rowCount())
        try:
            query = self.db.query(Product).filter(Product.is_deleted == False)

            search = self.txt_search.text().strip().lower()
            if search:
                query = query.filter(Product.sku.ilike(f"%{search}%") | Product.name.ilike(f"%{search}%"))

            cat_id = self.cmb_filter_cat.currentData()
            if cat_id is not None:
                query = query.filter(Product.category_id == cat_id)

            status_val = self.cmb_filter_status.currentData()
            if status_val != -1:
                query = query.filter(Product.status == status_val)

            # Toplam Eşleşen Kayıt Sayısını Hesaplama
            self.total_products = query.count()

            # Sayfa Sayısı Hesaplama
            if self.page_size > 0:
                self.total_pages = max(1, (self.total_products + self.page_size - 1) // self.page_size)
            else:
                self.total_pages = 1

            self.current_page = max(1, min(self.current_page, self.total_pages))

            # SQL Limit / Offset Sayfalama Uygulaması
            if self.page_size > 0:
                offset_val = (self.current_page - 1) * self.page_size
                query = query.offset(offset_val).limit(self.page_size)

            products = query.all()
            for prod in products:
                cat_name = prod.category.name if prod.category else "-"
                status_txt = "Aktif" if (prod.status is None or prod.status == 1) else "Pasif"
                row_items = [
                    QStandardItem(prod.sku or "-"),
                    QStandardItem(prod.name or "-"),
                    QStandardItem(prod.custom_code or "TOR"),
                    QStandardItem(str(prod.stock or 0)),
                    QStandardItem("AD"),
                    QStandardItem(f"{prod.base_price or 0.0:.2f} TL"),
                    QStandardItem(f"{prod.price or 0.0:.2f} TL"),
                    QStandardItem(cat_name),
                    QStandardItem(status_txt),
                ]
                row_items[0].setData(prod.id, Qt.ItemDataRole.UserRole)
                self.table_model.appendRow(row_items)

            # Sayfalama UI Durum Güncellemesi
            self.lbl_record_count.setText(f"Toplam Kayıt: {self.total_products} | Gösterilen: {len(products)}")
            self.lbl_page_info.setText(f"Sayfa {self.current_page} / {self.total_pages}")

            self.btn_first_page.setEnabled(self.current_page > 1)
            self.btn_prev_page.setEnabled(self.current_page > 1)
            self.btn_next_page.setEnabled(self.current_page < self.total_pages)
            self.btn_last_page.setEnabled(self.current_page < self.total_pages)
        except Exception as e:
            logger.error(f"Ürünler yüklenemedi: {e}")

    def get_selected_product_id(self) -> int | None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            return None
        row = indexes[0].row()
        item = self.table_model.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def open_add_product_dialog(self):
        dlg = ProductDetailDialog(self.db, company_id=self.company_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_products()

    def open_edit_product_dialog(self):
        prod_id = self.get_selected_product_id()
        if not prod_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz ürünü seçin.")
            return
        dlg = ProductDetailDialog(self.db, company_id=self.company_id, product_id=prod_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_products()

    def inspect_product_dialog(self):
        prod_id = self.get_selected_product_id()
        if not prod_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen incelemek istediğiniz ürünü seçin.")
            return
        dlg = ProductDetailDialog(self.db, company_id=self.company_id, product_id=prod_id, read_only=True, parent=self)
        dlg.exec()

    def delete_product(self):
        prod_id = self.get_selected_product_id()
        if not prod_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz ürünü seçin.")
            return

        try:
            prod = self.db.query(Product).filter(Product.id == prod_id).first()
            if prod:
                reply = QMessageBox.question(
                    self, "Onay", f"'{prod.name}' stok kartını silmek istediğinize emin misiniz?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    prod.is_deleted = True
                    self.db.commit()
                    QMessageBox.information(self, "Başarılı", "Stok kartı silindi.")
                    self.load_products()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Silme hatası: {e}")

    def show_table_context_menu(self, pos):
        menu = QMenu(self)
        action_add = QAction("➕ Yeni Stok Kartı Ekle", self)
        action_add.triggered.connect(self.open_add_product_dialog)

        action_edit = QAction("✏️ Seçili Kartı Değiştir", self)
        action_edit.triggered.connect(self.open_edit_product_dialog)

        action_inspect = QAction("🔍 Seçili Kartı İncele", self)
        action_inspect.triggered.connect(self.inspect_product_dialog)

        action_delete = QAction("🗑️ Seçili Kartı Sil", self)
        action_delete.triggered.connect(self.delete_product)

        action_pull = QAction("🔄 Uzak Sistemden Çek (Pull)", self)
        action_pull.triggered.connect(self.trigger_pull)

        action_push = QAction("🚀 Uzak Sisteme Gönder (Push)", self)
        action_push.triggered.connect(self.trigger_push)

        action_cols = QAction("⚙️ Kolonları Yapılandır", self)
        action_cols.triggered.connect(self.filterable_table.open_column_manager_dialog)

        menu.addAction(action_add)
        menu.addAction(action_edit)
        menu.addAction(action_inspect)
        menu.addSeparator()
        menu.addAction(action_delete)
        menu.addSeparator()
        menu.addAction(action_pull)
        menu.addAction(action_push)

        self.filterable_table.add_column_actions_to_menu(menu)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def trigger_pull(self):
        site = self.db.query(Site).filter(Site.id == self.company_id).first()
        if not site:
            QMessageBox.warning(self, "Hata", "Geçerli bir şirket bağlantısı bulunamadı.")
            return

        api_key = get_api_key(site.api_key_account)
        if not api_key:
            QMessageBox.warning(self, "Hata", "API anahtarı bulunamadı.")
            return

        self.sync_started.emit("pull")

        def run_pull():
            if site.cms_type == "dolibarr":
                client = DolibarrClient(base_url=site.url, api_key=api_key)
                adapter = DolibarrAdapter(site_id=site.id, client=client)
            else:
                ck, cs = api_key.split(":", 1)
                client = WooCommerceClient(base_url=site.url, consumer_key=ck, consumer_secret=cs)
                adapter = WooCommerceAdapter(site_id=site.id, client=client)

            engine = PullEngine(self.db, adapter)
            return engine.pull_products()

        worker = SyncWorker(run_pull)

        def on_finished(result, error_msg):
            self.sync_finished.emit("pull")
            if error_msg:
                QMessageBox.critical(self, "Hata", f"Pull senkronizasyonu başarısız: {error_msg}")
            else:
                QMessageBox.information(self, "Başarılı", f"Pull işlemi tamamlandı. Eklenen/Güncellenen: {result}")
                self.load_products()

        worker.signals.finished.connect(on_finished)
        self.threadpool.start(worker)

    def trigger_push(self):
        site = self.db.query(Site).filter(Site.id == self.company_id).first()
        if not site:
            QMessageBox.warning(self, "Hata", "Geçerli bir şirket bağlantısı bulunamadı.")
            return

        api_key = get_api_key(site.api_key_account)
        if not api_key:
            QMessageBox.warning(self, "Hata", "API anahtarı bulunamadı.")
            return

        self.sync_started.emit("push")

        def run_push():
            if site.cms_type == "dolibarr":
                client = DolibarrClient(base_url=site.url, api_key=api_key)
                adapter = DolibarrAdapter(site_id=site.id, client=client)
            else:
                ck, cs = api_key.split(":", 1)
                client = WooCommerceClient(base_url=site.url, consumer_key=ck, consumer_secret=cs)
                adapter = WooCommerceAdapter(site_id=site.id, client=client)

            engine = PushEngine(self.db, adapter)
            return engine.push_pending_changes()

        worker = SyncWorker(run_push)

        def on_finished(result, error_msg):
            self.sync_finished.emit("push")
            if error_msg:
                QMessageBox.critical(self, "Hata", f"Push senkronizasyonu başarısız: {error_msg}")
            else:
                QMessageBox.information(self, "Başarılı", f"Push işlemi tamamlandı. Gönderilen: {result}")
                self.load_products()

        worker.signals.finished.connect(on_finished)
        self.threadpool.start(worker)

    def open_import_dialog(self):
        dialog = ExcelImportDialog(self.db, entity_type="product", parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_products()

    def export_products(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Stok Listesini Kaydet", "stok_listesi.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            try:
                products = self.db.query(Product).filter(Product.is_deleted == False).all()
                data = [
                    {
                        "SKU": p.sku,
                        "Ürün Adı": p.name,
                        "Alış Fiyatı": p.base_price,
                        "Satış Fiyatı": p.price,
                        "Stok": p.stock,
                        "Kategori": p.category.name if p.category else "",
                    }
                    for p in products
                ]
                export_to_excel_file(data, file_path)
                QMessageBox.information(self, "Başarılı", "Stok listesi dışa aktarıldı.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dışa aktarım hatası: {e}")
