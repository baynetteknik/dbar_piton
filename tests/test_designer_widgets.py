"""Görsel Tasarımcı Aşama 3 - gömülebilir widget'lar ve WIDGET_REGISTRY kayıtları."""

import pytest
from PyQt6.QtWidgets import QApplication

from src.desktop.designer.services.teklif_print_service import TeklifPrintService


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def demo():
    svc = TeklifPrintService(page_size="A4")
    return svc.get_template(), TeklifPrintService.get_demo_data()


# ---- ReportDesignerWidget -------------------------------------------------
def test_designer_widget_builds_three_panels(qapp):
    from src.desktop.designer.ui.designer_widget import ReportDesignerWidget

    w = ReportDesignerWidget()
    assert w.canvas is not None
    assert w.toolbox is not None
    assert w.inspector is not None
    assert w.data_tree is not None
    # bağımsız QMainWindow olmadan tam işlevli
    assert w.template.title
    assert "Tasarımcı" in w.window_title()


def test_designer_window_embeds_widget(qapp):
    from src.desktop.designer.ui.designer_widget import ReportDesignerWidget
    from src.desktop.designer.ui.designer_window import ReportDesignerWindow

    win = ReportDesignerWindow()
    # pencere artık sekmeli; form tasarımcısı ilk sekme
    assert isinstance(win.designer, ReportDesignerWidget)
    assert win.tabs.widget(0) is win.designer
    # eski çağıranlar .template / .canvas okuyor
    assert win.template is win.designer.template
    assert win.canvas is win.designer.canvas


def test_designer_widget_save_emits_signal(qapp, tmp_path, monkeypatch):
    from src.desktop.designer.ui import designer_widget as dw

    svc = TeklifPrintService(page_size="A4")
    src_json = svc.template_path.read_text(encoding="utf-8")
    target = tmp_path / "tpl_copy.json"
    target.write_text(src_json, encoding="utf-8")

    w = dw.ReportDesignerWidget(template_path=target)
    monkeypatch.setattr(dw.QMessageBox, "information", staticmethod(lambda *a, **k: None))

    seen = []
    w.template_saved.connect(seen.append)
    w._save_template()
    assert seen == [str(target)]
    assert target.exists()


# ---- ReportPreviewWidget ------------------------------------------------
def test_preview_widget_renders_pages(qapp, demo):
    from src.desktop.designer.ui.preview_widget import ReportPreviewWidget

    tpl, data = demo
    w = ReportPreviewWidget(template=tpl, data=data)
    assert len(w.rendered_pages) >= 1
    n = len(w.rendered_pages)

    w.set_document(tpl, datas=[data, data, data])
    assert len(w.rendered_pages) >= 3 * n


def test_preview_widget_empty_state(qapp):
    from src.desktop.designer.ui.preview_widget import ReportPreviewWidget

    w = ReportPreviewWidget()
    assert w.rendered_pages == []
    assert w.lbl_page_info.text() == "Sayfa 0 / 0"


def test_preview_widget_compact_hides_output_buttons(qapp, demo):
    from src.desktop.designer.ui.preview_widget import ReportPreviewWidget

    tpl, data = demo
    w = ReportPreviewWidget(template=tpl, data=data, compact=True)
    assert w.btn_print.isHidden()
    assert w.btn_pdf.isHidden()
    assert w.zoom_mode == "fit_width"


def test_preview_widget_page_navigation(qapp, demo):
    from src.desktop.designer.ui.preview_widget import ReportPreviewWidget

    tpl, data = demo
    w = ReportPreviewWidget(template=tpl, datas=[data, data, data])
    assert w.current_page_idx == 0
    w._next_page()
    assert w.current_page_idx == 1
    w._prev_page()
    assert w.current_page_idx == 0


def test_preview_dialog_wraps_widget(qapp, demo):
    from src.desktop.designer.preview_dialog import ReportPreviewDialog
    from src.desktop.designer.ui.preview_widget import ReportPreviewWidget

    tpl, data = demo
    dlg = ReportPreviewDialog(template=tpl, data=data)
    assert isinstance(dlg.preview, ReportPreviewWidget)
    assert dlg.rendered_pages is dlg.preview.rendered_pages


# ---- WIDGET_REGISTRY ---------------------------------------------------
def test_registry_has_designer_and_preview(qapp):
    from src.desktop.designer.ui.designer_widget import ReportDesignerWidget
    from src.desktop.designer.ui.preview_widget import ReportPreviewWidget
    from src.desktop.ui.widgets.widget_registry import (
        WIDGET_REGISTRY,
        create_widget_by_id,
    )

    assert WIDGET_REGISTRY["widget_report_designer"]["class"] is ReportDesignerWidget
    assert WIDGET_REGISTRY["widget_report_preview"]["class"] is ReportPreviewWidget

    a = create_widget_by_id("widget_report_designer")
    b = create_widget_by_id("widget_report_preview")
    assert isinstance(a, ReportDesignerWidget)
    assert isinstance(b, ReportPreviewWidget)
