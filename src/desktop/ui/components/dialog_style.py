"""Ortak açık-tema diyalog stili.

Uygulama genelinde bir palet tanımlı olmadığından, Windows koyu modundayken
`QDialog` siyah zemin + okunmaz yazıyla açılıyordu. Diyaloglar bu stili
uygulayarak programın açık renk şemasıyla (slate/mavi) uyumlu görünür.
"""

from PyQt6.QtWidgets import QWidget

LIGHT_DIALOG_QSS = """
QDialog, QMessageBox { background-color: #f8fafc; color: #1e293b; }
QLabel { color: #1e293b; background: transparent; }
QLineEdit, QComboBox, QListWidget, QTextEdit, QSpinBox, QDateEdit {
    background-color: #ffffff; color: #1e293b;
    border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px;
    selection-background-color: #bfdbfe; selection-color: #0f172a;
}
QListWidget::item { padding: 4px 6px; }
QListWidget::item:selected { background-color: #dbeafe; color: #1e3a8a; }
QComboBox QAbstractItemView {
    background-color: #ffffff; color: #1e293b; selection-background-color: #dbeafe;
}
QPushButton {
    background-color: #ffffff; color: #1e293b;
    border: 1px solid #cbd5e1; border-radius: 4px; padding: 5px 12px; font-weight: 600;
}
QPushButton:hover { background-color: #eff6ff; border-color: #93c5fd; }
QPushButton:pressed { background-color: #dbeafe; }
QPushButton:default { background-color: #2563eb; color: #ffffff; border-color: #1d4ed8; }
"""


def apply_light_dialog_style(dialog: QWidget) -> None:
    dialog.setStyleSheet(LIGHT_DIALOG_QSS)
