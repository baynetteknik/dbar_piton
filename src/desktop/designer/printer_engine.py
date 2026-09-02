"""
TOYA ERP - Vektörel Baskı & PDF Render Motoru (ReportPrinterEngine)
JSON şablonunu milimetrik hassasiyetle okur, verileri enjekte eder ve
QPainter / QPrinter ile vektörel PDF veya fiziksel yazıcı çıktısı üretir.
"""

from __future__ import annotations

import logging
from typing import Any
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter

from src.desktop.designer.models import BandConfig, ItemConfig, ReportTemplate
from src.desktop.designer.expression_engine import ExpressionEngine

logger = logging.getLogger(__name__)

MM_TO_PT = 72.0 / 25.4  # 1 mm = ~2.8346 pt


class ReportPrinterEngine:
    """Milimetrik form ve rapor çizim motoru."""

    def __init__(self, template: ReportTemplate) -> None:
        self.template = template
        self.expr = ExpressionEngine()

    def _setup_font(self, item: ItemConfig) -> QFont:
        font = QFont(item.font_family, item.font_size)
        font.setBold(item.font_bold)
        font.setItalic(item.font_italic)
        font.setUnderline(item.font_underline)
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
        page_no: int = 1,
        total_pages: int = 1,
    ) -> None:
        """Tek bir öğeyi milimetrik koordinatlarda çizer."""
        x = item.x_mm
        y = band_top_mm + item.y_mm
        w = item.w_mm
        h = item.h_mm

        rect = QRectF(x, y, w, h)

        # Arka plan dolgusu
        if item.bg_color:
            painter.fillRect(rect, QColor(item.bg_color))

        # Çerçeve ve Kenarlıklar
        pen = QPen(QColor(item.border_color), item.border_width / MM_TO_PT)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        if item.type == "box":
            if item.corner_radius > 0:
                painter.drawRoundedRect(rect, item.corner_radius, item.corner_radius)
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
            painter.setPen(QPen(QColor("#111827"), 0.5))
            painter.drawRect(rect)
            qr_font = QFont("Segoe UI", 6)
            painter.setFont(qr_font)
            val = str(self.expr.resolve_field(item.field, context) or item.text or "QR CODE")
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"[QR]\n{val[:12]}")
            return

        # Metin Çizimi
        text = self._resolve_item_text(item, context, page_no, total_pages)
        if not text:
            return

        painter.setFont(self._setup_font(item))
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
        text_rect = rect.adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawText(text_rect, flags, text)

    def render_band(
        self,
        painter: QPainter,
        band: BandConfig,
        current_y_mm: float,
        context: dict[str, Any],
        page_no: int,
        total_pages: int,
    ) -> float:
        """Bandı çizer ve bandın bittiği yeni Y koordinatını döner."""
        for item in band.items:
            self.render_item(painter, item, current_y_mm, context, page_no, total_pages)
        return current_y_mm + band.height_mm

    def render_document(
        self,
        painter: QPainter,
        data: dict[str, Any],
        target_device_dpi: float = 300.0,
        new_page_callback=None,
    ) -> int:
        """
        Belgeyi milimetrik olarak render eder.
        Sayfa sınırına geldiğinde new_page_callback çağrılır.
        Toplam üretilen sayfa sayısını döner.
        """
        # DPI'a göre milimetrik ölçekleme
        scale_factor = target_device_dpi / 25.4
        painter.save()
        painter.scale(scale_factor, scale_factor)

        # Şablon bantlarını grupla
        page_header_band = next((b for b in self.template.bands if b.type == "page_header"), None)
        header_group_band = next((b for b in self.template.bands if b.type == "header_group"), None)
        column_header_band = next((b for b in self.template.bands if b.type == "column_header"), None)
        detail_band = next((b for b in self.template.bands if b.type == "detail_data"), None)
        summary_band = next((b for b in self.template.bands if b.type == "report_summary"), None)
        page_footer_band = next((b for b in self.template.bands if b.type == "page_footer"), None)

        margin_top = self.template.page.margin_top_mm
        margin_bottom = self.template.page.margin_bottom_mm
        margin_left = self.template.page.margin_left_mm
        page_height = self.template.page.height_mm

        footer_height = page_footer_band.height_mm if page_footer_band else 0.0
        summary_height = summary_band.height_mm if summary_band else 0.0
        max_y = page_height - margin_bottom - footer_height

        # Veri satırları
        kalemler = data.get("kalemler", []) or data.get("lines", [])
        if not kalemler:
            kalemler = [{}]

        # 1. Aşama: Sayfa sayısını simüle et
        # (İki geçişli render: önce toplam sayfa bulunur, sonra çizilir)
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
                current_y = self.render_band(painter, page_header_band, current_y, data, page_no, total_pages)
            if page_no == 1 and header_group_band:
                current_y = self.render_band(painter, header_group_band, current_y, data, page_no, total_pages)
            if column_header_band:
                current_y = self.render_band(painter, column_header_band, current_y, data, page_no, total_pages)

        def draw_page_end():
            if page_footer_band:
                footer_y = page_height - margin_bottom - footer_height
                self.render_band(painter, page_footer_band, footer_y, data, page_no, total_pages)

        # İlk sayfa başlıkları
        draw_page_start()

        # Detay kalemleri
        for idx, row in enumerate(kalemler):
            # Tek bir satır için context
            row_context = dict(data)
            row_context["kalem"] = row
            if "sira_no" not in row:
                row["sira_no"] = idx + 1

            if current_y + detail_h > max_y:
                # Sayfa Altı bas
                draw_page_end()
                if new_page_callback:
                    painter.restore()
                    new_page_callback()
                    painter.save()
                    painter.scale(scale_factor, scale_factor)
                page_no += 1
                draw_page_start()

            if detail_band:
                current_y = self.render_band(painter, detail_band, current_y, row_context, page_no, total_pages)
            else:
                current_y += detail_h

        # Dip Toplam (Summary)
        if summary_band:
            if current_y + summary_height > max_y:
                draw_page_end()
                if new_page_callback:
                    painter.restore()
                    new_page_callback()
                    painter.save()
                    painter.scale(scale_factor, scale_factor)
                page_no += 1
                draw_page_start()
            current_y = self.render_band(painter, summary_band, current_y, data, page_no, total_pages)

        # Son sayfa footer'ı
        draw_page_end()

        painter.restore()
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
