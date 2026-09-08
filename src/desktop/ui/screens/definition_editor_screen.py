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
import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QDoubleSpinBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.ui.components.collapsible_section import CollapsibleSection

logger = logging.getLogger(__name__)


class _ImageField(QWidget):
    """Base64 görsel alanı: önizleme + Seç / Temizle."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._b64: str | None = None
        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(6)
        self.preview = QLabel("—")
        self.preview.setFixedSize(120, 64)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("border:1px solid #cbd5e1;border-radius:4px;background:#f8fafc;")
        btn_pick = QPushButton("Seç…")
        btn_pick.clicked.connect(self._pick)
        btn_clear = QPushButton("Temizle")
        btn_clear.clicked.connect(lambda: self.set_value(None))
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
                self.preview.setPixmap(
                    pm.scaled(118, 62, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation),
                )
                self.preview.setText("")
                return
        self.preview.setPixmap(QPixmap())
        self.preview.setText("—")


class _SubTableField(QWidget):
    """list[dict] tutan basit alt tablo (satır ekle/sil)."""

    def __init__(self, columns: list[dict], parent=None):
        super().__init__(parent)
        self._cols = columns  # [{"key","label"}]
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(4)
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels([c["label"] for c in columns])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(26)
        lyt.addWidget(self.table)
        bar = QHBoxLayout()
        b_add = QPushButton("➕ Satır Ekle")
        b_add.clicked.connect(lambda: self._add_row({}))
        b_del = QPushButton("🗑️ Seçili Satırı Sil")
        b_del.clicked.connect(self._del_row)
        bar.addWidget(b_add)
        bar.addWidget(b_del)
        bar.addStretch()
        lyt.addLayout(bar)

    def _add_row(self, rec: dict):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for c, col in enumerate(self._cols):
            self.table.setItem(r, c, QTableWidgetItem(str(rec.get(col["key"], ""))))

    def _del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def value(self) -> list[dict]:
        out = []
        for r in range(self.table.rowCount()):
            rec = {}
            for c, col in enumerate(self._cols):
                it = self.table.item(r, c)
                rec[col["key"]] = it.text().strip() if it else ""
            if any(rec.values()):
                out.append(rec)
        return out

    def set_value(self, rows: list[dict] | None):
        self.table.setRowCount(0)
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
    closed = pyqtSignal()

    def __init__(
        self,
        title: str,
        tabs: list[dict],
        *,
        code: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._title = title
        self._tabs_spec = tabs
        self._is_edit = False
        self._widgets: dict[str, QWidget] = {}
        self._field_specs: dict[str, dict] = {}
        self._build_ui()
        QShortcut(QKeySequence("F2"), self, activated=self._on_save)
        QShortcut(QKeySequence("Esc"), self, activated=self.closed.emit)

    # ------------------------------------------------------------------
    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

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
            self.tabw.addTab(self._build_tab(tab), label)
        root.addWidget(self.tabw, 1)
        root.addWidget(self._build_footer())
        outer.addWidget(content, 1)

        outer.addWidget(self._build_right_panel())

    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("DefHeader")
        bar.setStyleSheet(
            "#DefHeader{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #1e3a8a, stop:1 #0f172a);border-radius:6px;}",
        )
        lyt = QHBoxLayout(bar)
        lyt.setContentsMargins(12, 6, 12, 6)
        self.lbl_title = QLabel(f"📄 {self._title}")
        self.lbl_title.setStyleSheet("color:#fff;font-size:13px;font-weight:800;")
        lyt.addWidget(self.lbl_title)
        lyt.addStretch()
        return bar

    def _build_tab(self, tab: dict) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(14, 12, 14, 12)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for spec in tab["fields"]:
            self._field_specs[spec["key"]] = spec
            widget = self._make_field(spec)
            self._widgets[spec["key"]] = widget
            lbl = spec["label"] + (" *" if spec.get("required") else "")
            if spec["type"] in ("subtable",):
                form.addRow(QLabel(f"<b>{lbl}</b>"))
                form.addRow(widget)
            else:
                form.addRow(lbl + ":", widget)
        scroll.setWidget(w)
        return scroll

    def _make_field(self, spec: dict) -> QWidget:
        t = spec["type"]
        if t == "combo":
            cb = QComboBox()
            cb.setEditable(bool(spec.get("editable")))
            cb.addItems([str(o) for o in spec.get("options", [])])
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
            return sp
        if t == "bool":
            return QCheckBox(spec.get("text", ""))
        if t == "image":
            return _ImageField()
        if t == "subtable":
            return _SubTableField(spec.get("columns", []))
        if t == "permtree":
            return _PermTreeField(spec.get("groups", []))
        # text / password / number / date -> QLineEdit
        le = QLineEdit()
        if t == "password":
            le.setEchoMode(QLineEdit.EchoMode.Password)
        if spec.get("placeholder"):
            le.setPlaceholderText(spec["placeholder"])
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
        b_cancel = QPushButton("❌ Vazgeç (Esc)")
        b_cancel.setStyleSheet(
            "QPushButton{background:#f1f5f9;color:#475569;border:1px solid #cbd5e1;"
            "font-size:11px;padding:0 16px;height:30px;border-radius:6px;}",
        )
        b_cancel.clicked.connect(self.closed.emit)
        b_save = QPushButton("💾 Kaydet (F2)")
        b_save.setStyleSheet(
            "QPushButton{background:#2563eb;color:#fff;border:1px solid #2563eb;"
            "font-weight:700;font-size:11px;padding:0 18px;height:30px;border-radius:6px;}"
            "QPushButton:hover{background:#1d4ed8;}",
        )
        b_save.clicked.connect(self._on_save)
        lyt.addWidget(b_cancel)
        lyt.addWidget(b_save)
        return bar

    def _build_left_panel(self) -> QWidget:
        frame = QFrame()
        frame.setFixedWidth(190)
        frame.setStyleSheet("background:transparent;border:none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(4, 4, 4, 4)
        lyt.setSpacing(6)
        sec = CollapsibleSection("BÖLÜMLER", is_expanded=True)
        self._nav_buttons = []
        for i, tab in enumerate(self._tabs_spec):
            b = QPushButton(f"  {i + 1}. {tab['title']}".replace("&", "&&"))
            b.setStyleSheet(
                "QPushButton{background:#fff;color:#1e293b;border:1px solid #cbd5e1;"
                "border-radius:4px;padding:5px 8px;font-size:11px;text-align:left;}"
                "QPushButton:hover{background:#eff6ff;}",
            )
            b.clicked.connect(lambda _c=False, idx=i: self.tabw.setCurrentIndex(idx))
            sec.add_widget(b)
            self._nav_buttons.append(b)
        lyt.addWidget(sec)

        sec2 = CollapsibleSection("İŞLEMLER", is_expanded=True)
        b_save = QPushButton("💾 Kaydet")
        b_save.setStyleSheet("QPushButton{background:#2563eb;color:#fff;border:none;"
                             "border-radius:4px;padding:6px;font-size:11px;font-weight:700;}")
        b_save.clicked.connect(self._on_save)
        b_cancel = QPushButton("🚪 Vazgeç")
        b_cancel.setStyleSheet("QPushButton{background:#fee2e2;color:#991b1b;border:none;"
                               "border-radius:4px;padding:6px;font-size:11px;}")
        b_cancel.clicked.connect(self.closed.emit)
        sec2.add_widget(b_save)
        sec2.add_widget(b_cancel)
        lyt.addWidget(sec2)
        lyt.addStretch()
        return frame

    def _build_right_panel(self) -> QWidget:
        frame = QFrame()
        frame.setFixedWidth(220)
        frame.setStyleSheet("background:transparent;border:none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(4, 4, 4, 4)
        lyt.setSpacing(6)
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
            elif isinstance(w, (_ImageField, _SubTableField, _PermTreeField)):
                w.set_value(val)
            else:  # QLineEdit
                w.setText("" if val is None else str(val))
            if spec.get("lock_on_edit"):
                w.setEnabled(not self._is_edit)
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
            elif isinstance(w, (_ImageField, _SubTableField, _PermTreeField)):
                out[key] = w.value()
            else:
                out[key] = w.text().strip()
        return out

    def _refresh_summary(self):
        d = self.collect()
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

    def _on_save(self):
        err = self._validate()
        if err:
            self.lbl_status.setText(err)
            return
        self.lbl_status.setText("")
        self._refresh_summary()
        self.saved.emit(self.collect())
