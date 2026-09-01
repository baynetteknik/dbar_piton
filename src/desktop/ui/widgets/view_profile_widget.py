"""
TOYA ERP - Atomik Görünüm Profilleri Widget'ı (ViewProfileWidget)
Görünüm profili seçici, aktif profili kaydetme ve sütun yöneticisi butonlarını barındıran
ProfileManager ile doğrudan entegre çalışan bağımsız bileşen.
"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QPushButton, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.desktop.managers.profile_manager import ProfileManager


class ViewProfileWidget(QWidget):
    """Kayıtlı görünüm profillerini ve sütun ayarlarını yöneten modüler widget."""

    profile_selected = pyqtSignal(str)
    save_requested = pyqtSignal()
    columns_requested = pyqtSignal()

    def __init__(self, profile_key: str = "default_view", title: str = "GÖRÜNÜM PROFİLLERİ", parent=None):
        super().__init__(parent)
        self.profile_key = profile_key
        self.title = title
        self.profile_manager = ProfileManager(profile_key=self.profile_key)
        self._init_ui()
        self.load_profiles()

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

        lbl_prof = QLabel("Aktif Görünüm Profili:")
        lbl_prof.setStyleSheet("font-weight: 600; color: #475569; font-size: 11px;")
        grp_lyt.addWidget(lbl_prof)

        self.combo_profiles = QComboBox()
        self.combo_profiles.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                color: #0f172a;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        self.combo_profiles.currentTextChanged.connect(self._on_combo_changed)
        grp_lyt.addWidget(self.combo_profiles)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        btn_style = """
            QPushButton {
                background-color: #ffffff;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #f1f5f9; }
        """

        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(btn_style)
        self.btn_save.clicked.connect(self.save_requested.emit)
        btn_row.addWidget(self.btn_save)

        self.btn_columns = QPushButton("⚙️ Sütunlar")
        self.btn_columns.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_columns.setStyleSheet(btn_style)
        self.btn_columns.clicked.connect(self.columns_requested.emit)
        btn_row.addWidget(self.btn_columns)

        grp_lyt.addLayout(btn_row)
        main_lyt.addWidget(self.grp_box)

    def load_profiles(self):
        """Kayıtlı profilleri combo içine doldurur."""
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()
        profiles = self.profile_manager.load_profiles()
        for name in profiles.keys():
            self.combo_profiles.addItem(name)
        active = self.profile_manager.get_active_profile_name()
        idx = self.combo_profiles.findText(active)
        if idx >= 0:
            self.combo_profiles.setCurrentIndex(idx)
        self.combo_profiles.blockSignals(False)

    def _on_combo_changed(self, text: str):
        if text:
            self.profile_selected.emit(text)

    def get_current_profile_name(self) -> str:
        return self.combo_profiles.currentText() or "Varsayılan"
