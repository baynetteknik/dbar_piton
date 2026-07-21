import logging

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class EdgeTriggeredPanel(QWidget):
    """Chrome Remote Desktop tarzı Edge-Triggered (Overlay/Dock) Yan Panel."""

    pinned_changed = pyqtSignal(bool)
    opened_changed = pyqtSignal(bool)

    def __init__(self, side="left", parent=None):
        super().__init__(parent)
        self.side = side  # "left" veya "right"
        self.is_pinned = False
        self.is_open = False
        self.panel_width = 220
        self.content_widget = None

        self.setObjectName(f"EdgePanel_{self.side}")
        self.init_ui()

        if parent:
            parent.installEventFilter(self)

    def init_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Tetikleme Şeridi (Trigger Strip)
        self.trigger_strip = QPushButton()
        self.trigger_strip.setObjectName(f"TriggerStrip_{self.side}")
        self.trigger_strip.setFixedWidth(14)
        self.trigger_strip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_trigger_strip_icon()

        strip_style = """
            QPushButton {
                background-color: #e2e8f0;
                border: 1px solid #cbd5e1;
                color: #475569;
                font-weight: bold;
                font-size: 9px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #cbd5e1;
            }
        """
        self.trigger_strip.setStyleSheet(strip_style)
        self.trigger_strip.clicked.connect(self.toggle_panel)

        # 2. İçerik Kutusu (Panel Frame)
        self.panel_frame = QFrame()
        self.panel_frame.setObjectName(f"PanelFrame_{self.side}")
        self.panel_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
            }
        """)
        self.panel_frame.setFixedWidth(self.panel_width)

        self.panel_layout = QVBoxLayout(self.panel_frame)
        self.panel_layout.setContentsMargins(5, 5, 5, 5)
        self.panel_layout.setSpacing(6)

        # Raptiye ve Kapatma Butonları (Header)
        self.header_widget = QWidget()
        header_lyt = QHBoxLayout(self.header_widget)
        header_lyt.setContentsMargins(2, 2, 2, 2)
        header_lyt.setSpacing(4)

        self.pin_btn = QPushButton("📌")
        self.pin_btn.setObjectName(f"PinBtn_{self.side}")
        self.pin_btn.setFixedSize(24, 24)
        self.pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_btn.setToolTip("Paneli Sabitle")
        self.pin_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #f1f5f9; }
        """)
        self.pin_btn.clicked.connect(self.toggle_pin)

        self.close_btn = QPushButton("❌")
        self.close_btn.setObjectName(f"CloseBtn_{self.side}")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Paneli Kapat")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 9px;
            }
            QPushButton:hover { background-color: #fee2e2; color: #ef4444; }
        """)
        self.close_btn.clicked.connect(self.close_panel)

        header_lyt.addWidget(self.pin_btn)
        header_lyt.addStretch()
        header_lyt.addWidget(self.close_btn)
        self.panel_layout.addWidget(self.header_widget)

        # Başlangıç Durumu: Kapalı
        self.panel_frame.hide()

        # Layout Yerleşimi
        if self.side == "left":
            self.main_layout.addWidget(self.panel_frame)
            self.main_layout.addWidget(self.trigger_strip)
        else:
            self.main_layout.addWidget(self.trigger_strip)
            self.main_layout.addWidget(self.panel_frame)

    def set_content(self, widget):
        """Panelin içine asıl form veya buton widget'ını yerleştirir."""
        if self.content_widget:
            self.panel_layout.removeWidget(self.content_widget)
            self.content_widget.deleteLater()

        self.content_widget = widget
        self.panel_layout.addWidget(self.content_widget, 1)

    def update_trigger_strip_icon(self):
        if self.side == "left":
            self.trigger_strip.setText("▶" if not self.is_open else "◀")
        else:
            self.trigger_strip.setText("◀" if not self.is_open else "▶")

    def toggle_panel(self):
        if self.is_open:
            self.close_panel()
        else:
            self.open_panel()

    def open_panel(self):
        self.is_open = True
        self.panel_frame.show()
        self.update_trigger_strip_icon()
        self.update_position()
        self.opened_changed.emit(True)

    def close_panel(self):
        self.is_open = False
        self.panel_frame.hide()
        self.update_trigger_strip_icon()
        self.update_position()
        self.opened_changed.emit(False)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.pin_btn.setToolTip("Sabitlemeyi Kaldır")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    border: 1px solid #1d4ed8;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #2563eb; }
            """)
        else:
            self.pin_btn.setToolTip("Paneli Sabitle")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #f1f5f9; }
            """)
        self.pinned_changed.emit(self.is_pinned)
        self.update_position()

    def update_position(self):
        """Eğer sabit (pinned) değilse overlay olarak parent üzerinde konumlandırır."""
        parent = self.parentWidget()
        if not parent or self.is_pinned:
            # Sabitlendiyse normal layout akışına girmesi için boyut sınırlamalarını kaldır/güncelle
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setGeometry(self.geometry())  # Layout'un yönetmesine izin ver
            return

        # Overlay modunda parent üzerindeki koordinatları ayarla
        parent_height = parent.height()
        parent_width = parent.width()
        w = self.panel_width + 14 if self.is_open else 14

        self.raise_()  # Tablonun üstüne çıkarmak için raise et

        if self.side == "left":
            self.setGeometry(0, 0, w, parent_height)
        else:
            self.setGeometry(parent_width - w, 0, w, parent_height)

    def eventFilter(self, obj, event):  # noqa: N802
        """Parent widget yeniden boyutlandığında overlay panelinin konumunu günceller."""
        if obj == self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.update_position()
        return super().eventFilter(obj, event)
