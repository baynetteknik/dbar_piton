"""
TOYA ERP - Teklif Formu Baskı ve Önizleme Servisi (TeklifPrintService)
Mevcut UI kodlarına zarar vermeden, tamamen izole olarak çalışır.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QWidget

from src.desktop.designer.models import ReportTemplate
from src.desktop.designer.preview_dialog import ReportPreviewDialog
from src.desktop.designer.printer_engine import ReportPrinterEngine

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PATH = (
    Path(__file__).parent.parent / "templates" / "tpl_teklif_kurumsal_a4.json"
)


class TeklifPrintService:
    """Teklif belgeleri için görsel baskı önizleme ve PDF üretim servisi."""

    def __init__(self, db_session=None, template_path: Path | str | None = None) -> None:
        self.db = db_session
        self.template_path = Path(template_path) if template_path else DEFAULT_TEMPLATE_PATH
        self._template: ReportTemplate | None = None

    def get_template(self) -> ReportTemplate:
        """JSON şablonunu okur ve ReportTemplate modeline dönüştürür."""
        if self._template is None:
            if not self.template_path.exists():
                raise FileNotFoundError(f"Teklif şablonu bulunamadı: {self.template_path}")
            with open(self.template_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            self._template = ReportTemplate.from_dict(d)
        return self._template

    def build_teklif_data(self, teklif_id: int | None = None) -> dict[str, Any]:
        """
        Teklif verisini hazırlar. Veritabanı oturumu varsa DB'den okur,
        yoksa zengin kurumsal demo verisi döner.
        """
        if self.db and teklif_id is not None:
            try:
                # Mevcut TeklifReportService içindeki veri hazırlık mantığını kullan
                from src.desktop.reports.teklif_report_service import TeklifReportService
                legacy_service = TeklifReportService(db_session=self.db)
                return legacy_service._build_teklif_data(teklif_id)
            except Exception as e:
                logger.warning(f"DB'den teklif verisi okunamadı, demo veri kullanılıyor: {e}")

        return self.get_demo_data()

    @staticmethod
    def get_demo_data() -> dict[str, Any]:
        """Test ve bağımsız çalıştırma için zengin kurumsal teklif verisi."""
        return {
            "firma": {
                "unvan": "TOYA TEKNOLOJİ VE BİLİŞİM SİSTEMLERİ A.Ş.",
                "adres": "Maslak Mah. Büyükdere Cad. No:123 Sarıyer / İSTANBUL",
                "vergi_daire": "Maslak",
                "vergi_no": "8520147963",
                "tel": "+90 (212) 555 01 00",
                "email": "info@toyaerp.com",
            },
            "musteri": {
                "adi": "ACME ENDÜSTRİYEL ÜRETİM VE TİCARET A.Ş.",
                "yetkili": "Sn. Mehmet Özkan (Satınalma Müdürü)",
                "adres": "Organize Sanayi Bölgesi 4. Cadde No:18 Nilüfer / BURSA",
                "vergi_daire": "Nilüfer",
                "vergi_no": "1234567890",
                "tel": "+90 (224) 444 02 16",
                "email": "satinalma@acme.com.tr",
            },
            "belge": {
                "teklif_no": "TK-2026-0089",
                "tarih": "02.09.2026",
                "vade": "17.09.2026",
                "para_birimi": "TL",
                "durum": "Onay Bekliyor",
                "odeme_plani": "30 Gün Vadeli",
                "aciklama": "Kurumsal ERP ve Barkod Otomasyon Sistemi Kurulum Teklifi",
            },
            "kalemler": [
                {
                    "sira_no": 1,
                    "kod": "SFT-ERP-01",
                    "aciklama": "TOYA ERP Kurumsal Sunucu Lisansı (5 Kullanıcı)",
                    "miktar": 1.0,
                    "birim": "Adet",
                    "birim_fiyat": 45000.0,
                    "iskonto": 10.0,
                    "kdv": 20,
                    "tutar": 40500.0,
                },
                {
                    "sira_no": 2,
                    "kod": "SRV-INS-02",
                    "aciklama": "Sistem Kurulumu, Veritabanı Konfigürasyonu & Eğitim",
                    "miktar": 3.0,
                    "birim": "Gün",
                    "birim_fiyat": 8500.0,
                    "iskonto": 0.0,
                    "kdv": 20,
                    "tutar": 25500.0,
                },
                {
                    "sira_no": 3,
                    "kod": "HDW-PRN-05",
                    "aciklama": "Endüstriyel Termal Barkod Yazıcı (Zebra ZT230)",
                    "miktar": 2.0,
                    "birim": "Adet",
                    "birim_fiyat": 16500.0,
                    "iskonto": 5.0,
                    "kdv": 20,
                    "tutar": 31350.0,
                },
                {
                    "sira_no": 4,
                    "kod": "HDW-TRM-12",
                    "aciklama": "Android El Terminali 2D Barkod Okuyuculu (Datalogic)",
                    "miktar": 4.0,
                    "birim": "Adet",
                    "birim_fiyat": 12000.0,
                    "iskonto": 8.0,
                    "kdv": 20,
                    "tutar": 44160.0,
                },
            ],
            "toplamlar": {
                "ara_toplam": 149500.0,
                "iskonto": 7990.0,
                "kdv_matrahi": 141510.0,
                "kdv_toplam": 28302.0,
                "genel_toplam": 169812.0,
            },
            "notlar": "1. Fiyatlarımıza %20 KDV dahil değildir.\n2. Teklifimiz hazırlandığı tarihten itibaren 15 gün süreyle geçerlidir.\n3. Donanım teslimatı sipariş onayından sonra 3 iş günü içinde yapılacaktır.\n4. Ödemeler Garanti BBVA Maslak Şubesi TR45 0006 2000 0001 2345 6789 01 nolu hesabımıza yapılacaktır.",
        }

    def show_preview(self, teklif_id: int | None = None, parent: QWidget | None = None) -> int:
        """Baskı Önizleme Penceresini ekranda açar."""
        template = self.get_template()
        data = self.build_teklif_data(teklif_id)

        dialog = ReportPreviewDialog(template=template, data=data, parent=parent)
        return dialog.exec()

    def export_pdf(self, output_path: str | Path, teklif_id: int | None = None) -> bool:
        """Teklifi doğrudan PDF dosyası olarak dışa aktarır."""
        template = self.get_template()
        data = self.build_teklif_data(teklif_id)

        engine = ReportPrinterEngine(template)
        return engine.export_to_pdf(data, output_path)
