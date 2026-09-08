"""
TOYA ERP - Atomik Favori İşlemler Widget'ı (FavoriteActionsWidget)
Kullanıcının sık kullandığı ekranları, hızlı kısayolları ve favori sayaç rozetini
barındıran bağımsız sol/orta panel bileşeni.
"""

from typing import List, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QListWidget, QListWidgetItem, QPushButton, 
    QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont


class FavoriteActionsWidget(QWidget):
    """Favori ekranlar ve hızlı işlem kısayolları paneli (Resim 1 & 2 ile birebir uyumlu)."""

    module_selected = pyqtSignal(str)
    quick_action_triggered = pyqtSignal(str)

    def __init__(self, favorites: Optional[List[str]] = None, parent=None):
        super().__init__(parent)
        self.favorites = favorites or ["Ürün Yönetimi", "Görevler", "Teklif Yönetimi", "Müşteriler & Cariler"]
        self._init_ui()

    def _init_ui(self):
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(0, 0, 0, 0)
        main_lyt.setSpacing(8)

        self.card_frame = QFrame()
        self.card_frame.setStyleSheet("""
            QFrame#card_frame {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #e2e8f0;
            }
        """)
        self.card_frame.setObjectName("card_frame")

        shadow = QGraphicsDropShadowEffect(self.card_frame)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 12))
        shadow.setOffset(0, 2)
        self.card_frame.setGraphicsEffect(shadow)

        card_lyt = QVBoxLayout(self.card_frame)
        card_lyt.setContentsMargins(14, 14, 14, 14)
        card_lyt.setSpacing(10)

        # Başlık ve Rozet
        header_lyt = QHBoxLayout()
        title_lbl = QLabel("⚡ Favori İşlemler")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #0f172a; font-family: 'Segoe UI';")
        header_lyt.addWidget(title_lbl)
        header_lyt.addStretch()

        self.badge_count = QLabel(str(len(self.favorites)))
        self.badge_count.setStyleSheet("""
            background-color: #eff6ff;
            color: #2563eb;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 10px;
            border: 1px solid #bfdbfe;
        """)
        header_lyt.addWidget(self.badge_count)
        card_lyt.addLayout(header_lyt)

        desc_lbl = QLabel("Sık kullandığınız ekranlar ve hızlı işlemler:")
        desc_lbl.setStyleSheet("font-size: 11px; color: #64748b; font-family: 'Segoe UI';")
        card_lyt.addWidget(desc_lbl)

        # Favori Liste
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #f1f5f9;
                border-radius: 8px;
                background-color: #f8fafc;
                font-size: 12px;
                color: #0f172a;
                font-weight: 600;
                padding: 4px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 6px;
                margin-bottom: 3px;
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                color: #0f172a;
            }
            QListWidget::item:hover {
                background-color: #eff6ff;
                color: #2563eb;
                border-color: #93c5fd;
            }
        """)
        self.list_widget.itemClicked.connect(lambda item: self.module_selected.emit(item.text()))
        card_lyt.addWidget(self.list_widget, 1)

        # Hızlı Kısayol Butonları
        quick_lbl = QLabel("➕ Hızlı Kısayollar")
        quick_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #475569; margin-top: 4px;")
        card_lyt.addWidget(quick_lbl)

        q_btn_lyt = QVBoxLayout()
        q_btn_lyt.setSpacing(6)

        self.btn_cari = self._create_quick_button("👥 Yeni Cari Kartı Aç", "Müşteriler & Cariler")
        self.btn_teklif = self._create_quick_button("📄 Yeni Teklif Hazırla", "Teklif Yönetimi")

        q_btn_lyt.addWidget(self.btn_cari)
        q_btn_lyt.addWidget(self.btn_teklif)
        card_lyt.addLayout(q_btn_lyt)

        main_lyt.addWidget(self.card_frame)
        self.refresh_favorites()
        self._apply_permissions()
        try:
            from src.desktop.managers.permission_manager import PermissionManager
            PermissionManager().role_changed.connect(lambda *_: self._apply_permissions())
        except Exception:  # noqa: BLE001
            pass

    def _apply_permissions(self):
        """Yetkisi olmayan favori satırlarını ve hızlı kısayolları gizler."""
        try:
            from src.desktop.security.gate import can, module_permission
        except Exception:  # noqa: BLE001
            return
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            perm = module_permission(it.text())
            it.setHidden(bool(perm) and not can(perm))
        self.btn_cari.setVisible(can("cari.create"))
        self.btn_teklif.setVisible(can("teklif.create"))

    def _create_quick_button(self, label: str, target: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 9px 12px;
                background-color: #2563eb;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 700;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
                border-color: #1e3a8a;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)
        btn.clicked.connect(lambda: self.quick_action_triggered.emit(target))
        return btn

    def refresh_favorites(self):
        self.list_widget.clear()
        for fav in self.favorites:
            item = QListWidgetItem(fav)
            self.list_widget.addItem(item)
        self.badge_count.setText(str(len(self.favorites)))
        if hasattr(self, "btn_cari"):
            self._apply_permissions()
