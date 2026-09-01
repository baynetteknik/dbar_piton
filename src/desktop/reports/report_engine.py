"""
ToyaUI — Raporlama Motoru
WeasyPrint + Jinja2 ile PDF üretimi.

Kullanım:
    engine = ReportEngine()
    pdf_bytes = engine.render_pdf("teklif/teklif_print.html", data)
    engine.save_pdf(pdf_bytes, "/path/to/output.pdf")
    engine.open_pdf(pdf_bytes)  # Sistem PDF görüntüleyici ile aç
"""

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Windows ortamında WeasyPrint için GTK/Pango kütüphane yollarını otomatik tespit et
if sys.platform == "win32":
    potential_dll_dirs = [
        os.environ.get("WEASYPRINT_DLL_DIRECTORIES", ""),
        r"C:\msys64\mingw64\bin",
        r"C:\msys64\ucrt64\bin",
        r"C:\msys64\clang64\bin",
        r"C:\Program Files\GTK3-Runtime Win64\bin",
        r"C:\GTK3\bin",
        r"C:\GTK\bin",
    ]
    for dll_dir in potential_dll_dirs:
        if dll_dir and os.path.isdir(dll_dir):
            try:
                os.add_dll_directory(dll_dir)
                if "WEASYPRINT_DLL_DIRECTORIES" not in os.environ:
                    os.environ["WEASYPRINT_DLL_DIRECTORIES"] = dll_dir
            except Exception:
                pass

# Jinja2 ve WeasyPrint import
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    JINJA2_OK = True
except ImportError:
    JINJA2_OK = False
    logger.warning("jinja2 bulunamadı: pip install jinja2")

try:
    import io
    _orig_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        from weasyprint import HTML

        WEASYPRINT_OK = True
    finally:
        sys.stderr = _orig_stderr
except (ImportError, OSError, Exception):
    WEASYPRINT_OK = False
    logger.info(
        "WeasyPrint veya GTK kütüphaneleri bulunamadı; "
        "PyQt6 PDF motoru devrede.",
    )


# Şablon klasörü — bu dosyanın yanında templates/ klasörü
TEMPLATES_DIR = Path(__file__).parent / "templates"


class ReportEngine:
    """Jinja2 + WeasyPrint tabanlı PDF raporlama motoru."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        if JINJA2_OK:
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(self.templates_dir)),
                autoescape=select_autoescape(["html", "xml"]),
            )
            # Özel filtreler
            self.jinja_env.filters["currency"] = self._fmt_currency
            self.jinja_env.filters["date_tr"] = self._fmt_date
            self.jinja_env.filters["percent"] = self._fmt_percent
        else:
            self.jinja_env = None

    # ─────────────────────────────────────────────
    # YARDIMCI FONKSİYONLAR
    # ─────────────────────────────────────────────

    @staticmethod
    def _fmt_currency(value: Any, symbol: str = "₺", decimals: int = 2) -> str:
        """Sayıyı para formatına çevirir: 1234.5 → 1.234,50 ₺"""
        try:
            v = float(value or 0)
            formatted = (
                f"{v:,.{decimals}f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
            return f"{formatted} {symbol}"
        except Exception:
            return f"0,00 {symbol}"

    @staticmethod
    def _fmt_date(value: Any) -> str:
        """Tarihi Türkçe formatlar: 2026-08-29 → 29.08.2026"""
        try:
            from datetime import date, datetime

            if isinstance(value, (datetime, date)):
                return value.strftime("%d.%m.%Y")
            if isinstance(value, str) and value:
                return datetime.strptime(
                    value[:10], "%Y-%m-%d",
                ).strftime("%d.%m.%Y")
        except Exception:
            pass
        return str(value or "")

    @staticmethod
    def _fmt_percent(value: Any, decimals: int = 0) -> str:
        """Yüzde formatlar: 20 → %20"""
        try:
            return f"%{float(value or 0):.{decimals}f}"
        except Exception:
            return "%0"

    # ─────────────────────────────────────────────
    # HTML RENDER
    # ─────────────────────────────────────────────

    def render_html(self, template_name: str, data: dict[str, Any]) -> str:
        """Jinja2 şablonunu veriyle render et, HTML string döndür."""
        if not JINJA2_OK or not self.jinja_env:
            raise RuntimeError("jinja2 yüklü değil: pip install jinja2")

        template = self.jinja_env.get_template(template_name)
        return template.render(**data)

    # ─────────────────────────────────────────────
    # PDF ÜRET
    # ─────────────────────────────────────────────

    def render_pdf(self, template_name: str, data: dict[str, Any]) -> bytes:
        """Şablonu render et ve PDF bytes döndür."""
        html_content = self.render_html(template_name, data)
        base_url = str(self.templates_dir / template_name.split("/")[0])

        if WEASYPRINT_OK:
            try:
                pdf = HTML(string=html_content, base_url=base_url).write_pdf()
                return pdf
            except Exception as e:
                logger.warning(
                    f"WeasyPrint PDF rendering failed, trying Qt fallback: {e}",
                )

        # Fallback to PyQt6
        try:
            from PyQt6.QtCore import QMarginsF, QSizeF
            from PyQt6.QtGui import QPageSize, QPdfWriter, QTextDocument

            doc = QTextDocument()
            doc.setHtml(html_content)
            doc.setPageSize(QSizeF(595, 842))

            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp.close()

            writer = QPdfWriter(tmp.name)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageMargins(QMarginsF(10, 10, 10, 10))
            doc.print(writer)

            with open(tmp.name, "rb") as f:
                pdf_data = f.read()
            try:
                os.remove(tmp.name)
            except Exception:
                pass
            return pdf_data
        except Exception as e:
            logger.error(f"PDF rendering failed: {e}")
            raise RuntimeError(f"PDF oluşturulamadı: {e}") from e

    def save_pdf(self, pdf_bytes: bytes, output_path: str) -> str:
        """PDF'i dosyaya kaydet."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"PDF kaydedildi: {path}")
        return str(path)

    def open_pdf(self, pdf_bytes: bytes) -> str:
        """PDF'i geçici dosyaya yaz ve sistem görüntüleyici ile aç."""
        tmp = tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, prefix="toya_",
        )
        tmp.write(pdf_bytes)
        tmp.close()

        if sys.platform == "win32":
            os.startfile(tmp.name)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", tmp.name])
        else:
            subprocess.Popen(["xdg-open", tmp.name])

        return tmp.name

    def render_and_open(self, template_name: str, data: dict[str, Any]) -> str:
        """Render et ve PDF'i sistem görüntüleyicide aç. Geçici dosya yolunu döndür."""
        pdf_bytes = self.render_pdf(template_name, data)
        return self.open_pdf(pdf_bytes)

    def render_and_save(
        self,
        template_name: str,
        data: dict[str, Any],
        output_path: str,
    ) -> str:
        """Render et ve dosyaya kaydet. Dosya yolunu döndür."""
        pdf_bytes = self.render_pdf(template_name, data)
        return self.save_pdf(pdf_bytes, output_path)
