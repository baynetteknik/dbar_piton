"""
TOYA ERP - Görsel Form & Rapor Tasarımcısı Ana Penceresi (ReportDesignerWindow)
3 Panelli mimari: Sol araçlar/veri ağacı, orta milimetrik tuval, sağ özellikler denetçisi.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from src.desktop.designer.models import BandConfig, ItemConfig, ReportTemplate
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


class ReportDesignerWindow(QMainWindow):
    """Görsel Form & Rapor Tasarımcısı Ana Penceresi."""

    def __init__(
        self,
        template_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.template_path = Path(template_path) if template_path else DEFAULT_TEMPLATE_PATH
        self.template = self._load_template(self.template_path)

        self.setWindowTitle(f"TOYA ERP - Görsel Form & Rapor Tasarımcısı — [{self.template.title}]")
        self.resize(1380, 900)
        self.setMinimumSize(950, 650)

        self._init_ui()

    def _load_template(self, path: Path) -> ReportTemplate:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            return ReportTemplate.from_dict(d)
        raise FileNotFoundError(f"Şablon dosyası bulunamadı: {path}")

    def _init_ui(self):
        # ─── 1. Üst Toolbar ───
        toolbar = QToolBar("Tasarımcı Araçları", self)
        toolbar.setMovable(False)
        toolbar.setStyleSheet("QToolBar { background-color: #0F172A; padding: 6px; spacing: 8px; border-bottom: 1px solid #334155; }")
        self.addToolBar(toolbar)

        btn_style_primary = "QPushButton { background-color: #2563EB; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px; } QPushButton:hover { background-color: #1D4ED8; }"
        btn_style_success = "QPushButton { background-color: #16A34A; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px; } QPushButton:hover { background-color: #15803D; }"
        btn_style_danger = "QPushButton { background-color: #DC2626; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px; } QPushButton:hover { background-color: #B91C1C; }"
        btn_style_neutral = "QPushButton { background-color: #334155; color: white; padding: 5px 10px; border-radius: 4px; } QPushButton:hover { background-color: #475569; }"

        # Kaydet Butonu
        self.btn_save = QPushButton("💾 Kaydet", self)
        self.btn_save.setStyleSheet(btn_style_success)
        self.btn_save.setShortcut(QKeySequence("Ctrl+S"))
        self.btn_save.clicked.connect(self._save_template)
        toolbar.addWidget(self.btn_save)

        # Şablon Aç Butonu
        self.btn_open = QPushButton("📂 Şablon Aç...", self)
        self.btn_open.setStyleSheet(btn_style_neutral)
        self.btn_open.clicked.connect(self._open_template)
        toolbar.addWidget(self.btn_open)

        # Canlı Önizleme Butonu
        self.btn_preview = QPushButton("👁️ Canlı Önizle (F9)", self)
        self.btn_preview.setStyleSheet(btn_style_primary)
        self.btn_preview.setShortcut(QKeySequence("F9"))
        self.btn_preview.clicked.connect(self._on_live_preview)
        toolbar.addWidget(self.btn_preview)

        toolbar.addSeparator()

        # Mıknatıslı Izgara Seçici
        lbl_grid = QLabel("  Izgara: ", self)
        lbl_grid.setStyleSheet("color: #94A3B8; font-size: 11px;")
        toolbar.addWidget(lbl_grid)

        self.cmb_grid = QComboBox(self)
        self.cmb_grid.addItems(["1.0 mm (Hassas)", "2.5 mm (Standart)", "5.0 mm (Geniş)", "Kapalı"])
        self.cmb_grid.setCurrentText("1.0 mm (Hassas)")
        self.cmb_grid.currentTextChanged.connect(self._on_grid_changed)
        toolbar.addWidget(self.cmb_grid)

        toolbar.addSeparator()

        # Sil Butonu
        self.btn_delete = QPushButton("🗑️ Sil (Del)", self)
        self.btn_delete.setStyleSheet(btn_style_danger)
        self.btn_delete.setShortcut(QKeySequence("Delete"))
        self.btn_delete.clicked.connect(self._delete_selected_item)
        toolbar.addWidget(self.btn_delete)

        # ─── 2. Üç Panelli Gövde (Splitter) ───
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setStyleSheet("QSplitter::handle { background-color: #CBD5E1; width: 3px; }")

        # ─── Sol Panel: Araç Kutusu ve Veri Ağacı (Tabs) ───
        left_tabs = QTabWidget(self)
        left_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #CBD5E1; background: #FFFFFF; }
            QTabBar::tab { background: #F1F5F9; color: #334155; padding: 6px 12px; font-weight: bold; font-size: 11px; }
            QTabBar::tab:selected { background: #FFFFFF; color: #0F172A; border-bottom: 2px solid #2563EB; }
        """)

        self.toolbox = ToolboxWidget(left_tabs)
        self.toolbox.item_requested.connect(self._on_toolbox_item_requested)
        left_tabs.addTab(self.toolbox, "🧰 Araçlar")

        self.data_tree = DataTreeWidget(left_tabs)
        self.data_tree.field_requested.connect(self._on_field_requested)
        left_tabs.addTab(self.data_tree, "🌲 Veri Ağacı")

        left_tabs.setMinimumWidth(240)
        left_tabs.setMaximumWidth(320)
        splitter.addWidget(left_tabs)

        # ─── Orta Panel: Milimetrik Çizim Tuvali ───
        self.canvas = DesignerCanvas(self.template, self)
        self.canvas.item_selected.connect(self._on_canvas_item_selected)
        self.canvas.item_changed.connect(self._on_canvas_item_changed)
        splitter.addWidget(self.canvas)

        # ─── Sağ Panel: Özellikler Denetçisi ───
        self.inspector = PropertyInspector(self)
        self.inspector.property_changed.connect(self._on_property_changed)
        self.inspector.setMinimumWidth(260)
        self.inspector.setMaximumWidth(340)
        splitter.addWidget(self.inspector)

        # Panel oranları: Sol: 260px, Orta: 780px, Sağ: 300px
        splitter.setSizes([260, 800, 300])

        self.setCentralWidget(splitter)

        # ─── 3. Durum Çubuğu ───
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("background-color: #F8FAFC; color: #475569; font-size: 11px;")
        self.status_bar.showMessage(f"Hazır — Şablon: {self.template.title} ({self.template.template_id})")

    def _on_toolbox_item_requested(self, item_cfg: ItemConfig):
        widget = self.canvas.add_new_item_to_band(item_cfg)
        if widget:
            self.inspector.set_item_widget(widget)
            self.status_bar.showMessage(f"Yeni öğe eklendi: [{item_cfg.id}]")

    def _on_field_requested(self, item_cfg: ItemConfig, target_band_type: str):
        widget = self.canvas.add_new_item_to_band(item_cfg, band_type=target_band_type)
        if widget:
            self.inspector.set_item_widget(widget)
            self.status_bar.showMessage(f"Veri alanı eklendi: {{{item_cfg.field}}}")

    def _on_canvas_item_selected(self, item_widget):
        self.inspector.set_item_widget(item_widget)
        if item_widget:
            cfg = item_widget.item
            self.status_bar.showMessage(f"Seçili: [{cfg.id}] | X: {cfg.x_mm:.1f} mm, Y: {cfg.y_mm:.1f} mm, W: {cfg.w_mm:.1f} mm, H: {cfg.h_mm:.1f} mm")
        else:
            self.status_bar.showMessage("Seçim kaldırıldı.")

    def _on_canvas_item_changed(self, item_widget):
        if item_widget == self.inspector.active_widget:
            self.inspector.set_item_widget(item_widget)

    def _on_property_changed(self, item_widget):
        self.status_bar.showMessage(f"Özellikler güncellendi: [{item_widget.item.id}]")

    def _on_grid_changed(self, text: str):
        if "1.0 mm" in text:
            self.canvas.set_snap_grid(1.0)
        elif "2.5 mm" in text:
            self.canvas.set_snap_grid(2.5)
        elif "5.0 mm" in text:
            self.canvas.set_snap_grid(5.0)
        else:
            self.canvas.set_snap_grid(0.0)

    def _delete_selected_item(self):
        self.canvas.delete_selected_item()
        self.inspector.clear_selection()
        self.status_bar.showMessage("Öğe silindi.")

    def _save_template(self):
        """Mevcut şablon modelini JSON formatında kaydeder."""
        try:
            # ReportTemplate -> dict dönüşümü
            out_dict = {
                "schema_version": self.template.schema_version,
                "template_id": self.template.template_id,
                "title": self.template.title,
                "template_type": self.template.template_type,
                "page": {
                    "size": self.template.page.size,
                    "orientation": self.template.page.orientation.value if hasattr(self.template.page.orientation, "value") else str(self.template.page.orientation),
                    "width_mm": self.template.page.width_mm,
                    "height_mm": self.template.page.height_mm,
                    "margin_top_mm": self.template.page.margin_top_mm,
                    "margin_bottom_mm": self.template.page.margin_bottom_mm,
                    "margin_left_mm": self.template.page.margin_left_mm,
                    "margin_right_mm": self.template.page.margin_right_mm,
                },
                "bands": [],
            }

            for b in self.template.bands:
                band_dict = {
                    "id": b.id,
                    "type": b.type,
                    "height_mm": b.height_mm,
                    "items": [],
                }
                if b.dataset:
                    band_dict["dataset"] = b.dataset
                if b.can_grow:
                    band_dict["can_grow"] = b.can_grow
                if b.keep_together:
                    band_dict["keep_together"] = b.keep_together

                for itm in b.items:
                    itm_dict = {
                        "id": itm.id,
                        "type": itm.type,
                        "x_mm": itm.x_mm,
                        "y_mm": itm.y_mm,
                        "w_mm": itm.w_mm,
                        "h_mm": itm.h_mm,
                    }
                    if itm.text:
                        itm_dict["text"] = itm.text
                    if itm.field:
                        itm_dict["field"] = itm.field
                    if itm.expression:
                        itm_dict["expression"] = itm.expression
                    if itm.format:
                        itm_dict["format"] = itm.format
                    if itm.font_size != 9:
                        itm_dict["font_size"] = itm.font_size
                    if itm.font_bold:
                        itm_dict["font_bold"] = itm.font_bold
                    if itm.font_italic:
                        itm_dict["font_italic"] = itm.font_italic
                    if itm.align != "left":
                        itm_dict["align"] = itm.align
                    if itm.border_top:
                        itm_dict["border_top"] = itm.border_top
                    if itm.border_bottom:
                        itm_dict["border_bottom"] = itm.border_bottom
                    if itm.border_left:
                        itm_dict["border_left"] = itm.border_left
                    if itm.border_right:
                        itm_dict["border_right"] = itm.border_right
                    if itm.border_color != "#CCCCCC":
                        itm_dict["border_color"] = itm.border_color
                    if itm.border_width != 0.5:
                        itm_dict["border_width"] = itm.border_width
                    if itm.bg_color:
                        itm_dict["bg_color"] = itm.bg_color
                    if itm.corner_radius > 0:
                        itm_dict["corner_radius"] = itm.corner_radius
                    if itm.word_wrap:
                        itm_dict["word_wrap"] = itm.word_wrap
                    if itm.text_color != "#000000":
                        itm_dict["text_color"] = itm.text_color

                    band_dict["items"].append(itm_dict)
                out_dict["bands"].append(band_dict)

            with open(self.template_path, "w", encoding="utf-8") as f:
                json.dump(out_dict, f, ensure_ascii=False, indent=2)

            QMessageBox.information(
                self,
                "Başarılı",
                f"Şablon başarıyla kaydedildi:\n{self.template_path}",
            )
            self.status_bar.showMessage(f"Kaydedildi: {self.template_path.name}")

        except Exception as e:
            logger.error(f"Şablon kaydetme hatası: {e}", exc_info=True)
            QMessageBox.critical(self, "Hata", f"Kaydetme sırasında hata oluştu:\n{e}")

    def _open_template(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Rapor Şablonu Aç",
            str(self.template_path.parent),
            "Şablon Dosyaları (*.json)",
        )
        if file_path:
            try:
                p = Path(file_path)
                new_tpl = self._load_template(p)
                self.template_path = p
                self.template = new_tpl
                self.setWindowTitle(f"TOYA ERP - Görsel Form & Rapor Tasarımcısı — [{self.template.title}]")
                self.canvas._populate_bands()
                self.inspector.clear_selection()
                self.status_bar.showMessage(f"Şablon yüklendi: {p.name}")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Şablon açılırken hata oluştu:\n{e}")

    def _on_live_preview(self):
        """Kullanıcının yaptığı son değişiklikleri anında Baskı Önizleme Penceresinde açar."""
        # Önce şablon nesnesini güncellemek için kaydetme formatında güncel veriyi al
        service = TeklifPrintService(template_path=self.template_path)
        data = service.build_teklif_data()

        # Önizleme diyaloğu
        dialog = ReportPreviewDialog(template=self.template, data=data, parent=self)
        dialog.exec()
