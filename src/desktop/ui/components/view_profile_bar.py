"""View Profile Bar Widget.

Top toolbar component for quick profile selection, dirty state tracking, and profile actions.
"""

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from src.desktop.managers.profile_manager import ProfileManager

if TYPE_CHECKING:
    from src.desktop.ui.components.filterable_table import FilterableTableView

logger = logging.getLogger(__name__)


class ViewProfileBar(QWidget):
    """Toolbar widget for quick profile switching and actions."""

    profile_changed = pyqtSignal(str)  # Emits selected profile name
    profile_saved = pyqtSignal()  # Emits when profile is saved

    def __init__(
        self,
        profile_key: str = "customers",
        table_view: "FilterableTableView | None" = None,
        parent=None,
    ):
        super().__init__(parent)
        self.profile_key = profile_key
        self.table_view = table_view
        self.profile_manager = ProfileManager(profile_key=self.profile_key)
        self.is_dirty = False

        self.setObjectName("ViewProfileBar")
        self.init_ui()

    def init_ui(self):
        """Initializes the toolbar UI layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Label
        self.lbl_title = QLabel(self.tr("👤 Görünüm Profili:"))
        self.lbl_title.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")
        layout.addWidget(self.lbl_title)

        # ComboBox Selector
        self.combo_profiles = QComboBox()
        self.combo_profiles.setMinimumWidth(180)
        self.combo_profiles.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
                background-color: #ffffff;
                color: #0f172a;
                font-weight: 500;
            }
            QComboBox:hover {
                border-color: #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.combo_profiles.currentTextChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo_profiles)

        # Dirty State Label (*)
        self.lbl_dirty = QLabel("")
        self.lbl_dirty.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.lbl_dirty)

        # Save Button
        self.btn_save = QPushButton(self.tr("💾 Kaydet"))
        self.btn_save.setToolTip(self.tr("Mevcut profil değişikliklerini kaydet"))
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.btn_save.clicked.connect(self._on_save_clicked)
        layout.addWidget(self.btn_save)

        # Save As Button
        self.btn_save_as = QPushButton(self.tr("➕ Farklı Kaydet"))
        self.btn_save_as.setToolTip(self.tr("Yeni profil olarak kaydet"))
        self.btn_save_as.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        self.btn_save_as.clicked.connect(self._on_save_as_clicked)
        layout.addWidget(self.btn_save_as)

        # Manage Profiles Button
        self.btn_manage = QPushButton(self.tr("⚙️ Yönet"))
        self.btn_manage.setToolTip(self.tr("Görünüm profillerini yönet"))
        self.btn_manage.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        self.btn_manage.clicked.connect(self._on_manage_clicked)
        layout.addWidget(self.btn_manage)

        layout.addStretch(1)
        self.reload_profiles()

    def reload_profiles(self):
        """Reloads profile list from ProfileManager."""
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()

        profiles = self.profile_manager.load_profiles()
        active_name = self.profile_manager.get_active_profile_name()

        for name in profiles.keys():
            self.combo_profiles.addItem(name)

        index = self.combo_profiles.findText(active_name)
        if index >= 0:
            self.combo_profiles.setCurrentIndex(index)

        self.combo_profiles.blockSignals(False)
        self.set_dirty(False)

    def set_dirty(self, dirty: bool):
        """Sets dirty state indicator."""
        self.is_dirty = dirty
        if dirty:
            self.lbl_dirty.setText("* (Değiştirildi)")
        else:
            self.lbl_dirty.setText("")

    def _on_combo_changed(self, profile_name: str):
        if not profile_name:
            return
        self.profile_manager.set_active_profile_name(profile_name)
        self.set_dirty(False)
        self.profile_changed.emit(profile_name)

        if self.table_view:
            profile = self.profile_manager.get_active_profile()
            self.table_view.apply_view_profile(profile)

    def _on_save_clicked(self):
        active_name = self.combo_profiles.currentText()
        if not active_name:
            return

        if self.table_view:
            current_profile = self.table_view.capture_current_view_profile(
                profile_name=active_name,
            )
            self.profile_manager.save_profile(current_profile)
            self.set_dirty(False)
            self.profile_saved.emit()
            QMessageBox.information(
                self,
                self.tr("Başarılı"),
                self.tr(f"'{active_name}' profili başarıyla kaydedildi."),
            )

    def _on_save_as_clicked(self):
        new_name, ok = QInputDialog.getText(
            self,
            self.tr("Yeni Profil Kaydet"),
            self.tr("Lütfen yeni profil adını giriniz:"),
        )
        if ok and new_name.strip():
            new_name = new_name.strip()
            if self.table_view:
                new_profile = self.table_view.capture_current_view_profile(
                    profile_name=new_name,
                )
                self.profile_manager.save_profile(new_profile)
                self.profile_manager.set_active_profile_name(new_name)
                self.reload_profiles()
                self.profile_changed.emit(new_name)
                self.table_view.apply_view_profile(new_profile)

    def _on_manage_clicked(self):
        from src.desktop.ui.dialogs.profile_manager_dialog import ProfileManagerDialog

        dlg = ProfileManagerDialog(
            profile_manager=self.profile_manager, parent=self,
        )
        dlg.exec()
        self.reload_profiles()
        if self.table_view:
            p = self.profile_manager.get_active_profile()
            self.table_view.apply_view_profile(p)
