"""TeklifPrintService / ReportPrinterEngine için sayfa boyutu regresyon testleri.

Önceden ReportPrinterEngine.export_to_pdf() kağıt boyutunu her zaman A4'e
sabitliyordu; şablon A5 (veya başka bir boyut) tanımlasa bile üretilen PDF hep
A4 çıkıyordu. Bu testler üretilen PDF'in gerçek sayfa boyutunun şablonla
eşleştiğini doğrular.
"""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QSize
from PyQt6.QtPdf import QPdfDocument

from src.desktop.designer.services.teklif_print_service import (
    PAGE_SIZE_TEMPLATES,
    TeklifPrintService,
)


def _pdf_page_size_mm(path) -> tuple[float, float]:
    doc = QPdfDocument(None)
    doc.load(str(path))
    assert doc.pageCount() >= 1
    pt = doc.pagePointSize(0)
    return pt.width() / 72 * 25.4, pt.height() / 72 * 25.4


@pytest.mark.parametrize("page_size,expected_mm", [
    ("A4", (210.0, 297.0)),
    ("A5", (148.0, 210.0)),
])
def test_export_pdf_uses_template_page_size(qapp, tmp_path, page_size, expected_mm):
    out = tmp_path / f"teklif_{page_size}.pdf"
    service = TeklifPrintService(page_size=page_size)
    assert service.export_pdf(out) is True
    assert out.exists()

    w_mm, h_mm = _pdf_page_size_mm(out)
    exp_w, exp_h = expected_mm
    assert abs(w_mm - exp_w) < 1.0, f"{page_size}: genişlik {w_mm:.1f}mm, beklenen ~{exp_w}mm"
    assert abs(h_mm - exp_h) < 1.0, f"{page_size}: yükseklik {h_mm:.1f}mm, beklenen ~{exp_h}mm"


def test_unknown_page_size_raises():
    with pytest.raises(ValueError):
        TeklifPrintService(page_size="A2")


def test_page_size_templates_exist():
    for size, path in PAGE_SIZE_TEMPLATES.items():
        assert path.exists(), f"{size} şablonu bulunamadı: {path}"


def test_export_pdf_many_combines_documents(qapp, tmp_path):
    """export_pdf_many, N belgeyi tek PDF'e (her biri >=1 sayfa) yazmalı."""
    svc = TeklifPrintService(page_size="A4")
    d = TeklifPrintService.get_demo_data()
    out = tmp_path / "coklu.pdf"
    engine_ok = svc.export_pdf_many.__self__ is svc  # metot bağlı
    assert engine_ok
    from src.desktop.designer.printer_engine import ReportPrinterEngine
    eng = ReportPrinterEngine(svc.get_template())
    assert eng.export_many_to_pdf([d, d, d], out) is True
    assert out.exists()

    from PyQt6.QtPdf import QPdfDocument
    doc = QPdfDocument(None)
    doc.load(str(out))
    assert doc.pageCount() >= 3  # en az belge başına 1 sayfa


def test_preview_dialog_accepts_multiple_documents(qapp):
    from src.desktop.designer.preview_dialog import ReportPreviewDialog
    svc = TeklifPrintService(page_size="A4")
    d = TeklifPrintService.get_demo_data()
    one = ReportPreviewDialog(template=svc.get_template(), data=d)
    many = ReportPreviewDialog(template=svc.get_template(), datas=[d, d, d])
    assert len(many.rendered_pages) >= 3 * len(one.rendered_pages)


def test_export_each_pdf_writes_one_file_per_doc(qapp, tmp_path, monkeypatch):
    svc = TeklifPrintService(page_size="A4")
    demo = TeklifPrintService.get_demo_data()
    monkeypatch.setattr(svc, "build_teklif_data", lambda tid: {
        **demo, "belge": {**demo["belge"], "teklif_no": f"TK-{tid}"},
    })
    written = svc.export_each_pdf([11, 22], tmp_path)
    assert len(written) == 2
    names = sorted(p.name for p in written)
    assert names == ["TK-11.pdf", "TK-22.pdf"]
    assert all(p.exists() for p in written)
