"""
TOYA ERP - Milimetrik Cetvel Bileşeni (RulerWidget)
Tuvalin üstünde ve solunda gerçek milimetre ölçülerini ve çentiklerini çizer.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class RulerWidget(QWidget):
    """Milimetrik yatay veya dikey cetvel."""

    HORIZONTAL = 1
    VERTICAL = 2

    def __init__(
        self,
        orientation: int = HORIZONTAL,
        mm_to_px: float = 3.7795,
        offset_px: float = 0.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.orientation = orientation
        self.mm_to_px = mm_to_px
        self.offset_px = offset_px
        self.scale_factor = 1.0

        if self.orientation == self.HORIZONTAL:
            self.setFixedHeight(24)
        else:
            self.setFixedWidth(24)

        self.setStyleSheet("background-color: #F1F5F9; border: 1px solid #CBD5E1;")

    def set_scale_and_offset(self, mm_to_px: float, scale_factor: float, offset_px: float = 0.0):
        self.mm_to_px = mm_to_px
        self.scale_factor = scale_factor
        self.offset_px = offset_px
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Arka plan
        painter.fillRect(self.rect(), QColor("#F8FAFC"))

        pen_border = QPen(QColor("#CBD5E1"), 1)
        pen_tick_minor = QPen(QColor("#94A3B8"), 1)
        pen_tick_major = QPen(QColor("#475569"), 1)

        font = QFont("Segoe UI", 6)
        painter.setFont(font)
        painter.setPen(pen_tick_major)

        step_px = self.mm_to_px * self.scale_factor

        if self.orientation == self.HORIZONTAL:
            # Kenar çizgisi
            painter.setPen(pen_border)
            painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

            # Çentikler (mm)
            max_mm = int((self.width() + abs(self.offset_px)) / step_px) + 5
            for mm in range(max_mm):
                pos_x = (mm * step_px) + self.offset_px
                if pos_x < 0 or pos_x > self.width():
                    continue

                if mm % 10 == 0:
                    painter.setPen(pen_tick_major)
                    painter.drawLine(int(pos_x), self.height() - 12, int(pos_x), self.height())
                    if mm > 0:
                        painter.drawText(int(pos_x) + 2, self.height() - 12, str(mm))
                elif mm % 5 == 0:
                    painter.setPen(pen_tick_minor)
                    painter.drawLine(int(pos_x), self.height() - 7, int(pos_x), self.height())
                else:
                    # 1 mm çentikleri sadece yeterince yakınlaştırılmışsa çiz
                    if step_px > 3.0:
                        painter.setPen(pen_tick_minor)
                        painter.drawLine(int(pos_x), self.height() - 4, int(pos_x), self.height())

        else:
            # Dikey kenar çizgisi
            painter.setPen(pen_border)
            painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())

            max_mm = int((self.height() + abs(self.offset_px)) / step_px) + 5
            for mm in range(max_mm):
                pos_y = (mm * step_px) + self.offset_px
                if pos_y < 0 or pos_y > self.height():
                    continue

                if mm % 10 == 0:
                    painter.setPen(pen_tick_major)
                    painter.drawLine(self.width() - 12, int(pos_y), self.width(), int(pos_y))
                    if mm > 0:
                        painter.drawText(2, int(pos_y) - 2, str(mm))
                elif mm % 5 == 0:
                    painter.setPen(pen_tick_minor)
                    painter.drawLine(self.width() - 7, int(pos_y), self.width(), int(pos_y))
                else:
                    if step_px > 3.0:
                        painter.setPen(pen_tick_minor)
                        painter.drawLine(self.width() - 4, int(pos_y), self.width(), int(pos_y))
