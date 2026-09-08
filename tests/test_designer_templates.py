"""Hazır belge şablonları — fatura (karekodlu), sevk irsaliyesi, 80mm termal fiş.

Şablonların geçerli JSON olduğunu, motorun beklediği bantları içerdiğini ve
`ReportPrinterEngine` ile şablonun tanımladığı kağıt boyutunda PDF ürettiğini
doğrular.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PyQt6.QtPdf import QPdfDocument

from src.desktop.designer.models import ReportTemplate
from src.desktop.designer.printer_engine import ReportPrinterEngine
from src.desktop.designer.services.teklif_print_service import TeklifPrintService

_TPL_DIR = Path("src/desktop/designer/templates")

NEW_TEMPLATES = {
    "tpl_fatura_kurumsal_a4": (210.0, 297.0),
    "tpl_irsaliye_kurumsal_a4": (210.0, 297.0),
    "tpl_perakende_fis_80mm": (80.0, 200.0),
}


@pytest.fixture
def demo_data():
    d = TeklifPrintService.get_demo_data()
    for k in d["kalemler"]:
        k.setdefault("iskonto", 0.0)
    return d


@pytest.mark.parametrize("tpl_id", list(NEW_TEMPLATES))
def test_template_parses_and_has_core_bands(tpl_id):
    d = json.loads((_TPL_DIR / f"{tpl_id}.json").read_text(encoding="utf-8"))
    tpl = ReportTemplate.from_dict(d)
    assert tpl.template_id == tpl_id
    band_types = {b.type for b in tpl.bands}
    # motorun render_document'ta aradığı asgari bantlar
    assert {"page_header", "column_header", "detail_data", "report_summary"} <= band_types
    detail = next(b for b in tpl.bands if b.type == "detail_data")
    assert any(it.field.startswith("kalem.") for it in detail.items)


@pytest.mark.parametrize("tpl_id,expected_mm", list(NEW_TEMPLATES.items()))
def test_template_pdf_page_size(qapp, tmp_path, demo_data, tpl_id, expected_mm):
    d = json.loads((_TPL_DIR / f"{tpl_id}.json").read_text(encoding="utf-8"))
    tpl = ReportTemplate.from_dict(d)
    out = tmp_path / f"{tpl_id}.pdf"
    assert ReportPrinterEngine(tpl).export_to_pdf(demo_data, out) is True
    assert out.exists()

    doc = QPdfDocument(None)
    doc.load(str(out))
    assert doc.pageCount() >= 1
    pt = doc.pagePointSize(0)
    w_mm, h_mm = pt.width() / 72 * 25.4, pt.height() / 72 * 25.4
    assert abs(w_mm - expected_mm[0]) < 1.5
    assert abs(h_mm - expected_mm[1]) < 1.5


def test_new_templates_listed_in_available_templates(qapp):
    titles = {t for t, _ in TeklifPrintService.available_templates()}
    paths = {Path(p).stem for _, p in TeklifPrintService.available_templates()}
    assert NEW_TEMPLATES.keys() <= paths
    assert any("Fatura" in t for t in titles)
    assert any("İrsaliye" in t for t in titles)
    assert any("Fiş" in t for t in titles)


def test_fis_80mm_resolves_custom_page_size(qapp):
    d = json.loads((_TPL_DIR / "tpl_perakende_fis_80mm.json").read_text(encoding="utf-8"))
    tpl = ReportTemplate.from_dict(d)
    qps = ReportPrinterEngine(tpl)._resolve_page_size()
    size = qps.size(qps.definitionUnits())
    # A4 değil, 80mm genişliğinde özel boyut
    assert round(qps.sizePoints().width() / 72 * 25.4) == 80


def test_data_field_text_acts_as_label_prefix(qapp):
    """printer_engine: data_field'de `text` verilmişse etiket öneki olur;
    değer boşsa dangling etiket basılmaz."""
    from src.desktop.designer.models import ItemConfig

    tpl = ReportTemplate.from_dict({"template_id": "t", "title": "t", "bands": []})
    eng = ReportPrinterEngine(tpl)
    ctx = {"firma": {"vergi_no": "8520147963"}}

    with_val = ItemConfig(id="a", type="data_field", field="firma.vergi_no", text="VKN: ")
    assert eng._resolve_item_text(with_val, ctx, 1, 1) == "VKN: 8520147963"

    empty = ItemConfig(id="b", type="data_field", field="firma.yok", text="VKN: ")
    assert eng._resolve_item_text(empty, ctx, 1, 1) == ""
