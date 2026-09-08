"""
TOYA ERP - Profesyonel Baskı Önizleme Penceresi (ReportPreviewDialog)

Modal pencere kabuğu. Tüm önizleme işlevi artık ``ReportPreviewWidget`` içinde
(araç çubuğu, sayfa navigasyonu, zoom, milimetrik render); bu sınıf onu bir
``QDialog`` içine yerleştirir. Panele gömmek için doğrudan ``ReportPreviewWidget``
kullanılır (bkz. WIDGET_REGISTRY → ``widget_report_preview``).
"""

from __future__ import annotations

import logging
from typing import Any

from PyQt6.QtWidgets import QDialog, QPushButton, QVBoxLayout, QWidget

from src.desktop.designer.models import ReportTemplate
from src.desktop.designer.ui.preview_widget import PageViewWidget, ReportPreviewWidget

logger = logging.getLogger(__name__)

__all__ = ["ReportPreviewDialog", "ReportPreviewWidget", "PageViewWidget"]


class ReportPreviewDialog(QDialog):
    """Gelişmiş Form ve Rapor Baskı Önizleme Penceresi (modal kabuk)."""

    def __init__(
        self,
        template: ReportTemplate,
        data: dict[str, Any] | None = None,
        parent: QWidget | None = None,
        datas: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Baskı Önizleme - {template.title}")
        self.resize(1100, 850)
        self.setMinimumSize(650, 500)

        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(0)

        self.preview = ReportPreviewWidget(
            template=template, data=data, datas=datas, parent=self,
        )
        lyt.addWidget(self.preview, 1)

        # Araç çubuğuna "Kapat" ekle (widget kendi başına kapatma bilmez).
        btn_close = QPushButton("Kapat", self)
        btn_close.clicked.connect(self.accept)
        self.preview.add_toolbar_widget(btn_close)

    # ── Geriye dönük uyum: eski çağıranlar dialog üzerinden okuyor ──
    @property
    def rendered_pages(self):
        return self.preview.rendered_pages

    @property
    def datas(self):
        return self.preview.datas

    @property
    def data(self):
        return self.preview.data
