"""
TOYA ERP - Atomik CRUD İşlemleri Widget'ı (CrudActionsWidget)
Ekle, Düzenle, Sil, Pasife Al, Toplu İşlemler ve Yenile butonlarını barındıran
merkezi yetkilendirme ve klavye kısayolu destekli bağımsız bileşen.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QMenu, QGroupBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from src.desktop.managers.theme_manager import ThemeManager


class CrudActionsWidget(QWidget):
    """Tüm liste ve form ekranlarında kullanılabilen standart CRUD işlem paneli."""

    new_requested = pyqtSignal()
    edit_requested = pyqtSignal()
    duplicate_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    status_toggle_requested = pyqtSignal()
    bulk_action_requested = pyqtSignal(str)  # 'bulk_delete', 'bulk_passive', etc.
    refresh_requested = pyqtSignal()

    def __init__(self, title: str = "İŞLEMLER", enable_bulk: bool = True, parent=None):
        super().__init__(parent)
        self.theme = ThemeManager()
        self.enable_bulk = enable_bulk
        self.title = title
        self._init_ui()

    def _btn_style(self, bg="#ffffff", text="#1e293b", border="#cbd5e1", is_bold=True):
        weight = "700" if is_bold else "600"
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: {weight};
                text-align: left;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{
                background-color: #f1f5f9;
            }}
            QPushButton:pressed {{
                background-color: #e2e8f0;
            }}
        """

    def _init_ui(self):
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(0, 0, 0, 0)
        main_lyt.setSpacing(6)

        self.grp_box = QGroupBox(self.title)
        self.grp_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #1e3a8a;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 4px;
                background-color: transparent;
            }
        """)
        grp_lyt = QVBoxLayout(self.grp_box)
        grp_lyt.setSpacing(6)
        grp_lyt.setContentsMargins(6, 8, 6, 8)

        # 1. Yeni / Ekle Butonu (Mavi Vurgulu)
        self.btn_new = QPushButton("➕ Yeni Ekle (F3)")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setStyleSheet(self._btn_style(bg="#2563eb", text="#ffffff", border="#1d4ed8"))
        self.btn_new.clicked.connect(self.new_requested.emit)
        grp_lyt.addWidget(self.btn_new)

        # 2. Değiştir / Düzenle Butonu
        self.btn_edit = QPushButton("✏️ Değiştir / Düzenle (F4)")
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.setStyleSheet(self._btn_style())
        self.btn_edit.clicked.connect(self.edit_requested.emit)
        grp_lyt.addWidget(self.btn_edit)

        # 3. Kopyala / Çoğalt
        self.btn_duplicate = QPushButton("📋 Kopyala / Çoğalt")
        self.btn_duplicate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_duplicate.setStyleSheet(self._btn_style())
        self.btn_duplicate.clicked.connect(self.duplicate_requested.emit)
        grp_lyt.addWidget(self.btn_duplicate)

        # 4. Pasif / Aktif Yap
        self.btn_status = QPushButton("⚠️ Pasife Al / Aktifleştir")
        self.btn_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_status.setStyleSheet(self._btn_style(bg="#fffbeb", text="#b45309", border="#fde68a"))
        self.btn_status.clicked.connect(self.status_toggle_requested.emit)
        grp_lyt.addWidget(self.btn_status)

        # 5. Sil Butonu (Kırmızı Vurgulu)
        self.btn_delete = QPushButton("🗑️ Sil (Del)")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setStyleSheet(self._btn_style(bg="#fee2e2", text="#dc2626", border="#fca5a5"))
        self.btn_delete.clicked.connect(self.delete_requested.emit)
        grp_lyt.addWidget(self.btn_delete)

        # 6. Toplu İşlemler Menüsü (Opsiyonel)
        if self.enable_bulk:
            self.btn_bulk = QPushButton("⚡ Toplu İşlemler ▼")
            self.btn_bulk.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_bulk.setStyleSheet(self._btn_style(bg="#f8fafc", text="#475569", border="#cbd5e1"))
            
            bulk_menu = QMenu(self)
            bulk_menu.setStyleSheet(self.theme.get_context_menu_stylesheet())
            
            act_bulk_del = QAction("🗑️ Seçilenleri Toplu Sil", self)
            act_bulk_del.triggered.connect(lambda: self.bulk_action_requested.emit("bulk_delete"))
            bulk_menu.addAction(act_bulk_del)

            act_bulk_pass = QAction("⚠️ Seçilenleri Toplu Pasife Al", self)
            act_bulk_pass.triggered.connect(lambda: self.bulk_action_requested.emit("bulk_passive"))
            bulk_menu.addAction(act_bulk_pass)

            act_bulk_act = QAction("🟢 Seçilenleri Toplu Aktif Et", self)
            act_bulk_act.triggered.connect(lambda: self.bulk_action_requested.emit("bulk_active"))
            bulk_menu.addAction(act_bulk_act)

            self.btn_bulk.setMenu(bulk_menu)
            grp_lyt.addWidget(self.btn_bulk)

        # 7. Listeyi Yenile
        self.btn_refresh = QPushButton("🔄 Listeyi Yenile")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet(self._btn_style())
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        grp_lyt.addWidget(self.btn_refresh)

        main_lyt.addWidget(self.grp_box)

    def set_title(self, title: str):
        self.grp_box.setTitle(title)
