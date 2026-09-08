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

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
DEFAULT_TEMPLATE_PATH = _TEMPLATES_DIR / "tpl_teklif_kurumsal_a4.json"

# Kağıt boyutuna göre hazır şablonlar (A4 kurumsal tasarımın ISO 216'daki standart
# %70.7 küçültme oranıyla A5'e ölçeklenmiş hali — bkz. tpl_teklif_kurumsal_a5.json).
# "PDF Yazdır (F9)" A4 üretmeye devam eder; A5 bunun yanına eklenen ek bir seçenektir.
PAGE_SIZE_TEMPLATES: dict[str, Path] = {
    "A4": DEFAULT_TEMPLATE_PATH,
    "A5": _TEMPLATES_DIR / "tpl_teklif_kurumsal_a5.json",
}


class TeklifPrintService:
    """Teklif belgeleri için görsel baskı önizleme ve PDF üretim servisi."""

    def __init__(
        self,
        db_session=None,
        template_path: Path | str | None = None,
        page_size: str = "A4",
    ) -> None:
        self.db = db_session
        if template_path:
            self.template_path = Path(template_path)
        else:
            key = (page_size or "A4").strip().upper()
            if key not in PAGE_SIZE_TEMPLATES:
                raise ValueError(
                    f"Bilinmeyen kağıt boyutu: {page_size!r}. "
                    f"Desteklenenler: {sorted(PAGE_SIZE_TEMPLATES)}",
                )
            self.template_path = PAGE_SIZE_TEMPLATES[key]
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
                # e-Belge / irsaliye alanları — teklif şablonu kullanmaz; fatura ve
                # irsaliye şablonları referans verir, kayıtsız kalınca boş basılır.
                "ettn": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "senaryo": "TEMEL FATURA",
                "fatura_tipi": "SATIŞ",
                "irsaliye_no": "IRS-2026-0451",
                "irsaliye_tarih": "02.09.2026",
                "siparis_no": "SIP-2026-0310",
                "sevk_adresi": "Organize Sanayi Bölgesi 4. Cadde No:18 Nilüfer / BURSA",
                "tasiyici": "TOYA Lojistik — 16 ABC 123",
                "saat": "14:35",
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

    def preview_with_data(
        self,
        data: dict[str, Any],
        parent: QWidget | None = None,
    ) -> int:
        """
        DB'ye gitmeden, çağıranın hazırladığı (örn. canlı belge detay ekranından
        toplanan) veri sözlüğü ile önizleme penceresini açar.
        """
        template = self.get_template()
        dialog = ReportPreviewDialog(template=template, data=data, parent=parent)
        return dialog.exec()

    def export_pdf(self, output_path: str | Path, teklif_id: int | None = None) -> bool:
        """Teklifi doğrudan PDF dosyası olarak dışa aktarır."""
        template = self.get_template()
        data = self.build_teklif_data(teklif_id)

        engine = ReportPrinterEngine(template)
        return engine.export_to_pdf(data, output_path)

    def export_pdf_with_data(
        self,
        data: dict[str, Any],
        output_path: str | Path,
    ) -> bool:
        """Hazır veri sözlüğünü doğrudan PDF dosyasına aktarır (DB'siz)."""
        template = self.get_template()
        engine = ReportPrinterEngine(template)
        return engine.export_to_pdf(data, output_path)

    # ---- Çoklu belge (toplu yazdırma / PDF / önizleme) ----------------
    def build_many_data(self, teklif_ids: list[int]) -> list[dict[str, Any]]:
        """Verilen tekliflerin her biri için baskı veri sözlüğü üretir."""
        return [self.build_teklif_data(tid) for tid in teklif_ids]

    def preview_many(
        self,
        teklif_ids: list[int],
        parent: QWidget | None = None,
    ) -> int:
        """Birden çok teklifi tek önizleme penceresinde (art arda) gösterir."""
        return self.preview_many_with_data(self.build_many_data(teklif_ids), parent)

    def preview_many_with_data(
        self,
        datas: list[dict[str, Any]],
        parent: QWidget | None = None,
    ) -> int:
        template = self.get_template()
        dialog = ReportPreviewDialog(template=template, datas=datas, parent=parent)
        return dialog.exec()

    def export_pdf_many(
        self,
        teklif_ids: list[int],
        output_path: str | Path,
    ) -> bool:
        """Birden çok teklifi tek bir PDF dosyasına (her biri yeni sayfadan) yazar."""
        template = self.get_template()
        engine = ReportPrinterEngine(template)
        return engine.export_many_to_pdf(self.build_many_data(teklif_ids), output_path)

    def export_each_pdf(
        self,
        teklif_ids: list[int],
        out_dir: str | Path,
        name_fn=None,
    ) -> list[Path]:
        """
        Her teklifi ayrı bir PDF dosyası olarak `out_dir` klasörüne kaydeder.
        `name_fn(data) -> str` verilmezse belge no'ya göre adlandırılır.
        Oluşturulan dosya yollarını döndürür.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        template = self.get_template()
        engine = ReportPrinterEngine(template)
        written: list[Path] = []
        for tid in teklif_ids:
            data = self.build_teklif_data(tid)
            if name_fn:
                stem = name_fn(data)
            else:
                stem = str(data.get("belge", {}).get("teklif_no") or f"belge_{tid}")
            safe = "".join(c for c in stem if c.isalnum() or c in " ._-").strip() or f"belge_{tid}"
            path = out_dir / f"{safe}.pdf"
            if engine.export_to_pdf(data, path):
                written.append(path)
        return written

    @staticmethod
    def available_templates() -> list[tuple[str, Path]]:
        """
        Seçilebilir hazır şablonların (başlık, yol) listesi. Görsel tasarımcı
        tamamlanana kadar kullanıcı buradan varsayılan dışında bir form seçebilir.
        """
        out: list[tuple[str, Path]] = []
        for path in sorted(_TEMPLATES_DIR.glob("tpl_*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    title = json.load(f).get("title") or path.stem
            except Exception:  # noqa: BLE001 - bozuk şablon listeyi düşürmesin
                title = path.stem
            out.append((str(title), path))
        return out
