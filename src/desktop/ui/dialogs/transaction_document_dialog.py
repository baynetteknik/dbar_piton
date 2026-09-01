"""TOYA ERP - Evrensel Fiş, Fatura, Sipariş ve Teklif Detay Motoru (Master Transaction Document Dialog).

Bu modül; Akınsoft Wolvox, DIA ERP ve Kurumsal ERP'lerin en güçlü yönlerini birleştiren
evrensel evrak yönetim motorudur (Alış, Satış, Toptan, İade, Hizmet Faturaları,
Verilen/Alınan Teklifler, Siparişler ve İrsaliyeler için tek çatı mimaridir).
Mockup 1:1 formatında yeniden yapılandırılmıştır.
"""

import logging
import os
import re
from datetime import datetime

from PyQt6.QtCore import QDate, Qt, QTime, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import Customer, Product
from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.managers.theme_manager import ThemeManager
from src.desktop.reports.teklif_report_service import TeklifReportService
from src.desktop.ui.column_manager import ColumnManagerDialog
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.layout_hint_helper import register_layout_hint

logger = logging.getLogger(__name__)


class NoteEditDialog(QDialog):
    """Fatura Notları & Özel Şartlar için Çok Satırlı Düzenleme Penceresi."""

    def __init__(self, note1: str = "", note2: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📝 Fatura Notları & Özel Şartlar Düzenle")
        self.setMinimumSize(500, 380)
        self.setStyleSheet("background-color: #f8fafc; font-family: 'Segoe UI';")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        lbl1 = QLabel("Not 1 / Banka IBAN Bilgileri:")
        lbl1.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px;")
        self.txt_note1 = QTextEdit(note1)
        self.txt_note1.setPlaceholderText(
            "Örn: Garanti BBVA TR12 0006 2000 0001 2345 6789 01 - TL Hesabı",
        )
        self.txt_note1.setStyleSheet(
            "background: white; border: 1px solid #cbd5e1; border-radius: 4px; "
            "padding: 6px; font-size: 12px;",
        )

        lbl2 = QLabel("Not 2 / Teslimat & Özel Şartlar:")
        lbl2.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px;")
        self.txt_note2 = QTextEdit(note2)
        self.txt_note2.setPlaceholderText(
            "Örn: Ürünler eksiksiz teslim alınmıştır. İhtilaf halinde "
            "Adana Mahkemeleri yetkilidir.",
        )
        self.txt_note2.setStyleSheet(
            "background: white; border: 1px solid #cbd5e1; border-radius: 4px; "
            "padding: 6px; font-size: 12px;",
        )

        layout.addWidget(lbl1)
        layout.addWidget(self.txt_note1)
        layout.addWidget(lbl2)
        layout.addWidget(self.txt_note2)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("💾 Uygula & Kapat")
        btn_ok.setStyleSheet(
            "background-color: #2563eb; color: white; font-weight: bold; "
            "padding: 8px 16px; border-radius: 4px;",
        )
        btn_ok.clicked.connect(self.accept)

        btn_cancel = QPushButton("Vazgeç")
        btn_cancel.setStyleSheet(
            "background-color: #64748b; color: white; padding: 8px 16px; "
            "border-radius: 4px;",
        )
        btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def get_notes(self) -> tuple[str, str]:
        return (
            self.txt_note1.toPlainText().strip(),
            self.txt_note2.toPlainText().strip(),
        )


class CustomerQuickLookupDialog(QDialog):
    """Cari Arama ve Seçim Penceresi."""

    def __init__(self, customers: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🔍 Cari Hesap Seçimi")
        self.setMinimumSize(680, 420)
        self.setStyleSheet("font-family: 'Segoe UI'; background: #f8fafc;")
        self.selected_customer = None
        self.customers = customers

        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(10, 10, 10, 10)
        lyt.setSpacing(6)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Cari Kodu, Ünvan, Vergi No ile filtrele...")
        self.txt_search.setFixedHeight(28)
        self.txt_search.textChanged.connect(self.filter_table)
        lyt.addWidget(self.txt_search)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels([
            "Cari Kodu", "Ünvan", "Vergi Dairesi", "Vergi No", "Bakiye",
        ])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.doubleClicked.connect(self.on_select)
        lyt.addWidget(self.tbl)

        btn_box = QHBoxLayout()
        btn_sel = QPushButton("✅ Seç")
        btn_sel.setStyleSheet(
            "background-color: #2563eb; color: white; font-weight: bold; "
            "padding: 6px 16px; border-radius: 4px;",
        )
        btn_sel.clicked.connect(self.on_select)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(btn_sel)
        btn_box.addWidget(btn_cancel)
        lyt.addLayout(btn_box)

        self.populate_table(self.customers)

    def populate_table(self, data: list[dict]) -> None:
        self.tbl.setRowCount(0)
        for r, c in enumerate(data):
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(c.get("code", "")))
            self.tbl.setItem(r, 1, QTableWidgetItem(c.get("name", "")))
            self.tbl.setItem(r, 2, QTableWidgetItem(c.get("tax_office", "")))
            self.tbl.setItem(r, 3, QTableWidgetItem(c.get("tax_no", "")))
            self.tbl.setItem(r, 4, QTableWidgetItem(c.get("balance", "")))

    def filter_table(self, text: str) -> None:
        q = text.lower()
        filtered = [
            c for c in self.customers
            if q in c.get("code", "").lower()
            or q in c.get("name", "").lower()
            or q in c.get("tax_no", "").lower()
        ]
        self.populate_table(filtered)

    def on_select(self) -> None:
        row = self.tbl.currentRow()
        if row >= 0:
            code = self.tbl.item(row, 0).text()
            for c in self.customers:
                if c.get("code") == code:
                    self.selected_customer = c
                    break
            self.accept()


class StockQuickLookupDialog(QDialog):
    """Stok ve Hizmet Arama ve Seçim Penceresi."""

    def __init__(self, products: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🔍 Stok & Hizmet Kartı Seçimi")
        self.setMinimumSize(720, 440)
        self.setStyleSheet("font-family: 'Segoe UI'; background: #f8fafc;")
        self.selected_product = None
        self.products = products

        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(10, 10, 10, 10)
        lyt.setSpacing(6)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Stok Kodu, Ürün Adı, Barkod ile filtrele...")
        self.txt_search.setFixedHeight(28)
        self.txt_search.textChanged.connect(self.filter_table)
        lyt.addWidget(self.txt_search)

        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels([
            "Stok Kodu", "Barkod", "Açıklama", "Birim", "Fiyat", "KDV %",
        ])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch,
        )
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl.doubleClicked.connect(self.on_select)
        lyt.addWidget(self.tbl)

        btn_box = QHBoxLayout()
        btn_sel = QPushButton("✅ Seç")
        btn_sel.setStyleSheet(
            "background-color: #2563eb; color: white; font-weight: bold; "
            "padding: 6px 16px; border-radius: 4px;",
        )
        btn_sel.clicked.connect(self.on_select)
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addStretch()
        btn_box.addWidget(btn_sel)
        btn_box.addWidget(btn_cancel)
        lyt.addLayout(btn_box)

        self.populate_table(self.products)

    def populate_table(self, data: list[dict]) -> None:
        self.tbl.setRowCount(0)
        for r, p in enumerate(data):
            self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(p.get("code", "")))
            self.tbl.setItem(r, 1, QTableWidgetItem(p.get("barcode", "")))
            self.tbl.setItem(r, 2, QTableWidgetItem(p.get("name", "")))
            self.tbl.setItem(r, 3, QTableWidgetItem(p.get("unit", "Adet")))
            self.tbl.setItem(r, 4, QTableWidgetItem(f"{p.get('price', 0):.2f} ₺"))
            self.tbl.setItem(r, 5, QTableWidgetItem(f"% {p.get('vat', 20)}"))

    def filter_table(self, text: str) -> None:
        q = text.lower()
        filtered = [
            p for p in self.products
            if q in p.get("code", "").lower()
            or q in p.get("name", "").lower()
            or q in p.get("barcode", "").lower()
        ]
        self.populate_table(filtered)

    def on_select(self) -> None:
        row = self.tbl.currentRow()
        if row >= 0:
            code = self.tbl.item(row, 0).text()
            for p in self.products:
                if p.get("code") == code:
                    self.selected_product = p
                    break
            self.accept()


