"""
TOYA ERP - Atomik Hızlı Erişim ve Durum Kartları Bandı Widget'ı (QuickTilesBarWidget)
Footer'ın hemen üzerinde yer alan, Açılır/Kapanır (Collapsible),
yüksek kontrastlı, net okunabilir, kurumsal renkli mini durum ve metrik kartları bileşeni.
"""

from typing import List, Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame, QScrollArea, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QColor, QFont


class QuickTileButton(QPushButton):
    """Yüksek kontrastlı, renkli ikon rozetine sahip kurumsal mini durum kartı."""

    def __init__(self, title: str, value: str = "", icon: str = "🔹", 
                 accent_color: str = "#2563eb", badge_bg: str = "#eff6ff", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(50)
        self.setMinimumWidth(135)

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: #f8fafc;
                border-color: {accent_color};
            }}
            QPushButton:pressed {{
                background-color: #f1f5f9;
            }}
        """)

        lyt = QHBoxLayout(self)
        lyt.setContentsMargins(8, 4, 8, 4)
        lyt.setSpacing(8)

        # Renkli İkon Rozeti (Icon Badge)
        lbl_icon_badge = QLabel(icon)
        lbl_icon_badge.setFixedSize(32, 32)
        lbl_icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon_badge.setFont(QFont("Segoe UI", 14))
        lbl_icon_badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {accent_color};
            border-radius: 6px;
            border: 1px solid #e2e8f0;
        """)
        lbl_icon_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        lyt.addWidget(lbl_icon_badge)

        # Metin Alanı: Başlık + Değer / Tutar
        text_box = QVBoxLayout()
        text_box.setSpacing(1)
        text_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; font-family: 'Segoe UI';")
        lbl_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        text_box.addWidget(lbl_title)

        if value:
            lbl_value = QLabel(value)
            lbl_value.setStyleSheet(f"font-size: 12px; font-weight: 800; color: #0f172a; font-family: 'Segoe UI';")
            lbl_value.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            text_box.addWidget(lbl_value)

        lyt.addLayout(text_box)

        # Hafif Kart Gölgesi
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(6)
        shadow.setColor(QColor(0, 0, 0, 8))
        shadow.setOffset(0, 1)
        self.setGraphicsEffect(shadow)


class QuickTilesBarWidget(QWidget):
    """Footer üstü açılır/kapanır (Collapsible) yüksek kontrastlı hızlı erişim paneli."""

    tile_clicked = pyqtSignal(str)
    collapsed_state_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("ToyaERP", "DashboardSettings")
        self.is_collapsed = self.settings.value("dashboard/quick_tiles_collapsed", False, type=bool)
        self._init_ui()

    def _init_ui(self):
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(8, 2, 8, 2)
        main_lyt.setSpacing(2)

        # Üst Başlık & Açılır/Kapanır Çubuğu
        header_bar = QFrame()
        header_bar.setFixedHeight(28)
        header_bar.setStyleSheet("""
            QFrame {
                background-color: #1e3a8a;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                border: 1px solid #1d4ed8;
            }
        """)
        h_lyt = QHBoxLayout(header_bar)
        h_lyt.setContentsMargins(10, 2, 10, 2)

        lbl_title = QLabel("⚡ HIZLI DURUM VE KISAYOL KARTLARI")
        lbl_title.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: 800; font-family: 'Segoe UI';")
        h_lyt.addWidget(lbl_title)
        h_lyt.addStretch()

        self.btn_toggle = QPushButton("▼ Gizle" if not self.is_collapsed else "▲ Göster")
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 8px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_toggle.clicked.connect(self.toggle_collapse)
        h_lyt.addWidget(self.btn_toggle)

        main_lyt.addWidget(header_bar)

        # Kartlar İçerik Alanı
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet("""
            QFrame#content_frame {
                background-color: #f1f5f9;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                border: 1px solid #cbd5e1;
                border-top: none;
            }
        """)
        self.content_frame.setObjectName("content_frame")

        content_lyt = QVBoxLayout(self.content_frame)
        content_lyt.setContentsMargins(6, 6, 6, 6)
        content_lyt.setSpacing(6)

        # 1. Satır Kısayolları (Scrollable Container)
        row1_scroll = QScrollArea()
        row1_scroll.setFixedHeight(58)
        row1_scroll.setWidgetResizable(True)
        row1_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        row1_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        row1_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        row1_w = QWidget()
        row1_w.setStyleSheet("background: transparent;")
        row1_lyt = QHBoxLayout(row1_w)
        row1_lyt.setContentsMargins(0, 0, 0, 0)
        row1_lyt.setSpacing(8)

        # Renkli, okunaklı ve net kart tanımları
        tiles_data = [
            ("Cari Bakiye", "₺ 125.450", "👥", "#2563eb", "#dbeafe"),
            ("Bugün Ciro", "₺ 48.200", "💰", "#16a34a", "#dcfce7"),
            ("Bekleyen Sipariş", "12 Adet", "📦", "#d97706", "#fef3c7"),
            ("Açık Teklifler", "8 Adet", "📄", "#9333ea", "#f3e8ff"),
            ("Kasa Durumu", "₺ 89.200", "🏦", "#0d9488", "#ccfbf1"),
            ("Stok Uyarısı", "3 Kritik", "⚠️", "#dc2626", "#fee2e2"),
            ("Aktif Görevler", "5 Görev", "🔄", "#0284c7", "#e0f2fe"),
            ("Hızlı Fatura", "Yeni Evrak", "➕", "#4f46e5", "#e0e7ff"),
        ]

        for title, val, icon, color, bg in tiles_data:
            btn = QuickTileButton(title, val, icon, accent_color=color, badge_bg=bg)
            btn.clicked.connect(lambda chk, t=title: self.tile_clicked.emit(t))
            row1_lyt.addWidget(btn)

        row1_lyt.addStretch()
        row1_scroll.setWidget(row1_w)
        content_lyt.addWidget(row1_scroll)

        main_lyt.addWidget(self.content_frame)
        self._apply_collapse_state()

    def toggle_collapse(self):
        """Açılır / kapanır durumunu değiştirir ve kaydeder."""
        self.is_collapsed = not self.is_collapsed
        self.settings.setValue("dashboard/quick_tiles_collapsed", self.is_collapsed)
        self._apply_collapse_state()
        self.collapsed_state_changed.emit(self.is_collapsed)

    def _apply_collapse_state(self):
        self.content_frame.setVisible(not self.is_collapsed)
        self.btn_toggle.setText("▲ Göster" if self.is_collapsed else "▼ Gizle")
