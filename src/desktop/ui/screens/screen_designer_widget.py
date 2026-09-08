"""
TOYA ERP - Masaüstü Ekran Tasarımcısı (ScreenDesignerWidget)

Görsel Form & Rapor Tasarımcısı bant tabanlı *baskı* şablonları içindir; bu widget
ise *ekran* şablonlarını tasarlar: `WIDGET_REGISTRY` kataloğundaki atomik parçalar
(cari künyesi, belge vade, hareket kalemleri, finans vb.) bölgelere (üst form,
gövde, alt form, sol/sağ kenar) yerleştirilerek `screen_registry` biçiminde bir
ekran tanımı (`components` + `regions` + `actions`) üretilir ve
`register_screen_definition()` ile kalıcılaştırılır.

Palet öğesine tıklamak onu varsayılan bölgesine ekler; bölgeler arası taşımak için
listeler arasında sürükle-bırak yapılır.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.desktop.core.screen_registry import (
    DEFAULT_SYSTEM_TEMPLATES,
    SCREEN_DEFINITIONS,
    get_screen_definition,
    register_screen_definition,
)
from src.desktop.ui.widgets.widget_registry import WIDGET_REGISTRY

logger = logging.getLogger(__name__)

#: Ekran şablonu bölgeleri — sıra, tuvaldeki dikey diziliştir.
REGIONS: list[tuple[str, str]] = [
    ("top_form", "ÜST FORM"),
    ("body", "GÖVDE"),
    ("bottom_form", "ALT FORM"),
    ("left_sidebar", "SOL KENAR"),
    ("right_sidebar", "SAĞ KENAR"),
]

_ROLE_WIDGET_ID = Qt.ItemDataRole.UserRole


class ScreenDesignerWidget(QWidget):
    """Atomik widget'lardan bölge tabanlı ekran şablonu tasarlar."""

    #: Şablon kaydedildiğinde yayınlanır — argüman: screen_id
    definition_saved = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._region_lists: dict[str, QListWidget] = {}
        self._init_ui()
        self._new_definition()

    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_toolbar())

        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.addWidget(self._build_palette())
        split.addWidget(self._build_canvas())
        split.addWidget(self._build_inspector())
        split.setStretchFactor(1, 1)
        split.setSizes([250, 640, 300])
        root.addWidget(split, 1)

        self.status_label = QLabel("Hazır", self)
        self.status_label.setStyleSheet(
            "background:#F8FAFC;color:#475569;font-size:11px;padding:3px 8px;border-top:1px solid #E2E8F0;",
        )
        root.addWidget(self.status_label)

    def _build_toolbar(self) -> QFrame:
        bar = QFrame(self)
        bar.setStyleSheet("QFrame{background:#0F172A;border-bottom:1px solid #334155;}")
        lyt = QHBoxLayout(bar)
        lyt.setContentsMargins(6, 6, 6, 6)
        lyt.setSpacing(8)

        def _b(text, style):
            b = QPushButton(text, bar)
            b.setStyleSheet(style)
            return b

        _succ = "QPushButton{background:#16A34A;color:#fff;font-weight:bold;padding:5px 12px;border-radius:4px;}QPushButton:hover{background:#15803D;}"
        _neu = "QPushButton{background:#334155;color:#fff;padding:5px 10px;border-radius:4px;}QPushButton:hover{background:#475569;}"

        self.btn_new = _b("🆕 Yeni", _neu)
        self.btn_new.clicked.connect(self._new_definition)
        lyt.addWidget(self.btn_new)

        lyt.addWidget(QLabel("Şablon Aç:", bar, styleSheet="color:#94A3B8;font-size:11px;"))
        self.cmb_open = QComboBox(bar)
        self.cmb_open.setMinimumWidth(220)
        self._reload_open_combo()
        self.cmb_open.activated.connect(self._on_open_selected)
        lyt.addWidget(self.cmb_open)

        lyt.addStretch(1)
        self.btn_save = _b("💾 Kaydet", _succ)
        self.btn_save.clicked.connect(self.save)
        lyt.addWidget(self.btn_save)
        return bar

    def _build_palette(self) -> QWidget:
        wrap = QWidget(self)
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addWidget(QLabel("🧩 WIDGET KATALOĞU", styleSheet="font-weight:bold;font-size:11px;color:#1E293B;"))

        scroll = QScrollArea(wrap)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:1px solid #CBD5E1;background:#fff;}")
        inner = QWidget()
        ilyt = QVBoxLayout(inner)
        ilyt.setContentsMargins(4, 4, 4, 4)
        ilyt.setSpacing(8)

        # Kayıt defterini varsayılan bölgeye göre grupla; bölge dışı olanlar "Diğer".
        by_region: dict[str, list[str]] = {}
        for wid, meta in WIDGET_REGISTRY.items():
            by_region.setdefault(meta.get("default_region", "diger"), []).append(wid)

        region_labels = dict(REGIONS)
        order = [k for k, _ in REGIONS] + sorted(
            r for r in by_region if r not in region_labels
        )
        for region in order:
            wids = by_region.get(region)
            if not wids:
                continue
            grp = QGroupBox(region_labels.get(region, region.upper()), inner)
            grp.setStyleSheet("QGroupBox{font-weight:bold;font-size:10px;color:#475569;}")
            glyt = QVBoxLayout(grp)
            glyt.setContentsMargins(4, 10, 4, 4)
            glyt.setSpacing(3)
            for wid in wids:
                meta = WIDGET_REGISTRY[wid]
                btn = QPushButton(f"➕ {meta['name']}", grp)
                btn.setToolTip(meta.get("description", ""))
                btn.setStyleSheet(
                    "QPushButton{background:#F8FAFC;border:1px solid #CBD5E1;border-radius:4px;"
                    "padding:5px;text-align:left;font-size:10px;color:#0F172A;}"
                    "QPushButton:hover{background:#EEF2FF;border-color:#6366F1;}",
                )
                target = region if region in region_labels else "body"
                btn.clicked.connect(lambda _c=False, w=wid, r=target: self._add_widget(r, w))
                glyt.addWidget(btn)
            ilyt.addWidget(grp)
        ilyt.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        return wrap

    def _build_canvas(self) -> QWidget:
        wrap = QWidget(self)
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.addWidget(QLabel("🖥️ EKRAN BÖLGELERİ  (öğeleri sürükleyerek bölgeler arası taşıyın)",
                               styleSheet="font-weight:bold;font-size:11px;color:#1E293B;"))

        scroll = QScrollArea(wrap)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        ilyt = QVBoxLayout(inner)
        ilyt.setContentsMargins(6, 6, 6, 6)
        ilyt.setSpacing(8)

        for key, label in REGIONS:
            grp = QGroupBox(label, inner)
            grp.setStyleSheet("QGroupBox{font-weight:bold;font-size:10px;color:#1E3A8A;}")
            glyt = QVBoxLayout(grp)
            glyt.setContentsMargins(6, 12, 6, 6)

            lst = QListWidget(grp)
            lst.setMinimumHeight(74)
            lst.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
            lst.setDefaultDropAction(Qt.DropAction.MoveAction)
            lst.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            lst.setStyleSheet("QListWidget{border:1px dashed #CBD5E1;border-radius:4px;font-size:11px;}")
            self._region_lists[key] = lst
            glyt.addWidget(lst)

            ctl = QHBoxLayout()
            b_up = QPushButton("↑", grp); b_up.setFixedWidth(30)
            b_dn = QPushButton("↓", grp); b_dn.setFixedWidth(30)
            b_rm = QPushButton("✕ Kaldır", grp)
            b_up.clicked.connect(lambda _c=False, k=key: self._move_within(k, -1))
            b_dn.clicked.connect(lambda _c=False, k=key: self._move_within(k, +1))
            b_rm.clicked.connect(lambda _c=False, k=key: self._remove_selected(k))
            ctl.addWidget(b_up); ctl.addWidget(b_dn); ctl.addWidget(b_rm); ctl.addStretch(1)
            glyt.addLayout(ctl)
            ilyt.addWidget(grp)

        ilyt.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)
        return wrap

    def _build_inspector(self) -> QWidget:
        wrap = QWidget(self)
        lyt = QVBoxLayout(wrap)
        lyt.setContentsMargins(6, 6, 6, 6)
        lyt.addWidget(QLabel("⚙️ EKRAN ÖZELLİKLERİ", styleSheet="font-weight:bold;font-size:11px;color:#1E293B;"))

        form = QFormLayout()
        form.setSpacing(6)
        self.txt_screen_id = QLineEdit(wrap)
        self.txt_screen_id.setPlaceholderText("örn. scr_evrak_ozel")
        self.txt_title = QLineEdit(wrap)
        self.cmb_base = QComboBox(wrap)
        for tpl_id, tpl in DEFAULT_SYSTEM_TEMPLATES.items():
            self.cmb_base.addItem(tpl.get("title", tpl_id), tpl_id)
        idx = self.cmb_base.findData("tpl_fis_detail")
        if idx >= 0:
            self.cmb_base.setCurrentIndex(idx)
        form.addRow("Ekran ID", self.txt_screen_id)
        form.addRow("Başlık", self.txt_title)
        form.addRow("Taban Şablon", self.cmb_base)
        lyt.addLayout(form)

        grp = QGroupBox("Bölge Görünürlükleri", wrap)
        grp.setStyleSheet("QGroupBox{font-weight:bold;color:#1e3a8a;font-size:10px;}")
        glyt = QVBoxLayout(grp)
        from PyQt6.QtWidgets import QCheckBox
        self.chk_header = QCheckBox("Üst Başlık (header)", grp); self.chk_header.setChecked(True)
        self.chk_left = QCheckBox("Sol Kenar Paneli", grp); self.chk_left.setChecked(True)
        self.chk_right = QCheckBox("Sağ Kenar Paneli", grp); self.chk_right.setChecked(True)
        self.chk_footer = QCheckBox("Alt Bilgi (footer)", grp); self.chk_footer.setChecked(True)
        for c in (self.chk_header, self.chk_left, self.chk_right, self.chk_footer):
            glyt.addWidget(c)
        lyt.addWidget(grp)

        form2 = QFormLayout()
        self.spin_row_h = QSpinBox(wrap); self.spin_row_h.setRange(0, 120); self.spin_row_h.setSpecialValueText("Varsayılan")
        self.spin_head_h = QSpinBox(wrap); self.spin_head_h.setRange(0, 120); self.spin_head_h.setSpecialValueText("Varsayılan")
        form2.addRow("Satır Yüksekliği", self.spin_row_h)
        form2.addRow("Başlık Yüksekliği", self.spin_head_h)
        lyt.addLayout(form2)
        lyt.addStretch(1)
        return wrap

    # ------------------------------------------------------------------
    def _add_widget(self, region: str, widget_id: str) -> None:
        lst = self._region_lists.get(region)
        if lst is None:
            return
        meta = WIDGET_REGISTRY.get(widget_id, {})
        item = QListWidgetItem(f"{meta.get('name', widget_id)}  ·  {widget_id}")
        item.setData(_ROLE_WIDGET_ID, widget_id)
        item.setToolTip(meta.get("description", ""))
        lst.addItem(item)
        self._set_status(f"'{meta.get('name', widget_id)}' → {region}")

    def _move_within(self, region: str, delta: int) -> None:
        lst = self._region_lists[region]
        row = lst.currentRow()
        new = row + delta
        if row < 0 or not (0 <= new < lst.count()):
            return
        it = lst.takeItem(row)
        lst.insertItem(new, it)
        lst.setCurrentRow(new)

    def _remove_selected(self, region: str) -> None:
        lst = self._region_lists[region]
        row = lst.currentRow()
        if row >= 0:
            lst.takeItem(row)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    # ------------------------------------------------------------------
    def _reload_open_combo(self) -> None:
        self.cmb_open.blockSignals(True)
        self.cmb_open.clear()
        self.cmb_open.addItem("— seçin —", None)
        for sid, d in sorted(SCREEN_DEFINITIONS.items()):
            if d.get("is_system_template"):
                continue
            self.cmb_open.addItem(f"{d.get('title', sid)}  [{sid}]", sid)
        self.cmb_open.blockSignals(False)

    def _on_open_selected(self, _idx: int) -> None:
        sid = self.cmb_open.currentData()
        if sid:
            self.load_definition(sid)

    def _new_definition(self) -> None:
        for lst in self._region_lists.values():
            lst.clear()
        self.txt_screen_id.clear()
        self.txt_title.clear()
        for c in (self.chk_header, self.chk_left, self.chk_right, self.chk_footer):
            c.setChecked(True)
        self.spin_row_h.setValue(0)
        self.spin_head_h.setValue(0)
        self._set_status("Yeni ekran şablonu")

    def load_definition(self, screen_id: str) -> None:
        d = get_screen_definition(screen_id)
        self.txt_screen_id.setText(screen_id)
        self.txt_title.setText(d.get("title", ""))
        bi = self.cmb_base.findData(d.get("base_template"))
        if bi >= 0:
            self.cmb_base.setCurrentIndex(bi)
        reg = d.get("regions", {})
        self.chk_header.setChecked(reg.get("header", True))
        self.chk_left.setChecked(reg.get("left_sidebar", True))
        self.chk_right.setChecked(reg.get("right_sidebar", True))
        self.chk_footer.setChecked(reg.get("footer", True))
        self.spin_row_h.setValue(int(d.get("custom_row_height") or 0))
        self.spin_head_h.setValue(int(d.get("custom_header_height") or 0))

        comps = d.get("components", {})
        for key, lst in self._region_lists.items():
            lst.clear()
            val = comps.get(key)
            wids = val if isinstance(val, list) else []
            for wid in wids:
                if wid in WIDGET_REGISTRY:
                    self._add_widget(key, wid)
        self._set_status(f"Yüklendi: {screen_id}")

    # ------------------------------------------------------------------
    def _collect_components(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for key, lst in self._region_lists.items():
            ids = [lst.item(i).data(_ROLE_WIDGET_ID) for i in range(lst.count())]
            if ids:
                out[key] = ids
        return out

    def collect_definition(self) -> dict:
        return {
            "title": self.txt_title.text().strip(),
            "base_template": self.cmb_base.currentData(),
            "is_system_template": False,
            "regions": {
                "header": self.chk_header.isChecked(),
                "left_sidebar": self.chk_left.isChecked(),
                "right_sidebar": self.chk_right.isChecked(),
                "footer": self.chk_footer.isChecked(),
            },
            "custom_row_height": self.spin_row_h.value() or None,
            "custom_header_height": self.spin_head_h.value() or None,
            "components": self._collect_components(),
        }

    def save(self) -> bool:
        screen_id = self.txt_screen_id.text().strip()
        if not screen_id or not self.txt_title.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Ekran ID ve Başlık zorunludur.")
            return False
        if screen_id in SCREEN_DEFINITIONS and SCREEN_DEFINITIONS[screen_id].get("is_system_template"):
            QMessageBox.warning(self, "Sistem Koruması", "Sistem şablonunun üzerine yazılamaz.")
            return False
        definition = self.collect_definition()
        register_screen_definition(screen_id, definition, auto_save=True)
        self._reload_open_combo()
        self.definition_saved.emit(screen_id)
        self._set_status(f"Kaydedildi: {screen_id}")
        QMessageBox.information(self, "Kaydedildi", f"'{screen_id}' ekran şablonu kaydedildi.")
        return True
