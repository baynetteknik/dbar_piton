"""
TOYA ERP - Gömülebilir Baskı Önizleme Widget'ı (ReportPreviewWidget)

`ReportPreviewDialog` uzun süre yalnızca modal bir pencereydi. Bu widget aynı
milimetrik sayfa önizlemesini (araç çubuğu + sayfa navigasyonu + zoom + kaydırma
tuvali) bir ``QWidget`` olarak paketler; böylece:

* ``ReportPreviewDialog`` bu widget'ı sarar (davranış aynı kalır), ve
* evrak detay ekranının sağ paneline "canlı mini önizleme" olarak gömülebilir
  (``compact=True`` — yazdır/PDF butonları gizli, varsayılan zoom genişliğe sığdır).

Veriyi çalışırken yeniden beslemek için ``set_document(...)`` kullanılır.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QResizeEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

from src.desktop.designer.models import ReportTemplate
from src.desktop.designer.printer_engine import ReportPrinterEngine

logger = logging.getLogger(__name__)

_RENDER_DPI = 150.0


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
        painter.drawImage(self.rect(), self.page_image)


class ReportPreviewWidget(QWidget):
    """Gömülebilir milimetrik baskı önizleme paneli."""

    #: Compact modda yazdır/PDF butonları gizlidir; host kendi eylemini bağlayabilir.
    print_requested = pyqtSignal()
    pdf_requested = pyqtSignal()

    def __init__(
        self,
        template: ReportTemplate | None = None,
        data: dict[str, Any] | None = None,
        parent: QWidget | None = None,
        datas: list[dict[str, Any]] | None = None,
        compact: bool = False,
    ) -> None:
        super().__init__(parent)
        self.compact = compact
        self.template: ReportTemplate | None = None
        self.datas: list[dict[str, Any]] = []
        self.data: dict[str, Any] = {}
        self.engine: ReportPrinterEngine | None = None

        self.current_page_idx = 0
        self.rendered_pages: list[QImage] = []
        self.scale_factor = 1.0
        self.zoom_mode = "fit_width" if compact else "fit_page"

        self._init_ui()
        if template is not None:
            self.set_document(template, data=data, datas=datas)
        else:
            self._show_empty_state()

    # ------------------------------------------------------------------
    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        toolbar = QFrame(self)
        toolbar.setStyleSheet("QFrame { background-color: #1E293B; }")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(10, 5, 10, 5)
        tb.setSpacing(8)

        self.btn_print = QPushButton("🖨️ Yazdır", self)
        self.btn_print.setStyleSheet(
            "background-color: #2563EB; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px;",
        )
        self.btn_print.clicked.connect(self._on_print_clicked)

        self.btn_pdf = QPushButton("💾 PDF Kaydet", self)
        self.btn_pdf.setStyleSheet(
            "background-color: #16A34A; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px;",
        )
        self.btn_pdf.clicked.connect(self._on_pdf_save_clicked)

        tb.addWidget(self.btn_print)
        tb.addWidget(self.btn_pdf)
        tb.addSpacing(12)

        self.btn_prev = QPushButton("◀", self)
        self.btn_prev.setFixedWidth(32)
        self.btn_prev.clicked.connect(self._prev_page)
        tb.addWidget(self.btn_prev)

        self.lbl_page_info = QLabel("Sayfa 1 / 1", self)
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #F1F5F9; font-size: 11px;")
        tb.addWidget(self.lbl_page_info)

        self.btn_next = QPushButton("▶", self)
        self.btn_next.setFixedWidth(32)
        self.btn_next.clicked.connect(self._next_page)
        tb.addWidget(self.btn_next)

        tb.addSpacing(12)
        lbl_zoom = QLabel("Zoom:", self)
        lbl_zoom.setStyleSheet("color: #CBD5E1; font-size: 11px;")
        tb.addWidget(lbl_zoom)
        self.cmb_zoom = QComboBox(self)
        self.cmb_zoom.addItems([
            "📄 Sayfaya Sığdır (Tümünü Göster)",
            "↔️ Genişliğe Sığdır",
            "%25", "%35", "%50", "%75", "%100", "%125", "%150", "%200",
        ])
        self.cmb_zoom.setCurrentIndex(1 if self.compact else 0)
        self.cmb_zoom.currentTextChanged.connect(self._on_zoom_changed)
        tb.addWidget(self.cmb_zoom)

        tb.addStretch(1)
        self._toolbar_layout = tb
        main_layout.addWidget(toolbar)

        if self.compact:
            # Mini önizlemede yazdır/PDF host tarafında; burada gizli.
            self.btn_print.hide()
            self.btn_pdf.hide()

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
        main_layout.addWidget(self.scroll_area, 1)

    def add_toolbar_widget(self, widget: QWidget) -> None:
        """Araç çubuğunun sağ ucuna ek bir kontrol (örn. Kapat butonu) ekler."""
        self._toolbar_layout.addWidget(widget)

    # ------------------------------------------------------------------
    def set_document(
        self,
        template: ReportTemplate,
        data: dict[str, Any] | None = None,
        datas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Şablonu ve belge verisini (yeniden) yükleyip önizlemeyi çizer."""
        self.template = template
        if datas is not None:
            self.datas = list(datas)
        elif data is not None:
            self.datas = [data]
        else:
            self.datas = []
        self.data = self.datas[0] if self.datas else {}
        self.engine = ReportPrinterEngine(template)
        self._render_all_pages()
        self._apply_zoom_mode(self.zoom_mode)

    def _show_empty_state(self) -> None:
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        lbl = QLabel("Önizlenecek belge yok.", self)
        lbl.setStyleSheet("color: #E2E8F0; font-size: 12px; padding: 40px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas_layout.addWidget(lbl)
        self.lbl_page_info.setText("Sayfa 0 / 0")
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)

    # ------------------------------------------------------------------
    def _render_all_pages(self) -> None:
        self.rendered_pages.clear()
        if self.engine is None or self.template is None:
            return
        mm_to_px = _RENDER_DPI / 25.4
        w_px = int(self.template.page.width_mm * mm_to_px)
        h_px = int(self.template.page.height_mm * mm_to_px)

        page_images: list[QImage] = []

        def new_page_image() -> tuple[QImage, QPainter]:
            img = QImage(w_px, h_px, QImage.Format.Format_RGB32)
            img.fill(QColor("#FFFFFF"))
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            return img, p

        current_img, current_painter = new_page_image()
        page_images.append(current_img)

        def on_new_page():
            nonlocal current_img, current_painter
            current_painter.end()
            current_img, current_painter = new_page_image()
            page_images.append(current_img)

        docs = self.datas or ([self.data] if self.data else [])
        for doc_idx, doc_data in enumerate(docs):
            if doc_idx > 0:
                on_new_page()
            self.engine.render_document(
                current_painter, doc_data,
                target_device_dpi=_RENDER_DPI, new_page_callback=on_new_page,
            )
        current_painter.end()

        self.rendered_pages = page_images
        self.current_page_idx = 0

    def _calculate_fit_scale(self, mode: str) -> float:
        if not self.rendered_pages:
            return 1.0
        page_w = self.rendered_pages[0].width()
        page_h = self.rendered_pages[0].height()
        viewport = self.scroll_area.viewport()
        avail_w = max(100, viewport.width() - 40)
        avail_h = max(100, viewport.height() - 40)
        if mode == "fit_page":
            return min(avail_w / page_w, avail_h / page_h)
        if mode == "fit_width":
            return avail_w / page_w
        return 1.0

    def _apply_zoom_mode(self, mode: str) -> None:
        self.zoom_mode = mode
        if mode in ("fit_page", "fit_width"):
            self.scale_factor = self._calculate_fit_scale(mode)
        self._display_current_page()

    def _display_current_page(self) -> None:
        if not self.rendered_pages:
            return
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        total = len(self.rendered_pages)
        curr = self.current_page_idx
        self.lbl_page_info.setText(f"Sayfa {curr + 1} / {total}")
        self.btn_prev.setEnabled(curr > 0)
        self.btn_next.setEnabled(curr < total - 1)

        page_widget = PageViewWidget(
            self.rendered_pages[curr], scale_factor=self.scale_factor, parent=self,
        )
        page_widget.setStyleSheet("border: 1px solid #1E293B; background: white;")
        shadow = QGraphicsDropShadowEffect(page_widget)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 100))
        page_widget.setGraphicsEffect(shadow)
        self.canvas_layout.addWidget(page_widget)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.zoom_mode in ("fit_page", "fit_width") and self.rendered_pages:
            self.scale_factor = self._calculate_fit_scale(self.zoom_mode)
            self._display_current_page()

    def _prev_page(self) -> None:
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
            self._display_current_page()

    def _next_page(self) -> None:
        if self.current_page_idx < len(self.rendered_pages) - 1:
            self.current_page_idx += 1
            self._display_current_page()

    def _on_zoom_changed(self, text: str) -> None:
        if "Sayfaya Sığdır" in text:
            self._apply_zoom_mode("fit_page")
        elif "Genişliğe Sığdır" in text:
            self._apply_zoom_mode("fit_width")
        else:
            self.zoom_mode = "manual"
            try:
                self.scale_factor = float(text.replace("%", "").strip()) / 100.0
                self._display_current_page()
            except ValueError:
                pass

    # ------------------------------------------------------------------
    def _on_pdf_save_clicked(self) -> None:
        self.pdf_requested.emit()
        if self.engine is None:
            return
        belge_no = (self.data.get("belge", {}) or {}).get("teklif_no", "TEKLIF")
        file_path, _ = QFileDialog.getSaveFileName(
            self, "PDF Olarak Kaydet", f"{belge_no}_Teklif_Formu.pdf",
            "PDF Dosyaları (*.pdf)",
        )
        if not file_path:
            return
        if len(self.datas) > 1:
            ok = self.engine.export_many_to_pdf(self.datas, file_path)
        else:
            ok = self.engine.export_to_pdf(self.data, file_path)
        if ok:
            QMessageBox.information(self, "Başarılı", f"PDF kaydedildi:\n{file_path}")
        else:
            QMessageBox.critical(self, "Hata", "PDF oluşturulurken bir hata oluştu.")

    def _on_print_clicked(self) -> None:
        self.print_requested.emit()
        if self.engine is None:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Belgeyi Yazdır")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        painter = QPainter(printer)
        if not painter.isActive():
            return
        dpi = float(printer.resolution())
        for doc_idx, doc_data in enumerate(self.datas or [self.data]):
            if doc_idx > 0:
                printer.newPage()
            self.engine.render_document(
                painter, doc_data, target_device_dpi=dpi,
                new_page_callback=lambda: printer.newPage(),
            )
        painter.end()
        QMessageBox.information(self, "Yazdırıldı", "Belge(ler) yazıcıya gönderildi.")


def _demo_widget() -> ReportPreviewWidget:  # pragma: no cover - manuel deneme
    from src.desktop.designer.services.teklif_print_service import TeklifPrintService
    svc = TeklifPrintService()
    return ReportPreviewWidget(template=svc.get_template(), data=svc.get_demo_data())
