"""
TOYA ERP - DefinitionEditorScreen

Tanım ekranları (Firma, Şube, Depo, Cari Grubu, Ödeme Planı ...) için
yeniden kullanılabilir, yapılandırma güdümlü TAM EKRAN kayıt editörü.

Mimari: sol sidebar (bölüm gezinme + hızlı eylemler) · sekmeli gövde ·
sağ sidebar (özet + yardımcılar) · alt bar (Kaydet / Vazgeç).

Kullanım:
    TABS = [
        {"title": "Kimlik", "fields": [
            {"key": "code", "label": "Firma Kodu", "type": "text",
             "required": True, "lock_on_edit": True},
            {"key": "company_type", "label": "Şirket Tipi", "type": "combo",
             "options": ["Şahıs", "Tüzel"]},
            ...
        ]},
        {"title": "Adres", "fields": [...]},
    ]
    ed = DefinitionEditorScreen(title="Firma Detayı", tabs=TABS)
    ed.set_data({...})
    ed.saved.connect(on_saved)        # dict yayar
    data = ed.collect()

Alan tipleri: text · multiline · combo · int · number · bool · date · image · subtable
"""

from __future__ import annotations

import base64
import json
import logging

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFontMetrics, QKeySequence, QPixmap, QShortcut, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QDoubleSpinBox,
    QSpinBox,
    QTabWidget,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services import settings_store
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.widgets.catalog_picker import CatalogSearchField, make_search_button
from src.desktop.ui.widgets.masked_decimal_field import MaskedDecimalField
from src.desktop.ui.widgets.money_edit import MoneyEdit
from src.desktop.ui.widgets.parametric_field_group import ParametricFieldGroup

logger = logging.getLogger(__name__)

# Açılır listelerde (QComboBox) Windows'un klasik stili öğe başına ikon/onay
# işareti için soldan boşluk ayırır; "combobox-popup:0" açılır listeyi kendi
# QAbstractItemView'ı ile çizmeye zorlar, böylece metin gerçekten sola yaslanır.
_COMBO_QSS = (
    "QComboBox{padding:2px 6px;combobox-popup:0;}"
    "QComboBox QAbstractItemView{outline:0;border:1px solid #cbd5e1;}"
    "QComboBox QAbstractItemView::item{padding:4px 8px;min-height:22px;}"
)

_VAT_MODE_OPTIONS = ["KDV D", "KDV H"]


class _ImageField(QWidget):
    """Base64 görsel alanı: önizleme + Seç / Temizle."""

    def __init__(self, parent=None, preview_size: tuple[int, int] = (120, 64),
                 buttons_below: bool = False):
        super().__init__(parent)
        self._b64: str | None = None
        self._preview_size = preview_size
        self.preview = QLabel("—")
        self.preview.setFixedSize(*preview_size)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("border:1px solid #cbd5e1;border-radius:4px;background:#f8fafc;")
        btn_pick = QPushButton("Seç…")
        btn_pick.clicked.connect(self._pick)
        btn_clear = QPushButton("Temizle")
        btn_clear.clicked.connect(lambda: self.set_value(None))
        if buttons_below:
            lyt = QVBoxLayout(self)
            lyt.setContentsMargins(0, 0, 0, 0)
            lyt.setSpacing(6)
            lyt.addWidget(self.preview)
            row = QHBoxLayout()
            row.addWidget(btn_pick)
            row.addWidget(btn_clear)
            lyt.addLayout(row)
        else:
            lyt = QHBoxLayout(self)
            lyt.setContentsMargins(0, 0, 0, 0)
            lyt.setSpacing(6)
            lyt.addWidget(self.preview)
            col = QVBoxLayout()
            col.addWidget(btn_pick)
            col.addWidget(btn_clear)
            col.addStretch()
            lyt.addLayout(col)
            lyt.addStretch()

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Görsel Seç", "", "Görseller (*.png *.jpg *.jpeg *.bmp)",
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                self.set_value(base64.b64encode(f.read()).decode("ascii"))
        except Exception:  # noqa: BLE001
            logger.exception("Görsel okunamadı")

    def value(self) -> str | None:
        return self._b64

    def set_value(self, b64: str | None):
        self._b64 = b64 or None
        if self._b64:
            pm = QPixmap()
            try:
                pm.loadFromData(base64.b64decode(self._b64))
            except Exception:  # noqa: BLE001
                pm = QPixmap()
            if not pm.isNull():
                w, h = self._preview_size
                self.preview.setPixmap(
                    pm.scaled(w - 2, h - 2, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation),
                )
                self.preview.setText("")
                return
        self.preview.setPixmap(QPixmap())
        self.preview.setText("—")


class _SearchField(QWidget):
    """QLineEdit + 🔍 arama butonu. Değer düz metin."""

    def __init__(self, on_search=None, placeholder: str = "", parent=None):
        super().__init__(parent)
        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(3)
        self.edit = QLineEdit()
        if placeholder:
            self.edit.setPlaceholderText(placeholder)
        btn = make_search_button()
        if callable(on_search):
            btn.clicked.connect(lambda: on_search(self.edit.text().strip()))
        lyt.addWidget(self.edit, 1)
        lyt.addWidget(btn)

    def text(self) -> str:
        return self.edit.text()

    def setText(self, value):  # noqa: N802
        self.edit.setText("" if value is None else str(value))


class _WholeNumberSpinBox(QSpinBox):
    """KDV oranı gibi tam sayı alanlarında kullanıcı yanlışlıkla virgül/nokta
    girerse sessizce yok saymak yerine kısa bir uyarı balonu gösterir —
    girişi yine kabul etmez (KDV oranında ondalık hane olmaz), ama en azından
    kullanıcı neden hiçbir şey yazılmadığını anlar."""

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.text() in (",", "."):
            QToolTip.showText(
                self.mapToGlobal(QPoint(0, self.height())),
                "KDV oranı tam sayı olmalıdır — ondalık hane girilemez.",
                self,
            )
            event.accept()
            return
        super().keyPressEvent(event)


