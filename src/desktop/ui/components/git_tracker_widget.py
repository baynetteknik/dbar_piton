"""
Git & Task Tracker Widget for Settings Dialog / Main Window.
Wraps the new 3-Panel GitTrackerScreen for backward compatibility.
"""

import logging
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.desktop.ui.components.git_tracker_screen import GitTrackerScreen

logger = logging.getLogger(__name__)


class GitTrackerWidget(QWidget):
    """3-Bölmeli Standart Git & Görev Takip Bileşeni"""

    def __init__(self, parent=None, embedded: bool = False, defer_load: bool = False):
        super().__init__(parent)
        self.embedded = embedded
        self.defer_load = defer_load
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.screen = GitTrackerScreen(parent=self, embedded=self.embedded, defer_load=self.defer_load)
        layout.addWidget(self.screen)

    def load_data(self):
        """Reloads git data inside the screen."""
        self.screen._load_git_data()

    def refresh_data(self):
        self.screen._load_git_data()

    def refresh_all(self) -> str:
        """Durum + tavsiye + tabloyu yeniler ve kullanıcıya görünür bir sonuç mesajı döner (ve ekranda gösterir)."""
        import git_tracker

        self.screen.load_data()
        self.screen.profile_panel.reload()
        st = git_tracker.get_git_status()
        msg = f"🔄 Yenilendi: {st.get('modified_count', 0)} değişen dosya, {st.get('ahead_count', 0)} gönderilmemiş commit"
        self.screen.lbl_stage.setText(msg)
        self.screen.lbl_stage.setStyleSheet("font-size: 11px; font-weight: bold; color: #16a34a;")
        self.screen.console_drawer.appendPlainText(msg)
        return msg
