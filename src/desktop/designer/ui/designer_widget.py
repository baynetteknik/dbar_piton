"""
TOYA ERP - Görsel Form & Rapor Tasarımcısı Gömülebilir Widget'ı (ReportDesignerWidget)

`ReportDesignerWindow` (QMainWindow) uzun süredir yalnızca bağımsız bir pencere
olarak açılabiliyordu. Bu widget, aynı 3 panelli tasarımcıyı (sol araçlar/veri
ağacı, orta milimetrik tuval, sağ özellik denetçisi) bir ``QWidget`` olarak
paketler; böylece hem eski pencere hem de ERP'nin bir sekmesi / paneli aynı
bileşeni kullanır (bkz. WIDGET_REGISTRY → ``widget_report_designer``).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.desktop.designer.models import ItemConfig, ReportTemplate
from src.desktop.designer.preview_dialog import ReportPreviewDialog
from src.desktop.designer.services.teklif_print_service import TeklifPrintService
from src.desktop.designer.ui.data_tree_widget import DataTreeWidget
from src.desktop.designer.ui.designer_canvas import DesignerCanvas
from src.desktop.designer.ui.property_inspector import PropertyInspector
from src.desktop.designer.ui.toolbox_widget import ToolboxWidget

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "templates" / "tpl_teklif_kurumsal_a4.json"
)

_BTN_PRIMARY = "QPushButton { background-color: #2563EB; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px; } QPushButton:hover { background-color: #1D4ED8; }"
_BTN_SUCCESS = "QPushButton { background-color: #16A34A; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px; } QPushButton:hover { background-color: #15803D; }"
_BTN_DANGER = "QPushButton { background-color: #DC2626; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px; } QPushButton:hover { background-color: #B91C1C; }"
_BTN_NEUTRAL = "QPushButton { background-color: #334155; color: white; padding: 5px 10px; border-radius: 4px; } QPushButton:hover { background-color: #475569; }"


class ReportDesignerWidget(QWidget):
    """Bant tabanlı görsel form & rapor tasarımcısı (gömülebilir)."""

    #: Şablon başarıyla kaydedildiğinde yayınlanır — argüman: kaydedilen JSON yolu
    template_saved = pyqtSignal(str)
    #: Aktif şablon değişince (aç/kaydet) pencere başlığı için yayınlanır
    title_changed = pyqtSignal(str)

    def __init__(
        self,
        template_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.template_path = Path(template_path) if template_path else DEFAULT_TEMPLATE_PATH
        self.template = self._load_template(self.template_path)
        self._init_ui()
        self._emit_title()

    # ------------------------------------------------------------------
    def window_title(self) -> str:
        return f"TOYA ERP - Görsel Form & Rapor Tasarımcısı — [{self.template.title}]"

    def _emit_title(self) -> None:
        self.title_changed.emit(self.window_title())

    def _load_template(self, path: Path) -> ReportTemplate:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            return ReportTemplate.from_dict(d)
        raise FileNotFoundError(f"Şablon dosyası bulunamadı: {path}")

    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar())

        # ─── Üç Panelli Gövde (Splitter) ───
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setStyleSheet("QSplitter::handle { background-color: #CBD5E1; width: 3px; }")

        left_tabs = QTabWidget(self)
        left_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #CBD5E1; background: #FFFFFF; }"
            "QTabBar::tab { background: #F1F5F9; color: #334155; padding: 6px 12px; font-weight: bold; font-size: 11px; }"
            "QTabBar::tab:selected { background: #FFFFFF; color: #0F172A; border-bottom: 2px solid #2563EB; }"
        )
        self.toolbox = ToolboxWidget(left_tabs)
        self.toolbox.item_requested.connect(self._on_toolbox_item_requested)
        left_tabs.addTab(self.toolbox, "🧰 Araçlar")

        self.data_tree = DataTreeWidget(left_tabs)
        self.data_tree.field_requested.connect(self._on_field_requested)
        left_tabs.addTab(self.data_tree, "🌲 Veri Ağacı")

        left_tabs.setMinimumWidth(240)
        left_tabs.setMaximumWidth(320)
        splitter.addWidget(left_tabs)

        self.canvas = DesignerCanvas(self.template, parent=self)
        self.canvas.item_selected.connect(self._on_canvas_item_selected)
        self.canvas.item_changed.connect(self._on_canvas_item_changed)
        splitter.addWidget(self.canvas)

        self.inspector = PropertyInspector(self)
        self.inspector.property_changed.connect(self._on_property_changed)
        self.inspector.setMinimumWidth(260)
        self.inspector.setMaximumWidth(340)
        splitter.addWidget(self.inspector)

        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 800, 300])
        root.addWidget(splitter, 1)

        # ─── Durum Şeridi ───
        self.status_label = QLabel(
            f"Hazır — Şablon: {self.template.title} ({self.template.template_id})", self,
        )
        self.status_label.setStyleSheet(
            "background-color: #F8FAFC; color: #475569; font-size: 11px; padding: 3px 8px;"
            " border-top: 1px solid #E2E8F0;",
        )
        root.addWidget(self.status_label)

    def _build_toolbar(self) -> QFrame:
        bar = QFrame(self)
        bar.setStyleSheet(
            "QFrame { background-color: #0F172A; border-bottom: 1px solid #334155; }",
        )
        lyt = QHBoxLayout(bar)
        lyt.setContentsMargins(6, 6, 6, 6)
        lyt.setSpacing(8)

        self.btn_save = QPushButton("💾 Kaydet", bar)
        self.btn_save.setStyleSheet(_BTN_SUCCESS)
        self.btn_save.setShortcut(QKeySequence("Ctrl+S"))
        self.btn_save.clicked.connect(self._save_template)
        lyt.addWidget(self.btn_save)

        self.btn_open = QPushButton("📂 Şablon Aç...", bar)
        self.btn_open.setStyleSheet(_BTN_NEUTRAL)
        self.btn_open.clicked.connect(self._open_template)
        lyt.addWidget(self.btn_open)

        self.btn_preview = QPushButton("👁️ Canlı Önizle (F9)", bar)
        self.btn_preview.setStyleSheet(_BTN_PRIMARY)
        self.btn_preview.setShortcut(QKeySequence("F9"))
        self.btn_preview.clicked.connect(self._on_live_preview)
        lyt.addWidget(self.btn_preview)

        sep = QLabel("  Izgara: ", bar)
        sep.setStyleSheet("color: #94A3B8; font-size: 11px;")
        lyt.addWidget(sep)

        self.cmb_grid = QComboBox(bar)
        self.cmb_grid.addItems(
            ["1.0 mm (Hassas)", "2.5 mm (Standart)", "5.0 mm (Geniş)", "Kapalı"],
        )
        self.cmb_grid.setCurrentText("1.0 mm (Hassas)")
        self.cmb_grid.currentTextChanged.connect(self._on_grid_changed)
        lyt.addWidget(self.cmb_grid)

        lyt.addStretch(1)

        self.btn_delete = QPushButton("🗑️ Sil (Del)", bar)
        self.btn_delete.setStyleSheet(_BTN_DANGER)
        self.btn_delete.setShortcut(QKeySequence("Delete"))
        self.btn_delete.clicked.connect(self._delete_selected_item)
        lyt.addWidget(self.btn_delete)
        return bar

    # ------------------------------------------------------------------
    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _on_toolbox_item_requested(self, item_cfg: ItemConfig) -> None:
        widget = self.canvas.add_new_item_to_band(item_cfg)
        if widget:
            self.inspector.set_item_widget(widget)
            self._set_status(f"Yeni öğe eklendi: [{item_cfg.id}]")

    def _on_field_requested(self, item_cfg: ItemConfig, target_band_type: str) -> None:
        widget = self.canvas.add_new_item_to_band(item_cfg, band_type=target_band_type)
        if widget:
            self.inspector.set_item_widget(widget)
            self._set_status(f"Veri alanı eklendi: {{{item_cfg.field}}}")

    def _on_canvas_item_selected(self, item_widget) -> None:
        self.inspector.set_item_widget(item_widget)
        if item_widget:
            cfg = item_widget.item
            self._set_status(
                f"Seçili: [{cfg.id}] | X: {cfg.x_mm:.1f} mm, Y: {cfg.y_mm:.1f} mm, "
                f"W: {cfg.w_mm:.1f} mm, H: {cfg.h_mm:.1f} mm",
            )
        else:
            self._set_status("Seçim kaldırıldı.")

    def _on_canvas_item_changed(self, item_widget) -> None:
        if item_widget == self.inspector.active_widget:
            self.inspector.set_item_widget(item_widget)

    def _on_property_changed(self, item_widget) -> None:
        self._set_status(f"Özellikler güncellendi: [{item_widget.item.id}]")

    def _on_grid_changed(self, text: str) -> None:
        if "1.0 mm" in text:
            self.canvas.set_snap_grid(1.0)
        elif "2.5 mm" in text:
            self.canvas.set_snap_grid(2.5)
        elif "5.0 mm" in text:
            self.canvas.set_snap_grid(5.0)
        else:
            self.canvas.set_snap_grid(0.0)

    def _delete_selected_item(self) -> None:
        self.canvas.delete_selected_item()
        self.inspector.clear_selection()
        self._set_status("Öğe silindi.")

    # ------------------------------------------------------------------
    def _save_template(self) -> None:
        """Mevcut şablon modelini JSON formatında kaydeder."""
        try:
            out_dict = _template_to_dict(self.template)
            with open(self.template_path, "w", encoding="utf-8") as f:
                json.dump(out_dict, f, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self, "Başarılı",
                f"Şablon başarıyla kaydedildi:\n{self.template_path}",
            )
            self._set_status(f"Kaydedildi: {self.template_path.name}")
            self.template_saved.emit(str(self.template_path))
        except Exception as e:  # noqa: BLE001
            logger.error("Şablon kaydetme hatası: %s", e, exc_info=True)
            QMessageBox.critical(self, "Hata", f"Kaydetme sırasında hata oluştu:\n{e}")

    def _open_template(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Rapor Şablonu Aç", str(self.template_path.parent),
            "Şablon Dosyaları (*.json)",
        )
        if not file_path:
            return
        try:
            p = Path(file_path)
            self.template = self._load_template(p)
            self.template_path = p
            self.canvas.template = self.template
            self.canvas._populate_bands()
            self.inspector.clear_selection()
            self._emit_title()
            self._set_status(f"Şablon yüklendi: {p.name}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Hata", f"Şablon açılırken hata oluştu:\n{e}")

    def _on_live_preview(self) -> None:
        """Son değişiklikleri anında Baskı Önizleme penceresinde açar."""
        service = TeklifPrintService(template_path=self.template_path)
        data = service.build_teklif_data()
        dialog = ReportPreviewDialog(template=self.template, data=data, parent=self)
        dialog.exec()


def _template_to_dict(template: ReportTemplate) -> dict:
    """ReportTemplate -> kaydedilebilir dict (yalnızca varsayılandan sapan alanlar)."""
    page = template.page
    orientation = page.orientation.value if hasattr(page.orientation, "value") else str(page.orientation)
    out: dict = {
        "schema_version": template.schema_version,
        "template_id": template.template_id,
        "title": template.title,
        "template_type": template.template_type,
        "page": {
            "size": page.size,
            "orientation": orientation,
            "width_mm": page.width_mm,
            "height_mm": page.height_mm,
            "margin_top_mm": page.margin_top_mm,
            "margin_bottom_mm": page.margin_bottom_mm,
            "margin_left_mm": page.margin_left_mm,
            "margin_right_mm": page.margin_right_mm,
        },
        "bands": [],
    }
    for b in template.bands:
        band_dict: dict = {"id": b.id, "type": b.type, "height_mm": b.height_mm, "items": []}
        if b.dataset:
            band_dict["dataset"] = b.dataset
        if b.can_grow:
            band_dict["can_grow"] = b.can_grow
        if b.keep_together:
            band_dict["keep_together"] = b.keep_together
        for itm in b.items:
            itm_dict: dict = {
                "id": itm.id, "type": itm.type,
                "x_mm": itm.x_mm, "y_mm": itm.y_mm, "w_mm": itm.w_mm, "h_mm": itm.h_mm,
            }
            for attr, default in (
                ("text", None), ("field", None), ("expression", None), ("format", None),
                ("font_bold", False), ("font_italic", False),
                ("border_top", False), ("border_bottom", False),
                ("border_left", False), ("border_right", False),
                ("bg_color", None), ("word_wrap", False),
            ):
                val = getattr(itm, attr)
                if val != default:
                    itm_dict[attr] = val
            if itm.font_size != 9:
                itm_dict["font_size"] = itm.font_size
            if itm.align != "left":
                itm_dict["align"] = itm.align
            if itm.border_color != "#CCCCCC":
                itm_dict["border_color"] = itm.border_color
            if itm.border_width != 0.5:
                itm_dict["border_width"] = itm.border_width
            if itm.corner_radius > 0:
                itm_dict["corner_radius"] = itm.corner_radius
            if itm.text_color != "#000000":
                itm_dict["text_color"] = itm.text_color
            band_dict["items"].append(itm_dict)
        out["bands"].append(band_dict)
    return out
