"""DefinitionEditorScreen — tpl.card.001 standardı eklentileri."""

import pytest

from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen

TABS = [{
    "title": "Genel",
    "fields": [
        {"key": "code", "label": "Kod", "type": "text"},
        {"key": "name", "label": "Ad", "type": "text"},
        {"key": "active", "label": "Aktif", "type": "bool", "text": "Aktif"},
        {"key": "plan", "label": "Plan", "type": "combo"},
    ],
}]


def test_header_reflects_code_title_status(qapp):
    ed = DefinitionEditorScreen(
        title="Kart", tabs=TABS,
        code_field="code", title_field="name", status_field="active",
    )
    ed.set_data({"code": "K1", "name": "Örnek", "active": True}, is_edit=True)
    assert "K1" in ed.lbl_record.text() and "Örnek" in ed.lbl_record.text()
    assert not ed.lbl_status_badge.isHidden() and "Aktif" in ed.lbl_status_badge.text()

    ed._widgets["active"].setChecked(False)
    assert "Pasif" in ed.lbl_status_badge.text()


def test_extra_actions_render_and_gate_on_edit(qapp):
    calls = []
    ed = DefinitionEditorScreen(
        title="Kart", tabs=TABS,
        extra_actions=[{"label": "📊 Hareketler", "callback": lambda: calls.append(1),
                        "enabled_on_edit": True}],
    )
    btn, only_edit = ed._extra_action_buttons[0]
    assert btn.text() == "📊 Hareketler" and only_edit

    ed.set_data({"code": "K1"}, is_edit=False)
    assert btn.isEnabled() is False
    ed.set_data({"code": "K1", "id": 5}, is_edit=True)
    assert btn.isEnabled() is True
    btn.click()
    assert calls == [1]


def test_summary_provider_called(qapp):
    ed = DefinitionEditorScreen(
        title="Kart", tabs=TABS,
        summary_provider=lambda d: f"özet:{d.get('name','')}",
    )
    ed.set_data({"name": "ABC"}, is_edit=True)
    assert ed.lbl_sum.text() == "özet:ABC"
    ed._widgets["name"].setText("XYZ")
    assert ed.lbl_sum.text() == "özet:XYZ"


def test_combo_options_provider(qapp):
    tabs = [{
        "title": "T",
        "fields": [{"key": "plan", "label": "Plan", "type": "combo",
                    "options_provider": lambda: ["A", "B", "C"]}],
    }]
    ed = DefinitionEditorScreen(title="Kart", tabs=tabs)
    items = [ed._widgets["plan"].itemText(i) for i in range(ed._widgets["plan"].count())]
    assert items == ["A", "B", "C"]


def test_readonly_number_field(qapp):
    tabs = [{
        "title": "T",
        "fields": [{"key": "bal", "label": "Bakiye", "type": "number", "readonly": True}],
    }]
    ed = DefinitionEditorScreen(title="Kart", tabs=tabs)
    assert ed._widgets["bal"].isReadOnly()


# ---- bands (çok kolonlu bölümlü) düzen ----
BANDS_TABS = [
    {
        "title": "Genel",
        "bands": [
            {"sections": [
                {"title": "1. Kimlik", "columns": 1, "stretch": 2, "fields": [
                    {"key": "sku", "label": "Kod", "type": "text"},
                    {"key": "name", "label": "Ad", "type": "text", "span": 2},
                ]},
                {"title": "DİĞER", "columns": 1, "stretch": 1, "fields": [
                    {"key": "note", "label": "Not", "type": "text"},
                ]},
            ]},
            {"sections": [{"title": "3. Fiyat", "columns": 2, "fields": [
                {"key": "buy", "label": "Alış", "type": "money",
                 "currencies": ["TRY", "USD"], "currency_key": "buy_cur"},
                {"key": "grp", "label": "Grup", "type": "search"},
            ]}]},
        ],
    },
    {"title": "Eski", "fields": [{"key": "x", "label": "X", "type": "text"}]},
]


def test_bands_layout_registers_all_fields(qapp):
    ed = DefinitionEditorScreen(title="Kart", tabs=BANDS_TABS, nav_sidebar=False)
    assert ed.tabw.count() == 2
    assert set(ed._widgets) == {"sku", "name", "note", "buy", "grp", "x"}
    assert ed._nav_sidebar is False   # bands → sol nav otomatik kapalı


def test_bands_and_flat_tabs_roundtrip(qapp):
    ed = DefinitionEditorScreen(title="Kart", tabs=BANDS_TABS)
    ed.set_data({"sku": "ST002", "name": "HP ADAPTOR", "buy": 1486.8,
                 "buy_cur": "USD", "grp": "ELEKTRONİK", "x": "legacy"}, is_edit=True)
    out = ed.collect()
    assert out["buy"] == 1486.8 and out["buy_cur"] == "USD"
    assert out["grp"] == "ELEKTRONİK" and out["name"] == "HP ADAPTOR" and out["x"] == "legacy"


