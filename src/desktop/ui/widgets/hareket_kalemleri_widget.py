"""
ToyaUI — HareketKalemleriWidget
Fiş detay ekranındaki kalem giriş tablosu.

Bağımsız widget — transaction_document_dialog.py'de kullanılır.
Özellikler:
    - DB'den stok listesi çekme
    - Tam stok seçim dialog (... butonu)
    - Kodu yazınca DB'den otomatik bul
    - Sağ tık menüsü (ekle/sil/taşı/sırala/gizle/kaydet)
    - Artan/azalan sıralama
    - Sütun gizle/göster + profil kaydet
    - Min 1 satır (son satır silinemez, temizlenir)
    - Çoklu satır seçimi
    - Satır taşıma (↑↓)
    - ThemeManager satır yüksekliği
"""

import logging
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Sütun indeksleri — sabit
COL_DEL   = 0
COL_TUR   = 1
COL_BARKOD= 2
COL_KOD   = 3
COL_ACIK  = 4
COL_NOT2  = 5
COL_MIKTAR= 6
COL_BIRIM = 7
COL_FIYAT = 8
COL_DOVIZ = 9
COL_ISK1P = 10
COL_ISK1T = 11
COL_ISK2P = 12
COL_ISK2T = 13
COL_ISK3P = 14
COL_ISK3T = 15
COL_KDVP  = 16
COL_TEV   = 17
COL_TUTAR = 18

COLUMN_NAMES = [
    "🗑️", "Türü", "Barkod", "Stok Kodu",
    "Açıklama / Ürün Adı", "Satır Notu 2",
    "Miktar", "Birim", "B.Fiyat", "Döviz",
    "İsk 1 %", "İsk 1 Tutar",
    "İsk 2 %", "İsk 2 Tutar",
    "İsk 3 %", "İsk 3 Tutar",
    "KDV %", "Tevkifat", "Tutar",
]

ITEM_TYPES  = ["Malzeme", "Hizmet", "Serbest Giriş"]
VAT_RATES   = ["% 20", "% 10", "% 1", "% 0"]
WITHHOLDING = ["Yok", "5/10", "7/10", "9/10", "10/10"]

# Varsayılan birim listesi — Genel Ayarlar hazır olunca DB'den gelir
DEFAULT_UNITS = [
    "Adet", "Kg", "Gram", "Litre", "Metre", "M2", "M3",
    "Paket", "Kutu", "Koli", "Hizmet", "Sefer",
]

# Varsayılan döviz listesi — DovizKurlariWidget hazır olunca oradan gelir
DEFAULT_CURRENCIES = ["TRY", "USD", "EUR", "GBP"]


# ─────────────────────────────────────────────
# STOK SEÇİM DIALOG
# ─────────────────────────────────────────────

class StokSecimDialog(QDialog):
    """
    Tam stok seçim listesi.
    ... butonuna tıklanınca açılır.
    """

    product_selected = pyqtSignal(dict)

    def __init__(self, products: list[dict], parent=None):
        super().__init__(parent)
        self.products  = products
        self._filtered = list(products)

        self.setWindowTitle("📦 Stok Seçim Listesi")
        self.setMinimumSize(800, 500)
        self.setStyleSheet("""
            QDialog { background:#f8fafc; font-family:'Segoe UI'; }
            QLineEdit {
                border:1px solid #cbd5e1; border-radius:4px;
                padding:4px 8px; font-size:11px; background:white;
            }
            QTableWidget {
                border:1px solid #e2e8f0; background:white;
                font-size:11px; gridline-color:#f1f5f9;
            }
            QHeaderView::section {
                background:#1e3a8a; color:white;
                padding:5px; font-weight:bold; font-size:10px;
                border:none; border-right:1px solid #2d4fa0;
            }
            QTableWidget::item:selected {
                background:#dbeafe; color:#1e40af;
            }
            QPushButton {
                border:1px solid #cbd5e1; border-radius:4px;
                padding:5px 12px; font-size:11px; font-weight:600;
            }
        """)
        self._init_ui()
        self._load_table(products)

    def _init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        # Arama
        search_row = QHBoxLayout()
        lbl = QLabel("🔍")
        lbl.setStyleSheet("font-size:14px;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(
            "Stok kodu, ürün adı veya barkod ile ara..."
        )
        self.txt_search.textChanged.connect(self._filter)
        search_row.addWidget(lbl)
        search_row.addWidget(self.txt_search)
        lyt.addLayout(search_row)

        # Tablo
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Stok Kodu", "Barkod", "Ürün Adı",
            "Birim", "Alış", "Satış", "Stok"
        ])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.doubleClicked.connect(self._on_double_click)
        lyt.addWidget(self.table, 1)

        # Kayıt sayısı
        self.lbl_count = QLabel("0 kayıt")
        self.lbl_count.setStyleSheet("color:#64748b; font-size:10px;")
        lyt.addWidget(self.lbl_count)

        # Butonlar
        btn_lyt = QHBoxLayout()
        btn_sec = QPushButton("✅ Seç")
        btn_sec.setStyleSheet(
            "background:#2563eb; color:white; border-color:#1d4ed8;"
        )
        btn_sec.clicked.connect(self._on_select)
        btn_kapat = QPushButton("✕ Kapat")
        btn_kapat.clicked.connect(self.reject)

        btn_lyt.addStretch()
        btn_lyt.addWidget(btn_sec)
        btn_lyt.addWidget(btn_kapat)
        lyt.addLayout(btn_lyt)

    def _load_table(self, data: list[dict]):
        self.table.setRowCount(0)
        for p in data:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(p.get("code", "")))
            self.table.setItem(r, 1, QTableWidgetItem(p.get("barcode", "")))
            self.table.setItem(r, 2, QTableWidgetItem(p.get("name", "")))
            self.table.setItem(r, 3, QTableWidgetItem(p.get("unit", "Adet")))
            self.table.setItem(r, 4, QTableWidgetItem(
                f"{float(p.get('purchase_price', 0)):.2f} ₺"
            ))
            self.table.setItem(r, 5, QTableWidgetItem(
                f"{float(p.get('price', 0)):.2f} ₺"
            ))
            self.table.setItem(r, 6, QTableWidgetItem(
                str(p.get("stock", 0))
            ))
            self.table.setRowHeight(r, 24)
        self._filtered = data
        self.lbl_count.setText(f"{len(data)} kayıt")

    def _filter(self, text: str):
        text = text.lower().strip()
        if not text:
            self._load_table(self.products)
            return
        filtered = [
            p for p in self.products
            if text in p.get("code", "").lower()
            or text in p.get("name", "").lower()
            or text in p.get("barcode", "").lower()
        ]
        self._load_table(filtered)

    def _get_selected(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered):
            return None
        return self._filtered[row]

    def _on_select(self):
        p = self._get_selected()
        if not p:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir ürün seçin.")
            return
        self.product_selected.emit(p)
        self.accept()

    def _on_double_click(self, index):
        row = index.row()
        if 0 <= row < len(self._filtered):
            self.product_selected.emit(self._filtered[row])
            self.accept()


