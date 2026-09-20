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


# ---- Klavye ile ince ayar (Ctrl+Ok taşı, Ctrl+Alt+Ok boyutlandır) --------
def test_item_keyboard_nudge_move_and_resize(qapp):
    from PyQt6.QtCore import QEvent, Qt
    from PyQt6.QtGui import QKeyEvent

    from src.desktop.designer.models import ItemConfig
    from src.desktop.designer.ui.designer_item import DesignerItemWidget

    cfg = ItemConfig(id="t1", type="text", text="X", x_mm=10.0, y_mm=10.0, w_mm=20.0, h_mm=8.0)
    w = DesignerItemWidget(cfg)
    w.set_selected(True)

    def send(key, mods):
        w.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, mods))

    send(Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
    assert (cfg.x_mm, cfg.y_mm) == (11.0, 10.0)

    send(Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
    assert (cfg.w_mm, cfg.h_mm) == (20.0, 9.0)

    # Ctrl olmadan ok tuşu göz ardı edilir (varsayılan Qt gezinme davranışı bozulmasın)
    send(Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier)
    assert cfg.x_mm == 11.0


# ---- Sürükle-bırak: Araç Kutusu / Veri Ağacı -> Bant ---------------------
def test_toolbox_click_still_emits_item(qapp):
    """Sürükleme desteği eklenirken düz tıklama davranışı bozulmamalı."""
    from PyQt6.QtWidgets import QPushButton

    from src.desktop.designer.ui.toolbox_widget import ToolboxWidget

    tb = ToolboxWidget()
    seen = []
    tb.item_requested.connect(seen.append)
    # Araç kutusundaki ilk buton (Sabit Metin)
    btn = tb.findChildren(QPushButton)[0]
    btn.click()
    assert len(seen) == 1
    assert seen[0].type == "text"


def test_band_drop_event_places_item_at_drop_position(qapp):
    import dataclasses
    import json

    from PyQt6.QtCore import QMimeData, QPointF, Qt
    from PyQt6.QtGui import QDropEvent

    from src.desktop.designer.models import MIME_ITEM_CONFIG, BandConfig
    from src.desktop.designer.ui.designer_band import DesignerBandWidget
    from src.desktop.designer.ui.toolbox_widget import ToolboxWidget

    band = DesignerBandWidget(BandConfig(id="b1", type="detail_data", height_mm=30.0))
    cfg = ToolboxWidget()._make_text_item()

    mime = QMimeData()
    mime.setData(MIME_ITEM_CONFIG, json.dumps(dataclasses.asdict(cfg)).encode("utf-8"))
    pos = QPointF(37.795, 37.795)  # mm_to_px varsayılanında ~10mm, 10mm
    ev = QDropEvent(
        pos, Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    band.dropEvent(ev)

    assert len(band.item_widgets) == 1
    dropped = band.item_widgets[0].item
    assert abs(dropped.x_mm - 10.0) < 0.2
    assert abs(dropped.y_mm - 10.0) < 0.2
    assert dropped.id != cfg.id  # yeni benzersiz id atanmış olmalı


def test_data_tree_leaf_provides_drag_mime_but_category_does_not(qapp):
    from PyQt6.QtCore import Qt

    from src.desktop.designer.models import MIME_ITEM_CONFIG
    from src.desktop.designer.ui.data_tree_widget import DataTreeWidget

    dt = DataTreeWidget()
    category_item = dt.tree.topLevelItem(0)
    leaf_item = category_item.child(0)

    cat_mime = dt.tree.mimeData([category_item])
    assert not cat_mime.hasFormat(MIME_ITEM_CONFIG)

    leaf_mime = dt.tree.mimeData([leaf_item])
    assert leaf_mime.hasFormat(MIME_ITEM_CONFIG)


# ---- Sayfa boyutu / yön seçici (mevcut elemanlar için onay ister) -------
def test_page_size_change_guarded_when_items_exist(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    from src.desktop.designer.ui.designer_widget import ReportDesignerWidget

    w = ReportDesignerWidget()
    assert any(b.items for b in w.template.bands)  # varsayılan şablon dolu

    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.No,
    ))
    before = (w.template.page.size, w.template.page.width_mm, w.template.page.height_mm)
    w.cmb_page_size.setCurrentText("A5")
    assert (w.template.page.size, w.template.page.width_mm, w.template.page.height_mm) == before

    monkeypatch.setattr(QMessageBox, "question", staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    ))
    w.cmb_page_size.setCurrentText("A3")
    assert w.template.page.size == "A3"
    assert (w.template.page.width_mm, w.template.page.height_mm) == (297.0, 420.0)

    w.cmb_orientation.setCurrentIndex(1)
    assert (w.template.page.width_mm, w.template.page.height_mm) == (420.0, 297.0)


# ---- Bant Yönetimi diyaloğu ----------------------------------------------
def test_band_manager_dialog_applies_enabled_and_height(qapp):
    from src.desktop.designer.ui.band_manager_dialog import BandManagerDialog
    from src.desktop.designer.ui.designer_widget import ReportDesignerWidget

    w = ReportDesignerWidget()
    dlg = BandManagerDialog(w.template)
    assert dlg.table.rowCount() == len(w.template.bands)

    dlg._checks[0].setChecked(False)
    dlg._spins[1].setValue(42.5)
    dlg._on_accept()

    assert w.template.bands[0].enabled is False
    assert w.template.bands[1].height_mm == 42.5


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
