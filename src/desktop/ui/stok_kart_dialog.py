"""
Toya ERP - Stok Kart Ekle / Düzenle Diyaloğu (StokKartDialog)
customers.py / CustomerDialog mimarisine ve ToyaUI tasarım standartlarına uygundur.
"""

import logging
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.models import Product
from src.desktop.ui.components.layout_hint_helper import register_layout_hint

logger = logging.getLogger(__name__)

UNITS = [
    "Adet",
    "Kg",
    "Gram",
    "Litre",
    "Metre",
    "Paket",
    "Kutu",
    "Koli",
    "Hizmet",
    "Sefer",
]

CATEGORIES = [
    "Malzeme",
    "Hizmet",
    "Sarf Malzeme",
    "Demirbaş",
    "Hammadde",
    "Yarı Mamul",
]

VAT_RATES = ["% 20", "% 10", "% 1", "% 0"]
DEPOS = ["Ana Depo", "Merkez Depo", "Şube Depo", "Sanal Depo"]


class StokKartDialog(QDialog):
    """Gelişmiş sekmeli Stok Kartı Ekleme ve Düzenleme Ekranı."""

    def __init__(
        self,
        db_session=None,
        company_id: int = 1,
        product_id: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db_session
        self.company_id = company_id
        self.product_id = product_id
        self.photo_path: str | None = None

        title = (
            self.tr("Stok Kart Düzenle")
            if product_id
            else self.tr("Yeni Stok Kartı")
        )
        self.setWindowTitle(f"📦 {title}")
        self.setMinimumWidth(850)
        self.setMinimumHeight(580)
        register_layout_hint(self, "Stok Kart Formu", "Stok Ekle/Düzenle Diyaloğu")

        self.init_ui()

        if self.product_id:
            self.load_product()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(18)

        # ─── SOL TARAF: Sekmeler (TabWidget) ───
        left_layout = QVBoxLayout()
        self.tabs = QTabWidget()
        register_layout_hint(
            self.tabs, "Stok Kart Formu", "Form Sekmeleri Kapsayıcısı",
        )
        self.tabs.setStyleSheet("""
            QTabWidget::panel {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #475569;
                padding: 8px 16px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #1e3a8a;
                border-bottom: 2px solid white;
            }
        """)

        # ─── 1. Sekme: Genel Bilgiler ───
        tab_general = QWidget()
        register_layout_hint(tab_general, "Stok Kart Formu", "Genel Bilgiler Sekmesi")
        tab_general_layout = QVBoxLayout(tab_general)
        tab_general_layout.setSpacing(12)

        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Durum:"))
        self.chk_is_active = QCheckBox("Aktif")
        self.chk_is_active.setChecked(True)
        status_layout.addWidget(self.chk_is_active)
        status_layout.addStretch()
        tab_general_layout.addLayout(status_layout)

        form_gen = QFormLayout()
        form_gen.setSpacing(10)

        self.txt_sku = QLineEdit()
        self.txt_sku.setPlaceholderText("STK00001 (Otomatik veya manuel stok kodu)")
        self.txt_barcode = QLineEdit()
        self.txt_barcode.setPlaceholderText("8690000000000")
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Ürün veya Hizmet Adı *")

        self.cmb_unit = QComboBox()
        self.cmb_unit.addItems(UNITS)

        self.cmb_category = QComboBox()
        self.cmb_category.addItems(CATEGORIES)

        self.txt_brand = QLineEdit()
        self.txt_brand.setPlaceholderText("Marka / Üretici")

        form_gen.addRow("Stok Kodu *:", self.txt_sku)
        form_gen.addRow("Barkod:", self.txt_barcode)
        form_gen.addRow("Ürün Adı *:", self.txt_name)
        form_gen.addRow("Birim:", self.cmb_unit)
        form_gen.addRow("Kategori:", self.cmb_category)
        form_gen.addRow("Marka:", self.txt_brand)

        tab_general_layout.addLayout(form_gen)
        tab_general_layout.addStretch()
        self.tabs.addTab(tab_general, "Genel Bilgiler")

        # ─── 2. Sekme: Fiyat & KDV ───
        tab_price = QWidget()
        register_layout_hint(tab_price, "Stok Kart Formu", "Fiyat & KDV Sekmesi")
        tab_price_layout = QVBoxLayout(tab_price)
        form_price = QFormLayout()
        form_price.setSpacing(10)

        self.txt_purchase_price = QLineEdit("0.00")
        self.txt_sale_price = QLineEdit("0.00")
        self.cmb_vat_rate = QComboBox()
        self.cmb_vat_rate.addItems(VAT_RATES)
        self.txt_min_price = QLineEdit("0.00")

        self.lbl_margin = QLabel("Marj: % 0.00")
        self.lbl_margin.setStyleSheet("font-weight: bold; color: #2563eb;")

        self.txt_purchase_price.textChanged.connect(self.calculate_margin)
        self.txt_sale_price.textChanged.connect(self.calculate_margin)

        form_price.addRow("Alış Fiyatı (₺):", self.txt_purchase_price)
        form_price.addRow("Satış Fiyatı (₺):", self.txt_sale_price)
        form_price.addRow("KDV Oranı:", self.cmb_vat_rate)
        form_price.addRow("Min. Satış Fiyatı (₺):", self.txt_min_price)
        form_price.addRow("Kâr Marjı:", self.lbl_margin)

        tab_price_layout.addLayout(form_price)
        tab_price_layout.addStretch()
        self.tabs.addTab(tab_price, "Fiyat & KDV")

        # ─── 3. Sekme: Stok & Depo ───
        tab_stock = QWidget()
        register_layout_hint(tab_stock, "Stok Kart Formu", "Stok & Depo Sekmesi")
        tab_stock_layout = QVBoxLayout(tab_stock)
        form_stock = QFormLayout()
        form_stock.setSpacing(10)

        self.txt_stock_qty = QLineEdit("0.00")
        self.txt_min_stock = QLineEdit("0.00")
        self.txt_max_stock = QLineEdit("0.00")
        self.cmb_depo = QComboBox()
        self.cmb_depo.addItems(DEPOS)

        self.lbl_stock_warning = QLabel("")
        self.lbl_stock_warning.setStyleSheet("font-weight: bold; color: #dc2626;")

        self.txt_stock_qty.textChanged.connect(self.check_stock_warning)
        self.txt_min_stock.textChanged.connect(self.check_stock_warning)

        form_stock.addRow("Mevcut Stok:", self.txt_stock_qty)
        form_stock.addRow("Kritik Stok (Min):", self.txt_min_stock)
        form_stock.addRow("Maksimum Stok:", self.txt_max_stock)
        form_stock.addRow("Varsayılan Depo:", self.cmb_depo)
        form_stock.addRow("Stok Durumu:", self.lbl_stock_warning)

        tab_stock_layout.addLayout(form_stock)
        tab_stock_layout.addStretch()
        self.tabs.addTab(tab_stock, "Stok & Depo")

        # ─── 4. Sekme: Ek Bilgiler ───
        tab_extra = QWidget()
        register_layout_hint(tab_extra, "Stok Kart Formu", "Ek Bilgiler Sekmesi")
        tab_extra_layout = QVBoxLayout(tab_extra)
        form_extra = QFormLayout()
        form_extra.setSpacing(10)

        self.txt_custom_code = QLineEdit()
        self.txt_custom_code.setPlaceholderText("Özel kod veya entegrasyon kodu")
        self.txt_description = QTextEdit()
        self.txt_description.setPlaceholderText("Ürün açıklaması ve detaylı notlar...")
        self.txt_description.setMaximumHeight(140)

        form_extra.addRow("Özel Kod:", self.txt_custom_code)
        form_extra.addRow("Açıklama / Notlar:", self.txt_description)

        tab_extra_layout.addLayout(form_extra)
        tab_extra_layout.addStretch()
        self.tabs.addTab(tab_extra, "Ek Bilgiler")

        left_layout.addWidget(self.tabs)

        # Girdilerin CSS stilleri
        input_style = """
            QLineEdit, QComboBox, QTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                color: #0f172a;
            }
            QLineEdit:focus, QTextEdit:focus { border-color: #3b82f6; }
        """
        for tab in [tab_general, tab_price, tab_stock, tab_extra]:
            for widget in tab.findChildren((QLineEdit, QComboBox, QTextEdit)):
                widget.setStyleSheet(input_style)

        # ─── Alt Buton Grubu ───
        btn_group_layout = QHBoxLayout()
        btn_group_layout.setSpacing(8)

        self.btn_save = QPushButton("💾 Kaydet (F2)")
        self.btn_save.setShortcut("F2")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 18px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_save.clicked.connect(lambda: self.save_product(and_new=False))

        self.btn_save_new = QPushButton("➕ Kaydet & Yeni")
        self.btn_save_new.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 18px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.btn_save_new.clicked.connect(lambda: self.save_product(and_new=True))

        self.btn_cancel = QPushButton("🚪 Vazgeç (Esc)")
        self.btn_cancel.setShortcut("Esc")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 18px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        btn_group_layout.addWidget(self.btn_save)
        btn_group_layout.addWidget(self.btn_save_new)
        btn_group_layout.addWidget(self.btn_cancel)
        btn_group_layout.addStretch()

        left_layout.addLayout(btn_group_layout)
        main_layout.addLayout(left_layout, 7)

        # ─── SAĞ TARAF: Ürün Görseli Paneli ───
        right_panel = QFrame()
        right_panel.setObjectName("RightPanel")
        register_layout_hint(right_panel, "Stok Kart Formu", "Sağ Görsel Paneli")
        right_panel.setStyleSheet("""
            QFrame#RightPanel {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(12)

        pic_title = QLabel("Ürün Görseli")
        pic_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        pic_title.setStyleSheet("color: #475569;")
        pic_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(pic_title)

        self.photo_label = QLabel()
        self.photo_label.setFixedSize(160, 210)
        self.photo_label.setStyleSheet(
            "background-color: #cbd5e1; border: 1px solid #94a3b8; border-radius: 6px;",
        )
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_default_avatar()
        right_layout.addWidget(self.photo_label)

        self.btn_change_photo = QPushButton("📷 Resmi Değiştir")
        self.btn_change_photo.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.btn_change_photo.clicked.connect(self.change_photo)
        right_layout.addWidget(self.btn_change_photo)

        self.btn_remove_photo = QPushButton("🗑️ Resmi Sil")
        self.btn_remove_photo.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)
        self.btn_remove_photo.clicked.connect(self.remove_photo)
        right_layout.addWidget(self.btn_remove_photo)

        right_layout.addStretch()
        main_layout.addWidget(right_panel, 3)

    def set_default_avatar(self):
        self.photo_label.setText("📦 Resim Yok")
        self.photo_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.photo_label.setStyleSheet(
            "background-color: #e2e8f0; color: #64748b; "
            "border: 1px dashed #cbd5e1; border-radius: 6px;",
        )

    def change_photo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Ürün Görseli Seç"),
            "",
            "Görsel Dosyaları (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if file_path:
            self.photo_path = file_path
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.photo_label.setPixmap(
                    pixmap.scaled(
                        self.photo_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ),
                )
                self.photo_label.setStyleSheet(
                    "border: 1px solid #94a3b8; border-radius: 6px;",
                )

    def remove_photo(self):
        self.photo_path = None
        self.set_default_avatar()

    def calculate_margin(self):
        try:
            p_text = self.txt_purchase_price.text().replace(",", ".").strip()
            s_text = self.txt_sale_price.text().replace(",", ".").strip()
            purchase = float(p_text) if p_text else 0.0
            sale = float(s_text) if s_text else 0.0

            if purchase > 0:
                margin = ((sale - purchase) / purchase) * 100
                self.lbl_margin.setText(f"Marj: % {margin:,.2f}")
                if margin >= 0:
                    self.lbl_margin.setStyleSheet("font-weight: bold; color: #16a34a;")
                else:
                    self.lbl_margin.setStyleSheet("font-weight: bold; color: #dc2626;")
            else:
                self.lbl_margin.setText("Marj: % 0.00")
                self.lbl_margin.setStyleSheet("font-weight: bold; color: #2563eb;")
        except Exception:
            self.lbl_margin.setText("Marj: % 0.00")

    def check_stock_warning(self):
        try:
            qty_text = self.txt_stock_qty.text().replace(",", ".").strip()
            min_text = self.txt_min_stock.text().replace(",", ".").strip()
            stock = float(qty_text) if qty_text else 0.0
            min_stock = float(min_text) if min_text else 0.0

            if min_stock > 0 and stock <= min_stock:
                self.lbl_stock_warning.setText(
                    f"⚠️ KRİTİK SEVİYEDE! (Stok <= {min_stock:,.2f})",
                )
                self.lbl_stock_warning.setStyleSheet(
                    "font-weight: bold; color: #dc2626;",
                )
            else:
                self.lbl_stock_warning.setText("✅ Yeterli")
                self.lbl_stock_warning.setStyleSheet(
                    "font-weight: bold; color: #16a34a;",
                )
        except Exception:
            self.lbl_stock_warning.setText("")

    def load_product(self):
        """Mevcut stok kartı verilerini form alanlarına yükler."""
        if not self.db or not self.product_id:
            return

        try:
            product = self.db.get(Product, self.product_id)
            if not product:
                QMessageBox.warning(self, "Uyarı", "Stok kartı bulunamadı.")
                return

            self.txt_sku.setText(product.sku or "")
            self.txt_barcode.setText(getattr(product, "barcode", "") or "")
            self.txt_name.setText(product.name or "")

            unit = getattr(product, "unit", "Adet") or "Adet"
            idx_unit = self.cmb_unit.findText(unit)
            if idx_unit >= 0:
                self.cmb_unit.setCurrentIndex(idx_unit)
            else:
                self.cmb_unit.setCurrentText(unit)

            cat = getattr(product, "category", "Malzeme") or "Malzeme"
            idx_cat = self.cmb_category.findText(cat)
            if idx_cat >= 0:
                self.cmb_category.setCurrentIndex(idx_cat)
            else:
                self.cmb_category.setCurrentText(cat)

            self.txt_brand.setText(getattr(product, "brand", "") or "")
            self.chk_is_active.setChecked(bool(getattr(product, "is_active", True)))

            # Fiyatlar
            purchase_price = float(getattr(product, "purchase_price", 0.0) or 0.0)
            sale_price = float(product.sale_price or 0.0)
            self.txt_purchase_price.setText(f"{purchase_price:.2f}")
            self.txt_sale_price.setText(f"{sale_price:.2f}")

            vat = int(getattr(product, "vat_rate", 20) or 20)
            vat_str = f"% {vat}"
            idx_vat = self.cmb_vat_rate.findText(vat_str)
            if idx_vat >= 0:
                self.cmb_vat_rate.setCurrentIndex(idx_vat)

            # Stok
            stock_qty = float(getattr(product, "stock_quantity", 0.0) or 0.0)
            min_stock = float(getattr(product, "min_stock", 0.0) or 0.0)
            self.txt_stock_qty.setText(f"{stock_qty:.2f}")
            self.txt_min_stock.setText(f"{min_stock:.2f}")

            # Ek
            self.txt_custom_code.setText(getattr(product, "custom_code", "") or "")
            self.txt_description.setText(getattr(product, "description", "") or "")

            # Görsel
            image_path = getattr(product, "image_path", None)
            if image_path and os.path.exists(image_path):
                self.photo_path = image_path
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    self.photo_label.setPixmap(
                        pixmap.scaled(
                            self.photo_label.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        ),
                    )
                    self.photo_label.setStyleSheet(
                        "border: 1px solid #94a3b8; border-radius: 6px;",
                    )

            self.calculate_margin()
            self.check_stock_warning()

        except Exception as e:
            logger.error(f"Stok kartı yüklenemedi: {e}")
            QMessageBox.critical(self, "Hata", f"Stok kartı yüklenemedi:\n{e}")

    def save_product(self, and_new: bool = False):
        """Stok kartını kaydet (yeni veya güncelle)."""
        if not self.db:
            QMessageBox.warning(self, "Uyarı", "Veritabanı bağlantısı yok.")
            return

        sku = self.txt_sku.text().strip()
        name = self.txt_name.text().strip()

        if not sku:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir Stok Kodu girin.")
            self.tabs.setCurrentIndex(0)
            self.txt_sku.setFocus()
            return

        if not name:
            QMessageBox.warning(self, "Uyarı", "Lütfen Ürün Adı girin.")
            self.tabs.setCurrentIndex(0)
            self.txt_name.setFocus()
            return

        try:
            if self.product_id:
                product = self.db.get(Product, self.product_id)
                if not product:
                    QMessageBox.warning(self, "Uyarı", "Güncellenecek ürün bulunamadı.")
                    return
            else:
                product = Product()
                product.company_id = self.company_id
                self.db.add(product)

            # Temel alanlar
            product.sku = sku
            product.barcode = self.txt_barcode.text().strip()
            product.name = name
            product.unit = self.cmb_unit.currentText()
            product.category = self.cmb_category.currentText()
            product.brand = self.txt_brand.text().strip()
            product.is_active = self.chk_is_active.isChecked()

            # Fiyatlar
            p_price_str = self.txt_purchase_price.text().replace(",", ".").strip()
            s_price_str = self.txt_sale_price.text().replace(",", ".").strip()
            product.purchase_price = float(p_price_str) if p_price_str else 0.0
            product.sale_price = float(s_price_str) if s_price_str else 0.0

            vat_str = (
                self.cmb_vat_rate.currentText().replace("%", "").strip() or "20"
            )
            product.vat_rate = int(vat_str)

            # Stok
            stock_str = self.txt_stock_qty.text().replace(",", ".").strip()
            min_stock_str = self.txt_min_stock.text().replace(",", ".").strip()
            product.stock_quantity = float(stock_str) if stock_str else 0.0
            product.min_stock = float(min_stock_str) if min_stock_str else 0.0

            # Ek alanlar
            product.custom_code = self.txt_custom_code.text().strip()
            product.description = self.txt_description.toPlainText().strip()

            if self.photo_path:
                product.image_path = self.photo_path

            self.db.commit()

            if and_new:
                # Yeni kayıt için formu sıfırla
                self.product_id = None
                self.setWindowTitle(f"📦 {self.tr('Yeni Stok Kartı')}")
                self.txt_sku.clear()
                self.txt_barcode.clear()
                self.txt_name.clear()
                self.txt_brand.clear()
                self.txt_purchase_price.setText("0.00")
                self.txt_sale_price.setText("0.00")
                self.txt_min_price.setText("0.00")
                self.txt_stock_qty.setText("0.00")
                self.txt_min_stock.setText("0.00")
                self.txt_max_stock.setText("0.00")
                self.txt_custom_code.clear()
                self.txt_description.clear()
                self.remove_photo()
                self.calculate_margin()
                self.check_stock_warning()
                self.tabs.setCurrentIndex(0)
                self.txt_sku.setFocus()
            else:
                self.accept()

        except Exception as e:
            self.db.rollback()
            logger.error(f"Stok kartı kaydedilirken hata: {e}")
            QMessageBox.critical(self, "Hata", f"Kayıt başarısız:\n{e}")
