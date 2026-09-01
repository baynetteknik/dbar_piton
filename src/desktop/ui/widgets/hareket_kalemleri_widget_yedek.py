"""
ToyaUI — HareketKalemleriWidget
Fiş detay ekranındaki kalem giriş tablosu.

Bağımsız widget — transaction_document_dialog.py'de kullanılır.
Özellikler:
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
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Sütun indeksleri — sabit, değiştirilmez
COL_DEL    = 0   # 🗑️
COL_TUR    = 1   # Türü
COL_BARKOD = 2   # Barkod
COL_KOD    = 3   # Stok Kodu
COL_ACIK   = 4   # Açıklama (Stretch)
COL_NOT2   = 5   # Satır Notu 2
COL_MIKTAR = 6   # Miktar
COL_BIRIM  = 7   # Birim
COL_FIYAT  = 8   # B.Fiyat
COL_DOVIZ  = 9   # Döviz
COL_ISK1P  = 10  # İsk 1 %
COL_ISK1T  = 11  # İsk 1 Tutar
COL_ISK2P  = 12  # İsk 2 %
COL_ISK2T  = 13  # İsk 2 Tutar
COL_ISK3P  = 14  # İsk 3 %
COL_ISK3T  = 15  # İsk 3 Tutar
COL_KDVP   = 16  # KDV %
COL_TEV    = 17  # Tevkifat
COL_TUTAR  = 18  # Tutar

COLUMN_NAMES = [
    "🗑️", "Türü", "Barkod", "Stok Kodu",
    "Açıklama / Ürün Adı", "Satır Notu 2",
    "Miktar", "Birim", "B.Fiyat", "Döviz",
    "İsk 1 %", "İsk 1 Tutar",
    "İsk 2 %", "İsk 2 Tutar",
    "İsk 3 %", "İsk 3 Tutar",
    "KDV %", "Tevkifat", "Tutar",
]

ITEM_TYPES = ["Malzeme", "Hizmet", "Serbest Giriş"]
CURRENCIES = ["TRY", "USD", "EUR", "GBP"]
VAT_RATES  = ["% 20", "% 10", "% 1", "% 0"]
WITHHOLDING= ["Yok", "5/10", "7/10", "9/10", "10/10"]


class HareketKalemleriWidget(QWidget):
    """
    Fiş detay kalem giriş tablosu widget'ı.

    Sinyaller:
        totals_changed: Toplam hesaplanması gerektiğinde
        row_added(int): Satır eklendiğinde — satır indeksi
        row_removed(int): Satır silindiğinde — satır indeksi
    """

    totals_changed = pyqtSignal()
    row_added      = pyqtSignal(int)
    row_removed    = pyqtSignal(int)

    def __init__(
        self,
        products_catalog: list[dict] | None = None,
        profile_key: str = "hareket_kalemleri",
        theme_row_height: int = 26,
        parent=None,
    ):
        super().__init__(parent)
        self.products_catalog  = products_catalog or []
        self.profile_key       = profile_key
        self.row_height        = theme_row_height
        self._sort_col         = -1
        self._sort_asc         = True

        self._init_ui()
        self._init_shortcuts()
        self._load_profile()

        # Başlangıçta 1 boş satır
        self.add_row()

    # ─────────────────────────────────────────────
    # UI KURULUM
    # ─────────────────────────────────────────────

    def _init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(0)

        # Tablo
        self.table = QTableWidget(0, len(COLUMN_NAMES))
        self.table.setHorizontalHeaderLabels(COLUMN_NAMES)

        # Seçim
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )

        # Header
        hh = self.table.horizontalHeader()
        hh.setFixedHeight(26)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        hh.setSectionResizeMode(COL_DEL,   QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(COL_ACIK,  QHeaderView.ResizeMode.Stretch)
        hh.setMinimumSectionSize(20)
        hh.sectionClicked.connect(self._on_header_clicked)
        hh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._show_header_menu)

        # Satır header
        vh = self.table.verticalHeader()
        vh.setVisible(True)
        vh.setDefaultSectionSize(self.row_height)
        vh.setMinimumSectionSize(self.row_height)
        vh.setMaximumSectionSize(self.row_height)
        vh.setSectionsMovable(True)

        # Genişlikler
        self._set_default_widths()

        # Stil
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-family: 'Segoe UI';
                font-size: 10px;
                color: #0f172a;
                alternate-background-color: #f8fafc;
            }
            QHeaderView::section {
                background-color: #1e3a8a;
                color: #ffffff;
                padding: 2px 4px;
                border: none;
                border-right: 1px solid #2d4fa0;
                font-weight: bold;
                font-size: 9px;
            }
            QHeaderView::section:vertical {
                background-color: #f8fafc;
                color: #64748b;
                font-size: 9px;
                padding: 1px 4px;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
            }
        """)

        # Sağ tık
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_body_menu)

        lyt.addWidget(self.table)

    def _set_default_widths(self):
        hh = self.table.horizontalHeader()
        widths = {
            COL_DEL:    24,
            COL_TUR:    90,
            COL_BARKOD: 80,
            COL_KOD:    90,
            # COL_ACIK → Stretch
            COL_NOT2:   80,
            COL_MIKTAR: 55,
            COL_BIRIM:  50,
            COL_FIYAT:  70,
            COL_DOVIZ:  55,
            COL_ISK1P:  45,
            COL_ISK1T:  60,
            COL_ISK2P:  45,
            COL_ISK2T:  60,
            COL_ISK3P:  45,
            COL_ISK3T:  60,
            COL_KDVP:   50,
            COL_TEV:    60,
            COL_TUTAR:  75,
        }
        for col, w in widths.items():
            self.table.setColumnWidth(col, w)
            if col != COL_DEL and col != COL_ACIK:
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(COL_DEL, 24)

    def _init_shortcuts(self):
        QShortcut(QKeySequence("Alt+Return"), self).activated.connect(
            lambda: self.add_row(),
        )
        QShortcut(QKeySequence("Ctrl+Delete"), self).activated.connect(
            self.delete_selected_rows,
        )
        QShortcut(QKeySequence("Alt+Up"), self).activated.connect(
            lambda: self.move_row_up(self.table.currentRow()),
        )
        QShortcut(QKeySequence("Alt+Down"), self).activated.connect(
            lambda: self.move_row_down(self.table.currentRow()),
        )

    # ─────────────────────────────────────────────
    # SATIR EKLEME
    # ─────────────────────────────────────────────

    COMBO_STYLE = """
        QComboBox {
            border: 1px solid #cbd5e1; border-radius: 3px;
            padding: 0 3px; font-size: 9px; background: #fff;
            min-height: 0px;
        }
        QComboBox QAbstractItemView {
            background: #1e293b; color: #ffffff;
            selection-background-color: #3b82f6;
        }
    """
    FIELD_STYLE = """
        QLineEdit {
            border: 1px solid #cbd5e1; border-radius: 3px;
            padding: 0 3px; font-size: 9px; background: #fff;
        }
    """

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
        """Tabloya satır ekler, satır indeksini döndürür."""
        row = self.table.rowCount() if insert_at is None else insert_at
        self.table.insertRow(row)
        row_h = self.row_height
        self.table.setRowHeight(row, row_h)
        widget_h = row_h - 2

        # ── 0: Sil butonu ──
        btn_del = QPushButton("🗑")
        btn_del.setFixedSize(22, widget_h)
        btn_del.setStyleSheet(
            "background:transparent; color:#ef4444; border:none; font-size:11px;",
        )
        btn_del.clicked.connect(
            lambda _, r=row: self._safe_remove_row(
                self.table.indexAt(btn_del.parent().pos()).row()
                if False else self._find_widget_row(btn_del),
            ),
        )
        self.table.setCellWidget(row, COL_DEL, btn_del)

        # ── 1: Türü ──
        cmb_tur = QComboBox()
        cmb_tur.addItems(ITEM_TYPES)
        cmb_tur.setCurrentText(item_type)
        cmb_tur.setFixedHeight(widget_h)
        cmb_tur.setStyleSheet(self.COMBO_STYLE)
        cmb_tur.currentTextChanged.connect(
            lambda t, r=row: self._on_type_changed(r, t),
        )
        self.table.setCellWidget(row, COL_TUR, cmb_tur)

        # ── 2: Barkod ──
        txt_barkod = QLineEdit(barcode)
        txt_barkod.setFixedHeight(widget_h)
        txt_barkod.setStyleSheet(self.FIELD_STYLE)
        self.table.setCellWidget(row, COL_BARKOD, txt_barkod)

        # ── 3: Stok Kodu + ... ──
        kod_w = QWidget()
        kod_w.setFixedHeight(row_h)
        kod_lyt = QHBoxLayout(kod_w)
        kod_lyt.setContentsMargins(0, 0, 0, 0)
        kod_lyt.setSpacing(1)
        txt_kod = QLineEdit(code)
        txt_kod.setFixedHeight(widget_h)
        txt_kod.setStyleSheet(self.FIELD_STYLE + "font-weight:bold;")
        codes = [p["code"] for p in self.products_catalog]
        comp_kod = QCompleter(codes, self)
        comp_kod.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_kod.setFilterMode(Qt.MatchFlag.MatchContains)
        comp_kod.activated.connect(
            lambda sel, r=row: self._on_code_selected(r, sel),
        )
        txt_kod.setCompleter(comp_kod)
        btn_kod = QPushButton("...")
        btn_kod.setFixedSize(18, widget_h)
        btn_kod.setStyleSheet(
            "background:#e2e8f0;border:1px solid #cbd5e1;"
            "border-radius:2px;font-size:9px;padding:0;",
        )
        btn_kod.clicked.connect(lambda _, r=row: self._open_stock_lookup(r))
        kod_lyt.addWidget(txt_kod)
        kod_lyt.addWidget(btn_kod)
        self.table.setCellWidget(row, COL_KOD, kod_w)

        # ── 4: Açıklama (direkt QLineEdit, Stretch) ──
        txt_acik = QLineEdit(name)
        txt_acik.setFixedHeight(widget_h)
        txt_acik.setStyleSheet(self.FIELD_STYLE + "font-weight:600;")
        names = [p["name"] for p in self.products_catalog]
        comp_name = QCompleter(names, self)
        comp_name.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_name.setFilterMode(Qt.MatchFlag.MatchContains)
        comp_name.activated.connect(
            lambda sel, r=row: self._on_name_selected(r, sel),
        )
        txt_acik.setCompleter(comp_name)
        txt_acik.textChanged.connect(self.totals_changed)
        self.table.setCellWidget(row, COL_ACIK, txt_acik)

        # ── 5: Satır Notu 2 ──
        txt_not2 = QLineEdit(note2)
        txt_not2.setFixedHeight(widget_h)
        txt_not2.setStyleSheet(self.FIELD_STYLE)
        txt_not2.setPlaceholderText("Not 2...")
        self.table.setCellWidget(row, COL_NOT2, txt_not2)

        # ── 6: Miktar ──
        txt_miktar = QLineEdit(str(qty))
        txt_miktar.setFixedHeight(widget_h)
        txt_miktar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_miktar.setStyleSheet(self.FIELD_STYLE + "font-weight:bold;")
        txt_miktar.textChanged.connect(self._on_value_changed)
        self.table.setCellWidget(row, COL_MIKTAR, txt_miktar)

        # ── 7: Birim ──
        txt_birim = QLineEdit(unit)
        txt_birim.setFixedHeight(widget_h)
        txt_birim.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt_birim.setStyleSheet(self.FIELD_STYLE)
        self.table.setCellWidget(row, COL_BIRIM, txt_birim)

        # ── 8: B.Fiyat ──
        txt_fiyat = QLineEdit(f"{price:.2f}")
        txt_fiyat.setFixedHeight(widget_h)
        txt_fiyat.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        txt_fiyat.setStyleSheet(self.FIELD_STYLE + "font-weight:bold;")
        txt_fiyat.textChanged.connect(self._on_value_changed)
        txt_fiyat.returnPressed.connect(lambda: self.add_row())
        self.table.setCellWidget(row, COL_FIYAT, txt_fiyat)

        # ── 9: Döviz ──
        cmb_dov = QComboBox()
        cmb_dov.addItems(CURRENCIES)
        cmb_dov.setCurrentText(currency)
        cmb_dov.setFixedHeight(widget_h)
        cmb_dov.setStyleSheet(self.COMBO_STYLE)
        cmb_dov.currentIndexChanged.connect(self._on_value_changed)
        self.table.setCellWidget(row, COL_DOVIZ, cmb_dov)

        # ── 10-15: İskonto 1/2/3 % ve Tutarları ──
        for col_p, col_t, val in [
            (COL_ISK1P, COL_ISK1T, disc1),
            (COL_ISK2P, COL_ISK2T, disc2),
            (COL_ISK3P, COL_ISK3T, disc3),
        ]:
            txt_p = QLineEdit(str(val))
            txt_p.setFixedHeight(widget_h)
            txt_p.setAlignment(Qt.AlignmentFlag.AlignCenter)
            txt_p.setStyleSheet(self.FIELD_STYLE)
            txt_p.textChanged.connect(self._on_value_changed)
            self.table.setCellWidget(row, col_p, txt_p)

            lbl_t = QLabel("0,00")
            lbl_t.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_t.setStyleSheet(
                "color:#dc2626; font-weight:bold; font-size:9px;"
                "padding-right:3px;",
            )
            self.table.setCellWidget(row, col_t, lbl_t)

        # ── 16: KDV % ──
        cmb_kdv = QComboBox()
        cmb_kdv.addItems(VAT_RATES)
        cmb_kdv.setCurrentText(f"% {vat}")
        cmb_kdv.setFixedHeight(widget_h)
        cmb_kdv.setStyleSheet(self.COMBO_STYLE)
        cmb_kdv.currentIndexChanged.connect(self._on_value_changed)
        self.table.setCellWidget(row, COL_KDVP, cmb_kdv)

        # ── 17: Tevkifat ──
        cmb_tev = QComboBox()
        cmb_tev.addItems(WITHHOLDING)
        cmb_tev.setFixedHeight(widget_h)
        cmb_tev.setStyleSheet(self.COMBO_STYLE)
        cmb_tev.currentIndexChanged.connect(self._on_value_changed)
        self.table.setCellWidget(row, COL_TEV, cmb_tev)

        # ── 18: Tutar (salt okunur label) ──
        lbl_tutar = QLabel("0,00 ₺")
        lbl_tutar.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        lbl_tutar.setStyleSheet(
            "color:#1e3a8a; font-weight:800; font-size:10px; padding-right:4px;",
        )
        self.table.setCellWidget(row, COL_TUTAR, lbl_tutar)

        self._on_value_changed()
        self.row_added.emit(row)
        return row

    def _find_widget_row(self, widget: QWidget) -> int:
        """Widget'ın bulunduğu satır indeksini bulur."""
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                w = self.table.cellWidget(r, c)
                if w is widget:
                    return r
                # container widget içinde ara
                if w and widget in w.findChildren(type(widget)):
                    return r
        return self.table.currentRow()

    # ─────────────────────────────────────────────
    # SATIR SİLME
    # ─────────────────────────────────────────────

    def _safe_remove_row(self, row: int):
        """Son satırı silmez — temizler."""
        if self.table.rowCount() <= 1:
            self._clear_row(row)
            return
        self.table.removeRow(row)
        self._on_value_changed()
        self.row_removed.emit(row)

    def _clear_row(self, row: int):
        """Satır içeriğini temizler."""
        self.set_row_data(row, {
            "item_type": "Malzeme", "barcode": "", "code": "",
            "name": "", "note2": "", "qty": 1.0, "unit": "Adet",
            "price": 0.0, "currency": "TRY",
            "disc1": 0.0, "disc2": 0.0, "disc3": 0.0, "vat": 20,
        })
        self._on_value_changed()

    def delete_selected_rows(self):
        """Seçili satırları siler — en az 1 kalır."""
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

    # ─────────────────────────────────────────────
    # SATIR TAŞIMA
    # ─────────────────────────────────────────────

    def move_row_up(self, row: int | None = None):
        r = row if row is not None else self.table.currentRow()
        if r <= 0:
            return
        d_curr = self.get_row_data(r)
        d_prev = self.get_row_data(r - 1)
        self.set_row_data(r - 1, d_curr)
        self.set_row_data(r, d_prev)
        self.table.selectRow(r - 1)
        self._on_value_changed()

    def move_row_down(self, row: int | None = None):
        r = row if row is not None else self.table.currentRow()
        if r < 0 or r >= self.table.rowCount() - 1:
            return
        d_curr = self.get_row_data(r)
        d_next = self.get_row_data(r + 1)
        self.set_row_data(r + 1, d_curr)
        self.set_row_data(r, d_next)
        self.table.selectRow(r + 1)
        self._on_value_changed()

    # ─────────────────────────────────────────────
    # SIRALAMA
    # ─────────────────────────────────────────────

    def _on_header_clicked(self, col: int):
        """Başlığa tıklanınca sırala."""
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self.sort_by_column(col, self._sort_asc)

    def sort_by_column(self, col: int, ascending: bool = True):
        """Belirtilen sütuna göre sırala."""
        row_count = self.table.rowCount()
        if row_count <= 1:
            return

        rows_data = [self.get_row_data(r) for r in range(row_count)]

        col_key_map = {
            COL_TUR:    "item_type",
            COL_BARKOD: "barcode",
            COL_KOD:    "code",
            COL_ACIK:   "name",
            COL_NOT2:   "note2",
            COL_MIKTAR: "qty",
            COL_BIRIM:  "unit",
            COL_FIYAT:  "price",
            COL_ISK1P:  "disc1",
            COL_ISK2P:  "disc2",
            COL_ISK3P:  "disc3",
        }
        key = col_key_map.get(col, "name")

        def sort_val(d):
            v = d.get(key, "")
            try:
                return float(str(v).replace(",", "."))
            except Exception:
                return str(v).lower()

        rows_data.sort(key=sort_val, reverse=not ascending)

        for r, row_data in enumerate(rows_data):
            self.set_row_data(r, row_data)

        self._on_value_changed()

    # ─────────────────────────────────────────────
    # SAĞ TIK MENÜSÜ — GÖVDE
    # ─────────────────────────────────────────────

    def _show_body_menu(self, pos):
        row = self.table.currentRow()
        col = self.table.currentColumn()
        can_del = self.table.rowCount() > 1

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background:#ffffff; border:1px solid #cbd5e1;
                font-size:10px; padding:2px;
            }
            QMenu::item { padding:5px 20px 5px 10px; }
            QMenu::item:selected { background:#2563eb; color:#ffffff; }
            QMenu::separator { height:1px; background:#e2e8f0; margin:2px 0; }
        """)

        # Satır işlemleri
        act_add    = QAction("➕ Satır Ekle (Alt+Enter)", self)
        act_insert = QAction("➕ Araya Satır Ekle", self)
        act_del    = QAction("🗑️ Satırı Sil", self)
        act_del.setEnabled(can_del and row >= 0)
        act_bulk   = QAction("🗑️ Seçilenleri Sil (Ctrl+Del)", self)
        sel_count  = len(self.table.selectionModel().selectedRows())
        act_bulk.setEnabled(can_del and sel_count > 1)
        act_up     = QAction("⬆️ Yukarı Taşı (Alt+↑)", self)
        act_down   = QAction("⬇️ Aşağı Taşı (Alt+↓)", self)

        menu.addAction(act_add)
        menu.addAction(act_insert)
        menu.addAction(act_del)
        menu.addAction(act_bulk)
        menu.addSeparator()
        menu.addAction(act_up)
        menu.addAction(act_down)
        menu.addSeparator()

        # Sıralama
        if col >= 0:
            col_name = COLUMN_NAMES[col] if col < len(COLUMN_NAMES) else ""
            act_sort_asc  = QAction(f"🔼 '{col_name}' Artan Sırala", self)
            act_sort_desc = QAction(f"🔽 '{col_name}' Azalan Sırala", self)
            menu.addAction(act_sort_asc)
            menu.addAction(act_sort_desc)
            menu.addSeparator()

            # Sütun gizle
            act_hide = QAction(f"🙈 '{col_name}' Sütununu Gizle", self)
            menu.addAction(act_hide)

        # Gizli sütunları göster
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
                    lambda _, c=hc: self.table.setColumnHidden(c, False),
                )
                show_m.addAction(a)

        menu.addSeparator()
        act_save   = QAction("💾 Görünümü Kaydet", self)
        act_reset  = QAction("↩️ Görünümü Sıfırla", self)
        menu.addAction(act_save)
        menu.addAction(act_reset)

        # Bağlantılar
        act_add.triggered.connect(lambda: self.add_row())
        act_insert.triggered.connect(
            lambda: self.add_row(insert_at=max(0, row)),
        )
        act_del.triggered.connect(lambda: self._safe_remove_row(row))
        act_bulk.triggered.connect(self.delete_selected_rows)
        act_up.triggered.connect(lambda: self.move_row_up(row))
        act_down.triggered.connect(lambda: self.move_row_down(row))

        if col >= 0:
            act_sort_asc.triggered.connect(
                lambda: self.sort_by_column(col, True),
            )
            act_sort_desc.triggered.connect(
                lambda: self.sort_by_column(col, False),
            )
            act_hide.triggered.connect(
                lambda: self.table.setColumnHidden(col, True),
            )

        act_save.triggered.connect(self._save_profile)
        act_reset.triggered.connect(self._reset_widths)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ─────────────────────────────────────────────
    # SAĞ TIK MENÜSÜ — HEADER
    # ─────────────────────────────────────────────

    def _show_header_menu(self, pos):
        col = self.table.horizontalHeader().logicalIndexAt(pos)
        col_name = COLUMN_NAMES[col] if col < len(COLUMN_NAMES) else str(col)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background:#ffffff; border:1px solid #cbd5e1;
                font-size:10px; padding:2px;
            }
            QMenu::item { padding:5px 20px 5px 10px; }
            QMenu::item:selected { background:#2563eb; color:#ffffff; }
            QMenu::separator { height:1px; background:#e2e8f0; }
        """)

        act_sort_asc  = QAction("🔼 Artan Sırala", self)
        act_sort_desc = QAction("🔽 Azalan Sırala", self)
        act_hide      = QAction(f"🙈 '{col_name}' Gizle", self)
        menu.addAction(act_sort_asc)
        menu.addAction(act_sort_desc)
        menu.addSeparator()
        menu.addAction(act_hide)

        # Gizli sütunlar
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
                    lambda _, c=hc: self.table.setColumnHidden(c, False),
                )
                show_m.addAction(a)

        menu.addSeparator()
        act_save  = QAction("💾 Görünümü Kaydet", self)
        act_reset = QAction("↩️ Sıfırla", self)
        menu.addAction(act_save)
        menu.addAction(act_reset)

        act_sort_asc.triggered.connect(lambda: self.sort_by_column(col, True))
        act_sort_desc.triggered.connect(lambda: self.sort_by_column(col, False))
        act_hide.triggered.connect(lambda: self.table.setColumnHidden(col, True))
        act_save.triggered.connect(self._save_profile)
        act_reset.triggered.connect(self._reset_widths)

        menu.exec(self.table.horizontalHeader().mapToGlobal(pos))

    # ─────────────────────────────────────────────
    # VERİ OKUMA / YAZMA
    # ─────────────────────────────────────────────

    def get_row_data(self, row: int) -> dict[str, Any]:
        """Satırdaki tüm veriyi dict olarak döndürür."""

        def txt(col: int) -> str:
            w = self.table.cellWidget(row, col)
            if isinstance(w, QLineEdit):
                return w.text()
            if isinstance(w, QComboBox):
                return w.currentText()
            if isinstance(w, QLabel):
                return w.text()
            return ""

        def flt(col: int) -> float:
            try:
                return float(txt(col).replace(",", ".") or "0")
            except Exception:
                return 0.0

        # Stok kodu container içindeki QLineEdit
        kod_w = self.table.cellWidget(row, COL_KOD)
        kod = ""
        if kod_w:
            le = kod_w.findChild(QLineEdit)
            kod = le.text() if le else ""

        return {
            "item_type": txt(COL_TUR),
            "barcode": txt(COL_BARKOD),
            "code": kod,
            "name": txt(COL_ACIK),
            "note2": txt(COL_NOT2),
            "qty": flt(COL_MIKTAR),
            "unit": txt(COL_BIRIM),
            "price": flt(COL_FIYAT),
            "currency": txt(COL_DOVIZ),
            "disc1": flt(COL_ISK1P),
            "disc2": flt(COL_ISK2P),
            "disc3": flt(COL_ISK3P),
            "vat": int(txt(COL_KDVP).replace("%", "").strip() or "20"),
            "tevkifat": txt(COL_TEV),
        }

    def set_row_data(self, row: int, data: dict) -> None:
        """Satıra veri yazar."""

        def set_line(col: int, val: Any) -> None:
            w = self.table.cellWidget(row, col)
            if isinstance(w, QLineEdit):
                w.setText(str(val))

        def set_combo(col: int, val: Any) -> None:
            w = self.table.cellWidget(row, col)
            if isinstance(w, QComboBox):
                idx = w.findText(str(val))
                if idx >= 0:
                    w.setCurrentIndex(idx)

        set_combo(COL_TUR, data.get("item_type", "Malzeme"))
        set_line(COL_BARKOD, data.get("barcode", ""))

        kod_w = self.table.cellWidget(row, COL_KOD)
        if kod_w:
            le = kod_w.findChild(QLineEdit)
            if le:
                le.setText(data.get("code", ""))

        set_line(COL_ACIK, data.get("name", ""))
        set_line(COL_NOT2, data.get("note2", ""))
        set_line(COL_MIKTAR, str(data.get("qty", 1.0)))
        set_line(COL_BIRIM, data.get("unit", "Adet"))
        set_line(COL_FIYAT, f"{float(data.get('price', 0)):.2f}")
        set_combo(COL_DOVIZ, data.get("currency", "TRY"))
        set_line(COL_ISK1P, str(data.get("disc1", 0.0)))
        set_line(COL_ISK2P, str(data.get("disc2", 0.0)))
        set_line(COL_ISK3P, str(data.get("disc3", 0.0)))
        set_combo(COL_KDVP, f"% {data.get('vat', 20)}")
        set_combo(COL_TEV, data.get("tevkifat", "Yok"))

    def get_all_rows(self) -> list[dict]:
        """Tüm satırların verisini döndürür (boş satırları atlar)."""
        rows = []
        for r in range(self.table.rowCount()):
            d = self.get_row_data(r)
            if d.get("name") or d.get("code"):
                rows.append(d)
        return rows

    def clear_rows(self):
        """Tüm satırları temizler, 1 boş satır bırakır."""
        self.table.setRowCount(0)
        self.add_row()

    # ─────────────────────────────────────────────
    # TOPLAM HESAPLAMA
    # ─────────────────────────────────────────────

    def _on_value_changed(self):
        """Herhangi bir değer değiştiğinde satır tutarlarını günceller."""
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

            base   = qty * price
            after  = base * (1 - d1/100) * (1 - d2/100) * (1 - d3/100)
            total  = round(after * (1 + vat/100), 2)

            # İskonto tutarları
            disc1_amt = round(base - base*(1-d1/100), 2)
            disc2_amt = round(base*(1-d1/100) - base*(1-d1/100)*(1-d2/100), 2)
            disc3_amt = round(after/(1-d3/100)*d3/100 if d3 > 0 else 0, 2)

            for col, val in [
                (COL_ISK1T, disc1_amt),
                (COL_ISK2T, disc2_amt),
                (COL_ISK3T, disc3_amt),
            ]:
                lbl = self.table.cellWidget(row, col)
                if isinstance(lbl, QLabel):
                    lbl.setText(f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            lbl_tot = self.table.cellWidget(row, COL_TUTAR)
            if isinstance(lbl_tot, QLabel):
                sym = self._currency_symbol(d.get("currency", "TRY"))
                lbl_tot.setText(
                    f"{total:,.2f} {sym}".replace(",", "X").replace(".", ",").replace("X", "."),
                )
            return total
        except Exception:
            return 0.0

    @staticmethod
    def _currency_symbol(currency: str) -> str:
        return {"TRY": "₺", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency, currency)

    # ─────────────────────────────────────────────
    # STOK ARAMA
    # ─────────────────────────────────────────────

    def _on_code_selected(self, row: int, code: str):
        p = next((x for x in self.products_catalog if x["code"] == code), None)
        if p:
            self._apply_product(row, p)

    def _on_name_selected(self, row: int, name: str):
        p = next((x for x in self.products_catalog if x["name"] == name), None)
        if p:
            self._apply_product(row, p)

    def _apply_product(self, row: int, p: dict):
        self.set_row_data(row, {
            **self.get_row_data(row),
            "code":    p.get("code", ""),
            "barcode": p.get("barcode", ""),
            "name":    p.get("name", ""),
            "unit":    p.get("unit", "Adet"),
            "price":   p.get("price", 0.0),
            "vat":     p.get("vat", 20),
        })
        self._on_value_changed()

    def _open_stock_lookup(self, row: int):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background:white; border:1px solid #cbd5e1; font-size:10px; }
            QMenu::item { padding:5px 14px; }
            QMenu::item:selected { background:#2563eb; color:white; }
        """)
        for p in self.products_catalog:
            act = QAction(
                f"📦 {p['code']} — {p['name']} "
                f"({p['price']:.2f} ₺ | Stok: {p.get('stock', '?')})",
                self,
            )
            act.triggered.connect(
                lambda _, prod=p, r=row: self._apply_product(r, prod),
            )
            menu.addAction(act)

        w = self.table.cellWidget(row, COL_KOD)
        if w:
            menu.exec(w.mapToGlobal(w.rect().bottomLeft()))

    def _on_type_changed(self, row: int, new_type: str):
        w = self.table.cellWidget(row, COL_KOD)
        txt = w.findChild(QLineEdit) if w else None
        acik = self.table.cellWidget(row, COL_ACIK)
        if new_type == "Serbest Giriş":
            if txt:
                txt.setPlaceholderText("Serbest Kod")
            if acik:
                acik.setPlaceholderText("Serbest Açıklama Yazın...")
        else:
            if txt:
                txt.setPlaceholderText("")
            if acik:
                acik.setPlaceholderText("")

    # ─────────────────────────────────────────────
    # PROFİL — SÜTUN GENİŞLİKLERİ
    # ─────────────────────────────────────────────

    def _save_profile(self):
        """Sütun genişliklerini ve gizliliğini JSON'a kaydet."""
        import json
        import os
        profile = {}
        for c in range(self.table.columnCount()):
            profile[str(c)] = {
                "width":  self.table.columnWidth(c),
                "hidden": self.table.isColumnHidden(c),
            }
        path = self._profile_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f)
        QMessageBox.information(self, "Profil Kaydedildi", "Sütun görünümü kaydedildi.")

    def _load_profile(self):
        """Kaydedilmiş profili yükle."""
        import json
        path = self._profile_path()
        try:
            with open(path, encoding="utf-8") as f:
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
        """Sütun genişliklerini varsayılana döndür."""
        self._set_default_widths()
        for c in range(self.table.columnCount()):
            self.table.setColumnHidden(c, False)

    def _profile_path(self) -> str:
        import os
        base = os.path.join(
            os.path.expanduser("~"), ".toya_erp", "profiles",
        )
        return os.path.join(base, f"{self.profile_key}.json")

    # ─────────────────────────────────────────────
    # TEMA — SATIR YÜKSEKLİĞİ
    # ─────────────────────────────────────────────

    def update_row_height(self, height: int):
        """ThemeManager'dan gelen yükseklik değişince güncelle."""
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
