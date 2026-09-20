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

    def refresh_all(self):
        """Ayarlar kabuğu eski adla çağırıyordu; durum + tavsiye + tabloyu yeniler."""
        self.screen.load_data()
