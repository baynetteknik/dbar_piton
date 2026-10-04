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
#: Boş alan (placeholder) yazısı açık zeminde okunur olsun (varsayılan tema çok açık gri çiziyordu).
PLACEHOLDER_QSS = "QLineEdit, QPlainTextEdit, QTextEdit { placeholder-text-color: #64748b; }"

#: Hazır (statik) diyaloglar — QMessageBox / QInputDialog — hangi pencereden açılırsa açılsın açık zeminde okunur olsun.
#: Diyalog, üst widget'ının stil sayfasını (ör. sol panelin `background-color: transparent`ı) miras alıp siyah zeminle açılabiliyordu;
#: tür seçicili bu kurallar `*` gibi seçicisiz miras kurallarından daha özgüldür ve onları ezer.
DIALOG_QSS = (
    "QDialog, QMessageBox, QInputDialog { background-color: #f8fafc; color: #1e293b; }"
    " QMessageBox QLabel, QInputDialog QLabel { color: #1e293b; background: transparent; }"
    " QInputDialog QLineEdit, QInputDialog QComboBox, QInputDialog QSpinBox, QInputDialog QDoubleSpinBox {"
    " combobox-popup: 0; background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; }"
    " QInputDialog QComboBox QAbstractItemView { outline: 0; padding: 0px; border: 1px solid #cbd5e1; background-color: #ffffff; color: #1e293b; }"
    " QInputDialog QComboBox QAbstractItemView::item { padding: 3px 6px; min-height: 20px; }"
    " QMessageBox QPushButton, QInputDialog QPushButton { background-color: #ffffff; color: #1e293b; border: 1px solid #94a3b8;"
    " border-bottom: 3px solid #94a3b8; border-radius: 6px; padding: 5px 14px; font-weight: 600; min-height: 22px; }"
    " QMessageBox QPushButton:hover, QInputDialog QPushButton:hover { background-color: #eff6ff; color: #1d4ed8; }"
    " QMessageBox QPushButton:default, QInputDialog QPushButton:default { background-color: #2563eb; color: #ffffff;"
    " border: 1px solid #1d4ed8; border-bottom: 3px solid #1e40af; }"
)
_MARK = "/*toya-tooltip*/"


def with_tooltip(css: str) -> str:
    """Bir widget stil sayfasına ipucu kuralını ekler (zaten varsa dokunmaz)."""
    return css if _MARK in css else f"{css}\n{_MARK}{QSS}"


def apply_app_style() -> None:
    """Uygulama düzeyinde bir kez ekler (qt_material'ın QToolTip kuralından sonra gelir)."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None and _MARK not in app.styleSheet():
        app.setStyleSheet(f"{app.styleSheet()}\n{_MARK}{QSS}\n{PLACEHOLDER_QSS}\n{DIALOG_QSS}")