# ─────────────────────────────────────────────
# ANA WIDGET
# ─────────────────────────────────────────────

class HareketKalemleriWidget(QWidget):
    """
    Fiş detay kalem giriş tablosu widget'ı.

    Sinyaller:
        totals_changed: Toplam hesaplanması gerektiğinde
        row_added(int): Satır eklendiğinde
        row_removed(int): Satır silindiğinde
    """

    totals_changed = pyqtSignal()
    row_added      = pyqtSignal(int)
    row_removed    = pyqtSignal(int)

    COMBO_STYLE = """
        QComboBox {
            border:1px solid #cbd5e1; border-radius:3px;
            padding:0 3px; font-size:9px; background:#fff;
            min-height:0px;
        }
        QComboBox QAbstractItemView {
            background:#1e293b; color:#ffffff;
            selection-background-color:#3b82f6;
        }
    """
    FIELD_STYLE = """
        QLineEdit {
            border:1px solid #cbd5e1; border-radius:3px;
            padding:0 3px; font-size:9px; background:#fff;
        }
    """

    def __init__(
        self,
        products_catalog: list[dict] | None = None,
        db_session=None,
        profile_key: str = "hareket_kalemleri",
        theme_row_height: int = 26,
        parent=None,
    ):
        super().__init__(parent)
        self.db               = db_session
        self.profile_key      = profile_key
        self.row_height       = theme_row_height
        self._sort_col        = -1
        self._sort_asc        = True
        self._currencies      = DEFAULT_CURRENCIES
        self._units           = DEFAULT_UNITS

        # Ürün kataloğu — DB yoksa dışarıdan verilir
        self.products_catalog = products_catalog or []

        # DB varsa ürünleri yükle
        if self.db and not self.products_catalog:
            self._load_products_from_db()

        self._init_ui()
        self._init_shortcuts()
        self._load_profile()
        self.add_row()

    # ─────────────────────────────────────────────
    # DB'DEN ÜRÜN YÜKLEMESİ
    # ─────────────────────────────────────────────

    def _load_products_from_db(self):
        """DB'den stok kartlarını yükle."""
        try:
            from sqlalchemy import select
            from src.core.models import Product
            rows = self.db.scalars(
                select(Product).where(Product.is_deleted == False)
            ).all()
            self.products_catalog = [
                {
                    "code":           p.sku or f"STK-{p.id}",
                    "barcode":        getattr(p, "barcode", "") or "",
                    "name":           p.name or "",
                    "unit":           getattr(p, "unit", "Adet") or "Adet",
                    "purchase_price": float(getattr(p, "purchase_price", 0) or 0),
                    "price":          float(p.sale_price or 0),
                    "vat":            int(getattr(p, "vat_rate", 20) or 20),
                    "stock":          float(p.stock_quantity or 0),
                    "id":             p.id,
                }
                for p in rows
            ]
            logger.info(f"{len(self.products_catalog)} ürün yüklendi")
        except Exception as e:
            logger.warning(f"Ürünler DB'den yüklenemedi: {e}")

    def refresh_products(self):
        """Ürün listesini DB'den yenile ve completers'ı güncelle."""
        if self.db:
            self._load_products_from_db()
            self._update_completers()

    def _update_completers(self):
        """Tüm satırlardaki autocomplete listelerini güncelle."""
        codes = [p["code"] for p in self.products_catalog]
        names = [p["name"] for p in self.products_catalog]
        for r in range(self.table.rowCount()):
            kod_w = self.table.cellWidget(r, COL_KOD)
            if kod_w:
                le = kod_w.findChild(QLineEdit)
                if le and le.completer():
                    from PyQt6.QtCore import QStringListModel
                    le.completer().setModel(QStringListModel(codes))
            acik = self.table.cellWidget(r, COL_ACIK)
            if isinstance(acik, QLineEdit) and acik.completer():
                from PyQt6.QtCore import QStringListModel
                acik.completer().setModel(QStringListModel(names))

    # ─────────────────────────────────────────────
    # DIŞARIDAN GÜNCELLEME
    # ─────────────────────────────────────────────

    def set_currencies(self, currencies: list[str]):
        """
        HareketFinansWidget'tan döviz listesini al.
        Her satırdaki döviz combo'yu güncelle.
        """
        self._currencies = currencies
        for r in range(self.table.rowCount()):
            cmb = self.table.cellWidget(r, COL_DOVIZ)
            if isinstance(cmb, QComboBox):
                current = cmb.currentText()
                cmb.blockSignals(True)
                cmb.clear()
                cmb.addItems(currencies)
                idx = cmb.findText(current)
                cmb.setCurrentIndex(idx if idx >= 0 else 0)
                cmb.blockSignals(False)

    def set_units(self, units: list[str]):
        """
        Genel Ayarlar'dan birim listesini al.
        Yeni satır eklenince bu liste kullanılır.
        """
        self._units = units

    # ─────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────

    def _init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(0)

        self.table = QTableWidget(0, len(COLUMN_NAMES))
        self.table.setHorizontalHeaderLabels(COLUMN_NAMES)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        hh = self.table.horizontalHeader()
        hh.setFixedHeight(26)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        hh.setSectionResizeMode(COL_DEL,  QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(COL_ACIK, QHeaderView.ResizeMode.Stretch)
        hh.setMinimumSectionSize(20)
        hh.sectionClicked.connect(self._on_header_clicked)
        hh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._show_header_menu)

        vh = self.table.verticalHeader()
        vh.setVisible(True)
        vh.setDefaultSectionSize(self.row_height)
        vh.setMinimumSectionSize(self.row_height)
        vh.setMaximumSectionSize(self.row_height)
        vh.setSectionsMovable(True)

        self._set_default_widths()

        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border:1px solid #cbd5e1;
                background-color:#ffffff;
                gridline-color:#e2e8f0;
                font-family:'Segoe UI';
                font-size:10px;
                color:#0f172a;
                alternate-background-color:#f8fafc;
            }
            QHeaderView::section {
                background-color:#1e3a8a;
                color:#ffffff;
                padding:2px 4px;
                border:none;
                border-right:1px solid #2d4fa0;
                font-weight:bold;
                font-size:9px;
            }
            QHeaderView::section:vertical {
                background-color:#f8fafc;
                color:#64748b;
                font-size:9px;
                padding:1px 4px;
            }
            QTableWidget::item:selected {
                background-color:#dbeafe;
                color:#1e40af;
            }
        """)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_body_menu)
        lyt.addWidget(self.table)

    def _set_default_widths(self):
        hh = self.table.horizontalHeader()
        widths = {
            COL_DEL:24, COL_TUR:90, COL_BARKOD:80, COL_KOD:90,
            COL_NOT2:80, COL_MIKTAR:55, COL_BIRIM:50, COL_FIYAT:70,
            COL_DOVIZ:55, COL_ISK1P:45, COL_ISK1T:60, COL_ISK2P:45,
            COL_ISK2T:60, COL_ISK3P:45, COL_ISK3T:60,
            COL_KDVP:50, COL_TEV:60, COL_TUTAR:75,
        }
        for col, w in widths.items():
            self.table.setColumnWidth(col, w)
            if col not in (COL_DEL, COL_ACIK):
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(COL_DEL, 24)

    def _init_shortcuts(self):
        QShortcut(QKeySequence("Alt+Return"), self).activated.connect(
            lambda: self.add_row()
        )
        QShortcut(QKeySequence("Ctrl+Delete"), self).activated.connect(
            self.delete_selected_rows
        )
        QShortcut(QKeySequence("Alt+Up"), self).activated.connect(
            lambda: self.move_row_up(self.table.currentRow())
        )
        QShortcut(QKeySequence("Alt+Down"), self).activated.connect(
            lambda: self.move_row_down(self.table.currentRow())
        )

    # ─────────────────────────────────────────────
    # SATIR EKLEME
    # ─────────────────────────────────────────────

    def add_row(
        self,
        item_type: str = "Malzeme",
        barcode: str = "",
        code: str = "",
        name: str = "",
        note2: str = "",
        qty: float = 1.0,
        unit: str = "Adet",
        price: float = 0.0,
        currency: str = "TRY",
        vat: int = 20,
        disc1: float = 0.0,
        disc2: float = 0.0,
        disc3: float = 0.0,
        insert_at: int | None = None,
    ) -> int:
        row = self.table.rowCount() if insert_at is None else insert_at
        self.table.insertRow(row)
        RH = self.row_height
        self.table.setRowHeight(row, RH)
        WH = RH - 2

        # 0: Sil
        btn_del = QPushButton("🗑")
        btn_del.setFixedSize(22, WH)
        btn_del.setStyleSheet(
            "background:transparent;color:#ef4444;border:none;font-size:11px;"
        )
        btn_del.clicked.connect(
            lambda _, b=btn_del: self._safe_remove_row(
                self._find_widget_row(b)
            )
        )
        self.table.setCellWidget(row, COL_DEL, btn_del)

        # 1: Türü
        cmb_tur = QComboBox()
        cmb_tur.addItems(ITEM_TYPES)
        cmb_tur.setCurrentText(item_type)
        cmb_tur.setFixedHeight(WH)
        cmb_tur.setStyleSheet(self.COMBO_STYLE)
        cmb_tur.currentTextChanged.connect(
            lambda t, r=row: self._on_type_changed(r, t)
        )
        self.table.setCellWidget(row, COL_TUR, cmb_tur)

        # 2: Barkod
        txt_barkod = QLineEdit(barcode)
        txt_barkod.setFixedHeight(WH)
        txt_barkod.setStyleSheet(self.FIELD_STYLE)
        txt_barkod.editingFinished.connect(
            lambda r=row: self._on_barcode_entered(r)
        )
        self.table.setCellWidget(row, COL_BARKOD, txt_barkod)

        # 3: Stok Kodu + ... butonu
        kod_frame = QFrame()
        kod_frame.setStyleSheet("background:transparent;border:none;")
        kod_lyt = QHBoxLayout(kod_frame)
        kod_lyt.setContentsMargins(0, 0, 0, 0)
        kod_lyt.setSpacing(1)

        txt_kod = QLineEdit(code)
        txt_kod.setFixedHeight(WH)
        txt_kod.setStyleSheet(self.FIELD_STYLE + "font-weight:bold;")
        txt_kod.setPlaceholderText("Stok kodu...")

        # Autocomplete — stok kodları
        codes = [p["code"] for p in self.products_catalog]
        comp_kod = QCompleter(codes, self)
        comp_kod.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_kod.setFilterMode(Qt.MatchFlag.MatchContains)
        comp_kod.activated.connect(
            lambda sel, r=row: self._on_code_selected(r, sel)
        )
        txt_kod.setCompleter(comp_kod)
        txt_kod.editingFinished.connect(
            lambda r=row: self._on_code_editing_finished(r)
        )

        btn_stok = QPushButton("...")
        btn_stok.setFixedSize(18, WH)
        btn_stok.setToolTip("Stok listesinden seç (F10)")
        btn_stok.setStyleSheet(
            "background:#e2e8f0;border:1px solid #cbd5e1;"
            "border-radius:2px;font-size:9px;padding:0;"
        )
        btn_stok.clicked.connect(lambda _, r=row: self._open_stock_dialog(r))

        kod_lyt.addWidget(txt_kod)
        kod_lyt.addWidget(btn_stok)
        self.table.setCellWidget(row, COL_KOD, kod_frame)

        # 4: Açıklama — direkt QLineEdit (Stretch)
        txt_acik = QLineEdit(name)
        txt_acik.setFixedHeight(WH)
        txt_acik.setStyleSheet(self.FIELD_STYLE + "font-weight:600;")
        txt_acik.setPlaceholderText("Ürün adı / açıklama...")
        names = [p["name"] for p in self.products_catalog]
        comp_name = QCompleter(names, self)
        comp_name.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_name.setFilterMode(Qt.MatchFlag.MatchContains)
        comp_name.activated.connect(
            lambda sel, r=row: self._on_name_selected(r, sel)
        )
        txt_acik.setCompleter(comp_name)
        txt_acik.textChanged.connect(self.totals_changed)
        self.table.setCellWidget(row, COL_ACIK, txt_acik)

        # 5: Satır Notu 2
        txt_not2 = QLineEdit(note2)
        txt_not2.setFixedHeight(WH)
        txt_not2.setStyleSheet(self.FIELD_STYLE)
        txt_not2.setPlaceholderText("Not 2...")
        self.table.setCellWidget(row, COL_NOT2, txt_not2)

        # 6: Miktar
        txt_miktar = QLineEdit(str(qty))
        txt_miktar.setFixedHeight(WH)
        txt_miktar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_miktar.setStyleSheet(self.FIELD_STYLE + "font-weight:bold;")
        txt_miktar.textChanged.connect(self._on_value_changed)
        self.table.setCellWidget(row, COL_MIKTAR, txt_miktar)

        # 7: Birim — QComboBox (birim listesinden)
        cmb_birim = QComboBox()
        cmb_birim.addItems(self._units)
        idx_unit = cmb_birim.findText(unit)
        cmb_birim.setCurrentIndex(idx_unit if idx_unit >= 0 else 0)
        cmb_birim.setFixedHeight(WH)
        cmb_birim.setStyleSheet(self.COMBO_STYLE)
        cmb_birim.currentIndexChanged.connect(self._on_value_changed)
        self.table.setCellWidget(row, COL_BIRIM, cmb_birim)

        # 8: B.Fiyat
        txt_fiyat = QLineEdit(f"{price:.2f}")
        txt_fiyat.setFixedHeight(WH)
        txt_fiyat.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        txt_fiyat.setStyleSheet(self.FIELD_STYLE + "font-weight:bold;")
        txt_fiyat.textChanged.connect(self._on_value_changed)
        txt_fiyat.returnPressed.connect(lambda: self.add_row())
        self.table.setCellWidget(row, COL_FIYAT, txt_fiyat)

        # 9: Döviz
        cmb_dov = QComboBox()
        cmb_dov.addItems(self._currencies)
        idx_cur = cmb_dov.findText(currency)
        cmb_dov.setCurrentIndex(idx_cur if idx_cur >= 0 else 0)
        cmb_dov.setFixedHeight(WH)
        cmb_dov.setStyleSheet(self.COMBO_STYLE)
        cmb_dov.currentIndexChanged.connect(self._on_value_changed)
        self.table.setCellWidget(row, COL_DOVIZ, cmb_dov)

        # 10-15: İskonto 1/2/3 % ve Tutarları
        for col_p, col_t, val in [
            (COL_ISK1P, COL_ISK1T, disc1),
            (COL_ISK2P, COL_ISK2T, disc2),
            (COL_ISK3P, COL_ISK3T, disc3),
        ]:
            txt_p = QLineEdit(str(val))
            txt_p.setFixedHeight(WH)
            txt_p.setAlignment(Qt.AlignmentFlag.AlignCenter)
            txt_p.setStyleSheet(self.FIELD_STYLE)
            txt_p.textChanged.connect(self._on_value_changed)
            self.table.setCellWidget(row, col_p, txt_p)

            lbl_t = QLabel("0,00")
            lbl_t.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lbl_t.setStyleSheet(
                "color:#dc2626;font-weight:bold;font-size:9px;padding-right:3px;"
            )
            self.table.setCellWidget(row, col_t, lbl_t)

        # 16: KDV %
        cmb_kdv = QComboBox()
        cmb_kdv.addItems(VAT_RATES)
        idx_vat = cmb_kdv.findText(f"% {vat}")
        cmb_kdv.setCurrentIndex(idx_vat if idx_vat >= 0 else 0)
        cmb_kdv.setFixedHeight(WH)
        cmb_kdv.setStyleSheet(self.COMBO_STYLE)
        cmb_kdv.currentIndexChanged.connect(self._on_value_changed)
        self.table.setCellWidget(row, COL_KDVP, cmb_kdv)

        # 17: Tevkifat
        cmb_tev = QComboBox()
        cmb_tev.addItems(WITHHOLDING)
        cmb_tev.setFixedHeight(WH)
        cmb_tev.setStyleSheet(self.COMBO_STYLE)
        cmb_tev.currentIndexChanged.connect(self._on_value_changed)
        self.table.setCellWidget(row, COL_TEV, cmb_tev)

        # 18: Tutar
        lbl_tutar = QLabel("0,00 ₺")
        lbl_tutar.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        lbl_tutar.setStyleSheet(
            "color:#1e3a8a;font-weight:800;font-size:10px;padding-right:4px;"
        )
        self.table.setCellWidget(row, COL_TUTAR, lbl_tutar)

        self._on_value_changed()
        self.row_added.emit(row)
        return row

    def _find_widget_row(self, widget: QWidget) -> int:
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                w = self.table.cellWidget(r, c)
                if w is widget:
                    return r
                if w and widget in w.findChildren(type(widget)):
                    return r
        return self.table.currentRow()

    # ─────────────────────────────────────────────
    # STOK ARAMA
    # ─────────────────────────────────────────────

    def _open_stock_dialog(self, row: int):
        """... butonuna tıklanınca tam stok listesi dialog açılır."""
        # DB'den güncel listeyi al
        if self.db:
            self._load_products_from_db()

        if not self.products_catalog:
            QMessageBox.information(
                self, "Stok Yok",
                "Stok kataloğu boş.\n"
                "Genel Ayarlar > Stok Tanımları'ndan ürün ekleyin."
            )
            return

        dlg = StokSecimDialog(self.products_catalog, parent=self)
        dlg.product_selected.connect(
            lambda p, r=row: self._apply_product(r, p)
        )
        dlg.exec()

    def _on_barcode_entered(self, row: int):
        """Barkod alanına yazınca DB'de sorgula."""
        barkod_w = self.table.cellWidget(row, COL_BARKOD)
        if not isinstance(barkod_w, QLineEdit):
            return
        barcode = barkod_w.text().strip()
        if not barcode:
            return

        # Katalogda ara
        p = next(
            (x for x in self.products_catalog if x.get("barcode") == barcode),
            None
        )
        # DB'de ara
        if not p and self.db:
            try:
                from sqlalchemy import select
                from src.core.models import Product
                prod = self.db.scalar(
                    select(Product).where(
                        Product.barcode == barcode,
                        Product.is_deleted == False,
                    )
                )
                if prod:
                    p = {
                        "code":    prod.sku or "",
                        "barcode": prod.barcode or "",
                        "name":    prod.name or "",
                        "unit":    getattr(prod, "unit", "Adet") or "Adet",
                        "price":   float(prod.sale_price or 0),
                        "vat":     int(getattr(prod, "vat_rate", 20) or 20),
                        "stock":   float(prod.stock_quantity or 0),
                    }
            except Exception as e:
                logger.warning(f"Barkod sorgusu: {e}")

        if p:
            self._apply_product(row, p)

    def _on_code_editing_finished(self, row: int):
        """Stok kodu alanından çıkılınca DB'de sorgula."""
        kod_w = self.table.cellWidget(row, COL_KOD)
        if not kod_w:
            return
        le = kod_w.findChild(QLineEdit)
        if not le:
            return
        code = le.text().strip()
        if not code:
            return

        p = next(
            (x for x in self.products_catalog if x.get("code") == code),
            None
        )
        if not p and self.db:
            try:
                from sqlalchemy import select
                from src.core.models import Product
                prod = self.db.scalar(
                    select(Product).where(
                        Product.sku == code,
                        Product.is_deleted == False,
                    )
                )
                if prod:
                    p = {
                        "code":    prod.sku or "",
                        "barcode": getattr(prod, "barcode", "") or "",
                        "name":    prod.name or "",
                        "unit":    getattr(prod, "unit", "Adet") or "Adet",
                        "price":   float(prod.sale_price or 0),
                        "vat":     int(getattr(prod, "vat_rate", 20) or 20),
                        "stock":   float(prod.stock_quantity or 0),
                    }
            except Exception as e:
                logger.warning(f"Kod sorgusu: {e}")

        if p:
            self._apply_product(row, p)

    def _on_code_selected(self, row: int, code: str):
        p = next(
            (x for x in self.products_catalog if x["code"] == code), None
        )
        if p:
            self._apply_product(row, p)

    def _on_name_selected(self, row: int, name: str):
        p = next(
            (x for x in self.products_catalog if x["name"] == name), None
        )
        if p:
            self._apply_product(row, p)

    def _apply_product(self, row: int, p: dict):
        """Seçilen ürünü satıra yaz."""
        # Stok kodu
        kod_w = self.table.cellWidget(row, COL_KOD)
        if kod_w:
            le = kod_w.findChild(QLineEdit)
            if le:
                le.setText(p.get("code", ""))

        # Barkod
        barkod_w = self.table.cellWidget(row, COL_BARKOD)
        if isinstance(barkod_w, QLineEdit):
            barkod_w.setText(p.get("barcode", ""))

        # Açıklama
        acik = self.table.cellWidget(row, COL_ACIK)
        if isinstance(acik, QLineEdit):
            acik.setText(p.get("name", ""))

        # Birim
        birim_w = self.table.cellWidget(row, COL_BIRIM)
        if isinstance(birim_w, QComboBox):
            idx = birim_w.findText(p.get("unit", "Adet"))
            if idx >= 0:
                birim_w.setCurrentIndex(idx)

        # Fiyat
        fiyat_w = self.table.cellWidget(row, COL_FIYAT)
        if isinstance(fiyat_w, QLineEdit):
            fiyat_w.setText(f"{float(p.get('price', 0)):.2f}")

        # KDV
        kdv_w = self.table.cellWidget(row, COL_KDVP)
        if isinstance(kdv_w, QComboBox):
            idx = kdv_w.findText(f"% {p.get('vat', 20)}")
            if idx >= 0:
                kdv_w.setCurrentIndex(idx)

        # Stok tooltip
        stock = p.get("stock", 0)
        acik_w = self.table.cellWidget(row, COL_ACIK)
        if acik_w:
            acik_w.setToolTip(
                f"Kod: {p.get('code', '')}\n"
                f"Barkod: {p.get('barcode', '')}\n"
                f"Mevcut Stok: {stock}\n"
                f"Alış Fiyatı: {p.get('purchase_price', 0):.2f} ₺\n"
                f"Satış Fiyatı: {p.get('price', 0):.2f} ₺"
            )

        self._on_value_changed()

    def _on_type_changed(self, row: int, new_type: str):
        kod_w = self.table.cellWidget(row, COL_KOD)
        le = kod_w.findChild(QLineEdit) if kod_w else None
        acik = self.table.cellWidget(row, COL_ACIK)
        if new_type == "Serbest Giriş":
            if le:
                le.setPlaceholderText("Serbest Kod")
            if acik:
                acik.setPlaceholderText("Serbest Açıklama Yazın...")
        else:
            if le:
                le.setPlaceholderText("Stok kodu...")
            if acik:
                acik.setPlaceholderText("Ürün adı / açıklama...")

    # ─────────────────────────────────────────────
    # SATIR SİLME / TAŞIMA
    # ─────────────────────────────────────────────

    def _safe_remove_row(self, row: int):
        if self.table.rowCount() <= 1:
            self._clear_row(row)
            return
        self.table.removeRow(row)
        self._on_value_changed()
        self.row_removed.emit(row)

    def _clear_row(self, row: int):
        self.set_row_data(row, {
            "item_type": "Malzeme", "barcode": "", "code": "",
            "name": "", "note2": "", "qty": 1.0, "unit": "Adet",
            "price": 0.0, "currency": "TRY",
            "disc1": 0.0, "disc2": 0.0, "disc3": 0.0, "vat": 20,
        })
        self._on_value_changed()

    def delete_selected_rows(self):
        rows = sorted(
            {idx.row() for idx in self.table.selectionModel().selectedRows()},
            reverse=True,
        )
        if not rows:
            return
        if self.table.rowCount() - len(rows) < 1:
            QMessageBox.warning(self, "Uyarı", "En az 1 satır kalmalıdır.")
            return
        reply = QMessageBox.question(
            self, "Toplu Sil",
            f"{len(rows)} satır silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for r in rows:
                self.table.removeRow(r)
            self._on_value_changed()

    def move_row_up(self, row: int | None = None):
        r = row if row is not None else self.table.currentRow()
        if r <= 0:
            return
        d1, d2 = self.get_row_data(r), self.get_row_data(r - 1)
        self.set_row_data(r - 1, d1)
        self.set_row_data(r, d2)
        self.table.selectRow(r - 1)
        self._on_value_changed()

    def move_row_down(self, row: int | None = None):
        r = row if row is not None else self.table.currentRow()
        if r < 0 or r >= self.table.rowCount() - 1:
            return
        d1, d2 = self.get_row_data(r), self.get_row_data(r + 1)
        self.set_row_data(r + 1, d1)
        self.set_row_data(r, d2)
        self.table.selectRow(r + 1)
        self._on_value_changed()

    # ─────────────────────────────────────────────
    # SIRALAMA
    # ─────────────────────────────────────────────

    def _on_header_clicked(self, col: int):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self.sort_by_column(col, self._sort_asc)

    def sort_by_column(self, col: int, ascending: bool = True):
        rc = self.table.rowCount()
        if rc <= 1:
            return
        rows_data = [self.get_row_data(r) for r in range(rc)]
        col_key = {
            COL_TUR: "item_type", COL_BARKOD: "barcode",
            COL_KOD: "code",     COL_ACIK: "name",
            COL_MIKTAR: "qty",   COL_FIYAT: "price",
            COL_ISK1P: "disc1",  COL_ISK2P: "disc2",
        }.get(col, "name")

        def sv(d):
            v = d.get(col_key, "")
            try:
                return float(str(v).replace(",", "."))
            except Exception:
                return str(v).lower()

        rows_data.sort(key=sv, reverse=not ascending)
        for r, d in enumerate(rows_data):
            self.set_row_data(r, d)
        self._on_value_changed()

    # ─────────────────────────────────────────────
    # SAĞ TIK MENÜSÜ
    # ─────────────────────────────────────────────

    def _menu_style(self) -> str:
        return """
            QMenu {
                background:#ffffff; border:1px solid #cbd5e1;
                font-size:10px; padding:2px;
            }
            QMenu::item { padding:5px 20px 5px 10px; }
            QMenu::item:selected { background:#2563eb; color:#ffffff; }
            QMenu::separator { height:1px; background:#e2e8f0; margin:2px 0; }
        """

    def _show_body_menu(self, pos):
        row = self.table.currentRow()
        col = self.table.currentColumn()
        can_del = self.table.rowCount() > 1
        sel_count = len(self.table.selectionModel().selectedRows())

        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())

        act_add    = QAction("➕ Satır Ekle (Alt+Enter)", self)
        act_insert = QAction("➕ Araya Satır Ekle", self)
        act_del    = QAction("🗑️ Satırı Sil", self)
        act_del.setEnabled(can_del and row >= 0)
        act_bulk   = QAction("🗑️ Seçilenleri Sil (Ctrl+Del)", self)
        act_bulk.setEnabled(can_del and sel_count > 1)
        act_up     = QAction("⬆️ Yukarı Taşı (Alt+↑)", self)
        act_down   = QAction("⬇️ Aşağı Taşı (Alt+↓)", self)
        act_stok   = QAction("📦 Stok Listesinden Seç", self)

        menu.addAction(act_add)
        menu.addAction(act_insert)
        menu.addAction(act_del)
        menu.addAction(act_bulk)
        menu.addSeparator()
        menu.addAction(act_up)
        menu.addAction(act_down)
        menu.addSeparator()
        menu.addAction(act_stok)
        menu.addSeparator()

        if col >= 0:
            col_name = COLUMN_NAMES[col] if col < len(COLUMN_NAMES) else ""
            act_asc  = QAction(f"🔼 '{col_name}' Artan", self)
            act_desc = QAction(f"🔽 '{col_name}' Azalan", self)
            act_hide = QAction(f"🙈 '{col_name}' Gizle", self)
            menu.addAction(act_asc)
            menu.addAction(act_desc)
            menu.addSeparator()
            menu.addAction(act_hide)

        hidden = [
            i for i in range(self.table.columnCount())
            if self.table.isColumnHidden(i)
        ]
        if hidden:
            show_m = menu.addMenu("👁️ Gizli Sütunları Göster")
            for hc in hidden:
                hn = COLUMN_NAMES[hc] if hc < len(COLUMN_NAMES) else str(hc)
                a = QAction(hn, self)
                a.triggered.connect(
                    lambda _, c=hc: self.table.setColumnHidden(c, False)
                )
                show_m.addAction(a)

        menu.addSeparator()
        act_save  = QAction("💾 Görünümü Kaydet", self)
        act_reset = QAction("↩️ Görünümü Sıfırla", self)
        menu.addAction(act_save)
        menu.addAction(act_reset)

        act_add.triggered.connect(lambda: self.add_row())
        act_insert.triggered.connect(lambda: self.add_row(insert_at=max(0, row)))
        act_del.triggered.connect(lambda: self._safe_remove_row(row))
        act_bulk.triggered.connect(self.delete_selected_rows)
        act_up.triggered.connect(lambda: self.move_row_up(row))
        act_down.triggered.connect(lambda: self.move_row_down(row))
        act_stok.triggered.connect(lambda: self._open_stock_dialog(row))
        act_save.triggered.connect(self._save_profile)
        act_reset.triggered.connect(self._reset_widths)

        if col >= 0:
            act_asc.triggered.connect(lambda: self.sort_by_column(col, True))
            act_desc.triggered.connect(lambda: self.sort_by_column(col, False))
            act_hide.triggered.connect(
                lambda: self.table.setColumnHidden(col, True)
            )

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _show_header_menu(self, pos):
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        col_name = COLUMN_NAMES[col] if col < len(COLUMN_NAMES) else str(col)

        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())

        act_asc  = QAction("🔼 Artan Sırala", self)
        act_desc = QAction("🔽 Azalan Sırala", self)
        act_hide = QAction(f"🙈 '{col_name}' Gizle", self)
        menu.addAction(act_asc)
        menu.addAction(act_desc)
        menu.addSeparator()
        menu.addAction(act_hide)

        hidden = [
            i for i in range(self.table.columnCount())
            if self.table.isColumnHidden(i)
        ]
        if hidden:
            menu.addSeparator()
            show_m = menu.addMenu("👁️ Gizlileri Göster")
            for hc in hidden:
                hn = COLUMN_NAMES[hc] if hc < len(COLUMN_NAMES) else str(hc)
                a = QAction(hn, self)
                a.triggered.connect(
                    lambda _, c=hc: self.table.setColumnHidden(c, False)
                )
                show_m.addAction(a)

        menu.addSeparator()
        act_save  = QAction("💾 Görünümü Kaydet", self)
        act_reset = QAction("↩️ Sıfırla", self)
        menu.addAction(act_save)
        menu.addAction(act_reset)

        act_asc.triggered.connect(lambda: self.sort_by_column(col, True))
        act_desc.triggered.connect(lambda: self.sort_by_column(col, False))
        act_hide.triggered.connect(lambda: self.table.setColumnHidden(col, True))
        act_save.triggered.connect(self._save_profile)
        act_reset.triggered.connect(self._reset_widths)

        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    # ─────────────────────────────────────────────
    # VERİ OKUMA / YAZMA
    # ─────────────────────────────────────────────

    def get_row_data(self, row: int) -> dict[str, Any]:
        def txt(col):
            w = self.table.cellWidget(row, col)
            if isinstance(w, QLineEdit):  return w.text()
            if isinstance(w, QComboBox):  return w.currentText()
            if isinstance(w, QLabel):     return w.text()
            return ""

        def flt(col):
            try:
                return float(txt(col).replace(",", ".") or "0")
            except Exception:
                return 0.0

        kod_w = self.table.cellWidget(row, COL_KOD)
        kod = ""
        if kod_w:
            le = kod_w.findChild(QLineEdit)
            kod = le.text() if le else ""

        return {
            "item_type": txt(COL_TUR),
            "barcode":   txt(COL_BARKOD),
            "code":      kod,
            "name":      txt(COL_ACIK),
            "note2":     txt(COL_NOT2),
            "qty":       flt(COL_MIKTAR),
            "unit":      txt(COL_BIRIM),
            "price":     flt(COL_FIYAT),
            "currency":  txt(COL_DOVIZ),
            "disc1":     flt(COL_ISK1P),
            "disc2":     flt(COL_ISK2P),
            "disc3":     flt(COL_ISK3P),
            "vat":       int(txt(COL_KDVP).replace("%", "").strip() or "20"),
            "tevkifat":  txt(COL_TEV),
        }

    def set_row_data(self, row: int, data: dict):
        def sl(col, val):
            w = self.table.cellWidget(row, col)
            if isinstance(w, QLineEdit):
                w.setText(str(val))

        def sc(col, val):
            w = self.table.cellWidget(row, col)
            if isinstance(w, QComboBox):
                idx = w.findText(str(val))
                if idx >= 0:
                    w.setCurrentIndex(idx)

        sc(COL_TUR, data.get("item_type", "Malzeme"))
        sl(COL_BARKOD, data.get("barcode", ""))

        kod_w = self.table.cellWidget(row, COL_KOD)
        if kod_w:
            le = kod_w.findChild(QLineEdit)
            if le:
                le.setText(data.get("code", ""))

        sl(COL_ACIK, data.get("name", ""))
        sl(COL_NOT2, data.get("note2", ""))
        sl(COL_MIKTAR, str(data.get("qty", 1.0)))
        sc(COL_BIRIM, data.get("unit", "Adet"))
        sl(COL_FIYAT, f"{float(data.get('price', 0)):.2f}")
        sc(COL_DOVIZ, data.get("currency", "TRY"))
        sl(COL_ISK1P, str(data.get("disc1", 0.0)))
        sl(COL_ISK2P, str(data.get("disc2", 0.0)))
        sl(COL_ISK3P, str(data.get("disc3", 0.0)))
        sc(COL_KDVP, f"% {data.get('vat', 20)}")
        sc(COL_TEV, data.get("tevkifat", "Yok"))

    def get_all_rows(self) -> list[dict]:
        return [
            self.get_row_data(r)
            for r in range(self.table.rowCount())
            if self.get_row_data(r).get("name")
            or self.get_row_data(r).get("code")
        ]

    def clear_rows(self):
        self.table.setRowCount(0)
        self.add_row()

    # ─────────────────────────────────────────────
    # TOPLAM HESAPLAMA
    # ─────────────────────────────────────────────

    def _on_value_changed(self):
        for r in range(self.table.rowCount()):
            self._calc_row_total(r)
        self.totals_changed.emit()

    def _calc_row_total(self, row: int) -> float:
        try:
            d     = self.get_row_data(row)
            qty   = float(d.get("qty",   1) or 1)
            price = float(d.get("price", 0) or 0)
            d1    = float(d.get("disc1", 0) or 0)
            d2    = float(d.get("disc2", 0) or 0)
            d3    = float(d.get("disc3", 0) or 0)
            vat   = float(d.get("vat",  20) or 20)

            base  = qty * price
            after = base * (1-d1/100) * (1-d2/100) * (1-d3/100)
            total = round(after * (1 + vat/100), 2)

            d1_amt = round(base - base*(1-d1/100), 2)
            d2_amt = round(base*(1-d1/100) - base*(1-d1/100)*(1-d2/100), 2)
            d3_amt = round(after/(1-d3/100)*d3/100 if d3 > 0 else 0, 2)

            for col, val in [
                (COL_ISK1T, d1_amt),
                (COL_ISK2T, d2_amt),
                (COL_ISK3T, d3_amt),
            ]:
                lbl = self.table.cellWidget(row, col)
                if isinstance(lbl, QLabel):
                    lbl.setText(
                        f"{val:,.2f}".replace(",","X").replace(".","," ).replace("X",".")
                    )

            lbl_tot = self.table.cellWidget(row, COL_TUTAR)
            if isinstance(lbl_tot, QLabel):
                sym = {"TRY":"₺","USD":"$","EUR":"€","GBP":"£"}.get(
                    d.get("currency","TRY"), "₺"
                )
                lbl_tot.setText(
                    f"{total:,.2f} {sym}".replace(",","X").replace(".","," ).replace("X",".")
                )
            return total
        except Exception:
            return 0.0

    # ─────────────────────────────────────────────
    # PROFİL
    # ─────────────────────────────────────────────

    def _save_profile(self):
        import json, os
        profile = {
            str(c): {
                "width":  self.table.columnWidth(c),
                "hidden": self.table.isColumnHidden(c),
            }
            for c in range(self.table.columnCount())
        }
        path = self._profile_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f)
        QMessageBox.information(self, "Kaydedildi", "Sütun görünümü kaydedildi.")

    def _load_profile(self):
        import json
        try:
            with open(self._profile_path(), encoding="utf-8") as f:
                profile = json.load(f)
            for c_str, info in profile.items():
                c = int(c_str)
                if 0 <= c < self.table.columnCount():
                    self.table.setColumnWidth(c, info.get("width", 60))
                    self.table.setColumnHidden(c, info.get("hidden", False))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Profil yüklenemedi: {e}")

    def _reset_widths(self):
        self._set_default_widths()
        for c in range(self.table.columnCount()):
            self.table.setColumnHidden(c, False)

    def _profile_path(self) -> str:
        import os
        return os.path.join(
            os.path.expanduser("~"), ".toya_erp", "profiles",
            f"{self.profile_key}.json"
        )

    def update_row_height(self, height: int):
        self.row_height = height
        vh = self.table.verticalHeader()
        vh.setDefaultSectionSize(height)
        vh.setMinimumSectionSize(height)
        vh.setMaximumSectionSize(height)
        for r in range(self.table.rowCount()):
            self.table.setRowHeight(r, height)
            for c in range(self.table.columnCount()):
                w = self.table.cellWidget(r, c)
                if w and not isinstance(w, QLabel):
                    w.setFixedHeight(height - 2)
