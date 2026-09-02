"""Standardized Full-Screen Document Edit/Create Engine (Teklif, Sipariş, Fatura, İrsaliye)."""

import logging
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QDate, QTime, Qt
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import Customer, Product
from src.desktop.services.quotation_service import QuotationService

logger = logging.getLogger(__name__)


class QuotationEditDialog(QDialog):
    """Standardized Full-Screen Document Form (Teklif, Sipariş, Fatura, İrsaliye)."""

    def __init__(self, db_session, quotation_id: int | None = None, document_kind: str = "Quotation", parent=None):
        super().__init__(parent)
        self.db = db_session
        self.quotation_id = quotation_id
        self.document_kind = document_kind  # Quotation, Order, Invoice, DeliveryNote
        self.service = QuotationService(self.db)

        # Window Properties: Full Screen / Maximized
        title_prefix = "Teklif" if document_kind == "Quotation" else "Sipariş"
        self.setWindowTitle(f"{title_prefix} Formu - TOYA ERP Standart Ekranı" if not quotation_id else f"{title_prefix} Düzenle - TOYA ERP Standart Ekranı")
        self.setMinimumSize(1100, 700)
        self.showMaximized()

        self.init_ui()
        self.load_reference_data()

        if quotation_id:
            self.load_quotation_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # ----------------------------------------------------
        # 0. ÜST BİLGİ BARI (Firma, Türü: Alınan/Verilen, Üst İşlem Türü...)
        # ----------------------------------------------------
        top_bar = QFrame()
        top_bar.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 2px;")
        top_bar_lyt = QHBoxLayout(top_bar)
        top_bar_lyt.setContentsMargins(6, 4, 6, 4)
        top_bar_lyt.setSpacing(12)

        lbl_firma = QLabel("Firma:")
        lbl_firma.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.cmb_top_firma = QComboBox()
        self.cmb_top_firma.addItems(["GENEL", "MERKEZ"])

        lbl_turu = QLabel("Türü:")
        lbl_turu.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px;")
        self.cmb_top_turu = QComboBox()

        if self.document_kind == "Quotation":
            self.cmb_top_turu.addItems(["TEKLİF: (1) VERİLEN", "TEKLİF: (2) ALINAN"])
        elif self.document_kind == "Order":
            self.cmb_top_turu.addItems(["SİPARİŞ: (1) ALINAN", "SİPARİŞ: (2) VERİLEN"])
        elif self.document_kind == "Invoice":
            self.cmb_top_turu.addItems(["FATURA: (1) SATIŞ", "FATURA: (2) SATIN ALMA"])
        else:
            self.cmb_top_turu.addItems(["İRSALİYE: (1) SATIŞ", "İRSALİYE: (2) SATIN ALMA"])

        lbl_ust = QLabel("Üst İşlem Türü:")
        lbl_ust.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.cmb_top_ust = QComboBox()
        self.cmb_top_ust.addItems(["GR", "ST", "SR"])

        lbl_client = QLabel("İstemci:")
        lbl_client.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.txt_top_client = QLineEdit("Masaüstü İstemci")
        self.txt_top_client.setFixedWidth(110)

        lbl_fgrp = QLabel("F. Grubu:")
        lbl_fgrp.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.txt_top_fgrp = QLineEdit("01")
        self.txt_top_fgrp.setFixedWidth(40)

        top_bar_lyt.addWidget(lbl_firma)
        top_bar_lyt.addWidget(self.cmb_top_firma)
        top_bar_lyt.addWidget(lbl_turu)
        top_bar_lyt.addWidget(self.cmb_top_turu, 1)
        top_bar_lyt.addWidget(lbl_ust)
        top_bar_lyt.addWidget(self.cmb_top_ust)
        top_bar_lyt.addWidget(lbl_client)
        top_bar_lyt.addWidget(self.txt_top_client)
        top_bar_lyt.addWidget(lbl_fgrp)
        top_bar_lyt.addWidget(self.txt_top_fgrp)

        main_layout.addWidget(top_bar)

        # ----------------------------------------------------
        # 1. ÜST TAB ÇUBUĞU (1 Genel, 2 Detay, 3 Diğer...)
        # ----------------------------------------------------
        self.top_tabs = QTabWidget()
        self.top_tabs.setStyleSheet("""
            QTabBar::tab {
                background: #e2e8f0; color: #334155; font-weight: bold; font-size: 11px;
                padding: 6px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px;
            }
            QTabBar::tab:selected { background: #ffffff; color: #1e3a8a; border-bottom: 2px solid #2563eb; }
        """)

        tab_genel = QWidget()
        tab_genel_layout = QVBoxLayout(tab_genel)
        tab_genel_layout.setContentsMargins(4, 4, 4, 4)
        tab_genel_layout.setSpacing(6)

        # FİŞ BİLGİLERİ VE CARİ HESAP BİLGİLERİ PANELİ (SPLITTER)
        header_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol Kısım: Fiş Bilgileri
        fis_frame = QFrame()
        fis_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;")
        fis_layout = QFormLayout(fis_frame)
        fis_layout.setContentsMargins(8, 8, 8, 8)
        fis_layout.setSpacing(6)

        lbl_fis_title = QLabel("Fiş Bilgileri")
        lbl_fis_title.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 11px;")
        fis_layout.addRow(lbl_fis_title)

        self.cmb_sube = QComboBox()
        self.cmb_sube.addItems(["MERKEZ ŞUBE", "İSTANBUL ŞUBE"])

        self.cmb_depo = QComboBox()
        self.cmb_depo.addItems(["MERKEZ DEPO", "YEDEK DEPO"])

        prefix_code = "TEK" if self.document_kind == "Quotation" else "SIP"
        self.txt_fis_no = QLineEdit(f"{prefix_code}-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        self.txt_belge_no = QLineEdit()

        date_box = QHBoxLayout()
        self.date_tarih = QDateEdit(QDate.currentDate())
        self.date_tarih.setCalendarPopup(True)
        self.txt_saat = QLineEdit(QTime.currentTime().toString("HH:mm:ss"))
        date_box.addWidget(self.date_tarih)
        date_box.addWidget(self.txt_saat)

        self.cmb_onay = QComboBox()
        self.cmb_onay.addItems(["Teklif Durumunda", "Onaylandı", "Reddedildi"])

        self.date_son_tarih = QDateEdit(QDate.currentDate().addDays(15))
        self.date_son_tarih.setCalendarPopup(True)

        doviz_box = QHBoxLayout()
        self.cmb_doviz = QComboBox()
        self.cmb_doviz.addItems(["TL", "USD", "EUR"])
        self.txt_kur = QLineEdit("1,0000")
        doviz_box.addWidget(self.cmb_doviz)
        doviz_box.addWidget(self.txt_kur)

        fis_layout.addRow("Şube:", self.cmb_sube)
        fis_layout.addRow("Depo:", self.cmb_depo)
        fis_layout.addRow("Fiş No:", self.txt_fis_no)
        fis_layout.addRow("Belge No:", self.txt_belge_no)
        fis_layout.addRow("Tarih / Saat:", date_box)
        fis_layout.addRow("Onay:", self.cmb_onay)
        fis_layout.addRow("Son Tarih:", self.date_son_tarih)
        fis_layout.addRow("Döviz / Kur:", doviz_box)

        # Sağ Kısım: Cari Hesap Bilgileri
        cari_frame = QFrame()
        cari_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;")
        cari_layout = QFormLayout(cari_frame)
        cari_layout.setContentsMargins(8, 8, 8, 8)
        cari_layout.setSpacing(6)

        lbl_cari_title = QLabel("Cari Hesap Bilgileri")
        lbl_cari_title.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 11px;")
        cari_layout.addRow(lbl_cari_title)

        hk_box = QHBoxLayout()
        self.txt_hesap_kodu = QLineEdit()
        self.txt_hesap_kodu.setPlaceholderText("Hesap Kodu (Serbest veya Seçin)")
        btn_search_hk = QPushButton("🔍")
        btn_search_hk.setFixedWidth(28)
        btn_search_hk.clicked.connect(self.select_customer_dialog)
        hk_box.addWidget(self.txt_hesap_kodu)
        hk_box.addWidget(btn_search_hk)

        unv_box = QHBoxLayout()
        self.txt_unvan = QLineEdit()
        self.txt_unvan.setPlaceholderText("Unvanı (Serbest Giriş Yapılabilir)")
        btn_search_unv = QPushButton("🔍")
        btn_search_unv.setFixedWidth(28)
        btn_search_unv.clicked.connect(self.select_customer_dialog)
        btn_card_icon = QPushButton("💳")
        btn_card_icon.setFixedWidth(28)
        btn_card_icon.setToolTip("Cari Karta Dönüştür")
        btn_card_icon.clicked.connect(self.convert_customer_to_card)

        unv_box.addWidget(self.txt_unvan)
        unv_box.addWidget(btn_search_unv)
        unv_box.addWidget(btn_card_icon)

        self.txt_sevk_adresi = QLineEdit()
        self.txt_odeme_plani = QLineEdit("30 Gün Vadeli")
        self.txt_yetkili = QLineEdit()

        cari_layout.addRow("Hesap Kodu:", hk_box)
        cari_layout.addRow("Unvanı:", unv_box)
        cari_layout.addRow("Sevk Adresi:", self.txt_sevk_adresi)
        cari_layout.addRow("Ödeme Planı:", self.txt_odeme_plani)
        cari_layout.addRow("Yetkili:", self.txt_yetkili)

        header_splitter.addWidget(fis_frame)
        header_splitter.addWidget(cari_frame)
        header_splitter.setSizes([500, 500])

        tab_genel_layout.addWidget(header_splitter)

        self.top_tabs.addTab(tab_genel, "1 Genel")
        self.top_tabs.addTab(QWidget(), "2 Detay")
        self.top_tabs.addTab(QWidget(), "3 Diğer")
        self.top_tabs.addTab(QWidget(), "5 Ek Alanlar")
        self.top_tabs.addTab(QWidget(), "6 Kümülatif Toplamlar")

        main_layout.addWidget(self.top_tabs)

        # ----------------------------------------------------
        # 2. KALEMLER TABLOSU (ÜRÜN YÖNETİMİ STANDART DATAGRID)
        # ----------------------------------------------------
        lbl_kalemler_hdr = QLabel("Kalemler")
        lbl_kalemler_hdr.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px;")
        main_layout.addWidget(lbl_kalemler_hdr)

        self.table_items = QTableWidget(0, 9)
        self.table_items.setHorizontalHeaderLabels([
            "Tür", "Kodu", "Açıklama", "Birim", "Miktar", "Birim Fiyat", "KDV %", "İskonto %", "Tutar (₺)"
        ])
        self.table_items.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_items.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_items.setShowGrid(True)
        self.table_items.setAlternatingRowColors(True)
        self.table_items.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_items.customContextMenuRequested.connect(self.show_items_context_menu)

        # Ürün Yönetimi Datagrid Görsel Stili
        self.table_items.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                gridline-color: #cbd5e1;
                border-radius: 6px;
                font-family: 'Segoe UI';
                font-size: 12px;
                color: #334155;
                alternate-background-color: #f8fafc;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #eff6ff;
                color: #1d4ed8;
                font-weight: 600;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                padding: 6px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                font-weight: bold;
                font-size: 11px;
            }
        """)

        main_layout.addWidget(self.table_items, 1)

        # ----------------------------------------------------
        # 3. ALT TOPLAMLAR VE EYLEM BUTONLARI
        # ----------------------------------------------------
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        left_bottom = QWidget()
        lb_lyt = QVBoxLayout(left_bottom)
        lb_lyt.setContentsMargins(0, 0, 0, 0)
        lb_lyt.setSpacing(4)

        lbl_notes = QLabel("Açıklama / Notlar:")
        lbl_notes.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Belge ile ilgili özel notlar ve şartlar...")
        self.txt_notes.setFixedHeight(70)
        lb_lyt.addWidget(lbl_notes)
        lb_lyt.addWidget(self.txt_notes)

        totals_frame = QFrame()
        totals_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        totals_lyt = QFormLayout(totals_frame)
        totals_lyt.setContentsMargins(8, 8, 8, 8)
        totals_lyt.setSpacing(4)

        self.lbl_subtotal = QLabel("0,00 TL")
        self.lbl_discount = QLabel("0,00 TL")
        self.lbl_vat = QLabel("0,00 TL")
        self.lbl_grand = QLabel("0,00 TL")
        self.lbl_grand.setStyleSheet("font-weight: bold; font-size: 13px; color: #1e3a8a;")

        totals_lyt.addRow("Ara Toplam:", self.lbl_subtotal)
        totals_lyt.addRow("İndirim:", self.lbl_discount)
        totals_lyt.addRow("KDV:", self.lbl_vat)
        totals_lyt.addRow("Genel Toplam:", self.lbl_grand)

        bottom_splitter.addWidget(left_bottom)
        bottom_splitter.addWidget(totals_frame)
        bottom_splitter.setSizes([600, 350])

        main_layout.addWidget(bottom_splitter)

        # Bottom Buttons Bar
        btn_bar = QHBoxLayout()

        btn_save = QPushButton("💾 Kaydet")
        btn_save.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; border-radius: 4px; padding: 6px 16px;")
        btn_save.clicked.connect(self.save_quotation)

        btn_save_new = QPushButton("💾 Kaydet & Yeni")
        btn_save_new.setStyleSheet("background-color: #0d9488; color: white; font-weight: bold; border-radius: 4px; padding: 6px 16px;")
        btn_save_new.clicked.connect(self.save_and_new_quotation)

        btn_cancel = QPushButton("❌ Vazgeç")
        btn_cancel.setStyleSheet("background-color: #64748b; color: white; font-weight: bold; border-radius: 4px; padding: 6px 16px;")
        btn_cancel.clicked.connect(self.reject)

        btn_bar.addStretch()
        btn_bar.addWidget(btn_save)
        btn_bar.addWidget(btn_save_new)
        btn_bar.addWidget(btn_cancel)

        main_layout.addLayout(btn_bar)

        # Otomatik olarak ilk 1 satır ekli gelir
        self.add_blank_item_row()

    def load_reference_data(self):
        self.available_products = []
        if self.db:
            try:
                self.available_products = self.db.scalars(select(Product).where(Product.is_deleted == False)).all()
            except Exception as e:
                logger.error(f"Products loading error: {e}")

    def select_customer_dialog(self):
        if not self.db:
            return
        customers = self.db.scalars(select(Customer).where(Customer.is_deleted == False)).all()
        if customers:
            c = customers[0]
            self.txt_hesap_kodu.setText(c.customer_code or f"CAR-{c.id}")
            self.txt_unvan.setText(c.fullname)

    def add_blank_item_row(self, insert_index: int | None = None):
        row = self.table_items.rowCount() if insert_index is None else insert_index
        self.table_items.insertRow(row)

        cmb_tur = QComboBox()
        cmb_tur.addItems(["Malzeme", "Hizmet", "Serbest"])
        cmb_tur.currentIndexChanged.connect(lambda idx, r=row: self.on_tur_changed(r, cmb_tur.currentText()))

        txt_code = QLineEdit("STK-001")
        txt_name = QLineEdit("Yeni Kalem Açıklaması")
        txt_name.textChanged.connect(self.calculate_totals)

        txt_unit = QLineEdit("Adet")
        txt_qty = QLineEdit("1")
        txt_qty.textChanged.connect(self.calculate_totals)

        txt_price = QLineEdit("0.00")
        txt_price.textChanged.connect(self.calculate_totals)

        txt_vat = QLineEdit("20")
        txt_vat.textChanged.connect(self.calculate_totals)

        txt_disc = QLineEdit("0")
        txt_disc.textChanged.connect(self.calculate_totals)
        txt_disc.returnPressed.connect(self.on_last_cell_enter_pressed)

        lbl_tot = QLabel("0.00 ₺")
        lbl_tot.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.table_items.setCellWidget(row, 0, cmb_tur)
        self.table_items.setCellWidget(row, 1, txt_code)
        self.table_items.setCellWidget(row, 2, txt_name)
        self.table_items.setCellWidget(row, 3, txt_unit)
        self.table_items.setCellWidget(row, 4, txt_qty)
        self.table_items.setCellWidget(row, 5, txt_price)
        self.table_items.setCellWidget(row, 6, txt_vat)
        self.table_items.setCellWidget(row, 7, txt_disc)
        self.table_items.setCellWidget(row, 8, lbl_tot)

        self.calculate_totals()

    def on_tur_changed(self, row: int, tur_name: str):
        txt_code = self.table_items.cellWidget(row, 1)
        txt_name = self.table_items.cellWidget(row, 2)

        if tur_name == "Malzeme" and self.available_products:
            p = self.available_products[0]
            if txt_code:
                txt_code.setText(p.sku)
            if txt_name:
                txt_name.setText(p.name)
        elif tur_name == "Hizmet":
            if txt_code:
                txt_code.setText("HZM-001")
            if txt_name:
                txt_name.setText("Danışmanlık / Hizmet Kalemi")
        else:
            if txt_code:
                txt_code.setPlaceholderText("Serbest Kod")
            if txt_name:
                txt_name.setPlaceholderText("Serbest Açıklama Girin...")

    def on_last_cell_enter_pressed(self):
        self.add_blank_item_row()

    def remove_item_row(self, row: int):
        if self.table_items.rowCount() > 1:
            self.table_items.removeRow(row)
            self.calculate_totals()
        else:
            QMessageBox.warning(self, "Uyarı", "Formda en az 1 satır kalem bulunmalıdır.")

    def show_items_context_menu(self, pos):
        menu = QMenu(self)
        row = self.table_items.currentRow()

        act_add = QAction("📌 Satır Ekle", self)
        act_add.triggered.connect(lambda: self.add_blank_item_row())

        act_insert = QAction("📌 Araya Satır Ekle", self)
        act_insert.triggered.connect(lambda: self.add_blank_item_row(insert_index=max(0, row)))

        act_del = QAction("🗑️ Satır Sil", self)
        act_del.triggered.connect(lambda: self.remove_item_row(max(0, row)))

        menu.addAction(act_add)
        menu.addAction(act_insert)
        menu.addAction(act_del)
        menu.exec(self.table_items.viewport().mapToGlobal(pos))

    def calculate_totals(self):
        if not hasattr(self, "lbl_subtotal"):
            return

        subtotal = 0.0
        vat_total = 0.0
        disc_total = 0.0
        grand_total = 0.0

        for r in range(self.table_items.rowCount()):
            try:
                qty_w = self.table_items.cellWidget(r, 4)
                price_w = self.table_items.cellWidget(r, 5)
                vat_w = self.table_items.cellWidget(r, 6)
                disc_w = self.table_items.cellWidget(r, 7)
                lbl_tot = self.table_items.cellWidget(r, 8)

                qty = float(qty_w.text()) if qty_w and qty_w.text() else 1.0
                price = float(price_w.text()) if price_w and price_w.text() else 0.0
                vat = float(vat_w.text()) if vat_w and vat_w.text() else 20.0
                disc = float(disc_w.text()) if disc_w and disc_w.text() else 0.0

                base_total = qty * price
                disc_amt = base_total * (disc / 100.0)
                taxable = base_total - disc_amt
                vat_amt = taxable * (vat / 100.0)
                line_tot = taxable + vat_amt

                subtotal += base_total
                disc_total += disc_amt
                vat_total += vat_amt
                grand_total += line_tot

                if lbl_tot:
                    lbl_tot.setText(f"{line_tot:,.2f} ₺")
            except Exception:
                pass

        self.lbl_subtotal.setText(f"{subtotal:,.2f} TL")
        self.lbl_discount.setText(f"{disc_total:,.2f} TL")
        self.lbl_vat.setText(f"{vat_total:,.2f} TL")
        self.lbl_grand.setText(f"{grand_total:,.2f} TL")

    def convert_customer_to_card(self):
        cust_name = self.txt_unvan.text().strip()
        if not cust_name:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir Cari Unvanı girin.")
            return

        if not self.db:
            return

        from src.core.models import Customer
        c = Customer(
            fullname=cust_name,
            customer_code=self.txt_hesap_kodu.text().strip() or f"CAR-{datetime.now().strftime('%H%M%S')}",
            marketplace="local",
        )
        self.db.add(c)
        self.db.commit()
        self.db.refresh(c)

        QMessageBox.information(self, "Başarılı", f"'{cust_name}' ismiyle yeni Cari Kart oluşturuldu.")

    def load_quotation_data(self):
        if not self.quotation_id or not self.db:
            return
        q = self.service.get_quotation(self.quotation_id)
        if not q:
            return

        self.txt_fis_no.setText(q.quotation_number)
        self.txt_unvan.setText(q.customer_name_free or (q.customer.fullname if q.customer else ""))
        self.txt_notes.setText(q.notes or "")

        self.table_items.setRowCount(0)
        for item in q.items:
            self.add_blank_item_row()
            r = self.table_items.rowCount() - 1
            if self.table_items.cellWidget(r, 1):
                self.table_items.cellWidget(r, 1).setText(item.product_code_free or "")
            if self.table_items.cellWidget(r, 2):
                self.table_items.cellWidget(r, 2).setText(item.product_name_free)
            if self.table_items.cellWidget(r, 3):
                self.table_items.cellWidget(r, 3).setText(item.unit)
            if self.table_items.cellWidget(r, 4):
                self.table_items.cellWidget(r, 4).setText(str(item.quantity))
            if self.table_items.cellWidget(r, 5):
                self.table_items.cellWidget(r, 5).setText(str(item.unit_price))
            if self.table_items.cellWidget(r, 6):
                self.table_items.cellWidget(r, 6).setText(str(item.vat_rate))
            if self.table_items.cellWidget(r, 7):
                self.table_items.cellWidget(r, 7).setText(str(item.discount_rate))

        self.calculate_totals()

    def save_quotation(self) -> bool:
        unvan = self.txt_unvan.text().strip()
        if not unvan:
            QMessageBox.warning(self, "Uyarı", "Lütfen Cari Unvanı giriniz.")
            return False

        q_data = {
            "quotation_number": self.txt_fis_no.text().strip(),
            "title": f"{self.document_kind} - {unvan}",
            "quotation_type": self.document_kind,
            "customer_name_free": unvan,
            "notes": self.txt_notes.toPlainText().strip(),
        }

        items_data = []
        for r in range(self.table_items.rowCount()):
            code_w = self.table_items.cellWidget(r, 1)
            name_w = self.table_items.cellWidget(r, 2)
            unit_w = self.table_items.cellWidget(r, 3)
            qty_w = self.table_items.cellWidget(r, 4)
            price_w = self.table_items.cellWidget(r, 5)
            vat_w = self.table_items.cellWidget(r, 6)
            disc_w = self.table_items.cellWidget(r, 7)

            items_data.append({
                "product_code_free": code_w.text().strip() if code_w else "",
                "product_name_free": name_w.text().strip() if name_w else "Kalem",
                "unit": unit_w.text().strip() if unit_w else "Adet",
                "quantity": float(qty_w.text()) if qty_w and qty_w.text() else 1.0,
                "unit_price": float(price_w.text()) if price_w and price_w.text() else 0.0,
                "vat_rate": float(vat_w.text()) if vat_w and vat_w.text() else 20.0,
                "discount_rate": float(disc_w.text()) if disc_w and disc_w.text() else 0.0,
            })

        q = self.service.create_quotation(q_data, items_data)
        if q:
            QMessageBox.information(self, "Başarılı", f"Belge '{q.quotation_number}' numarası ile kaydedildi.")
            self.accept()
            return True
        else:
            QMessageBox.critical(self, "Hata", "Belge kaydedilirken bir hata oluştu.")
            return False

    def save_and_new_quotation(self):
        if self.save_quotation():
            prefix_code = "TEK" if self.document_kind == "Quotation" else "SIP"
            self.txt_fis_no.setText(f"{prefix_code}-{datetime.now().strftime('%Y%m%d%H%M%S')}")
            self.txt_unvan.clear()
            self.txt_hesap_kodu.clear()
            self.txt_notes.clear()
            self.table_items.setRowCount(0)
            self.add_blank_item_row()
