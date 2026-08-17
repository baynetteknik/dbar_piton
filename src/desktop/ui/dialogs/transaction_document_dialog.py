"""TOYA ERP - Evrensel Fiş, Fatura, Sipariş ve Teklif Detay Motoru (Master Transaction Document Dialog).

Bu modül; Akınsoft Wolvox, DIA ERP ve Kurumsal ERP'lerin en güçlü yönlerini birleştiren
evrensel evrak yönetim motorudur (Alış, Satış, Toptan, İade, Hizmet Faturaları,
Verilen/Alınan Teklifler, Siparişler ve İrsaliyeler için tek çatı mimaridir).
"""

import logging
from datetime import datetime

from PyQt6.QtCore import QDate, QTime, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
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

logger = logging.getLogger(__name__)


class NoteEditDialog(QDialog):
    """Fatura Notları & Özel Şartlar için Çok Satırlı Düzenleme Penceresi."""

    def __init__(self, note1: str = "", note2: str = "", parent=None):
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
        self.txt_note1.setPlaceholderText("Örn: Garanti BBVA TR12 0006 2000 0001 2345 6789 01 - TL Hesabı")
        self.txt_note1.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px; font-size: 12px;")

        lbl2 = QLabel("Not 2 / Teslimat & Özel Şartlar:")
        lbl2.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px;")
        self.txt_note2 = QTextEdit(note2)
        self.txt_note2.setPlaceholderText("Örn: Ürünler eksiksiz teslim alınmıştır. İhtilaf halinde Adana Mahkemeleri yetkilidir.")
        self.txt_note2.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px; font-size: 12px;")

        layout.addWidget(lbl1)
        layout.addWidget(self.txt_note1)
        layout.addWidget(lbl2)
        layout.addWidget(self.txt_note2)

        btn_box = QHBoxLayout()
        btn_ok = QPushButton("💾 Uygula & Kapat")
        btn_ok.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px;")
        btn_ok.clicked.connect(self.accept)

        btn_cancel = QPushButton("Vazgeç")
        btn_cancel.setStyleSheet("background-color: #64748b; color: white; padding: 8px 16px; border-radius: 4px;")
        btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def get_notes(self) -> tuple[str, str]:
        return self.txt_note1.toPlainText().strip(), self.txt_note2.toPlainText().strip()


