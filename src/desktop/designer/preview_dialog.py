"""
TOYA ERP - Profesyonel Baskı Önizleme Penceresi (ReportPreviewDialog)
Teklif, fatura veya raporu ekranda milimetrik olarak birebir önizler,
sayfalar arasında geçiş, zoom, PDF kaydetme ve yazdırma işlevlerini sağlar.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

from src.desktop.designer.models import ReportTemplate
from src.desktop.designer.printer_engine import ReportPrinterEngine

logger = logging.getLogger(__name__)


class PageViewWidget(QWidget):
    """Tek bir sayfanın milimetrik çizimini gösteren tuval."""

    def __init__(self, page_image: QImage, scale_factor: float = 1.0, parent=None):
        super().__init__(parent)
        self.page_image = page_image
        self.scale_factor = scale_factor
        self._update_size()

    def set_scale(self, scale: float):
        self.scale_factor = scale
        self._update_size()
        self.update()

    def _update_size(self):
        w = int(self.page_image.width() * self.scale_factor)
        h = int(self.page_image.height() * self.scale_factor)
        self.setFixedSize(w, h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target_rect = self.rect()

        # Sayfa arka planı ve gölge
        painter.drawImage(target_rect, self.page_image)


class ReportPreviewDialog(QDialog):
    """Gelişmiş Form ve Rapor Baskı Önizleme Penceresi."""

    def __init__(
        self,
        template: ReportTemplate,
        data: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.template = template
        self.data = data
        self.engine = ReportPrinterEngine(template)

        self.current_page_idx = 0
        self.rendered_pages: list[QImage] = []
        self.scale_factor = 1.0

        self.setWindowTitle(f"Baskı Önizleme - {self.template.title}")
        self.resize(980, 850)
        self.setMinimumSize(700, 600)

        self._init_ui()
        self._render_all_pages()
        self._display_current_page()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── 1. Üst Araç Çubuğu (Toolbar) ───
        toolbar = QWidget(self)
        toolbar.setStyleSheet("background-color: #24292E; color: #FFFFFF; padding: 6px;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(10)

        # Yazdır Butonu
        self.btn_print = QPushButton("🖨️ Yazdır", self)
        self.btn_print.setStyleSheet(
            "background-color: #0366D6; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;"
        )
        self.btn_print.clicked.connect(self._on_print_clicked)
        tb_layout.addWidget(self.btn_print)

        # PDF Kaydet Butonu
        self.btn_pdf = QPushButton("💾 PDF Kaydet", self)
        self.btn_pdf.setStyleSheet(
            "background-color: #2EA44F; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;"
        )
        self.btn_pdf.clicked.connect(self._on_pdf_save_clicked)
        tb_layout.addWidget(self.btn_pdf)

        tb_layout.addSpacing(20)

        # Sayfa Navigasyonu
        self.btn_prev = QPushButton("◀ Önceki", self)
        self.btn_prev.clicked.connect(self._prev_page)
        tb_layout.addWidget(self.btn_prev)

        self.lbl_page_info = QLabel("Sayfa 1 / 1", self)
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #F0F6FC;")
        tb_layout.addWidget(self.lbl_page_info)

        self.btn_next = QPushButton("Sonraki ▶", self)
        self.btn_next.clicked.connect(self._next_page)
        tb_layout.addWidget(self.btn_next)

        tb_layout.addSpacing(20)

        # Yakınlaştırma (Zoom)
        tb_layout.addWidget(QLabel("Yakınlaştır:", self))
        self.cmb_zoom = QComboBox(self)
        self.cmb_zoom.addItems(["%75", "%100", "%125", "%150", "Genişliğe Sığdır"])
        self.cmb_zoom.setCurrentText("%100")
        self.cmb_zoom.currentTextChanged.connect(self._on_zoom_changed)
        tb_layout.addWidget(self.cmb_zoom)

        tb_layout.addStretch()

        # Kapat Butonu
        self.btn_close = QPushButton("Kapat", self)
        self.btn_close.clicked.connect(self.accept)
        tb_layout.addWidget(self.btn_close)

        main_layout.addWidget(toolbar)

        # ─── 2. Orta Sayfa Tuvali (Scroll Area) ───
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setStyleSheet("background-color: #525659;")
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.canvas_container = QWidget()
        self.canvas_container.setStyleSheet("background: transparent;")
        self.canvas_layout = QVBoxLayout(self.canvas_container)
        self.canvas_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_layout.setContentsMargins(20, 20, 20, 20)

        self.scroll_area.setWidget(self.canvas_container)
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area)

    def _render_all_pages(self):
        """Tüm sayfaları milimetrik yüksek çözünürlüklü QImage olarak hafızaya çizer."""
        self.rendered_pages.clear()

        # A4 ebatları (mm) -> 150 DPI için piksel
        target_dpi = 150.0
        mm_to_px = target_dpi / 25.4
        w_px = int(self.template.page.width_mm * mm_to_px)
        h_px = int(self.template.page.height_mm * mm_to_px)

        page_images: list[QImage] = []

        def create_new_page_image() -> tuple[QImage, QPainter]:
            img = QImage(w_px, h_px, QImage.Format.Format_RGB32)
            img.fill(QColor("#FFFFFF"))
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            return img, p

        current_img, current_painter = create_new_page_image()
        page_images.append(current_img)

        # Sayfa geçişinde yeni QImage oluştur
        def on_new_page():
            nonlocal current_img, current_painter
            current_painter.end()
            current_img, current_painter = create_new_page_image()
            page_images.append(current_img)

        # Render işlemi
        self.engine.render_document(
            current_painter,
            self.data,
            target_device_dpi=target_dpi,
            new_page_callback=on_new_page,
        )
        current_painter.end()

        self.rendered_pages = page_images
        self.current_page_idx = 0

    def _display_current_page(self):
        """Aktif sayfayı ekrana yansıtır."""
        if not self.rendered_pages:
            return

        # Eski sayfayı temizle
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total = len(self.rendered_pages)
        curr = self.current_page_idx
        self.lbl_page_info.setText(f"Sayfa {curr + 1} / {total}")
        self.btn_prev.setEnabled(curr > 0)
        self.btn_next.setEnabled(curr < total - 1)

        page_img = self.rendered_pages[curr]
        page_widget = PageViewWidget(page_img, scale_factor=self.scale_factor, parent=self)
        page_widget.setStyleSheet(
            "border: 1px solid #333; background: white; "
            "box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.5);"
        )
        self.canvas_layout.addWidget(page_widget)

    def _prev_page(self):
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
            self._display_current_page()

    def _next_page(self):
        if self.current_page_idx < len(self.rendered_pages) - 1:
            self.current_page_idx += 1
            self._display_current_page()

    def _on_zoom_changed(self, text: str):
        if text == "%75":
            self.scale_factor = 0.75
        elif text == "%100":
            self.scale_factor = 1.0
        elif text == "%125":
            self.scale_factor = 1.25
        elif text == "%150":
            self.scale_factor = 1.5
        elif text == "Genişliğe Sığdır":
            viewport_w = self.scroll_area.viewport().width() - 60
            if self.rendered_pages:
                self.scale_factor = max(0.5, viewport_w / self.rendered_pages[0].width())
        self._display_current_page()

    def _on_pdf_save_clicked(self):
        """PDF dosyasını kaydeder."""
        belge_no = self.data.get("belge", {}).get("teklif_no", "TEKLIF")
        dosya_adi = f"{belge_no}_Teklif_Formu.pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Teklif Formunu PDF Olarak Kaydet",
            dosya_adi,
            "PDF Dosyaları (*.pdf)",
        )
        if file_path:
            ok = self.engine.export_to_pdf(self.data, file_path)
            if ok:
                QMessageBox.information(
                    self,
                    "Başarılı",
                    f"Teklif formu başarıyla PDF olarak kaydedildi:\n{file_path}",
                )
            else:
                QMessageBox.critical(self, "Hata", "PDF oluşturulurken bir hata oluştu.")

    def _on_print_clicked(self):
        """Fiziksel yazıcı seçim diyaloğu açar ve yazdırır."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Teklif Formunu Yazdır")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            painter = QPainter(printer)
            if painter.isActive():
                dpi = float(printer.resolution())
                self.engine.render_document(
                    painter,
                    self.data,
                    target_device_dpi=dpi,
                    new_page_callback=lambda: printer.newPage(),
                )
                painter.end()
                QMessageBox.information(self, "Yazdırıldı", "Teklif yazıcıya gönderildi.")