class _IntCatalogField(QWidget):
    """QSpinBox + mavi 🔍 butonu; buton paylaşılan bir sayısal değer kataloğu
    (ör. KDV Tanımları) açar ve seçilen değeri kutuya yazar."""

    def __init__(self, *, catalog_key: str, db_session=None, defaults: list[str] | None = None,
                 minimum: int = 0, maximum: int = 100, title: str = "Kayıtlı Değerler",
                 parent=None):
        super().__init__(parent)
        self._catalog_key = catalog_key
        self._db = db_session
        self._defaults = defaults
        self._title = title
        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(3)
        self.spin = _WholeNumberSpinBox()
        self.spin.setRange(minimum, maximum)
        btn = make_search_button()
        btn.clicked.connect(self._open_picker)
        lyt.addWidget(self.spin, 1)
        lyt.addWidget(btn)

    def _open_picker(self) -> None:
        from src.desktop.ui.widgets.catalog_picker import open_catalog_picker
        chosen = open_catalog_picker(
            self, self._db, self._catalog_key, str(self.spin.value()),
            defaults=self._defaults, title=self._title,
        )
        if chosen is None:
            return
        try:
            self.spin.setValue(int(float(chosen.replace("%", "").strip())))
        except (TypeError, ValueError):
            pass

    def value(self) -> int:
        return self.spin.value()

    def setValue(self, v) -> None:  # noqa: N802
        try:
            self.spin.setValue(int(float(v)) if v not in (None, "") else 0)
        except (TypeError, ValueError):
            self.spin.setValue(0)


class _MoneyField(QWidget):
    """Maskeli ondalık tutar alanı + para birimi + opsiyonel hesap butonu."""

    def __init__(self, *, currencies=None, on_calc=None, decimals: int = 2,
                 maximum: float = 1e12, vat_mode: bool = False, parent=None):
        super().__init__(parent)
        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(3)
        self.spin = MaskedDecimalField(decimals=decimals)
        self.spin.setMinimumWidth(80)
        self.spin.setMaximumWidth(150)
        self.currency = None
        if currencies:
            self.currency = QComboBox()
            self.currency.addItems([str(c) for c in currencies])
            self.currency.setFixedWidth(64)
            self.currency.setStyleSheet(_COMBO_QSS)
        self.vat_combo = None
        if vat_mode:
            self.vat_combo = QComboBox()
            self.vat_combo.addItems(_VAT_MODE_OPTIONS)
            self.vat_combo.setCurrentIndex(1)  # varsayılan: KDV Hariç (H)
            self.vat_combo.setFixedWidth(88)
            self.vat_combo.setStyleSheet(_COMBO_QSS)
        lyt.addWidget(self.spin, 1)
        if self.currency is not None:
            lyt.addWidget(self.currency)
        if self.vat_combo is not None:
            lyt.addWidget(self.vat_combo)
        if callable(on_calc):
            btn = QPushButton("🧮")
            btn.setFixedWidth(22)
            btn.clicked.connect(lambda: on_calc(self))
            lyt.addWidget(btn)

    def value(self) -> float:
        return self.spin.value()

    def setValue(self, v):  # noqa: N802
        try:
            self.spin.setValue(float(v or 0))
        except (TypeError, ValueError):
            self.spin.setValue(0.0)

    def currency_text(self) -> str:
        return self.currency.currentText() if self.currency is not None else ""

    def set_currency_text(self, t):
        if self.currency is not None and t:
            i = self.currency.findText(str(t))
            if i >= 0:
                self.currency.setCurrentIndex(i)

    def vat_mode_text(self) -> str:
        return self.vat_combo.currentText() if self.vat_combo is not None else ""

    def set_vat_mode_text(self, t):
        if self.vat_combo is None:
            return
        i = self.vat_combo.findText(str(t)) if t else -1
        self.vat_combo.setCurrentIndex(i if i >= 0 else 1)  # varsayılan: KDV Hariç


class _SubTableField(QWidget):
    """list[dict] tutan çok satırlı alan (satır ekle/sil/düzenle) — uygulamadaki
    diğer "standart" DB grid'leriyle (belge kalem/masraf gridleri) aynı çekirdeği
    (`FilterableTableView`, entry modu) kullanır: işaretleme kolonu, sürüklenebilir
    ve gizlenebilir sütunlar, sağ tık "Sütunlar" alt menüsü."""

    COL_SELECT = 0

    def __init__(self, columns: list[dict], parent=None, profile_key: str = "card_subtable"):
        super().__init__(parent)
        self._cols = columns  # [{"key","label"}]
        headers_dict: dict[int, tuple[str, str]] = {self.COL_SELECT: ("☑", "select")}
        for i, col in enumerate(columns, start=1):
            headers_dict[i] = (col["label"], col["key"])

        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(4)

        self.grid = FilterableTableView(
            headers_dict=headers_dict, profile_key=profile_key,
            select_column=self.COL_SELECT, mode="entry",
        )
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels([headers_dict[c][0] for c in sorted(headers_dict)])
        self.grid.table_view.setModel(self.model)
        self.grid.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.table_view.customContextMenuRequested.connect(self._show_context_menu)
        self.grid.setMinimumHeight(120)
        lyt.addWidget(self.grid, 1)

        bar = QHBoxLayout()
        b_add = QPushButton("➕ Satır Ekle")
        b_add.clicked.connect(lambda: self._add_row({}))
        b_del = QPushButton("🗑️ Seçili Satırları Sil")
        b_del.clicked.connect(self._del_checked_rows)
        bar.addWidget(b_add)
        bar.addWidget(b_del)
        bar.addStretch()
        lyt.addLayout(bar)

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        a_add = QAction("➕ Satır Ekle", self)
        a_add.triggered.connect(lambda: self._add_row({}))
        a_del = QAction("🗑️ Seçili Satırları Sil", self)
        a_del.triggered.connect(self._del_checked_rows)
        menu.addAction(a_add)
        menu.addAction(a_del)
        menu.addSeparator()
        self.grid.add_column_actions_to_menu(menu)
        menu.exec(self.grid.table_view.viewport().mapToGlobal(pos))

    def _add_row(self, rec: dict) -> None:
        chk = QStandardItem("")
        chk.setCheckable(True)
        chk.setCheckState(Qt.CheckState.Unchecked)
        chk.setEditable(False)
        row = [chk]
        for col in self._cols:
            row.append(QStandardItem(str(rec.get(col["key"], ""))))
        self.model.appendRow(row)

    def _del_checked_rows(self) -> None:
        rows = sorted(self.grid.get_checked_rows(), reverse=True)
        if not rows:
            sel = self.grid.table_view.selectionModel().selectedRows()
            rows = sorted({i.row() for i in sel}, reverse=True)
        for r in rows:
            self.model.removeRow(r)

    def value(self) -> list[dict]:
        out = []
        for r in range(self.model.rowCount()):
            rec = {}
            for i, col in enumerate(self._cols, start=1):
                it = self.model.item(r, i)
                rec[col["key"]] = it.text().strip() if it else ""
            if any(rec.values()):
                out.append(rec)
        return out

    def set_value(self, rows: list[dict] | None) -> None:
        self.model.removeRows(0, self.model.rowCount())
        for rec in (rows or []):
            self._add_row(rec)


