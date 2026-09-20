"""
TOYA ERP - İpucu (Tooltip) Görünümü: mavi zemin, beyaz yazı

Qt'de kendi stil sayfası olan bir widget'ın ipucu penceresi, uygulama düzeyindeki `QToolTip` kuralını KAYBEDİP siyah
zeminle çizilir. Bu yüzden kural hem uygulama düzeyinde (qt_material'ınkinden SONRA) hem de ipucu taşıyan
widget'ların kendi stil sayfalarında bulunmalıdır: `with_tooltip(css)` bunu ekler.
(border-radius kullanılmaz: Windows'ta ipucu zeminini siyah çizdirir.)
"""

from __future__ import annotations

QSS = ("QToolTip { background-color:#2563eb; color:#ffffff; border:1px solid #1d4ed8; border-radius:0px;"
       " padding:5px 8px; font-size:12px; }")
_MARK = "/*toya-tooltip*/"


def with_tooltip(css: str) -> str:
    """Bir widget stil sayfasına ipucu kuralını ekler (zaten varsa dokunmaz)."""
    return css if _MARK in css else f"{css}\n{_MARK}{QSS}"


def apply_app_style() -> None:
    """Uygulama düzeyinde bir kez ekler (qt_material'ın QToolTip kuralından sonra gelir)."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None and _MARK not in app.styleSheet():
        app.setStyleSheet(f"{app.styleSheet()}\n{_MARK}{QSS}")
