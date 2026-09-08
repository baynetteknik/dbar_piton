"""
TOYA ERP - Görsel Tasarım Tuvali (DesignerCanvas)
Milimetrik cetveller, mıknatıslı ızgara ve bantları barındıran ana çizim alanı.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPointF, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.desktop.designer.models import BandConfig, ItemConfig, ReportTemplate
from src.desktop.designer.ui.designer_band import DesignerBandWidget
from src.desktop.designer.ui.designer_item import DesignerItemWidget
from src.desktop.designer.ui.ruler_widget import RulerWidget


class PageCanvasWidget(QWidget):
    """Gerçek A4 boyutundaki beyaz milimetrik sayfa alanı."""

    def __init__(self, template: ReportTemplate, mm_to_px: float = 3.7795, parent=None):
        super().__init__(parent)
        self.template = template
        self.mm_to_px = mm_to_px
        self.show_grid = True
        self.grid_size_mm = 2.5

        self.setStyleSheet("background-color: #FFFFFF;")
        self._update_size()

    def set_scale(self, mm_to_px: float):
        self.mm_to_px = mm_to_px
        self._update_size()
        self.update()

    def set_grid(self, show: bool, size_mm: float):
        self.show_grid = show
        self.grid_size_mm = size_mm
        self.update()

    def _update_size(self):
        # A4 ebatları (piksel)
        w_px = int(round(self.template.page.width_mm * self.mm_to_px))
        h_px = int(round(self.template.page.height_mm * self.mm_to_px))
        self.setFixedSize(w_px, h_px)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        # Noktalı Mıknatıslı Izgara (Dot Grid)
        if self.show_grid and self.grid_size_mm > 0:
            grid_step_px = self.grid_size_mm * self.mm_to_px
            if grid_step_px >= 4.0:
                painter.setPen(QPen(QColor("#E2E8F0"), 1))
                w = self.width()
                h = self.height()
                x = 0.0
                while x < w:
                    y = 0.0
                    while y < h:
                        painter.drawPoint(int(x), int(y))
                        y += grid_step_px
                    x += grid_step_px

        # Sayfa Marj Sınır Çizgileri
        margin_left_px = int(self.template.page.margin_left_mm * self.mm_to_px)
        margin_top_px = int(self.template.page.margin_top_mm * self.mm_to_px)
        margin_right_px = int((self.template.page.width_mm - self.template.page.margin_right_mm) * self.mm_to_px)
        margin_bottom_px = int((self.template.page.height_mm - self.template.page.margin_bottom_mm) * self.mm_to_px)

        pen_margin = QPen(QColor("#CBD5E1"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_margin)
        painter.drawLine(margin_left_px, 0, margin_left_px, self.height())
        painter.drawLine(margin_right_px, 0, margin_right_px, self.height())
        painter.drawLine(0, margin_top_px, self.width(), margin_top_px)
        painter.drawLine(0, margin_bottom_px, self.width(), margin_bottom_px)


class DesignerCanvas(QWidget):
    """Cetvelleri ve bantları içeren tam teşekküllü tuval yöneticisi."""

    item_selected = pyqtSignal(object)  # DesignerItemWidget
    item_changed = pyqtSignal(object)  # DesignerItemWidget
    band_height_changed = pyqtSignal(object)  # DesignerBandWidget

    def __init__(
        self,
        template: ReportTemplate,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.template = template
        self.mm_to_px = 3.7795  # 96 DPI bazlı (1 mm ~ 3.78 px)
        self.snap_grid_mm = 1.0

        self.selected_item_widget: DesignerItemWidget | None = None
        self.band_widgets: list[DesignerBandWidget] = []

        self._init_ui()

    def _init_ui(self):
        grid_layout = QGridLayout(self)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)

        # Köşe Boşluğu (Cetvellerin kesişimi)
        corner = QWidget(self)
        corner.setFixedSize(24, 24)
        corner.setStyleSheet("background-color: #E2E8F0; border: 1px solid #CBD5E1;")
        grid_layout.addWidget(corner, 0, 0)

        # Üst Yatay Cetvel
        self.ruler_top = RulerWidget(orientation=RulerWidget.HORIZONTAL, mm_to_px=self.mm_to_px, parent=self)
        grid_layout.addWidget(self.ruler_top, 0, 1)

        # Sol Dikey Cetvel
        self.ruler_left = RulerWidget(orientation=RulerWidget.VERTICAL, mm_to_px=self.mm_to_px, parent=self)
        grid_layout.addWidget(self.ruler_left, 1, 0)

        # Orta Kaydırma Alanı (Scroll Area)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setStyleSheet("background-color: #64748B;")
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Beyaz A4 Sayfası
        self.page_canvas = PageCanvasWidget(self.template, mm_to_px=self.mm_to_px, parent=self)
        # NOT: Qt QSS 'box-shadow' desteklemez ("Unknown property" uyarısı verirdi);
        # gölge QGraphicsDropShadowEffect ile verilir.
        self.page_canvas.setStyleSheet(
            "background-color: #FFFFFF; border: 1px solid #334155;",
        )
        _shadow = QGraphicsDropShadowEffect(self.page_canvas)
        _shadow.setBlurRadius(24)
        _shadow.setOffset(0, 8)
        _shadow.setColor(QColor(0, 0, 0, 90))
        self.page_canvas.setGraphicsEffect(_shadow)

        # Sayfa içindeki bantlar dikey dizilim
        self.bands_layout = QVBoxLayout(self.page_canvas)
        self.bands_layout.setContentsMargins(0, 0, 0, 0)
        self.bands_layout.setSpacing(0)
        self.bands_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._populate_bands()

        self.scroll_area.setWidget(self.page_canvas)
        self.scroll_area.setWidgetResizable(False)

        # Scroll senkronizasyonu
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self._on_h_scroll)
        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_v_scroll)

        grid_layout.addWidget(self.scroll_area, 1, 1)

    def _populate_bands(self):
        """Şablon bantlarını sırayla ekler."""
        # Eski bantları temizle
        while self.bands_layout.count():
            item = self.bands_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.band_widgets.clear()

        for band_cfg in self.template.bands:
            band_widget = DesignerBandWidget(
                band_cfg,
                mm_to_px=self.mm_to_px,
                snap_grid_mm=self.snap_grid_mm,
                parent=self.page_canvas,
            )
            band_widget.height_changed.connect(self._on_band_height_changed)
            band_widget.item_selected.connect(self._on_item_selected)
            band_widget.item_changed.connect(self._on_item_changed)
            self.bands_layout.addWidget(band_widget)
            self.band_widgets.append(band_widget)

    def _on_h_scroll(self, val: int):
        self.ruler_top.set_scale_and_offset(self.mm_to_px, 1.0, -val)

    def _on_v_scroll(self, val: int):
        self.ruler_left.set_scale_and_offset(self.mm_to_px, 1.0, -val)

    def _on_band_height_changed(self, band_widget: DesignerBandWidget):
        self.band_height_changed.emit(band_widget)

    def _on_item_selected(self, item_widget: DesignerItemWidget):
        # Diğer bantlardaki elemanların seçimini kaldır
        for b_w in self.band_widgets:
            for itm in b_w.item_widgets:
                if itm != item_widget:
                    itm.set_selected(False)

        self.selected_item_widget = item_widget
        self.item_selected.emit(item_widget)

    def _on_item_changed(self, item_widget: DesignerItemWidget):
        self.item_changed.emit(item_widget)

    def set_snap_grid(self, grid_mm: float):
        self.snap_grid_mm = grid_mm
        self.page_canvas.set_grid(grid_mm > 0, grid_mm)
        for b in self.band_widgets:
            b.set_snap_grid(grid_mm)

    def get_target_band(self, band_type: str = "detail_data") -> DesignerBandWidget | None:
        """Belirtilen tipte veya ilk uygun bandı döner."""
        for b in self.band_widgets:
            if b.band.type == band_type:
                return b
        return self.band_widgets[0] if self.band_widgets else None

    def add_new_item_to_band(self, item_cfg: ItemConfig, band_type: str | None = None) -> DesignerItemWidget | None:
        target_band = None
        if self.selected_item_widget:
            # Seçili nesnenin bulunduğu banda ekle
            parent = self.selected_item_widget.parent()
            if isinstance(parent, DesignerBandWidget):
                target_band = parent

        if not target_band:
            target_band = self.get_target_band(band_type or "page_header")

        if target_band:
            new_widget = target_band.add_item_widget(item_cfg)
            new_widget.set_selected(True)
            self._on_item_selected(new_widget)
            return new_widget
        return None

    def delete_selected_item(self):
        """Seçili nesneyi tuvalden ve modelden siler."""
        if self.selected_item_widget:
            parent = self.selected_item_widget.parent()
            if isinstance(parent, DesignerBandWidget):
                parent.remove_item_widget(self.selected_item_widget)
                self.selected_item_widget = None
                self.item_selected.emit(None)
