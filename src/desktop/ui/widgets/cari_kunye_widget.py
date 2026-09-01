"""
ToyaUI — CariKunyeWidget
Fiş detay ekranlarındaki cari hesap bilgileri paneli.

Kullanım:
    widget = CariKunyeWidget(customers_catalog=[], db_session=db)
    widget.customer_selected.connect(self.on_customer_selected)
    layout.addWidget(widget)

    # Veri okuma
    data = widget.get_data()
    # data = {
    #     "code": "M210000194",
    #     "name": "TATU HIRDAVAT...",
    #     "tax_office": "Seyhan V.D.",
    #     "tax_no": "1234567896",
    #     "address": "Mersinli Mah...",
    # }

    # Veri yazma
    widget.set_data(data)

    # Temizleme
    widget.clear()
"""

import logging
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCompleter,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class FieldWithButton(QFrame):
    """
    QLineEdit + sağda küçük buton — tek bir alan gibi görünür.
    Buton input'un İÇİNDE sağda konumlanır, yer kaplamaz.

    Kullanım:
        field = FieldWithButton(placeholder="Cari kodu...", btn_text="🔍")
        field.btn.clicked.connect(handler)
        field.txt.editingFinished.connect(handler2)
        value = field.txt.text()
    """

    def __init__(
        self,
        placeholder: str = "",
        btn_text: str = "🔍",
        btn_width: int = 22,
        field_style: str = "",
        bold: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet("background:transparent; border:none;")

        # Dış layout — sıfır margin
        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(0)

        # Input
        self.txt = QLineEdit()
        self.txt.setPlaceholderText(placeholder)
        base_style = """
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-right: none;
                border-radius: 3px 0 0 3px;
                padding: 1px 4px;
                font-size: 10px;
                background: white;
                color: #0f172a;
            }
            QLineEdit:focus { border-color: #2563eb; }
            QLineEdit:read-only { background:#f8fafc; color:#64748b; }
        """
        if bold:
            base_style += "QLineEdit { font-weight: bold; }"
        self.txt.setStyleSheet(field_style or base_style)

        # Buton — sağa yapışık
        self.btn = QPushButton(btn_text)
        self.btn.setFixedWidth(btn_width)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-left: none;
                border-radius: 0 3px 3px 0;
                font-size: 11px;
                color: #475569;
                padding: 0;
            }
            QPushButton:hover {
                background: #e2e8f0;
                color: #1e3a8a;
            }
        """)

        lyt.addWidget(self.txt, 1)
        lyt.addWidget(self.btn)

    def setFixedHeight(self, h: int):  # noqa: N802
        super().setFixedHeight(h)
        self.txt.setFixedHeight(h)
        self.btn.setFixedHeight(h)

    def text(self) -> str:
        return self.txt.text()

    def setText(self, text: str):  # noqa: N802
        self.txt.setText(text)

    def clear(self):
        self.txt.clear()

# Sabit widget isimleri — dışarıdan erişim için
FIELD_CARI_KODU  = "txt_cari_kodu"
FIELD_CARI_UNVAN = "txt_cari_unvan"
FIELD_VERGI_D    = "txt_vergi_daire"
FIELD_VERGI_NO   = "txt_vergi_no"
FIELD_SEVK_ADRES = "txt_sevk_adres"


class CariSecimDialog(QDialog):
    """
    Cari seçim listesi dialog'u.
    Arama, filtreleme ve yeni cari ekleme desteği.
    """

    customer_selected = pyqtSignal(dict)

    def __init__(self, customers: list[dict], db_session=None, parent=None):
        super().__init__(parent)
        self.customers  = customers
        self.db         = db_session
        self._filtered  = list(customers)

        self.setWindowTitle("👤 Cari Seçim Listesi")
        self.setMinimumSize(750, 480)
        self.setStyleSheet("""
            QDialog { background: #f8fafc; font-family: 'Segoe UI'; }
            QLineEdit {
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 4px 8px; font-size: 11px; background: white;
            }
            QTableWidget {
                border: 1px solid #e2e8f0; background: white;
                font-size: 11px; gridline-color: #f1f5f9;
            }
            QHeaderView::section {
                background: #1e3a8a; color: white;
                padding: 5px; font-weight: bold; font-size: 10px;
                border: none; border-right: 1px solid #2d4fa0;
            }
            QTableWidget::item:selected {
                background: #dbeafe; color: #1e40af;
            }
            QPushButton {
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 5px 12px; font-size: 11px; font-weight: 600;
            }
        """)

        self._init_ui()
        self._load_table(self.customers)

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
            "Cari kodu, ünvan veya vergi no ile ara...",
        )
        self.txt_search.textChanged.connect(self._filter)
        search_row.addWidget(lbl)
        search_row.addWidget(self.txt_search)
        lyt.addLayout(search_row)

        # Tablo
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Cari Kodu", "Ünvan", "Vergi D.", "Vergi No", "Şehir"],
        )
        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(1, hh.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self.table.doubleClicked.connect(self._on_double_click)
        lyt.addWidget(self.table, 1)

        # Kayıt sayısı
        self.lbl_count = QLabel("0 kayıt")
        self.lbl_count.setStyleSheet("color:#64748b; font-size:10px;")
        lyt.addWidget(self.lbl_count)

        # Alt butonlar
        btn_lyt = QHBoxLayout()
        btn_yeni = QPushButton("➕ Yeni Cari Ekle")
        btn_yeni.setStyleSheet(
            "background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe;",
        )
        btn_yeni.clicked.connect(self._on_new_customer)

        btn_sec = QPushButton("✅ Seç")
        btn_sec.setStyleSheet(
            "background:#2563eb; color:white; border-color:#1d4ed8;",
        )
        btn_sec.clicked.connect(self._on_select)

        btn_kapat = QPushButton("✕ Kapat")
        btn_kapat.clicked.connect(self.reject)

        btn_lyt.addWidget(btn_yeni)
        btn_lyt.addStretch()
        btn_lyt.addWidget(btn_sec)
        btn_lyt.addWidget(btn_kapat)
        lyt.addLayout(btn_lyt)

    def _load_table(self, data: list[dict]):
        self.table.setRowCount(0)
        for c in data:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(c.get("code", "")))
            self.table.setItem(r, 1, QTableWidgetItem(c.get("name", "")))
            self.table.setItem(r, 2, QTableWidgetItem(c.get("tax_office", "")))
            self.table.setItem(r, 3, QTableWidgetItem(c.get("tax_no", "")))
            self.table.setItem(r, 4, QTableWidgetItem(c.get("city", "")))
            self.table.setRowHeight(r, 26)
        self.lbl_count.setText(f"{len(data)} kayıt")
        self._filtered = data

    def _filter(self, text: str):
        text = text.lower().strip()
        if not text:
            self._load_table(self.customers)
            return
        filtered = [
            c for c in self.customers
            if text in c.get("code", "").lower()
            or text in c.get("name", "").lower()
            or text in c.get("tax_no", "").lower()
        ]
        self._load_table(filtered)

    def _get_selected_customer(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered):
            return None
        return self._filtered[row]

    def _on_select(self):
        c = self._get_selected_customer()
        if not c:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir cari seçin.")
            return
        self.customer_selected.emit(c)
        self.accept()

    def _on_double_click(self, index):
        row = index.row()
        if 0 <= row < len(self._filtered):
            self.customer_selected.emit(self._filtered[row])
            self.accept()

    def _on_new_customer(self):
        QMessageBox.information(
            self, "Yeni Cari",
            "Cari kart formu açılacak.\n(Stok Kart Dialog ile aynı şablonda)",
        )


class CariKunyeWidget(QFrame):
    """
    Cari Hesap Künye Widget'ı.

    Sinyaller:
        customer_selected(dict): Cari seçildiğinde
        data_changed(): Herhangi bir alan değiştiğinde
        balance_requested(str): BAKİYE butonuna tıklanınca cari kodu ile
    """

    customer_selected  = pyqtSignal(dict)
    data_changed       = pyqtSignal()
    balance_requested  = pyqtSignal(str)

    # Stil sabitleri
    FIELD_H   = 24
    LBL_STYLE = "font-size:9px; font-weight:600; color:#475569; min-width:60px;"
    FIELD_STYLE = """
        QLineEdit {
            border: 1px solid #cbd5e1; border-radius: 3px;
            padding: 1px 4px; font-size: 10px; background: white;
            color: #0f172a;
        }
        QLineEdit:focus {
            border-color: #2563eb;
        }
        QLineEdit:read-only {
            background: #f8fafc; color: #64748b;
        }
    """

    def __init__(
        self,
        customers_catalog: list[dict] | None = None,
        db_session=None,
        collapsible: bool = False,  # Dialog tarafından yönetilir
        parent=None,
    ):
        super().__init__(parent)
        self.customers_catalog = customers_catalog or []
        self.db                = db_session
        self.collapsible       = collapsible
        self._collapsed        = False
        self._current_customer: dict | None = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            CariKunyeWidget {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
        """)
        self.setFixedHeight(108)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._init_ui()
        self._setup_completers()

    # ─────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────

    def _init_ui(self):
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(6, 4, 6, 4)
        main_lyt.setSpacing(2)

        # ── BAŞLIK SATIRI ──
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 0, 0)

        lbl_hdr = QLabel("👤 CARİ HESAP KÜNYESİ")
        lbl_hdr.setStyleSheet(
            "font-weight:800; color:#1e3a8a; font-size:10px;",
        )

        # Başlık butonları
        self.btn_sec = QPushButton("🔍 Seç")
        self.btn_sec.setFixedHeight(18)
        self.btn_sec.setStyleSheet("""
            QPushButton {
                background:#eff6ff; color:#1d4ed8;
                border:1px solid #bfdbfe; border-radius:3px;
                font-size:9px; font-weight:600; padding:0 6px;
            }
            QPushButton:hover { background:#dbeafe; }
        """)
        self.btn_sec.clicked.connect(self.open_customer_lookup)

        self.btn_temizle = QPushButton("🗑️ Temizle")
        self.btn_temizle.setFixedHeight(18)
        self.btn_temizle.setStyleSheet("""
            QPushButton {
                background:#fff7ed; color:#c2410c;
                border:1px solid #fed7aa; border-radius:3px;
                font-size:9px; font-weight:600; padding:0 6px;
            }
            QPushButton:hover { background:#ffedd5; }
        """)
        self.btn_temizle.clicked.connect(self.clear)

        self.btn_collapse = QPushButton("∧")
        self.btn_collapse.setFixedSize(18, 18)
        self.btn_collapse.setStyleSheet("""
            QPushButton {
                background:#e2e8f0; border:none; border-radius:3px;
                font-size:10px; color:#64748b;
            }
            QPushButton:hover { background:#cbd5e1; }
        """)
        self.btn_collapse.clicked.connect(self.toggle_collapse)
        self.btn_collapse.setVisible(False)  # Dış dialog yönetir

        hdr_row.addWidget(lbl_hdr)
        hdr_row.addStretch()
        hdr_row.addWidget(self.btn_sec)
        hdr_row.addWidget(self.btn_temizle)
        main_lyt.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_lyt.addLayout(hdr_row)

        # ── İÇERİK ──
        self.content_widget = QWidget()
        content_lyt = QGridLayout(self.content_widget)
        content_lyt.setContentsMargins(0, 2, 0, 0)
        content_lyt.setSpacing(3)
        content_lyt.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_lyt.setColumnStretch(1, 1)
        content_lyt.setColumnStretch(3, 2)

        # ── SATIR 1: Cari Kodu | Ünvan ──
        lbl_kod = QLabel("Cari Kodu:")
        lbl_kod.setStyleSheet(self.LBL_STYLE)
        lbl_kod.setFixedWidth(64)

        # ── Cari Kodu: FieldWithButton ──
        self._kod_field = FieldWithButton(
            placeholder="Cari kodu...",
            btn_text="🔍",
            bold=True,
        )
        self._kod_field.setFixedHeight(self.FIELD_H)
        self.txt_cari_kodu = self._kod_field.txt
        self.txt_cari_kodu.setMinimumWidth(120)
        self._kod_field.setMinimumWidth(120)
        self._kod_field.btn.setToolTip("Cari Seç (F10)")
        self._kod_field.btn.clicked.connect(self.open_customer_lookup)
        self.txt_cari_kodu.editingFinished.connect(
            self._on_code_editing_finished,
        )
        self.txt_cari_kodu.textChanged.connect(
            lambda: self.data_changed.emit(),
        )

        # ── Ünvan: FieldWithButton ──
        lbl_unv = QLabel("Ünvanı:")
        lbl_unv.setStyleSheet(self.LBL_STYLE)

        self._unv_field = FieldWithButton(
            placeholder="Ticari ünvan...",
            btn_text="🔍",
        )
        self._unv_field.setFixedHeight(self.FIELD_H)
        self.txt_cari_unvan = self._unv_field.txt
        self._unv_field.btn.setToolTip("Cari Seç")
        self._unv_field.btn.clicked.connect(self.open_customer_lookup)
        self.txt_cari_unvan.textChanged.connect(
            lambda: self.data_changed.emit(),
        )
        self.txt_cari_unvan.editingFinished.connect(
            lambda: self._check_and_suggest_quick_add(
                self.txt_cari_unvan.text().strip(),
            ) if self.txt_cari_unvan.text().strip()
            and not self._current_customer else None,
        )

        content_lyt.addWidget(lbl_kod,         0, 0)
        content_lyt.addWidget(self._kod_field,  0, 1)
        content_lyt.addWidget(lbl_unv,          0, 2)
        content_lyt.addWidget(self._unv_field,  0, 3)

        # ── SATIR 2: Vergi D. | Vergi No | BAKİYE ──
        lbl_vd = QLabel("Vergi D./No:")
        lbl_vd.setStyleSheet(self.LBL_STYLE)
        lbl_vd.setFixedWidth(64)

        self.txt_vergi_daire = QLineEdit()
        self.txt_vergi_daire.setFixedHeight(self.FIELD_H)
        self.txt_vergi_daire.setStyleSheet(self.FIELD_STYLE)
        self.txt_vergi_daire.setPlaceholderText("Vergi dairesi...")
        self.txt_vergi_daire.setMinimumWidth(130)
        self.txt_vergi_daire.textChanged.connect(
            lambda: self.data_changed.emit(),
        )

        # txt_vergi_no → _vno_field.txt olarak tanımlanıyor (aşağıda)

        self.btn_bakiye = QPushButton("💳 BAKİYE")
        self.btn_bakiye.setFixedHeight(self.FIELD_H)
        self.btn_bakiye.setFixedWidth(72)
        self.btn_bakiye.setStyleSheet("""
            QPushButton {
                background:#fee2e2; color:#991b1b;
                border:1px solid #fca5a5; border-radius:3px;
                font-size:9px; font-weight:700; padding:0 4px;
            }
            QPushButton:hover { background:#fca5a5; }
        """)
        self.btn_bakiye.clicked.connect(
            lambda: self.balance_requested.emit(
                self.txt_cari_kodu.text().strip(),
            ),
        )

        # Vergi No — FieldWithButton (🔍 içinde)
        self._vno_field = FieldWithButton(
            placeholder="Vergi No / TCKN",
            btn_text="🔍",
        )
        self._vno_field.setFixedHeight(self.FIELD_H)
        self.txt_vergi_no = self._vno_field.txt
        self.txt_vergi_no.setMinimumWidth(110)
        self._vno_field.setMinimumWidth(110)
        self._vno_field.btn.setToolTip("Vergi No ile sorgula (Enter)")
        self._vno_field.btn.clicked.connect(self._search_by_tax_no)
        self.txt_vergi_no.returnPressed.connect(self._search_by_tax_no)
        self.txt_vergi_no.textChanged.connect(
            lambda: self.data_changed.emit(),
        )

        vd_row = QHBoxLayout()
        vd_row.setSpacing(4)
        vd_row.addWidget(self.txt_vergi_daire, 2)
        vd_row.addWidget(self._vno_field, 2)
        vd_row.addWidget(self.btn_bakiye)

        content_lyt.addWidget(lbl_vd,  1, 0)
        content_lyt.addLayout(vd_row,  1, 1, 1, 3)

        # ── SATIR 3: Sevk Adresi ──
        lbl_adres = QLabel("Sevk Adresi:")
        lbl_adres.setStyleSheet(self.LBL_STYLE)
        lbl_adres.setFixedWidth(64)

        self.txt_sevk_adres = QLineEdit()
        self.txt_sevk_adres.setFixedHeight(self.FIELD_H)
        self.txt_sevk_adres.setStyleSheet(self.FIELD_STYLE)
        self.txt_sevk_adres.setPlaceholderText("Sevk adresi...")
        self.txt_sevk_adres.textChanged.connect(
            lambda: self.data_changed.emit(),
        )

        content_lyt.addWidget(lbl_adres,          2, 0)
        content_lyt.addWidget(self.txt_sevk_adres, 2, 1, 1, 3)

        # ── DİNAMİK ALAN ALANI (ileride ek alanlar buraya) ──
        self._extra_layout = QVBoxLayout()
        self._extra_layout.setSpacing(2)
        content_lyt.addLayout(self._extra_layout, 3, 0, 1, 4)

        main_lyt.addWidget(self.content_widget)
        main_lyt.addStretch()

    def _setup_completers(self):
        """Cari kodu ve ünvan için autocomplete."""
        if not self.customers_catalog:
            return

        codes = [c.get("code", "") for c in self.customers_catalog]
        comp_kod = QCompleter(codes, self)
        comp_kod.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_kod.setFilterMode(Qt.MatchFlag.MatchContains)
        comp_kod.activated.connect(self._on_code_completed)
        self.txt_cari_kodu.setCompleter(comp_kod)

        names = [c.get("name", "") for c in self.customers_catalog]
        comp_name = QCompleter(names, self)
        comp_name.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp_name.setFilterMode(Qt.MatchFlag.MatchContains)
        comp_name.activated.connect(self._on_name_completed)
        self.txt_cari_unvan.setCompleter(comp_name)

    # ─────────────────────────────────────────────
    # COLLAPSE
    # ─────────────────────────────────────────────

    @staticmethod
    def _search_btn_style() -> str:
        return """
            QPushButton {
                background:#f1f5f9; color:#475569;
                border:1px solid #cbd5e1; border-radius:3px;
                font-size:11px; padding:0;
            }
            QPushButton:hover {
                background:#e2e8f0; color:#1e3a8a;
            }
        """

    def toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.content_widget.setVisible(not self._collapsed)
        self.btn_collapse.setText("∨" if self._collapsed else "∧")

    def expand(self):
        if self._collapsed:
            self.toggle_collapse()

    def collapse(self):
        if not self._collapsed:
            self.toggle_collapse()

    # ─────────────────────────────────────────────
    # CARİ ARAMA
    # ─────────────────────────────────────────────

    def open_customer_lookup(self):
        """
        MOD A — Tam cari seçim listesi.
        CariSecimDialog açılır → seç → geri dön.
        """
        catalog = self._get_catalog()
        dlg = CariSecimDialog(
            customers=catalog,
            db_session=self.db,
            parent=self,
        )
        dlg.customer_selected.connect(self.apply_customer)
        dlg.exec()

    def open_quick_add(self, initial_name: str = ""):
        """
        MOD B — Hızlı cari ekleme.
        Küçük dialog: otomatik kod + açıklama → kaydet → seç.
        """
        dlg = HizliCariEkleDialog(
            initial_name=initial_name,
            db_session=self.db,
            parent=self,
        )
        dlg.customer_added.connect(self._on_quick_add)
        dlg.exec()

    def _on_quick_add(self, customer: dict):
        """Hızlı ekleme sonrası kataloğu güncelle ve seç."""
        self.customers_catalog.append(customer)
        self._setup_completers()
        self.apply_customer(customer)

    def _check_and_suggest_quick_add(self, typed: str):
        """
        Yazılan metin katalogda yoksa hızlı ekleme öner.
        txt_cari_kodu veya txt_cari_unvan'dan Enter'a basılınca çağrılır.
        """
        if not typed.strip():
            return
        catalog = self._get_catalog()
        found = any(
            typed.lower() in c.get("code", "").lower()
            or typed.lower() in c.get("name", "").lower()
            for c in catalog
        )
        if not found:
            reply = QMessageBox.question(
                self,
                "Cari Bulunamadı",
                f"'{typed}' bulunamadı.\n\nHızlı cari eklemek ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.open_quick_add(initial_name=typed)

    def _get_catalog(self) -> list[dict]:
        """DB'den veya catalog'dan cari listesini döndür."""
        if self.db:
            try:
                from sqlalchemy import select

                from src.core.models import Customer
                rows = self.db.scalars(
                    select(Customer).where(Customer.is_deleted == False),
                ).all()
                if rows:
                    return [
                        {
                            "code":       c.customer_code or f"CAR-{c.id}",
                            "name":       c.fullname or "",
                            "tax_office": getattr(c, "tax_office", "") or "",
                            "tax_no":     c.tax_number or "",
                            "address":    getattr(c, "address", "") or "",
                            "city":       "",
                            "balance":    "0,00 ₺",
                            "terms":      30,
                        }
                        for c in rows
                    ]
            except Exception as e:
                logger.warning(f"DB'den cari listesi alınamadı: {e}")

        return self.customers_catalog

    def _on_code_completed(self, code: str):
        c = next(
            (x for x in self._get_catalog() if x.get("code") == code),
            None,
        )
        if c:
            self.apply_customer(c)

    def _on_name_completed(self, name: str):
        c = next(
            (x for x in self._get_catalog() if x.get("name") == name),
            None,
        )
        if c:
            self.apply_customer(c)

    def _search_by_tax_no(self):
        """
        Vergi No ile DB'de cari sorgula.
        Enter veya 🔍 ikonuna tıklanınca çalışır.
        """
        tax_no = self.txt_vergi_no.text().strip()
        if not tax_no:
            return

        catalog = self._get_catalog()

        # Önce katalogda ara
        found = next(
            (c for c in catalog if c.get("tax_no", "") == tax_no),
            None,
        )

        if found:
            self.apply_customer(found)
            return

        # DB'de ara
        if self.db:
            try:
                from sqlalchemy import select

                from src.core.models import Customer
                c = self.db.scalar(
                    select(Customer).where(
                        Customer.tax_number == tax_no,
                        Customer.is_deleted == False,
                    ),
                )
                if c:
                    self.apply_customer({
                        "code":       c.customer_code or "",
                        "name":       c.fullname or "",
                        "tax_office": getattr(c, "tax_office", "") or "",
                        "tax_no":     c.tax_number or "",
                        "address":    getattr(c, "address", "") or "",
                        "city":       "",
                        "balance":    "0,00 ₺",
                        "terms":      30,
                    })
                    return
            except Exception as e:
                logger.warning(f"Vergi no sorgusu başarısız: {e}")

        # Bulunamadı
        reply = QMessageBox.question(
            self,
            "Vergi No Bulunamadı",
            f"'{tax_no}' vergi numaralı cari bulunamadı.\n\n"
            f"Hızlı cari eklemek ister misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            dlg = HizliCariEkleDialog(
                initial_name="",
                db_session=self.db,
                parent=self,
            )
            # Vergi no'yu otomatik doldur
            dlg.txt_vergi_no.setText(tax_no)
            dlg.customer_added.connect(self._on_quick_add)
            dlg.exec()

    def _on_code_editing_finished(self):
        """
        Cari kodu alanından çıkılınca DB'de ara.
        Bulunamazsa hızlı ekleme öner.
        """
        code = self.txt_cari_kodu.text().strip()
        if not code:
            return
        c = next(
            (x for x in self._get_catalog() if x.get("code") == code),
            None,
        )
        if c:
            self.apply_customer(c)
        else:
            self._check_and_suggest_quick_add(code)

    def apply_customer(self, customer: dict):
        """Seçilen cariyi alanlara yaz."""
        self._current_customer = customer

        self.txt_cari_kodu.setText(customer.get("code", ""))
        self.txt_cari_unvan.setText(customer.get("name", ""))
        self.txt_vergi_daire.setText(customer.get("tax_office", ""))
        self.txt_vergi_no.setText(customer.get("tax_no", ""))
        self.txt_sevk_adres.setText(customer.get("address", ""))

        self.customer_selected.emit(customer)
        self.data_changed.emit()

    # ─────────────────────────────────────────────
    # DİNAMİK ALAN
    # ─────────────────────────────────────────────

    def add_extra_field(self, label: str, widget: QWidget):
        """
        Dinamik alan ekle.
        Örn: Ödeme Planı, Yetkili, E-Posta gibi ek alanlar.
        """
        row_lyt = QHBoxLayout()
        row_lyt.setSpacing(4)
        lbl = QLabel(f"{label}:")
        lbl.setStyleSheet(self.LBL_STYLE)
        lbl.setFixedWidth(70)
        row_lyt.addWidget(lbl)
        row_lyt.addWidget(widget)
        self._extra_layout.addLayout(row_lyt)

    # ─────────────────────────────────────────────
    # VERİ OKUMA / YAZMA
    # ─────────────────────────────────────────────

    def get_data(self) -> dict[str, Any]:
        """Tüm alan değerlerini dict olarak döndürür."""
        return {
            "code":       self.txt_cari_kodu.text().strip(),
            "name":       self.txt_cari_unvan.text().strip(),
            "tax_office": self.txt_vergi_daire.text().strip(),
            "tax_no":     self.txt_vergi_no.text().strip(),
            "address":    self.txt_sevk_adres.text().strip(),
            "customer":   self._current_customer,
        }

    def set_data(self, data: dict):
        """Dict'ten alan değerlerini yazar."""
        self.txt_cari_kodu.setText(data.get("code", ""))
        self.txt_cari_unvan.setText(data.get("name", ""))
        self.txt_vergi_daire.setText(data.get("tax_office", ""))
        self.txt_vergi_no.setText(data.get("tax_no", ""))
        self.txt_sevk_adres.setText(data.get("address", ""))
        if data.get("customer"):
            self._current_customer = data["customer"]

    def clear(self):
        """Tüm alanları temizler."""
        self.txt_cari_kodu.clear()
        self.txt_cari_unvan.clear()
        self.txt_vergi_daire.clear()
        self.txt_vergi_no.clear()
        self.txt_sevk_adres.clear()
        self._current_customer = None

    def get_current_customer(self) -> dict | None:
        """Mevcut seçili cariyi döndürür."""
        return self._current_customer

    # ─────────────────────────────────────────────
    # KATALOG GÜNCELLEME
    # ─────────────────────────────────────────────

    def update_catalog(self, catalog: list[dict]):
        """Cari kataloğunu günceller ve completers'ı yeniler."""
        self.customers_catalog = catalog
        self._setup_completers()


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    DEMO_CUSTOMERS = [
        {
            "code": "M210000194",
            "name": "TATU HIRDAVAT İÇ VE DIŞ TİC.LTD.ŞTİ",
            "tax_office": "Seyhan V.D.",
            "tax_no": "1234567896",
            "address": "Mersinli Mah. 2826 Sokak No:14/101 Adana",
            "city": "Adana",
            "balance": "45.250,00 ₺",
            "terms": 30,
        },
        {
            "code": "M210000195",
            "name": "DENEME BİLİŞİM TEKNOLOJİLERİ A.Ş.",
            "tax_office": "Kadıköy V.D.",
            "tax_no": "9876543210",
            "address": "Bağdat Cad. No:44 İstanbul",
            "city": "İstanbul",
            "balance": "12.800,00 ₺",
            "terms": 15,
        },
    ]

    widget = CariKunyeWidget(customers_catalog=DEMO_CUSTOMERS)

    # Test sinyalleri
    widget.customer_selected.connect(
        lambda c: print(f"✅ Cari seçildi: {c['code']} — {c['name']}"),
    )
    widget.balance_requested.connect(
        lambda code: print(f"💳 Bakiye istendi: {code}"),
    )
    widget.data_changed.connect(
        lambda: print(f"📝 Veri değişti: {widget.get_data()}"),
    )

    # Demo veri yükle
    widget.set_data(DEMO_CUSTOMERS[0])

    win = QWidget()
    win.setWindowTitle("CariKunyeWidget Test")
    win.setMinimumWidth(700)
    lyt = QVBoxLayout(win)
    lyt.addWidget(widget)

    lyt.addStretch()

    win.show()
    sys.exit(app.exec())


# ─────────────────────────────────────────────
# HIZLI CARİ EKLEME DIALOG'U
# ─────────────────────────────────────────────

class HizliCariEkleDialog(QDialog):
    """
    Hızlı cari ekleme dialog'u.
    Sadece: Otomatik Kod + Açıklama → Kaydet
    """

    customer_added = pyqtSignal(dict)

    def __init__(
        self,
        initial_name: str = "",
        db_session=None,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db_session
        self.setWindowTitle("➕ Hızlı Cari Ekle")
        self.setFixedSize(420, 260)
        self.setStyleSheet("""
            QDialog {
                background: #f8fafc;
                font-family: 'Segoe UI';
            }
            QLabel {
                font-size: 11px; color: #334155;
                font-weight: 600;
            }
            QLineEdit {
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 4px 8px; font-size: 11px; background: white;
            }
            QPushButton {
                border-radius: 4px; padding: 5px 14px;
                font-size: 11px; font-weight: 600;
            }
        """)

        self._next_code = self._get_next_code()
        self._init_ui(initial_name)

    def _get_next_code(self) -> str:
        """Sonraki otomatik cari kodunu üret."""
        if self.db:
            try:
                from sqlalchemy import func, select

                from src.core.models import Customer
                count = self.db.scalar(
                    select(func.count()).select_from(Customer),
                ) or 0
                return f"C{count + 1:06d}"
            except Exception:
                pass
        import time
        return f"C{int(time.time()) % 1000000:06d}"

    def _init_ui(self, initial_name: str):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(20, 16, 20, 16)
        lyt.setSpacing(10)

        # Bilgi
        lbl_info = QLabel(
            "Hızlı cari tanımlama — ünvan zorunlu, diğerleri opsiyonel.",
        )
        lbl_info.setStyleSheet(
            "color:#64748b; font-size:10px; font-weight:400;",
        )
        lyt.addWidget(lbl_info)

        # Form grid
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setColumnMinimumWidth(0, 80)
        grid.setColumnStretch(1, 1)

        lbl_style = "font-size:11px; font-weight:600; color:#334155;"

        # Cari Kodu (readonly — otomatik)
        lbl_kod = QLabel("Cari Kodu:")
        lbl_kod.setStyleSheet(lbl_style)
        self.txt_kod = QLineEdit(self._next_code)
        self.txt_kod.setReadOnly(True)
        self.txt_kod.setToolTip("Otomatik atanır — değiştirilemez")
        self.txt_kod.setStyleSheet(
            "background:#f1f5f9; color:#64748b; "
            "border:1px solid #e2e8f0; border-radius:4px; padding:4px 8px;"
            "font-size:11px;",
        )
        grid.addWidget(lbl_kod, 0, 0)
        grid.addWidget(self.txt_kod, 0, 1)

        # Ünvan / Ad (zorunlu)
        lbl_name = QLabel("Ünvan / Ad: *")
        lbl_name.setStyleSheet(lbl_style + "color:#dc2626;")
        self.txt_name = QLineEdit(initial_name)
        self.txt_name.setPlaceholderText("Cari ünvan veya ad soyad... (zorunlu)")
        self.txt_name.setStyleSheet(
            "border:1px solid #cbd5e1; border-radius:4px; "
            "padding:4px 8px; font-size:11px; background:white;",
        )
        self.txt_name.returnPressed.connect(self.txt_vergi_no.setFocus
            if hasattr(self, "txt_vergi_no") else self._on_save)
        grid.addWidget(lbl_name, 1, 0)
        grid.addWidget(self.txt_name, 1, 1)

        # Vergi No (opsiyonel ama unique)
        lbl_vno = QLabel("Vergi No:")
        lbl_vno.setStyleSheet(lbl_style)
        self.txt_vergi_no = QLineEdit()
        self.txt_vergi_no.setPlaceholderText("Vergi No veya TCKN (opsiyonel)")
        self.txt_vergi_no.setStyleSheet(
            "border:1px solid #cbd5e1; border-radius:4px; "
            "padding:4px 8px; font-size:11px; background:white;",
        )
        self.txt_vergi_no.returnPressed.connect(self._on_save)
        grid.addWidget(lbl_vno, 2, 0)
        grid.addWidget(self.txt_vergi_no, 2, 1)

        # Vergi Dairesi (opsiyonel)
        lbl_vd = QLabel("Vergi D.:")
        lbl_vd.setStyleSheet(lbl_style)
        self.txt_vergi_daire_h = QLineEdit()
        self.txt_vergi_daire_h.setPlaceholderText("Vergi dairesi (opsiyonel)")
        self.txt_vergi_daire_h.setStyleSheet(
            "border:1px solid #cbd5e1; border-radius:4px; "
            "padding:4px 8px; font-size:11px; background:white;",
        )
        self.txt_vergi_daire_h.returnPressed.connect(self._on_save)
        grid.addWidget(lbl_vd, 3, 0)
        grid.addWidget(self.txt_vergi_daire_h, 3, 1)

        lyt.addLayout(grid)
        lyt.addStretch()

        # Butonlar
        btn_lyt = QHBoxLayout()
        btn_iptal = QPushButton("İptal")
        btn_iptal.setStyleSheet(
            "background:#f1f5f9; color:#475569; border:1px solid #cbd5e1;",
        )
        btn_iptal.clicked.connect(self.reject)

        self.btn_kaydet = QPushButton("💾 Kaydet ve Seç")
        self.btn_kaydet.setStyleSheet(
            "background:#2563eb; color:white; border:1px solid #1d4ed8;",
        )
        self.btn_kaydet.clicked.connect(self._on_save)
        self.btn_kaydet.setDefault(True)

        btn_lyt.addWidget(btn_iptal)
        btn_lyt.addStretch()
        btn_lyt.addWidget(self.btn_kaydet)
        lyt.addLayout(btn_lyt)

        self.txt_name.setFocus()

    def _on_save(self):
        name    = self.txt_name.text().strip()
        tax_no  = self.txt_vergi_no.text().strip()
        tax_d   = self.txt_vergi_daire_h.text().strip()

        # Ünvan zorunlu
        if not name:
            self.txt_name.setFocus()
            self.txt_name.setStyleSheet(
                "border:1px solid #ef4444; border-radius:4px; "
                "padding:4px 8px; font-size:11px; background:white;",
            )
            QMessageBox.warning(self, "Uyarı", "Ünvan / Ad zorunludur.")
            return

        code = self.txt_kod.text().strip()

        # DB'ye kaydet
        if self.db:
            try:
                from sqlalchemy import select

                from src.core.models import Customer

                # Vergi no unique kontrolü
                if tax_no:
                    existing = self.db.scalar(
                        select(Customer).where(
                            Customer.tax_number == tax_no,
                            Customer.is_deleted == False,
                        ),
                    )
                    if existing:
                        reply = QMessageBox.question(
                            self,
                            "Vergi No Mevcut",
                            f"Bu vergi numarası zaten kayıtlı:\n"
                            f"{existing.customer_code} — {existing.fullname}\n\n"
                            f"Yine de yeni kayıt oluşturulsun mu?",
                            QMessageBox.StandardButton.Yes
                            | QMessageBox.StandardButton.No,
                        )
                        if reply == QMessageBox.StandardButton.No:
                            # Mevcut cariyi seç
                            self.customer_added.emit({
                                "code":       existing.customer_code or "",
                                "name":       existing.fullname or "",
                                "tax_office": getattr(existing, "tax_office", "") or "",
                                "tax_no":     existing.tax_number or "",
                                "address":    getattr(existing, "address", "") or "",
                                "city":       "",
                                "balance":    "0,00 ₺",
                                "terms":      30,
                            })
                            self.accept()
                            return

                c = Customer()
                c.customer_code = code
                c.fullname      = name
                c.tax_number    = tax_no or None
                if hasattr(c, "tax_office"):
                    c.tax_office = tax_d or None
                c.is_deleted    = False
                self.db.add(c)
                self.db.commit()

            except Exception as e:
                logger.error(f"Hızlı cari eklenemedi: {e}")
                self.db.rollback()
                QMessageBox.critical(
                    self, "Hata", f"Cari eklenemedi:\n{e}",
                )
                return

        self.customer_added.emit({
            "code":       code,
            "name":       name,
            "tax_office": tax_d,
            "tax_no":     tax_no,
            "address":    "",
            "city":       "",
            "balance":    "0,00 ₺",
            "terms":      30,
        })
        self.accept()
