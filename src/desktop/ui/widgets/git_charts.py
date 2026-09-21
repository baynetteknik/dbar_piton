"""
TOYA ERP - Git Rapor Grafikleri (QPainter, harici kütüphane gerektirmez)

  BarChart   : dikey sütun grafiği (ör. son 14 günde commit sayısı)
  HBarChart  : yatay çubuklar (ör. klasöre göre değişen dosya, gönderilmemiş/gelen commit)
  StackBar   : tek satır yığılmış çubuk + gösterge (ör. değişiklik türleri)
Renkler tek bir palette bağlıdır; her grafik değerleri sayı olarak da yazar (renge bağımlı olmadan okunur).
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

PALETTE = {
    "primary": "#2563eb", "amber": "#d97706", "green": "#16a34a", "red": "#dc2626", "violet": "#7c3aed",
    "slate": "#64748b", "grid": "#e2e8f0", "text": "#334155", "muted": "#94a3b8",
}


class _Base(QWidget):
    def __init__(self, title: str = "", parent=None) -> None:
        super().__init__(parent)
        self.title = title
        self.empty_text = "Veri yok"

    def _title(self, p: QPainter) -> int:
        # paintEvent geçersiz kılındığı için stil sayfası zemin/çerçeve çizmez: burada elle çizilir
        p.setPen(QPen(QColor("#cbd5e1"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 6, 6)
        f = QFont("Segoe UI", 9)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(PALETTE["text"]))
        p.drawText(QRectF(10, 6, self.width() - 20, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)
        return 28

    def _empty(self, p: QPainter, top: int) -> None:
        p.setPen(QColor(PALETTE["muted"]))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRectF(0, top, self.width(), self.height() - top), Qt.AlignmentFlag.AlignCenter, self.empty_text)


class BarChart(_Base):
    def __init__(self, title: str = "", color: str = PALETTE["primary"], parent=None) -> None:
        super().__init__(title, parent)
        self.data: list[tuple[str, int]] = []
        self.color = color
        self.setMinimumHeight(150)

    def set_data(self, data: list[tuple[str, int]]) -> None:
        self.data = list(data)
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = self._title(p)
        if not self.data or all(v == 0 for _l, v in self.data):
            self._empty(p, top)
            return
        left, right, bottom = 10, 10, 22
        w, h = self.width() - left - right, self.height() - top - bottom - 6
        vmax = max(v for _l, v in self.data)
        n = len(self.data)
        slot = w / n
        bar_w = max(4.0, slot * 0.6)
        p.setPen(QPen(QColor(PALETTE["grid"]), 1))
        p.drawLine(QPointF(left, top + h), QPointF(left + w, top + h))
        small = QFont("Segoe UI", 7)
        for i, (label, v) in enumerate(self.data):
            x = left + i * slot + (slot - bar_w) / 2
            bh = 0 if v == 0 else max(3.0, h * v / vmax * 0.85)
            p.setBrush(QColor(self.color if v else PALETTE["grid"]))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(x, top + h - bh, bar_w, bh if v else 2), 2, 2)
            p.setFont(small)
            p.setPen(QColor(PALETTE["text"]))
            if v:
                p.drawText(QRectF(x - 6, top + h - bh - 14, bar_w + 12, 12), Qt.AlignmentFlag.AlignCenter, str(v))
            p.setPen(QColor(PALETTE["muted"]))
            if n <= 16 or i % 2 == 0:
                p.drawText(QRectF(left + i * slot, top + h + 3, slot, 14), Qt.AlignmentFlag.AlignCenter, label)


class HBarChart(_Base):
    def __init__(self, title: str = "", parent=None) -> None:
        super().__init__(title, parent)
        self.data: list[tuple[str, int, str]] = []
        self.setMinimumHeight(110)

    def set_data(self, data: list[tuple[str, int, str | None]]) -> None:
        self.data = [(l, v, c or PALETTE["primary"]) for l, v, c in data]
        self.setMinimumHeight(40 + 24 * max(2, len(self.data)))
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = self._title(p)
        if not self.data or all(v == 0 for _l, v, _c in self.data):
            self._empty(p, top)
            return
        vmax = max(v for _l, v, _c in self.data) or 1
        label_w = min(130, max(60, int(self.width() * 0.34)))
        f = QFont("Segoe UI", 8)
        p.setFont(f)
        for i, (label, v, color) in enumerate(self.data):
            y = top + i * 24
            p.setPen(QColor(PALETTE["text"]))
            p.drawText(QRectF(10, y, label_w - 6, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       p.fontMetrics().elidedText(label, Qt.TextElideMode.ElideMiddle, label_w - 8))
            bw = (self.width() - label_w - 60) * v / vmax
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(PALETTE["grid"]))
            p.drawRoundedRect(QRectF(label_w + 10, y + 3, self.width() - label_w - 60, 14), 3, 3)
            if v:
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(label_w + 10, y + 3, max(4.0, bw), 14), 3, 3)
            p.setPen(QColor(PALETTE["text"]))
            p.drawText(QRectF(label_w + 14 + max(4.0, bw) if v else label_w + 14, y, 50, 20),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, str(v))


class StackBar(_Base):
    def __init__(self, title: str = "", parent=None) -> None:
        super().__init__(title, parent)
        self.segments: list[tuple[str, int, str]] = []
        self.setMinimumHeight(130)

    def set_segments(self, segments: list[tuple[str, int, str]]) -> None:
        self.segments = [s for s in segments if s[1] > 0]
        self.update()

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = self._title(p)
        total = sum(v for _l, v, _c in self.segments)
        if not total:
            self._empty(p, top)
            return
        x, w = 10.0, float(self.width() - 20)
        p.setPen(Qt.PenStyle.NoPen)
        for _l, v, c in self.segments:
            sw = w * v / total
            p.setBrush(QColor(c))
            p.drawRect(QRectF(x, top + 4, sw, 22))
            x += sw
        p.setFont(QFont("Segoe UI", 8))
        lx, ly = 10.0, top + 38
        for label, v, c in self.segments:
            text = f"{label}: {v}"
            tw = p.fontMetrics().horizontalAdvance(text) + 22
            if lx + tw > self.width() - 8:
                lx, ly = 10.0, ly + 18
            p.setBrush(QColor(c))
            p.drawRoundedRect(QRectF(lx, ly + 3, 10, 10), 2, 2)
            p.setPen(QColor(PALETTE["text"]))
            p.drawText(QRectF(lx + 14, ly, tw, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            p.setPen(Qt.PenStyle.NoPen)
            lx += tw + 6
