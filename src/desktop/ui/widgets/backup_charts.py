"""TOYA ERP - Yedekleme panosu grafikleri (QPainter; ek kütüphane gerekmez).

- `TimelineBarChart`: yedek geçmişi ve boyutu. Tam yedek mavi ve kalın, artımlı yeşil ve ince, hatalı kırmızı + "!" işareti.
  Çubuğun üzerine gelince tür / tarih / süre / boyut / durum-hata mesajı görünür; tıklayınca `run_clicked(Run)` yayılır.
- `DonutChart`: hedef disk doluluğu (son yedek, eski yedekler, diğer kullanım, boş alan); dilime tıklayınca `slice_clicked(anahtar)`.
- `LineChart`: performans trendi; süre (dk, sol eksen) ve aktarım hızı (MB/s, sağ eksen).
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QToolTip, QWidget

from src.desktop.services.backup.history import Run, format_duration, format_size

C_FULL, C_INC, C_MIRROR = QColor("#3b82f6"), QColor("#22c55e"), QColor("#a855f7")
C_ERR, C_WARN, C_TEXT, C_GRID = QColor("#ef4444"), QColor("#f59e0b"), QColor("#334155"), QColor("#e2e8f0")
_TUR = {"full": "Tam yedek", "inc": "Artımlı", "mirror": "Klasör senkronu"}
_DURUM = {"ok": "✔ Başarılı", "warning": "⚠ Uyarıyla tamamlandı", "error": "✘ Hata", "nochange": "⏭ Değişiklik yok"}


def _nice_ceiling(v: float) -> float:
    if v <= 0:
        return 1.0
    p = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * p:
            return m * p
    return 10 * p


class _ChartBase(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self._hits: list[tuple[QRectF, object]] = []
        self._hover: object | None = None
        self.setMinimumHeight(170)

    def _hit_at(self, pos: QPointF):
        for rect, payload in reversed(self._hits):
            if rect.contains(pos):
                return payload
        return None

    def _tip(self, payload) -> str:            # alt sınıflar doldurur
        return ""

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        hit = self._hit_at(e.position())
        if hit is not self._hover:
            self._hover = hit
            self.update()
        if hit is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            QToolTip.showText(e.globalPosition().toPoint(), self._tip(hit), self)
        else:
            self.unsetCursor()
            QToolTip.hideText()

    def leaveEvent(self, _e) -> None:  # noqa: N802
        self._hover = None
        self.update()

    def _frame(self, p: QPainter) -> None:
        p.fillRect(self.rect(), QColor("#ffffff"))
        p.setPen(QPen(QColor("#cbd5e1")))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _empty(self, p: QPainter, text: str) -> None:
        p.setPen(QColor("#94a3b8"))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)


class TimelineBarChart(_ChartBase):
    run_clicked = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.runs: list[Run] = []
        self.setMinimumHeight(220)

    def set_runs(self, runs: list[Run]) -> None:
        self.runs = list(runs)
        self._hits = []
        self.update()

    def run_at(self, pos: QPointF) -> Run | None:
        self._layout_hits()
        return self._hit_at(pos)

    # ---- geometri -----------------------------------------------------------------------
    def _plot(self) -> QRectF:
        return QRectF(58, 34, max(10, self.width() - 58 - 12), max(10, self.height() - 34 - 30))

    def _scale(self) -> tuple[float, str, float]:
        m = max((r.bytes for r in self.runs), default=0)
        unit, div = ("GB", 1 << 30) if m >= (1 << 30) else ("MB", 1 << 20) if m >= (1 << 20) else ("KB", 1 << 10)
        top = _nice_ceiling(max(m / div, 0.001) * 1.08)
        return top, unit, div

    def _layout_hits(self) -> None:
        self._hits = []
        if not self.runs:
            return
        plot = self._plot()
        top, _u, div = self._scale()
        slot = plot.width() / len(self.runs)
        for i, r in enumerate(self.runs):
            w = (min(46.0, slot * 0.72) if r.mode == "full" else min(24.0, slot * 0.46)) if r.mode != "mirror" else min(40.0, slot * 0.6)
            h = plot.height() * (r.bytes / div) / top if r.bytes else 0
            if r.status == "error":
                h = max(h, plot.height() * 0.05)
            h = max(h, 3.0)
            x = plot.left() + slot * i + (slot - w) / 2
            self._hits.append((QRectF(x, plot.bottom() - h, w, h), r))

    def _tip(self, r: Run) -> str:
        satirlar = [f"<b>{r.start.strftime('%d.%m.%Y')}</b>", f"<b>Tür:</b> {_TUR.get(r.mode, r.mode)} — {r.job}",
                    f"<b>Tarih:</b> {r.start.strftime('%H:%M')} → {r.end.strftime('%H:%M')}", f"<b>Süre:</b> {format_duration(r.seconds)}",
                    f"<b>Boyut:</b> {format_size(r.bytes)}", f"<b>Durum:</b> {_DURUM.get(r.status, r.status)}"]
        if r.status in ("error", "warning") and r.message:
            satirlar.append(f"<i>{r.message[:160]}</i>")
        return "<br>".join(satirlar)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        hit = self._hit_at(e.position())
        if hit is not None:
            self.run_clicked.emit(hit)

    # ---- çizim --------------------------------------------------------------------------
    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._frame(p)
        f = QFont(self.font())
        f.setPointSize(8)
        p.setFont(f)
        if not self.runs:
            self._empty(p, "Bu aralıkta yedek çalışması yok")
            return
        self._layout_hits()
        plot = self._plot()
        top, unit, _div = self._scale()
        p.setPen(QPen(C_TEXT))
        for i in range(5):                                          # yatay ızgara + Y ekseni
            y = plot.bottom() - plot.height() * i / 4
            p.setPen(QPen(C_GRID))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QPen(C_TEXT))
            v = top * i / 4
            p.drawText(QRectF(0, y - 8, plot.left() - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{v:g} {unit}" if i else "0")
        fm = QFontMetrics(f)
        slot = plot.width() / len(self.runs)
        adim = max(1, math.ceil((fm.horizontalAdvance("00.00 00:00") + 6) / max(slot, 1)))
        for i, (rect, r) in enumerate(self._hits):
            renk = C_ERR if r.status == "error" else {"full": C_FULL, "inc": C_INC, "mirror": C_MIRROR}.get(r.mode, C_FULL)
            if r is self._hover:
                renk = renk.lighter(115)
            p.setPen(QPen(C_WARN, 2) if r.status == "warning" else Qt.PenStyle.NoPen)
            p.setBrush(QBrush(renk))
            p.drawRoundedRect(rect, 2, 2)
            if r.status == "error":                                # kırmızı uyarı işareti
                c = QPointF(rect.center().x(), rect.top() - 11)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(C_ERR))
                p.drawEllipse(c, 8, 8)
                p.setPen(QPen(QColor("white")))
                fb = QFont(f)
                fb.setBold(True)
                p.setFont(fb)
                p.drawText(QRectF(c.x() - 8, c.y() - 8, 16, 16), Qt.AlignmentFlag.AlignCenter, "!")
                p.setFont(f)
            if i % adim == 0:
                p.setPen(QPen(C_TEXT))
                etiket = r.start.strftime("%d.%m") + (r.start.strftime(" %H:%M") if (self.runs[-1].start - self.runs[0].start).days < 2 else "")
                p.drawText(QRectF(rect.center().x() - 34, plot.bottom() + 4, 68, 16), Qt.AlignmentFlag.AlignCenter, etiket)
        # gösterge
        x = plot.left() + plot.width() / 2 - 120
        for etiket, renk in (("Tam yedek", C_FULL), ("Artımlı", C_INC), ("Hata", C_ERR)):
            p.setBrush(QBrush(renk))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(x, 12, 11, 11))
            p.setPen(QPen(C_TEXT))
            p.drawText(QRectF(x + 15, 8, 80, 18), Qt.AlignmentFlag.AlignVCenter, etiket)
            x += 92


class DonutChart(_ChartBase):
    slice_clicked = pyqtSignal(str)
    RENK = {"last": QColor("#3b82f6"), "old": QColor("#93c5fd"), "other": QColor("#94a3b8"), "free": QColor("#22c55e")}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.slices: list[tuple[str, str, int]] = []
        self.center_text = ""
        self.setMinimumSize(230, 200)

    def set_slices(self, slices: list[tuple[str, str, int]], center_text: str = "") -> None:
        self.slices, self.center_text = list(slices), center_text
        self.update()

    def _geometry(self) -> tuple[QPointF, float, float]:
        side = min(self.width(), self.height() - 44)
        r = max(20.0, side / 2 - 8)
        return QPointF(self.width() / 2, 10 + r + 4), r, r * 0.58

    def slice_at(self, pos: QPointF) -> str | None:
        total = sum(v for _k, _l, v in self.slices)
        if total <= 0:
            return None
        c, r, ri = self._geometry()
        dx, dy = pos.x() - c.x(), pos.y() - c.y()
        d = math.hypot(dx, dy)
        if not (ri <= d <= r):
            return None
        ang = (math.degrees(math.atan2(dx, -dy)) + 360) % 360           # saat 12'den saat yönünde
        acc = 0.0
        for k, _l, v in self.slices:
            acc += 360 * v / total
            if ang <= acc:
                return k
        return self.slices[-1][0]

    def _tip(self, key: str) -> str:
        total = sum(v for _k, _l, v in self.slices) or 1
        for k, l, v in self.slices:
            if k == key:
                return f"<b>{l}</b><br>{format_size(v)} (%{v * 100 / total:.1f})" + ("<br><i>Tıklayınca dosyalar listelenir</i>" if k in ("last", "old") else "")
        return ""

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        k = self.slice_at(e.position())
        if k != self._hover:
            self._hover = k
            self.update()
        if k:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            QToolTip.showText(e.globalPosition().toPoint(), self._tip(k), self)
        else:
            self.unsetCursor()
            QToolTip.hideText()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        k = self.slice_at(e.position())
        if k:
            self.slice_clicked.emit(k)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._frame(p)
        total = sum(v for _k, _l, v in self.slices)
        if total <= 0:
            self._empty(p, "Hedef disk bilgisi yok")
            return
        c, r, ri = self._geometry()
        start = 90.0                                                     # saat 12'den başla
        for k, _l, v in self.slices:
            if v <= 0:
                continue
            span = -360.0 * v / total
            path = QPainterPath()
            path.arcMoveTo(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), start)
            path.arcTo(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), start, span)
            path.arcTo(QRectF(c.x() - ri, c.y() - ri, 2 * ri, 2 * ri), start + span, -span)
            path.closeSubpath()
            col = self.RENK.get(k, QColor("#64748b"))
            p.setPen(QPen(QColor("white"), 1.5))
            p.setBrush(QBrush(col.lighter(112) if k == self._hover else col))
            p.drawPath(path)
            start += span
        f = QFont(self.font())
        f.setBold(True)
        f.setPointSize(11)
        p.setFont(f)
        p.setPen(QPen(C_TEXT))
        p.drawText(QRectF(c.x() - ri, c.y() - 20, 2 * ri, 40), Qt.AlignmentFlag.AlignCenter, self.center_text)
        f.setBold(False)
        f.setPointSize(8)
        p.setFont(f)
        x = 10.0
        y = c.y() + r + 10
        for k, l, _v in self.slices:                                     # gösterge
            w = QFontMetrics(f).horizontalAdvance(l) + 22
            if x > 10.0 and x + w > self.width() - 6:                    # sığmıyorsa alt satıra sar (kutucuk da birlikte)
                x, y = 10.0, y + 16
            p.setBrush(QBrush(self.RENK.get(k, QColor("#64748b"))))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(x, y + 3, 9, 9))
            p.setPen(QPen(C_TEXT))
            p.drawText(QRectF(x + 13, y, w, 15), Qt.AlignmentFlag.AlignVCenter, l)
            x += w + 6


class LineChart(_ChartBase):
    run_clicked = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.runs: list[Run] = []

    def set_runs(self, runs: list[Run]) -> None:
        self.runs = [r for r in runs if r.seconds > 0 and r.ok]
        self.update()

    def _plot(self) -> QRectF:
        return QRectF(46, 30, max(10, self.width() - 46 - 46), max(10, self.height() - 30 - 26))

    def _points(self) -> tuple[list[tuple[QPointF, Run]], list[tuple[QPointF, Run]], float, float]:
        plot = self._plot()
        tmax = _nice_ceiling(max((r.seconds / 60 for r in self.runs), default=1) * 1.1)
        smax = _nice_ceiling(max((r.mbps for r in self.runs), default=1) * 1.1)
        n = len(self.runs)
        dur, spd = [], []
        for i, r in enumerate(self.runs):
            x = plot.left() + (plot.width() * (i + 0.5) / n)
            dur.append((QPointF(x, plot.bottom() - plot.height() * (r.seconds / 60) / tmax), r))
            spd.append((QPointF(x, plot.bottom() - plot.height() * r.mbps / smax), r))
        return dur, spd, tmax, smax

    def point_hits(self) -> list[tuple[QPointF, Run]]:
        dur, spd, _t, _s = self._points()
        return dur + spd

    def _tip(self, r: Run) -> str:
        return (f"<b>{r.start.strftime('%d.%m.%Y %H:%M')}</b> — {_TUR.get(r.mode, r.mode)}<br>Süre: {format_duration(r.seconds)}<br>"
                f"Hız: {r.mbps:.1f} MB/s<br>Boyut: {format_size(r.bytes)}")

    def _nearest(self, pos: QPointF) -> Run | None:
        best, bd = None, 14.0
        for pt, r in self.point_hits():
            d = math.hypot(pt.x() - pos.x(), pt.y() - pos.y())
            if d < bd:
                best, bd = r, d
        return best

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        r = self._nearest(e.position())
        if r is not self._hover:
            self._hover = r
            self.update()
        if r:
            QToolTip.showText(e.globalPosition().toPoint(), self._tip(r), self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        r = self._nearest(e.position())
        if r:
            self.run_clicked.emit(r)

    def paintEvent(self, _e) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._frame(p)
        f = QFont(self.font())
        f.setPointSize(8)
        p.setFont(f)
        if len(self.runs) < 1:
            self._empty(p, "Süre/hız trendi için başarılı yedek gerekli")
            return
        plot = self._plot()
        dur, spd, tmax, smax = self._points()
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            p.setPen(QPen(C_GRID))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QPen(C_FULL))
            p.drawText(QRectF(0, y - 8, plot.left() - 5, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{tmax * i / 4:g}")
            p.setPen(QPen(C_WARN))
            p.drawText(QRectF(plot.right() + 5, y - 8, 40, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{smax * i / 4:g}")
        for serie, renk in ((dur, C_FULL), (spd, C_WARN)):
            p.setPen(QPen(renk, 2))
            for (a, _r1), (b, _r2) in zip(serie, serie[1:]):
                p.drawLine(a, b)
            p.setBrush(QBrush(renk))
            for pt, r in serie:
                p.drawEllipse(pt, 5 if r is self._hover else 3.5, 5 if r is self._hover else 3.5)
        p.setPen(QPen(C_FULL))
        p.drawText(QRectF(plot.left(), 6, 120, 16), Qt.AlignmentFlag.AlignVCenter, "● Süre (dk)")
        p.setPen(QPen(C_WARN))
        p.drawText(QRectF(plot.left() + 110, 6, 140, 16), Qt.AlignmentFlag.AlignVCenter, "● Hız (MB/s)")
        p.setPen(QPen(C_TEXT))
        n = len(self.runs)
        adim = max(1, math.ceil(n / 8))
        for i, r in enumerate(self.runs):
            if i % adim == 0:
                p.drawText(QRectF(dur[i][0].x() - 30, plot.bottom() + 5, 60, 16), Qt.AlignmentFlag.AlignCenter, r.start.strftime("%d.%m"))
