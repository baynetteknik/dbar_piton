"""
TOYA ERP - Atomik Son İşlemler Şeridi Widget'ı (RecentActivityWidget)
"Hızlı Durum ve Kısayol Kartları" (QuickTilesBarWidget) ile aynı görsel dilde,
kart giriş ekranlarının (Cari Kartı, Stok Kartı) alt tarafına gömülebilen,
salt-okunur "son yapılan işlemler" (giriş/çıkış) özet şeridi.
"""

from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea,
)
from PyQt6.QtCore import Qt

from src.desktop.ui.widgets.quick_tiles_bar_widget import QuickTileButton


class RecentActivityWidget(QWidget):
    """Kart giriş ekranlarının altında son işlemleri (giriş/çıkış) listeleyen şerit.

    Veri kaynağından bağımsızdır: ekran, `set_items()` ile hazır bir kart listesi verir.
    Her öğe: {"title": str, "value": str, "icon": str, "accent": "#hex", "badge_bg": "#hex"}.
    """

    def __init__(self, title: str = "SON İŞLEMLER", parent=None):
        super().__init__(parent)
        self._init_ui(title)

    def _init_ui(self, title: str) -> None:
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(0, 0, 0, 0)
        main_lyt.setSpacing(0)

        header_bar = QFrame()
        header_bar.setFixedHeight(26)
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
        lbl_title = QLabel(f"⚡ {title}")
        lbl_title.setStyleSheet("color:#ffffff; font-size:11px; font-weight:800; font-family:'Segoe UI';")
        h_lyt.addWidget(lbl_title)
        h_lyt.addStretch()
        main_lyt.addWidget(header_bar)

        content_frame = QFrame()
        content_frame.setStyleSheet("""
            QFrame {
                background-color: #f1f5f9;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
                border: 1px solid #cbd5e1;
                border-top: none;
            }
        """)
        content_lyt = QVBoxLayout(content_frame)
        content_lyt.setContentsMargins(6, 6, 6, 6)

        self._scroll = QScrollArea()
        self._scroll.setFixedHeight(58)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._row_w = QWidget()
        self._row_w.setStyleSheet("background: transparent;")
        self._row_lyt = QHBoxLayout(self._row_w)
        self._row_lyt.setContentsMargins(0, 0, 0, 0)
        self._row_lyt.setSpacing(8)
        self._scroll.setWidget(self._row_w)
        content_lyt.addWidget(self._scroll)

        self.lbl_empty = QLabel("Bu kayıt için henüz işlem bulunmuyor.")
        self.lbl_empty.setStyleSheet("color:#94a3b8; font-size:11px; padding:4px 2px;")
        content_lyt.addWidget(self.lbl_empty)

        main_lyt.addWidget(content_frame)
        self.set_items([])

    def set_items(self, items: List[Dict[str, str]]) -> None:
        """Şeridi verilen kart listesiyle yeniden çizer (boşsa 'işlem yok' mesajı gösterir)."""
        while self._row_lyt.count():
            child = self._row_lyt.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for it in items:
            btn = QuickTileButton(
                it.get("title", ""), it.get("value", ""), it.get("icon", "🔹"),
                accent_color=it.get("accent", "#2563eb"),
                badge_bg=it.get("badge_bg", "#eff6ff"),
            )
            btn.setCursor(Qt.CursorShape.ArrowCursor)  # salt-okunur özet; tıklanabilir aksiyon değil
            self._row_lyt.addWidget(btn)
        self._row_lyt.addStretch()

        self._scroll.setVisible(bool(items))
        self.lbl_empty.setVisible(not items)
