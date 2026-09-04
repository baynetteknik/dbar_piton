"""
TOYA ERP - Profesyonel Baskı Önizleme Penceresi (ReportPreviewDialog)
Teklif, fatura veya raporu ekranda milimetrik olarak birebir önizler,
sayfalar arasında geçiş, zoom (Sayfaya Sığdır, Genişliğe Sığdır, %25-%200),
PDF kaydetme ve yazdırma işlevlerini sağlar.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QImage, QPainter, QPixmap, QResizeEvent
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
        w = max(10, int(self.page_image.width() * self.scale_factor))
        h = max(10, int(self.page_image.height() * self.scale_factor))
        self.setFixedSize(w, h)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target_rect = self.rect()

        # Sayfayı ölçekleyerek çiz
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
        self.zoom_mode = "fit_page"  # "fit_page", "fit_width", "manual"

        self.setWindowTitle(f"Baskı Önizleme - {self.template.title}")
        self.resize(1100, 850)
        self.setMinimumSize(650, 500)

        self._init_ui()
        self._render_all_pages()

        # İlk açılışta sayfaya sığdır
        self._apply_zoom_mode("fit_page")

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── 1. Üst Araç Çubuğu (Toolbar) ───
        toolbar = QWidget(self)
        toolbar.setStyleSheet("background-color: #1E293B; color: #FFFFFF; padding: 6px;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 6, 12, 6)
        tb_layout.setSpacing(10)

        # Yazdır Butonu
        self.btn_print = QPushButton("🖨️ Yazdır", self)
        self.btn_print.setStyleSheet(
            "background-color: #2563EB; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;"
        )
        self.btn_print.clicked.connect(self._on_print_clicked)
        tb_layout.addWidget(self.btn_print)

        # PDF Kaydet Butonu
        self.btn_pdf = QPushButton("💾 PDF Kaydet", self)
        self.btn_pdf.setStyleSheet(
            "background-color: #16A34A; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;"
        )
        self.btn_pdf.clicked.connect(self._on_pdf_save_clicked)
        tb_layout.addWidget(self.btn_pdf)

        tb_layout.addSpacing(16)

        # Sayfa Navigasyonu
        self.btn_prev = QPushButton("◀ Önceki", self)
        self.btn_prev.clicked.connect(self._prev_page)
        tb_layout.addWidget(self.btn_prev)

        self.lbl_page_info = QLabel("Sayfa 1 / 1", self)
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #F1F5F9; font-size: 12px;")
        tb_layout.addWidget(self.lbl_page_info)

        self.btn_next = QPushButton("Sonraki ▶", self)
        self.btn_next.clicked.connect(self._next_page)
        tb_layout.addWidget(self.btn_next)

        tb_layout.addSpacing(16)

        # Yakınlaştırma (Zoom) Seçici
        tb_layout.addWidget(QLabel("Yakınlaştır:", self))
        self.cmb_zoom = QComboBox(self)
        self.cmb_zoom.addItems([
            "📄 Sayfaya Sığdır (Tümünü Göster)",
            "↔️ Genişliğe Sığdır",
            "%25",
            "%35",
            "%50",
            "%75",
            "%100",
            "%125",
            "%150",
            "%200",
        ])
        self.cmb_zoom.setCurrentIndex(0)
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
        self.scroll_area.setStyleSheet("background-color: #475569;")
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.canvas_container = QWidget()
        self.canvas_container.setStyleSheet("background: transparent;")
        self.canvas_layout = QVBoxLayout(self.canvas_container)
        self.canvas_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_layout.setContentsMargins(15, 15, 15, 15)

        self.scroll_area.setWidget(self.canvas_container)
        self.scroll_area.setWidgetResizable(True)
        main_layout.addWidget(self.scroll_area)

    def _render_all_pages(self):
        """Tüm sayfaları milimetrik DPI bazlı piksel çözünürlüğünde çizer."""
        self.rendered_pages.clear()

        # A4 ebatları (mm) -> 150 DPI için piksel (1240 x 1754 px)
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

    def _calculate_fit_scale(self, mode: str) -> float:
        """Pencere boyutuna göre sığdırma oranını hesaplar."""
        if not self.rendered_pages:
            return 1.0

        page_w = self.rendered_pages[0].width()
        page_h = self.rendered_pages[0].height()

        viewport = self.scroll_area.viewport()
        avail_w = max(100, viewport.width() - 40)
        avail_h = max(100, viewport.height() - 40)

        if mode == "fit_page":
            # Hem en hem boy sığsın (Tüm sayfayı göster)
            scale_w = avail_w / page_w
            scale_h = avail_h / page_h
            return min(scale_w, scale_h)
        elif mode == "fit_width":
            # Yalnızca genişliğe sığdır
            return avail_w / page_w
        return 1.0

    def _apply_zoom_mode(self, mode: str):
        self.zoom_mode = mode
        if mode in ("fit_page", "fit_width"):
            self.scale_factor = self._calculate_fit_scale(mode)
        self._display_current_page()

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
            "border: 1px solid #1E293B; background: white; "
            "box-shadow: 0px 8px 20px rgba(0, 0, 0, 0.4);"
        )
        self.canvas_layout.addWidget(page_widget)

    def resizeEvent(self, event: QResizeEvent):
        """Pencere yeniden boyutlandırıldığında sığdırma oranını güncelle."""
        super().resizeEvent(event)
        if self.zoom_mode in ("fit_page", "fit_width"):
            self.scale_factor = self._calculate_fit_scale(self.zoom_mode)
            self._display_current_page()

    def _prev_page(self):
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
            self._display_current_page()

    def _next_page(self):
        if self.current_page_idx < len(self.rendered_pages) - 1:
            self.current_page_idx += 1
            self._display_current_page()

    def _on_zoom_changed(self, text: str):
        if "Sayfaya Sığdır" in text:
            self._apply_zoom_mode("fit_page")
        elif "Genişliğe Sığdır" in text:
            self._apply_zoom_mode("fit_width")
        else:
            self.zoom_mode = "manual"
            # %25, %35, %50, %75 vb.
            clean_pct = text.replace("%", "").strip()
            try:
                pct = float(clean_pct)
                self.scale_factor = pct / 100.0
                self._display_current_page()
            except ValueError:
                pass

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
