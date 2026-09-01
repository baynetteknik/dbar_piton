"""
TOYA ERP - Edge-Triggered & Boyutlandırılabilir Yan Panel (EdgeTriggeredPanel)
Sol ve Sağ kenar panellerinin açılıp kapanmasını, sabitlenmesini ve
kullanıcı tarafından genişliğinin (eninin) ayarlanıp QSettings'te kalıcı olarak saklanmasını sağlar.
"""

import logging
from PyQt6.QtCore import QEvent, Qt, pyqtSignal, QSettings
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QPushButton, QVBoxLayout, 
    QWidget, QLabel, QSizeGrip
)

logger = logging.getLogger(__name__)


class EdgeTriggeredPanel(QWidget):
    """Açılır/Kapanır, Sabitlenebilir ve Eni Ayarlanabilir (Persistent Width) Yan Panel."""

    pinned_changed = pyqtSignal(bool)
    opened_changed = pyqtSignal(bool)
    width_changed = pyqtSignal(int)

    def __init__(self, side="left", default_width=240, parent=None):
        super().__init__(parent)
        self.side = side  # "left" veya "right"
        self.settings = QSettings("ToyaERP", "SidebarSettings")
        
        # En (Genişlik) Ayarı QSettings'ten yüklenir
        saved_width = int(self.settings.value(f"sidebar/{self.side}_width", default_width))
        self.panel_width = max(180, min(500, saved_width))
        
        self.is_pinned = False
        self.is_open = False
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

        # Başlık ve Boyutlandırma Kontrolleri
        self.header_widget = QWidget()
        header_lyt = QHBoxLayout(self.header_widget)
        header_lyt.setContentsMargins(2, 2, 2, 2)
        header_lyt.setSpacing(4)

        btn_style = """
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                color: #475569;
                padding: 2px 5px;
            }
            QPushButton:hover { background-color: #f1f5f9; color: #0f172a; }
        """

        self.pin_btn = QPushButton("📌 Sabitle")
        self.pin_btn.setFixedHeight(24)
        self.pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_btn.setStyleSheet(btn_style)
        self.pin_btn.clicked.connect(self.toggle_pin)
        header_lyt.addWidget(self.pin_btn)

        # Genişlet / Daralt En Butonları
        btn_w_minus = QPushButton("◀ En -")
        btn_w_minus.setFixedHeight(24)
        btn_w_minus.setStyleSheet(btn_style)
        btn_w_minus.setToolTip("Genişliği 30px Daralt")
        btn_w_minus.clicked.connect(lambda: self.adjust_panel_width(-30))

        btn_w_plus = QPushButton("+ En ▶")
        btn_w_plus.setFixedHeight(24)
        btn_w_plus.setStyleSheet(btn_style)
        btn_w_plus.setToolTip("Genişliği 30px Arttır")
        btn_w_plus.clicked.connect(lambda: self.adjust_panel_width(30))

        header_lyt.addWidget(btn_w_minus)
        header_lyt.addWidget(btn_w_plus)
        header_lyt.addStretch()

        self.close_btn = QPushButton("❌")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                color: #ef4444;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #fee2e2; }
        """)
        self.close_btn.clicked.connect(self.close_panel)
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

    def adjust_panel_width(self, delta: int):
        """Genişliği artırır/azaltır ve QSettings'e kaydeder."""
        new_w = max(180, min(550, self.panel_width + delta))
        self.set_panel_width(new_w)

    def set_panel_width(self, width: int):
        """Paneli belirli bir genişliğe ayarlar ve kalıcı kaydeder."""
        self.panel_width = max(180, min(550, width))
        self.panel_frame.setFixedWidth(self.panel_width)
        self.settings.setValue(f"sidebar/{self.side}_width", self.panel_width)
        self.update_position()
        self.width_changed.emit(self.panel_width)

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
            self.pin_btn.setText("📍 Serbest")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3b82f6;
                    border: 1px solid #1d4ed8;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                    color: white;
                    padding: 2px 6px;
                }
                QPushButton:hover { background-color: #2563eb; }
            """)
        else:
            self.pin_btn.setText("📌 Sabitle")
            self.pin_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: bold;
                    color: #475569;
                    padding: 2px 6px;
                }
                QPushButton:hover { background-color: #f1f5f9; color: #0f172a; }
            """)
        self.pinned_changed.emit(self.is_pinned)
        self.update_position()

    def update_position(self):
        parent = self.parentWidget()
        if not parent or self.is_pinned:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setGeometry(self.geometry())
            return

        parent_height = parent.height()
        parent_width = parent.width()
        w = self.panel_width + 14 if self.is_open else 14

        self.raise_()

        if self.side == "left":
            self.setGeometry(0, 0, w, parent_height)
        else:
            self.setGeometry(parent_width - w, 0, w, parent_height)

    def eventFilter(self, obj, event):  # noqa: N802
        if obj == self.parentWidget() and event.type() == QEvent.Type.Resize:
            self.update_position()
        return super().eventFilter(obj, event)
