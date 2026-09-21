"""Ortak açık-tema diyalog stili.

Uygulama genelinde bir palet tanımlı olmadığından, Windows koyu modundayken
`QDialog` siyah zemin + okunmaz yazıyla açılıyordu. Diyaloglar bu stili
uygulayarak programın açık renk şemasıyla (slate/mavi) uyumlu görünür.

Düğmeler kenar çubuğundaki düğmelerle aynıdır: alt kenarı kalın (derinlikli), üzerine gelince mavimsi, basınca
çöker. Varsayılan (birincil) düğme mavi zemin + beyaz yazıdır. İpuçları mavi zemin + beyaz yazıdır.
"""

from PyQt6.QtWidgets import QWidget

from src.desktop.ui.components.tooltip_style import with_tooltip

LIGHT_DIALOG_QSS = with_tooltip("""
QDialog, QMessageBox { background-color: #f8fafc; color: #1e293b; }
QLabel { color: #1e293b; background: transparent; }
QCheckBox, QRadioButton { color: #1e293b; background: transparent; }
QGroupBox { color: #1e293b; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 10px; padding-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #1e3a8a; font-weight: 700; }
QLineEdit, QComboBox, QListWidget, QTextEdit, QPlainTextEdit, QSpinBox, QDateEdit, QTimeEdit {
    background-color: #ffffff; color: #1e293b;
    border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px;
    selection-background-color: #bfdbfe; selection-color: #0f172a;
}
QListWidget::item { padding: 4px 6px; }
QListWidget::item:selected { background-color: #dbeafe; color: #1e3a8a; }
QComboBox QAbstractItemView {
    background-color: #ffffff; color: #1e293b; selection-background-color: #dbeafe;
}
QTabWidget::pane { border: 1px solid #cbd5e1; background: #ffffff; border-radius: 4px; }
QTabBar::tab { background: #e2e8f0; color: #334155; padding: 6px 14px; border: 1px solid #cbd5e1; border-bottom: none;
               border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; font-weight: 600; }
QTabBar::tab:selected { background: #2563eb; color: #ffffff; border-color: #1d4ed8; }
QTabBar::tab:hover:!selected { background: #dbeafe; color: #1d4ed8; }
QPushButton {
    background-color: #ffffff; color: #1e293b;
    border: 1px solid #94a3b8; border-bottom: 3px solid #94a3b8; border-radius: 6px;
    padding: 5px 14px; font-weight: 600; min-height: 22px;
}
QPushButton:hover { background-color: #eff6ff; border-color: #60a5fa; border-bottom-color: #2563eb; color: #1d4ed8; }
QPushButton:pressed { border-bottom: 1px solid #94a3b8; padding-top: 7px; }
QPushButton:disabled { color: #94a3b8; background-color: #f1f5f9; border-color: #e2e8f0; }
QPushButton:default { background-color: #2563eb; color: #ffffff; border: 1px solid #1d4ed8; border-bottom: 3px solid #1e40af; }
QPushButton:default:hover { background-color: #1d4ed8; color: #ffffff; }
""")


def apply_light_dialog_style(dialog: QWidget) -> None:
    dialog.setStyleSheet(LIGHT_DIALOG_QSS)
