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

from src.desktop.designer.models import ItemConfig, PaperOrientation, ReportTemplate
from src.desktop.designer.preview_dialog import ReportPreviewDialog
from src.desktop.designer.services.teklif_print_service import TeklifPrintService
from src.desktop.designer.ui.band_manager_dialog import BandManagerDialog
from src.desktop.designer.ui.data_tree_widget import DataTreeWidget
from src.desktop.designer.ui.designer_canvas import DesignerCanvas
from src.desktop.designer.ui.property_inspector import PropertyInspector
from src.desktop.designer.ui.toolbox_widget import ToolboxWidget

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "templates" / "tpl_teklif_kurumsal_a4.json"
)

#: Sayfa boyutu seçici — dikey (portrait) mm ölçüleri; yatayda genişlik/yükseklik yer değiştirir.
PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
}

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

        self.data_tree = DataTreeWidget(left_tabs, module=self.template.module)
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

        self.btn_bands = QPushButton("🗂️ Bantlar...", bar)
        self.btn_bands.setStyleSheet(_BTN_NEUTRAL)
        self.btn_bands.setToolTip(
            "Bantları etkinleştir/kapat, yüksekliklerini mm olarak düzenle.",
        )
        self.btn_bands.clicked.connect(self._open_band_manager)
        lyt.addWidget(self.btn_bands)

        sep_page = QLabel("  Sayfa: ", bar)
        sep_page.setStyleSheet("color: #94A3B8; font-size: 11px;")
        lyt.addWidget(sep_page)

        self.cmb_page_size = QComboBox(bar)
        self.cmb_page_size.setStyleSheet("""
    QComboBox {
        combobox-popup: 0;
        background-color: #1E293B;
        color: #F8FAFC;
        border: 1px solid #334155;
        border-radius: 4px;
        padding: 3px 8px;
        font-size: 11px;
    }
    QComboBox QAbstractItemView {
        outline: 0;
        padding: 0px;
        border: 1px solid #334155;
        background-color: #1E293B;
        color: #F8FAFC;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 6px;
        min-height: 20px;
    }
""")
        self.cmb_page_size.addItems(list(PAGE_SIZES_MM.keys()))
        self.cmb_page_size.setCurrentText(
            self.template.page.size if self.template.page.size in PAGE_SIZES_MM else "A4",
        )
        self.cmb_page_size.currentTextChanged.connect(self._on_page_size_changed)
        lyt.addWidget(self.cmb_page_size)

        self.cmb_orientation = QComboBox(bar)
        self.cmb_orientation.setStyleSheet("""
    QComboBox {
        combobox-popup: 0;
        background-color: #1E293B;
        color: #F8FAFC;
        border: 1px solid #334155;
        border-radius: 4px;
        padding: 3px 8px;
        font-size: 11px;
    }
    QComboBox QAbstractItemView {
        outline: 0;
        padding: 0px;
        border: 1px solid #334155;
        background-color: #1E293B;
        color: #F8FAFC;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 6px;
        min-height: 20px;
    }
""")
        self.cmb_orientation.addItems(["Dikey", "Yatay"])
        self.cmb_orientation.setCurrentIndex(
            1 if self.template.page.orientation == PaperOrientation.LANDSCAPE else 0,
        )
        self.cmb_orientation.currentIndexChanged.connect(self._on_orientation_changed)
        lyt.addWidget(self.cmb_orientation)

        sep = QLabel("  Izgara: ", bar)
        sep.setStyleSheet("color: #94A3B8; font-size: 11px;")
        lyt.addWidget(sep)

        self.cmb_grid = QComboBox(bar)
        self.cmb_grid.setStyleSheet("""
    QComboBox {
        combobox-popup: 0;
        background-color: #1E293B;
        color: #F8FAFC;
        border: 1px solid #334155;
        border-radius: 4px;
        padding: 3px 8px;
        font-size: 11px;
    }
    QComboBox QAbstractItemView {
        outline: 0;
        padding: 0px;
        border: 1px solid #334155;
        background-color: #1E293B;
        color: #F8FAFC;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 6px;
        min-height: 20px;
    }
""")
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

    # ------------------------------------------------------------------
    # Sayfa Boyutu / Yön
    # ------------------------------------------------------------------
    def _has_placed_items(self) -> bool:
        return any(b.items for b in self.template.bands)

    def _confirm_page_change(self, prompt: str) -> bool:
        """Bantlarda zaten yerleştirilmiş eleman varsa onay ister."""
        if not self._has_placed_items():
            return True
        reply = QMessageBox.question(
            self, "Sayfa Ayarı Değişikliği",
            f"{prompt}\n\n"
            "Tuval üzerinde zaten yerleştirilmiş elemanlar var; sayfa boyutu/yönü "
            "değişince bu elemanların konumu yeni sayfa sınırlarına göre elle "
            "kontrol edilmelidir.\n\nYine de devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _apply_page_dimensions(self) -> None:
        base_w, base_h = PAGE_SIZES_MM.get(self.template.page.size, (210.0, 297.0))
        if self.template.page.orientation == PaperOrientation.LANDSCAPE:
            base_w, base_h = base_h, base_w
        self.template.page.width_mm = base_w
        self.template.page.height_mm = base_h
        self.canvas.page_canvas._update_size()
        self.canvas.page_canvas.update()

    def _on_page_size_changed(self, size_name: str) -> None:
        if not self._confirm_page_change(f"Sayfa boyutu '{size_name}' olarak değiştirilecek."):
            self.cmb_page_size.blockSignals(True)
            self.cmb_page_size.setCurrentText(self.template.page.size)
            self.cmb_page_size.blockSignals(False)
            return
        self.template.page.size = size_name
        self._apply_page_dimensions()
        self._set_status(f"Sayfa boyutu değiştirildi: {size_name}")

    def _on_orientation_changed(self, index: int) -> None:
        new_orientation = PaperOrientation.LANDSCAPE if index == 1 else PaperOrientation.PORTRAIT
        if new_orientation == self.template.page.orientation:
            return
        if not self._confirm_page_change(
            f"Sayfa yönü '{'Yatay' if index == 1 else 'Dikey'}' olarak değiştirilecek.",
        ):
            self.cmb_orientation.blockSignals(True)
            self.cmb_orientation.setCurrentIndex(
                1 if self.template.page.orientation == PaperOrientation.LANDSCAPE else 0,
            )
            self.cmb_orientation.blockSignals(False)
            return
        self.template.page.orientation = new_orientation
        self._apply_page_dimensions()
        self._set_status(f"Sayfa yönü değiştirildi: {'Yatay' if index == 1 else 'Dikey'}")

    # ------------------------------------------------------------------
    # Bant Yönetimi
    # ------------------------------------------------------------------
    def _open_band_manager(self) -> None:
        dlg = BandManagerDialog(self.template, parent=self)
        if dlg.exec():
            for band_widget in self.canvas.band_widgets:
                band_widget.update_geometry_from_model()
                band_widget.update()
            self._set_status("Bant ayarları güncellendi.")

    def _delete_selected_item(self) -> None:
        self.canvas.delete_selected_item()
        self.inspector.clear_selection()
        self._set_status("Öğe silindi.")

    # ------------------------------------------------------------------
    def _save_template(self) -> None:
        """Mevcut şablon modelini JSON formatında kaydeder."""
        try:
            out_dict = self.template.to_dict()
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
            self.data_tree.set_module(self.template.module)
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
