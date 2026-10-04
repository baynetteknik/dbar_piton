"""TOYA ERP - Uygulama geneli ipucu (tooltip) yöneticisi: her pencerede, her gridde ipuçları okunur.

Sorun: Qt'nin kendi ipucu penceresi, ipucunu gösteren widget'ın (ya da üst widget'ların) stil sayfasından ve temadan renk alır;
kendi QSS'i olan bir pencerede siyah zemin + siyah yazı (ya da açık zemin + açık yazı) çıkabiliyor. Ekran ekran `with_tooltip`
eklemek bunu kalıcı çözmez.

Çözüm: `TooltipManager`, uygulama düzeyinde `QEvent.ToolTip` olaylarını yakalar ve ipucunu KENDİ stil sayfası sabit bir pencerede
gösterir (lacivert zemin, beyaz yazı) — temadan ve widget stillerinden bağımsız. Şunları kapsar: normal widget ipuçları,
tablo/liste hücreleri (`ToolTipRole`), tablo başlıkları, sekmeler, menü eylemleri ve `QToolTip.showText` çağrıları."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QLabel,
    QMenu,
    QTabBar,
    QToolTip,
    QWidget,
)

STYLE = ("QLabel { background-color:#1e3a8a; color:#ffffff; border:1px solid #93c5fd; padding:6px 10px;"
         " font-size:12px; font-family:'Segoe UI', sans-serif; }")
MAX_WIDTH = 460
HIDE_MS = 9000

_HIDE_EVENTS = {
    QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.KeyPress,
    QEvent.Type.Wheel, QEvent.Type.WindowDeactivate,
}


class _TipLabel(QLabel):
    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setObjectName("ToyaTooltip")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setTextFormat(Qt.TextFormat.AutoText)
        self.setWordWrap(True)
        self.setStyleSheet(STYLE)
        self.setMaximumWidth(MAX_WIDTH)


class TooltipManager(QObject):
    _instance: TooltipManager | None = None

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.label = _TipLabel()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    # ---- kurulum -----------------------------------------------------------------
    @classmethod
    def install(cls, app: QApplication | None = None) -> TooltipManager:
        app = app or QApplication.instance()
        if cls._instance is None:
            cls._instance = cls(app)
            app.installEventFilter(cls._instance)
            cls._orijinal = (QToolTip.showText, QToolTip.hideText)
            QToolTip.showText = staticmethod(cls._instance._show_text)        # doğrudan QToolTip.showText çağıranlar da aynı pencereyi kullanır
            QToolTip.hideText = staticmethod(lambda: cls._instance.hide())
        return cls._instance

    @classmethod
    def uninstall(cls) -> None:
        """Süzgeci kaldırır ve QToolTip'i eski haline getirir (testler için)."""
        if cls._instance is None:
            return
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(cls._instance)
        QToolTip.showText, QToolTip.hideText = cls._orijinal
        cls._instance.hide()
        cls._instance = None

    # ---- gösterim ----------------------------------------------------------------
    def show(self, text: str, global_pos: QPoint) -> None:
        self.label.setText(text)
        self.label.adjustSize()
        size = self.label.sizeHint()
        pos = global_pos + QPoint(14, 20)
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        if screen is not None:
            g = screen.availableGeometry()
            pos.setX(max(g.left(), min(pos.x(), g.right() - size.width())))
            if pos.y() + size.height() > g.bottom():
                pos.setY(global_pos.y() - size.height() - 8)
        self.label.move(pos)
        self.label.show()
        self.label.raise_()
        self._timer.start(HIDE_MS)

    def hide(self) -> None:
        self._timer.stop()
        if self.label.isVisible():
            self.label.hide()

    def _show_text(self, pos: QPoint, text: str, widget: QWidget | None = None, rect: QRect = QRect(), msec: int = -1) -> None:
        if text:
            self.show(text, pos)
        else:
            self.hide()

    # ---- olay süzgeci ------------------------------------------------------------
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        t = event.type()
        if t == QEvent.Type.ToolTip and isinstance(obj, QWidget):
            text = self.text_for(obj, event.pos())
            if text:
                self.show(text, event.globalPos())
                return True
            return False                                  # Qt olayı üst widget'a iletir; oradan ipucu gelebilir
        if t in _HIDE_EVENTS and obj is not self.label and self.label.isVisible():
            self.hide()
        return False

    @staticmethod
    def text_for(w: QWidget, pos: QPoint) -> str:
        """Fare konumundaki öğenin ipucu metni (boşsa '')."""
        parent = w.parent()
        if isinstance(parent, QHeaderView) and w is parent.viewport():
            sec = parent.logicalIndexAt(pos)
            m = parent.model()
            if m is not None and sec >= 0:
                return str(m.headerData(sec, parent.orientation(), Qt.ItemDataRole.ToolTipRole) or "")
            return ""
        if isinstance(parent, QAbstractItemView) and w is parent.viewport():
            idx = parent.indexAt(pos)
            return str(idx.data(Qt.ItemDataRole.ToolTipRole) or "") if idx.isValid() else ""
        if isinstance(w, QTabBar):
            i = w.tabAt(pos)
            return w.tabToolTip(i) if i >= 0 else ""
        if isinstance(w, QMenu):
            a = w.actionAt(pos)
            if a is not None and a.toolTip() and a.toolTip().replace("&", "") != a.text().replace("&", ""):
                return a.toolTip()
            return ""
        return w.toolTip() or ""
