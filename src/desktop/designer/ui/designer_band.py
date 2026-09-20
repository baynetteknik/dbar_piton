"""
TOYA ERP - Görsel Tasarımcı Bant Bileşeni (DesignerBandWidget)
Sayfa Başı, Detay Satırı, Dip Toplam gibi bantları görsel olarak temsil eder;
alt kenarından tutularak milimetrik yüksekliğinin değiştirilmesini sağlar.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QLabel, QWidget

from src.desktop.designer.models import MIME_ITEM_CONFIG, BandConfig, ItemConfig
from src.desktop.designer.ui.designer_item import DesignerItemWidget


class DesignerBandWidget(QWidget):
    """Tuval üzerindeki tek bir rapor bandı."""

    height_changed = pyqtSignal(object)  # self
    item_selected = pyqtSignal(object)  # DesignerItemWidget
    item_changed = pyqtSignal(object)  # DesignerItemWidget

    RESIZE_BORDER_THICKNESS = 6

    BAND_TITLES = {
        "report_title": "📜 Rapor Başlığı (Report Title)",
        "page_header": "🏷️ Sayfa Üst Bilgisi (Page Header)",
        "header_group": "👤 Müşteri / Cari Künyesi (Header Group)",
        "group_header": "🗂️ Grup Başlığı (Group Header)",
        "column_header": "📋 Kolon Başlıkları (Column Header)",
        "detail_data": "📊 Detay / Kalem Satırı (Detail Data)",
        "child": "🔗 Alt / Bağlı Bant (Child Band)",
        "group_footer": "📑 Grup Özeti (Group Footer)",
        "column_footer": "🔄 Sayfa Nakli Yekûn (Column Footer)",
        "report_summary": "💰 Belge Özeti / Dip Toplam (Report Summary)",
        "page_footer": "📄 Sayfa Altı (Page Footer)",
    }

    BAND_COLORS = {
        "page_header": ("#EFF6FF", "#1D4ED8"),
        "header_group": ("#F8FAFC", "#475569"),
        "column_header": ("#0F172A", "#FFFFFF"),
        "detail_data": ("#FAF5FF", "#7C3AED"),
        "report_summary": ("#ECFDF5", "#047857"),
        "page_footer": ("#F1F5F9", "#64748B"),
    }

    def __init__(
        self,
        band_config: BandConfig,
        mm_to_px: float = 3.7795,
        snap_grid_mm: float = 1.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.band = band_config
        self.mm_to_px = mm_to_px
        self.snap_grid_mm = snap_grid_mm

        self._resizing_height = False
        self._resize_start_y = 0
        self._resize_start_h = 0

        self.item_widgets: list[DesignerItemWidget] = []
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self._init_items()
        self.update_geometry_from_model()

    def set_scale(self, mm_to_px: float):
        self.mm_to_px = mm_to_px
        self.update_geometry_from_model()
        for itm in self.item_widgets:
            itm.set_scale(mm_to_px)

    def set_snap_grid(self, grid_mm: float):
        self.snap_grid_mm = grid_mm
        for itm in self.item_widgets:
            itm.set_snap_grid(grid_mm)

    def update_geometry_from_model(self):
        h_px = int(round(self.band.height_mm * self.mm_to_px))
        self.setFixedHeight(max(20, h_px))
        self.update()

    def _init_items(self):
        """ItemConfig modellerini DesignerItemWidget nesnelerine dönüştürür."""
        for itm_config in self.band.items:
            self.add_item_widget(itm_config)

    def add_item_widget(self, itm_config: ItemConfig) -> DesignerItemWidget:
        if itm_config not in self.band.items:
            self.band.items.append(itm_config)

        widget = DesignerItemWidget(
            itm_config,
            mm_to_px=self.mm_to_px,
            snap_grid_mm=self.snap_grid_mm,
            parent=self,
        )
        widget.selected.connect(self._on_item_selected)
        widget.geometry_changed.connect(self._on_item_changed)
        widget.show()
        self.item_widgets.append(widget)
        return widget

    def remove_item_widget(self, widget: DesignerItemWidget):
        if widget in self.item_widgets:
            self.item_widgets.remove(widget)
        if widget.item in self.band.items:
            self.band.items.remove(widget.item)
        widget.deleteLater()
        self.update()

    def _on_item_selected(self, item_widget: DesignerItemWidget):
        # Diğer tüm elemanların seçimini kaldır
        for itm in self.item_widgets:
            if itm != item_widget:
                itm.set_selected(False)
        self.item_selected.emit(item_widget)

    def _on_item_changed(self, item_widget: DesignerItemWidget):
        self.item_changed.emit(item_widget)

    def _is_on_resize_border(self, pos: QPoint) -> bool:
        return abs(pos.y() - self.height()) <= self.RESIZE_BORDER_THICKNESS

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_on_resize_border(event.pos()):
                self._resizing_height = True
                self._resize_start_y = event.globalPosition().toPoint().y()
                self._resize_start_h = self.height()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._resizing_height:
            delta_y = event.globalPosition().toPoint().y() - self._resize_start_y
            new_h_px = max(20, self._resize_start_h + delta_y)

            # Milimetreye çevir ve ızgaraya yapıştır
            new_h_mm = new_h_px / self.mm_to_px
            if self.snap_grid_mm > 0:
                new_h_mm = round(new_h_mm / self.snap_grid_mm) * self.snap_grid_mm

            self.band.height_mm = max(2.0, round(new_h_mm, 1))
            self.update_geometry_from_model()
            self.height_changed.emit(self)
            event.accept()
        else:
            if self._is_on_resize_border(event.pos()):
                self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor) if not self.underMouse() else QCursor(Qt.CursorShape.ArrowCursor))
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._resizing_height:
            self._resizing_height = False
            self.height_changed.emit(self)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Sürükle-Bırak: Araç Kutusu / Veri Ağacı'ndan bu banda eleman bırakma
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_ITEM_CONFIG):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_ITEM_CONFIG):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(MIME_ITEM_CONFIG):
            return
        raw = bytes(event.mimeData().data(MIME_ITEM_CONFIG))
        try:
            payload = json.loads(raw.decode("utf-8"))
            cfg = ItemConfig(**payload)
        except (ValueError, TypeError):
            event.ignore()
            return

        # Aynı sürükleme her zaman yeni bir eleman oluşturur; kaynak
        # widget'taki id ile çakışmasın diye burada tazelenir.
        cfg.id = f"{cfg.type}_{uuid.uuid4().hex[:6]}"

        drop_pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        x_mm = max(0.0, drop_pos.x() / self.mm_to_px)
        y_mm = max(0.0, drop_pos.y() / self.mm_to_px)
        if self.snap_grid_mm > 0:
            x_mm = round(x_mm / self.snap_grid_mm) * self.snap_grid_mm
            y_mm = round(y_mm / self.snap_grid_mm) * self.snap_grid_mm
        cfg.x_mm = round(x_mm, 2)
        cfg.y_mm = round(y_mm, 2)

        widget = self.add_item_widget(cfg)
        widget.set_selected(True)
        self._on_item_selected(widget)
        event.acceptProposedAction()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w, h = self.width(), self.height()

        # Bant arka planı
        bg_col_hex, text_col_hex = self.BAND_COLORS.get(
            self.band.type, ("#FFFFFF", "#334155")
        )
        painter.fillRect(0, 0, w, h, QColor(bg_col_hex if self.band.type != "column_header" else "#FFFFFF"))

        # Bant sol başlık etiketi bandı
        painter.fillRect(0, 0, w, 16, QColor("#F1F5F9"))
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.drawLine(0, 16, w, 16)

        # Bant adı ve milimetrik boyutu
        title = self.BAND_TITLES.get(self.band.type, self.band.type)
        suffix = " (KAPALI — baskıda kullanılmaz)" if not self.band.enabled else ""
        label_text = f"{title} — [H: {self.band.height_mm:.1f} mm]{suffix}"
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        painter.setPen(QPen(QColor(text_col_hex) if self.band.enabled else QColor("#94A3B8")))
        painter.drawText(8, 12, label_text)

        # Kapalı bantlar tuvalde soluk (yarı saydam gri) gösterilir.
        if not self.band.enabled:
            painter.fillRect(0, 16, w, h - 16, QColor(148, 163, 184, 90))

        # Alt kenar ayırıcı çizgi (Boyutlandırma kolu)
        painter.setPen(QPen(QColor("#3B82F6"), 2 if self._resizing_height else 1, Qt.PenStyle.DashLine))
        painter.drawLine(0, h - 1, w, h - 1)
