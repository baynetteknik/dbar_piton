"""
TOYA ERP - ParametricFieldGroup

N adet parametrik alan barındıran, kullanıcı tarafından yeniden
etiketlenebilir alan grubu ("Özel Kodlar", "Ek Fiyat Tanımları" vb. için).
Cari, Stok, Görev gibi farklı modüllerde `scope` parametresiyle tekrar
kullanılabilir; etiket geçersiz kılmaları `SystemSetting` tablosunda
(`param_labels:<scope>` anahtarı altında) JSON olarak saklanır, değerler ise
kartın kendi JSON alanında (`value()` → JSON metin) tutulur.

Kullanım (DefinitionEditorScreen alan şeması içinde):
    {"key": "extra_codes", "type": "param_group", "scope": "urun.ozel_kod",
     "count": 10, "default_name": "Özel Kod", "db_session": db}
"""

from __future__ import annotations

import json
import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services import settings_store
from src.desktop.ui.widgets.catalog_picker import make_search_button
from src.desktop.ui.widgets.masked_decimal_field import MaskedDecimalField

logger = logging.getLogger(__name__)

_VAT_MODE_OPTIONS = ["KDV D", "KDV H"]
_COMBO_QSS = (
    "QComboBox{padding:2px 6px;combobox-popup:0;}"
    "QComboBox QAbstractItemView{outline:0;border:1px solid #cbd5e1;}"
    "QComboBox QAbstractItemView::item{padding:4px 8px;min-height:22px;}"
)