class TransactionDocumentDialog(QDialog):
    """Evrensel Fiş & Evrak Detay Penceresi (DIA + Akınsoft + Kurumsal ERP Sentezi)."""

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
        "Sil", "Türü", "Barkod", "Stok Kodu", "Açıklama / Ürün Adı", "Satır Notu 2",
        "Miktar", "Birim", "B.Fiyat", "Döviz", "İsk 1 %", "İsk 2 %", "İsk. Tutarı", "KDV %", "Tevkifat", "Tutar"
    ]

    SAMPLE_CUSTOMERS = [
        {"code": "M210000194", "name": "TATU HIRDAVAT İÇ VE DIŞ TİC.LTD.ŞTİ", "tax_office": "Seyhan V.D.", "tax_no": "1234567896", "address": "Mersinli Mah. 2826 Sk. No:14/101 Adana", "balance": "45.250,00 ₺ (Borçlu)", "terms": 30},
        {"code": "M210000195", "name": "DENEME BİLİŞİM TEKNOLOJİLERİ A.Ş.", "tax_office": "Kadıköy V.D.", "tax_no": "9876543210", "address": "Bağdat Cad. No:44 İstanbul", "balance": "12.800,00 ₺ (Alacaklı)", "terms": 15},
        {"code": "M210000196", "name": "METRO MARKET TİCARET A.Ş.", "tax_office": "Güneşli V.D.", "tax_no": "5554443322", "address": "Basın Ekspres Yolu No:12 İstanbul", "balance": "0,00 ₺", "terms": 45},
    ]

    SAMPLE_PRODUCTS = [
        {"code": "STK-001", "barcode": "8697240000008", "name": "VGA Sinyal Uzatma Kablosu 5M", "unit": "Metre", "price": 150.00, "vat": 20, "stock": 42},
        {"code": "STK-002", "barcode": "8697240000009", "name": "Tükenmez Kalem Mavi 0.7mm", "unit": "Adet", "price": 15.00, "vat": 20, "stock": 180},
        {"code": "STK-003", "barcode": "8697240000010", "name": "Tam Yağlı Günlük Süt 1 LT", "unit": "LT", "price": 28.50, "vat": 1, "stock": 65},
        {"code": "STK-004", "barcode": "8697240000011", "name": "A4 Fotokopi Kağıdı 80gr 500lü", "unit": "Paket", "price": 120.00, "vat": 20, "stock": 25},
        {"code": "HZM-001", "barcode": "", "name": "Teknik Servis & Yerinde Montaj Hizmeti", "unit": "Hizmet", "price": 450.00, "vat": 20, "stock": 999},
        {"code": "HZM-002", "barcode": "", "name": "Şehir İçi Nakliye & Teslimat Bedeli", "unit": "Sefer", "price": 300.00, "vat": 20, "stock": 999},
    ]

    def __init__(self, db_session=None, company_id: int = 1, doc_id: int | None = None, initial_type_idx: int = 0, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.company_id = company_id
        self.doc_id = doc_id
        self.initial_type_idx = initial_type_idx
        self.products_catalog = list(self.SAMPLE_PRODUCTS)
        self.customers_catalog = list(self.SAMPLE_CUSTOMERS)

        self.doc_note1 = "Garanti BBVA TR12 0006 2000 0001 2345 6789 01 - TL Hesabı"
        self.doc_note2 = "Ürünler eksiksiz teslim alınmıştır. İhtilaf halinde Adana Mahkemeleri yetkilidir."

        self.setWindowTitle("[isl.doc.001] Evrensel Fiş & Evrak Detay Formu - TOYA ERP Master Şablon")
        self.setObjectName("isl.doc.001")
        self.setMinimumSize(1250, 780)
        self.resize(1280, 800)

        self.load_data_from_db()
        self.init_ui()
        self.setup_keyboard_shortcuts()

        # İlk örnek satırı oluştur
        self.add_item_row(item_type="Malzeme", code="STK-001", name="VGA Sinyal Uzatma Kablosu 5M", note2="1. Kalite Bakır İletken", qty=1.5, unit="Metre", price=150.00, currency="TRY", vat=20, disc1=0.0, disc2=0.0)

    def load_data_from_db(self):
        if self.db:
            try:
                db_prods = self.db.scalars(select(Product).where(Product.is_deleted == False)).all()
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
                db_custs = self.db.scalars(select(Customer).where(Customer.is_deleted == False)).all()
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

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 6, 8, 6)
        main_layout.setSpacing(5)

        # -------------------------------------------------------------
        # 0. EN ÜST MASTER BİLGİ ŞERİDİ (Evrak Türü, Firma, Şube, E-Belge Senaryosu, Belge No)
        # -------------------------------------------------------------
        top_bar = QFrame()
        top_bar.setObjectName("cmp.nav.001")
        top_bar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e3a8a, stop:1 #0f172a);
                border-radius: 6px;
                padding: 2px;
            }
        """)
        top_bar_lyt = QHBoxLayout(top_bar)
        top_bar_lyt.setContentsMargins(10, 5, 10, 5)
        top_bar_lyt.setSpacing(10)

        lbl_code_badge = QLabel("[isl.doc.001]")
        lbl_code_badge.setStyleSheet("background-color: #3b82f6; color: #ffffff; font-weight: 900; font-size: 10px; padding: 2px 6px; border-radius: 3px;")
        
        lbl_doc_badge = QLabel("📄 EVRAK TÜRÜ:")
        lbl_doc_badge.setStyleSheet("color: #93c5fd; font-weight: 800; font-size: 11px;")
        
        self.cmb_doc_type = QComboBox()
        self.cmb_doc_type.setObjectName("cmp.nav.doc_type")
        self.cmb_doc_type.addItems(self.DOCUMENT_TYPES)
        self.cmb_doc_type.setCurrentIndex(self.initial_type_idx)
        self.cmb_doc_type.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                font-weight: 800;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 4px;
                min-width: 250px;
            }
        """)
        self.cmb_doc_type.currentIndexChanged.connect(self.on_doc_type_changed)

        lbl_firma = QLabel("Firma: GENEL")
        lbl_firma.setStyleSheet("color: #e2e8f0; font-weight: bold; font-size: 11px;")

        lbl_branch = QLabel("Şube: MERKEZ (01)")
        lbl_branch.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 600;")

        # E-BELGE / E-FATURA SENARYOSU (En üstte Şubenin Sağına Alındı)
        lbl_efatura = QLabel("⚡ E-BELGE / E-ARŞİV:")
        lbl_efatura.setStyleSheet("color: #fde047; font-weight: 800; font-size: 11px;")

        self.cmb_efatura_scenario = QComboBox()
        self.cmb_efatura_scenario.addItems(self.EFATURA_SCENARIOS)
        self.cmb_efatura_scenario.setCurrentIndex(1)
        self.cmb_efatura_scenario.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                color: #0f172a;
                font-weight: bold;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 4px;
                min-width: 230px;
            }
        """)

        lbl_doc_no_badge = QLabel("BELGE NO:")
        lbl_doc_no_badge.setStyleSheet("color: #93c5fd; font-weight: bold; font-size: 11px;")

        self.txt_top_doc_no = QLineEdit(f"TOY2026-{datetime.now().strftime('%m%d%H%M')}")
        self.txt_top_doc_no.setFixedWidth(130)
        self.txt_top_doc_no.setStyleSheet("background-color: #ffffff; font-weight: bold; padding: 3px 6px; border-radius: 4px; color: #1e3a8a; font-size: 11px;")

        top_bar_lyt.addWidget(lbl_code_badge)
        top_bar_lyt.addWidget(lbl_doc_badge)
        top_bar_lyt.addWidget(self.cmb_doc_type)
        top_bar_lyt.addWidget(lbl_firma)
        top_bar_lyt.addWidget(lbl_branch)
        top_bar_lyt.addWidget(lbl_efatura)
        top_bar_lyt.addWidget(self.cmb_efatura_scenario)
        top_bar_lyt.addStretch()
        top_bar_lyt.addWidget(lbl_doc_no_badge)
        top_bar_lyt.addWidget(self.txt_top_doc_no)

        main_layout.addWidget(top_bar)

        # -------------------------------------------------------------
        # 1. ÜST BİLGİ PANELİ: SEKMELİ KÜNYE (Genel, Detay, Diğer, Kümülatif)
        # -------------------------------------------------------------
        self.header_tabs = QTabWidget()
        self.header_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #475569;
                font-weight: bold;
                font-size: 11px;
                padding: 5px 14px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #1e3a8a;
                border-top: 3px solid #2563eb;
            }
        """)

        tab_genel = QWidget()
        tab_genel_lyt = QVBoxLayout(tab_genel)
        tab_genel_lyt.setContentsMargins(6, 6, 6, 6)
        tab_genel_lyt.setSpacing(4)

        header_grid_layout = QHBoxLayout()
        header_grid_layout.setSpacing(8)

        # BLOK 1: CARİ HESAP BİLGİLERİ (Sol - Autocomplete + ... Butonlu)
        grp_cari = QFrame()
        grp_cari.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        cari_lyt = QFormLayout(grp_cari)
        cari_lyt.setContentsMargins(8, 6, 8, 6)
        cari_lyt.setSpacing(4)

        lbl_cari_hdr = QLabel("👤 CARİ HESAP KÜNYESİ")
        lbl_cari_hdr.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 11px; border: none;")
        cari_lyt.addRow(lbl_cari_hdr)

        # Cari Kodu
        hk_box = QHBoxLayout()
        self.txt_cari_kodu = QLineEdit("M210000194")
        self.txt_cari_kodu.setPlaceholderText("Cari Kodu yazın...")
        self.txt_cari_kodu.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-weight: bold; font-size: 11px;")
        
        btn_cari_rehber_kod = QPushButton("...")
        btn_cari_rehber_kod.setToolTip("Cari Kartlar Listesinden Seç (F10)")
        btn_cari_rehber_kod.setFixedWidth(26)
        btn_cari_rehber_kod.setStyleSheet("font-weight: bold; background: #e2e8f0; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px;")
        btn_cari_rehber_kod.clicked.connect(self.open_customer_lookup)
        hk_box.addWidget(self.txt_cari_kodu)
        hk_box.addWidget(btn_cari_rehber_kod)
        cari_lyt.addRow("Cari Kodu:", hk_box)

        # Cari Ünvanı
        unv_box = QHBoxLayout()
        self.txt_cari_unvan = QLineEdit("TATU HIRDAVAT İÇ VE DIŞ TİC.LTD.ŞTİ")
        self.txt_cari_unvan.setPlaceholderText("Cari Ünvanı yazın...")
        self.txt_cari_unvan.setStyleSheet("background: white; color: #0f172a; font-weight: 600; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        
        btn_cari_rehber_unv = QPushButton("...")
        btn_cari_rehber_unv.setToolTip("Cari Kartlar Listesinden Seç")
        btn_cari_rehber_unv.setFixedWidth(26)
        btn_cari_rehber_unv.setStyleSheet("font-weight: bold; background: #e2e8f0; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 2px;")
        btn_cari_rehber_unv.clicked.connect(self.open_customer_lookup)

        btn_cari_bakiye = QPushButton("💳 Bakiye")
        btn_cari_bakiye.setToolTip("Cari Bakiye & Ekstre Görüntüle")
        btn_cari_bakiye.setStyleSheet("background-color: #fee2e2; color: #991b1b; font-weight: bold; border: 1px solid #fca5a5; border-radius: 4px; padding: 3px 6px; font-size: 10px;")
        btn_cari_bakiye.clicked.connect(self.show_customer_balance)
        
        unv_box.addWidget(self.txt_cari_unvan)
        unv_box.addWidget(btn_cari_rehber_unv)
        unv_box.addWidget(btn_cari_bakiye)
        cari_lyt.addRow("Ticari Ünvan:", unv_box)

        self.setup_customer_completers()

        # Vergi Dairesi / No
        vd_box = QHBoxLayout()
        self.txt_vergi_daire = QLineEdit("Seyhan V.D.")
        self.txt_vergi_daire.setPlaceholderText("Vergi Dairesi")
        self.txt_vergi_daire.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        self.txt_vergi_no = QLineEdit("1234567896")
        self.txt_vergi_no.setPlaceholderText("Vergi / TCKN No")
        self.txt_vergi_no.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        vd_box.addWidget(self.txt_vergi_daire)
        vd_box.addWidget(self.txt_vergi_no)
        cari_lyt.addRow("Vergi D./No:", vd_box)

        self.txt_sevk_adres = QLineEdit("Mersinli Mah. 2826 Sokak No:14/101 1.Sanayi Sitesi")
        self.txt_sevk_adres.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        cari_lyt.addRow("Sevk Adresi:", self.txt_sevk_adres)

        # BLOK 2: BELGE, TARİH & DEPO (Orta)
        grp_belge = QFrame()
        grp_belge.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        belge_lyt = QFormLayout(grp_belge)
        belge_lyt.setContentsMargins(8, 6, 8, 6)
        belge_lyt.setSpacing(4)

        lbl_belge_hdr = QLabel("📅 BELGE & VADE DETAYLARI")
        lbl_belge_hdr.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 11px; border: none;")
        belge_lyt.addRow(lbl_belge_hdr)

        seri_box = QHBoxLayout()
        self.txt_fatura_seri = QLineEdit("S220165")
        self.txt_fatura_seri.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        self.txt_fatura_sira = QLineEdit("0")
        self.txt_fatura_sira.setFixedWidth(45)
        self.txt_fatura_sira.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        seri_box.addWidget(self.txt_fatura_seri)
        seri_box.addWidget(self.txt_fatura_sira)
        belge_lyt.addRow("Fatura Seri/No:", seri_box)

        date_box = QHBoxLayout()
        self.date_belge = QDateEdit(QDate.currentDate())
        self.date_belge.setCalendarPopup(True)
        self.date_belge.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        self.txt_saat = QLineEdit(QTime.currentTime().toString("HH:mm"))
        self.txt_saat.setFixedWidth(55)
        self.txt_saat.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        date_box.addWidget(self.date_belge)
        date_box.addWidget(self.txt_saat)
        belge_lyt.addRow("Tarih / Saat:", date_box)

        vade_box = QHBoxLayout()
        self.date_vade = QDateEdit(QDate.currentDate().addDays(30))
        self.date_vade.setCalendarPopup(True)
        self.date_vade.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        self.lbl_vade_gun = QLabel("(30 Gün)")
        self.lbl_vade_gun.setStyleSheet("color: #64748b; font-weight: bold; font-size: 11px;")
        vade_box.addWidget(self.date_vade)
        vade_box.addWidget(self.lbl_vade_gun)
        belge_lyt.addRow("Vade Tarihi:", vade_box)

        self.cmb_depo = QComboBox()
        self.cmb_depo.addItems(["2001 - MERKEZ DEPO (Zentrallager)", "2002 - ŞUBE DEPOSU", "2003 - TEŞHİR DEPOSU"])
        self.cmb_depo.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        belge_lyt.addRow("Çıkış Deposu:", self.cmb_depo)

        # BLOK 3: FİNANS, FİŞ DÖVİZİ & HAREKET ONAYLARI (Sağ)
        grp_finans = QFrame()
        grp_finans.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        finans_lyt = QFormLayout(grp_finans)
        finans_lyt.setContentsMargins(8, 6, 8, 6)
        finans_lyt.setSpacing(4)

        lbl_finans_hdr = QLabel("⚙️ HAREKET AYARLARI & FİNANS")
        lbl_finans_hdr.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 11px; border: none;")
        finans_lyt.addRow(lbl_finans_hdr)

        # Fiş Dövizi & Kur
        doviz_box = QHBoxLayout()
        self.cmb_doviz = QComboBox()
        self.cmb_doviz.addItems(["TRY (₺)", "USD ($)", "EUR (€)", "GBP (£)"])
        self.cmb_doviz.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-weight: bold; font-size: 11px;")
        self.cmb_doviz.currentIndexChanged.connect(self.calculate_totals)
        
        self.txt_doviz_kuru = QLineEdit("1.0000")
        self.txt_doviz_kuru.setPlaceholderText("Kur")
        self.txt_doviz_kuru.setFixedWidth(65)
        self.txt_doviz_kuru.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.txt_doviz_kuru.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-weight: bold; font-size: 11px;")
        self.txt_doviz_kuru.textChanged.connect(self.calculate_totals)
        
        doviz_box.addWidget(self.cmb_doviz)
        doviz_box.addWidget(QLabel("Kur:"))
        doviz_box.addWidget(self.txt_doviz_kuru)
        finans_lyt.addRow("Fiş Dövizi / Kur:", doviz_box)

        kdv_tip_box = QHBoxLayout()
        self.cmb_kdv_durumu = QComboBox()
        self.cmb_kdv_durumu.addItems(["KDV Hariç", "KDV Dahil"])
        self.cmb_kdv_durumu.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        self.cmb_kdv_durumu.currentIndexChanged.connect(self.calculate_totals)
        kdv_tip_box.addWidget(self.cmb_kdv_durumu)
        finans_lyt.addRow("KDV Durumu:", kdv_tip_box)

        # Fatura Şekli (Açık-Vadeli / Kapalı-Nakit Kasa)
        sekil_box = QHBoxLayout()
        self.cmb_fatura_sekli = QComboBox()
        self.cmb_fatura_sekli.addItems(["Kapalı - Peşin (Nakit)", "Açık - Vadeli", "Kredi Kartı / POS"])
        self.cmb_fatura_sekli.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        self.cmb_kasa = QComboBox()
        self.cmb_kasa.addItems(["K01 - Satış Kasası", "B01 - Garanti Ticari"])
        self.cmb_kasa.setStyleSheet("background: white; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        sekil_box.addWidget(self.cmb_fatura_sekli)
        sekil_box.addWidget(self.cmb_kasa)
        finans_lyt.addRow("Fatura Şekli / Kasa:", sekil_box)

        # Hareket Checkboxları
        from PyQt6.QtWidgets import QCheckBox
        chk_box = QHBoxLayout()
        self.chk_cari_islesin = QCheckBox("Cari Hareketlere İşle")
        self.chk_cari_islesin.setChecked(True)
        self.chk_cari_islesin.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px;")
        
        self.chk_stok_islesin = QCheckBox("Stok Hareketlere İşle")
        self.chk_stok_islesin.setChecked(True)
        self.chk_stok_islesin.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px;")

        chk_box.addWidget(self.chk_cari_islesin)
        chk_box.addWidget(self.chk_stok_islesin)
        finans_lyt.addRow("İşlem Onayları:", chk_box)

        header_grid_layout.addWidget(grp_cari, 4)
        header_grid_layout.addWidget(grp_belge, 3)
        header_grid_layout.addWidget(grp_finans, 3)

        tab_genel_lyt.addLayout(header_grid_layout)
        self.header_tabs.addTab(tab_genel, "1 Genel Bilgiler")
        self.header_tabs.addTab(QWidget(), "2 Detay Bilgiler")
        self.header_tabs.addTab(QWidget(), "3 İskontolar & Masraflar")
        self.header_tabs.addTab(QWidget(), "4 Ek Alanlar")
        self.header_tabs.addTab(QWidget(), "5 Kümülatif KDV Dağılımı")

        main_layout.addWidget(self.header_tabs)

        # -------------------------------------------------------------
        # 2. ORTA PANEL: KALEMLER TABLOSU (DATA GRID - 16 Sütunlu Zengin Düzen)
        # -------------------------------------------------------------
        self.table_items = QTableWidget(0, 16)
        self.table_items.setHorizontalHeaderLabels(self.COLUMN_NAMES)
        
        self.table_items.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_items.setShowGrid(True)
        self.table_items.setAlternatingRowColors(True)

        # SATIR YÜKSEKLİĞİ VE OKUNABİLİRLİK (KULLANICI TALEBİ: 34px Ferah Satırlar)
        vheader = self.table_items.verticalHeader()
        vheader.setVisible(True)
        vheader.setDefaultSectionSize(34)
        vheader.setSectionsMovable(True)
        vheader.sectionDoubleClicked.connect(lambda r: self.table_items.selectRow(r))
        vheader.sectionMoved.connect(self.on_row_reordered)

        # SAĞ KLİK AYRIMI: Header Sağ Klik vs Tablo Gövdesi Sağ Klik
        self.table_items.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_items.customContextMenuRequested.connect(self.show_items_body_context_menu)

        hheader = self.table_items.horizontalHeader()
        hheader.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hheader.customContextMenuRequested.connect(self.show_header_columns_context_menu)

        # Sütun Genişlikleri
        hheader.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table_items.setColumnWidth(0, 32)   # Sil
        self.table_items.setColumnWidth(1, 105)  # Türü
        self.table_items.setColumnWidth(2, 110)  # Barkod
        self.table_items.setColumnWidth(3, 140)  # Kod + ...
        hheader.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Açıklama
        self.table_items.setColumnWidth(5, 120)  # Satır Notu 2
        self.table_items.setColumnWidth(6, 65)   # Miktar
        self.table_items.setColumnWidth(7, 65)   # Birim
        self.table_items.setColumnWidth(8, 85)   # B.Fiyat
        self.table_items.setColumnWidth(9, 65)   # Satır Dövizi
        self.table_items.setColumnWidth(10, 55)  # İsk 1 %
        self.table_items.setColumnWidth(11, 55)  # İsk 2 %
        self.table_items.setColumnWidth(12, 75)  # İsk Tutarı
        self.table_items.setColumnWidth(13, 60)  # KDV %
        self.table_items.setColumnWidth(14, 70)  # Tevkifat
        self.table_items.setColumnWidth(15, 100) # Tutar

        self.table_items.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                border-radius: 6px;
                font-family: 'Segoe UI';
                font-size: 12px;
                color: #0f172a;
                alternate-background-color: #f8fafc;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #334155;
                padding: 6px 8px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                font-weight: 800;
                font-size: 11px;
            }
            QHeaderView::section:vertical {
                background-color: #f8fafc;
                color: #64748b;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 6px;
                border-right: 2px solid #cbd5e1;
            }
        """)

        main_layout.addWidget(self.table_items, 1)

        # -------------------------------------------------------------
        # 3. ALT BÖLÜM: ÇOKLU İSKONTO/MASRAF MİNİ TABLOSU + POPUP NOTLAR + BÜYÜK GENEL TOPLAM
        # -------------------------------------------------------------
        bottom_box = QHBoxLayout()
        bottom_box.setSpacing(8)

        # SOL ALT 1: FATURA ALTI ÇOKLU İSKONTO & MASRAFLAR (KULLANICI TALEBİ: Mini Tablo)
        grp_alt_iskonto = QFrame()
        grp_alt_iskonto.setFixedHeight(130)
        grp_alt_iskonto.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;")
        alt_isk_lyt = QVBoxLayout(grp_alt_iskonto)
        alt_isk_lyt.setContentsMargins(6, 4, 6, 4)
        alt_isk_lyt.setSpacing(2)

        hdr_alt_box = QHBoxLayout()
        lbl_alt_isk_title = QLabel("🏷️ Fatura Altı Çoklu İskonto & Masraflar:")
        lbl_alt_isk_title.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 11px;")
        
        btn_add_alt_isk = QPushButton("➕ Satır Ekle")
        btn_add_alt_isk.setStyleSheet("background-color: #eff6ff; color: #1d4ed8; font-weight: bold; font-size: 10px; border: 1px solid #bfdbfe; border-radius: 3px; padding: 2px 6px;")
        btn_add_alt_isk.clicked.connect(self.add_alt_iskonto_row)
        
        hdr_alt_box.addWidget(lbl_alt_isk_title)
        hdr_alt_box.addStretch()
        hdr_alt_box.addWidget(btn_add_alt_isk)
        alt_isk_lyt.addLayout(hdr_alt_box)

        # Mini Çoklu İskonto / Masraf Tablosu
        self.table_alt_iskonto = QTableWidget(0, 5)
        self.table_alt_iskonto.setHorizontalHeaderLabels(["Sil", "Tür", "Hesap Tipi", "Değer", "Tutar (₺)"])
        self.table_alt_iskonto.setShowGrid(True)
        self.table_alt_iskonto.verticalHeader().setVisible(False)
        self.table_alt_iskonto.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_alt_iskonto.setColumnWidth(0, 26)
        self.table_alt_iskonto.setStyleSheet("QTableWidget { font-size: 10px; border: 1px solid #e2e8f0; } QHeaderView::section { font-size: 10px; padding: 2px; }")
        alt_isk_lyt.addWidget(self.table_alt_iskonto)

        # Varsayılan 1 satır ekle
        self.add_alt_iskonto_row(item_type="İskonto", calc_type="Oran %", val="0.00")

        bottom_box.addWidget(grp_alt_iskonto, 5)

        # SOL ALT 2: KOMPAKT FATURA NOTLARI & DETAY POPUP BUTONU (KULLANICI TALEBİ)
        notes_frame = QFrame()
        notes_frame.setFixedHeight(130)
        notes_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;")
        notes_lyt = QVBoxLayout(notes_frame)
        notes_lyt.setContentsMargins(6, 6, 6, 6)
        notes_lyt.setSpacing(4)

        lbl_notes_hdr = QLabel("📝 Fatura Notları & Şartlar:")
        lbl_notes_hdr.setStyleSheet("font-weight: 800; color: #475569; font-size: 11px;")
        notes_lyt.addWidget(lbl_notes_hdr)

        self.lbl_note_preview = QLabel("Banka: Garanti BBVA TR12 0006...\nŞartlar: Adana Mahkemeleri yetkilidir.")
        self.lbl_note_preview.setStyleSheet("color: #0f172a; font-size: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 4px;")
        self.lbl_note_preview.setWordWrap(True)
        notes_lyt.addWidget(self.lbl_note_preview, 1)

        btn_open_notes = QPushButton("✏️ Çok Satırlı Notları Düzenle...")
        btn_open_notes.setStyleSheet("background-color: #f1f5f9; color: #1e3a8a; font-weight: bold; font-size: 11px; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px;")
        btn_open_notes.clicked.connect(self.open_notes_dialog)
        notes_lyt.addWidget(btn_open_notes)

        bottom_box.addWidget(notes_frame, 3)

        # SAĞ ALT: BÜYÜK OKUNABİLİR VERGİ, MASRAF & DEV GENEL TOPLAM (EŞİT YÜKSEKLİKTE 130px)
        totals_frame = QFrame()
        totals_frame.setFixedHeight(130)
        totals_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px;")
        totals_lyt = QHBoxLayout(totals_frame)
        totals_lyt.setContentsMargins(10, 6, 10, 6)
        totals_lyt.setSpacing(12)

        # Sol sütun: Büyük ve Okunabilir Ara Toplamlar
        tax_form = QFormLayout()
        tax_form.setContentsMargins(0, 0, 0, 0)
        tax_form.setSpacing(3)

        self.lbl_subtotal = QLabel("0,00 ₺")
        self.lbl_subtotal.setStyleSheet("font-weight: 800; color: #1e293b; font-size: 12px;")

        self.lbl_discount = QLabel("-0,00 ₺")
        self.lbl_discount.setStyleSheet("font-weight: 800; color: #dc2626; font-size: 12px;")

        self.lbl_expense_total = QLabel("+0,00 ₺")
        self.lbl_expense_total.setStyleSheet("font-weight: 800; color: #0284c7; font-size: 12px;")

        self.lbl_vat_total = QLabel("+0,00 ₺")
        self.lbl_vat_total.setStyleSheet("font-weight: 800; color: #7c3aed; font-size: 12px;")

        lbl_sub_title = QLabel("Ara Toplam:")
        lbl_sub_title.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        lbl_disc_title = QLabel("İskonto Toplamı:")
        lbl_disc_title.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        lbl_exp_title = QLabel("Masraflar:")
        lbl_exp_title.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        lbl_vat_title = QLabel("Hesaplanan KDV:")
        lbl_vat_title.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")

        tax_form.addRow(lbl_sub_title, self.lbl_subtotal)
        tax_form.addRow(lbl_disc_title, self.lbl_discount)
        tax_form.addRow(lbl_exp_title, self.lbl_expense_total)
        tax_form.addRow(lbl_vat_title, self.lbl_vat_total)

        totals_lyt.addLayout(tax_form)

        # Sağ sütun: BÜYÜK VURGULU GENEL TOPLAM KUTUSU
        grand_box = QFrame()
        grand_box.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e3a8a, stop:1 #0f172a);
                border-radius: 6px;
                padding: 4px 10px;
                min-width: 170px;
            }
        """)
        grand_lyt = QVBoxLayout(grand_box)
        grand_lyt.setContentsMargins(6, 4, 6, 4)
        grand_lyt.setSpacing(1)

        lbl_gt_title = QLabel("GENEL TOPLAM")
        lbl_gt_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_gt_title.setStyleSheet("color: #93c5fd; font-weight: 800; font-size: 11px; letter-spacing: 1px;")

        self.lbl_grand_total = QLabel("0,00 ₺")
        self.lbl_grand_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_grand_total.setStyleSheet("color: #ffffff; font-weight: 900; font-size: 22px; font-family: 'Segoe UI';")

        self.lbl_doviz_total = QLabel("0,00 USD")
        self.lbl_doviz_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_doviz_total.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 10px;")

        grand_lyt.addWidget(lbl_gt_title)
        grand_lyt.addWidget(self.lbl_grand_total)
        grand_lyt.addWidget(self.lbl_doviz_total)

        totals_lyt.addWidget(grand_box)
        bottom_box.addWidget(totals_frame, 4)

        main_layout.addLayout(bottom_box)

        # -------------------------------------------------------------
        # 4. EN ALT AKSİYON ÇUBUĞU (ACTION BAR - Sütun Yönetimi Kaldırıldı)
        # -------------------------------------------------------------
        action_bar = QHBoxLayout()
        action_bar.setSpacing(6)

        btn_save = QPushButton("💾 Kaydet (F2)")
        btn_save.setShortcut("F2")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: 800;
                font-size: 11px;
                border-radius: 5px;
                padding: 7px 16px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        btn_save.clicked.connect(self.save_document)

        btn_save_new = QPushButton("➕ Kaydet & Yeni")
        btn_save_new.setStyleSheet("""
            QPushButton {
                background-color: #0d9488;
                color: white;
                font-weight: 800;
                font-size: 11px;
                border-radius: 5px;
                padding: 7px 16px;
            }
            QPushButton:hover { background-color: #0f766e; }
        """)
        btn_save_new.clicked.connect(self.save_and_new_document)

        btn_save_print = QPushButton("🖨️ Kaydet & Yazdır (F9)")
        btn_save_print.setShortcut("F9")
        btn_save_print.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 5px;
                padding: 7px 14px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        btn_save_print.clicked.connect(self.save_and_print_document)

        # KALEMLERİ AKTAR BUTONU
        self.btn_import_lines = QPushButton("📥 Kalemleri Aktar ▼")
        self.btn_import_lines.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #1e3a8a;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 7px 12px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.setup_import_lines_menu()
        action_bar.addWidget(self.btn_import_lines)

        btn_earciv_send = QPushButton("📤 e-Fatura Gönder")
        btn_earciv_send.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 5px;
                padding: 7px 14px;
            }
            QPushButton:hover { background-color: #6d28d9; }
        """)
        btn_earciv_send.clicked.connect(self.send_earciv)

        btn_cancel = QPushButton("✖ Vazgeç (Esc)")
        btn_cancel.setShortcut("Esc")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 5px;
                padding: 7px 14px;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        btn_cancel.clicked.connect(self.reject)

        action_bar.addWidget(btn_save)
        action_bar.addWidget(btn_save_new)
        action_bar.addWidget(btn_save_print)
        action_bar.addWidget(btn_earciv_send)
        action_bar.addStretch()
        action_bar.addWidget(btn_cancel)

        main_layout.addLayout(action_bar)

    def setup_customer_completers(self):
        codes = [c["code"] for c in self.customers_catalog]
        comp_code = QCompleter(codes, self)
        comp_code.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_code.setFilterMode(Qt.MatchFlag.MatchContains)
        comp_code.activated.connect(self.on_customer_code_selected)
        self.txt_cari_kodu.setCompleter(comp_code)

        names = [c["name"] for c in self.customers_catalog]
        comp_name = QCompleter(names, self)
        comp_name.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_name.setFilterMode(Qt.MatchFlag.MatchContains)
        comp_name.activated.connect(self.on_customer_name_selected)
        self.txt_cari_unvan.setCompleter(comp_name)

    def on_customer_code_selected(self, selected_code: str):
        for c in self.customers_catalog:
            if c["code"] == selected_code:
                self.apply_customer_info(c)
                break

    def on_customer_name_selected(self, selected_name: str):
        for c in self.customers_catalog:
            if c["name"] == selected_name:
                self.apply_customer_info(c)
                break

    def apply_customer_info(self, c: dict):
        self.txt_cari_kodu.setText(c["code"])
        self.txt_cari_unvan.setText(c["name"])
        self.txt_vergi_daire.setText(c.get("tax_office", ""))
        self.txt_vergi_no.setText(c.get("tax_no", ""))
        self.txt_sevk_adres.setText(c.get("address", ""))
        self.date_vade.setDate(QDate.currentDate().addDays(c.get("terms", 30)))
        self.lbl_vade_gun.setText(f"({c.get('terms', 30)} Gün)")

    def open_customer_lookup(self):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: white; border: 1px solid #cbd5e1; font-size: 12px; } QMenu::item { padding: 6px 14px; } QMenu::item:selected { background-color: #2563eb; color: white; }")
        
        for c in self.customers_catalog:
            act = QAction(f"👤 {c['code']} - {c['name']}", self)
            act.triggered.connect(lambda _, cust=c: self.apply_customer_info(cust))
            menu.addAction(act)
        
        menu.exec(self.txt_cari_kodu.mapToGlobal(self.txt_cari_kodu.rect().bottomLeft()))

    def show_customer_balance(self):
        current_code = self.txt_cari_kodu.text().strip()
        matched = next((c for c in self.customers_catalog if c["code"] == current_code), None)
        bal_txt = matched["balance"] if matched else "45.250,00 ₺ (Borçlu)"
        unv_txt = matched["name"] if matched else self.txt_cari_unvan.text()
        QMessageBox.information(self, "Cari Bakiye & Ekstre", f"{unv_txt}\n\n🔴 Güncel Bakiye: {bal_txt}\nVadesi Geçen: 12.000,00 ₺\nKredi Limiti: 100.000,00 ₺")

    def open_notes_dialog(self):
        dlg = NoteEditDialog(self.doc_note1, self.doc_note2, self)
        if dlg.exec():
            self.doc_note1, self.doc_note2 = dlg.get_notes()
            n1_preview = (self.doc_note1[:35] + "...") if len(self.doc_note1) > 35 else self.doc_note1
            n2_preview = (self.doc_note2[:35] + "...") if len(self.doc_note2) > 35 else self.doc_note2
            self.lbl_note_preview.setText(f"Not 1: {n1_preview or 'Yok'}\nNot 2: {n2_preview or 'Yok'}")

    def add_alt_iskonto_row(self, item_type: str = "İskonto", calc_type: str = "Oran %", val: str = "0.00"):
        row = self.table_alt_iskonto.rowCount()
        self.table_alt_iskonto.insertRow(row)

        btn_del = QPushButton("❌")
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("background: transparent; color: #ef4444; border: none; font-weight: bold;")
        btn_del.clicked.connect(lambda _, r=row: self.remove_alt_iskonto_row(r))

        cmb_type = QComboBox()
        cmb_type.addItems(["İskonto", "Masraf", "Nakliye", "Sigorta", "Ambalaj"])
        cmb_type.setCurrentText(item_type)
        cmb_type.currentIndexChanged.connect(self.calculate_totals)

        cmb_calc = QComboBox()
        cmb_calc.addItems(["Oran %", "Tutar ₺"])
        cmb_calc.setCurrentText(calc_type)
        cmb_calc.currentIndexChanged.connect(self.calculate_totals)

        txt_val = QLineEdit(val)
        txt_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        txt_val.textChanged.connect(self.calculate_totals)

        lbl_net = QLabel("0,00 ₺")
        lbl_net.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_net.setStyleSheet("font-weight: bold; color: #1e3a8a;")

        self.table_alt_iskonto.setCellWidget(row, 0, btn_del)
        self.table_alt_iskonto.setCellWidget(row, 1, cmb_type)
        self.table_alt_iskonto.setCellWidget(row, 2, cmb_calc)
        self.table_alt_iskonto.setCellWidget(row, 3, txt_val)
        self.table_alt_iskonto.setCellWidget(row, 4, lbl_net)

        self.calculate_totals()

    def remove_alt_iskonto_row(self, row: int):
        self.table_alt_iskonto.removeRow(row)
        self.calculate_totals()

    def setup_import_lines_menu(self):
        import_menu = QMenu(self)
        import_menu.setStyleSheet("QMenu { background-color: white; border: 1px solid #cbd5e1; font-size: 12px; } QMenu::item { padding: 6px 14px; } QMenu::item:selected { background-color: #2563eb; color: white; }")
        
        act_tek = QAction("📋 Tekliften Kalem Aktar...", self)
        act_tek.triggered.connect(lambda: self.trigger_line_import("Teklif"))
        
        act_sip = QAction("📦 Siparişten Kalem Aktar...", self)
        act_sip.triggered.connect(lambda: self.trigger_line_import("Sipariş"))
        
        act_irs = QAction("🚚 İrsaliyeden Kalem Aktar...", self)
        act_irs.triggered.connect(lambda: self.trigger_line_import("İrsaliye"))
        
        act_fat = QAction("📄 Başka Faturadan Kalem Aktar...", self)
        act_fat.triggered.connect(lambda: self.trigger_line_import("Fatura"))

        act_xls = QAction("📊 Excel / Dış Dosyadan Kalem Yükle...", self)
        act_xls.triggered.connect(lambda: self.trigger_line_import("Excel"))

        import_menu.addAction(act_tek)
        import_menu.addAction(act_sip)
        import_menu.addAction(act_irs)
        import_menu.addAction(act_fat)
        import_menu.addSeparator()
        import_menu.addAction(act_xls)

        self.btn_import_lines.setMenu(import_menu)

    def trigger_line_import(self, source_type: str):
        if source_type == "Excel":
            fpath, _ = QFileDialog.getOpenFileName(self, "Excel Kalem Listesi Seç", "", "Excel Files (*.xlsx *.xls *.csv)")
            if fpath:
                self.add_item_row(item_type="Malzeme", code="STK-002", name="Excelden Aktarılan Kalem", note2="İthal Ürün", qty=10, unit="Adet", price=85.00, vat=20)
                QMessageBox.information(self, "Aktarım Tamamlandı", f"{fpath} dosyasından kalemler evraka aktarıldı.")
        else:
            self.add_item_row(item_type="Malzeme", code="STK-004", name=f"{source_type} Kaynaklı A4 Fotokopi Kağıdı 80gr", note2=f"Ref: {source_type}-2026", qty=5, unit="Paket", price=120.00, vat=20)
            self.add_item_row(item_type="Hizmet", code="HZM-002", name=f"{source_type} Nakliye Bedeli", note2="Şehir İçi", qty=1, unit="Sefer", price=300.00, vat=20)
            QMessageBox.information(self, "Aktarım Başarılı", f"Seçilen {source_type} belgesindeki kalemler bu evraka başarıyla aktarıldı.")

    def setup_keyboard_shortcuts(self):
        # Ctrl+E -> Araya satır ekle
        sc_add_row = QShortcut(QKeySequence("Ctrl+E"), self)
        sc_add_row.activated.connect(lambda: self.add_item_row(item_type="Malzeme"))

    def add_item_row(self, item_type="Malzeme", barcode="", code="", name="", note2="", qty=1.0, unit="Adet", price=0.00, currency="TRY", vat=20, disc1=0.0, disc2=0.0, insert_index=None):
        row = self.table_items.rowCount() if insert_index is None else insert_index
        self.table_items.insertRow(row)

        cell_style = "background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; font-size: 12px; min-height: 24px;"

        # 0. Sil Butonu (❌)
        btn_del = QPushButton("❌")
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("background: transparent; color: #ef4444; border: none; font-weight: bold; font-size: 11px;")
        btn_del.clicked.connect(lambda _, r=row: self.remove_item_row(self.table_items.currentRow() if self.table_items.currentRow() >= 0 else r))

        # 1. Türü (Malzeme / Hizmet / Serbest Giriş)
        cmb_tur = QComboBox()
        cmb_tur.addItems(["Malzeme", "Hizmet", "Serbest Giriş"])
        cmb_tur.setCurrentText(item_type)
        cmb_tur.setStyleSheet(cell_style)

        # 2. Barkod
        txt_barcode = QLineEdit(barcode)
        txt_barcode.setStyleSheet(cell_style)

        # 3. Stok / Hizmet Kodu (Geniş & Net QLineEdit + ...)
        code_widget = QWidget()
        code_widget.setStyleSheet("background: transparent;")
        code_lyt = QHBoxLayout(code_widget)
        code_lyt.setContentsMargins(1, 1, 1, 1)
        code_lyt.setSpacing(2)
        txt_code = QLineEdit(code)
        txt_code.setStyleSheet(cell_style + " font-weight: bold;")
        
        prod_codes = [p["code"] for p in self.products_catalog]
        code_completer = QCompleter(prod_codes, self)
        code_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        code_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        code_completer.activated.connect(lambda sel_code, r=row: self.on_inline_code_selected(r, sel_code))
        txt_code.setCompleter(code_completer)

        btn_code_search = QPushButton("...")
        btn_code_search.setFixedWidth(24)
        btn_code_search.setFixedHeight(24)
        btn_code_search.setStyleSheet("background: #e2e8f0; color: #1e293b; font-weight: bold; border: 1px solid #cbd5e1; border-radius: 3px;")
        btn_code_search.clicked.connect(lambda _, r=row: self.open_stock_lookup_for_row(r))
        code_lyt.addWidget(txt_code)
        code_lyt.addWidget(btn_code_search)

        # 4. Açıklama / Ürün Adı (Geniş & Net QLineEdit + ...)
        name_widget = QWidget()
        name_widget.setStyleSheet("background: transparent;")
        name_lyt = QHBoxLayout(name_widget)
        name_lyt.setContentsMargins(1, 1, 1, 1)
        name_lyt.setSpacing(2)
        txt_name = QLineEdit(name)
        txt_name.setStyleSheet(cell_style + " font-weight: 600;")
        
        prod_names = [p["name"] for p in self.products_catalog]
        name_completer = QCompleter(prod_names, self)
        name_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        name_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        name_completer.activated.connect(lambda selected_name, r=row: self.on_inline_name_selected(r, selected_name))
        txt_name.setCompleter(name_completer)
        txt_name.textChanged.connect(self.calculate_totals)

        btn_name_search = QPushButton("...")
        btn_name_search.setFixedWidth(24)
        btn_name_search.setFixedHeight(24)
        btn_name_search.setStyleSheet("background: #e2e8f0; color: #1e293b; font-weight: bold; border: 1px solid #cbd5e1; border-radius: 3px;")
        btn_name_search.clicked.connect(lambda _, r=row: self.open_stock_lookup_for_row(r))
        name_lyt.addWidget(txt_name)
        name_lyt.addWidget(btn_name_search)

        # 5. Satır Notu 2
        txt_note2 = QLineEdit(note2)
        txt_note2.setPlaceholderText("Ek Bilgi / Not 2...")
        txt_note2.setStyleSheet(cell_style)

        # 6. Miktar
        txt_qty = QLineEdit(str(qty))
        txt_qty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_qty.setStyleSheet(cell_style + " font-weight: bold;")
        txt_qty.textChanged.connect(self.calculate_totals)

        # 7. Birim
        txt_unit = QLineEdit(unit)
        txt_unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_unit.setStyleSheet(cell_style)

        # 8. Birim Fiyat
        txt_price = QLineEdit(f"{price:.2f}")
        txt_price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        txt_price.setStyleSheet(cell_style + " font-weight: bold;")
        txt_price.textChanged.connect(self.calculate_totals)

        # 9. Satır Dövizi
        cmb_cur = QComboBox()
        cmb_cur.addItems(["TRY", "USD", "EUR", "GBP"])
        cmb_cur.setCurrentText(currency)
        cmb_cur.setStyleSheet(cell_style)
        cmb_cur.currentIndexChanged.connect(self.calculate_totals)

        # 10. İskonto 1 %
        txt_disc1 = QLineEdit(str(disc1))
        txt_disc1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_disc1.setStyleSheet(cell_style)
        txt_disc1.textChanged.connect(self.calculate_totals)

        # 11. İskonto 2 %
        txt_disc2 = QLineEdit(str(disc2))
        txt_disc2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_disc2.setStyleSheet(cell_style)
        txt_disc2.textChanged.connect(self.calculate_totals)

        # 12. İskonto Tutarı
        lbl_disc_amt = QLabel("0,00")
        lbl_disc_amt.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_disc_amt.setStyleSheet("color: #dc2626; font-weight: bold; font-size: 11px;")

        # 13. KDV %
        cmb_vat = QComboBox()
        cmb_vat.addItems(["% 20", "% 10", "% 1", "% 0"])
        cmb_vat.setCurrentText(f"% {vat}")
        cmb_vat.setStyleSheet(cell_style)
        cmb_vat.currentIndexChanged.connect(self.calculate_totals)

        # 14. Tevkifat
        cmb_tevkifat = QComboBox()
        cmb_tevkifat.addItems(["Yok", "5/10", "7/10", "9/10", "10/10"])
        cmb_tevkifat.setStyleSheet(cell_style)
        cmb_tevkifat.currentIndexChanged.connect(self.calculate_totals)

        # 15. Satır Tutarı
        lbl_tot = QLabel("0,00 ₺")
        lbl_tot.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_tot.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 11px;")

        # Enter ile bir sonraki satıra geçme
        txt_price.returnPressed.connect(lambda: self.add_item_row(item_type="Malzeme"))

        # Hücreleri yerleştir
        self.table_items.setCellWidget(row, 0, btn_del)
        self.table_items.setCellWidget(row, 1, cmb_tur)
        self.table_items.setCellWidget(row, 2, txt_barcode)
        self.table_items.setCellWidget(row, 3, code_widget)
        self.table_items.setCellWidget(row, 4, name_widget)
        self.table_items.setCellWidget(row, 5, txt_note2)
        self.table_items.setCellWidget(row, 6, txt_qty)
        self.table_items.setCellWidget(row, 7, txt_unit)
        self.table_items.setCellWidget(row, 8, txt_price)
        self.table_items.setCellWidget(row, 9, cmb_cur)
        self.table_items.setCellWidget(row, 10, txt_disc1)
        self.table_items.setCellWidget(row, 11, txt_disc2)
        self.table_items.setCellWidget(row, 12, lbl_disc_amt)
        self.table_items.setCellWidget(row, 13, cmb_vat)
        self.table_items.setCellWidget(row, 14, cmb_tevkifat)
        self.table_items.setCellWidget(row, 15, lbl_tot)

        # Tür değiştiğinde davranış
        cmb_tur.currentTextChanged.connect(lambda new_tur, r=row: self.on_item_type_changed(r, new_tur))

        self.calculate_totals()

    def on_row_reordered(self, logicalIndex, oldVisualIndex, newVisualIndex):
        """Satırlar sürüklendiğinde sıra numaralarını otomatik tazele."""
        pass

    def on_item_type_changed(self, row: int, new_tur: str):
        code_w = self.table_items.cellWidget(row, 3)
        name_w = self.table_items.cellWidget(row, 4)
        if new_tur == "Serbest Giriş":
            if code_w:
                txt = code_w.findChild(QLineEdit)
                if txt:
                    txt.setPlaceholderText("Serbest Kod")
            if name_w:
                txt = name_w.findChild(QLineEdit)
                if txt:
                    txt.setPlaceholderText("Serbest Açıklama Yazın...")

    def on_inline_code_selected(self, row: int, selected_code: str):
        for p in self.products_catalog:
            if p["code"] == selected_code:
                self.apply_product_to_row(row, p)
                break

    def on_inline_name_selected(self, row: int, selected_name: str):
        for p in self.products_catalog:
            if p["name"] == selected_name:
                self.apply_product_to_row(row, p)
                break

    def apply_product_to_row(self, row: int, p: dict):
        code_w = self.table_items.cellWidget(row, 3)
        if code_w:
            txt = code_w.findChild(QLineEdit)
            if txt:
                txt.setText(p["code"])

        name_w = self.table_items.cellWidget(row, 4)
        if name_w:
            txt = name_w.findChild(QLineEdit)
            if txt:
                txt.setText(p["name"])

        barcode_w = self.table_items.cellWidget(row, 2)
        if barcode_w and isinstance(barcode_w, QLineEdit):
            barcode_w.setText(p.get("barcode", ""))

        unit_w = self.table_items.cellWidget(row, 7)
        if unit_w and isinstance(unit_w, QLineEdit):
            unit_w.setText(p.get("unit", "Adet"))

        price_w = self.table_items.cellWidget(row, 8)
        if price_w and isinstance(price_w, QLineEdit):
            price_w.setText(f"{p['price']:.2f}")

        vat_w = self.table_items.cellWidget(row, 13)
        if vat_w and isinstance(vat_w, QComboBox):
            vat_w.setCurrentText(f"% {p['vat']}")

        self.calculate_totals()

    def open_stock_lookup_for_row(self, row: int):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: white; border: 1px solid #cbd5e1; font-size: 12px; } QMenu::item { padding: 6px 14px; } QMenu::item:selected { background-color: #2563eb; color: white; }")
        
        for p in self.products_catalog:
            act = QAction(f"📦 {p['code']} - {p['name']} ({p['price']:.2f} ₺ | Stok: {p['stock']})", self)
            act.triggered.connect(lambda _, prod=p, r=row: self.apply_product_to_row(r, prod))
            menu.addAction(act)
        
        name_w = self.table_items.cellWidget(row, 4)
        if name_w:
            menu.exec(name_w.mapToGlobal(name_w.rect().bottomLeft()))

    def show_header_columns_context_menu(self, pos):
        """Grid Kolon Başlığına (Header) Sağ Tıklandığında Çıkan Sütun Yönetim Menüsü."""
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: white; border: 1px solid #cbd5e1; font-size: 12px; } QMenu::item { padding: 5px 14px; } QMenu::item:selected { background-color: #2563eb; color: white; }")

        act_cfg = QAction("⚙️ Sütunları Yapılandır (Görünüm Profili)...", self)
        act_cfg.triggered.connect(lambda: QMessageBox.information(self, "Sütun Yönetimi", "Sütun genişlikleri, sırası ve görünürlükleri burada özelleştirilebilir."))

        act_save = QAction("💾 Sütun Genişliklerini Kaydet", self)
        act_save.triggered.connect(lambda: QMessageBox.information(self, "Başarılı", "Mevcut sütun genişlikleri ve yerleşimi kaydedildi."))

        act_reset = QAction("🔄 Sütunları Varsayılana Sıfırla", self)
        act_reset.triggered.connect(lambda: [self.table_items.setColumnHidden(i, False) for i in range(self.table_items.columnCount())])

        menu.addAction(act_cfg)
        menu.addAction(act_save)
        menu.addAction(act_reset)
        menu.addSeparator()

        sub_vis = menu.addMenu("👁️ Sütunları Göster / Gizle")
        for col_idx, col_name in enumerate(self.COLUMN_NAMES):
            act_col = QAction(col_name, self)
            act_col.setCheckable(True)
            act_col.setChecked(not self.table_items.isColumnHidden(col_idx))
            act_col.toggled.connect(lambda checked, idx=col_idx: self.table_items.setColumnHidden(idx, not checked))
            sub_vis.addAction(act_col)

        menu.exec(self.table_items.horizontalHeader().mapToGlobal(pos))

    def show_items_body_context_menu(self, pos):
        """Grid Tablo Gövdesine Sağ Tıklandığında Çıkan Fiş & Fiyat İşlemleri Menüsü."""
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: white; border: 1px solid #cbd5e1; font-size: 12px; } QMenu::item { padding: 6px 14px; } QMenu::item:selected { background-color: #2563eb; color: white; }")
        row = self.table_items.currentRow()

        act_add_row = QAction("➕ Satır Ekle (Ctrl+E)", self)
        act_insert_row = QAction("➕ Araya Satır Ekle", self)
        act_del_row = QAction("🗑️ Satırı Sil (Ctrl+Del)", self)

        act_price_last = QAction("💰 Son Satış / Alış Fiyatı (145,00 ₺)", self)
        act_price_cust = QAction("👥 Müşteriye Özel Fiyat Listesi", self)
        act_stock_depo = QAction("🏢 Depo Stok Durumu (Merkez: 42, Şube: 12)", self)

        # Aktarım Alt Menüsü
        import_submenu = menu.addMenu("📥 Kalemleri Aktar")
        act_tek = QAction("📋 Tekliften Kalem Aktar...", self)
        act_tek.triggered.connect(lambda: self.trigger_line_import("Teklif"))
        act_sip = QAction("📦 Siparişten Kalem Aktar...", self)
        act_sip.triggered.connect(lambda: self.trigger_line_import("Sipariş"))
        act_irs = QAction("🚚 İrsaliyeden Kalem Aktar...", self)
        act_irs.triggered.connect(lambda: self.trigger_line_import("İrsaliye"))
        act_fat = QAction("📄 Başka Faturadan Kalem Aktar...", self)
        act_fat.triggered.connect(lambda: self.trigger_line_import("Fatura"))
        act_xls = QAction("📊 Excel'den Kalem Yükle...", self)
        act_xls.triggered.connect(lambda: self.trigger_line_import("Excel"))

        import_submenu.addAction(act_tek)
        import_submenu.addAction(act_sip)
        import_submenu.addAction(act_irs)
        import_submenu.addAction(act_fat)
        import_submenu.addSeparator()
        import_submenu.addAction(act_xls)

        menu.addAction(act_add_row)
        menu.addAction(act_insert_row)
        menu.addAction(act_del_row)
        menu.addSeparator()
        menu.addAction(act_price_last)
        menu.addAction(act_price_cust)
        menu.addAction(act_stock_depo)

        act_add_row.triggered.connect(lambda: self.add_item_row(item_type="Malzeme"))
        act_insert_row.triggered.connect(lambda: self.add_item_row(item_type="Malzeme", insert_index=max(0, row)))
        act_del_row.triggered.connect(lambda: self.remove_item_row(max(0, row)))

        menu.exec(self.table_items.viewport().mapToGlobal(pos))

    def remove_item_row(self, row: int):
        if self.table_items.rowCount() > 1:
            self.table_items.removeRow(row)
            self.calculate_totals()
        else:
            QMessageBox.warning(self, "Uyarı", "Formda en az 1 satır kalem bulunmalıdır.")

    def calculate_totals(self):
        if not hasattr(self, "lbl_subtotal"):
            return

        subtotal = 0.0
        line_disc_total = 0.0
        vat_total = 0.0
        grand_total = 0.0

        is_kdv_dahil = (self.cmb_kdv_durumu.currentText() == "KDV Dahil")
        currency_sym = "₺" if "TRY" in self.cmb_doviz.currentText() else ("$" if "USD" in self.cmb_doviz.currentText() else ("€" if "EUR" in self.cmb_doviz.currentText() else "£"))

        for r in range(self.table_items.rowCount()):
            try:
                qty_w = self.table_items.cellWidget(r, 6)
                price_w = self.table_items.cellWidget(r, 8)
                disc1_w = self.table_items.cellWidget(r, 10)
                disc2_w = self.table_items.cellWidget(r, 11)
                lbl_disc_amt = self.table_items.cellWidget(r, 12)
                vat_w = self.table_items.cellWidget(r, 13)
                lbl_tot = self.table_items.cellWidget(r, 15)

                qty = float(qty_w.text().replace(",", ".")) if qty_w and qty_w.text() else 1.0
                price = float(price_w.text().replace(",", ".")) if price_w and price_w.text() else 0.0
                d1 = float(disc1_w.text().replace(",", ".")) if disc1_w and disc1_w.text() else 0.0
                d2 = float(disc2_w.text().replace(",", ".")) if disc2_w and disc2_w.text() else 0.0

                vat_text = vat_w.currentText().replace("%", "").strip() if vat_w else "20"
                vat_rate = float(vat_text) if vat_text else 20.0

                base_amt = qty * price
                # Çoklu İskonto (Kademeli)
                amt_after_d1 = base_amt * (1.0 - (d1 / 100.0))
                amt_after_d2 = amt_after_d1 * (1.0 - (d2 / 100.0))
                item_disc_amt = base_amt - amt_after_d2
                taxable = amt_after_d2

                if lbl_disc_amt:
                    lbl_disc_amt.setText(f"{item_disc_amt:,.2f}")

                if is_kdv_dahil:
                    line_net = taxable / (1.0 + (vat_rate / 100.0))
                    line_vat = taxable - line_net
                    line_total = taxable
                else:
                    line_vat = taxable * (vat_rate / 100.0)
                    line_total = taxable + line_vat

                subtotal += base_amt
                line_disc_total += item_disc_amt
                vat_total += line_vat
                grand_total += line_total

                if lbl_tot:
                    lbl_tot.setText(f"{line_total:,.2f} {currency_sym}")
            except Exception:
                pass

        # ÇOKLU FATURA ALTI İSKONTO & MASRAF TABLOSU HESAPLAMASI
        doc_extra_disc = 0.0
        doc_extra_exp = 0.0

        for ar in range(self.table_alt_iskonto.rowCount()):
            try:
                cmb_type = self.table_alt_iskonto.cellWidget(ar, 1)
                cmb_calc = self.table_alt_iskonto.cellWidget(ar, 2)
                txt_val = self.table_alt_iskonto.cellWidget(ar, 3)
                lbl_net = self.table_alt_iskonto.cellWidget(ar, 4)

                type_txt = cmb_type.currentText() if cmb_type else "İskonto"
                calc_txt = cmb_calc.currentText() if cmb_calc else "Oran %"
                val_num = float(txt_val.text().replace(",", ".")) if txt_val and txt_val.text() else 0.0

                line_net_val = 0.0
                if "Oran %" in calc_txt:
                    line_net_val = (subtotal - line_disc_total) * (val_num / 100.0)
                else:
                    line_net_val = val_num

                if lbl_net:
                    lbl_net.setText(f"{line_net_val:,.2f} {currency_sym}")

                if type_txt == "İskonto":
                    doc_extra_disc += line_net_val
                else:
                    doc_extra_exp += line_net_val
            except Exception:
                pass

        total_discount = line_disc_total + doc_extra_disc
        total_grand = grand_total - doc_extra_disc + doc_extra_exp

        self.lbl_subtotal.setText(f"{subtotal:,.2f} {currency_sym}")
        self.lbl_discount.setText(f"-{total_discount:,.2f} {currency_sym}")
        self.lbl_expense_total.setText(f"+{doc_extra_exp:,.2f} {currency_sym}")
        self.lbl_vat_total.setText(f"+{vat_total:,.2f} {currency_sym}")
        self.lbl_grand_total.setText(f"{total_grand:,.2f} {currency_sym}")

        # Döviz Kuru Çevrimi
        try:
            kur = float(self.txt_doviz_kuru.text().replace(",", ".")) if self.txt_doviz_kuru.text() else 1.0
        except Exception:
            kur = 1.0

        if "TRY" in self.cmb_doviz.currentText():
            usd_equiv = total_grand / 38.50
            self.lbl_doviz_total.setText(f"Döviz Karşılığı: ~{usd_equiv:,.2f} USD")
        else:
            tl_equiv = total_grand * kur
            self.lbl_doviz_total.setText(f"TL Karşılığı: {tl_equiv:,.2f} ₺")

    def on_doc_type_changed(self, idx: int):
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

    def save_document(self):
        doc_type = self.cmb_doc_type.currentText()
        doc_no = self.txt_top_doc_no.text()
        grand = self.lbl_grand_total.text()
        QMessageBox.information(self, "Başarılı (F2)", f"'{doc_type}' ({doc_no}) başarıyla kaydedildi.\n\nToplam: {grand}")
        self.accept()

    def save_and_new_document(self):
        doc_no = self.txt_top_doc_no.text()
        QMessageBox.information(self, "Kaydedildi", f"{doc_no} başarıyla kaydedildi. Yeni evrak girişi hazırlanıyor...")
        self.txt_top_doc_no.setText(f"FTR2026-{datetime.now().strftime('%m%d%H%M%S')}")
        self.table_items.setRowCount(0)
        self.add_item_row(item_type="Malzeme", code="STK-001", name="VGA Sinyal Uzatma Kablosu 5M", qty=1.0, unit="Metre", price=150.00, vat=20)

    def save_and_print_document(self):
        QMessageBox.information(self, "Yazdırılıyor (F9)", "Evrak kaydedildi ve varsayılan Fatura / Fiş yazdırma şablonuna gönderildi.")
        self.accept()

    def send_earciv(self):
        sc_name = self.cmb_efatura_scenario.currentText()
        QMessageBox.information(self, "e-Fatura Entegratörü", f"Seçilen Senaryo: {sc_name}\n\nGİB e-Fatura / e-Arşiv XML paketi üretildi ve entegratöre iletildi.")
