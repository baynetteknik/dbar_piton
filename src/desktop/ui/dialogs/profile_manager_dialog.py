"""Dialog for View Profile Management."""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from src.desktop.managers.profile_manager import ProfileManager

logger = logging.getLogger(__name__)


class ProfileManagerDialog(QDialog):
    """Management dialog for listing, deleting, and selecting View Profiles."""

    def __init__(self, profile_manager: "ProfileManager", parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.setWindowTitle(self.tr("⚙️ Görünüm Profillerini Yönet"))
        self.setFixedSize(380, 320)
        self.init_ui()

    def init_ui(self):
        """Initializes dialog layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        lbl_info = QLabel(self.tr("Kayıtlı Görünüm Profilleri:"))
        lbl_info.setStyleSheet("font-weight: bold; color: #334155;")
        layout.addWidget(lbl_info)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
                color: #334155;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                color: #2563eb;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_delete = QPushButton(self.tr("❌ Seçili Profili Sil"))
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #b91c1c;
                border: 1px solid #fca5a5;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #fca5a5;
            }
        """)
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_layout.addWidget(self.btn_delete, 1)

        self.btn_close = QPushButton(self.tr("Kapat"))
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)
        self.reload_list()

    def reload_list(self):
        """Reloads profiles from ProfileManager into list widget."""
        self.list_widget.clear()
        profiles = self.profile_manager.load_profiles()
        active_name = self.profile_manager.get_active_profile_name()

        for name in profiles.keys():
            item_text = f"{name} (Aktif)" if name == active_name else name
            self.list_widget.addItem(item_text)

    def _delete_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(
                self, self.tr("Uyarı"), self.tr("Lütfen silmek istediğiniz profili seçin."),
            )
            return

        raw_text = item.text().replace(" (Aktif)", "")
        if raw_text == "Varsayılan":
            QMessageBox.warning(
                self, self.tr("Uyarı"), self.tr("Varsayılan sistem profili silinemez."),
            )
            return

        confirm = QMessageBox.question(
            self,
            self.tr("Profil Sil"),
            self.tr(f"'{raw_text}' profilini silmek istediğinizden emin misiniz?"),
        )
        if confirm == QMessageBox.StandardButton.Yes:
            if self.profile_manager.delete_profile(raw_text):
                QMessageBox.information(
                    self, self.tr("Başarılı"), self.tr(f"'{raw_text}' profili silindi."),
                )
                self.reload_list()
