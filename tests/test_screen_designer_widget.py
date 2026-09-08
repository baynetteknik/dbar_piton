"""Masaüstü Ekran Tasarımcısı (Aşama 3 Adım 3) testleri."""

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def widget(qapp, monkeypatch):
    """ScreenDesignerWidget — disk yazmayı engelleyip yakalanan kayıtları döndürür."""
    from src.desktop.ui.screens import screen_designer_widget as mod

    saved = {}
    monkeypatch.setattr(
        mod, "register_screen_definition",
        lambda sid, d, auto_save=True: saved.__setitem__(sid, d),
    )
    monkeypatch.setattr(mod.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(mod.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    w = mod.ScreenDesignerWidget()
    w._saved = saved
    return w


def test_builds_five_regions(widget):
    assert list(widget._region_lists) == [
        "top_form", "body", "bottom_form", "left_sidebar", "right_sidebar",
    ]


def test_add_and_collect_components(widget):
    widget._add_widget("top_form", "widget_cari_kunyesi")
    widget._add_widget("top_form", "widget_belge_vade")
    widget._add_widget("body", "widget_hareket_kalemleri")
    comps = widget._collect_components()
    assert comps == {
        "top_form": ["widget_cari_kunyesi", "widget_belge_vade"],
        "body": ["widget_hareket_kalemleri"],
    }


def test_move_within_and_remove(widget):
    for wid in ("widget_crud_actions", "widget_view_profiles", "widget_export_actions"):
        widget._add_widget("left_sidebar", wid)
    lst = widget._region_lists["left_sidebar"]
    lst.setCurrentRow(2)
    widget._move_within("left_sidebar", -1)
    assert widget._collect_components()["left_sidebar"] == [
        "widget_crud_actions", "widget_export_actions", "widget_view_profiles",
    ]
    lst.setCurrentRow(0)
    widget._remove_selected("left_sidebar")
    assert widget._collect_components()["left_sidebar"] == [
        "widget_export_actions", "widget_view_profiles",
    ]


def test_collect_definition_shape(widget):
    widget.txt_screen_id.setText("scr_designer_test")
    widget.txt_title.setText("Tasarımcı Test Ekranı")
    widget.chk_right.setChecked(False)
    widget.spin_row_h.setValue(32)
    widget._add_widget("body", "widget_hareket_kalemleri")

    d = widget.collect_definition()
    assert d["title"] == "Tasarımcı Test Ekranı"
    assert d["is_system_template"] is False
    assert d["regions"]["right_sidebar"] is False
    assert d["custom_row_height"] == 32
    assert d["components"] == {"body": ["widget_hareket_kalemleri"]}


def test_save_requires_id_and_title(widget):
    assert widget.save() is False           # boş
    widget.txt_screen_id.setText("scr_x")
    assert widget.save() is False           # başlık yok
    assert widget._saved == {}


def test_save_registers_and_emits(widget):
    widget.txt_screen_id.setText("scr_designer_roundtrip")
    widget.txt_title.setText("Roundtrip")
    widget._add_widget("top_form", "widget_cari_kunyesi")
    widget._add_widget("right_sidebar", "widget_finans")

    got = []
    widget.definition_saved.connect(got.append)
    assert widget.save() is True
    assert got == ["scr_designer_roundtrip"]
    assert "scr_designer_roundtrip" in widget._saved
    assert widget._saved["scr_designer_roundtrip"]["components"] == {
        "top_form": ["widget_cari_kunyesi"],
        "right_sidebar": ["widget_finans"],
    }


def test_load_definition_roundtrip(widget):
    from src.desktop.core.screen_registry import SCREEN_DEFINITIONS

    sid = "scr_designer_load"
    SCREEN_DEFINITIONS[sid] = {
        "title": "Yüklenen",
        "base_template": "tpl_fis_detail",
        "regions": {"header": True, "left_sidebar": False, "right_sidebar": True, "footer": True},
        "custom_row_height": 30,
        "components": {
            "top_form": ["widget_cari_kunyesi", "widget_belge_vade"],
            "body": ["widget_hareket_kalemleri"],
        },
    }
    try:
        widget.load_definition(sid)
        assert widget.txt_title.text() == "Yüklenen"
        assert widget.chk_left.isChecked() is False
        assert widget.spin_row_h.value() == 30
        assert widget._collect_components() == {
            "top_form": ["widget_cari_kunyesi", "widget_belge_vade"],
            "body": ["widget_hareket_kalemleri"],
        }
    finally:
        SCREEN_DEFINITIONS.pop(sid, None)


def test_designer_window_has_screen_designer_tab(qapp):
    from src.desktop.designer.ui.designer_window import ReportDesignerWindow
    from src.desktop.ui.screens.screen_designer_widget import ScreenDesignerWidget

    win = ReportDesignerWindow()
    assert win.tabs.count() == 2
    assert isinstance(win.screen_designer, ScreenDesignerWidget)
