"""
TOYA ERP - Görsel Form & Rapor Tasarımcısı Ana Penceresi (ReportDesignerWindow)

Bağımsız pencere kabuğu. Tasarımcının tüm işlevi artık ``ReportDesignerWidget``
içinde; bu sınıf onu bir ``QMainWindow`` içine yerleştirir (bağımsız başlatıcı ve
"ayrı pencerede aç" akışları için). ERP sekmesi / paneli olarak gömmek için
doğrudan ``ReportDesignerWidget`` kullanılır (bkz. WIDGET_REGISTRY).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget

from src.desktop.designer.ui.designer_widget import ReportDesignerWidget

logger = logging.getLogger(__name__)

__all__ = ["ReportDesignerWindow", "ReportDesignerWidget"]


class ReportDesignerWindow(QMainWindow):
    """Görsel Tasarımcı — bağımsız pencere kabuğu.

    İki sekme: baskı formu/rapor tasarımcısı (bant tabanlı) ve masaüstü ekran
    tasarımcısı (WIDGET_REGISTRY atomik parçaları bölgelere).
    """

    def __init__(
        self,
        template_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.designer = ReportDesignerWidget(template_path=template_path, parent=self)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.designer, "📄 Form & Rapor Tasarımı")

        # Ekran tasarımcısı ağır bağımlılıkları (screen_registry) yalnız gerekince
        # yüklensin diye burada import edilir.
        try:
            from src.desktop.ui.screens.screen_designer_widget import ScreenDesignerWidget
            self.screen_designer = ScreenDesignerWidget(self)
            self.tabs.addTab(self.screen_designer, "🖥️ Masaüstü Ekran Tasarımı")
        except Exception:  # noqa: BLE001 - ekran tasarımcısı olmadan da form tasarımı çalışsın
            logger.exception("Masaüstü Ekran Tasarımcısı sekmesi yüklenemedi")
            self.screen_designer = None

        self.designer.title_changed.connect(self.setWindowTitle)
        self.setCentralWidget(self.tabs)
        self.setWindowTitle(self.designer.window_title())
        self.resize(1380, 900)
        self.setMinimumSize(950, 650)

    # ── Geriye dönük uyum proxy'leri (eski çağıranlar .template/.canvas okuyor) ──
    @property
    def template(self):
        return self.designer.template

    @property
    def template_path(self) -> Path:
        return self.designer.template_path

    @property
    def canvas(self):
        return self.designer.canvas

    @property
    def inspector(self):
        return self.designer.inspector