def test_search_field_button_calls_callback(qapp):
    calls = []
    tabs = [{"title": "T", "bands": [{"sections": [{"title": "S", "fields": [
        {"key": "grp", "label": "Grup", "type": "search",
         "on_search": lambda t: calls.append(t)},
    ]}]}]}]
    ed = DefinitionEditorScreen(title="K", tabs=tabs)
    ed._widgets["grp"].setText("abc")
    from PyQt6.QtWidgets import QPushButton
    ed._widgets["grp"].findChildren(QPushButton)[0].click()   # 🔍
    assert calls == ["abc"]


def test_summary_widget_update_from_called(qapp):
    from PyQt6.QtWidgets import QWidget
    seen = {}

    class _Panel(QWidget):
        def update_from(self, d):
            seen.update(d)

    tabs = [{"title": "T", "fields": [{"key": "n", "label": "N", "type": "text"}]}]
    ed = DefinitionEditorScreen(title="K", tabs=tabs, summary_widget=_Panel())
    ed.set_data({"n": "ABC"}, is_edit=True)
    assert seen.get("n") == "ABC"


def test_header_status_combo_syncs_with_bool(qapp):
    tabs = [{"title": "T", "fields": [
        {"key": "act", "label": "Aktif", "type": "bool"},
        {"key": "c", "label": "C", "type": "text"},
    ]}]
    ed = DefinitionEditorScreen(title="K", tabs=tabs, status_field="act", code_field="c")
    assert ed.cmb_header_status is not None
    ed._widgets["act"].setChecked(True)
    assert ed.cmb_header_status.currentText() == "Aktif"
    ed.cmb_header_status.setCurrentText("Pasif")
    assert ed._widgets["act"].isChecked() is False


# ---------------------------------------------------------------- 2026-10-03: taşma düzeltmeleri
def test_combo_genislik_uzun_secenek_metninden_bagimsizdir(qapp):
    """Uzun seçenek metni (ör. 'KOD — Uzun Hesap Adı') kapalı kutunun kendisini büyütüp pencereyi
    sağa taşırmamalı — genişlik sabit bir karakter sayısına bağlı, popup'ta tam metin görünür."""
    uzun = "BNK001 — Çok Uzun Bir Banka Hesabı Adı Buraya Sığdırılmaya Çalışılıyor A.Ş."
    tabs = [{"title": "T", "fields": [{"key": "h", "label": "Hesap", "type": "combo", "options": [uzun]}]}]
    ed = DefinitionEditorScreen(title="K", tabs=tabs)
    cb = ed._widgets["h"]
    assert cb.sizeHint().width() < 300   # eskiden uzun metin yüzünden >600px olabiliyordu
    assert cb.itemText(0) == uzun        # tam metin yine de saklanır/seçilebilir


def test_right_panel_false_ozet_paneli_olusturmaz_ve_cokmez(qapp):
    """`right_panel=False` (ör. Banka/Kasa Kartı editörü) sağ 'ÖZET' panelini hiç kurmamalı;
    `set_data`/`collect` canlı yenileme akışı bu durumda çökmeden no-op geçmeli."""
    tabs = [{"title": "T", "fields": [{"key": "n", "label": "N", "type": "text"}]}]
    ed = DefinitionEditorScreen(title="K", tabs=tabs, right_panel=False, nav_sidebar=False)
    assert not hasattr(ed, "sec_summary")
    ed.set_data({"n": "ABC"}, is_edit=True)   # çökmemeli
    assert ed._widgets["n"].text() == "ABC"


def test_sol_sag_paneller_acilir_kapanir_toggle_ile(qapp):
    tabs = [{"title": "T", "fields": [{"key": "n", "label": "N", "type": "text"}]}]
    ed = DefinitionEditorScreen(title="K", tabs=tabs, nav_sidebar=True)
    sol_panel, sag_panel = ed._left_panel_frame, ed._right_panel_frame
    # `.show()` edilmemiş bir widget ağacında `isVisible()` her zaman False döner (üst pencere
    # görünürlüğüne bağlı), bu yüzden `isHidden()` kullanılıyor; dar ekranlı test ortamlarında
    # paneller varsayılan kapalı başlayabileceğinden burada sadece toggle'ın çalıştığı doğrulanır.

    basta_sol, basta_sag = sol_panel.isHidden(), sag_panel.isHidden()
    ed._left_panel_toggle.click()
    assert sol_panel.isHidden() != basta_sol
    ed._left_panel_toggle.click()
    assert sol_panel.isHidden() == basta_sol

    ed._right_panel_toggle.click()
    assert sag_panel.isHidden() != basta_sag
    ed._right_panel_toggle.click()
    assert sag_panel.isHidden() == basta_sag
