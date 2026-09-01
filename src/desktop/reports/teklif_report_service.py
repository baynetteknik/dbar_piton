"""
ToyaUI — Teklif Raporlama Servisi
PDF, Excel, E-posta ve Paylaşım işlemlerini tek noktadan yönetir.

Kullanım:
    service = TeklifReportService(db_session=db)
    
    # PDF aç
    service.print_teklif(teklif_id=42)
    
    # PDF kaydet
    service.save_pdf(teklif_id=42, path="C:/teklifler/TEK-001.pdf")
    
    # Excel aç
    service.export_excel(teklif_id=42)
    
    # E-posta gönder
    service.send_email(teklif_id=42, to_email="musteri@example.com")
    
    # Paylaşım linki kopyala
    service.copy_share_link(teklif_id=42)
    
    # WhatsApp paylaş
    service.share_whatsapp(teklif_id=42)
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Motor importları
from src.desktop.reports.report_engine import ReportEngine
from src.desktop.reports.excel_engine  import ExcelEngine
from src.desktop.reports.email_engine  import EmailEngine, SMTPConfig
from src.desktop.reports.share_engine  import ShareEngine


class TeklifReportService:
    """Teklif modülü için tüm raporlama işlemlerini yöneten servis."""

    def __init__(
        self,
        db_session=None,
        smtp_config: SMTPConfig | None = None,
        base_url: str = "",
        company_id: int = 1,
    ):
        self.db         = db_session
        self.company_id = company_id

        self.pdf_engine   = ReportEngine()
        self.excel_engine = ExcelEngine()
        self.email_engine = EmailEngine(smtp_config or SMTPConfig.from_db(db_session))
        self.share_engine = ShareEngine(base_url=base_url, db_session=db_session)

    # ─────────────────────────────────────────────
    # VERİ HAZIRLIĞI
    # ─────────────────────────────────────────────

    def _build_teklif_data(self, teklif_id: int) -> dict[str, Any]:
        """
        DB'den teklif verisini çekip şablon için hazırlar.
        Demo verisi ile de çalışır (DB yoksa).
        """
        if not self.db:
            return self._demo_data()

        try:
            from sqlalchemy import select
            from src.core.models import Quotation, Customer, Product

            # Teklif
            q = self.db.scalar(
                select(Quotation).where(Quotation.id == teklif_id)
            )
            if not q:
                raise ValueError(f"Teklif bulunamadı: ID={teklif_id}")

            # Müşteri
            musteri_data = {}
            if hasattr(q, "customer_id") and q.customer_id:
                c = self.db.get(Customer, q.customer_id)
                if c:
                    musteri_data = {
                        "adi":         c.fullname or "",
                        "vergi_daire": getattr(c, "tax_office", "") or "",
                        "vergi_no":    c.tax_number or "",
                        "adres":       getattr(c, "address", "") or "",
                        "tel":         c.phone or "",
                        "email":       getattr(c, "email", "") or "",
                    }

            # Firma bilgileri (sistem ayarlarından)
            firma_data = self._get_firma_data()

            # Belge
            belge_data = {
                "teklif_no":   getattr(q, "quotation_number", "") or f"TEK-{q.id:04d}",
                "tarih":       getattr(q, "date", "") or "",
                "vade":        getattr(q, "valid_until", "") or "",
                "para_birimi": getattr(q, "currency", "TRY"),
                "durum":       getattr(q, "status", "Açık"),
                "odeme_plani": getattr(q, "payment_plan", "") or "",
                "aciklama":    getattr(q, "description", "") or "",
            }

            # Kalemler
            kalemler = []
            if hasattr(q, "lines"):
                for line in (q.lines or []):
                    kalemler.append({
                        "kod":        getattr(line, "sku", "") or "",
                        "aciklama":   getattr(line, "name", "") or "",
                        "not2":       getattr(line, "note2", "") or "",
                        "miktar":     float(getattr(line, "quantity", 1) or 1),
                        "birim":      getattr(line, "unit", "Adet") or "Adet",
                        "birim_fiyat":float(getattr(line, "unit_price", 0) or 0),
                        "iskonto":    float(getattr(line, "discount1", 0) or 0),
                        "kdv":        int(getattr(line, "vat_rate", 20) or 20),
                        "tutar":      float(getattr(line, "total_amount", 0) or 0),
                    })

            # Toplamlar
            toplamlar = {
                "ara_toplam":   float(getattr(q, "subtotal", 0) or 0),
                "iskonto":      float(getattr(q, "total_discount", 0) or 0),
                "masraflar":    float(getattr(q, "total_expense", 0) or 0),
                "kdv_matrahi":  float(getattr(q, "tax_base", 0) or 0),
                "kdv_toplam":   float(getattr(q, "total_vat", 0) or 0),
                "genel_toplam": float(getattr(q, "grand_total", 0) or 0),
            }

            return {
                "firma":     firma_data,
                "musteri":   musteri_data,
                "belge":     belge_data,
                "kalemler":  kalemler,
                "toplamlar": toplamlar,
                "notlar":    getattr(q, "notes", "") or "",
            }

        except Exception as e:
            logger.error(f"Teklif verisi hazırlanamadı: {e}")
            return self._demo_data()

    def _get_firma_data(self) -> dict[str, Any]:
        """Sistem ayarlarından firma bilgilerini çek."""
        try:
            from sqlalchemy import select
            from src.core.models import SystemSetting

            def get(key, default=""):
                row = self.db.scalar(
                    select(SystemSetting).where(SystemSetting.key == key)
                )
                return row.value if row else default

            return {
                "adi":    get("firma.adi", "BAYNET BİLİŞİM TEKNOLOJİLERİ"),
                "adres":  get("firma.adres", "Ankara"),
                "tel":    get("firma.tel", ""),
                "email":  get("firma.email", ""),
                "web":    get("firma.web", ""),
                "logo_base64": get("firma.logo_base64", ""),
            }
        except Exception:
            return {
                "adi":   "BAYNET BİLİŞİM TEKNOLOJİLERİ",
                "adres": "Ankara",
                "tel":   "", "email": "", "web": "",
                "logo_base64": "",
            }

    @staticmethod
    def _demo_data() -> dict[str, Any]:
        """Demo/test verisi."""
        return {
            "firma": {
                "adi":   "BAYNET BİLİŞİM TEKNOLOJİLERİ TAS. VE DAN. LTD.ŞTİ.",
                "adres": "Aşağı Eğlence Mah. Temizel Sokak 5/7 Etlik 06050 Keçiören / Ankara",
                "tel":   "0312 905 04 04",
                "email": "info@baynetbilisim.com.tr",
                "web":   "www.baynetbilisim.com.tr",
                "logo_base64": "",
            },
            "musteri": {
                "adi":         "TATU HIRDAVAT İÇ VE DIŞ TİC.LTD.ŞTİ",
                "vergi_daire": "Seyhan V.D.",
                "vergi_no":    "1234567896",
                "adres":       "Mersinli Mah. 2826 Sokak No:14/101 1.Sanayi Sitesi Adana",
                "tel":         "0322 000 0000",
                "email":       "info@tatu.com.tr",
            },
            "belge": {
                "teklif_no":   "TEK-2026-0013",
                "tarih":       "2026-08-29",
                "vade":        "2026-09-28",
                "para_birimi": "TRY ₺",
                "durum":       "Açık",
                "odeme_plani": "30 Gün Vade",
                "aciklama":    "",
            },
            "kalemler": [
                {
                    "kod": "STK-001", "aciklama": "VGA Sinyal Uzatma Kablosu 5M",
                    "not2": "1. Kalite Bakır İletken",
                    "miktar": 1.5, "birim": "Metre",
                    "birim_fiyat": 150.0, "iskonto": 0, "kdv": 20,
                    "tutar": 270.0,
                },
                {
                    "kod": "HZM-001", "aciklama": "Teknik Servis & Montaj Hizmeti",
                    "not2": "",
                    "miktar": 1, "birim": "Hizmet",
                    "birim_fiyat": 450.0, "iskonto": 10, "kdv": 20,
                    "tutar": 486.0,
                },
            ],
            "toplamlar": {
                "ara_toplam":   675.0,
                "iskonto":      45.0,
                "masraflar":    0.0,
                "kdv_matrahi":  630.0,
                "kdv_toplam":   126.0,
                "genel_toplam": 756.0,
            },
            "notlar": (
                "Banka: Garanti BBVA TR12 0006 2000 0001 2345 6789 01 - TL Hesabı\n"
                "Şartlar: Adana Mahkemeleri yetkilidir."
            ),
        }

    # ─────────────────────────────────────────────
    # PDF
    # ─────────────────────────────────────────────

    def print_teklif(self, teklif_id: int) -> str:
        """PDF üret ve sistem görüntüleyicide aç."""
        data = self._build_teklif_data(teklif_id)
        return self.pdf_engine.render_and_open(
            "teklif/teklif_print.html", data
        )

    def save_pdf(self, teklif_id: int, path: str | None = None) -> str:
        """PDF üret ve dosyaya kaydet."""
        data = self._build_teklif_data(teklif_id)
        teklif_no = data["belge"].get("teklif_no", f"TEK-{teklif_id:04d}")
        if not path:
            safe_no = teklif_no.replace("/", "-").replace(" ", "_")
            path = str(Path.home() / "Documents" / f"{safe_no}.pdf")
        return self.pdf_engine.render_and_save(
            "teklif/teklif_print.html", data, path
        )

    def get_pdf_bytes(self, teklif_id: int) -> bytes:
        """PDF bytes döndür (e-posta eki için)."""
        data = self._build_teklif_data(teklif_id)
        return self.pdf_engine.render_pdf("teklif/teklif_print.html", data)

    # ─────────────────────────────────────────────
    # EXCEL
    # ─────────────────────────────────────────────

    def export_excel(self, teklif_id: int, path: str | None = None) -> str:
        """Excel üret ve aç (veya kaydet)."""
        data = self._build_teklif_data(teklif_id)
        wb = self.excel_engine.render_teklif(data)
        if path:
            return self.excel_engine.save(wb, path)
        return self.excel_engine.open(wb)

    # ─────────────────────────────────────────────
    # E-POSTA
    # ─────────────────────────────────────────────

    def send_email(
        self,
        teklif_id: int,
        to_email: str | None = None,
        attach_pdf: bool = True,
        include_public_url: bool = True,
    ) -> tuple[bool, str]:
        """
        Teklif e-postası gönder.
        Dolibarr send_mail.php'nin Python versiyonu.
        """
        data = self._build_teklif_data(teklif_id)

        # E-posta adresi
        email = to_email or data["musteri"].get("email", "")
        if not email:
            return False, "Müşteri e-posta adresi bulunamadı."

        # PDF eki
        pdf_bytes = None
        if attach_pdf:
            try:
                pdf_bytes = self.get_pdf_bytes(teklif_id)
            except Exception as e:
                logger.warning(f"PDF eki oluşturulamadı: {e}")

        # Public URL (varsa)
        public_url = None
        if include_public_url:
            try:
                share_data = self.share_engine.get_share_data(teklif_id, data)
                public_url = share_data.get("public_url")
            except Exception:
                pass

        return self.email_engine.send_teklif_email(
            to_email=email,
            teklif_data=data,
            pdf_bytes=pdf_bytes,
            public_url=public_url,
        )

    # ─────────────────────────────────────────────
    # PAYLAŞIM
    # ─────────────────────────────────────────────

    def copy_share_link(self, teklif_id: int) -> str:
        """
        Paylaşım linkini oluştur ve panoya kopyala.
        Dolibarr'daki "Linki Kopyala" butonunun karşılığı.
        """
        data = self._build_teklif_data(teklif_id)
        share_data = self.share_engine.get_share_data(teklif_id, data)
        url = share_data["public_url"]
        self.share_engine.copy_to_clipboard(url)
        return url

    def share_whatsapp(self, teklif_id: int) -> bool:
        """
        WhatsApp ile paylaş.
        Dolibarr'daki "WhatsApp ile Gönder" butonunun karşılığı.
        """
        data = self._build_teklif_data(teklif_id)
        share_data = self.share_engine.get_share_data(teklif_id, data)
        return self.share_engine.share_whatsapp(
            url=share_data["public_url"],
            musteri_adi=share_data["musteri_adi"],
            teklif_no=share_data["teklif_no"],
            firma_adi=share_data["firma_adi"],
        )

    def get_share_data(self, teklif_id: int) -> dict[str, Any]:
        """Paylaşım dialog verilerini hazırla."""
        data = self._build_teklif_data(teklif_id)
        return self.share_engine.get_share_data(teklif_id, data)