class ParametricFieldGroup(QWidget):
    """N alanlık, etiketleri kullanıcı tarafından özelleştirilebilir grup."""

    def __init__(
        self,
        *,
        scope: str,
        count: int = 10,
        start_index: int = 1,
        kind: str = "text",  # text | money | percent
        default_labels: dict[int, str] | None = None,
        default_name: str = "Özel Kod",
        db_session=None,
        columns: int = 2,
        searchable_slots: set[int] | None = None,
        on_search=None,
        visible_default: int | None = None,
        button_text: str = "✏ Alan Adlarını Düzenle",
        show_button: bool = True,
        vat_mode: bool = False,
        currencies: list[str] | None = None,
        decimals: int = 2,
        parent=None,
    ):
        super().__init__(parent)
        self._scope = scope
        self._count = count
        self._start = start_index
        self._kind = kind
        self._default_name = default_name
        self._db = db_session
        self._cols = max(1, columns)
        self._vat_mode = vat_mode and kind == "money"
        self._currencies = currencies if kind == "money" else None
        self._decimals = decimals
        self._searchable = searchable_slots or set()
        self._on_search = on_search
        self._visible_default = visible_default or count
        self._expanded = self._visible_default >= count

        self._labels: dict[int, str] = dict(default_labels or {})
        self._load_labels()

        self._rows: dict[int, QWidget] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        if show_button:
            bar = QHBoxLayout()
            bar.addStretch()
            btn_edit = QPushButton(button_text)
            btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_edit.setStyleSheet(
                "QPushButton{background:transparent;color:#2563eb;border:none;"
                "font-size:10px;font-weight:700;}"
                "QPushButton:hover{text-decoration:underline;}",
            )
            btn_edit.clicked.connect(self._edit_labels)
            bar.addWidget(btn_edit)
            root.addLayout(bar)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(6)
        self._grid.setVerticalSpacing(6)
        root.addWidget(self._grid_host)

        self._btn_toggle = None
        if self._visible_default < self._count:
            self._btn_toggle = QPushButton()
            self._btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_toggle.setStyleSheet(
                "QPushButton{background:transparent;color:#2563eb;border:none;"
                "font-size:10px;font-weight:700;text-align:left;}"
                "QPushButton:hover{text-decoration:underline;}",
            )
            self._btn_toggle.clicked.connect(self._toggle_expand)
            root.addWidget(self._btn_toggle)

        self._build_rows()
        self._update_toggle_text()

    # ------------------------------------------------------------------
    def _label_key(self) -> str:
        return f"param_labels:{self._scope}"

    def _load_labels(self) -> None:
        stored = settings_store.get_json(self._db, self._label_key(), {}) if self._db else {}
        stored = stored or {}
        for i in range(self._start, self._start + self._count):
            if str(i) in stored:
                self._labels[i] = stored[str(i)]
            elif i not in self._labels:
                self._labels[i] = f"{self._default_name} {i}"

    def _save_labels(self) -> None:
        if not self._db:
            return
        data = {
            str(i): self._labels.get(i, f"{self._default_name} {i}")
            for i in range(self._start, self._start + self._count)
        }
        settings_store.set_setting(self._db, self._label_key(), json.dumps(data, ensure_ascii=False))

    def _slot_visible(self, i: int) -> bool:
        return self._expanded or (i - self._start) < self._visible_default

    # ------------------------------------------------------------------
    def _build_rows(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._rows.clear()
        r = c = 0
        for i in range(self._start, self._start + self._count):
            if not self._slot_visible(i):
                continue
            lbl = QLabel(self._labels.get(i, f"{self._default_name} {i}") + ":")
            lbl.setStyleSheet("font-size:11px;color:#334155;font-weight:600;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            field = self._make_row_widget(i)
            self._rows[i] = field
            self._grid.addWidget(lbl, r, c * 2)
            self._grid.addWidget(field, r, c * 2 + 1)
            c += 1
            if c >= self._cols:
                c = 0
                r += 1
        for col in range(self._cols):
            self._grid.setColumnStretch(col * 2 + 1, 1)

    def _make_row_widget(self, i: int) -> QWidget:
        if self._kind == "money":
            if self._vat_mode or self._currencies:
                row = QWidget()
                lyt = QHBoxLayout(row)
                lyt.setContentsMargins(0, 0, 0, 0)
                lyt.setSpacing(3)
                spin = MaskedDecimalField(decimals=self._decimals)
                spin.setMinimumWidth(80)
                spin.setMaximumWidth(150)
                lyt.addWidget(spin, 1)
                row.spin = spin  # noqa: SLF001 (basit bileşik widget)
                row.currency = None  # noqa: SLF001
                if self._currencies:
                    currency = QComboBox()
                    currency.addItems([str(c) for c in self._currencies])
                    currency.setFixedWidth(64)
                    currency.setStyleSheet(_COMBO_QSS)
                    lyt.addWidget(currency)
                    row.currency = currency  # noqa: SLF001
                row.vat_combo = None  # noqa: SLF001
                if self._vat_mode:
                    vat_combo = QComboBox()
                    vat_combo.addItems(_VAT_MODE_OPTIONS)
                    vat_combo.setCurrentIndex(1)  # varsayılan: KDV Hariç (H)
                    vat_combo.setFixedWidth(88)
                    vat_combo.setStyleSheet(_COMBO_QSS)
                    lyt.addWidget(vat_combo)
                    row.vat_combo = vat_combo  # noqa: SLF001
                return row
            return MaskedDecimalField(decimals=self._decimals)
        if self._kind == "percent":
            w = QDoubleSpinBox()
            w.setRange(0.0, 100.0)
            w.setDecimals(0)
            w.setSuffix(" %")
            return w
        if i in self._searchable:
            row = QWidget()
            lyt = QHBoxLayout(row)
            lyt.setContentsMargins(0, 0, 0, 0)
            lyt.setSpacing(3)
            edit = QLineEdit()
            btn = make_search_button()
            if callable(self._on_search):
                def _do_search(_c=False, idx=i, e=edit):
                    chosen = self._on_search(idx, e.text().strip())
                    if chosen is not None:
                        e.setText(chosen)
                btn.clicked.connect(_do_search)
            lyt.addWidget(edit, 1)
            lyt.addWidget(btn)
            row.edit = edit  # noqa: SLF001 (basit bileşik widget)
            return row
        return QLineEdit()

    def _row_value(self, i: int):
        w = self._rows.get(i)
        if w is None:
            return None
        if hasattr(w, "spin"):
            amt = w.spin.value()
            if amt in (0, 0.0):
                return None
            data = {"v": amt}
            if w.currency is not None:
                data["cur"] = w.currency.currentText()
            if w.vat_combo is not None:
                data["vat"] = w.vat_combo.currentText()
            return data
        if isinstance(w, (MaskedDecimalField, QDoubleSpinBox)):
            return w.value()
        if hasattr(w, "edit"):
            return w.edit.text().strip()
        if isinstance(w, QLineEdit):
            return w.text().strip()
        return None

    def _set_row_value(self, i: int, val) -> None:
        w = self._rows.get(i)
        if w is None:
            return
        if hasattr(w, "spin"):
            if isinstance(val, dict):
                amt, cur, vat = val.get("v"), val.get("cur"), val.get("vat")
            else:
                amt, cur, vat = val, None, None
            w.spin.setValue(amt or 0)
            if w.currency is not None and cur:
                idx = w.currency.findText(cur)
                if idx >= 0:
                    w.currency.setCurrentIndex(idx)
            if w.vat_combo is not None:
                idx = w.vat_combo.findText(vat) if vat else -1
                w.vat_combo.setCurrentIndex(idx if idx >= 0 else 1)
        elif isinstance(w, MaskedDecimalField):
            w.setValue(val)
        elif isinstance(w, QDoubleSpinBox):
            try:
                w.setValue(float(val or 0))
            except (TypeError, ValueError):
                w.setValue(0.0)
        elif hasattr(w, "edit"):
            w.edit.setText("" if val is None else str(val))
        elif isinstance(w, QLineEdit):
            w.setText("" if val is None else str(val))

    def first_focusable(self) -> QWidget | None:
        """İlk satırın asıl yazılabilir alt widget'ını döndürür — Ctrl+<N>
        kısayoluyla bu bölüme atlarken sarmalayıcı widget değil, doğrudan
        yazılabilir alana odaklanılsın diye."""
        w = self._rows.get(self._start)
        if w is None:
            return None
        if hasattr(w, "edit"):
            return w.edit
        if hasattr(w, "spin"):
            return w.spin
        return w

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        current = self.value()
        self._build_rows()
        self.set_value(current)
        self._update_toggle_text()

    def _update_toggle_text(self) -> None:
        if not self._btn_toggle:
            return
        hidden = self._count - self._visible_default
        if self._expanded:
            self._btn_toggle.setText("▲ Daha Az Göster")
        else:
            self._btn_toggle.setText(f"▼ Daha Fazla Göster (+{hidden})")

    def _edit_labels(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Alan Adlarını Düzenle")
        lyt = QVBoxLayout(dlg)
        edits: dict[int, QLineEdit] = {}
        for i in range(self._start, self._start + self._count):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{self._default_name} {i}:"))
            e = QLineEdit(self._labels.get(i, f"{self._default_name} {i}"))
            edits[i] = e
            row.addWidget(e, 1)
            lyt.addLayout(row)
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        lyt.addWidget(box)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            current = self.value()
            for i, e in edits.items():
                self._labels[i] = e.text().strip() or f"{self._default_name} {i}"
            self._save_labels()
            self._build_rows()
            self.set_value(current)

    # ------------------------------------------------------------------
    def value(self) -> str:
        data = {}
        for i in range(self._start, self._start + self._count):
            v = self._row_value(i)
            if v not in (None, "", 0, 0.0):
                data[str(i)] = v
        return json.dumps(data, ensure_ascii=False) if data else ""

    def set_value(self, raw) -> None:
        if isinstance(raw, str):
            try:
                data = json.loads(raw) if raw else {}
            except (TypeError, ValueError):
                data = {}
        elif isinstance(raw, dict):
            data = raw
        else:
            data = {}
        for i in range(self._start, self._start + self._count):
            self._set_row_value(i, data.get(str(i)))
