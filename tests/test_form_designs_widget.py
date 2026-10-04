"""Form Tasarımları: şablonların modül etiketi, veri ağacının modüle göre değişmesi,
belge ekranının modülüne uyan şablonu önermesi ve yeni form ekleme akışı."""

from __future__ import annotations

import json
from pathlib import Path

from src.desktop.designer.models import ReportTemplate, blank_template
from src.desktop.designer.services import teklif_print_service
from src.desktop.designer.services.teklif_print_service import TeklifPrintService


def test_blank_template_has_core_bands_and_no_items():
    tpl = blank_template("tpl_ornek_a4", "Örnek Form", module="fatura", page_size="A4")
    assert tpl.module == "fatura"
    assert tpl.page.size == "A4"
    band_types = {b.type for b in tpl.bands}
    assert {"page_header", "column_header", "detail_data", "report_summary"} <= band_types
    assert all(not b.items for b in tpl.bands)


def test_report_template_to_dict_roundtrip_preserves_module():
    tpl = blank_template("tpl_x_a5", "X", module="irsaliye", page_size="A5")
    again = ReportTemplate.from_dict(tpl.to_dict())
    assert again.module == "irsaliye"
    assert again.page.size == "A5"


def test_existing_templates_are_tagged_with_their_module():
    mods = {Path(p).name: m for _t, p, m in TeklifPrintService.available_templates_full()}
    assert mods["tpl_teklif_kurumsal_a4.json"] == "teklif"
    assert mods["tpl_irsaliye_kurumsal_a4.json"] == "irsaliye"
    assert mods["tpl_fatura_kurumsal_a4.json"] == "fatura"


def test_invoice_template_title_text_is_no_longer_teklif():
    """Regresyon: fatura şablonunun başlık kutusu daha önce yanlışlıkla 'Teklif' basıyordu."""
    tpl_dir = teklif_print_service.templates_dir()
    d = json.loads((tpl_dir / "tpl_fatura_kurumsal_a4.json").read_text(encoding="utf-8"))
    header = next(b for b in d["bands"] if b["id"] == "band_page_header")
    title_item = next(it for it in header["items"] if it["id"] == "txt_doc_title")
    assert title_item["text"] != "Teklif"
    assert "FATURA" in title_item["text"].upper()


def test_data_tree_unknown_module_falls_back_to_shared_schema(qapp):
    from src.desktop.designer.ui.data_tree_widget import DataTreeWidget, _kategoriler_for

    assert _kategoriler_for("boyle_bir_modul_yok") is _kategoriler_for("fatura")

    dt = DataTreeWidget(module="fatura")
    before = dt.tree.topLevelItemCount()
    assert before > 0
    dt.set_module("fatura")  # aynı modül: yeniden doldurmaz
    assert dt.tree.topLevelItemCount() == before
    dt.set_module("irsaliye")  # ortak şemayı paylaşıyor ama repopulate path'i çalışmalı
    assert dt.tree.topLevelItemCount() == before


def test_document_screen_prefers_template_tagged_for_its_own_document_type(qapp):
    from src.desktop.ui.screens.document_detail_screen import DOCUMENT_TYPES, DocumentDetailScreen

    fatura_idx = DOCUMENT_TYPES.index("FATURA: Yurt İçi Satış Faturası")
    s = DocumentDetailScreen(initial_type_idx=fatura_idx)
    path = Path(s._tpl_selector.currentData())
    d = json.loads(path.read_text(encoding="utf-8"))
    assert d.get("module") == "fatura"


def test_slugify_handles_turkish_and_empty_text():
    from src.desktop.ui.widgets.form_designs_widget import slugify

    assert slugify("Kurumsal Fatura (Yedek)") == "kurumsal_fatura_yedek"
    assert slugify("İrsaliye Şablonu Öğe") == "irsaliye_sablonu_oge"
    assert slugify("") != ""  # boşsa bile geçerli, benzersiz bir ad üretir


def test_create_blank_form_writes_tagged_file_in_templates_dir(tmp_path, monkeypatch):
    from src.desktop.ui.widgets.form_designs_widget import create_blank_form

    monkeypatch.setattr(teklif_print_service, "_TEMPLATES_DIR", tmp_path)
    path = create_blank_form("Test Formu", "fatura", "A4")

    assert path.parent == tmp_path
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["module"] == "fatura"
    assert saved["title"] == "Test Formu"
    assert saved["page"]["size"] == "A4"


def test_create_blank_form_avoids_overwriting_an_existing_file(tmp_path, monkeypatch):
    from src.desktop.ui.widgets.form_designs_widget import create_blank_form

    monkeypatch.setattr(teklif_print_service, "_TEMPLATES_DIR", tmp_path)
    first = create_blank_form("Aynı Ad", "teklif", "A4")
    second = create_blank_form("Aynı Ad", "teklif", "A4")

    assert first != second
    assert first.exists() and second.exists()


def test_yeni_form_dialog_rejects_empty_name(qapp):
    from src.desktop.ui.widgets.form_designs_widget import YeniFormDialog

    dlg = YeniFormDialog()
    dlg.txt_ad.setText("   ")
    dlg._on_accept()
    assert dlg.result() != dlg.DialogCode.Accepted  # boş ad kabul edilmemeli

    dlg.txt_ad.setText("Geçerli Ad")
    dlg._on_accept()
    assert dlg.result() == dlg.DialogCode.Accepted
