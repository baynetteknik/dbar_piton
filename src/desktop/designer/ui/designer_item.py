"""
TOYA ERP - Görsel Tasarımcı Elemanı (DesignerItemWidget)
Bant içerisindeki her bir metin, veri alanı, resim, kutu veya çizginin
sürükle-bırak ile taşınmasını, boyutlandırılmasını ve seçilmesini yönetir.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from src.desktop.designer.models import ItemConfig


class DesignerItemWidget(QWidget):
    """Görsel tuval üzerindeki düzenlenebilir nesne."""

    selected = pyqtSignal(object)  # self
    geometry_changed = pyqtSignal(object)  # self

    HANDLE_SIZE = 6

    def __init__(
        self,
        item_config: ItemConfig,
        mm_to_px: float = 3.7795,
        snap_grid_mm: float = 1.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.item = item_config
        self.mm_to_px = mm_to_px
        self.snap_grid_mm = snap_grid_mm
        self.is_selected = False

        # Sürükleme ve Boyutlandırma durumları
        self._dragging = False
        self._resizing = False
        self._active_handle = None
        self._drag_start_pos = QPoint()
        self._drag_orig_geom = QRect()

        self.setMouseTracking(True)
        self.update_geometry_from_model()

    def set_snap_grid(self, grid_mm: float):
        self.snap_grid_mm = grid_mm

    def set_scale(self, mm_to_px: float):
        self.mm_to_px = mm_to_px
        self.update_geometry_from_model()

    def update_geometry_from_model(self):
        """ItemConfig milimetrik değerlerinden piksel geometrisini hesaplar."""
        x_px = int(round(self.item.x_mm * self.mm_to_px))
        y_px = int(round(self.item.y_mm * self.mm_to_px))
        w_px = max(12, int(round(self.item.w_mm * self.mm_to_px)))
        h_px = max(10, int(round(self.item.h_mm * self.mm_to_px)))
        self.setGeometry(x_px, y_px, w_px, h_px)
        self.update()

    def update_model_from_geometry(self):
        """Piksel geometrisinden milimetrik değerleri modele yazar."""
        x_mm = self.x() / self.mm_to_px
        y_mm = self.y() / self.mm_to_px
        w_mm = self.width() / self.mm_to_px
        h_mm = self.height() / self.mm_to_px

        # Mıknatıslı Izgara (Snap to Grid)
        if self.snap_grid_mm > 0:
            x_mm = round(x_mm / self.snap_grid_mm) * self.snap_grid_mm
            y_mm = round(y_mm / self.snap_grid_mm) * self.snap_grid_mm
            w_mm = max(self.snap_grid_mm, round(w_mm / self.snap_grid_mm) * self.snap_grid_mm)
            h_mm = max(self.snap_grid_mm, round(h_mm / self.snap_grid_mm) * self.snap_grid_mm)

        self.item.x_mm = round(x_mm, 2)
        self.item.y_mm = round(y_mm, 2)
        self.item.w_mm = round(w_mm, 2)
        self.item.h_mm = round(h_mm, 2)

        self.update_geometry_from_model()
        self.geometry_changed.emit(self)

    def set_selected(self, val: bool):
        self.is_selected = val
        self.update()

    def _get_handles(self) -> dict[str, QRect]:
        """8 adet tutamaç dikdörtgeni döner (Sol-Üst, Orta-Üst, Sağ-Üst vb.)."""
        s = self.HANDLE_SIZE
        half = s // 2
        w, h = self.width(), self.height()

        return {
            "top_left": QRect(0, 0, s, s),
            "top_mid": QRect(w // 2 - half, 0, s, s),
            "top_right": QRect(w - s, 0, s, s),
            "mid_left": QRect(0, h // 2 - half, s, s),
            "mid_right": QRect(w - s, h // 2 - half, s, s),
            "bottom_left": QRect(0, h - s, s, s),
            "bottom_mid": QRect(w // 2 - half, h - s, s, s),
            "bottom_right": QRect(w - s, h - s, s, s),
        }

    def _get_handle_at(self, pos: QPoint) -> str | None:
        if not self.is_selected:
            return None
        for name, rect in self._get_handles().items():
            if rect.contains(pos):
                return name
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_selected(True)
            self.selected.emit(self)

            handle = self._get_handle_at(event.pos())
            if handle:
                self._resizing = True
                self._active_handle = handle
            else:
                self._dragging = True
                self._drag_start_pos = event.globalPosition().toPoint()
                self._drag_orig_geom = self.geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resizing and self._active_handle:
            delta = event.pos()
            orig = self._drag_orig_geom if hasattr(self, "_drag_orig_geom") else self.geometry()
            geom = self.geometry()

            # Tutamaç yönüne göre boyutlandır
            if "right" in self._active_handle:
                geom.setWidth(max(15, event.pos().x()))
            if "bottom" in self._active_handle:
                geom.setHeight(max(10, event.pos().y()))
            if "left" in self._active_handle:
                diff_x = event.pos().x()
                geom.setLeft(geom.left() + diff_x)
            if "top" in self._active_handle:
                diff_y = event.pos().y()
                geom.setTop(geom.top() + diff_y)

            self.setGeometry(geom)
            self.update_model_from_geometry()
            event.accept()

        elif self._dragging:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            new_pos = self._drag_orig_geom.topLeft() + delta

            # Üst sınır kontrolü (bant dışına taşmasın)
            new_x = max(0, new_pos.x())
            new_y = max(0, new_pos.y())
            self.move(new_x, new_y)
            self.update_model_from_geometry()
            event.accept()

        else:
            # İmleç ikonunu güncelle
            handle = self._get_handle_at(event.pos())
            if handle in ("top_left", "bottom_right"):
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
            elif handle in ("top_right", "bottom_left"):
                self.setCursor(QCursor(Qt.CursorShape.SizeBDiagCursor))
            elif handle in ("top_mid", "bottom_mid"):
                self.setCursor(QCursor(Qt.CursorShape.SizeVerCursor))
            elif handle in ("mid_left", "mid_right"):
                self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._resizing = False
            self._active_handle = None
            self.update_model_from_geometry()
            event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)

        # Arka plan
        if self.item.bg_color:
            painter.fillRect(rect, QColor(self.item.bg_color))
        else:
            # Şeffaf veya hafif arka plan
            if self.item.type == "data_field":
                painter.fillRect(rect, QColor("#F5F3FF"))  # Hafif mor
            elif self.item.type == "expression":
                painter.fillRect(rect, QColor("#EFF6FF"))  # Hafif mavi
            else:
                painter.fillRect(rect, QColor(255, 255, 255, 180))

        # Çerçeve
        if self.is_selected:
            painter.setPen(QPen(QColor("#2563EB"), 1.5, Qt.PenStyle.SolidLine))
        else:
            painter.setPen(QPen(QColor("#CBD5E1"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(rect)

        # İçerik Çizimi
        font = QFont(self.item.font_family, max(6, int(self.item.font_size * 0.9)))
        font.setBold(self.item.font_bold)
        font.setItalic(self.item.font_italic)
        painter.setFont(font)

        if self.item.type == "data_field":
            painter.setPen(QPen(QColor("#7C3AED")))
            display_text = f"{{{self.item.field}}}"
        elif self.item.type == "expression":
            painter.setPen(QPen(QColor("#1D4ED8")))
            display_text = self.item.expression or "[Fx]"
        elif self.item.type == "barcode":
            painter.setPen(QPen(QColor("#0F172A")))
            display_text = f"[QR: {self.item.field or 'Karekod'}]"
        elif self.item.type == "image":
            painter.setPen(QPen(QColor("#0284C7")))
            display_text = "🖼️ [LOGO / RESİM]"
        else:
            painter.setPen(QPen(QColor(self.item.text_color)))
            display_text = self.item.text

        flags = Qt.AlignmentFlag.AlignVCenter
        if self.item.align == "center":
            flags |= Qt.AlignmentFlag.AlignHCenter
        elif self.item.align == "right":
            flags |= Qt.AlignmentFlag.AlignRight
        else:
            flags |= Qt.AlignmentFlag.AlignLeft

        text_rect = rect.adjusted(3, 2, -3, -2)
        painter.drawText(text_rect, flags, display_text)

        # Seçim Tutamaçları (8 Nokta)
        if self.is_selected:
            painter.setPen(QPen(QColor("#1E40AF"), 1))
            painter.setBrush(QColor("#FFFFFF"))
            for h_rect in self._get_handles().values():
                painter.drawRect(h_rect)
