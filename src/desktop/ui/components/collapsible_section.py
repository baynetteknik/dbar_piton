"""Açılır / Kapanır (Accordion / Collapsible) Panel Bölümü Bileşeni.

Modern ERP panelleri için sol ve sağ menülerde grupları + / - simgeleriyle
genişletip daraltmayı sağlar.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class CollapsibleSection(QWidget):
    """Açılır/kapanır başlık ve alt içerik çerçevesine sahip akordiyon bileşeni."""

    toggled = pyqtSignal(bool)

    def __init__(self, title: str, is_expanded: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.title_text = title
        self.is_expanded = is_expanded

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 4)
        main_layout.setSpacing(0)

        # Başlık Butonu
        self.header_btn = QPushButton()
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.clicked.connect(self.toggle)
        main_layout.addWidget(self.header_btn)

        # Gövde Çerçevesi
        self.content_frame = QFrame()
        self.content_frame.setObjectName("CollapsibleContentFrame")
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(6, 8, 6, 8)
        self.content_layout.setSpacing(5)
        main_layout.addWidget(self.content_frame)

        self.update_style()
        self.content_frame.setVisible(self.is_expanded)

    def update_style(self):
        icon = "➖" if self.is_expanded else "➕"
        self.header_btn.setText(f"{icon}  {self.title_text}")

        if self.is_expanded:
            self.header_btn.setStyleSheet("""
                QPushButton {
                    background-color: #e0e7ff;
                    color: #1e3a8a;
                    font-weight: 800;
                    font-size: 11px;
                    font-family: 'Segoe UI';
                    text-align: left;
                    padding: 8px 10px;
                    border: 1px solid #cbd5e1;
                    border-bottom: none;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                    border-bottom-left-radius: 0px;
                    border-bottom-right-radius: 0px;
                }
                QPushButton:hover {
                    background-color: #c7d2fe;
                }
            """)
            self.content_frame.setStyleSheet("""
                QFrame#CollapsibleContentFrame {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-top: none;
                    border-bottom-left-radius: 6px;
                    border-bottom-right-radius: 6px;
                }
            """)
        else:
            self.header_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f8fafc;
                    color: #334155;
                    font-weight: 700;
                    font-size: 11px;
                    font-family: 'Segoe UI';
                    text-align: left;
                    padding: 8px 10px;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                    border-color: #94a3b8;
                }
            """)

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.content_frame.setVisible(self.is_expanded)
        self.update_style()
        self.toggled.emit(self.is_expanded)

    def add_widget(self, widget: QWidget):
        """İçerik alanına yeni bir bileşen ekler."""
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        """İçerik alanına yeni bir layout ekler."""
        self.content_layout.addLayout(layout)