class CustomerBalanceDialog(QDialog):
    """Cari Detaylı Bakiye ve Ekstre Özeti Penceresi."""

    def __init__(self, customer_name: str, balance: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("💳 Cari Hesap Bakiye & Risk Özeti")
        self.setMinimumSize(420, 260)
        self.setStyleSheet("font-family: 'Segoe UI'; background: #f8fafc;")

        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(16, 16, 16, 16)
        lyt.setSpacing(10)

        lbl_name = QLabel(f"<b>Cari:</b> {customer_name}")
        lbl_name.setStyleSheet("font-size: 13px; color: #1e3a8a;")
        lyt.addWidget(lbl_name)

        frame = QFrame()
        frame.setStyleSheet(
            "background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px;",
        )
        flyt = QVBoxLayout(frame)
        flyt.setSpacing(6)

        lbl_b = QLabel(f"Güncel Bakiye: <b style='color:#dc2626; font-size:14px;'>{balance}</b>")
        lbl_r = QLabel("Risk Limiti: <b>100.000,00 ₺</b>")
        lbl_k = QLabel("Kalan Kredi: <b>54.750,00 ₺</b>")
        lbl_v = QLabel("Ortalama Vade: <b>32 Gün</b>")

        flyt.addWidget(lbl_b)
        flyt.addWidget(lbl_r)
        flyt.addWidget(lbl_k)
        flyt.addWidget(lbl_v)
        lyt.addWidget(frame)

        btn_ok = QPushButton("Kapat")
        btn_ok.setStyleSheet("background: #2563eb; color: white; padding: 6px 16px; border-radius: 4px;")
        btn_ok.clicked.connect(self.accept)
        lyt.addWidget(btn_ok, alignment=Qt.AlignmentFlag.AlignRight)


class TransactionDocumentDialog(QDialog):
    """Evrensel Fiş & Evrak Detay Penceresi (Mockup 1:1 Tasarımı)."""

    document_saved = pyqtSignal(dict)

    DOCUMENT_TYPES = [
        "FATURA: (1) YURT İÇİ SATIŞ FATURASI",
        "FATURA: (2) TOPTAN SATIŞ FATURASI",
        "FATURA: (3) SATIN ALMA / ALIŞ FATURASI",
        "FATURA: (4) SATIŞ İADE FATURASI",
        "FATURA: (5) HİZMET FATURASI",
        "TEKLİF: (1) VERİLEN SATIŞ TEKLİFİ",
        "TEKLİF: (2) ALINAN TEKLİF",
        "SİPARİŞ: (1) ALINAN MÜŞTERİ SİPARİŞİ",
        "SİPARİŞ: (2) VERİLEN TEDARİKÇİ SİPARİŞİ",
        "İRSALİYE: (1) SEVK / SATIŞ İRSALİYESİ",
        "İRSALİYE: (2) ALIŞ İRSALİYESİ",
    ]

    EFATURA_SCENARIOS = [
        "--- (Resmi Olmayan / Taslak Belge)",
        "E-Fatura: TEMEL FATURA",
        "E-Fatura: TİCARİ FATURA",
        "E-Fatura: KAMU",
        "E-Fatura: İHRACAT (GÇB)",
        "E-Arşiv: STANDART (GİB 5.000 / 30.000 ₺)",
        "E-Arşiv: İNTERNET SATIŞI",
        "E-İrsaliye: TEMEL",
    ]

    COLUMN_NAMES = [
        "🗑️",
        "Türü",
        "Barkod",
        "Stok Kodu",
        "Açıklama / Ürün Adı",
        "Satır Notu 2",
        "Miktar",
        "Birim",
        "B.Fiyat",
        "Döviz",
        "İsk 1 %",
        "İsk 1 Tutar",
        "İsk 2 %",
        "İsk 2 Tutar",
        "İsk 3 %",
        "İsk 3 Tutar",
        "KDV %",
        "Tevkifat",
        "Tutar",
    ]

    ALT_ISKONTO_COLUMNS = [
        "🗑️",
        "Tür",
        "Türü",
        "Değer",
        "Döviz",
        "Kur",
        "KDV %",
        "Tutar",
        "Not",
        "Maliyet Etkilesin",
        "İlk Değer",
        "Formül",
    ]

    ISKONTO_TURLERI = [
        "Toplamdan % Düş",
        "Toplamdan Düş",
        "Toplamı Eşitle",
        "G.Toplamdan % Düş",
        "G.Toplamdan Düş",
        "G.Toplamı Eşitle",
    ]

    ODEME_PLANLARI = [
        {"kod": "30GVD", "aciklama": "30 GÜN VADE", "gun": 30, "tip": "Açık Hesap"},
        {"kod": "40GVD", "aciklama": "40 GÜNLÜK VADE", "gun": 40, "tip": "Açık Hesap"},
        {"kod": "45GVD", "aciklama": "45 GÜNLÜK VADE", "gun": 45, "tip": "Açık Hesap"},
        {"kod": "60GVD", "aciklama": "60 GÜNLÜK VADE", "gun": 60, "tip": "Açık Hesap"},
        {"kod": "60GUNKK", "aciklama": "60 GÜN KREDİ KARTI", "gun": 60, "tip": "Kredi Kartı"},
        {"kod": "AH", "aciklama": "AÇIK HESAP", "gun": 0, "tip": "Açık Hesap"},
        {"kod": "NAKIT", "aciklama": "NAKİT", "gun": 0, "tip": "Nakit"},
        {"kod": "CF3TAK", "aciklama": "CARDFINANS 3 TAKSİT", "gun": 90, "tip": "Taksit"},
    ]

    SHORTCUTS = {
        "satir_ekle": "Alt+Return",
        "satir_sil": "Ctrl+Delete",
        "yukari_tas": "Alt+Up",
        "asagi_tas": "Alt+Down",
        "stok_ara": "F10",
    }

    SAMPLE_CUSTOMERS = [
        {
            "code": "M210000194",
            "name": "TATU HIRDAVAT İÇ VE DIŞ TİC.LTD.ŞTİ",
            "tax_office": "Seyhan V.D.",
            "tax_no": "1234567896",
            "address": "Mersinli Mah. 2826 Sk. No:14/101 Adana",
            "balance": "45.250,00 ₺ (Borçlu)",
            "terms": 30,
        },
        {
            "code": "M210000195",
            "name": "DENEME BİLİŞİM TEKNOLOJİLERİ A.Ş.",
            "tax_office": "Kadıköy V.D.",
            "tax_no": "9876543210",
            "address": "Bağdat Cad. No:44 İstanbul",
            "balance": "12.800,00 ₺ (Alacaklı)",
            "terms": 15,
        },
        {
            "code": "M210000196",
            "name": "METRO MARKET TİCARET A.Ş.",
            "tax_office": "Güneşli V.D.",
            "tax_no": "5554443322",
            "address": "Basın Ekspres Yolu No:12 İstanbul",
            "balance": "0,00 ₺",
            "terms": 45,
        },
    ]

    SAMPLE_PRODUCTS = [
        {
            "code": "STK-001",
            "barcode": "8697240000008",
            "name": "VGA Sinyal Uzatma Kablosu 5M",
            "unit": "Metre",
            "price": 150.00,
            "vat": 20,
            "stock": 42,
        },
        {
            "code": "STK-002",
            "barcode": "8697240000009",
            "name": "Tükenmez Kalem Mavi 0.7mm",
            "unit": "Adet",
            "price": 15.00,
            "vat": 20,
            "stock": 180,
        },
        {
            "code": "STK-003",
            "barcode": "8697240000010",
            "name": "Tam Yağlı Günlük Süt 1 LT",
            "unit": "LT",
            "price": 28.50,
            "vat": 1,
            "stock": 65,
        },
        {
            "code": "STK-004",
            "barcode": "8697240000011",
            "name": "A4 Fotokopi Kağıdı 80gr 500lü",
            "unit": "Paket",
            "price": 120.00,
            "vat": 20,
            "stock": 25,
        },
        {
            "code": "HZM-001",
            "barcode": "",
            "name": "Teknik Servis & Yerinde Montaj Hizmeti",
            "unit": "Hizmet",
            "price": 450.00,
            "vat": 20,
            "stock": 999,
        },
        {
            "code": "HZM-002",
            "barcode": "",
            "name": "Şehir İçi Nakliye & Teslimat Bedeli",
            "unit": "Sefer",
            "price": 300.00,
            "vat": 20,
            "stock": 999,
        },
    ]

    def __init__(
        self,
        db_session=None,
        company_id: int = 1,
        doc_id: int | None = None,
        initial_type_idx: int = 0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.db = db_session
        self.company_id = company_id
        self.doc_id = doc_id
        self.initial_type_idx = initial_type_idx
        self.profile_key = "transaction_doc_items"
        self.profile_manager = ProfileManager(profile_key=self.profile_key)
        self.hidden_columns: set[int] = set()

        self.products_catalog = list(self.SAMPLE_PRODUCTS)
        self.customers_catalog = list(self.SAMPLE_CUSTOMERS)

        self.doc_note1 = "Garanti BBVA TR12 0006 2000 0001 2345 6789 01 - TL Hesabı"
        self.doc_note2 = (
            "Ürünler eksiksiz teslim alınmıştır. İhtilaf halinde "
            "Adana Mahkemeleri yetkilidir."
        )

        self._info_visible = True
        self._bottom_visible = True

        self.setWindowTitle(
            "[isl.doc.001] Evrensel Fiş & Evrak Detay Formu - TOYA ERP Master Şablon",
        )
        self.setObjectName("isl.doc.001")
        self.setMinimumSize(1024, 650)
        self.setWindowState(Qt.WindowState.WindowMaximized)

        self.setup_headers_dict()
        self.load_data_from_db()
        self.init_ui()
        self.setup_default_column_widths()
        self.load_sidebar_profiles()
        self.setup_keyboard_shortcuts()
        register_layout_hint(
            self,
            "Evrensel Fiş Detay Formu",
            "Master Fiş & Evrak Giriş Formu [tpl.trans.001]",
        )

        # Başlangıçta sadece 1 boş satır oluştur
        if self.doc_id is None:
            self.add_item_row(
                item_type="Malzeme",
                code="",
                name="",
                note2="",
                qty=1.0,
                unit="Adet",
                price=0.0,
                currency="TRY",
                vat=20,
                disc1=0.0,
                disc2=0.0,
                disc3=0.0,
            )
            if self.table_alt_iskonto.rowCount() == 0:
                self.add_alt_iskonto_row(
                    tur="İndirim",
                    turu="Toplamdan % Düş",
                    val=0.0,
                )

        # F6/F7 için event filter
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def closeEvent(self, event) -> None:  # noqa: N802
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            try:
                app.removeEventFilter(self)
            except Exception:
                pass
        super().closeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.showMaximized()

    def setup_default_column_widths(self) -> None:
        """Sütun genişliklerini standartlara göre ayarlar."""
        hheader = self.table_items.horizontalHeader()
        hheader.setMinimumSectionSize(20)
        hheader.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table_items.setColumnWidth(0, 24)  # 🗑️
        self.table_items.setColumnWidth(1, 85)  # Türü
        self.table_items.setColumnWidth(2, 90)  # Barkod
        self.table_items.setColumnWidth(3, 110)  # Stok Kodu
        hheader.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Açıklama
        self.table_items.setColumnWidth(5, 75)  # Satır Notu 2
        self.table_items.setColumnWidth(6, 50)  # Miktar
        self.table_items.setColumnWidth(7, 45)  # Birim
        self.table_items.setColumnWidth(8, 70)  # B.Fiyat
        self.table_items.setColumnWidth(9, 50)  # Döviz
        self.table_items.setColumnWidth(10, 40)  # İsk 1 %
        self.table_items.setColumnWidth(11, 55)  # İsk 1 Tutar
        self.table_items.setColumnWidth(12, 40)  # İsk 2 %
        self.table_items.setColumnWidth(13, 55)  # İsk 2 Tutar
        self.table_items.setColumnWidth(14, 40)  # İsk 3 %
        self.table_items.setColumnWidth(15, 55)  # İsk 3 Tutar
        self.table_items.setColumnWidth(16, 45)  # KDV %
        self.table_items.setColumnWidth(17, 55)  # Tevkifat
        self.table_items.setColumnWidth(18, 80)  # Tutar

    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        self.headers_dict = {
            0: ("🗑️", "action_delete"),
            1: ("Türü", "item_type"),
            2: ("Barkod", "barcode"),
            3: ("Stok Kodu", "sku"),
            4: ("Açıklama / Ürün Adı", "name"),
            5: ("Satır Notu 2", "note2"),
            6: ("Miktar", "quantity"),
            7: ("Birim", "unit"),
            8: ("B.Fiyat", "price"),
            9: ("Döviz", "currency"),
            10: ("İsk 1 %", "discount1"),
            11: ("İsk 1 Tutar", "discount1_amount"),
            12: ("İsk 2 %", "discount2"),
            13: ("İsk 2 Tutar", "discount2_amount"),
            14: ("İsk 3 %", "discount3"),
            15: ("İsk 3 Tutar", "discount3_amount"),
            16: ("KDV %", "vat_rate"),
            17: ("Tevkifat", "withholding"),
            18: ("Tutar", "total_amount"),
        }
        return self.headers_dict

    def sidebar_btn_style(self, bg_color="#ffffff", text_color="#1e293b") -> str:
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 600;
                text-align: left;
                font-family: 'Segoe UI';
                min-height: 26px;
                max-height: 26px;
            }}
            QPushButton:hover {{ background-color: #f1f5f9; }}
            QPushButton:disabled {{
                color: #94a3b8;
                background-color: #f8fafc;
                border-color: #e2e8f0;
            }}
        """

    def load_data_from_db(self) -> None:
        if self.db:
            try:
                db_prods = self.db.scalars(
                    select(Product).where(Product.is_deleted == False),  # noqa: E712
                ).all()
                if db_prods:
                    self.products_catalog = [
                        {
                            "code": p.sku or f"PRD-{p.id}",
                            "barcode": p.barcode or "",
                            "name": p.name,
                            "unit": "Adet",
                            "price": float(p.sale_price or 0.0),
                            "vat": 20,
                            "stock": int(p.stock_quantity or 0),
                        }
                        for p in db_prods
                    ]
                db_custs = self.db.scalars(
                    select(Customer).where(Customer.is_deleted == False),  # noqa: E712
                ).all()
                if db_custs:
                    self.customers_catalog = [
                        {
                            "code": c.customer_code or f"CAR-{c.id}",
                            "name": c.fullname,
                            "tax_office": c.tax_office or "-",
                            "tax_no": c.tax_number or "-",
                            "address": c.address or "-",
                            "balance": "0,00 ₺",
                            "terms": 30,
                        }
                        for c in db_custs
                    ]
            except Exception as e:
                logger.error(f"Error loading reference data: {e}")

    def init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 2, 4, 2)
        main_layout.setSpacing(2)

        # -------------------------------------------------------------
        # 1. TOP BAR (32px)
        # -------------------------------------------------------------
        top_bar = QFrame()
        top_bar.setObjectName("cmp.nav.001")
        top_bar.setFixedHeight(32)
        top_bar.setStyleSheet("""
            QFrame#cmp.nav.001 {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                           stop:0 #1e3a8a, stop:1 #0f172a);
                border-radius: 3px;
            }
            QComboBox, QLineEdit {
                background: #ffffff;
                color: #0f172a;
                font-weight: bold;
                font-size: 10px;
                padding: 1px 4px;
                border-radius: 3px;
                min-height: 20px;
            }
            QComboBox QAbstractItemView {
                background: #1e3a8a;
                color: #ffffff;
                border: 1px solid #3b82f6;
                selection-background-color: #3b82f6;
                selection-color: #ffffff;
            }
            QLabel {
                color: #93c5fd;
                font-size: 9px;
                font-weight: 600;
            }
        """)
        top_bar_lyt = QHBoxLayout(top_bar)
        top_bar_lyt.setContentsMargins(6, 2, 6, 2)
        top_bar_lyt.setSpacing(6)

        badge = QLabel("[isl.doc.001]")
        badge.setStyleSheet(
            "background:#3b82f6; color:#ffffff; font-size:8px; "
            "padding:1px 4px; border-radius:2px; font-weight:900;",
        )

        lbl_doc_badge = QLabel("📄 Tür:")
        self.cmb_doc_type = QComboBox()
        self.cmb_doc_type.setObjectName("cmp.nav.doc_type")
        self.cmb_doc_type.addItems(self.DOCUMENT_TYPES)
        self.cmb_doc_type.setCurrentIndex(self.initial_type_idx)
        self.cmb_doc_type.setMinimumWidth(180)
        self.cmb_doc_type.currentIndexChanged.connect(self.on_doc_type_changed)

        lbl_firma = QLabel("Firma: GENEL")
        lbl_branch = QLabel("Şube: MERKEZ (01)")

        lbl_depo = QLabel("🏢 Depo:")
        self.cmb_depo_top = QComboBox()
        self.cmb_depo_top.addItems([
            "2001 - MERKEZ DEPO",
            "2002 - ŞUBE DEPO",
            "2003 - TEŞHİR DEPO",
        ])
        self.cmb_depo_top.setMinimumWidth(120)
        self.cmb_depo = self.cmb_depo_top  # alias

        lbl_efatura = QLabel("⚡ E-Belge:")
        self.cmb_efatura_scenario = QComboBox()
        self.cmb_efatura_scenario.addItems(self.EFATURA_SCENARIOS)
        self.cmb_efatura_scenario.setCurrentIndex(1)
        self.cmb_efatura_scenario.setMinimumWidth(150)
        self.cmb_efatura = self.cmb_efatura_scenario  # alias

        lbl_top_doc = QLabel("Belge No:")
        self.txt_top_doc_no = QLineEdit()
        self.txt_top_doc_no.setPlaceholderText("Kaydedilince atanır")
        self.txt_top_doc_no.setReadOnly(True)
        self.txt_top_doc_no.setMaximumWidth(120)
        self.txt_top_doc_no.setStyleSheet(
            "background: #ffffff; color: #1e3a8a; font-weight: 800; font-size: 10px;",
        )

        top_bar_lyt.addWidget(badge)
        top_bar_lyt.addWidget(lbl_doc_badge)
        top_bar_lyt.addWidget(self.cmb_doc_type)
        top_bar_lyt.addWidget(lbl_firma)
        top_bar_lyt.addWidget(lbl_branch)
        top_bar_lyt.addWidget(lbl_depo)
        top_bar_lyt.addWidget(self.cmb_depo_top)
        top_bar_lyt.addWidget(lbl_efatura)
        top_bar_lyt.addWidget(self.cmb_efatura_scenario)
        top_bar_lyt.addStretch()
        top_bar_lyt.addWidget(lbl_top_doc)
        top_bar_lyt.addWidget(self.txt_top_doc_no)

        main_layout.addWidget(top_bar)

        # -------------------------------------------------------------
        # 2. SEKMELER (26px)
        # -------------------------------------------------------------
        self.header_tabs = QTabWidget()
        self.header_tabs.tabBar().setFixedHeight(26)
        self.header_tabs.setStyleSheet("""
            QTabBar::tab {
                height: 24px;
                padding: 0 12px;
                font-size: 10px;
                font-weight: bold;
                background: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                color: #1e3a8a;
                background: #ffffff;
                border-top: 2px solid #2563eb;
            }
            QTabWidget::pane {
                border: 1px solid #e2e8f0;
                background: #ffffff;
            }
        """)

        # -------------------------------------------------------------
        # 3. ORTA ANA GÖVDE: SOL PANEL (SIDEBAR) + SAĞ İÇERİK KAPSAYICISI
        # -------------------------------------------------------------
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        # SOL PANEL: EdgeTriggeredPanel (Başlangıçta açık)
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)
        register_layout_hint(
            self.left_panel,
            "Evrensel Fiş Detay",
            "Sol Evrak İşlemleri Paneli",
        )

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        left_frame = QFrame()
        left_frame.setStyleSheet("background-color: transparent; border: none;")
        left_lyt = QVBoxLayout(left_frame)
        left_lyt.setContentsMargins(0, 0, 0, 0)
        left_lyt.setSpacing(4)

        # 3.1. EVRAK İŞLEMLERİ
        self.sec_actions = CollapsibleSection("EVRAK İŞLEMLERİ", is_expanded=True)
        self.sec_actions.setObjectName("cmp.act.doc")

        self.btn_save = QPushButton("💾 Kaydet (F2)")
        self.btn_save.setShortcut("F2")
        self.btn_save.setFixedHeight(26)
        self.btn_save.setStyleSheet(self.sidebar_btn_style("#2563eb", "#ffffff"))
        self.btn_save.clicked.connect(self.save_document)

        self.btn_save_new = QPushButton("➕ Kaydet & Yeni")
        self.btn_save_new.setFixedHeight(26)
        self.btn_save_new.setStyleSheet(self.sidebar_btn_style("#059669", "#ffffff"))
        self.btn_save_new.clicked.connect(self.save_and_new_document)

        self.btn_save_print = QPushButton("🖨️ Kaydet & Yazdır (F9)")
        self.btn_save_print.setShortcut("F9")
        self.btn_save_print.setFixedHeight(26)
        self.btn_save_print.setStyleSheet(self.sidebar_btn_style("#0284c7", "#ffffff"))
        self.btn_save_print.clicked.connect(self.save_and_print_document)

        self.btn_import_lines = QPushButton("📥 Kalemleri Aktar ▼")
        self.btn_import_lines.setFixedHeight(26)
        self.btn_import_lines.setStyleSheet(self.sidebar_btn_style("#f1f5f9", "#1e3a8a"))
        self.setup_import_lines_menu()

        self.btn_share = QPushButton("📤 Gönder / Paylaş")
        self.btn_share.setFixedHeight(26)
        self.btn_share.setStyleSheet(self.sidebar_btn_style("#7c3aed", "#ffffff"))
        self.btn_share.clicked.connect(self.open_share_dialog)

        self.btn_earciv_send = QPushButton("⚡ e-Fatura Gönder")
        self.btn_earciv_send.setFixedHeight(26)
        self.btn_earciv_send.setStyleSheet(self.sidebar_btn_style("#7c3aed", "#ffffff"))
        self.btn_earciv_send.clicked.connect(self.send_earciv)

        self.btn_cancel = QPushButton("🚪 Vazgeç (Esc)")
        self.btn_cancel.setShortcut("Esc")
        self.btn_cancel.setFixedHeight(26)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                border: 1px solid #fca5a5;
                border-radius: 4px;
                padding: 2px 8px;
                font-family: 'Segoe UI';
                font-size: 10px;
                color: #991b1b;
                font-weight: bold;
                text-align: left;
                min-height: 26px;
                max-height: 26px;
            }
            QPushButton:hover { background-color: #fca5a5; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.sec_actions.add_widget(self.btn_save)
        self.sec_actions.add_widget(self.btn_save_new)
        self.sec_actions.add_widget(self.btn_save_print)
        self.sec_actions.add_widget(self.btn_import_lines)
        self.sec_actions.add_widget(self.btn_share)
        self.sec_actions.add_widget(self.btn_earciv_send)
        self.sec_actions.add_widget(self.btn_cancel)
        left_lyt.addWidget(self.sec_actions)

        # 3.2. SATIR İŞLEMLERİ
        self.sec_row_actions = CollapsibleSection("SATIR İŞLEMLERİ", is_expanded=True)
        self.sec_row_actions.setObjectName("cmp.act.rows")

        self.btn_add_row = QPushButton("➕ Satır Ekle (Alt+Enter)")
        self.btn_add_row.setFixedHeight(26)
        self.btn_add_row.setStyleSheet(self.sidebar_btn_style())
        self.btn_add_row.clicked.connect(lambda: self.add_item_row(item_type="Malzeme"))

        self.btn_del_selected = QPushButton("🗑️ Seçilenleri Sil (Ctrl+Del)")
        self.btn_del_selected.setFixedHeight(26)
        self.btn_del_selected.setStyleSheet(self.sidebar_btn_style("#fee2e2", "#991b1b"))
        self.btn_del_selected.clicked.connect(self.delete_selected_rows)
        self.btn_del_selected.setEnabled(False)
        self.btn_bulk_delete = self.btn_del_selected

        self.btn_move_up = QPushButton("⬆️ Satırı Yukarı (Alt+↑)")
        self.btn_move_up.setFixedHeight(26)
        self.btn_move_up.setStyleSheet(self.sidebar_btn_style())
        self.btn_move_up.clicked.connect(self.move_row_up)

        self.btn_move_down = QPushButton("⬇️ Satırı Aşağı (Alt+↓)")
        self.btn_move_down.setFixedHeight(26)
        self.btn_move_down.setStyleSheet(self.sidebar_btn_style())
        self.btn_move_down.clicked.connect(self.move_row_down)

        self.sec_row_actions.add_widget(self.btn_add_row)
        self.sec_row_actions.add_widget(self.btn_del_selected)
        self.sec_row_actions.add_widget(self.btn_move_up)
        self.sec_row_actions.add_widget(self.btn_move_down)
        left_lyt.addWidget(self.sec_row_actions)

        # 3.3. GÖRÜNÜM & SÜTUNLAR
        self.sec_profiles = CollapsibleSection("GÖRÜNÜM & SÜTUNLAR", is_expanded=True)
        lbl_prof = QLabel("Aktif Profil:")
        lbl_prof.setStyleSheet("font-weight: bold; color: #475569; font-size: 9px;")
        self.combo_sidebar_profiles = QComboBox()
        self.combo_sidebar_profiles.setFixedHeight(24)
        self.combo_sidebar_profiles.setStyleSheet(
            "QComboBox { border: 1px solid #cbd5e1; border-radius: 3px; font-size: 10px; }"
            "QComboBox QAbstractItemView { background: #1e293b; color: #ffffff; }",
        )
        self.combo_sidebar_profiles.currentTextChanged.connect(
            self._on_sidebar_profile_changed,
        )

        prof_btn_lyt = QHBoxLayout()
        prof_btn_lyt.setSpacing(4)
        btn_save_prof = QPushButton("💾 Kaydet")
        btn_save_prof.setFixedHeight(24)
        btn_save_prof.setStyleSheet(self.sidebar_btn_style())
        btn_save_prof.clicked.connect(self.save_current_profile)
        btn_manage_prof = QPushButton("⚙️ Sütunlar")
        btn_manage_prof.setFixedHeight(24)
        btn_manage_prof.setStyleSheet(self.sidebar_btn_style())
        btn_manage_prof.clicked.connect(self.open_column_manager)
        prof_btn_lyt.addWidget(btn_save_prof)
        prof_btn_lyt.addWidget(btn_manage_prof)

        self.sec_profiles.add_widget(lbl_prof)
        self.sec_profiles.add_widget(self.combo_sidebar_profiles)
        self.sec_profiles.add_layout(prof_btn_lyt)
        left_lyt.addWidget(self.sec_profiles)
        left_lyt.addStretch()

        left_scroll.setWidget(left_frame)
        self.left_panel.set_content(left_scroll)
        content_layout.addWidget(self.left_panel)

        # SAĞ GÖVDE KAPSAYICISI
        body_container = QWidget()
        body_layout = QVBoxLayout(body_container)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(2)

        # -------------------------------------------------------------
        # 4. ÜST BİLGİ PANELİ
        # -------------------------------------------------------------
        self.info_bar = QFrame()
        self.info_bar.setMaximumHeight(120)
        self.info_bar.setStyleSheet(
            "QFrame { background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 4px; }",
        )
        info_bar_main_lyt = QVBoxLayout(self.info_bar)
        info_bar_main_lyt.setContentsMargins(4, 2, 4, 2)
        info_bar_main_lyt.setSpacing(2)

        # 3 Panel Yan Yana
        info_panels_row = QHBoxLayout()
        info_panels_row.setContentsMargins(0, 0, 0, 0)
        info_panels_row.setSpacing(6)

        self.grp_cari = self.build_cari_panel()
        self.grp_belge = self.build_belge_panel()
        self.grp_finans = self.build_finans_panel()

        self.cari_kunye_widget = self.grp_cari
        self.belge_vade_widget = self.grp_belge
        self.hareket_finans_widget = self.grp_finans

        info_panels_row.addWidget(self.grp_cari, 4)
        info_panels_row.addWidget(self.grp_belge, 3)
        info_panels_row.addWidget(self.grp_finans, 3)
        info_bar_main_lyt.addLayout(info_panels_row)

        tab_genel = QWidget()
        tab_genel_lyt = QVBoxLayout(tab_genel)
        tab_genel_lyt.setContentsMargins(2, 2, 2, 2)
        tab_genel_lyt.addWidget(self.info_bar)

        self.header_tabs.addTab(tab_genel, "1 Genel Bilgiler")
        self.header_tabs.addTab(QWidget(), "2 Detay Bilgiler")
        self.header_tabs.addTab(QWidget(), "3 İskontolar & Masraflar")
        self.header_tabs.addTab(QWidget(), "4 Ek Alanlar")
        self.header_tabs.addTab(QWidget(), "5 Kümülatif KDV Dağılımı")

        body_layout.addWidget(self.header_tabs)

        # -------------------------------------------------------------
        # ÜST SPLITTER BAR (F7 TOGGLE) — Alt panel gibi ince bar
        # -------------------------------------------------------------
        top_splitter_bar = QFrame()
        top_splitter_bar.setFixedHeight(18)
        top_splitter_bar.setStyleSheet("""
            QFrame { background:#f1f5f9; border-top:1px solid #e2e8f0;
                     border-bottom:1px solid #e2e8f0; }
        """)
        top_split_lyt = QHBoxLayout(top_splitter_bar)
        top_split_lyt.setContentsMargins(4, 0, 4, 0)
        top_split_lyt.setSpacing(4)

        line_top_sep = QFrame()
        line_top_sep.setFrameShape(QFrame.Shape.HLine)
        line_top_sep.setStyleSheet("color:#cbd5e1;")

        self.btn_toggle_top = QPushButton("∨ ÜST PANEL (F7)")
        self.btn_toggle_top.setFixedHeight(16)
        self.btn_toggle_top.setStyleSheet("""
            QPushButton {
                background:#e2e8f0; border:none; border-radius:3px;
                font-size:9px; color:#64748b; padding:0 6px; font-weight:600;
            }
            QPushButton:hover { background:#cbd5e1; color:#0f172a; }
        """)
        self.btn_toggle_top.clicked.connect(self.toggle_info_panel)

        top_split_lyt.addWidget(line_top_sep, 1)
        top_split_lyt.addWidget(self.btn_toggle_top)
        body_layout.addWidget(top_splitter_bar)

        # -------------------------------------------------------------
        # 5. KALEMLER GRİD — HareketKalemleriWidget
        # -------------------------------------------------------------
        self.table_items = QTableWidget(0, len(self.COLUMN_NAMES))
        self.hareket_kalemleri_widget = self.table_items
        self.table_items.setHorizontalHeaderLabels(self.COLUMN_NAMES)

        self.table_items.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self.table_items.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.table_items.setShowGrid(True)
        self.table_items.setAlternatingRowColors(True)
        self.table_items.itemSelectionChanged.connect(self._on_table_selection_changed)

        self.table_items.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #cbd5e1;
                font-family: 'Segoe UI';
                font-size: 11px;
                color: #0f172a;
                alternate-background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                selection-background-color: #e2e8f0;
                selection-color: #0f172a;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #334155;
                padding: 2px 4px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 1px solid #cbd5e1;
                font-weight: bold;
                font-size: 9px;
                min-height: 24px;
                max-height: 26px;
            }
            QHeaderView::section:vertical {
                background-color: #f8fafc;
                color: #64748b;
                font-weight: bold;
                font-size: 10px;
                padding: 1px 4px;
                border-right: 1px solid #cbd5e1;
            }
        """)

        hheader = self.table_items.horizontalHeader()
        hheader.setFixedHeight(26)
        hheader.setHighlightSections(False)
        hheader.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        h_font = hheader.font()
        h_font.setPointSize(9)
        hheader.setFont(h_font)

        theme_mgr = ThemeManager()
        row_h = theme_mgr.row_height
        vheader = self.table_items.verticalHeader()
        vheader.setVisible(True)
        vheader.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        vheader.setDefaultSectionSize(row_h)
        vheader.setMinimumSectionSize(20)
        vheader.setHighlightSections(False)
        vheader.setSectionsMovable(True)
        vheader.sectionDoubleClicked.connect(lambda r: self.table_items.selectRow(r))
        vheader.sectionMoved.connect(self.on_row_reordered)
        theme_mgr.row_height_changed.connect(self._on_theme_row_height_changed)

        self.table_items.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table_items.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

        self.table_items.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_items.customContextMenuRequested.connect(
            self.show_items_body_context_menu,
        )

        body_layout.addWidget(self.table_items, 1)

        # -------------------------------------------------------------
        # 6. ALT SPLITTER BAR (F6 TOGGLE)
        # -------------------------------------------------------------
        splitter_bar = QFrame()
        splitter_bar.setFixedHeight(18)
        splitter_bar.setStyleSheet("""
            QFrame { background:#f1f5f9; border-top:1px solid #e2e8f0;
                     border-bottom:1px solid #e2e8f0; }
        """)
        bar_split_lyt = QHBoxLayout(splitter_bar)
        bar_split_lyt.setContentsMargins(4, 0, 4, 0)
        bar_split_lyt.setSpacing(4)

        line_sep = QFrame()
        line_sep.setFrameShape(QFrame.Shape.HLine)
        line_sep.setStyleSheet("color:#cbd5e1;")

        self.btn_toggle_bottom = QPushButton("∨ Alt Panel (F6)")
        self.btn_toggle_bottom.setFixedHeight(16)
        self.btn_toggle_bottom.setStyleSheet("""
            QPushButton {
                background:#e2e8f0; border:none; border-radius:3px;
                font-size:9px; color:#64748b; padding:0 6px; font-weight:600;
            }
            QPushButton:hover { background:#cbd5e1; color:#0f172a; }
        """)
        self.btn_toggle_bottom.clicked.connect(self.toggle_bottom_panel)

        bar_split_lyt.addWidget(line_sep, 1)
        bar_split_lyt.addWidget(self.btn_toggle_bottom)
        body_layout.addWidget(splitter_bar)

        # F6 Kısayolu
        sc_f6 = QShortcut(QKeySequence("F6"), self)
        sc_f6.activated.connect(self.toggle_bottom_panel)
        self._shortcuts = {"f6_toggle": sc_f6}

        # -------------------------------------------------------------
        # 7. ALT PANEL (QSPLITTER)
        # -------------------------------------------------------------
        self.alt_tabs = QTabWidget()
        self.alt_iskonto_masraf_widget = self.alt_tabs
        self.alt_tabs.tabBar().setMaximumHeight(24)
        self.alt_tabs.tabBar().setFixedHeight(24)
        self.alt_tabs.setMinimumHeight(90)
        self.alt_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                font-weight: bold;
                font-size: 10px;
                padding: 1px 8px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 3px;
                border-top-right-radius: 3px;
                margin-right: 2px;
                min-height: 18px;
                max-height: 22px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1e3a8a;
                border-top: 2px solid #2563eb;
            }
        """)

        self.alt_tabs.addTab(self.build_iskonto_tab(), "A İndirim & Masraflar")
        self.alt_tabs.addTab(QWidget(), "B Seri-Lot")
        self.alt_tabs.addTab(QWidget(), "C Varyant")
        self.alt_tabs.addTab(QWidget(), "D Paketler")

        # 7b. Notlar & Barkod Alanı
        notes_frame = QFrame()
        notes_frame.setMinimumHeight(90)
        notes_frame.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;",
        )
        notes_lyt = QVBoxLayout(notes_frame)
        notes_lyt.setContentsMargins(4, 2, 4, 2)
        notes_lyt.setSpacing(2)

        barcode_frame = QFrame()
        barcode_frame.setStyleSheet(
            "background:#f0fdf4; border:1px solid #86efac; border-radius:3px;",
        )
        bc_lyt = QHBoxLayout(barcode_frame)
        bc_lyt.setContentsMargins(4, 1, 4, 1)
        bc_lyt.setSpacing(4)

        lbl_bc = QLabel("🔍")
        lbl_bc.setStyleSheet("font-size:11px;")

        self.txt_barcode_input = QLineEdit()
        self.txt_barcode_input.setPlaceholderText("Barkod / Seri No / Lot No ile ürün çağır...")
        self.txt_barcode_input.setFixedHeight(22)
        self.txt_barcode_input.setStyleSheet(
            "background: white; border: 1px solid #86efac; border-radius: 2px; font-size: 10px; padding: 1px 4px;",
        )
        self.txt_barcode_input.returnPressed.connect(self.on_barcode_entered)

        self.cmb_barcode_type = QComboBox()
        self.cmb_barcode_type.addItems(["Barkod", "Seri No", "Lot No"])
        self.cmb_barcode_type.setFixedHeight(22)
        self.cmb_barcode_type.setFixedWidth(75)
        self.cmb_barcode_type.setStyleSheet(
            "QComboBox { font-size: 10px; } QComboBox QAbstractItemView { background: #1e293b; color: #ffffff; }",
        )

        bc_lyt.addWidget(lbl_bc)
        bc_lyt.addWidget(self.txt_barcode_input, 1)
        bc_lyt.addWidget(self.cmb_barcode_type)
        notes_lyt.addWidget(barcode_frame)

        self.lbl_note_preview = QLabel(
            "Banka: Garanti BBVA TR12 0006...\nŞartlar: Adana Mahkemeleri yetkilidir.",
        )
        self.lbl_note_preview.setStyleSheet(
            "color: #0f172a; font-size: 9px; background: #f8fafc; "
            "border: 1px solid #e2e8f0; border-radius: 3px; padding: 2px 4px;",
        )
        self.lbl_note_preview.setWordWrap(True)
        notes_lyt.addWidget(self.lbl_note_preview, 1)

        btn_open_notes = QPushButton("✏️ Notları Düzenle...")
        btn_open_notes.setFixedHeight(22)
        btn_open_notes.setStyleSheet(
            "background-color: #f1f5f9; color: #1e3a8a; font-weight: bold; "
            "font-size: 9px; border: 1px solid #cbd5e1; border-radius: 3px;",
        )
        btn_open_notes.clicked.connect(self.open_notes_dialog)
        notes_lyt.addWidget(btn_open_notes)

        # 7c. Toplamlar Paneli
        totals_frame = QFrame()
        self.toplam_widget = totals_frame
        totals_frame.setMinimumHeight(90)
        totals_frame.setMinimumWidth(170)
        totals_frame.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px;",
        )

        totals_grid = QGridLayout(totals_frame)
        totals_grid.setContentsMargins(6, 2, 6, 2)
        totals_grid.setSpacing(1)

        totals_grid.addWidget(QLabel(""), 0, 0)
        lbl_tl_hdr = QLabel("TL")
        lbl_tl_hdr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_tl_hdr.setStyleSheet("font-weight:bold; color:#475569; font-size:9px;")
        lbl_dov_hdr = QLabel("Döviz")
        lbl_dov_hdr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_dov_hdr.setStyleSheet("font-weight:bold; color:#475569; font-size:9px;")
        totals_grid.addWidget(lbl_tl_hdr, 0, 1)
        totals_grid.addWidget(lbl_dov_hdr, 0, 2)

        total_rows_config = [
            ("Ara Top:", "lbl_subtotal", "0,00 ₺", "#1e293b"),
            ("Masraf:", "lbl_expense_total", "+0,00 ₺", "#0284c7"),
            ("İndirim:", "lbl_discount", "-0,00 ₺", "#dc2626"),
            ("Toplam:", "lbl_net_total", "0,00 ₺", "#1e293b"),
            ("Özel V.:", "lbl_special_tax", "+0,00 ₺", "#7c3aed"),
            ("KDV:", "lbl_vat_total", "+0,00 ₺", "#7c3aed"),
            ("Tevkifat:", "lbl_withholding", "-0,00 ₺", "#94a3b8"),
        ]

        for r, (baslik, attr, default, color) in enumerate(total_rows_config, 1):
            lbl_t = QLabel(baslik)
            lbl_t.setStyleSheet("font-size:9px; font-weight:600; color:#475569;")

            lbl_v_tl = QLabel(default)
            lbl_v_tl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_v_tl.setStyleSheet(f"font-size:10px; font-weight:bold; color:{color};")

            lbl_v_dov = QLabel("0,00 $")
            lbl_v_dov.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_v_dov.setStyleSheet("font-size:9px; color:#64748b;")

            setattr(self, attr, lbl_v_tl)
            setattr(self, f"{attr}_doviz", lbl_v_dov)

            totals_grid.addWidget(lbl_t, r, 0)
            totals_grid.addWidget(lbl_v_tl, r, 1)
            totals_grid.addWidget(lbl_v_dov, r, 2)

        line_t = QFrame()
        line_t.setFrameShape(QFrame.Shape.HLine)
        line_t.setStyleSheet("color:#cbd5e1;")
        totals_grid.addWidget(line_t, len(total_rows_config) + 1, 0, 1, 3)

        lbl_gt = QLabel("G.TOPLAM:")
        lbl_gt.setStyleSheet("font-size:10px; font-weight:800; color:#1e3a8a;")

        self.lbl_grand_total = QLabel("0,00 ₺")
        self.lbl_grand_total.setStyleSheet(
            "font-size:13px; font-weight:800; color:#ffffff;"
            "background:#1e3a8a; border-radius:3px; padding:1px 4px;",
        )
        self.lbl_grand_total.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.lbl_grand_total_doviz = QLabel("0,00 $")
        self.lbl_grand_total_doviz.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_grand_total_doviz.setStyleSheet("font-size:10px; font-weight:bold; color:#1e3a8a;")
        self.lbl_doviz_total = self.lbl_grand_total_doviz

        totals_grid.addWidget(lbl_gt, len(total_rows_config) + 2, 0)
        totals_grid.addWidget(self.lbl_grand_total, len(total_rows_config) + 2, 1)
        totals_grid.addWidget(self.lbl_grand_total_doviz, len(total_rows_config) + 2, 2)

        totals_grid.setColumnStretch(0, 0)
        totals_grid.setColumnStretch(1, 1)
        totals_grid.setColumnStretch(2, 1)

        self.bottom_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.bottom_splitter.setChildrenCollapsible(False)
        self.bottom_splitter.addWidget(self.alt_tabs)
        self.bottom_splitter.addWidget(notes_frame)
        self.bottom_splitter.addWidget(totals_frame)
        self.bottom_splitter.setStretchFactor(0, 5)
        self.bottom_splitter.setStretchFactor(1, 3)
        self.bottom_splitter.setStretchFactor(2, 3)

        self.bottom_panel = self.bottom_splitter
        body_layout.addWidget(self.bottom_panel)

        content_layout.addWidget(body_container, 1)

        # -------------------------------------------------------------
        # SAĞ PANEL: EdgeTriggeredPanel (Başlangıçta kapalı)
        # -------------------------------------------------------------
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)
        register_layout_hint(
            self.right_panel,
            "Evrensel Fiş Detay",
            "Sağ Evrak İşlemleri ve Özet Paneli",
        )

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }",
        )

        right_frame = QFrame()
        right_frame.setStyleSheet("background-color: transparent; border: none;")
        right_lyt = QVBoxLayout(right_frame)
        right_lyt.setContentsMargins(0, 0, 0, 0)
        right_lyt.setSpacing(6)

        # ── YAZDIRMA & AKTARIM ──
        sec_print = CollapsibleSection("🖨️ YAZDIRMA & AKTARIM", is_expanded=True)

        btn_pdf = QPushButton("🖨️ PDF Yazdır (F9)")
        btn_pdf.setStyleSheet(self.sidebar_btn_style("#0284c7", "#ffffff"))
        btn_pdf.clicked.connect(self.save_and_print_document)

        btn_excel = QPushButton("📊 Excel'e Aktar")
        btn_excel.setStyleSheet(self.sidebar_btn_style())
        btn_excel.clicked.connect(self.export_to_excel)

        btn_share = QPushButton("📤 Gönder / Paylaş")
        btn_share.setStyleSheet(self.sidebar_btn_style("#7c3aed", "#ffffff"))
        btn_share.clicked.connect(self.open_share_dialog)

        btn_whatsapp = QPushButton("💬 WhatsApp")
        btn_whatsapp.setStyleSheet(self.sidebar_btn_style("#16a34a", "#ffffff"))
        btn_whatsapp.clicked.connect(self._share_whatsapp)

        btn_email = QPushButton("📧 E-posta Gönder")
        btn_email.setStyleSheet(self.sidebar_btn_style())
        btn_email.clicked.connect(self._send_email_quick)

        btn_copy_link = QPushButton("🔗 Linki Kopyala")
        btn_copy_link.setStyleSheet(self.sidebar_btn_style())
        btn_copy_link.clicked.connect(self._copy_link)

        sec_print.add_widget(btn_pdf)
        sec_print.add_widget(btn_excel)
        sec_print.add_widget(btn_share)
        sec_print.add_widget(btn_whatsapp)
        sec_print.add_widget(btn_email)
        sec_print.add_widget(btn_copy_link)
        right_lyt.addWidget(sec_print)

        # ── EVRAK BİLGİLERİ (salt okunur özet) ──
        sec_info = CollapsibleSection("📋 EVRAK ÖZETİ", is_expanded=True)

        self.lbl_right_teklif_no = QLabel("Belge No: —")
        self.lbl_right_teklif_no.setStyleSheet(
            "font-size:10px; font-weight:600; color:#1e3a8a;",
        )
        self.lbl_right_musteri = QLabel("Müşteri: —")
        self.lbl_right_musteri.setStyleSheet(
            "font-size:10px; color:#475569;",
        )
        self.lbl_right_toplam = QLabel("Toplam: —")
        self.lbl_right_toplam.setStyleSheet(
            "font-size:11px; font-weight:700; color:#1e3a8a;",
        )
        self.lbl_right_durum = QLabel("Durum: Taslak")
        self.lbl_right_durum.setStyleSheet(
            "font-size:10px; color:#64748b;",
        )

        sec_info.add_widget(self.lbl_right_teklif_no)
        sec_info.add_widget(self.lbl_right_musteri)
        sec_info.add_widget(self.lbl_right_toplam)
        sec_info.add_widget(self.lbl_right_durum)
        right_lyt.addWidget(sec_info)

        # ── HIZLI İŞLEMLER ──
        sec_quick = CollapsibleSection("⚡ HIZLI İŞLEMLER", is_expanded=True)

        btn_convert = QPushButton("🔄 Siparişe Dönüştür")
        btn_convert.setStyleSheet(self.sidebar_btn_style("#0369a1", "#ffffff"))
        btn_convert.clicked.connect(self._on_convert_clicked)

        btn_copy_doc = QPushButton("📋 Belgeyi Kopyala")
        btn_copy_doc.setStyleSheet(self.sidebar_btn_style())
        btn_copy_doc.clicked.connect(self._on_duplicate_doc)

        btn_efatura = QPushButton("⚡ e-Fatura Gönder")
        btn_efatura.setStyleSheet(self.sidebar_btn_style("#7c3aed", "#ffffff"))
        btn_efatura.clicked.connect(self.send_earciv)

        sec_quick.add_widget(btn_convert)
        sec_quick.add_widget(btn_copy_doc)
        sec_quick.add_widget(btn_efatura)
        right_lyt.addWidget(sec_quick)

        right_lyt.addStretch()
        right_scroll.setWidget(right_frame)
        self.right_panel.set_content(right_scroll)
        self.right_panel.close_panel()  # Başlangıçta kapalı

        content_layout.addWidget(self.right_panel)
        main_layout.addLayout(content_layout, 1)

        # -------------------------------------------------------------
        # 8. ALT BAR (38px)
        # -------------------------------------------------------------
        bottom_bar = QFrame()
        bottom_bar.setObjectName("BottomActionBar")
        bottom_bar.setFixedHeight(38)
        bottom_bar.setStyleSheet("""
            QFrame#BottomActionBar {
                background-color: #f8fafc;
                border-top: 1px solid #e2e8f0;
                padding: 2px 6px;
            }
        """)
        bot_lyt = QHBoxLayout(bottom_bar)
        bot_lyt.setContentsMargins(6, 2, 6, 2)
        bot_lyt.setSpacing(6)

        lbl_keys = QLabel(
            "F2: Kaydet | F9: Yazdır | Alt+Enter: Satır | Ctrl+Del: Sil | F6: Alt Panel | F7: Üst Panel | Esc: Vazgeç",
        )
        lbl_keys.setStyleSheet("color: #94a3b8; font-size: 9px; font-family: 'Segoe UI';")

        btn_h = 28

        self.btn_bottom_cancel = QPushButton("🚪 Vazgeç (Esc)")
        self.btn_bottom_cancel.setShortcut("Esc")
        self.btn_bottom_cancel.setFixedHeight(btn_h)
        self.btn_bottom_cancel.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2; color: #991b1b;
                font-weight: 700; font-size: 10px;
                border: 1px solid #fca5a5; border-radius: 4px; padding: 2px 10px;
            }
            QPushButton:hover { background-color: #fca5a5; }
        """)
        self.btn_bottom_cancel.clicked.connect(self.reject)

        self.btn_bottom_excel = QPushButton("📊 Excel")
        self.btn_bottom_excel.setFixedHeight(btn_h)
        self.btn_bottom_excel.setStyleSheet("""
            QPushButton {
                background-color: #0284c7; color: #ffffff;
                font-weight: 700; font-size: 10px;
                border: 1px solid #0369a1; border-radius: 4px; padding: 2px 10px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_bottom_excel.clicked.connect(self.export_to_excel)

        self.btn_bottom_save_print = QPushButton("🖨️ Kaydet & Yazdır (F9)")
        self.btn_bottom_save_print.setShortcut("F9")
        self.btn_bottom_save_print.setFixedHeight(btn_h)
        self.btn_bottom_save_print.setStyleSheet("""
            QPushButton {
                background-color: #0284c7; color: #ffffff;
                font-weight: 700; font-size: 10px;
                border: 1px solid #0369a1; border-radius: 4px; padding: 2px 10px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_bottom_save_print.clicked.connect(self.save_and_print_document)

        self.btn_bottom_save_new = QPushButton("➕ Kaydet & Yeni")
        self.btn_bottom_save_new.setFixedHeight(btn_h)
        self.btn_bottom_save_new.setStyleSheet("""
            QPushButton {
                background-color: #059669; color: #ffffff;
                font-weight: 700; font-size: 10px;
                border: 1px solid #047857; border-radius: 4px; padding: 2px 10px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.btn_bottom_save_new.clicked.connect(self.save_and_new_document)

        self.btn_bottom_save = QPushButton("💾 KAYDET (F2)")
        self.btn_bottom_save.setShortcut("F2")
        self.btn_bottom_save.setFixedHeight(btn_h)
        self.btn_bottom_save.setStyleSheet("""
            QPushButton {
                background-color: #1d4ed8; color: #ffffff;
                font-weight: 800; font-size: 11px;
                border: 1px solid #1e40af; border-radius: 4px; padding: 2px 16px;
            }
            QPushButton:hover { background-color: #1e40af; }
        """)
        self.btn_bottom_save.clicked.connect(self.save_document)

        bot_lyt.addWidget(lbl_keys)
        bot_lyt.addStretch()
        bot_lyt.addWidget(self.btn_bottom_cancel)
        bot_lyt.addWidget(self.btn_bottom_excel)
        bot_lyt.addWidget(self.btn_bottom_save_print)
        bot_lyt.addWidget(self.btn_bottom_save_new)
        bot_lyt.addWidget(self.btn_bottom_save)

        main_layout.addWidget(bottom_bar)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        from PyQt6.QtCore import QEvent, Qt
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_F6:
                self.toggle_bottom_panel()
                return True
            elif key == Qt.Key.Key_F7:
                self.toggle_info_panel()
                return True
            elif key == Qt.Key.Key_F5:
                self.calculate_totals()
                return True
        return super().eventFilter(obj, event)

    def accept(self) -> None:
        from PyQt6.QtWidgets import QApplication
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        super().accept()

    def reject(self) -> None:
        from PyQt6.QtWidgets import QApplication
        try:
            QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        super().reject()

    def toggle_info_panel(self) -> None:
        """Üst bilgi panelini açıp kapatır."""
        self._info_visible = not self._info_visible
        if hasattr(self, "info_panels_widget"):
            self.info_panels_widget.setVisible(self._info_visible)
        if hasattr(self, "header_tabs"):
            self.header_tabs.setVisible(self._info_visible)
        if hasattr(self, "btn_toggle_top"):
            self.btn_toggle_top.setText(
                "∨ ÜST PANEL (F7)" if self._info_visible else "∧ ÜST PANEL (F7)",
            )

    def toggle_bottom_panel(self) -> None:
        """Alt paneli (masraf/not/toplam) açıp kapatır."""
        self._bottom_visible = not self._bottom_visible
        self.bottom_panel.setVisible(self._bottom_visible)
        if hasattr(self, "btn_toggle_bottom"):
            self.btn_toggle_bottom.setText(
                "∨ Alt Panel (F6)" if self._bottom_visible else "∧ Alt Panel (F6)",
            )

    def build_cari_panel(self) -> QFrame:
        """4a. CARİ KÜNYESİ Paneli."""
        frame = QFrame()
        frame.setStyleSheet("background: transparent; border: none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(2, 0, 2, 0)
        lyt.setSpacing(2)

        lbl_hdr = QLabel("👤 CARİ HESAP KÜNYESİ")
        lbl_hdr.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px;")
        lyt.addWidget(lbl_hdr)

        lbl_style = "font-size: 9px; font-weight: 600; color: #64748b;"
        field_h = 22
        combo_style = (
            "QLineEdit { border: 1px solid #cbd5e1; border-radius: 3px; "
            "padding: 1px 4px; font-size: 10px; background: white; }"
        )

        # Satır 1: Cari Kodu / Ünvan
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        lbl_kod_unv = QLabel("Cari Kodu / Ünvan:")
        lbl_kod_unv.setStyleSheet(lbl_style)
        lbl_kod_unv.setFixedWidth(95)

        self.txt_cari_kodu = QLineEdit("M210000194")
        self.txt_cari_kodu.setMinimumWidth(120)
        self.txt_cari_kodu.setFixedHeight(field_h)
        self.txt_cari_kodu.setStyleSheet(combo_style + " font-weight: bold;")

        self.txt_cari_unvan = QLineEdit("TATU HIRDAVAT İÇ VE DIŞ TİC.LTD.ŞTİ")
        self.txt_cari_unvan.setFixedHeight(field_h)
        self.txt_cari_unvan.setStyleSheet(combo_style + " font-weight: bold;")

        search_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        act_search_kod = QAction(search_icon, "", self)
        act_search_kod.triggered.connect(self.open_customer_lookup)
        self.txt_cari_kodu.addAction(act_search_kod, QLineEdit.ActionPosition.TrailingPosition)

        act_search_unv = QAction(search_icon, "", self)
        act_search_unv.triggered.connect(self.open_customer_lookup)
        self.txt_cari_unvan.addAction(act_search_unv, QLineEdit.ActionPosition.TrailingPosition)

        row1.addWidget(lbl_kod_unv)
        row1.addWidget(self.txt_cari_kodu)
        row1.addWidget(self.txt_cari_unvan, 1)
        lyt.addLayout(row1)

        # Satır 2: Vergi D./No
        row2 = QHBoxLayout()
        row2.setSpacing(3)
        lbl_vd = QLabel("Vergi D./No:")
        lbl_vd.setStyleSheet(lbl_style)
        lbl_vd.setFixedWidth(95)

        self.txt_vergi_daire = QLineEdit("Seyhan V.D.")
        self.txt_vergi_daire.setMinimumWidth(130)
        self.txt_vergi_daire.setFixedHeight(field_h)
        self.txt_vergi_daire.setStyleSheet(combo_style)

        self.txt_vergi_no = QLineEdit("1234567896")
        self.txt_vergi_no.setMinimumWidth(110)
        self.txt_vergi_no.setFixedHeight(field_h)
        self.txt_vergi_no.setStyleSheet(combo_style)

        self.btn_bakiye = QPushButton("💳 BAKİYE")
        self.btn_bakiye.setFixedHeight(field_h)
        self.btn_bakiye.setStyleSheet(
            "background:#fee2e2; color:#991b1b; font-weight:bold; "
            "border: 1px solid #fca5a5; border-radius: 3px; font-size: 9px; padding: 1px 6px;",
        )
        self.btn_bakiye.clicked.connect(self.show_customer_balance)

        row2.addWidget(lbl_vd)
        row2.addWidget(self.txt_vergi_daire)
        row2.addWidget(self.txt_vergi_no)
        row2.addWidget(self.btn_bakiye)
        row2.addStretch()
        lyt.addLayout(row2)

        # Satır 3: Sevk Adr.
        row3 = QHBoxLayout()
        row3.setSpacing(4)
        lbl_adres = QLabel("Sevk Adr.:")
        lbl_adres.setStyleSheet(lbl_style)
        lbl_adres.setFixedWidth(95)

        self.txt_sevk_adres = QLineEdit("Mersinli Mah. 2826 Sk. No:14/101 Adana")
        self.txt_sevk_adres.setFixedHeight(field_h)
        self.txt_sevk_adres.setStyleSheet(combo_style)

        row3.addWidget(lbl_adres)
        row3.addWidget(self.txt_sevk_adres, 1)
        lyt.addLayout(row3)

        self.setup_customer_completers()
        return frame

    def build_belge_panel(self) -> QFrame:
        """4b. BELGE & VADE Paneli."""
        frame = QFrame()
        frame.setStyleSheet("background: transparent; border: none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(2, 0, 2, 0)
        lyt.setSpacing(2)

        lbl_hdr = QLabel("📅 BELGE & VADE DETAYLARI")
        lbl_hdr.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px;")
        lyt.addWidget(lbl_hdr)

        lbl_style = "font-size: 9px; font-weight: 600; color: #64748b;"
        field_h = 22
        combo_style = (
            "QLineEdit, QComboBox, QDateEdit { border: 1px solid #cbd5e1; border-radius: 3px; "
            "padding: 1px 4px; font-size: 10px; background: white; color: #0f172a; }"
            "QComboBox QAbstractItemView { background: #1e293b; color: #ffffff; }"
        )

        # Satır 1: Seri / No / Fiş
        row1 = QHBoxLayout()
        row1.setSpacing(2)
        lbl_seri = QLabel("Seri/No/Fiş:")
        lbl_seri.setStyleSheet(lbl_style)
        lbl_seri.setFixedWidth(80)

        self.txt_fatura_seri = QLineEdit("S220165")
        self.txt_fatura_seri.setMinimumWidth(70)
        self.txt_fatura_seri.setFixedHeight(field_h)
        self.txt_fatura_seri.setStyleSheet(combo_style)

        self.txt_belge_no = QLineEdit("TOY2026-001")
        self.txt_belge_no.setMaximumWidth(80)
        self.txt_belge_no.setFixedHeight(field_h)
        self.txt_belge_no.setStyleSheet(combo_style)

        self.txt_fis_no = QLineEdit("00000056")
        self.txt_fis_no.setMinimumWidth(80)
        self.txt_fis_no.setFixedHeight(field_h)
        self.txt_fis_no.setStyleSheet(combo_style)
        self.txt_fatura_sira = self.txt_fis_no  # alias

        row1.addWidget(lbl_seri)
        row1.addWidget(self.txt_fatura_seri)
        row1.addWidget(self.txt_belge_no)
        row1.addWidget(self.txt_fis_no)
        row1.addStretch()
        lyt.addLayout(row1)

        # Satır 2: Tarih / Saat / Vade
        row2 = QHBoxLayout()
        row2.setSpacing(2)
        lbl_tarih = QLabel("Tarih/Saat/Vade:")
        lbl_tarih.setStyleSheet(lbl_style)
        lbl_tarih.setFixedWidth(80)

        self.date_belge = QDateEdit(QDate.currentDate())
        self.date_belge.setCalendarPopup(True)
        self.date_belge.setDisplayFormat("dd.MM.yyyy")
        self.date_belge.setFixedHeight(field_h)
        self.date_belge.setStyleSheet(combo_style)

        self.txt_saat = QLineEdit(QTime.currentTime().toString("HH:mm"))
        self.txt_saat.setMaximumWidth(42)
        self.txt_saat.setFixedHeight(field_h)
        self.txt_saat.setStyleSheet(combo_style)

        self.date_vade = QDateEdit(QDate.currentDate().addDays(30))
        self.date_vade.setCalendarPopup(True)
        self.date_vade.setDisplayFormat("dd.MM.yyyy")
        self.date_vade.setFixedHeight(field_h)
        self.date_vade.setStyleSheet(combo_style)

        self.cmb_vade_gun = QComboBox()
        self.cmb_vade_gun.addItems(["(30 Gün)", "(45 Gün)", "(60 Gün)", "(90 Gün)", "Manuel"])
        self.cmb_vade_gun.setMaximumWidth(58)
        self.cmb_vade_gun.setFixedHeight(field_h)
        self.cmb_vade_gun.setStyleSheet(combo_style)
        self.cmb_vade_gun.currentTextChanged.connect(self.on_vade_gun_changed)
        self.cmb_vade_formul = self.cmb_vade_gun  # alias

        row2.addWidget(lbl_tarih)
        row2.addWidget(self.date_belge)
        row2.addWidget(self.txt_saat)
        row2.addWidget(self.date_vade)
        row2.addWidget(self.cmb_vade_gun)
        lyt.addLayout(row2)

        # Satır 3: Ödeme Planı
        row3 = QHBoxLayout()
        row3.setSpacing(2)
        lbl_odeme = QLabel("Ödeme Planı:")
        lbl_odeme.setStyleSheet(lbl_style)
        lbl_odeme.setFixedWidth(80)

        self.cmb_odeme_plani = QComboBox()
        self.cmb_odeme_plani.setFixedHeight(field_h)
        self.cmb_odeme_plani.setStyleSheet(combo_style)
        self.cmb_odeme_plani.addItem("--- Ödeme Planı Seçin ---", None)
        for p in self.ODEME_PLANLARI:
            self.cmb_odeme_plani.addItem(f"{p['kod']} - {p['aciklama']}", p)
        self.cmb_odeme_plani.currentIndexChanged.connect(self.on_odeme_plani_changed)

        row3.addWidget(lbl_odeme)
        row3.addWidget(self.cmb_odeme_plani, 1)
        lyt.addLayout(row3)

        return frame

    def build_finans_panel(self) -> QFrame:
        """4c. FİNANS Paneli."""
        frame = QFrame()
        frame.setStyleSheet("background: transparent; border: none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(2, 0, 2, 0)
        lyt.setSpacing(2)

        lbl_hdr = QLabel("⚙️ HAREKET AYARLARI & FİNANS")
        lbl_hdr.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px;")
        lyt.addWidget(lbl_hdr)

        lbl_style = "font-size: 9px; font-weight: 600; color: #64748b;"
        field_h = 22
        combo_style = (
            "QLineEdit, QComboBox { border: 1px solid #cbd5e1; border-radius: 3px; "
            "padding: 1px 4px; font-size: 10px; background: white; color: #0f172a; }"
            "QComboBox QAbstractItemView { background: #1e293b; color: #ffffff; }"
        )

        # Satır 1: Döviz / Kur / KDV
        row1 = QHBoxLayout()
        row1.setSpacing(2)
        lbl_dov = QLabel("Döviz/Kur:")
        lbl_dov.setStyleSheet(lbl_style)
        lbl_dov.setFixedWidth(65)

        self.cmb_doviz = QComboBox()
        self.cmb_doviz.addItems(["TRY (₺)", "USD ($)", "EUR (€)", "GBP (£)"])
        self.cmb_doviz.setMaximumWidth(70)
        self.cmb_doviz.setFixedHeight(field_h)
        self.cmb_doviz.setStyleSheet(combo_style + " font-weight: bold;")
        self.cmb_doviz.currentIndexChanged.connect(self.calculate_totals)

        self.txt_doviz_kuru = QLineEdit("1.0000")
        self.txt_doviz_kuru.setMaximumWidth(52)
        self.txt_doviz_kuru.setFixedHeight(field_h)
        self.txt_doviz_kuru.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.txt_doviz_kuru.setStyleSheet(combo_style + " font-weight: bold;")
        self.txt_doviz_kuru.textChanged.connect(self.calculate_totals)

        self.cmb_kdv_durumu = QComboBox()
        self.cmb_kdv_durumu.addItems(["KDV Hariç", "KDV Dahil"])
        self.cmb_kdv_durumu.setFixedHeight(field_h)
        self.cmb_kdv_durumu.setStyleSheet(combo_style)
        self.cmb_kdv_durumu.currentIndexChanged.connect(self.calculate_totals)

        row1.addWidget(lbl_dov)
        row1.addWidget(self.cmb_doviz)
        row1.addWidget(self.txt_doviz_kuru)
        row1.addWidget(self.cmb_kdv_durumu, 1)
        lyt.addLayout(row1)

        # Satır 2: Şekil / Kasa
        row2 = QHBoxLayout()
        row2.setSpacing(2)
        lbl_sek = QLabel("Şekil/Kasa:")
        lbl_sek.setStyleSheet(lbl_style)
        lbl_sek.setFixedWidth(65)

        self.cmb_fatura_sekli = QComboBox()
        self.cmb_fatura_sekli.addItems(["Kapalı (Nakit)", "Açık - Vadeli", "Kredi Kartı"])
        self.cmb_fatura_sekli.setFixedHeight(field_h)
        self.cmb_fatura_sekli.setStyleSheet(combo_style)

        self.cmb_kasa = QComboBox()
        self.cmb_kasa.addItems([
            "K01 - Satış Kasası",
            "B01 - Garanti Ticari",
            "B02 - Akbank Ticari",
            "K02 - Merkez Kasa",
        ])
        self.cmb_kasa.setFixedHeight(field_h)
        self.cmb_kasa.setStyleSheet(combo_style)

        row2.addWidget(lbl_sek)
        row2.addWidget(self.cmb_fatura_sekli, 1)
        row2.addWidget(self.cmb_kasa, 1)
        lyt.addLayout(row2)

        # Satır 3: İşlemler
        row3 = QHBoxLayout()
        row3.setSpacing(6)
        lbl_isl = QLabel("İşlemler:")
        lbl_isl.setStyleSheet(lbl_style)
        lbl_isl.setFixedWidth(65)

        self.chk_cari_islesin = QCheckBox("✓ Cari")
        self.chk_cari_islesin.setChecked(True)
        self.chk_cari_islesin.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 10px;")
        self.chk_cari = self.chk_cari_islesin  # alias

        self.chk_stok_islesin = QCheckBox("✓ Stok")
        self.chk_stok_islesin.setChecked(True)
        self.chk_stok_islesin.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 10px;")
        self.chk_stok = self.chk_stok_islesin  # alias

        row3.addWidget(lbl_isl)
        row3.addWidget(self.chk_cari_islesin)
        row3.addWidget(self.chk_stok_islesin)
        row3.addStretch()
        lyt.addLayout(row3)

        return frame

    def build_iskonto_tab(self) -> QWidget:
        """7a. İndirim & Masraflar Sekmesi."""
        tab = QWidget()
        tab_lyt = QVBoxLayout(tab)
        tab_lyt.setContentsMargins(0, 0, 0, 0)
        tab_lyt.setSpacing(0)

        self.table_alt_iskonto = QTableWidget(0, len(self.ALT_ISKONTO_COLUMNS))
        self.table_alt_iskonto.setHorizontalHeaderLabels(self.ALT_ISKONTO_COLUMNS)
        self.table_alt_iskonto.setShowGrid(True)
        self.table_alt_iskonto.setAlternatingRowColors(True)
        self.table_alt_iskonto.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )

        hhdr = self.table_alt_iskonto.horizontalHeader()
        hhdr.setFixedHeight(22)
        hhdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hhdr.setStretchLastSection(True)

        theme_mgr = ThemeManager()
        row_h = theme_mgr.row_height
        vhdr = self.table_alt_iskonto.verticalHeader()
        vhdr.setDefaultSectionSize(row_h)

        self.table_alt_iskonto.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_alt_iskonto.customContextMenuRequested.connect(
            self.show_alt_iskonto_context_menu,
        )

        tab_lyt.addWidget(self.table_alt_iskonto)
        return tab

    def setup_keyboard_shortcuts(self) -> None:
        """Kısayolları dinamik olarak bağlar."""
        self._shortcuts = {}
        for action, key in self.SHORTCUTS.items():
            sc = QShortcut(QKeySequence(key), self)
            self._shortcuts[action] = sc

        if "satir_ekle" in self._shortcuts:
            self._shortcuts["satir_ekle"].activated.connect(
                lambda: self.add_item_row(item_type="Malzeme"),
            )
        if "satir_sil" in self._shortcuts:
            self._shortcuts["satir_sil"].activated.connect(
                lambda: self.remove_item_row(self.table_items.currentRow()),
            )
        if "yukari_tas" in self._shortcuts:
            self._shortcuts["yukari_tas"].activated.connect(self.move_row_up)
        if "asagi_tas" in self._shortcuts:
            self._shortcuts["asagi_tas"].activated.connect(self.move_row_down)
        if "stok_ara" in self._shortcuts:
            self._shortcuts["stok_ara"].activated.connect(
                lambda: self.open_stock_lookup_for_row(
                    self.table_items.currentRow()
                    if self.table_items.currentRow() >= 0
                    else 0,
                ),
            )

        # F2: Kaydet
        sc_f2 = QShortcut(QKeySequence("F2"), self)
        sc_f2.activated.connect(self.save_document)
        self._shortcuts["f2_save"] = sc_f2

        # F9: Kaydet & Yazdır
        sc_f9 = QShortcut(QKeySequence("F9"), self)
        sc_f9.activated.connect(self.save_and_print_document)
        self._shortcuts["f9_print"] = sc_f9

        # F6: Alt Panel Toggle
        sc_f6 = QShortcut(QKeySequence("F6"), self)
        sc_f6.activated.connect(self.toggle_bottom_panel)
        self._shortcuts["f6_toggle"] = sc_f6

        # F7: Üst Panel Toggle
        sc_f7 = QShortcut(QKeySequence("F7"), self)
        sc_f7.activated.connect(self.toggle_info_panel)
        self._shortcuts["f7_toggle"] = sc_f7

        # Alt+Enter / Alt+Return: Yeni Satır Ekle
        sc_alt_enter = QShortcut(QKeySequence("Alt+Return"), self)
        sc_alt_enter.activated.connect(lambda: self.add_item_row(item_type="Malzeme"))
        self._shortcuts["alt_enter_add"] = sc_alt_enter

        sc_alt_enter2 = QShortcut(QKeySequence("Alt+Enter"), self)
        sc_alt_enter2.activated.connect(lambda: self.add_item_row(item_type="Malzeme"))
        self._shortcuts["alt_enter2_add"] = sc_alt_enter2

        # Ctrl+E: Satır Ekle
        sc_ctrle = QShortcut(QKeySequence("Ctrl+E"), self)
        sc_ctrle.activated.connect(lambda: self.add_item_row(item_type="Malzeme"))
        self._shortcuts["satir_ekle_ctrle"] = sc_ctrle

        # Ctrl+Delete: Seçili Satır(ları) Sil
        sc_ctrl_del = QShortcut(QKeySequence("Ctrl+Delete"), self)
        sc_ctrl_del.activated.connect(self.delete_selected_rows)
        self._shortcuts["ctrl_del_delete"] = sc_ctrl_del

    def add_item_row(
        self,
        item_type="Malzeme",
        barcode="",
        code="",
        name="",
        note2="",
        qty=1.0,
        unit="Adet",
        price=0.00,
        currency="TRY",
        vat=20,
        disc1=0.0,
        disc2=0.0,
        disc3=0.0,
        insert_index=None,
    ) -> None:
        """Grid tablosuna yeni kalem satırı ekler ve tüm widget yüksekliklerini eşitler."""
        row = self.table_items.rowCount() if insert_index is None else insert_index
        self.table_items.insertRow(row)

        theme_mgr = ThemeManager()
        row_h = theme_mgr.row_height
        self.table_items.setRowHeight(row, row_h)
        widget_h = max(18, row_h - 2)

        cell_style = (
            "background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; "
            "border-radius: 3px; padding: 1px 4px; font-size: 10px;"
        )

        combo_cell_style = """
            QComboBox {
                background: #ffffff; color: #0f172a;
                border: 1px solid #cbd5e1; border-radius: 3px;
                padding: 1px 4px; font-size: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: #ffffff;
                border: 1px solid #475569;
                selection-background-color: #2563eb;
                selection-color: #ffffff;
                padding: 2px 0px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 20px;
                padding: 2px 6px;
                background-color: #1e293b;
                color: #ffffff;
            }
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
        """

        # 0. Sil Butonu (🗑️)
        btn_del = QPushButton("🗑️")
        btn_del.setToolTip("Satırı Sil")
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setFixedHeight(widget_h)
        btn_del.setStyleSheet(
            "background: transparent; color: #ef4444; border: none; "
            "font-weight: bold; font-size: 11px; padding: 0px;",
        )
        btn_del.clicked.connect(
            lambda _, r=row: self.remove_item_row(
                self.table_items.currentRow()
                if self.table_items.currentRow() >= 0
                else r,
            ),
        )

        # 1. Türü (Malzeme / Hizmet / Serbest Giriş)
        cmb_tur = QComboBox()
        cmb_tur.addItems(["Malzeme", "Hizmet", "Serbest Giriş"])
        cmb_tur.setCurrentText(item_type)
        cmb_tur.setFixedHeight(widget_h)
        cmb_tur.setStyleSheet(combo_cell_style)

        # 2. Barkod
        txt_barcode = QLineEdit(barcode)
        txt_barcode.setFixedHeight(widget_h)
        txt_barcode.setStyleSheet(cell_style)

        # 3. Stok / Hizmet Kodu
        code_widget = QWidget()
        code_widget.setFixedHeight(row_h)
        code_widget.setStyleSheet("background: transparent;")
        code_lyt = QHBoxLayout(code_widget)
        code_lyt.setContentsMargins(0, 0, 0, 0)
        code_lyt.setSpacing(2)
        txt_code = QLineEdit(code)
        txt_code.setFixedHeight(widget_h)
        txt_code.setStyleSheet(cell_style + " font-weight: bold;")

        prod_codes = [p["code"] for p in self.products_catalog]
        code_completer = QCompleter(prod_codes, self)
        code_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        code_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        code_completer.activated.connect(
            lambda sel_code, r=row: self.on_inline_code_selected(r, sel_code),
        )
        txt_code.setCompleter(code_completer)

        btn_code_search = QPushButton("...")
        btn_code_search.setFixedWidth(20)
        btn_code_search.setFixedHeight(widget_h)
        btn_code_search.setStyleSheet(
            "background: #e2e8f0; color: #1e293b; font-weight: bold; "
            "border: 1px solid #cbd5e1; border-radius: 2px; padding: 0px;",
        )
        btn_code_search.clicked.connect(
            lambda _, r=row: self.open_stock_lookup_for_row(r),
        )
        code_lyt.addWidget(txt_code)
        code_lyt.addWidget(btn_code_search)

        # 4. Açıklama / Ürün Adı (Direkt QLineEdit — Sarmalayıcı Yok)
        txt_name = QLineEdit(name)
        txt_name.setFixedHeight(widget_h)
        txt_name.setStyleSheet(cell_style + " font-weight: 600;")
        prod_names = [p["name"] for p in self.products_catalog]
        name_completer = QCompleter(prod_names, self)
        name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        name_completer.activated.connect(
            lambda selected_name, r=row: self.on_inline_name_selected(r, selected_name),
        )
        txt_name.setCompleter(name_completer)
        txt_name.textChanged.connect(self.calculate_totals)

        # 5. Satır Notu 2
        txt_note2 = QLineEdit(note2)
        txt_note2.setPlaceholderText("Not 2...")
        txt_note2.setFixedHeight(widget_h)
        txt_note2.setStyleSheet(cell_style)

        # 6. Miktar
        txt_qty = QLineEdit(str(qty))
        txt_qty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_qty.setFixedHeight(widget_h)
        txt_qty.setStyleSheet(cell_style + " font-weight: bold;")
        txt_qty.textChanged.connect(self.calculate_totals)

        # 7. Birim
        txt_unit = QLineEdit(unit)
        txt_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_unit.setFixedHeight(widget_h)
        txt_unit.setStyleSheet(cell_style)

        # 8. Birim Fiyat
        txt_price = QLineEdit(f"{price:.2f}")
        txt_price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        txt_price.setFixedHeight(widget_h)
        txt_price.setStyleSheet(cell_style + " font-weight: bold;")
        txt_price.textChanged.connect(self.calculate_totals)

        # 9. Satır Dövizi
        cmb_cur = QComboBox()
        cmb_cur.addItems(["TRY", "USD", "EUR", "GBP"])
        cmb_cur.setCurrentText(currency)
        cmb_cur.setFixedHeight(widget_h)
        cmb_cur.setStyleSheet(combo_cell_style)
        cmb_cur.currentIndexChanged.connect(self.calculate_totals)

        # 10. İskonto 1 %
        txt_disc1 = QLineEdit(str(disc1))
        txt_disc1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_disc1.setFixedHeight(widget_h)
        txt_disc1.setStyleSheet(cell_style)
        txt_disc1.textChanged.connect(self.calculate_totals)

        # 11. İskonto 1 Tutar
        lbl_disc1_amt = QLabel("0,00")
        lbl_disc1_amt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_disc1_amt.setFixedHeight(widget_h)
        lbl_disc1_amt.setStyleSheet("color: #dc2626; font-weight: bold; font-size: 10px;")

        # 12. İskonto 2 %
        txt_disc2 = QLineEdit(str(disc2))
        txt_disc2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_disc2.setFixedHeight(widget_h)
        txt_disc2.setStyleSheet(cell_style)
        txt_disc2.textChanged.connect(self.calculate_totals)

        # 13. İskonto 2 Tutar
        lbl_disc2_amt = QLabel("0,00")
        lbl_disc2_amt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_disc2_amt.setFixedHeight(widget_h)
        lbl_disc2_amt.setStyleSheet("color: #dc2626; font-weight: bold; font-size: 10px;")

        # 14. İskonto 3 %
        txt_disc3 = QLineEdit(str(disc3))
        txt_disc3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_disc3.setFixedHeight(widget_h)
        txt_disc3.setStyleSheet(cell_style)
        txt_disc3.textChanged.connect(self.calculate_totals)

        # 15. İskonto 3 Tutar
        lbl_disc3_amt = QLabel("0,00")
        lbl_disc3_amt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_disc3_amt.setFixedHeight(widget_h)
        lbl_disc3_amt.setStyleSheet("color: #dc2626; font-weight: bold; font-size: 10px;")

        # 16. KDV %
        cmb_vat = QComboBox()
        cmb_vat.addItems(["% 20", "% 10", "% 1", "% 0"])
        cmb_vat.setCurrentText(f"% {vat}")
        cmb_vat.setFixedHeight(widget_h)
        cmb_vat.setStyleSheet(combo_cell_style)
        cmb_vat.currentIndexChanged.connect(self.calculate_totals)

        # 17. KDV Tevkifatı
        cmb_tevkifat = QComboBox()
        cmb_tevkifat.addItems(["Yok", "2/10", "3/10", "4/10", "5/10", "7/10", "9/10", "10/10"])
        cmb_tevkifat.setCurrentText("Yok")
        cmb_tevkifat.setFixedHeight(widget_h)
        cmb_tevkifat.setStyleSheet(combo_cell_style)
        cmb_tevkifat.currentIndexChanged.connect(self.calculate_totals)

        # 18. Satır Tutarı
        lbl_tot = QLabel("0,00 ₺")
        lbl_tot.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_tot.setFixedHeight(widget_h)
        lbl_tot.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px;")

        txt_price.returnPressed.connect(lambda: self.add_item_row(item_type="Malzeme"))

        self.table_items.setCellWidget(row, 0, btn_del)
        self.table_items.setCellWidget(row, 1, cmb_tur)
        self.table_items.setCellWidget(row, 2, txt_barcode)
        self.table_items.setCellWidget(row, 3, code_widget)
        self.table_items.setCellWidget(row, 4, txt_name)
        self.table_items.setCellWidget(row, 5, txt_note2)
        self.table_items.setCellWidget(row, 6, txt_qty)
        self.table_items.setCellWidget(row, 7, txt_unit)
        self.table_items.setCellWidget(row, 8, txt_price)
        self.table_items.setCellWidget(row, 9, cmb_cur)
        self.table_items.setCellWidget(row, 10, txt_disc1)
        self.table_items.setCellWidget(row, 11, lbl_disc1_amt)
        self.table_items.setCellWidget(row, 12, txt_disc2)
        self.table_items.setCellWidget(row, 13, lbl_disc2_amt)
        self.table_items.setCellWidget(row, 14, txt_disc3)
        self.table_items.setCellWidget(row, 15, lbl_disc3_amt)
        self.table_items.setCellWidget(row, 16, cmb_vat)
        self.table_items.setCellWidget(row, 17, cmb_tevkifat)
        self.table_items.setCellWidget(row, 18, lbl_tot)

        cmb_tur.currentTextChanged.connect(
            lambda new_tur, r=row: self.on_item_type_changed(r, new_tur),
        )

        self.calculate_totals()

    def remove_item_row(self, row: int) -> None:
        """Satırı sil — en az 1 satır kalmalı."""
        if self.table_items.rowCount() <= 1:
            # Son satırı silme, sadece temizle
            if 0 <= row < self.table_items.rowCount():
                self.set_row_data(
                    row,
                    {
                        "item_type": "Malzeme",
                        "barcode": "",
                        "code": "",
                        "name": "",
                        "note2": "",
                        "qty": 1.0,
                        "unit": "Adet",
                        "price": 0.0,
                        "currency": "TRY",
                        "disc1": 0.0,
                        "disc2": 0.0,
                        "disc3": 0.0,
                        "vat": 20,
                        "tevkifat": "Yok",
                    },
                )
            self.calculate_totals()
            return

        if 0 <= row < self.table_items.rowCount():
            self.table_items.removeRow(row)
            self.calculate_totals()

    def get_row_data(self, row: int) -> dict:
        """Satırdaki tüm hücre verilerini sözlük olarak döndürür."""
        data = {
            "item_type": "Malzeme",
            "barcode": "",
            "code": "",
            "name": "",
            "note2": "",
            "qty": 1.0,
            "unit": "Adet",
            "price": 0.0,
            "currency": "TRY",
            "disc1": 0.0,
            "disc2": 0.0,
            "disc3": 0.0,
            "vat": 20,
            "tevkifat": "Yok",
        }
        cmb_tur = self.table_items.cellWidget(row, 1)
        if isinstance(cmb_tur, QComboBox):
            data["item_type"] = cmb_tur.currentText()

        txt_barcode = self.table_items.cellWidget(row, 2)
        if isinstance(txt_barcode, QLineEdit):
            data["barcode"] = txt_barcode.text()

        code_w = self.table_items.cellWidget(row, 3)
        if code_w:
            txt_code = code_w.findChild(QLineEdit)
            if txt_code:
                data["code"] = txt_code.text()

        txt_name = self.table_items.cellWidget(row, 4)
        if isinstance(txt_name, QLineEdit):
            data["name"] = txt_name.text()

        txt_note2 = self.table_items.cellWidget(row, 5)
        if isinstance(txt_note2, QLineEdit):
            data["note2"] = txt_note2.text()

        txt_qty = self.table_items.cellWidget(row, 6)
        if isinstance(txt_qty, QLineEdit):
            try:
                data["qty"] = float(txt_qty.text().replace(",", "."))
            except Exception:
                data["qty"] = 1.0

        txt_unit = self.table_items.cellWidget(row, 7)
        if isinstance(txt_unit, QLineEdit):
            data["unit"] = txt_unit.text()

        txt_price = self.table_items.cellWidget(row, 8)
        if isinstance(txt_price, QLineEdit):
            try:
                data["price"] = float(txt_price.text().replace(",", "."))
            except Exception:
                data["price"] = 0.0

        cmb_cur = self.table_items.cellWidget(row, 9)
        if isinstance(cmb_cur, QComboBox):
            data["currency"] = cmb_cur.currentText()

        txt_d1 = self.table_items.cellWidget(row, 10)
        if isinstance(txt_d1, QLineEdit):
            try:
                data["disc1"] = float(txt_d1.text().replace(",", "."))
            except Exception:
                data["disc1"] = 0.0

        txt_d2 = self.table_items.cellWidget(row, 12)
        if isinstance(txt_d2, QLineEdit):
            try:
                data["disc2"] = float(txt_d2.text().replace(",", "."))
            except Exception:
                data["disc2"] = 0.0

        txt_d3 = self.table_items.cellWidget(row, 14)
        if isinstance(txt_d3, QLineEdit):
            try:
                data["disc3"] = float(txt_d3.text().replace(",", "."))
            except Exception:
                data["disc3"] = 0.0

        cmb_vat = self.table_items.cellWidget(row, 16)
        if isinstance(cmb_vat, QComboBox):
            vat_txt = cmb_vat.currentText().replace("%", "").strip()
            try:
                data["vat"] = int(vat_txt)
            except Exception:
                data["vat"] = 20

        cmb_tev = self.table_items.cellWidget(row, 17)
        if isinstance(cmb_tev, QComboBox):
            data["tevkifat"] = cmb_tev.currentText()

        return data

    def set_row_data(self, row: int, data: dict) -> None:
        if row < 0 or row >= self.table_items.rowCount():
            return
        cmb_tur = self.table_items.cellWidget(row, 1)
        if isinstance(cmb_tur, QComboBox) and "item_type" in data:
            cmb_tur.setCurrentText(str(data["item_type"]))

        txt_barcode = self.table_items.cellWidget(row, 2)
        if isinstance(txt_barcode, QLineEdit) and "barcode" in data:
            txt_barcode.setText(str(data["barcode"]))

        code_w = self.table_items.cellWidget(row, 3)
        if code_w and "code" in data:
            txt_code = code_w.findChild(QLineEdit)
            if txt_code:
                txt_code.setText(str(data["code"]))

        txt_name = self.table_items.cellWidget(row, 4)
        if isinstance(txt_name, QLineEdit) and "name" in data:
            txt_name.setText(str(data["name"]))

        txt_note2 = self.table_items.cellWidget(row, 5)
        if isinstance(txt_note2, QLineEdit) and "note2" in data:
            txt_note2.setText(str(data["note2"]))

        txt_qty = self.table_items.cellWidget(row, 6)
        if isinstance(txt_qty, QLineEdit) and "qty" in data:
            txt_qty.setText(str(data["qty"]))

        txt_unit = self.table_items.cellWidget(row, 7)
        if isinstance(txt_unit, QLineEdit) and "unit" in data:
            txt_unit.setText(str(data["unit"]))

        txt_price = self.table_items.cellWidget(row, 8)
        if isinstance(txt_price, QLineEdit) and "price" in data:
            txt_price.setText(f"{float(data['price']):.2f}")

        cmb_cur = self.table_items.cellWidget(row, 9)
        if isinstance(cmb_cur, QComboBox) and "currency" in data:
            cmb_cur.setCurrentText(str(data["currency"]))

        txt_d1 = self.table_items.cellWidget(row, 10)
        if isinstance(txt_d1, QLineEdit) and "disc1" in data:
            txt_d1.setText(str(data["disc1"]))

        txt_d2 = self.table_items.cellWidget(row, 12)
        if isinstance(txt_d2, QLineEdit) and "disc2" in data:
            txt_d2.setText(str(data["disc2"]))

        txt_d3 = self.table_items.cellWidget(row, 14)
        if isinstance(txt_d3, QLineEdit) and "disc3" in data:
            txt_d3.setText(str(data["disc3"]))

        cmb_vat = self.table_items.cellWidget(row, 16)
        if isinstance(cmb_vat, QComboBox) and "vat" in data:
            cmb_vat.setCurrentText(f"% {data['vat']}")

        cmb_tev = self.table_items.cellWidget(row, 17)
        if isinstance(cmb_tev, QComboBox) and "tevkifat" in data:
            cmb_tev.setCurrentText(str(data["tevkifat"]))

        self.calculate_totals()

    def move_row_up(self, row: int | None = None) -> None:
        curr = self.table_items.currentRow() if row is None or isinstance(row, bool) else row
        if curr > 0:
            d_curr = self.get_row_data(curr)
            d_prev = self.get_row_data(curr - 1)
            self.set_row_data(curr, d_prev)
            self.set_row_data(curr - 1, d_curr)
            self.table_items.selectRow(curr - 1)

    def move_row_down(self, row: int | None = None) -> None:
        curr = self.table_items.currentRow() if row is None or isinstance(row, bool) else row
        if 0 <= curr < self.table_items.rowCount() - 1:
            d_curr = self.get_row_data(curr)
            d_next = self.get_row_data(curr + 1)
            self.set_row_data(curr, d_next)
            self.set_row_data(curr + 1, d_curr)
            self.table_items.selectRow(curr + 1)

    def delete_selected_rows(self) -> None:
        selected_rows = sorted(
            {idx.row() for idx in self.table_items.selectionModel().selectedRows()},
            reverse=True,
        )
        if not selected_rows:
            return
        for r in selected_rows:
            if self.table_items.rowCount() > 1:
                self.table_items.removeRow(r)
            else:
                self.remove_item_row(r)
        self.calculate_totals()

    def calculate_totals(self) -> None:
        """Tüm satır tutarlarını, KDV, tevkifat ve genel toplamları hesaplar."""
        if not hasattr(self, "lbl_subtotal") or not hasattr(self, "lbl_grand_total"):
            return
        subtotal = 0.0
        line_disc_total = 0.0
        vat_total = 0.0
        withholding_total = 0.0
        grand_total = 0.0

        is_kdv_dahil = self.cmb_kdv_durumu.currentText() == "KDV Dahil"
        try:
            kur = float(self.txt_doviz_kuru.text().replace(",", "."))
            if kur <= 0:
                kur = 1.0
        except Exception:
            kur = 1.0

        doviz_sym = "$" if "USD" in self.cmb_doviz.currentText() else (
            "€" if "EUR" in self.cmb_doviz.currentText() else "£"
        )

        def parse_num(w) -> float:
            if not w:
                return 0.0
            t = w.text() if hasattr(w, "text") else (
                w.currentText() if hasattr(w, "currentText") else str(w)
            )
            t = re.sub(r"[^\d,\.-]", "", str(t)).strip()
            if not t:
                return 0.0
            try:
                if "." in t and "," in t:
                    if t.find(".") < t.find(","):
                        clean = t.replace(".", "").replace(",", ".")
                    else:
                        clean = t.replace(",", "")
                elif "," in t:
                    clean = t.replace(",", ".")
                else:
                    clean = t
                return float(clean)
            except Exception:
                return 0.0

        for r in range(self.table_items.rowCount()):
            try:
                qty_w = self.table_items.cellWidget(r, 6)
                price_w = self.table_items.cellWidget(r, 8)
                d1_w = self.table_items.cellWidget(r, 10)
                lbl_d1_amt = self.table_items.cellWidget(r, 11)
                d2_w = self.table_items.cellWidget(r, 12)
                lbl_d2_amt = self.table_items.cellWidget(r, 13)
                d3_w = self.table_items.cellWidget(r, 14)
                lbl_d3_amt = self.table_items.cellWidget(r, 15)
                vat_w = self.table_items.cellWidget(r, 16)
                tev_w = self.table_items.cellWidget(r, 17)
                lbl_tot = self.table_items.cellWidget(r, 18)

                qty = parse_num(qty_w)
                price = parse_num(price_w)
                d1 = parse_num(d1_w)
                d2 = parse_num(d2_w)
                d3 = parse_num(d3_w)
                vat_rate = parse_num(vat_w)

                base_amt = qty * price
                after_d1 = base_amt * (1.0 - (d1 / 100.0))
                amt_d1 = base_amt - after_d1

                after_d2 = after_d1 * (1.0 - (d2 / 100.0))
                amt_d2 = after_d1 - after_d2

                after_d3 = after_d2 * (1.0 - (d3 / 100.0))
                amt_d3 = after_d2 - after_d3

                item_disc_amt = amt_d1 + amt_d2 + amt_d3
                taxable = after_d3

                if lbl_d1_amt:
                    lbl_d1_amt.setText(f"{amt_d1:,.2f}")
                if lbl_d2_amt:
                    lbl_d2_amt.setText(f"{amt_d2:,.2f}")
                if lbl_d3_amt:
                    lbl_d3_amt.setText(f"{amt_d3:,.2f}")

                if is_kdv_dahil:
                    line_net = taxable / (1.0 + (vat_rate / 100.0))
                    line_vat = taxable - line_net
                    line_total = taxable
                else:
                    line_vat = taxable * (vat_rate / 100.0)
                    line_total = taxable + line_vat

                tev_txt = tev_w.currentText() if tev_w else "Yok"
                line_withholding = 0.0
                if "/" in tev_txt:
                    try:
                        pay, payda = map(float, tev_txt.split("/"))
                        line_withholding = line_vat * (pay / payda)
                    except Exception:
                        line_withholding = 0.0

                subtotal += base_amt
                line_disc_total += item_disc_amt
                vat_total += line_vat
                withholding_total += line_withholding
                grand_total += line_total - line_withholding

                if lbl_tot:
                    lbl_tot.setText(f"{line_total:,.2f} ₺")
            except Exception:
                pass

        doc_extra_disc = 0.0
        doc_extra_exp = 0.0

        for ar in range(self.table_alt_iskonto.rowCount()):
            try:
                cmb_tur = self.table_alt_iskonto.cellWidget(ar, 1)
                cmb_turu = self.table_alt_iskonto.cellWidget(ar, 2)
                txt_val = self.table_alt_iskonto.cellWidget(ar, 3)
                txt_alt_kur = self.table_alt_iskonto.cellWidget(ar, 5)
                lbl_net = self.table_alt_iskonto.cellWidget(ar, 7)

                tur_txt = cmb_tur.currentText() if cmb_tur else "İndirim"
                turu_txt = cmb_turu.currentText() if cmb_turu else "Toplamdan % Düş"
                val_num = parse_num(txt_val)
                alt_kur_num = parse_num(txt_alt_kur) or 1.0

                line_net_val = 0.0
                current_net_sub = max(0.0, subtotal - line_disc_total)

                if "%" in turu_txt:
                    if "G.Toplam" in turu_txt:
                        line_net_val = grand_total * (val_num / 100.0)
                    else:
                        line_net_val = current_net_sub * (val_num / 100.0)
                elif "Eşitle" in turu_txt:
                    if "G.Toplam" in turu_txt:
                        line_net_val = max(0.0, grand_total - (val_num * alt_kur_num))
                    else:
                        line_net_val = max(0.0, current_net_sub - (val_num * alt_kur_num))
                else:
                    line_net_val = val_num * alt_kur_num

                if lbl_net:
                    lbl_net.setText(f"{line_net_val:,.2f} ₺")

                if tur_txt == "İndirim":
                    doc_extra_disc += line_net_val
                else:
                    doc_extra_exp += line_net_val
            except Exception:
                pass

        total_discount = line_disc_total + doc_extra_disc
        net_total = subtotal - total_discount + doc_extra_exp
        special_tax = 0.0
        final_grand_total = net_total + vat_total - withholding_total

        self.lbl_subtotal.setText(f"{subtotal:,.2f} ₺")
        self.lbl_subtotal_doviz.setText(f"{subtotal / kur:,.2f} {doviz_sym}")

        self.lbl_expense_total.setText(f"+{doc_extra_exp:,.2f} ₺")
        self.lbl_expense_total_doviz.setText(f"+{doc_extra_exp / kur:,.2f} {doviz_sym}")

        self.lbl_discount.setText(f"-{total_discount:,.2f} ₺")
        self.lbl_discount_doviz.setText(f"-{total_discount / kur:,.2f} {doviz_sym}")

        self.lbl_net_total.setText(f"{net_total:,.2f} ₺")
        self.lbl_net_total_doviz.setText(f"{net_total / kur:,.2f} {doviz_sym}")

        self.lbl_special_tax.setText(f"+{special_tax:,.2f} ₺")
        self.lbl_special_tax_doviz.setText(f"+{special_tax / kur:,.2f} {doviz_sym}")

        self.lbl_vat_total.setText(f"+{vat_total:,.2f} ₺")
        self.lbl_vat_total_doviz.setText(f"+{vat_total / kur:,.2f} {doviz_sym}")

        self.lbl_withholding.setText(f"-{withholding_total:,.2f} ₺")
        self.lbl_withholding_doviz.setText(f"-{withholding_total / kur:,.2f} {doviz_sym}")

        self.lbl_grand_total.setText(f"{final_grand_total:,.2f} ₺")
        self.lbl_grand_total_doviz.setText(f"{final_grand_total / kur:,.2f} {doviz_sym}")

        self._update_right_panel_summary()

    def on_barcode_entered(self) -> None:
        code = self.txt_barcode_input.text().strip()
        if not code:
            return
        found = next((p for p in self.products_catalog if p.get("barcode") == code or p.get("code") == code), None)
        if found:
            self.add_item_row(
                item_type="Malzeme",
                code=found.get("code", ""),
                barcode=found.get("barcode", ""),
                name=found.get("name", ""),
                qty=1.0,
                unit=found.get("unit", "Adet"),
                price=float(found.get("price", 0.0)),
                vat=int(found.get("vat", 20)),
            )
            self.txt_barcode_input.clear()
        else:
            QMessageBox.warning(self, "Bulunamadı", f"'{code}' kodlu / barkodlu ürün katalogda bulunamadı.")

    def open_customer_lookup(self) -> None:
        dlg = CustomerQuickLookupDialog(self.customers_catalog, parent=self)
        if dlg.exec() and dlg.selected_customer:
            self.apply_customer_info(dlg.selected_customer)

    def apply_customer_info(self, c: dict) -> None:
        self.txt_cari_kodu.setText(c.get("code", ""))
        self.txt_cari_unvan.setText(c.get("name", ""))
        self.txt_vergi_daire.setText(c.get("tax_office", ""))
        self.txt_vergi_no.setText(c.get("tax_no", ""))
        self.txt_sevk_adres.setText(c.get("address", ""))

    def open_stock_lookup_for_row(self, row: int) -> None:
        dlg = StockQuickLookupDialog(self.products_catalog, parent=self)
        if dlg.exec() and dlg.selected_product:
            self.apply_product_to_row(row, dlg.selected_product)

    def apply_product_to_row(self, row: int, p: dict) -> None:
        code_w = self.table_items.cellWidget(row, 3)
        if code_w:
            txt_code = code_w.findChild(QLineEdit)
            if txt_code:
                txt_code.setText(p.get("code", ""))

        txt_barcode = self.table_items.cellWidget(row, 2)
        if isinstance(txt_barcode, QLineEdit):
            txt_barcode.setText(p.get("barcode", ""))

        txt_name = self.table_items.cellWidget(row, 4)
        if isinstance(txt_name, QLineEdit):
            txt_name.setText(p.get("name", ""))

        txt_unit = self.table_items.cellWidget(row, 7)
        if isinstance(txt_unit, QLineEdit):
            txt_unit.setText(p.get("unit", "Adet"))

        txt_price = self.table_items.cellWidget(row, 8)
        if isinstance(txt_price, QLineEdit):
            txt_price.setText(f"{float(p.get('price', 0.0)):.2f}")

        cmb_vat = self.table_items.cellWidget(row, 16)
        if isinstance(cmb_vat, QComboBox):
            cmb_vat.setCurrentText(f"% {p.get('vat', 20)}")

        self.calculate_totals()

    def show_items_body_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff; border: 1px solid #cbd5e1;
                font-size: 11px; padding: 2px;
            }
            QMenu::item { padding: 5px 20px 5px 10px; }
            QMenu::item:selected {
                background: #2563eb; color: #ffffff;
            }
            QMenu::separator { height: 1px; background: #e2e8f0; margin: 2px 0; }
        """)

        row = self.table_items.currentRow()
        col = self.table_items.currentColumn()

        # ── SATIR İŞLEMLERİ ──
        act_add = QAction("➕ Satır Ekle (Alt+Enter)", self)
        act_insert = QAction("➕ Araya Satır Ekle", self)
        act_del = QAction("🗑️ Satırı Sil", self)
        act_up = QAction("⬆️ Yukarı Taşı (Alt+↑)", self)
        act_down = QAction("⬇️ Aşağı Taşı (Alt+↓)", self)
        act_bulk = QAction("🗑️ Seçilenleri Sil (Ctrl+Del)", self)

        menu.addAction(act_add)
        menu.addAction(act_insert)

        # Silinemeyen son satır kontrolü
        can_delete = self.table_items.rowCount() > 1
        act_del.setEnabled(can_delete and row >= 0)
        selected_count = len(self.table_items.selectionModel().selectedRows())
        act_bulk.setEnabled(can_delete and selected_count > 1)

        menu.addAction(act_del)
        menu.addAction(act_bulk)
        menu.addSeparator()
        menu.addAction(act_up)
        menu.addAction(act_down)
        menu.addSeparator()

        # ── SÜTUN İŞLEMLERİ ──
        if col >= 0:
            col_name = self.COLUMN_NAMES[col] if col < len(self.COLUMN_NAMES) else ""

            # Sıralama
            act_sort_asc = QAction(f"🔼 '{col_name}' Artan Sırala", self)
            act_sort_desc = QAction(f"🔽 '{col_name}' Azalan Sırala", self)
            menu.addAction(act_sort_asc)
            menu.addAction(act_sort_desc)
            menu.addSeparator()

            # Sütun gizle
            act_hide = QAction(f"👁️ '{col_name}' Sütununu Gizle", self)
            menu.addAction(act_hide)

        # Gizli sütunları göster
        hidden_cols = [
            i for i in range(self.table_items.columnCount())
            if self.table_items.isColumnHidden(i)
        ]
        if hidden_cols:
            show_menu = menu.addMenu("👁️ Gizli Sütunları Göster")
            for hcol in hidden_cols:
                hname = self.COLUMN_NAMES[hcol] if hcol < len(self.COLUMN_NAMES) else str(hcol)
                act_show = QAction(hname, self)
                act_show.triggered.connect(
                    lambda _, c=hcol: self.table_items.setColumnHidden(c, False),
                )
                show_menu.addAction(act_show)

        menu.addSeparator()

        # ── PROFİL KAYDET ──
        act_save_profile = QAction("💾 Görünümü Kaydet", self)
        act_reset = QAction("↩️ Görünümü Sıfırla", self)
        menu.addAction(act_save_profile)
        menu.addAction(act_reset)

        # ── BAĞLANTILARI KUR ──
        act_add.triggered.connect(
            lambda: self.add_item_row(item_type="Malzeme"),
        )
        act_insert.triggered.connect(
            lambda: self.add_item_row(
                item_type="Malzeme",
                insert_index=max(0, row),
            ),
        )
        act_del.triggered.connect(
            lambda: self.remove_item_row(row) if can_delete else None,
        )
        act_bulk.triggered.connect(self.delete_selected_rows)
        act_up.triggered.connect(lambda: self.move_row_up(row))
        act_down.triggered.connect(lambda: self.move_row_down(row))

        if col >= 0:
            act_sort_asc.triggered.connect(
                lambda: self._sort_items_table(col, ascending=True),
            )
            act_sort_desc.triggered.connect(
                lambda: self._sort_items_table(col, ascending=False),
            )
            act_hide.triggered.connect(
                lambda: self.table_items.setColumnHidden(col, True),
            )

        act_save_profile.triggered.connect(self.save_current_profile)
        act_reset.triggered.connect(self._reset_column_widths)

        menu.exec(self.table_items.viewport().mapToGlobal(pos))

    def _sort_items_table(self, col: int, ascending: bool = True) -> None:
        """Kalem tablosunu belirtilen sütuna göre sırala."""
        row_count = self.table_items.rowCount()
        if row_count <= 1:
            return

        rows_data = []
        for r in range(row_count):
            rows_data.append(self.get_row_data(r))

        col_keys = {
            1: "item_type",
            2: "barcode",
            3: "code",
            4: "name",
            5: "note2",
            6: "qty",
            7: "unit",
            8: "price",
            9: "currency",
            10: "disc1",
            12: "disc2",
            14: "disc3",
            16: "vat",
            17: "tevkifat",
        }
        key = col_keys.get(col, "name")

        def sort_val(d):
            v = d.get(key, "")
            try:
                return float(str(v).replace(",", "."))
            except Exception:
                return str(v).lower()

        rows_data.sort(key=sort_val, reverse=not ascending)

        for r, row_data in enumerate(rows_data):
            self.set_row_data(r, row_data)

    def _reset_column_widths(self) -> None:
        """Sütun genişliklerini varsayılana döndür."""
        self.setup_default_column_widths()

    def show_alt_iskonto_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #ffffff; border: 1px solid #cbd5e1;
                font-size: 11px; padding: 2px;
            }
            QMenu::item { padding: 5px 20px 5px 10px; }
            QMenu::item:selected { background: #2563eb; color: #ffffff; }
            QMenu::separator { height: 1px; background: #e2e8f0; }
        """)

        row = self.table_alt_iskonto.currentRow()
        col = self.table_alt_iskonto.currentColumn()
        can_delete = self.table_alt_iskonto.rowCount() > 1

        act_add = QAction("➕ Satır Ekle", self)
        act_del = QAction("🗑️ Satırı Sil", self)
        act_del.setEnabled(can_delete and row >= 0)

        menu.addAction(act_add)
        menu.addAction(act_del)
        menu.addSeparator()

        # Sıralama (Değer sütununa göre)
        act_sort_asc = QAction("🔼 Değere Göre Artan", self)
        act_sort_desc = QAction("🔽 Değere Göre Azalan", self)
        menu.addAction(act_sort_asc)
        menu.addAction(act_sort_desc)
        menu.addSeparator()

        # Sütun gizle/göster
        if col >= 0:
            col_name = self.table_alt_iskonto.horizontalHeaderItem(col)
            col_name_str = col_name.text() if col_name else str(col)
            act_hide = QAction(f"👁️ '{col_name_str}' Gizle", self)
            menu.addAction(act_hide)
            act_hide.triggered.connect(
                lambda: self.table_alt_iskonto.setColumnHidden(col, True),
            )

        hidden = [
            i for i in range(self.table_alt_iskonto.columnCount())
            if self.table_alt_iskonto.isColumnHidden(i)
        ]
        if hidden:
            show_m = menu.addMenu("👁️ Gizlileri Göster")
            for hc in hidden:
                hi = self.table_alt_iskonto.horizontalHeaderItem(hc)
                hn = hi.text() if hi else str(hc)
                a = QAction(hn, self)
                a.triggered.connect(
                    lambda _, c=hc: self.table_alt_iskonto.setColumnHidden(c, False),
                )
                show_m.addAction(a)

        # Bağlantılar
        act_add.triggered.connect(self.add_alt_iskonto_row)
        act_del.triggered.connect(
            lambda: self.remove_alt_iskonto_row(row) if can_delete else None,
        )
        act_sort_asc.triggered.connect(
            lambda: self._sort_alt_iskonto(ascending=True),
        )
        act_sort_desc.triggered.connect(
            lambda: self._sort_alt_iskonto(ascending=False),
        )

        menu.exec(self.table_alt_iskonto.viewport().mapToGlobal(pos))

    def _sort_alt_iskonto(self, ascending: bool = True) -> None:
        """Alt iskonto tablosunu değere göre sırala."""
        row_count = self.table_alt_iskonto.rowCount()
        if row_count <= 1:
            return
        rows_data = []
        for r in range(row_count):
            cmb_tur = self.table_alt_iskonto.cellWidget(r, 1)
            cmb_turu = self.table_alt_iskonto.cellWidget(r, 2)
            txt_val = self.table_alt_iskonto.cellWidget(r, 3)
            cmb_cur = self.table_alt_iskonto.cellWidget(r, 4)
            txt_kur = self.table_alt_iskonto.cellWidget(r, 5)
            cmb_vat = self.table_alt_iskonto.cellWidget(r, 6)
            txt_note = self.table_alt_iskonto.cellWidget(r, 8)
            chk_mal = self.table_alt_iskonto.cellWidget(r, 9)

            tur_val = cmb_tur.currentText() if isinstance(cmb_tur, QComboBox) else "İndirim"
            turu_val = cmb_turu.currentText() if isinstance(cmb_turu, QComboBox) else "Toplamdan % Düş"
            try:
                v_num = float(txt_val.text().replace(",", ".")) if isinstance(txt_val, QLineEdit) else 0.0
            except Exception:
                v_num = 0.0
            cur_val = cmb_cur.currentText() if isinstance(cmb_cur, QComboBox) else "TRY"
            try:
                kur_num = float(txt_kur.text().replace(",", ".")) if isinstance(txt_kur, QLineEdit) else 1.0
            except Exception:
                kur_num = 1.0
            try:
                vat_str = cmb_vat.currentText().replace("%", "").strip() if isinstance(cmb_vat, QComboBox) else "20"
                vat_num = int(vat_str)
            except Exception:
                vat_num = 20
            note_val = txt_note.text() if isinstance(txt_note, QLineEdit) else ""
            mal_val = chk_mal.isChecked() if isinstance(chk_mal, QCheckBox) else True

            rows_data.append({
                "tur": tur_val,
                "turu": turu_val,
                "val": v_num,
                "currency": cur_val,
                "kur": kur_num,
                "vat": vat_num,
                "note": note_val,
                "maliyet_etkilesin": mal_val,
            })

        rows_data.sort(key=lambda x: x["val"], reverse=not ascending)

        self.table_alt_iskonto.setRowCount(0)
        for d in rows_data:
            self.add_alt_iskonto_row(
                tur=d["tur"],
                turu=d["turu"],
                val=d["val"],
                currency=d["currency"],
                kur=d["kur"],
                vat=d["vat"],
                note=d["note"],
                maliyet_etkilesin=d["maliyet_etkilesin"],
            )

    def remove_alt_iskonto_row(self, row: int) -> None:
        """İndirim satırını sil — en az 1 kalmalı."""
        if self.table_alt_iskonto.rowCount() <= 1:
            w_val = self.table_alt_iskonto.cellWidget(row, 3)
            if isinstance(w_val, QLineEdit):
                w_val.setText("0.00")
            self.calculate_totals()
            return
        if 0 <= row < self.table_alt_iskonto.rowCount():
            self.table_alt_iskonto.removeRow(row)
            self.calculate_totals()

    def add_alt_iskonto_row(
        self,
        tur="İndirim",
        turu="Toplamdan % Düş",
        val=5.0,
        currency="TRY",
        kur=1.0,
        vat=20,
        note="",
        maliyet_etkilesin=True,
    ) -> None:
        row = self.table_alt_iskonto.rowCount()
        self.table_alt_iskonto.insertRow(row)

        theme_mgr = ThemeManager()
        row_h = theme_mgr.row_height
        self.table_alt_iskonto.setRowHeight(row, row_h)
        widget_h = max(18, row_h - 2)

        cell_style = "background: white; border: 1px solid #cbd5e1; border-radius: 3px; font-size: 10px;"

        btn_del = QPushButton("🗑️")
        btn_del.setFixedHeight(widget_h)
        btn_del.setStyleSheet("background: transparent; border: none; color: #dc2626;")
        btn_del.clicked.connect(
            lambda: self.remove_alt_iskonto_row(self.table_alt_iskonto.currentRow()),
        )

        cmb_tur = QComboBox()
        cmb_tur.addItems(["İndirim", "Masraf"])
        cmb_tur.setCurrentText(tur)
        cmb_tur.setFixedHeight(widget_h)
        cmb_tur.setStyleSheet(cell_style)
        cmb_tur.currentIndexChanged.connect(self.calculate_totals)

        cmb_turu = QComboBox()
        cmb_turu.addItems(self.ISKONTO_TURLERI)
        cmb_turu.setCurrentText(turu)
        cmb_turu.setFixedHeight(widget_h)
        cmb_turu.setStyleSheet(cell_style)
        cmb_turu.currentIndexChanged.connect(self.calculate_totals)

        txt_val = QLineEdit(str(val))
        txt_val.setFixedHeight(widget_h)
        txt_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        txt_val.setStyleSheet(cell_style)
        txt_val.textChanged.connect(self.calculate_totals)

        cmb_cur = QComboBox()
        cmb_cur.addItems(["TRY", "USD", "EUR", "GBP"])
        cmb_cur.setCurrentText(currency)
        cmb_cur.setFixedHeight(widget_h)
        cmb_cur.setStyleSheet(cell_style)
        cmb_cur.currentIndexChanged.connect(self.calculate_totals)

        txt_kur = QLineEdit(f"{kur:.4f}")
        txt_kur.setFixedHeight(widget_h)
        txt_kur.setAlignment(Qt.AlignmentFlag.AlignRight)
        txt_kur.setStyleSheet(cell_style)
        txt_kur.textChanged.connect(self.calculate_totals)

        cmb_vat = QComboBox()
        cmb_vat.addItems(["% 20", "% 10", "% 1", "% 0"])
        cmb_vat.setCurrentText(f"% {vat}")
        cmb_vat.setFixedHeight(widget_h)
        cmb_vat.setStyleSheet(cell_style)
        cmb_vat.currentIndexChanged.connect(self.calculate_totals)

        lbl_tot = QLabel("0,00 ₺")
        lbl_tot.setFixedHeight(widget_h)
        lbl_tot.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_tot.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 10px;")

        txt_note = QLineEdit(note)
        txt_note.setFixedHeight(widget_h)
        txt_note.setStyleSheet(cell_style)

        chk_mal = QCheckBox()
        chk_mal.setChecked(maliyet_etkilesin)

        lbl_ilk = QLabel(str(val))
        lbl_ilk.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_form = QLabel("Formülsüz")
        lbl_form.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.table_alt_iskonto.setCellWidget(row, 0, btn_del)
        self.table_alt_iskonto.setCellWidget(row, 1, cmb_tur)
        self.table_alt_iskonto.setCellWidget(row, 2, cmb_turu)
        self.table_alt_iskonto.setCellWidget(row, 3, txt_val)
        self.table_alt_iskonto.setCellWidget(row, 4, cmb_cur)
        self.table_alt_iskonto.setCellWidget(row, 5, txt_kur)
        self.table_alt_iskonto.setCellWidget(row, 6, cmb_vat)
        self.table_alt_iskonto.setCellWidget(row, 7, lbl_tot)
        self.table_alt_iskonto.setCellWidget(row, 8, txt_note)
        self.table_alt_iskonto.setCellWidget(row, 9, chk_mal)
        self.table_alt_iskonto.setCellWidget(row, 10, lbl_ilk)
        self.table_alt_iskonto.setCellWidget(row, 11, lbl_form)

        self.calculate_totals()

    def open_notes_dialog(self) -> None:
        dlg = NoteEditDialog(self.doc_note1, self.doc_note2, parent=self)
        if dlg.exec():
            self.doc_note1, self.doc_note2 = dlg.get_notes()
            self.lbl_note_preview.setText(f"{self.doc_note1}\n{self.doc_note2}")

    def show_customer_balance(self) -> None:
        c_name = self.txt_cari_unvan.text().strip() or "TATU HIRDAVAT"
        dlg = CustomerBalanceDialog(c_name, "45.250,00 ₺ (Borçlu)", parent=self)
        dlg.exec()

    def setup_customer_completers(self) -> None:
        cust_codes = [c["code"] for c in self.customers_catalog]
        comp_kodu = QCompleter(cust_codes, self)
        comp_kodu.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_kodu.activated.connect(
            lambda code: self.apply_customer_info(next(c for c in self.customers_catalog if c["code"] == code)),
        )
        self.txt_cari_kodu.setCompleter(comp_kodu)

        cust_names = [c["name"] for c in self.customers_catalog]
        comp_unv = QCompleter(cust_names, self)
        comp_unv.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_unv.activated.connect(
            lambda name: self.apply_customer_info(next(c for c in self.customers_catalog if c["name"] == name)),
        )
        self.txt_cari_unvan.setCompleter(comp_unv)

    def setup_import_lines_menu(self) -> None:
        import_menu = QMenu(self)
        act_sip = import_menu.addAction("📦 Siparişten Kalemleri Aktar...")
        act_irs = import_menu.addAction("🚚 İrsaliyeden Kalemleri Aktar...")
        act_fat = import_menu.addAction("🧾 Faturadan Kalemleri Aktar...")
        import_menu.addSeparator()
        act_xls = import_menu.addAction("📊 Excel / CSV Dosyasından Aktar...")

        act_sip.triggered.connect(lambda: self.trigger_line_import("Sipariş"))
        act_irs.triggered.connect(lambda: self.trigger_line_import("İrsaliye"))
        act_fat.triggered.connect(lambda: self.trigger_line_import("Fatura"))
        act_xls.triggered.connect(lambda: self.trigger_line_import("Excel"))

        self.btn_import_lines.setMenu(import_menu)

    def trigger_line_import(self, source_type: str) -> None:
        if source_type == "Excel":
            fpath, _ = QFileDialog.getOpenFileName(
                self, "Excel Kalem Listesi Seç", "", "Excel Files (*.xlsx *.xls *.csv)",
            )
            if fpath:
                self.add_item_row(
                    item_type="Malzeme",
                    code="STK-002",
                    name="Excelden Aktarılan Kalem",
                    qty=10,
                    unit="Adet",
                    price=85.00,
                    vat=20,
                )
                QMessageBox.information(
                    self, "Aktarım Tamamlandı", f"{fpath} dosyasından kalemler evraka aktarıldı.",
                )
        else:
            self.add_item_row(
                item_type="Malzeme",
                code="STK-004",
                name=f"{source_type} Kaynaklı A4 Fotokopi Kağıdı 80gr",
                qty=5,
                unit="Paket",
                price=120.00,
                vat=20,
            )
            QMessageBox.information(
                self, "Aktarım Başarılı", f"Seçilen {source_type} belgesindeki kalemler aktarıldı.",
            )

    def load_sidebar_profiles(self) -> None:
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
        else:
            if "Varsayılan" not in profiles:
                self.combo_sidebar_profiles.addItem("Varsayılan")
            self.combo_sidebar_profiles.setCurrentText("Varsayılan")
        self.combo_sidebar_profiles.blockSignals(False)
        self.apply_current_profile_settings()

    def _on_sidebar_profile_changed(self, profile_name: str) -> None:
        if not profile_name:
            return
        self.profile_manager.set_active_profile_name(profile_name)
        self.apply_current_profile_settings()

    def apply_current_profile_settings(self) -> None:
        profile = self.profile_manager.get_active_profile()
        if not profile or not profile.column_settings:
            return
        indiv = profile.column_settings.individual_columns
        if not indiv:
            return
        hheader = self.table_items.horizontalHeader()
        for col_idx in range(self.table_items.columnCount()):
            key_idx = str(col_idx)
            header_name = self.COLUMN_NAMES[col_idx]
            field_name = self.headers_dict.get(col_idx, ("", ""))[1]
            col_info = (
                indiv.get(key_idx)
                or indiv.get(field_name)
                or indiv.get(header_name)
            )
            if col_info:
                self.table_items.setColumnHidden(col_idx, not col_info.visible)
                if col_info.width and col_info.width > 10:
                    if col_idx == 4:
                        hheader.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
                    self.table_items.setColumnWidth(col_idx, col_info.width)

    def save_current_profile(self) -> None:
        from src.desktop.models.profile_models import IndividualColumn

        active_name = (
            self.combo_sidebar_profiles.currentText()
            if hasattr(self, "combo_sidebar_profiles")
            else "Varsayılan"
        ) or "Varsayılan"

        profiles = self.profile_manager.load_profiles()
        profile = profiles.get(active_name)
        if not profile:
            profile = self.profile_manager.create_default_profile()
            profile.profile.name = active_name

        indiv = {}
        for col_idx in range(self.table_items.columnCount()):
            is_visible = not self.table_items.isColumnHidden(col_idx)
            w = self.table_items.columnWidth(col_idx)
            header_name = self.COLUMN_NAMES[col_idx]
            field_name = self.headers_dict.get(col_idx, ("", ""))[1]
            order = self.table_items.horizontalHeader().visualIndex(col_idx)
            col_obj = IndividualColumn(visible=is_visible, width=w, order=order)
            indiv[str(col_idx)] = col_obj
            if field_name:
                indiv[field_name] = col_obj
            if header_name:
                indiv[header_name] = col_obj

        profile.column_settings.individual_columns = indiv
        self.profile_manager.save_profile(profile)
        self.profile_manager.set_active_profile_name(active_name)
        QMessageBox.information(
            self,
            "Profil Kaydedildi",
            f"'{active_name}' görünüm profili ve sütun genişlikleri başarıyla kaydedildi.",
        )

    def open_column_manager(self) -> None:
        hidden_cols = {
            i for i in range(self.table_items.columnCount()) if self.table_items.isColumnHidden(i)
        }
        dlg = ColumnManagerDialog(
            all_columns=self.COLUMN_NAMES,
            hidden_columns=hidden_cols,
            parent=self,
        )
        if dlg.exec():
            cols = dlg.get_selected_columns()
            for i, col in enumerate(self.COLUMN_NAMES):
                self.table_items.setColumnHidden(i, col not in cols)

    def _on_table_selection_changed(self) -> None:
        has_sel = len(self.table_items.selectionModel().selectedRows()) > 0
        if hasattr(self, "btn_del_selected"):
            self.btn_del_selected.setEnabled(has_sel)

    def _on_theme_row_height_changed(self, new_h: int) -> None:
        for r in range(self.table_items.rowCount()):
            self.table_items.setRowHeight(r, new_h)

    def on_item_type_changed(self, row: int, new_tur: str) -> None:
        txt_name = self.table_items.cellWidget(row, 4)
        if isinstance(txt_name, QLineEdit):
            if new_tur == "Hizmet":
                txt_name.setPlaceholderText("Hizmet / Masraf Açıklaması...")
            elif new_tur == "Serbest Giriş":
                txt_name.setPlaceholderText("Serbest Kalem Tanımı...")
            else:
                txt_name.setPlaceholderText("Ürün / Malzeme Adı...")

    def on_inline_code_selected(self, row: int, code: str) -> None:
        p = next((x for x in self.products_catalog if x.get("code") == code), None)
        if p:
            self.apply_product_to_row(row, p)

    def on_inline_name_selected(self, row: int, name: str) -> None:
        p = next((x for x in self.products_catalog if x.get("name") == name), None)
        if p:
            self.apply_product_to_row(row, p)

    def on_vade_gun_changed(self, txt: str) -> None:
        match = re.search(r"\d+", txt)
        if match:
            days = int(match.group())
            self.date_vade.setDate(self.date_belge.date().addDays(days))

    def on_vade_formul_changed(self, txt: str) -> None:
        self.on_vade_gun_changed(txt)

    def on_odeme_plani_changed(self, idx: int) -> None:
        p = self.cmb_odeme_plani.currentData()
        if p and isinstance(p, dict):
            days = p.get("gun", 0)
            self.date_vade.setDate(self.date_belge.date().addDays(days))
            if p.get("tip") == "Nakit":
                self.cmb_fatura_sekli.setCurrentText("Kapalı (Nakit)")
            elif p.get("tip") == "Kredi Kartı":
                self.cmb_fatura_sekli.setCurrentText("Kredi Kartı")

    def on_row_reordered(self, logical_index: int, old_visual_index: int, new_visual_index: int) -> None:
        pass

    def on_doc_type_changed(self, idx: int) -> None:
        doc_name = self.cmb_doc_type.currentText()
        prefix = "TOY"
        if "TEKLİF" in doc_name:
            prefix = "TEK"
            self.chk_stok_islesin.setChecked(False)
            self.chk_cari_islesin.setChecked(False)
            self.cmb_efatura_scenario.setCurrentIndex(0)
        elif "SİPARİŞ" in doc_name:
            prefix = "SIP"
            self.chk_stok_islesin.setChecked(False)
            self.chk_cari_islesin.setChecked(False)
            self.cmb_efatura_scenario.setCurrentIndex(0)
        elif "İRSALİYE" in doc_name:
            prefix = "IRS"
            self.chk_stok_islesin.setChecked(True)
            self.chk_cari_islesin.setChecked(False)
            self.cmb_efatura_scenario.setCurrentIndex(7)
        else:
            prefix = "FTR"
            self.chk_stok_islesin.setChecked(True)
            self.chk_cari_islesin.setChecked(True)
            self.cmb_efatura_scenario.setCurrentIndex(1)

        self.txt_top_doc_no.setText(f"{prefix}2026-{datetime.now().strftime('%m%d%H%M')}")

    def save_document(self) -> None:
        from src.desktop.services.quotation_save_service import QuotationSaveService

        svc = QuotationSaveService(
            db_session=self.db,
            company_id=self.company_id,
        )
        result = svc.save_from_dialog(self)

        if result.success:
            self.doc_id = result.quotation_id
            self.document_saved.emit({
                "quotation_id": result.quotation_id,
                "quotation_number": result.quotation_number,
            })
            QMessageBox.information(
                self, "Kaydedildi",
                f"{result.quotation_number} başarıyla kaydedildi.",
            )
            self.accept()
        else:
            QMessageBox.critical(
                self, "Kayıt Hatası",
                f"Kayıt başarısız:\n{result.error}",
            )

    def save_and_new_document(self) -> None:
        from src.desktop.services.quotation_save_service import QuotationSaveService

        svc = QuotationSaveService(
            db_session=self.db,
            company_id=self.company_id,
        )
        result = svc.save_from_dialog(self)

        if result.success:
            self.document_saved.emit({
                "quotation_id": result.quotation_id,
                "quotation_number": result.quotation_number,
            })
            QMessageBox.information(
                self, "Kaydedildi",
                f"{result.quotation_number} başarıyla kaydedildi. Yeni evrak girişi hazırlanıyor...",
            )
            self.doc_id = None
            self.txt_top_doc_no.setText(f"FTR2026-{datetime.now().strftime('%m%d%H%M%S')}")
            self.table_items.setRowCount(0)
            self.add_item_row(
                item_type="Malzeme",
                code="STK-001",
                name="VGA Sinyal Uzatma Kablosu 5M",
                qty=1.0,
                unit="Metre",
                price=150.00,
                vat=20,
            )
        else:
            QMessageBox.critical(
                self, "Kayıt Hatası",
                f"Kayıt başarısız:\n{result.error}",
            )

    def _get_report_service(self) -> TeklifReportService:
        if not self._report_service:
            self._report_service = TeklifReportService(
                db_session=self.db,
                company_id=self.company_id,
            )
        return self._report_service

    def _calc_line_total(self, row_data: dict) -> float:
        try:
            qty = float(row_data.get("qty", 1) or 1)
            price = float(row_data.get("price", 0) or 0)
            d1 = float(row_data.get("disc1", 0) or 0)
            d2 = float(row_data.get("disc2", 0) or 0)
            d3 = float(row_data.get("disc3", 0) or 0)
            vat = float(row_data.get("vat", 20) or 20)
            base = qty * price
            after_d = base * (1 - d1 / 100) * (1 - d2 / 100) * (1 - d3 / 100)
            return round(after_d * (1 + vat / 100), 2)
        except Exception:
            return 0.0

    def _get_current_teklif_data(self) -> dict:
        firma = {
            "adi": "BAYNET BİLİŞİM TEKNOLOJİLERİ",
            "adres": "Ankara",
            "tel": "",
            "email": "",
            "web": "",
            "logo_base64": "",
        }

        musteri = {
            "adi": self.txt_cari_unvan.text().strip(),
            "vergi_daire": self.txt_vergi_daire.text().strip(),
            "vergi_no": self.txt_vergi_no.text().strip(),
            "adres": self.txt_sevk_adres.text().strip(),
            "tel": "",
            "email": "",
        }

        belge = {
            "teklif_no": self.txt_top_doc_no.text().strip(),
            "tarih": self.date_belge.date().toString("yyyy-MM-dd"),
            "vade": self.date_vade.date().toString("yyyy-MM-dd"),
            "para_birimi": self.cmb_doviz.currentText(),
            "durum": "Açık",
            "odeme_plani": self.cmb_odeme_plani.currentText(),
            "aciklama": "",
        }

        kalemler = []
        for r in range(self.table_items.rowCount()):
            row_data = self.get_row_data(r)
            if not row_data.get("name"):
                continue
            kalemler.append({
                "kod": row_data.get("code", ""),
                "aciklama": row_data.get("name", ""),
                "not2": row_data.get("note2", ""),
                "miktar": float(row_data.get("qty", 1)),
                "birim": row_data.get("unit", "Adet"),
                "birim_fiyat": float(row_data.get("price", 0)),
                "iskonto": float(row_data.get("disc1", 0)),
                "kdv": int(row_data.get("vat", 20)),
                "tutar": self._calc_line_total(row_data),
            })

        def parse_currency(lbl) -> float:
            try:
                txt = lbl.text().replace("₺", "").replace("$", "").replace("€", "")
                txt = txt.replace(".", "").replace(",", ".").replace("+", "").replace("-", "").strip()
                return float(txt)
            except Exception:
                return 0.0

        toplamlar = {
            "ara_toplam": parse_currency(self.lbl_subtotal),
            "iskonto": parse_currency(self.lbl_discount),
            "masraflar": parse_currency(self.lbl_expense_total),
            "kdv_matrahi": parse_currency(self.lbl_subtotal),
            "kdv_toplam": parse_currency(self.lbl_vat_total),
            "genel_toplam": parse_currency(self.lbl_grand_total),
        }

        notlar_str = f"{self.doc_note1}\n{self.doc_note2}"

        return {
            "firma": firma,
            "musteri": musteri,
            "belge": belge,
            "kalemler": kalemler,
            "toplamlar": toplamlar,
            "notlar": notlar_str,
        }

    def save_and_print_document(self) -> None:
        """Kaydeder ve PDF olarak yazdırıp açar."""
        from PyQt6.QtWidgets import QProgressDialog

        progress = QProgressDialog("PDF hazırlanıyor...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setWindowTitle("Yazdırılıyor")
        progress.show()

        try:
            data = self._get_current_teklif_data()
            service = self._get_report_service()
            pdf_bytes = service.pdf_engine.render_pdf("teklif/teklif_print.html", data)
            service.pdf_engine.open_pdf(pdf_bytes)
            progress.close()
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Hata", f"PDF oluşturulamadı:\n{e}")

    def export_to_excel(self) -> None:
        """Mevcut teklifi Excel olarak dışa aktarır."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Excel Kaydet",
            f"{self.txt_top_doc_no.text().replace('/', '-')}.xlsx",
            "Excel Dosyası (*.xlsx)",
        )
        if not path:
            return

        try:
            data = self._get_current_teklif_data()
            service = self._get_report_service()
            wb = service.excel_engine.render_teklif(data)
            service.excel_engine.save(wb, path)
            os.startfile(path)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Excel oluşturulamadı:\n{e}")

    def open_share_dialog(self) -> None:
        """Teklif paylaşım dialogunu açar."""
        data = self._get_current_teklif_data()
        teklif_no = data["belge"]["teklif_no"]
        musteri_adi = data["musteri"]["adi"]
        musteri_email = data["musteri"].get("email", "")

        dlg = QDialog(self)
        dlg.setWindowTitle(f"📤 Teklif Paylaş — {teklif_no}")
        dlg.setMinimumWidth(480)
        dlg.setStyleSheet("font-family:'Segoe UI'; background:white;")

        lyt = QVBoxLayout(dlg)
        lyt.setContentsMargins(20, 20, 20, 20)
        lyt.setSpacing(12)

        lbl_title = QLabel(f"📄 {teklif_no} — {musteri_adi}")
        lbl_title.setStyleSheet("font-size:13px; font-weight:700; color:#1e3a8a;")
        lyt.addWidget(lbl_title)

        lbl_email = QLabel("E-posta Adresi:")
        lbl_email.setStyleSheet("font-weight:600; color:#475569; font-size:11px;")
        txt_email = QLineEdit(musteri_email)
        txt_email.setPlaceholderText("musteri@example.com")
        txt_email.setFixedHeight(28)
        lyt.addWidget(lbl_email)
        lyt.addWidget(txt_email)

        def make_btn(text, color, hover):
            b = QPushButton(text)
            b.setFixedHeight(36)
            b.setStyleSheet(f"""
                QPushButton {{
                    background:{color}; color:white;
                    border:none; border-radius:6px;
                    font-size:12px; font-weight:600;
                }}
                QPushButton:hover {{ background:{hover}; }}
            """)
            return b

        btn_send = make_btn("📧 E-posta Gönder", "#2563eb", "#1d4ed8")
        btn_pdf = make_btn("🖨️ PDF İndir / Yazdır", "#475569", "#334155")
        btn_copy = make_btn("🔗 Linki Kopyala", "#7c3aed", "#6d28d9")
        btn_wa = make_btn("💬 WhatsApp ile Gönder", "#16a34a", "#15803d")
        btn_xls = make_btn("📊 Excel İndir", "#0284c7", "#0369a1")
        btn_close = make_btn("✖ Kapat", "#64748b", "#475569")

        def send_email():
            email = txt_email.text().strip()
            if not email:
                QMessageBox.warning(dlg, "Uyarı", "E-posta adresi girin.")
                return
            try:
                pdf_bytes = self._get_report_service().pdf_engine.render_pdf("teklif/teklif_print.html", data)
                ok, msg = self._get_report_service().email_engine.send_teklif_email(
                    to_email=email, teklif_data=data, pdf_bytes=pdf_bytes,
                )
                if ok:
                    QMessageBox.information(dlg, "Başarılı", msg)
                else:
                    QMessageBox.critical(dlg, "Hata", msg)
            except Exception as e:
                QMessageBox.critical(dlg, "Hata", str(e))

        def copy_link():
            fake_token = f"DEMO-{teklif_no.replace('/', '-')}"
            url = f"https://baynetbilisim.tr/teklif/view?token={fake_token}"
            self._get_report_service().share_engine.copy_to_clipboard(url)
            QMessageBox.information(dlg, "Kopyalandı", f"Link panoya kopyalandı:\n{url}")

        def share_wa():
            dlg.accept()
            self._get_report_service().share_engine.share_whatsapp(
                url="https://baynetbilisim.tr/teklif/view?token=DEMO",
                musteri_adi=musteri_adi,
                teklif_no=teklif_no,
                firma_adi=data["firma"]["adi"],
            )

        btn_send.clicked.connect(send_email)
        btn_pdf.clicked.connect(lambda: (self.save_and_print_document(), dlg.accept()))
        btn_copy.clicked.connect(copy_link)
        btn_wa.clicked.connect(share_wa)
        btn_xls.clicked.connect(lambda: (self.export_to_excel(), dlg.accept()))
        btn_close.clicked.connect(dlg.reject)

        for btn in [btn_send, btn_pdf, btn_copy, btn_wa, btn_xls]:
            lyt.addWidget(btn)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#e2e8f0;")
        lyt.addWidget(line)
        lyt.addWidget(btn_close)

        dlg.exec()

    def send_earciv(self) -> None:
        sc_name = self.cmb_efatura_scenario.currentText()
        QMessageBox.information(
            self,
            "e-Fatura Entegratörü",
            f"Seçilen Senaryo: {sc_name}\n\n"
            "GİB e-Fatura / e-Arşiv XML paketi üretildi ve entegratöre iletildi.",
        )

    def _share_whatsapp(self) -> None:
        """WhatsApp ile paylaş."""
        try:
            data = self._get_current_teklif_data()
            svc = self._get_report_service()
            svc.share_engine.share_whatsapp(
                url="https://baynetbilisim.tr/teklif/view?token=DEMO",
                musteri_adi=data["musteri"].get("adi", ""),
                teklif_no=data["belge"].get("teklif_no", ""),
                firma_adi=data["firma"].get("adi", ""),
            )
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def _send_email_quick(self) -> None:
        """E-posta gönder — önce adres sor."""
        from PyQt6.QtWidgets import QInputDialog

        addr, ok = QInputDialog.getText(
            self,
            "E-posta Gönder",
            "Alıcı e-posta adresi:",
            text="",
        )
        if not ok or not addr.strip():
            return
        try:
            data = self._get_current_teklif_data()
            pdf = self._get_report_service().pdf_engine.render_pdf(
                "teklif/teklif_print.html", data,
            )
            ok2, msg = self._get_report_service().email_engine.send_teklif_email(
                to_email=addr.strip(),
                teklif_data=data,
                pdf_bytes=pdf,
            )
            if ok2:
                QMessageBox.information(self, "Gönderildi", msg)
            else:
                QMessageBox.critical(self, "Hata", msg)
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def _copy_link(self) -> None:
        """Teklif linkini panoya kopyala."""
        try:
            data = self._get_current_teklif_data()
            teklif_no = data["belge"].get("teklif_no", "DEMO")
            url = f"https://baynetbilisim.tr/teklif/view?token={teklif_no}"
            self._get_report_service().share_engine.copy_to_clipboard(url)
            QMessageBox.information(self, "Kopyalandı", f"Link panoya kopyalandı:\n{url}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def _on_convert_clicked(self) -> None:
        """Siparişe dönüştür."""
        QMessageBox.information(
            self,
            "Siparişe Dönüştür",
            "Teklif kaydedildikten sonra siparişe dönüştürülebilir.",
        )

    def _on_duplicate_doc(self) -> None:
        """Belgeyi kopyala."""
        QMessageBox.information(
            self,
            "Kopyala",
            "Belge kopyalanıyor...",
        )

    def _update_right_panel_summary(self) -> None:
        """Sağ paneldeki özet bilgileri günceller."""
        if not hasattr(self, "lbl_right_teklif_no"):
            return
        try:
            no = self.txt_top_doc_no.text() if hasattr(self, "txt_top_doc_no") else "—"
            raw_musteri = self.txt_cari_unvan.text() if hasattr(self, "txt_cari_unvan") else ""
            musteri = (raw_musteri[:25] + "...") if len(raw_musteri) > 25 else raw_musteri
            toplam = self.lbl_grand_total.text() if hasattr(self, "lbl_grand_total") else "—"

            self.lbl_right_teklif_no.setText(f"📄 {no}")
            self.lbl_right_musteri.setText(f"👤 {musteri or '—'}")
            self.lbl_right_toplam.setText(f"💰 {toplam}")
        except Exception:
            pass


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dlg = TransactionDocumentDialog()
    dlg.show()
    sys.exit(app.exec())
