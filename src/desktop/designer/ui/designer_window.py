"""
TOYA ERP - Görsel Form & Rapor Tasarımcısı Ana Penceresi (ReportDesignerWindow)

Bağımsız pencere kabuğu. Tasarımcının tüm işlevi artık ``ReportDesignerWidget``
içinde; bu sınıf onu bir ``QMainWindow`` içine yerleştirir (bağımsız başlatıcı ve
"ayrı pencerede aç" akışları için). ERP sekmesi / paneli olarak gömmek için
doğrudan ``ReportDesignerWidget`` kullanılır (bkz. WIDGET_REGISTRY).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QMainWindow, QWidget

from src.desktop.designer.ui.designer_widget import ReportDesignerWidget

__all__ = ["ReportDesignerWindow", "ReportDesignerWidget"]


class ReportDesignerWindow(QMainWindow):
    """Görsel Form & Rapor Tasarımcısı — bağımsız pencere kabuğu."""

    def __init__(
        self,
        template_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.designer = ReportDesignerWidget(template_path=template_path, parent=self)
        self.designer.title_changed.connect(self.setWindowTitle)
        self.setCentralWidget(self.designer)
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