class _PermTreeField(QWidget):
    """
    Yetki ağacı. groups = [(mod_code, mod_name, [(act_code, act_name), ...])]
    value() -> ["mod.act", ...]  ("*" -> hepsi seçili).
    """

    def __init__(self, groups: list, parent=None):
        super().__init__(parent)
        self._groups = groups
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(4)
        bar = QHBoxLayout()
        b_all = QPushButton("Tümünü Seç")
        b_all.clicked.connect(lambda: self._set_all(True))
        b_none = QPushButton("Tümünü Kaldır")
        b_none.clicked.connect(lambda: self._set_all(False))
        bar.addWidget(b_all)
        bar.addWidget(b_none)
        bar.addStretch()
        lyt.addLayout(bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumHeight(320)
        self._leaf_items: dict[str, QTreeWidgetItem] = {}
        for mod_code, mod_name, actions in groups:
            top = QTreeWidgetItem(self.tree, [mod_name])
            top.setExpanded(True)
            top.setFlags(top.flags() | Qt.ItemFlag.ItemIsAutoTristate
                         | Qt.ItemFlag.ItemIsUserCheckable)
            top.setCheckState(0, Qt.CheckState.Unchecked)
            for act_code, act_name in actions:
                leaf = QTreeWidgetItem(top, [act_name])
                leaf.setFlags(leaf.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                leaf.setCheckState(0, Qt.CheckState.Unchecked)
                self._leaf_items[f"{mod_code}.{act_code}"] = leaf
        lyt.addWidget(self.tree)

    def _set_all(self, on: bool):
        st = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        for leaf in self._leaf_items.values():
            leaf.setCheckState(0, st)

    def value(self) -> list[str]:
        codes = [c for c, it in self._leaf_items.items()
                 if it.checkState(0) == Qt.CheckState.Checked]
        if len(codes) == len(self._leaf_items):
            return ["*"]
        return codes

    def set_value(self, codes: list[str] | None):
        codes = codes or []
        wildcard = "*" in codes
        for c, leaf in self._leaf_items.items():
            on = wildcard or c in codes
            leaf.setCheckState(0, Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)


class DefinitionEditorScreen(QWidget):
    """Yapılandırma güdümlü tam ekran tanım editörü."""

    saved = pyqtSignal(dict)
    saved_and_new = pyqtSignal(dict)
    closed = pyqtSignal()

    def __init__(
        self,
        title: str,
        tabs: list[dict],
        *,
        code: str = "",
        code_field: str | None = None,
        title_field: str | None = None,
        header_extra_field: str | None = None,
        status_field: str | None = None,
        status_map: dict | None = None,
        extra_actions: list[dict] | None = None,
        summary_provider=None,
        summary_widget: QWidget | None = None,
        nav_sidebar: bool = True,
        show_section_nav: bool = True,
        enable_save_and_new: bool = False,
        right_panel_width: int = 240,
        left_panel_width: int = 190,
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._tabs_spec = tabs
        self._is_edit = False
        self._widgets: dict[str, QWidget] = {}
        self._field_specs: dict[str, dict] = {}
        self._field_labels: dict[str, QLabel] = {}
        self._extra_action_buttons: list[tuple[QPushButton, bool]] = []
        # Her sekme için, o sekmedeki bölümlerin (section) sırasıyla ilk
        # odaklanabilir alanı — Ctrl+<N> kısayoluyla o bölüme atlamak için.
        self._tab_sections: list[list[QWidget]] = []
        self._right_panel_width = right_panel_width
        self._left_panel_width = left_panel_width
        # tpl.card.001 standardı
        self._code_field = code_field
        self._title_field = title_field
        self._header_extra_field = header_extra_field
        self._status_field = status_field
        self._status_map = status_map or {
            True: ("🟢 Aktif", "#16a34a"),
            False: ("⚪ Pasif", "#64748b"),
        }
        self._extra_actions = extra_actions or []
        self._summary_provider = summary_provider
        self._summary_widget = summary_widget
        self._nav_sidebar = nav_sidebar
        self._show_section_nav = show_section_nav
        self._enable_save_and_new = enable_save_and_new
        self._build_ui()
        self._wire_live_refresh()
        QShortcut(QKeySequence("F2"), self, activated=self._on_save)
        QShortcut(QKeySequence("Esc"), self, activated=self.closed.emit)
        # Sadece klavye kullanan kullanıcılar için: Ctrl+<N> aktif sekmedeki
        # N. bölüme (ör. "1. Ürün Kimliği") odaklanır; Ctrl+Shift+<N> N.
        # sekmeye geçer (ör. Ctrl+Shift+2 -> "2. Gelişmiş Fiyat Tanımlama"),
        # ardından o sekmede yine Ctrl+1 ile ilk bölümüne atlanabilir. Bölüm/
        # sekme yapısına göre otomatik kurulduğundan her karta aynı şekilde
        # uygulanan genel bir şablondur.
        for n in range(1, 10):
            QShortcut(QKeySequence(f"Ctrl+{n}"), self,
                      activated=lambda n=n: self._focus_section(n))
            QShortcut(QKeySequence(f"Ctrl+Shift+{n}"), self,
                      activated=lambda n=n: self._goto_tab(n))

    # ------------------------------------------------------------------
    def _wire_live_refresh(self):
        """Alan değişimlerinde header + özet paneli canlı güncellenir."""
        watch_keys = {
            k for k in (self._code_field, self._title_field, self._status_field,
                        self._header_extra_field) if k
        }
        for key in watch_keys:
            w = self._widgets.get(key)
            if isinstance(w, QLineEdit):
                w.textChanged.connect(self._refresh_header)
            elif isinstance(w, QPlainTextEdit):
                w.textChanged.connect(self._refresh_header)
            elif isinstance(w, QCheckBox):
                w.toggled.connect(self._refresh_header)
            elif isinstance(w, QComboBox):
                w.currentTextChanged.connect(self._refresh_header)
            elif isinstance(w, (_SearchField, CatalogSearchField)):
                w.edit.textChanged.connect(self._refresh_header)
        # Header'daki durum combosu ↔ formdaki bool alan senkron (varsa)
        sw = self._widgets.get(self._status_field) if self._status_field else None
        if isinstance(sw, QCheckBox) and getattr(self, "cmb_header_status", None):
            sw.toggled.connect(
                lambda on: self.cmb_header_status.setCurrentText("Aktif" if on else "Pasif"),
            )
            self.cmb_header_status.currentTextChanged.connect(
                lambda t: sw.setChecked(t == "Aktif"),
            )
        elif self._status_field and getattr(self, "cmb_header_status", None):
            # Formda ayrı bir durum alanı yok — tek gerçek kaynak header'daki combo.
            self.cmb_header_status.currentTextChanged.connect(self._refresh_header)
            self.cmb_header_status.currentTextChanged.connect(self._refresh_summary)
        if self._summary_provider or self._summary_widget:
            for w in self._widgets.values():
                if isinstance(w, QLineEdit):
                    w.textChanged.connect(self._refresh_summary)
                elif isinstance(w, QPlainTextEdit):
                    w.textChanged.connect(self._refresh_summary)
                elif isinstance(w, QCheckBox):
                    w.toggled.connect(self._refresh_summary)
                elif isinstance(w, QComboBox):
                    w.currentTextChanged.connect(self._refresh_summary)
                elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                    w.valueChanged.connect(self._refresh_summary)
                elif isinstance(w, _MoneyField):
                    w.spin.valueChanged.connect(self._refresh_summary)
                elif isinstance(w, _SearchField):
                    w.edit.textChanged.connect(self._refresh_summary)

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        if self._nav_sidebar:
            outer.addWidget(self._build_left_panel())

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)
        root.addWidget(self._build_header())

        self.tabw = QTabWidget()
        self.tabw.setStyleSheet(
            "QTabBar::tab{height:28px;padding:0 16px;font-size:11px;font-weight:700;}"
            "QTabWidget::pane{border:1px solid #e2e8f0;}",
        )
        for i, tab in enumerate(self._tabs_spec):
            # '&' QTabBar'da kısayol işareti sayılır -> '&&' ile düz metin
            label = f"{i + 1}. {tab['title']}".replace("&", "&&")
            self._tab_sections.append([])
            self.tabw.addTab(self._build_tab(tab), label)
        root.addWidget(self.tabw, 1)
        root.addWidget(self._build_footer())
        outer.addWidget(content, 1)

        outer.addWidget(self._build_right_panel())
        self._fix_enter_key_default_button()

    def _fix_enter_key_default_button(self) -> None:
        """Yalnızca klavye kullanan kullanıcılar için: Qt'de bir QPushButton
        odak aldığında kendini otomatik "varsayılan" (Enter'a basınca
        tetiklenen) buton yapar (`autoDefault`). Bu formda çok sayıda buton
        (sol panel İşlemler/Raporlar, sekme/bölüm kısayolları vb.) olduğundan,
        bir alandan Tab ile geçerken Enter'a basmak beklenmedik bir sol
        sidebar butonunu tetikleyebiliyordu. Burada tek seferde tüm
        butonların autoDefault'u kapatılır, yalnızca "Kaydet" varsayılan
        bırakılır — böylece herhangi bir metin alanındayken Enter'a basmak
        güvenilir şekilde kaydeder."""
        for b in self.findChildren(QPushButton):
            if b is self._btn_save:
                continue
            b.setAutoDefault(False)
            b.setDefault(False)
        self._btn_save.setAutoDefault(True)
        self._btn_save.setDefault(True)

    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("DefHeader")
        # WA_StyledBackground olmadan bazı Windows stillerinde QFrame zemini
        # çocuk widget'ların arkasında düzgün boyanmayıp okunaksız bir karışım
        # bırakabiliyor; tek düz renk + bu bayrak zemini garanti eder.
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        bar.setStyleSheet("#DefHeader{background:#1e3a8a;border-radius:6px;}")
        lyt = QHBoxLayout(bar)
        lyt.setContentsMargins(12, 6, 12, 6)
        lyt.setSpacing(10)
        self.lbl_title = QLabel(f"📄 {self._title}")
        self.lbl_title.setStyleSheet(
            "color:#ffffff;background:transparent;font-size:13px;font-weight:800;",
        )
        lyt.addWidget(self.lbl_title)
        # Kod + kayıt başlığı (tpl.card.001)
        self.lbl_record = QLabel("")
        self.lbl_record.setStyleSheet(
            "color:#ffffff;background:transparent;font-size:12px;font-weight:600;",
        )
        lyt.addWidget(self.lbl_record)
        lyt.addStretch()
        self.lbl_status_badge = QLabel("")
        self.lbl_status_badge.setStyleSheet(
            "color:#fff;font-size:11px;font-weight:700;padding:2px 10px;border-radius:9px;",
        )
        self.lbl_status_badge.setVisible(False)
        lyt.addWidget(self.lbl_status_badge)

        # Bool durum alanı için header'da hızlı Aktif/Pasif seçici (görseldeki gibi)
        self.cmb_header_status = None
        if self._status_field:
            spec = next(
                (f for t in self._tabs_spec for f in self._iter_specs(t)
                 if f.get("key") == self._status_field),
                None,
            )
            # Alan şemasında ayrı bir gövde alanı yoksa (ör. tekrarı önlemek için
            # kaldırıldıysa) varsayılan olarak yine de bool kabul edilir.
            if spec is None or spec.get("type") == "bool":
                self.cmb_header_status = QComboBox()
                self.cmb_header_status.addItems(["Aktif", "Pasif"])
                self.cmb_header_status.setFixedWidth(96)
                self.cmb_header_status.setStyleSheet(
                    "QComboBox{background:#2563eb;color:#ffffff;border:1px solid #93c5fd;"
                    "border-radius:6px;padding:2px 8px;font-size:11px;combobox-popup:0;}"
                    "QComboBox QAbstractItemView{outline:0;background:#2563eb;color:#ffffff;"
                    "border:1px solid #93c5fd;}"
                    "QComboBox QAbstractItemView::item{padding:4px 8px;min-height:20px;}",
                )
                lyt.addWidget(self.cmb_header_status)
        return bar

    @staticmethod
    def _iter_specs(tab: dict):
        """Sekmedeki tüm alan spec'lerini gezer (fields veya bands şeması)."""
        if tab.get("bands"):
            for band in tab["bands"]:
                for section in band.get("sections", []):
                    yield from section.get("fields", [])
        else:
            yield from tab.get("fields", [])

    def _refresh_header(self):
        if not hasattr(self, "lbl_record"):
            return
        d = self.collect()
        code = str(d.get(self._code_field, "")).strip() if self._code_field else ""
        name = str(d.get(self._title_field, "")).strip() if self._title_field else ""
        extra = str(d.get(self._header_extra_field, "")).strip() \
            if self._header_extra_field else ""
        parts = [p for p in (code, name, extra) if p]
        self.lbl_record.setText("  ·  ".join(parts))

        if self._status_field and self._status_field in self._widgets:
            raw = d.get(self._status_field)
            key = bool(raw) if isinstance(raw, bool) else raw
            label, color = self._status_map.get(
                key, self._status_map.get(bool(raw), ("", "#64748b")),
            )
            if label:
                self.lbl_status_badge.setText(label)
                self.lbl_status_badge.setStyleSheet(
                    f"background:{color};color:#fff;font-size:11px;font-weight:700;"
                    "padding:2px 10px;border-radius:9px;",
                )
                self.lbl_status_badge.setVisible(True)
            else:
                self.lbl_status_badge.setVisible(False)

    def _build_tab(self, tab: dict) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        if tab.get("bands"):
            scroll.setWidget(self._build_bands_tab(tab["bands"]))
            return scroll

        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(14, 12, 14, 12)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        first_widget: QWidget | None = None
        for spec in tab["fields"]:
            self._field_specs[spec["key"]] = spec
            widget = self._make_field(spec)
            self._widgets[spec["key"]] = widget
            if first_widget is None:
                first_widget = widget
            lbl = spec["label"] + (" *" if spec.get("required") else "")
            if spec["type"] in ("subtable",):
                form.addRow(QLabel(f"<b>{lbl}</b>"))
                form.addRow(widget)
            else:
                form.addRow(lbl + ":", widget)
        if self._tab_sections and first_widget is not None:
            self._tab_sections[-1].append(self._focus_target(first_widget))
        scroll.setWidget(w)
        return scroll

    # -- bands (çok kolonlu bölümlü) yerleşim --------------------------
    def _build_bands_tab(self, bands: list[dict]) -> QWidget:
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(8, 8, 8, 8)
        col.setSpacing(8)
        for band in bands:
            row = QHBoxLayout()
            row.setSpacing(8)
            for section in band.get("sections", []):
                row.addWidget(self._build_section(section), section.get("stretch", 1))
            col.addLayout(row)
        col.addStretch()
        return w

    def _build_section(self, section: dict) -> QWidget:
        box = QFrame()
        box.setObjectName("DefSection")
        box.setStyleSheet(
            "#DefSection{background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;}",
        )
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(6)

        title = section.get("title", "")
        edit_cfg = section.get("editable_labels")
        overrides: dict[str, str] = {}
        if edit_cfg and edit_cfg.get("db_session"):
            overrides = settings_store.get_json(
                edit_cfg["db_session"], f"param_labels:{edit_cfg['scope']}", {},
            ) or {}
        if title:
            numbered = section.get("blue_header", title[:2].strip().rstrip(".").isdigit())
            hdr = QWidget()
            hdr_lyt = QHBoxLayout(hdr)
            hdr_lyt.setContentsMargins(10, 4, 10, 4) if numbered else \
                hdr_lyt.setContentsMargins(10, 6, 10, 0)
            hdr_lyt.setSpacing(6)
            lbl_title = QLabel(title)
            lbl_title.setStyleSheet(
                "color:#fff;font-size:11px;font-weight:800;" if numbered else
                "color:#475569;font-size:11px;font-weight:800;",
            )
            hdr_lyt.addWidget(lbl_title)
            hdr_lyt.addStretch()
            if edit_cfg and not edit_cfg.get("hide_button"):
                btn_lbl = QPushButton(edit_cfg.get("button_text", "✏ Alan Adlarını Düzenle"))
                btn_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_lbl.setStyleSheet(
                    "QPushButton{background:transparent;border:none;font-size:10px;"
                    "font-weight:700;" + ("color:#dbeafe;" if numbered else "color:#2563eb;") +
                    "}QPushButton:hover{text-decoration:underline;}",
                )
                btn_lbl.clicked.connect(
                    lambda _c=False, sec=section, cfg=edit_cfg: self._edit_section_labels(sec, cfg),
                )
                hdr_lyt.addWidget(btn_lbl)
            if numbered:
                hdr.setStyleSheet(
                    "background:#1e3a8a;border-top-left-radius:8px;border-top-right-radius:8px;",
                )
            hdr.setFixedHeight(hdr.sizeHint().height())     # başlık şeridi içeriğinden büyümez (yan yana bölüm yüksekliği eşitlenirken şişmesin)
            outer.addWidget(hdr)

        grid = QGridLayout()
        grid.setContentsMargins(8, 4, 8, 4)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(6)
        cols = max(1, int(section.get("columns", 1)))
        r = c = 0
        first_widget: QWidget | None = None
        for spec in section.get("fields", []):
            self._field_specs[spec["key"]] = spec
            widget = self._make_field(spec)
            self._widgets[spec["key"]] = widget
            if first_widget is None:
                first_widget = widget
            if spec["type"] in ("param_group",):
                if c != 0:
                    c = 0
                    r += 1
                grid.addWidget(widget, r, 0, 1, cols * 2)
                r += 1
                continue
            label_text = overrides.get(spec["key"], spec["label"])
            spec["label"] = label_text
            lbl = QLabel(label_text + (" *" if spec.get("required") else "") + ":")
            lbl.setStyleSheet("font-size:11px;color:#334155;font-weight:600;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self._field_labels[spec["key"]] = lbl
            span = max(1, int(spec.get("span", 1)))
            grid.addWidget(lbl, r, c * 2)
            grid.addWidget(widget, r, c * 2 + 1, 1, span * 2 - 1)
            c += span
            if c >= cols:
                c = 0
                r += 1
        for i in range(cols):
            grid.setColumnStretch(i * 2 + 1, 1)
        outer.addLayout(grid)
        outer.addStretch(1)                                  # artan yükseklik alanların altında kalır, başlığa/alanlara dağılmaz
        if self._tab_sections and first_widget is not None:
            self._tab_sections[-1].append(self._focus_target(first_widget))
        return box

    @staticmethod
    def _focus_target(widget: QWidget) -> QWidget:
        """Ctrl+<N> ile bir bölüme atlarken, bileşik alan sarmalayıcıları
        (ör. `_MoneyField`, `_SearchField`) yerine asıl yazılabilir alt
        widget'a odaklanılır."""
        if isinstance(widget, (_MoneyField, _IntCatalogField)):
            return widget.spin
        if isinstance(widget, (_SearchField, CatalogSearchField)):
            return widget.edit
        if isinstance(widget, ParametricFieldGroup):
            return widget.first_focusable() or widget
        return widget

    def _edit_section_labels(self, section: dict, cfg: dict) -> None:
        db = cfg.get("db_session")
        scope = cfg["scope"]
        fields = [f for f in section.get("fields", []) if f["type"] != "param_group"]
        dlg = QDialog(self)
        dlg.setWindowTitle("Alan Adlarını Düzenle")
        lyt = QVBoxLayout(dlg)
        edits: dict[str, QLineEdit] = {}
        for f in fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(f["label"] + ":"))
            e = QLineEdit(self._field_specs[f["key"]].get("label", f["label"]))
            edits[f["key"]] = e
            row.addWidget(e, 1)
            lyt.addLayout(row)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        lyt.addWidget(box)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data: dict[str, str] = {}
        for f in fields:
            text = edits[f["key"]].text().strip() or f["label"]
            data[f["key"]] = text
            self._field_specs[f["key"]]["label"] = text
            lbl_w = self._field_labels.get(f["key"])
            if lbl_w:
                req = " *" if self._field_specs[f["key"]].get("required") else ""
                lbl_w.setText(text + req + ":")
        if db:
            settings_store.set_setting(db, f"param_labels:{scope}", json.dumps(data, ensure_ascii=False))

    @staticmethod
    def _resolve_decimals(spec: dict) -> int:
        """Alanın ondalık hane sayısını döndürür: Genel Ayarlar'daki
        `DECIMAL_PLACES_SETTING_KEY` ayarı varsa onu, yoksa alanın kendi
        `decimals` değerini (varsayılan 2) kullanır."""
        db = spec.get("db_session")
        fallback = spec.get("decimals", 2)
        if not db:
            return fallback
        return settings_store.get_int(db, settings_store.DECIMAL_PLACES_KEY, fallback)

    def _make_field(self, spec: dict) -> QWidget:
        t = spec["type"]
        if t == "combo":
            cb = QComboBox()
            cb.setEditable(bool(spec.get("editable")))
            cb.setStyleSheet(_COMBO_QSS)
            provider = spec.get("options_provider")
            options = list(spec.get("options", []))
            if callable(provider):
                try:
                    options = list(provider()) or options
                except Exception:  # noqa: BLE001
                    logger.exception("options_provider hatası (%s)", spec.get("key"))
            cb.addItems([str(o) for o in options])
            return cb
        if t == "multiline":
            pt = QPlainTextEdit()
            pt.setFixedHeight(spec.get("height", 70))
            return pt
        if t == "int":
            sp = QSpinBox()
            sp.setRange(spec.get("min", 0), spec.get("max", 1_000_000))
            return sp
        if t == "number":
            sp = QDoubleSpinBox()
            sp.setRange(spec.get("min", 0.0), spec.get("max", 1e12))
            sp.setDecimals(spec.get("decimals", 2))
            sp.setGroupSeparatorShown(True)
            if spec.get("suffix"):
                sp.setSuffix(" " + spec["suffix"])
            if spec.get("readonly"):
                sp.setReadOnly(True)
                sp.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            return sp
        if t == "tutar":                     # ortak para alanı: binlik nokta, kuruş, + - * / hesap makinesi
            return MoneyEdit(decimals=spec.get("decimals", 2), allow_negative=bool(spec.get("negative")))
        if t == "bool":
            return QCheckBox(spec.get("text", ""))
        if t == "search":
            return _SearchField(
                on_search=spec.get("on_search"),
                placeholder=spec.get("placeholder", ""),
            )
        if t == "catalog_search":
            return CatalogSearchField(
                catalog_key=spec["catalog_key"],
                db_session=spec.get("db_session"),
                defaults=spec.get("defaults"),
                placeholder=spec.get("placeholder", ""),
                title=spec.get("catalog_title", "Kayıtlı Değerler"),
            )
        if t == "int_catalog":
            return _IntCatalogField(
                catalog_key=spec["catalog_key"],
                db_session=spec.get("db_session"),
                defaults=spec.get("defaults"),
                minimum=spec.get("min", 0),
                maximum=spec.get("max", 100),
                title=spec.get("catalog_title", "Kayıtlı Değerler"),
            )
        if t == "money":
            return _MoneyField(
                currencies=spec.get("currencies"),
                on_calc=spec.get("on_calc"),
                decimals=self._resolve_decimals(spec),
                maximum=spec.get("max", 1e12),
                vat_mode=spec.get("vat_mode", False),
            )
        if t == "image":
            return _ImageField(preview_size=spec.get("preview_size", (120, 64)))
        if t == "subtable":
            return _SubTableField(
                spec.get("columns", []),
                profile_key=f"card_subtable_{spec['key']}",
            )
        if t == "permtree":
            return _PermTreeField(spec.get("groups", []))
        if t == "param_group":
            return ParametricFieldGroup(
                scope=spec["scope"],
                count=spec.get("count", 10),
                start_index=spec.get("start_index", 1),
                kind=spec.get("kind", "text"),
                default_labels=spec.get("default_labels"),
                default_name=spec.get("default_name", "Alan"),
                db_session=spec.get("db_session"),
                columns=spec.get("columns", 2),
                searchable_slots=spec.get("searchable_slots"),
                on_search=spec.get("on_search"),
                visible_default=spec.get("visible_default"),
                button_text=spec.get("button_text", "✏ Alan Adlarını Düzenle"),
                show_button=spec.get("show_button", True),
                vat_mode=spec.get("vat_mode", False),
                currencies=spec.get("currencies"),
                decimals=self._resolve_decimals(spec),
            )
        # text / password / number / date -> QLineEdit
        le = QLineEdit()
        if t == "password":
            le.setEchoMode(QLineEdit.EchoMode.Password)
        if spec.get("placeholder"):
            le.setPlaceholderText(spec["placeholder"])
        if spec.get("readonly"):
            le.setReadOnly(True)
        return le

    def _build_footer(self) -> QWidget:
        bar = QWidget()
        lyt = QHBoxLayout(bar)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(6)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#dc2626;font-size:11px;font-weight:600;")
        lyt.addWidget(self.lbl_status)
        lyt.addStretch()

        # Sol nav paneli açıksa ekstra eylemler zaten "İŞLEMLER" bölümünde —
        # burada tekrar göstermeyip footer'ı Kaydet/Vazgeç ile sade tutuyoruz.
        if not self._nav_sidebar:
            for act in self._extra_actions:
                b = QPushButton(act.get("label", "İşlem"))
                b.setStyleSheet(
                    "QPushButton{background:#eef2ff;color:#4338ca;border:1px solid #c7d2fe;"
                    "font-size:11px;padding:0 14px;height:30px;border-radius:6px;}"
                    "QPushButton:hover{background:#e0e7ff;}",
                )
                cb = act.get("callback")
                if callable(cb):
                    b.clicked.connect(lambda _c=False, fn=cb: fn())
                lyt.addWidget(b)
                self._extra_action_buttons.append((b, bool(act.get("enabled_on_edit"))))

        b_cancel = QPushButton("❌ Vazgeç (Esc)")
        b_cancel.setStyleSheet(
            "QPushButton{background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;"
            "font-size:11px;padding:0 16px;height:30px;border-radius:6px;}",
        )
        b_cancel.clicked.connect(self.closed.emit)
        if self._enable_save_and_new:
            b_save_new = QPushButton("💾+ Kaydet ve Yeni")
            b_save_new.setStyleSheet(
                "QPushButton{background:#eef2ff;color:#3730a3;border:1px solid #c7d2fe;"
                "font-weight:700;font-size:11px;padding:0 16px;height:30px;border-radius:6px;}"
                "QPushButton:hover{background:#e0e7ff;}",
            )
            b_save_new.clicked.connect(lambda: self._on_save(and_new=True))
        b_save = QPushButton("💾 Kaydet (F2)")
        b_save.setStyleSheet(
            "QPushButton{background:#2563eb;color:#fff;border:1px solid #2563eb;"
            "font-weight:700;font-size:11px;padding:0 18px;height:30px;border-radius:6px;}"
            "QPushButton:hover{background:#1d4ed8;}",
        )
        b_save.clicked.connect(lambda: self._on_save())
        self._btn_save = b_save
        lyt.addWidget(b_cancel)
        if self._enable_save_and_new:
            lyt.addWidget(b_save_new)
        lyt.addWidget(b_save)
        return bar

    @staticmethod
    def _elide(text: str, avail_px: int) -> str:
        fm = QFontMetrics(QPushButton().font())
        return fm.elidedText(text, Qt.TextElideMode.ElideRight, max(avail_px, 40))

    _GROUP_TITLES = {"islemler": "İŞLEMLER", "raporlar": "RAPORLAR"}

    def _build_left_panel(self) -> QWidget:
        frame = QFrame()
        frame.setFixedWidth(self._left_panel_width)
        frame.setStyleSheet("background:transparent;border:none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(4, 4, 4, 4)
        lyt.setSpacing(6)
        avail_px = self._left_panel_width - 44

        if self._show_section_nav:
            sec = CollapsibleSection("BÖLÜMLER", is_expanded=True)
            self._nav_buttons = []
            for i, tab in enumerate(self._tabs_spec):
                full_text = f"{i + 1}. {tab['title']}"
                b = QPushButton("  " + self._elide(full_text, avail_px).replace("&", "&&"))
                b.setToolTip(full_text)
                b.setStyleSheet(
                    "QPushButton{background:#fff;color:#1e293b;border:1px solid #cbd5e1;"
                    "border-radius:4px;padding:5px 8px;font-size:11px;text-align:left;}"
                    "QPushButton:hover{background:#eff6ff;}",
                )
                b.clicked.connect(lambda _c=False, idx=i: self.tabw.setCurrentIndex(idx))
                sec.add_widget(b)
                self._nav_buttons.append(b)
            lyt.addWidget(sec)

        # Kaydet / Vazgeç zaten alt bardadır — burada tekrarlanmıyor; sol panel
        # sadece ekstra aksiyonları, "İşlemler" ve "Raporlar" olarak gruplayıp gösterir.
        self._extra_action_buttons: list[tuple[QPushButton, bool]] = \
            getattr(self, "_extra_action_buttons", [])
        groups: dict[str, list[dict]] = {}
        for act in self._extra_actions:
            groups.setdefault(act.get("group", "islemler"), []).append(act)
        for group_key in ("islemler", "raporlar"):
            acts = groups.get(group_key)
            if not acts:
                continue
            sec_group = CollapsibleSection(self._GROUP_TITLES[group_key], is_expanded=True)
            for act in acts:
                b_extra = self._build_action_button(act, avail_px)
                sec_group.add_widget(b_extra)
            lyt.addWidget(sec_group)
        lyt.addStretch()
        return frame

    def _build_action_button(self, act: dict, avail_px: int) -> QPushButton:
        full_label = act.get("label", "İşlem")
        b_extra = QPushButton(self._elide(full_label, avail_px))
        b_extra.setToolTip(full_label)
        b_extra.setStyleSheet(
            "QPushButton{background:#eef2ff;color:#4338ca;border:none;"
            "border-radius:4px;padding:6px;font-size:11px;font-weight:600;text-align:left;}"
            "QPushButton::menu-indicator{subcontrol-position:right center;right:6px;}",
        )
        menu_items = act.get("menu")
        if menu_items:
            menu = QMenu(b_extra)
            for mi in menu_items:
                menu_action = menu.addAction(mi.get("label", ""))
                fn = mi.get("callback")
                if callable(fn):
                    menu_action.triggered.connect(lambda _c=False, fn=fn: fn())
            b_extra.setMenu(menu)
        else:
            cb = act.get("callback")
            if callable(cb):
                b_extra.clicked.connect(lambda _c=False, fn=cb: fn())
        self._extra_action_buttons.append((b_extra, bool(act.get("enabled_on_edit"))))
        return b_extra

    def _build_right_panel(self) -> QWidget:
        frame = QFrame()
        frame.setFixedWidth(self._right_panel_width)
        frame.setStyleSheet("background:transparent;border:none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(4, 4, 4, 4)
        lyt.setSpacing(6)
        if self._summary_widget is not None:
            lyt.addWidget(self._summary_widget)
            self.lbl_sum = QLabel("")   # geriye dönük referans
        else:
            self.sec_summary = CollapsibleSection("ÖZET", is_expanded=True)
            self.lbl_sum = QLabel("—")
            self.lbl_sum.setWordWrap(True)
            self.lbl_sum.setStyleSheet("font-size:11px;color:#334155;")
            self.sec_summary.add_widget(self.lbl_sum)
            lyt.addWidget(self.sec_summary)
        lyt.addStretch()
        return frame

    # ------------------------------------------------------------------
    def set_data(self, data: dict, *, is_edit: bool | None = None):
        self._is_edit = bool(is_edit) if is_edit is not None else bool(data.get("id"))
        for key, w in self._widgets.items():
            val = data.get(key)
            spec = self._field_specs[key]
            if isinstance(w, QComboBox):
                idx = w.findText(str(val)) if val is not None else -1
                if idx >= 0:
                    w.setCurrentIndex(idx)
                elif w.isEditable():
                    w.setCurrentText("" if val is None else str(val))
            elif isinstance(w, QPlainTextEdit):
                w.setPlainText("" if val is None else str(val))
            elif isinstance(w, QDoubleSpinBox):
                try:
                    w.setValue(float(val) if val not in (None, "") else 0.0)
                except (TypeError, ValueError):
                    w.setValue(0.0)
            elif isinstance(w, QSpinBox):
                try:
                    w.setValue(int(float(val)) if val not in (None, "") else 0)
                except (TypeError, ValueError):
                    w.setValue(0)
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(val))
            elif isinstance(w, (_MoneyField, _IntCatalogField)):
                w.setValue(val)
                ck = spec.get("currency_key")
                if ck and isinstance(w, _MoneyField):
                    w.set_currency_text(data.get(ck))
                vk = spec.get("vat_mode_key")
                if vk and isinstance(w, _MoneyField):
                    w.set_vat_mode_text(data.get(vk))
            elif isinstance(w, (_SearchField, CatalogSearchField)):
                w.setText(val)
            elif isinstance(w, (_ImageField, _SubTableField, _PermTreeField, ParametricFieldGroup)):
                w.set_value(val)
            elif isinstance(w, MoneyEdit):
                w.setValue(val)
            else:  # QLineEdit
                w.setText("" if val is None else str(val))
            if spec.get("lock_on_edit"):
                w.setEnabled(not self._is_edit)
        if (self._status_field and self._status_field not in self._widgets
                and getattr(self, "cmb_header_status", None)):
            self.cmb_header_status.setCurrentText(
                "Aktif" if bool(data.get(self._status_field)) else "Pasif",
            )
        for b, only_edit in getattr(self, "_extra_action_buttons", []):
            if only_edit:
                b.setEnabled(self._is_edit)
        self._refresh_header()
        self._refresh_summary()

    def collect(self) -> dict:
        out: dict = {}
        for key, w in self._widgets.items():
            if isinstance(w, QComboBox):
                out[key] = w.currentText()
            elif isinstance(w, QPlainTextEdit):
                out[key] = w.toPlainText().strip()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                out[key] = w.value()
            elif isinstance(w, QCheckBox):
                out[key] = w.isChecked()
            elif isinstance(w, _MoneyField):
                out[key] = w.value()
                spec = self._field_specs.get(key, {})
                ck = spec.get("currency_key")
                if ck:
                    out[ck] = w.currency_text()
                vk = spec.get("vat_mode_key")
                if vk:
                    out[vk] = w.vat_mode_text()
            elif isinstance(w, _IntCatalogField):
                out[key] = w.value()
            elif isinstance(w, (_SearchField, CatalogSearchField)):
                out[key] = w.text().strip()
            elif isinstance(w, (_ImageField, _SubTableField, _PermTreeField, ParametricFieldGroup)):
                out[key] = w.value()
            elif isinstance(w, MoneyEdit):
                out[key] = w.value()               # ifade yazılıysa hesaplanmış sonuç; metni bozmaz (collect her tuşta çağrılır)
            else:
                out[key] = w.text().strip()
        if (self._status_field and self._status_field not in self._widgets
                and getattr(self, "cmb_header_status", None)):
            out[self._status_field] = self.cmb_header_status.currentText() == "Aktif"
        return out

    def _refresh_summary(self):
        d = self.collect()
        if self._summary_widget is not None and hasattr(self._summary_widget, "update_from"):
            try:
                self._summary_widget.update_from(d)
            except Exception:  # noqa: BLE001
                logger.exception("summary_widget.update_from hatası")
            if not callable(self._summary_provider):
                return
        if callable(self._summary_provider):
            try:
                self.lbl_sum.setText(self._summary_provider(d) or "—")
                return
            except Exception:  # noqa: BLE001
                logger.exception("summary_provider hatası")
        parts = []
        for k in ("code", "short_name", "title", "tax_number", "city"):
            if k in self._widgets and d.get(k):
                parts.append(str(d[k]))
        self.lbl_sum.setText(" · ".join(parts) or "—")

    def _validate(self) -> str | None:
        d = self.collect()
        for key, spec in self._field_specs.items():
            if spec.get("required") and not str(d.get(key, "")).strip():
                return f"'{spec['label']}' zorunludur."
        return None

    def _focus_section(self, n: int) -> None:
        idx = self.tabw.currentIndex()
        if not (0 <= idx < len(self._tab_sections)):
            return
        sections = self._tab_sections[idx]
        if not (1 <= n <= len(sections)):
            return
        w = sections[n - 1]
        w.setFocus()
        if isinstance(w, QLineEdit):
            w.selectAll()

    def _goto_tab(self, n: int) -> None:
        if 1 <= n <= self.tabw.count():
            self.tabw.setCurrentIndex(n - 1)

    def _on_save(self, *, and_new: bool = False):
        err = self._validate()
        if err:
            self.lbl_status.setText(err)
            return
        self.lbl_status.setText("")
        self._refresh_summary()
        data = self.collect()
        if and_new:
            self.saved_and_new.emit(data)
        else:
            self.saved.emit(data)
