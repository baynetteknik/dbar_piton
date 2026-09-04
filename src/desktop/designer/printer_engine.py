"""
TOYA ERP - Vektörel Baskı & PDF Render Motoru (ReportPrinterEngine)
JSON şablonunu milimetrik hassasiyetle okur, DPI bazlı piksel hesaplamasıyla
QPainter / QPrinter ile vektörel PDF veya fiziksel yazıcı çıktısı üretir.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter

from src.desktop.designer.models import BandConfig, ItemConfig, ReportTemplate
from src.desktop.designer.expression_engine import ExpressionEngine

logger = logging.getLogger(__name__)


class ReportPrinterEngine:
    """Milimetrik form ve rapor çizim motoru."""

    def __init__(self, template: ReportTemplate) -> None:
        self.template = template
        self.expr = ExpressionEngine()

    def _setup_font(self, item: ItemConfig, dpi: float) -> QFont:
        font = QFont(item.font_family)
        font.setBold(item.font_bold)
        font.setItalic(item.font_italic)
        font.setUnderline(item.font_underline)
        # Font boyutu: point -> pixel dönüşümü
        font_px = max(1, int(round(item.font_size * (dpi / 72.0))))
        font.setPixelSize(font_px)
        return font

    def _resolve_item_text(self, item: ItemConfig, context: dict[str, Any], page_no: int, total_pages: int) -> str:
        """Öğenin basılacak metin içeriğini belirler."""
        if item.type == "text" or item.type == "label":
            return item.text

        elif item.type == "data_field":
            val = self.expr.resolve_field(item.field, context)
            return self.expr.format_value(val, item.format, item.format_mask)

        elif item.type == "expression":
            return self.expr.evaluate_expression(item.expression, context)

        elif item.type == "system_var":
            if "page" in item.field.lower():
                return f"Sayfa {page_no} / {total_pages}"
            elif "date" in item.field.lower():
                from datetime import datetime
                return datetime.now().strftime("%d.%m.%Y %H:%M")
            return item.text

        return item.text

    def render_item(
        self,
        painter: QPainter,
        item: ItemConfig,
        band_top_mm: float,
        context: dict[str, Any],
        dpi: float,
        page_no: int = 1,
        total_pages: int = 1,
    ) -> None:
        """Tek bir öğeyi DPI bazlı piksel koordinatlarında çizer."""
        mm_to_px = dpi / 25.4
        pt_to_px = dpi / 72.0

        x = item.x_mm * mm_to_px
        y = (band_top_mm + item.y_mm) * mm_to_px
        w = item.w_mm * mm_to_px
        h = item.h_mm * mm_to_px

        rect = QRectF(x, y, w, h)

        # Arka plan dolgusu
        if item.bg_color:
            painter.fillRect(rect, QColor(item.bg_color))

        # Çerçeve ve Kenarlıklar
        border_px = max(1.0, item.border_width * pt_to_px)
        pen = QPen(QColor(item.border_color), border_px)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        if item.type == "box":
            if item.corner_radius > 0:
                rad_px = item.corner_radius * mm_to_px
                painter.drawRoundedRect(rect, rad_px, rad_px)
            else:
                painter.drawRect(rect)
            return

        if item.type == "line":
            painter.drawLine(QPointF(x, y), QPointF(x + w, y + h))
            return

        # Kenarlık çizgileri
        if item.border_top:
            painter.drawLine(QPointF(x, y), QPointF(x + w, y))
        if item.border_bottom:
            painter.drawLine(QPointF(x, y + h), QPointF(x + w, y + h))
        if item.border_left:
            painter.drawLine(QPointF(x, y), QPointF(x, y + h))
        if item.border_right:
            painter.drawLine(QPointF(x + w, y), QPointF(x + w, y + h))

        # Resim / Logo çizimi
        if item.type == "image":
            img_src = item.image_path or str(self.expr.resolve_field(item.field, context) or "")
            if img_src and Path(img_src).exists():
                pix = QPixmap(img_src)
                if not pix.isNull():
                    painter.drawPixmap(rect.toRect(), pix)
            return

        # Barkod / QR Kod çizimi (Yer tutucu veya vektörel kutu)
        if item.type == "barcode":
            painter.fillRect(rect, QColor("#F3F4F6"))
            painter.setPen(QPen(QColor("#111827"), 1.0))
            painter.drawRect(rect)
            qr_font = QFont("Segoe UI")
            qr_font.setPixelSize(max(1, int(round(7 * pt_to_px))))
            painter.setFont(qr_font)
            val = str(self.expr.resolve_field(item.field, context) or item.text or "QR CODE")
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"[QR]\n{val[:12]}")
            return

        # Metin Çizimi
        text = self._resolve_item_text(item, context, page_no, total_pages)
        if not text:
            return

        painter.setFont(self._setup_font(item, dpi))
        painter.setPen(QPen(QColor(item.text_color)))

        # Hizalama
        flags = 0
        if item.align == "center":
            flags |= Qt.AlignmentFlag.AlignHCenter
        elif item.align == "right":
            flags |= Qt.AlignmentFlag.AlignRight
        else:
            flags |= Qt.AlignmentFlag.AlignLeft

        if item.valign == "top":
            flags |= Qt.AlignmentFlag.AlignTop
        elif item.valign == "bottom":
            flags |= Qt.AlignmentFlag.AlignBottom
        else:
            flags |= Qt.AlignmentFlag.AlignVCenter

        if item.word_wrap or item.can_grow:
            flags |= Qt.TextFlag.TextWordWrap

        # Padding (küçük boşluk)
        pad_px = 1.0 * pt_to_px
        text_rect = rect.adjusted(pad_px, pad_px, -pad_px, -pad_px)
        painter.drawText(text_rect, flags, text)

    def render_band(
        self,
        painter: QPainter,
        band: BandConfig,
        current_y_mm: float,
        context: dict[str, Any],
        dpi: float,
        page_no: int,
        total_pages: int,
    ) -> float:
        """Bandı çizer ve bandın bittiği yeni Y koordinatını döner."""
        for item in band.items:
            self.render_item(painter, item, current_y_mm, context, dpi, page_no, total_pages)
        return current_y_mm + band.height_mm

    def render_document(
        self,
        painter: QPainter,
        data: dict[str, Any],
        target_device_dpi: float = 150.0,
        new_page_callback=None,
    ) -> int:
        """
        Belgeyi milimetrik olarak render eder.
        DPI bazlı piksel hesaplama kullandığı için painter.scale yapmaz,
        böylece fontlar ve çizgiler tam oranında, net ve bozulmadan çizilir.
        """
        dpi = target_device_dpi

        # Şablon bantlarını grupla
        page_header_band = next((b for b in self.template.bands if b.type == "page_header"), None)
        header_group_band = next((b for b in self.template.bands if b.type == "header_group"), None)
        column_header_band = next((b for b in self.template.bands if b.type == "column_header"), None)
        detail_band = next((b for b in self.template.bands if b.type == "detail_data"), None)
        summary_band = next((b for b in self.template.bands if b.type == "report_summary"), None)
        page_footer_band = next((b for b in self.template.bands if b.type == "page_footer"), None)

        margin_top = self.template.page.margin_top_mm
        margin_bottom = self.template.page.margin_bottom_mm
        page_height = self.template.page.height_mm

        footer_height = page_footer_band.height_mm if page_footer_band else 0.0
        summary_height = summary_band.height_mm if summary_band else 0.0
        max_y = page_height - margin_bottom - footer_height

        # Veri satırları
        kalemler = data.get("kalemler", []) or data.get("lines", [])
        if not kalemler:
            kalemler = [{}]

        # 1. Aşama: Sayfa sayısını hesapla
        total_pages = 1
        test_y = margin_top
        if page_header_band:
            test_y += page_header_band.height_mm
        if header_group_band:
            test_y += header_group_band.height_mm
        if column_header_band:
            test_y += column_header_band.height_mm

        detail_h = detail_band.height_mm if detail_band else 8.0
        for _ in kalemler:
            if test_y + detail_h > max_y:
                total_pages += 1
                test_y = margin_top
                if page_header_band:
                    test_y += page_header_band.height_mm
                if column_header_band:
                    test_y += column_header_band.height_mm
            test_y += detail_h

        # Dip toplam sığıyor mu?
        if test_y + summary_height > max_y:
            total_pages += 1

        # 2. Aşama: Gerçek Çizim
        page_no = 1
        current_y = margin_top

        def draw_page_start():
            nonlocal current_y
            current_y = margin_top
            if page_header_band:
                current_y = self.render_band(painter, page_header_band, current_y, data, dpi, page_no, total_pages)
            if page_no == 1 and header_group_band:
                current_y = self.render_band(painter, header_group_band, current_y, data, dpi, page_no, total_pages)
            if column_header_band:
                current_y = self.render_band(painter, column_header_band, current_y, data, dpi, page_no, total_pages)

        def draw_page_end():
            if page_footer_band:
                footer_y = page_height - margin_bottom - footer_height
                self.render_band(painter, page_footer_band, footer_y, data, dpi, page_no, total_pages)

        # İlk sayfa başlıkları
        draw_page_start()

        # Detay kalemleri
        for idx, row in enumerate(kalemler):
            row_context = dict(data)
            row_context["kalem"] = row
            if "sira_no" not in row:
                row["sira_no"] = idx + 1

            if current_y + detail_h > max_y:
                draw_page_end()
                if new_page_callback:
                    new_page_callback()
                page_no += 1
                draw_page_start()

            if detail_band:
                current_y = self.render_band(painter, detail_band, current_y, row_context, dpi, page_no, total_pages)
            else:
                current_y += detail_h

        # Dip Toplam (Summary)
        if summary_band:
            if current_y + summary_height > max_y:
                draw_page_end()
                if new_page_callback:
                    new_page_callback()
                page_no += 1
                draw_page_start()
            current_y = self.render_band(painter, summary_band, current_y, data, dpi, page_no, total_pages)

        # Son sayfa footer'ı
        draw_page_end()

        return total_pages

    def export_to_pdf(self, data: dict[str, Any], output_pdf_path: str | Path) -> bool:
        """Şablonu ve veriyi vektörel PDF dosyası olarak kaydeder."""
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(str(output_pdf_path))

            # Kağıt ayarları
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(
                QPageLayout.Orientation.Portrait
                if self.template.page.orientation == "portrait"
                else QPageLayout.Orientation.Landscape
            )
            printer.setFullPage(True)

            painter = QPainter(printer)
            if not painter.isActive():
                logger.error("QPainter başlatılamadı.")
                return False

            dpi = float(printer.resolution())

            def on_new_page():
                printer.newPage()

            self.render_document(painter, data, target_device_dpi=dpi, new_page_callback=on_new_page)
            painter.end()
            return True

        except Exception as e:
            logger.error(f"PDF üretim hatası: {e}", exc_info=True)
            return False
