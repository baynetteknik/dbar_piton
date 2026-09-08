"""
TOYA ERP - Atomik Ana Menü Modül Gridi Widget'ı (MenuGridWidget)
Görsellerde yer alan büyük mavi ikon modül butonları gridini barındıran,
sağ ve sol tıklama destekli bağımsız merkez/gövde bileşeni.
"""

from typing import List, Tuple, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QPushButton, QFrame, QScrollArea, 
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QFont


class MenuGridButton(QPushButton):
    """Büyük mavi modül kart butonu."""

    right_clicked = pyqtSignal(str, QPoint)

    def __init__(self, name: str, emoji: str, target_module: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.emoji = emoji
        self.target_module = target_module
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(115, 96)

        self.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                border: 1px solid #1d4ed8;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
                border-color: #1e3a8a;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)

        btn_lyt = QVBoxLayout(self)
        btn_lyt.setContentsMargins(6, 6, 6, 6)
        btn_lyt.setSpacing(4)
        btn_lyt.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_emoji = QLabel(emoji)
        self.lbl_emoji.setFont(QFont("Segoe UI", 24))
        self.lbl_emoji.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_emoji.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        btn_lyt.addWidget(self.lbl_emoji)

        self.lbl_name = QLabel(name)
        self.lbl_name.setStyleSheet("font-size: 11px; font-weight: 700; color: #ffffff; font-family: 'Segoe UI';")
        self.lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        btn_lyt.addWidget(self.lbl_name)

        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(8)
        sh.setColor(QColor(0, 0, 0, 30))
        sh.setOffset(0, 2)
        self.setGraphicsEffect(sh)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.right_clicked.emit(self.target_module, event.globalPosition().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)


class MenuGridWidget(QWidget):
    """Ana ekran modül kartları gridi (Resim 1 & 2 ile birebir uyumlu)."""

    module_selected = pyqtSignal(str)
    module_right_clicked = pyqtSignal(str, QPoint)
    log_action_requested = pyqtSignal()

    def __init__(self, modules: Optional[List[Tuple[str, str, str]]] = None, parent=None):
        super().__init__(parent)
        self.modules = modules or [
            ("Faturalar", "📄", "Faturalar"),
            ("Kasa Yönetimi", "💰", "Kasa Yönetimi"),
            ("Personel", "👔", "Personel"),
            ("Müşteriler", "👥", "Müşteriler & Cariler"),
            ("Teklif Yönetimi", "📑", "Teklif Yönetimi"),
            ("Sipariş Yönetimi", "📦", "Sipariş Yönetimi"),
            ("Stok Kartları", "🏷️", "Ürün Yönetimi"),
            ("Çek / Senet", "📑", "Çek / Senet"),
            ("Banka Hesapları", "🏦", "Banka Hesapları"),
            ("Görevler", "🔄", "Görevler"),
            ("Cari Analiz", "📊", "Cari Analiz"),
            ("Genel Ayarlar", "⚙️", "Genel Ayarlar"),
        ]
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

        # Başlık Çubuğu
        header_lyt = QHBoxLayout()
        title_lbl = QLabel("🚀 Ana Menüler")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 800; color: #0f172a; font-family: 'Segoe UI';")
        header_lyt.addWidget(title_lbl)
        header_lyt.addStretch()

        btn_log = QPushButton("İşlem Günlüğü")
        btn_log.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_log.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                color: #2563eb;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
                border-radius: 6px;
                border: 1px solid #bfdbfe;
            }
            QPushButton:hover { background-color: #dbeafe; }
        """)
        btn_log.clicked.connect(self.log_action_requested.emit)
        header_lyt.addWidget(btn_log)
        card_lyt.addLayout(header_lyt)

        desc_lbl = QLabel("Tüm ana modüllere doğrudan erişim (Sağ tık ile alt menülere ulaşabilirsiniz):")
        desc_lbl.setStyleSheet("font-size: 11px; color: #64748b; font-family: 'Segoe UI';")
        card_lyt.addWidget(desc_lbl)

        # Scroll Alanı ve Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        grid_container = QWidget()
        grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(12)

        # Kartları Grid Olarak Diz (Satır başına 3 veya 4 kart)
        self._buttons: dict[str, MenuGridButton] = {}
        cols_count = 3
        for i, (name, emoji, target) in enumerate(self.modules):
            row = i // cols_count
            col = i % cols_count
            btn = MenuGridButton(name, emoji, target)
            btn.clicked.connect(lambda checked, t=target: self.module_selected.emit(t))
            btn.right_clicked.connect(lambda t, pos: self.module_right_clicked.emit(t, pos))
            self.grid_layout.addWidget(btn, row, col)
            self._buttons[target] = btn

        scroll.setWidget(grid_container)
        card_lyt.addWidget(scroll, 1)

        main_lyt.addWidget(self.card_frame)

        self._apply_permissions()
        try:
            from src.desktop.managers.permission_manager import PermissionManager
            PermissionManager().role_changed.connect(lambda *_: self._apply_permissions())
        except Exception:  # noqa: BLE001
            pass

    def _apply_permissions(self):
        """Kullanıcının erişemediği modül kartlarını gizler."""
        try:
            from src.desktop.security.gate import can, module_permission
        except Exception:  # noqa: BLE001
            return
        for target, btn in self._buttons.items():
            perm = module_permission(target)
            btn.setVisible(can(perm) if perm else True)
