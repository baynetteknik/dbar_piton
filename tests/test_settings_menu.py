"""Genel Ayarlar: menü/işlem kodları, isim+kod araması, sağ panelin sürükle-bırak sıralaması, AppGrid, sağ tık işlemleri."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt

from src.desktop.services import settings_menu as sm
from src.desktop.ui.components.entry_table_view import EntryTableView
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.settings import GeneralSettingsScreen


# ---------------------------------------------------------------- saf mantık
def test_every_menu_has_a_unique_code_and_every_group_too():
    pids = [pid for _g, _i, items in GeneralSettingsScreen.MENU_STRUCTURE for _n, pid in items]
    codes = [sm.item_code(p) for p in pids]
    assert all(codes) and len(set(codes)) == len(codes)
    assert set(sm.ITEM_CODES) == set(pids)                                   # kayıtta fazladan/eksik menü yok
    groups = [g for g, _i, _m in GeneralSettingsScreen.MENU_STRUCTURE]
    assert all(sm.GROUP_CODES.get(g) for g in groups) and len(set(sm.GROUP_CODES.values())) == len(sm.GROUP_CODES)
    assert sm.action_code("cari_gruplari", 2) == "sys.set.501.02" and sm.action_code("yok", 1) == ""


def test_search_matches_name_code_group_and_ignores_turkish_case_and_accents():
    m = sm.matches
    assert m("cari", "Cari Grupları", "CARİ TANIMLARI", "sys.set.501")
    assert m("CARİ", "cari grupları") and m("sirket", "ŞİRKET TANIMLARI") and m("gruplari", "Cari Grupları")
    assert m("501", "Cari Grupları", "sys.set.501") and m("sys.set.501", "x", "sys.set.501")
    assert m("cari 501", "Cari Grupları", "sys.set.501") and not m("cari 999", "Cari Grupları", "sys.set.501")
    assert m("", "herhangi") and m("  ", "x") and not m("zzz", "Cari", "sys.set.501")
    assert m("ışık", "ISIK") and m("kur", "Döviz & Kur")


def test_order_normalization_and_per_user_storage(db_session):
    assert sm.normalize_order(None) == sm.DEFAULT_SIDEBAR_ORDER
    rest = [k for k in sm.DEFAULT_SIDEBAR_ORDER if k not in ("hizli", "filtre")]
    assert sm.normalize_order(["hizli", "filtre", "bilinmeyen", "hizli"]) == ["hizli", "filtre"] + rest   # tekrar/bilinmeyen atılır, eksikler sona
    a, b = sm.SidebarOrderStore(db_session, "ali"), sm.SidebarOrderStore(db_session, "veli")
    a.save(["yazdir", "islemler"])
    assert a.load()[:2] == ["yazdir", "islemler"] and b.load() == sm.DEFAULT_SIDEBAR_ORDER   # kullanıcıya özel
    a.reset()
    assert a.load() == sm.DEFAULT_SIDEBAR_ORDER
    db_session.execute(__import__("sqlalchemy").text("UPDATE system_settings SET value='{bozuk' WHERE key LIKE 'ui.genel_ayarlar.sag_panel_sirasi%'"))
    db_session.commit()
    assert a.load() == sm.DEFAULT_SIDEBAR_ORDER                                          # bozuk kayıt varsayılana düşer


# ---------------------------------------------------------------- ekran
@pytest.fixture
def screen(qapp, db_session):
    s = GeneralSettingsScreen(db_session=db_session)
    yield s
    s.close()


def test_right_sidebar_sections_start_collapsed_and_left_menu_has_no_action_boxes(screen):
    screen.switch_panel("firma_bilgileri")   # varsayılan açılış artık "settings_hub" (paneller kapalı); normal bir menüye geçip davranışı test et
    sb = screen.right_sidebar
    assert screen.right_panel.is_open and screen.left_panel.is_open           # paneller açık, bölümler kapalı
    assert all(not sb.section(k).is_expanded for k in sb.keys())
    # alt eylemler artık sol menüde değil: hiçbir işlem düğmesi sol paneldeki bir menü öğesinin altında yok
    left_btns = {b for b in screen.left_panel.findChildren(type(next(iter(screen.menu_buttons.values()))))}
    for box in screen.menu_sub_boxes.values():
        assert not (set(box.findChildren(type(next(iter(screen.menu_buttons.values()))))) & set(screen.menu_buttons.values()))
        assert sb.isAncestorOf(box)                                            # işlemler sağ panelde
    assert screen.right_panel.isAncestorOf(screen.menu_sub_boxes["cari_gruplari"])
    assert left_btns >= set(screen.menu_buttons.values())


def test_only_the_selected_menus_actions_are_visible_in_the_right_panel(screen):
    screen.show()
    screen.on_menu_clicked("cari_gruplari", screen.menu_buttons["cari_gruplari"])
    screen.right_sidebar.section("islemler").set_expanded(True)
    vis = [pid for pid, box in screen.menu_sub_boxes.items() if box.isVisibleTo(screen.right_sidebar)]
    assert vis == ["cari_gruplari"]
    labels = [lab for _b, lab, _c in screen.menu_sub_boxes["cari_gruplari"].action_buttons]
    assert any("Yeni Grup" in x for x in labels)
    screen.on_menu_clicked("kullanicilar", screen.menu_buttons["kullanicilar"])
    assert [pid for pid, box in screen.menu_sub_boxes.items() if box.isVisibleTo(screen.right_sidebar)] == ["kullanicilar"]


def test_code_display_is_a_parameter_defaulting_to_hover_hints(screen, db_session):
    m = screen.menu_buttons["cari_gruplari"]
    grp = next(s for s in screen.menu_sections if "CARİ" in s.header_btn.text())
    assert screen.code_mode == "ipucu" and screen.cmb_code_mode.currentData() == "ipucu"
    assert not m.code_visible() and grp.code_label.isHidden()                       # varsayılan: rozet yok, sade görünüm
    tip = m.toolTip()
    assert "sys.set.501" in tip and "<b>" in tip and "Cari Grupları" in tip           # kod ipucunda
    assert "sys.set.50" in grp.header_btn.toolTip() and "sys.rp.02" in screen.right_sidebar.section("filtre").header_btn.toolTip()
    btn, _label, code = screen.menu_sub_boxes["cari_gruplari"].action_buttons[0]
    assert code == "sys.set.501.01" and code in btn.toolTip() and not btn.code_visible()
    assert "sys.rp.03.01" in screen.right_sidebar._entries["yazdir"].items[0][0].toolTip()

    screen.switch_panel("cari_gruplari")
    screen.cmb_code_mode.setCurrentIndex(screen.cmb_code_mode.findData("rozet"))     # rozet: adın altında
    assert m.code_visible() and btn.code_visible() and not grp.code_label.isHidden()
    assert grp.code_label.text() == "sys.set.50" and screen.right_sidebar.section("filtre").code_label.text() == "sys.rp.02"
    assert "[sys.set.501]" in screen.lbl_breadcrumb.text() and sm.code_mode(db_session) == "rozet"
    yazdir = screen.right_sidebar._entries["yazdir"].items[0][0]
    assert yazdir.code() == "sys.rp.03.01" and yazdir.code_visible()

    screen.cmb_code_mode.setCurrentIndex(screen.cmb_code_mode.findData("gizli"))     # gizli: hiçbir yerde kod yok
    assert not m.code_visible() and grp.code_label.isHidden() and "sys.set.501" not in m.toolTip()
    assert "[sys.set.501]" not in screen.lbl_breadcrumb.text() and sm.code_mode(db_session) == "gizli"
    assert sm.matches("501", "Cari Grupları", sm.item_code("cari_gruplari"))          # arama yine kodla çalışır

    screen.set_code_mode("ipucu")
    assert "sys.set.501" in m.toolTip() and not m.code_visible() and screen.cmb_code_mode.currentData() == "ipucu"


def test_reopening_restores_the_saved_code_mode(qapp, db_session):
    s = GeneralSettingsScreen(db_session=db_session)
    s.set_code_mode("rozet")
    s.close()
    s2 = GeneralSettingsScreen(db_session=db_session)
    assert s2.code_mode == "rozet" and s2.menu_buttons["cari_gruplari"].code_visible() and s2.cmb_code_mode.currentData() == "rozet"
    s2.close()


def test_hints_are_blue_with_white_text_and_real_buttons_have_depth(screen):
    from PyQt6.QtWidgets import QApplication

    css = QApplication.instance().styleSheet()
    assert css.count("toya-tooltip") == 1 and "#2563eb" in css.split("toya-tooltip")[-1]   # uygulama düzeyinde, bir kez
    m0 = screen.menu_buttons["cari_gruplari"]
    for w in (m0, screen.menu_sub_boxes["cari_gruplari"].action_buttons[0][0], screen.right_sidebar.section("filtre").header_btn,
              screen.txt_right_filter):
        assert "QToolTip" in w.styleSheet() and "#2563eb" in w.styleSheet()          # kendi stili olan widget ipucu kuralını KAYBETMEZ
    m = screen.menu_buttons["cari_gruplari"]
    assert "border-bottom:3px" in m.styleSheet() and "border-radius:6px" in m.styleSheet()   # asıl düğme: kart + derinlik
    assert "border-bottom:3px" in screen.btn_style() and "pressed" in screen.btn_style()
    active = screen.menu_btn_style(True)
    assert "#2563eb" in active and "font-weight:800" in active
    btn = screen.menu_sub_boxes["cari_gruplari"].action_buttons[0][0]
    assert "border-bottom:3px" in btn.styleSheet()
    badge_css = m._badge.styleSheet()                                               # rozet düğme gibi görünmemeli
    assert "border:none" in badge_css and "background:transparent" in badge_css


def test_badge_takes_less_width_than_appending_the_code_to_the_text(qapp):
    from src.desktop.ui.components.coded_button import CodedButton

    b = CodedButton("Yeni Grup Ekle", "sys.set.501.01")
    b.setStyleSheet("QPushButton{color:#334155; font-size:11px; font-weight:600;}")
    b.show()
    inline = b.fontMetrics().horizontalAdvance("Yeni Grup Ekle  [sys.set.501.01]")
    assert b._lbl.fontMetrics().horizontalAdvance("Yeni Grup Ekle") < inline                # ad tek başına dar
    assert b._badge.isVisibleTo(b) and b.minimumHeight() > 24
    b.set_code_visible(False)
    assert not b._badge.isVisibleTo(b) and b.minimumHeight() == 24
    seen = []
    b.clicked.connect(lambda: seen.append(1))
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    QTest.mouseClick(b, Qt.MouseButton.LeftButton)                                          # etiketler tıklamayı yutmaz
    assert seen == [1]


def test_left_menu_search_by_name_and_by_code(screen):
    screen.show()
    screen.switch_panel("firma_bilgileri")   # varsayılan açılış artık "settings_hub" (sol panel kapalı); arama görünürlüğü normal bir menüde test edilir
    screen.menu_search_input.setText("cari")
    vis = {pid for pid, (w, *_r) in screen.menu_item_containers.items() if w.isVisibleTo(screen)}
    assert vis == {"cari_gruplari", "cari_ozel_alanlar"}
    screen.menu_search_input.setText("501")
    assert {pid for pid, (w, *_r) in screen.menu_item_containers.items() if w.isVisibleTo(screen)} == {"cari_gruplari"}
    screen.menu_search_input.setText("sys.set.60")                                   # grup kodu: grubun tüm menüleri
    vis = {pid for pid, (w, *_r) in screen.menu_item_containers.items() if w.isVisibleTo(screen)}
    assert {"guvenlik", "surum_git", "yedek_merkezi"} <= vis and "cari_gruplari" not in vis
    screen.menu_search_input.setText("SİSTEM")
    assert "guvenlik" in {pid for pid, (w, *_r) in screen.menu_item_containers.items() if w.isVisibleTo(screen)}
    screen.menu_search_input.setText("")
    assert all(not w.isHidden() for w, *_r in screen.menu_item_containers.values())     # arama temizlenince hepsi geri gelir


def test_right_sidebar_search_by_section_name_action_name_and_code(screen):
    screen.show()
    screen.switch_panel("cari_gruplari")
    sb = screen.right_sidebar
    sb.search.setText("yazdır")
    assert sb.section("yazdir").isVisibleTo(sb) and not sb.section("filtre").isVisibleTo(sb)
    assert sb.section("yazdir").is_expanded                                        # eşleşen bölüm açılır
    sb.search.setText("sys.set.501.02")                                            # işlem koduna göre
    assert sb.section("islemler").isVisibleTo(sb) and not sb.section("yazdir").isVisibleTo(sb)
    shown = [lab for b, lab, _c in screen.menu_sub_boxes["cari_gruplari"].action_buttons if b.isVisibleTo(sb)]
    assert len(shown) == 1 and "Sil" in shown[0]
    sb.search.setText("excel")                                                     # işlem adına göre
    assert sb.section("yazdir").isVisibleTo(sb) and not sb.section("islemler").isVisibleTo(sb)
    sb.search.setText("sys.rp.04")                                                 # bölüm koduna göre
    assert [k for k in sb.keys() if sb.section(k).isVisibleTo(sb)] == ["hizli"]
    sb.search.setText("yokboyleseyzz")
    assert not any(sb.section(k).isVisibleTo(sb) for k in sb.keys())
    sb.search.setText("")
    assert all(not sb.section(k).is_expanded for k in sb.keys())                  # temizleyince yine kapalı
    assert sb.section("filtre").isVisibleTo(sb)


def test_dovi_sections_only_show_on_the_doviz_panel_and_keep_their_order(screen):
    screen.show()
    screen._doviz_ilk_secim_soruldu = True     # ilk kurulum döviz seçim penceresi (modal) testte açılmasın
    sb = screen.right_sidebar
    assert not sb.section("doviz").isVisibleTo(sb)
    screen.switch_panel("doviz_kur")
    assert sb.section("doviz").isVisibleTo(sb) and sb.section("kur_rapor").isVisibleTo(sb)
    sb.move("doviz", -1)
    order = sb.order()
    screen.switch_panel("cari_gruplari")
    assert not sb.section("doviz").isVisibleTo(sb) and sb.order() == order


# ---------------------------------------------------------------- sürükle-bırak sıralama
def test_drag_drop_reorders_persists_and_restores_on_reopen(qapp, db_session):
    s = GeneralSettingsScreen(db_session=db_session)
    s.show()
    sb = s.right_sidebar
    assert sb.order()[:4] == ["islemler", "filtre", "yazdir", "hizli"]
    qapp.processEvents()
    sb.drop_at("hizli", sb.section("islemler").y() - 5)                            # en üste bırak
    assert sb.order()[0] == "hizli" and sb.order()[1] == "islemler"
    # gerçek bırakma olayı yolu (sinyal): en alta bırak
    sb._frame.dropped.emit("islemler", 10_000)
    order = sb.order()
    visible = [k for k in order if sb.section(k).isVisibleTo(sb)]
    assert visible[-1] == "islemler" and visible[0] == "hizli"                     # görünenlerin en altı
    saved = sm.SidebarOrderStore(db_session, "").load()
    assert saved == order                                                          # kalıcı
    s.close()
    s2 = GeneralSettingsScreen(db_session=db_session)                              # yeniden aç: sıra geri gelir
    assert s2.right_sidebar.order() == order
    s2.right_sidebar.reset_order()
    assert s2.right_sidebar.order() == sm.DEFAULT_SIDEBAR_ORDER and sm.SidebarOrderStore(db_session, "").load() == sm.DEFAULT_SIDEBAR_ORDER
    s2.close()


def test_move_up_down_stops_at_edges_and_ignores_unknown_keys(screen):
    sb = screen.right_sidebar
    first = sb.order()[0]
    sb.move(first, -1)
    assert sb.order()[0] == first                                                   # kenarda değişmez
    sb.move(first, 1)
    assert sb.order()[1] == first
    last = sb.order()[-1]
    sb.move(last, 5)
    assert sb.order()[-1] == last
    before = sb.order()
    sb.move("yok", 1)
    sb._frame.dropped.emit("yok", 5)                                                # bilinmeyen anahtarlı bırakma yok sayılır
    assert sb.order() == before


def test_saved_order_with_unknown_and_missing_sections_is_repaired(qapp, db_session):
    sm.SidebarOrderStore(db_session, "").save(["yazdir", "eskiden_vardi", "islemler"])
    s = GeneralSettingsScreen(db_session=db_session)
    order = s.right_sidebar.order()
    assert order[:2] == ["yazdir", "islemler"] and set(order) == set(sm.DEFAULT_SIDEBAR_ORDER)
    s.close()


# ---------------------------------------------------------------- standart grid + sağ tık işlemleri
def _baslik(t, c: int) -> str:
    return str(t.model().headerData(c, Qt.Orientation.Horizontal) or "")


def test_all_definition_tables_are_standard_entry_grids_with_theme_style(screen):
    """Genel Ayarlar tanım tabloları standart gride taşındı (YZ2 Görev 27): AppGrid yerine `standart_grid`
    (`EntryTableView` + kapsayıcı `FilterableTableView` = `.container`), merkezi tema (bkz. `STANDART_TABLO_QSS`)."""
    screen.switch_panel("yetkiler")
    names = [n for n in dir(screen) if n.startswith("tbl_")]
    assert {"tbl_odeme", "tbl_fiyat", "tbl_kategori", "tbl_marka", "tbl_birim",
            "tbl_cari_grup", "tbl_yetkiler", "tbl_lockout", "tbl_form_tasarim"} <= set(names)
    for n in names:
        t = getattr(screen, n)
        assert isinstance(t, EntryTableView) and isinstance(t.container, FilterableTableView), n
        assert "font-family" in t.styleSheet() and t.alternatingRowColors() and not t.verticalHeader().isVisible()
        assert _baslik(t, 0) == _baslik(t, 0).upper()                                          # standart BÜYÜK harf başlık
    assert _baslik(screen.tbl_cari_grup, 0) == "GRUP KODU"
    assert _baslik(screen.tbl_kategori, 1) == "ÜST KATEGORİ"                                   # Türkçe büyük harf (i → İ)
    assert screen.tbl_cari_grup.model().item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable         # tanımlar düzenlenebilir
    assert not (screen.tbl_yetkiler.model().item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)    # matris salt okunur
    assert screen.tbl_yetkiler.model().columnCount() >= 2
    assert not (screen.tbl_form_tasarim.model().item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable)  # dosya tabanlı, satırdan düzenlenmez
    assert screen.tbl_form_tasarim.rowCount() >= 3                                               # teklif/irsaliye/fatura hazır şablonları


def test_form_tasarimlari_has_no_owned_buttons_actions_come_from_islemler_and_context_menu(screen):
    """Kullanıcı geri bildirimi: panelin kendi üst/alt buton satırı olmamalı, diğer tanım
    tabloları gibi tek kaynak (sağ panel İŞLEMLER + sağ tık) üzerinden yönetilmeli."""
    from PyQt6.QtWidgets import QPushButton

    screen.switch_panel("form_tasarimlari")
    panel = screen.panels["form_tasarimlari"]
    sibling = screen.panels["stok_markalar"]  # standart dbgrid'in kendi (arama/sütun) düğmeleri referans
    assert len(panel.findChildren(QPushButton)) == len(sibling.findChildren(QPushButton))        # panelin EK butonu yok
    labels = [lbl for lbl, _cb in screen._panel_actions("form_tasarimlari")]
    assert labels == ["➕ Yeni Form Ekle", "🎨 Tasarımcıda Aç", "🗑️ Sil", "🔄 Yenile"]
    right = [lab for _b, lab, _c in screen.menu_sub_boxes["form_tasarimlari"].action_buttons]
    assert labels == right                                                                       # sağ panel ile aynı kaynak


def test_form_tasarimlari_add_and_delete_via_panel_actions(qapp, db_session, tmp_path, monkeypatch):
    """Yeni Form Ekle -> dosya yazılır + grid'e düşer; Sil -> dosya silinir + grid'den düşer."""
    from src.desktop.designer.services import teklif_print_service
    from src.desktop.ui.widgets import form_designs_widget as fdw

    monkeypatch.setattr(teklif_print_service, "_TEMPLATES_DIR", tmp_path)
    s = GeneralSettingsScreen(db_session=db_session)
    try:
        s.switch_panel("form_tasarimlari")
        assert s.tbl_form_tasarim.rowCount() == 0

        monkeypatch.setattr(fdw.YeniFormDialog, "exec", lambda self: 1)
        monkeypatch.setattr(fdw.YeniFormDialog, "values", lambda self: ("Test Formu", "fatura", "A4"))
        opened = []
        s._form_tasarim_ac_yol = lambda p: opened.append(p)

        actions = dict(s._panel_actions("form_tasarimlari"))
        actions["➕ Yeni Form Ekle"]()
        assert s.tbl_form_tasarim.rowCount() == 1
        assert _baslik(s.tbl_form_tasarim, 0) == "FORM ADI"
        assert s.tbl_form_tasarim.model().item(0, 0).text() == "Test Formu"
        assert opened and opened[0].exists()

        s.tbl_form_tasarim.selectRow(0)
        actions["🗑️ Sil"]()
        assert s.tbl_form_tasarim.rowCount() == 0
        assert not opened[0].exists()
    finally:
        s.close()


def test_context_actions_are_the_same_as_the_right_panel_and_actually_work(screen):
    screen.switch_panel("cari_gruplari")
    acts = screen.tbl_cari_grup.context_actions_provider()
    labels = [a[0] for a in acts]
    assert all("[" not in x for x in labels)                                                  # ipucu modunda etikette kod yok
    assert any("Yeni Grup Ekle" in a[0] and "sys.set.501.01" in a[2] for a in acts)           # kod ipucunda (menüde ipucu görünür)
    right = [lab for _b, lab, _c in screen.menu_sub_boxes["cari_gruplari"].action_buttons]
    assert labels == right                                                                    # tek kaynak
    n = screen.tbl_cari_grup.rowCount()
    dict((a[0], a[1]) for a in acts)["➕ Yeni Grup Ekle"]()
    assert screen.tbl_cari_grup.rowCount() == n + 1
    screen.set_code_mode("rozet")
    assert any("Yeni Grup Ekle" in a[0] and "[sys.set.501.01]" in a[0] for a in screen.tbl_cari_grup.context_actions_provider())
    screen.set_code_mode("gizli")
    assert all("[" not in a[0] and "sys.set" not in a[2] for a in screen.tbl_cari_grup.context_actions_provider())


def test_new_category_and_brand_actions_now_work(screen):
    """Gerçek hata: işlem düğmeleri var olmayan tbl_stok_kategori/tbl_stok_marka adlarına bakıyordu (sessizce hiçbir şey yapmıyordu)."""
    for pid, tbl in (("stok_kategoriler", screen.tbl_kategori), ("stok_markalar", screen.tbl_marka)):
        screen.switch_panel(pid)
        assert screen._get_active_table() is tbl
        n = tbl.rowCount()
        cb = dict(screen._panel_actions(pid))[screen._panel_actions(pid)[0][0]]
        cb()
        assert tbl.rowCount() == n + 1
        tbl.selectRow(n)
        dict(screen._panel_actions(pid))[screen._panel_actions(pid)[1][0]]()
        assert tbl.rowCount() == n


def test_plain_panels_get_a_right_click_menu_but_grids_and_embedded_widgets_keep_their_own(screen):
    from PyQt6.QtCore import Qt

    plain = screen.panels["cari_gruplari"]
    assert plain.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    shown = []
    screen._show_panel_context_menu = lambda src, pos: shown.append(pos)
    plain.customContextMenuRequested.emit(plain.rect().center())
    assert shown == [plain.rect().center()]


def test_dragging_a_section_header_starts_a_drag_only_after_moving_but_a_click_still_toggles(screen, monkeypatch):
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtTest import QTest

    screen.show()
    sb = screen.right_sidebar
    started = []
    monkeypatch.setattr(sb, "_start_drag", lambda key, header: started.append(key))
    hdr = sb.section("hizli").header_btn
    was = sb.section("hizli").is_expanded
    QTest.mouseClick(hdr, Qt.MouseButton.LeftButton)                                # tıklama: açılır/kapanır, sürükleme yok
    assert started == [] and sb.section("hizli").is_expanded != was
    QTest.mousePress(hdr, Qt.MouseButton.LeftButton, pos=QPoint(20, 10))
    QTest.mouseMove(hdr, QPoint(22, 11))                                            # eşik altı: sürükleme başlamaz
    assert started == []
    QTest.mouseMove(hdr, QPoint(60, 40))
    assert started == ["hizli"]


def test_git_panel_has_real_actions_and_none_of_them_is_broken(qapp, db_session, tmp_path, monkeypatch):
    """Gerçek hata: 'Git Durumunu Yenile' var olmayan refresh_all'u çağırıyordu ve sağ panelde başka Git işlemi yoktu."""
    import git_tracker

    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))    # gerçek git_tracker.db'ye dokunma
    screen = GeneralSettingsScreen(db_session=db_session)
    labels = [lab for lab, _cb in screen._panel_actions("surum_git")]
    assert len(labels) >= 6 and any("Git'e Gönder" in x for x in labels) and any("Pull" in x for x in labels)
    started = []
    screen.git_tracker_tab.screen._start_worker = lambda a, p=None: started.append(a)
    for lab, cb in screen._panel_actions("surum_git"):
        if "Fetch" in lab or "Pull" in lab or "(Stash)" in lab or "(Stash Pop)" in lab:
            cb()
    assert started == ["fetch", "pull", "stash", "stash_pop"]
    dict(screen._panel_actions("surum_git"))["🔄 Git Durumunu Yenile"]()                    # hata vermez
    assert callable(screen.git_tracker_tab.refresh_all)
    screen.close()


def test_git_panel_loads_lazily_and_computes_git_state_once_per_refresh(qapp, db_session, tmp_path, monkeypatch):
    """Ayarlar ekranı her açılışta ~30 git süreci başlatıyordu (yavaşlık); Git paneli ilk gösterilince yüklenmeli."""
    import git_tracker
    from src.desktop.services import git_service

    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))
    calls = []
    real = git_service.GitService.run
    monkeypatch.setattr(git_service.GitService, "run", lambda self, args, *a, **k: (calls.append(args[0]), real(self, args, *a, **k))[1])
    s = GeneralSettingsScreen(db_session=db_session)
    assert calls == [] and s.git_tracker_tab.screen._loaded_once is False                  # açılışta git çalışmaz
    s.show()
    s.switch_panel("surum_git")
    qapp.processEvents()
    assert s.git_tracker_tab.screen._loaded_once is True
    n = len(calls)
    s.git_tracker_tab.screen.refresh_advice()
    assert sum(1 for c in calls[n:] if c == "status") == 1                                 # tavsiye + özet tek 'git status' kullanır
    s.close()


def test_every_embedded_widget_method_used_by_menu_actions_exists(screen):
    import inspect
    import re

    src = inspect.getsource(type(screen)._actions_map)
    missing = [f"{tab}.{m}" for tab, m in sorted(set(re.findall(r"self\.(\w+_tab)\.(\w+)\(", src)))
               if not hasattr(getattr(screen, tab, None), m)]
    assert missing == []


def test_git_connection_section_lives_in_the_shell_sidebar_only_on_the_git_menu(qapp, db_session, tmp_path, monkeypatch):
    """Gerçek sorun: profil ekle/düzenle/sil ve Google girişi gömülü ekranın GİZLİ sol panelindeydi; kullanıcı hiç göremiyordu."""
    import git_tracker

    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))
    s = GeneralSettingsScreen(db_session=db_session)
    s.show()
    sb = s.right_sidebar
    panel = s.git_tracker_tab.screen.profile_panel
    assert sb.section("git_baglanti").isAncestorOf(panel) and not s.git_tracker_tab.screen.left_panel.isAncestorOf(panel)
    assert not sb.section("git_baglanti").isVisibleTo(sb)                            # diğer menülerde görünmez
    s.switch_panel("surum_git")
    assert sb.section("git_baglanti").isVisibleTo(sb)
    assert "sys.rp.07" in sb.section("git_baglanti").header_btn.toolTip()
    texts = [tx for _w, tx, _c in sb._entries["git_baglanti"].items]
    assert texts == ["Bağlantı profili ekle", "Profili düzenle", "Profili sil (gizle)", "Etkin yap", "Bağlantıyı test et", "Google ile giriş yap"]
    assert "Sil" in panel.btn_hide.text()
    sb.search.setText("google")                                                        # aranabilir
    assert sb.section("git_baglanti").isVisibleTo(sb) and not sb.section("filtre").isVisibleTo(sb)
    s.switch_panel("cari_gruplari")
    assert not sb.section("git_baglanti").isVisibleTo(sb)
    s.close()


def test_git_menu_actions_include_profile_management_and_login_and_they_work(qapp, db_session, tmp_path, monkeypatch):
    import git_tracker
    from src.desktop.services import git_profile_store as store

    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))
    s = GeneralSettingsScreen(db_session=db_session)
    labels = [lab for lab, _cb in s._panel_actions("surum_git")]
    for need in ("Google ile Giriş", "Bağlantıyı Test", "Profil Ekle", "Profil Düzenle", "Profil Sil"):
        assert any(need in x for x in labels), need
    panel = s.git_tracker_tab.screen.profile_panel
    ok, _m, pid = store.save_profile({"title": "Ana", "repo_url": "https://github.com/baynetteknik/dbar_piton.git", "auth_type": "gcm"}, make_active=True)
    panel.reload(pid)
    reqs = []
    panel.worker_requested.connect(lambda a, p: reqs.append(a))
    actions = dict(s._panel_actions("surum_git"))
    actions["🔵 Google ile Giriş Yap"]()
    actions["🔌 Bağlantıyı Test Et"]()
    assert reqs == ["login", "test_remote"]
    s.close()


def test_refresh_button_gives_visible_feedback(qapp, db_session, tmp_path, monkeypatch):
    """Gerçek sorun: 'Git Durumunu Yenile' işlevsiz görünüyordu (hiçbir geri bildirim yoktu)."""
    import git_tracker

    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))
    s = GeneralSettingsScreen(db_session=db_session)
    toasts = []
    s.toast_requested.connect(lambda m, k: toasts.append((m, k)))
    dict(s._panel_actions("surum_git"))["🔄 Git Durumunu Yenile"]()
    assert toasts and "Yenilendi" in toasts[0][0] and "değişen dosya" in toasts[0][0] and toasts[0][1] == "success"
    assert "Yenilendi" in s.git_tracker_tab.screen.lbl_stage.text()
    assert "Yenilendi" in s.git_tracker_tab.screen.console_drawer.toPlainText()
    s.close()


def test_authentication_failures_offer_google_login_instead_of_a_dead_end_error(qapp, db_session, tmp_path, monkeypatch):
    import git_tracker
    from PyQt6.QtWidgets import QMessageBox
    from src.desktop.services import git_profile_store as store
    from src.desktop.ui.components import git_tracker_screen as gts

    real = ("Push hatası (Uzak depoya aktarılamadı): remote: Invalid username or token. Password authentication is not supported "
            "for Git operations.\nfatal: Authentication failed for 'https://github.com/baynetteknik/dbar_piton.git/'")
    assert gts._is_auth_failure(real) and gts._is_auth_failure("could not read Username for 'https://github.com'")
    assert not gts._is_auth_failure("error: failed to push some refs (non-fast-forward)") and not gts._is_auth_failure("")

    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))
    s = GeneralSettingsScreen(db_session=db_session)
    screen = s.git_tracker_tab.screen
    ok, _m, pid = store.save_profile({"title": "Ana", "repo_url": "https://github.com/baynetteknik/dbar_piton.git", "auth_type": "gcm"}, make_active=True)
    screen.profile_panel.reload(pid)
    reqs = []
    screen.profile_panel.worker_requested.connect(lambda a, p: reqs.append(a))
    shown = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: (shown.append(a[2]), QMessageBox.StandardButton.Yes)[1])
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append("KRITIK"))
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    screen._on_worker_finished(False, real)
    assert reqs == ["login"] and "Google" in shown[0] and "KRITIK" not in shown           # doğrudan giriş önerildi ve başlatıldı
    reqs.clear()
    shown.clear()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    screen._on_worker_finished(False, real)
    assert reqs == []                                                                    # vazgeçilirse giriş başlamaz
    screen._on_worker_finished(False, "error: failed to push some refs")
    assert shown == ["KRITIK"]                                                           # kimlik dışı hatalar eskisi gibi
    s.close()


def test_tooltip_style_helper_is_idempotent_and_never_uses_rounded_corners():
    from src.desktop.ui.components import tooltip_style as ts

    once = ts.with_tooltip("QPushButton{color:red;}")
    assert ts.with_tooltip(once) == once and once.count("QToolTip") == 1 and once.startswith("QPushButton{color:red;}")
    assert "background-color:#2563eb" in ts.QSS and "color:#ffffff" in ts.QSS
    assert "border-radius:0px" in ts.QSS                                             # Windows'ta yuvarlak köşe ipucunu siyah çizer


def test_real_tooltip_window_is_blue_with_white_text_for_a_styled_widget(screen):
    """Gerçek sorun: kendi stil sayfası olan widget'ın ipucu siyah çiziliyordu (uygulama düzeyindeki kural kayboluyordu)."""
    import os

    import pytest
    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QColor
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QToolTip

    if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        pytest.skip("gerçek ekran pikseli gerekir")
    screen.show()
    grp = next(s for s in screen.menu_sections if "CARİ" in s.header_btn.text())
    grp.set_expanded(True)
    QApplication.processEvents()
    btn = screen.menu_buttons["cari_gruplari"]
    QToolTip.showText(btn.mapToGlobal(QPoint(30, 12)), btn.toolTip(), btn)
    QTest.qWait(300)
    tips = [w for w in QApplication.allWidgets() if w.metaObject().className() == "QTipLabel" and w.isVisible()]
    if not tips:
        pytest.skip("bu ortamda ipucu penceresi oluşmadı")
    g = tips[0].geometry()
    px = QColor(QApplication.primaryScreen().grabWindow(0, g.x(), g.y(), g.width(), g.height()).toImage().pixel(6, 6))
    if px.name() == "#000000":
        pytest.skip("oturum ekranı kilitli veya pencere yakalama siyah")
    assert px.name() == "#2563eb"


def test_git_menu_is_split_into_profile_and_git_submenus_with_turkish_labels(qapp, db_session, tmp_path, monkeypatch):
    import git_tracker

    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))
    s = GeneralSettingsScreen(db_session=db_session)
    box = s.menu_sub_boxes["surum_git"]
    assert [sec.title_text for sec, _o in box.groups] == ["👤 PROFİL İŞLEMLERİ", "🌿 GİT İŞLEMLERİ"]
    prof, git = box.groups[0][0], box.groups[1][0]
    inside = lambda sec: [b.text() for b, _l, _c in box.action_buttons if sec.isAncestorOf(b)]     # noqa: E731
    assert inside(prof) == ["➕ Profil Ekle", "✏️ Profil Düzenle", "🗑 Profil Sil", "🔵 Google ile Giriş Yap", "🔌 Bağlantıyı Test Et"]
    git_labels = inside(git)
    assert len(git_labels) == 7 and git_labels[0].startswith("🚀 Git'e Gönder")
    assert "📦 Geçici Sakla (Stash)" in git_labels and "📤 Geri Al (Stash Pop)" in git_labels
    assert "📊 Git Raporu" in git_labels and not any(x in ("📦 Stash", "📦 Stash Pop", "Pop") for x in git_labels)
    assert box.groups[0][1] is False and box.groups[1][1] is True                       # profil kapalı, git işlemleri açık
    assert not prof.is_expanded and git.is_expanded
    assert [c for _b, _l, c in box.action_buttons][:2] == ["sys.set.652.01", "sys.set.652.02"]      # kodlar bölümler boyunca sürer
    s.right_sidebar.search.setText("google")                                            # arama sürerken alt menüler açılır
    assert prof.is_expanded and git.is_expanded
    s.right_sidebar.search.setText("")
    assert not prof.is_expanded and git.is_expanded                                     # temizlenince varsayılana döner
    s.close()


def test_git_screen_left_panel_uses_turkish_stash_names(qapp, db_session, tmp_path, monkeypatch):
    import git_tracker
    from PyQt6.QtWidgets import QPushButton

    monkeypatch.setattr(git_tracker, "DB_PATH", str(tmp_path / "gt.db"))
    s = GeneralSettingsScreen(db_session=db_session)
    texts = [b.text() for b in s.git_tracker_tab.screen.findChildren(QPushButton)]
    assert "📦 Geçici Sakla (Stash)" in texts and "📤 Geri Al" in texts and "📊 Git Raporu (F9)" in texts
    assert "📦 Stash" not in texts and "Pop" not in texts
    s.close()


# ---------------------------------------------------------------- SİSTEM: açılır alt menüler
def _sistem(s):
    return next(sec for sec in s.menu_sections if "SİSTEM" in sec.title_text)


def test_system_group_is_split_into_backup_connections_view_and_general_submenus_with_short_names(screen):
    inner = {t: sec for sec, t, _c in screen.menu_inner_all}
    assert list(inner) == ["🗄️ Yedekleme", "🔌 Bağlantılar", "🎨 Görünüm", "🧾 Genel"]
    of = lambda title: [b.text() for pid, b in screen.menu_buttons.items() if inner[title].isAncestorOf(b)]     # noqa: E731
    assert of("🗄️ Yedekleme") == ["Merkez", "Portal"]
    assert of("🔌 Bağlantılar") == ["CMS / ERP", "Portal Yayın", "Online Portal"]
    assert of("🎨 Görünüm") == ["Profiller", "Ekran Gridleri", "Form Tasarımları"]
    assert of("🧾 Genel") == ["E-Posta", "KDV", "Kuruş Hanesi"]
    flat = [b.text() for b in screen.menu_buttons.values() if _sistem(screen).isAncestorOf(b) and not any(i.isAncestorOf(b) for i in inner.values())]
    assert flat == ["Güvenlik", "Sürüm & Git", "Yardım"]                                # alt menüsüz öğeler grupta düz kalır
    names = [b.text() for b in screen.menu_buttons.values()]
    assert not any("Ayarları" in n or "Tanımları" in n and n in ("KDV Tanımları", "Kuruş Hanesi Tanımları") for n in names)
    assert all(sec.is_expanded is False for sec, _t, _c in screen.menu_inner_all)       # hepsi kapalı gelir
    assert [c for _s, _t, c in screen.menu_inner_all] == ["sys.set.61", "sys.set.62", "sys.set.63", "sys.set.64"]
    assert "sys.set.62" in inner["🔌 Bağlantılar"].header_btn.toolTip()                 # kod ipucunda


def test_clicking_a_submenu_item_opens_group_and_submenu_and_shows_the_short_breadcrumb(screen):
    screen.on_menu_clicked("portal_yedek", screen.menu_buttons["portal_yedek"])
    inner = screen.menu_inner_sections["portal_yedek"]
    assert inner.is_expanded and _sistem(screen).is_expanded and screen.active_panel_id == "portal_yedek"
    assert not screen.menu_inner_sections["cms_baglantilari"].is_expanded                # diğer alt menüler kapalı kalır
    assert "Genel Ayarlar > Yedekleme > Portal" in screen.lbl_breadcrumb.text()          # 'ayarlar' tekrarı yok, bağlam üst menüde
    assert "[sys.set.612]" in screen.lbl_breadcrumb.text()
    screen.on_menu_clicked("kdv_oranlari", screen.menu_buttons["kdv_oranlari"])
    assert "Genel Ayarlar > Genel > KDV" in screen.lbl_breadcrumb.text()
    screen.on_menu_clicked("guvenlik", screen.menu_buttons["guvenlik"])                   # alt menüsüz: yol yalnızca menü
    assert screen.lbl_breadcrumb.text().split("Genel Ayarlar > ")[1].startswith("Güvenlik")


def test_menu_search_finds_submenu_items_by_name_code_and_submenu_and_hides_empty_submenus(screen):
    screen.show()
    screen.switch_panel("firma_bilgileri")   # varsayılan açılış artık "settings_hub" (sol panel kapalı); arama görünürlüğü normal bir menüde test edilir
    vis = lambda: {pid for pid, (w, *_r) in screen.menu_item_containers.items() if w.isVisibleTo(screen)}       # noqa: E731
    screen.menu_search_input.setText("kdv")
    assert vis() == {"kdv_oranlari"}
    assert screen.menu_inner_sections["kdv_oranlari"].isVisibleTo(screen)
    assert not screen.menu_inner_sections["portal_yedek"].isVisibleTo(screen)             # eşleşmeyen alt menü gizlenir
    assert screen.menu_inner_sections["kdv_oranlari"].is_expanded and _sistem(screen).is_expanded
    screen.menu_search_input.setText("642")                                              # menü koduna göre
    assert vis() == {"kdv_oranlari"}
    screen.menu_search_input.setText("bağlantılar")                                      # alt menü adına göre: tüm öğeleri
    assert vis() == {"cms_baglantilari", "portal_yayin", "online_portal"}
    screen.menu_search_input.setText("sys.set.61")                                       # alt menü koduna göre
    assert vis() == {"yedek_merkezi", "portal_yedek"}
    screen.menu_search_input.setText("kurus")                                            # Türkçe harf duyarsız
    assert vis() == {"sayi_bicimi"}
    screen.menu_search_input.setText("")
    assert all(not w.isHidden() for w, *_r in screen.menu_item_containers.values())
    assert all(not sec.isHidden() and not sec.is_expanded for sec, _t, _c in screen.menu_inner_all)


def test_code_mode_reaches_submenu_headers_too(screen):
    sec = next(s for s, t, _c in screen.menu_inner_all if "Yedekleme" in t)
    assert sec.code_label.isHidden()
    screen.set_code_mode("rozet")
    assert sec.code_label.text() == "sys.set.61" and not sec.code_label.isHidden()
    screen.set_code_mode("gizli")
    assert sec.code_label.isHidden() and "sys.set.61" not in sec.header_btn.toolTip()


def test_kdv_panel_is_a_standard_editable_grid_that_persists(qapp, db_session):
    """KDV Oranları paneli 2026-09-30'dan itibaren firmaya bağlı (`KdvTanimi.company_id`) — panel bir
    aktif firma gerektiriyor, aksi halde boş görünür (bkz. `gelistirme/13_sirket_tanimlari/tasarim.md`)."""
    from src.desktop.services.company_service import CompanyService
    firma_svc = CompanyService(db_session)
    firma_id = firma_svc.save({**CompanyService.blank_company(), "code": "TST", "short_name": "Test A.Ş."}).company_id
    firma_svc.aktif_firma_sec(firma_id)

    s = GeneralSettingsScreen(db_session=db_session)
    s.switch_panel("kdv_oranlari")
    t = s.tbl_kdv
    assert isinstance(t, EntryTableView) and t.model().item(0, 0).flags() & Qt.ItemFlag.ItemIsEditable
    assert [_baslik(t, i) for i in range(4)] == ["KOD", "AÇIKLAMA", "ORAN (%)", "DURUM"]
    assert [t.item(r, 2).text() for r in range(t.rowCount())] == ["0", "1", "10", "20"]
    dict(s._panel_actions("kdv_oranlari"))["➕ Yeni KDV Ekle"]()
    t.item(t.rowCount() - 1, 0).setText("KDV8")
    t.item(t.rowCount() - 1, 2).setText("8")
    s.save_current_panel()
    s.close()
    s2 = GeneralSettingsScreen(db_session=db_session)
    codes = [s2.tbl_kdv.item(r, 0).text() for r in range(s2.tbl_kdv.rowCount())]
    assert codes == ["KDV0", "KDV1", "KDV10", "KDV20", "KDV8"]
    s2.tbl_kdv.selectRow(4)
    dict(s2._panel_actions("kdv_oranlari"))["🗑️ Seçiliyi Sil"]()
    assert s2.tbl_kdv.rowCount() == 4
    assert "KDV" in " ".join(lab for lab, _cb in s2._panel_actions("kdv_oranlari"))
    s2.close()


def test_odeme_planlari_odeme_tipi_hedef_hesap_banka_plani_ve_otomatik_fis_kaydedip_geri_yuklenir(qapp, db_session):
    """2026-10-02: Ödeme Planları artık yapılandırılmış Ödeme Tipi + Hedef Hesap (FinansHesap FK) +
    Banka Ödeme Planı (BankaOdemePlani FK) + Otomatik Fiş taşıyor (bkz. gelistirme/04_odeme_planlari/
    tasarim.md, 04.05/04.11) — faturadan otomatik kasa/banka fişi oluşturmanın temeli. Dördü de grid'de
    ComboDelegate ile düzenlenir, DB'ye yapılandırılmış kod olarak yazılır, geri okununca aynı görünür
    metne döner."""
    from PyQt6.QtGui import QStandardItem

    from src.core.models import BankaOdemePlani, FinansHesap, PaymentPlan

    kasa = FinansHesap(tur="kasa", kod="K01", ad="Merkez Kasa", aktif=True)
    db_session.add(kasa)
    banka_plani = BankaOdemePlani(
        kod="GARANTI3TAK", aciklama="Garanti 3 Taksit", komisyon_orani=2.5, bsmv_orani=5.0, is_active=True,
    )
    db_session.add(banka_plani)
    db_session.commit()

    s = GeneralSettingsScreen(db_session=db_session)
    s.switch_panel("odeme_planlari")
    t = s.tbl_odeme
    assert [_baslik(t, i) for i in range(8)] == [
        "KOD", "AÇIKLAMA", "GÜN", "ÖDEME TİPİ", "HEDEF HESAP", "BANKA ÖDEME PLANI", "OTOMATİK FİŞ", "DURUM",
    ]
    # "NAKIT" varsayılan satırı: Ödeme Tipi zaten "Nakit" — Hedef Hesap'ı K01'e bağla.
    nakit_row = next(r for r in range(t.rowCount()) if t.item(r, 0).text() == "NAKIT")
    t.item(nakit_row, 4).setText("K01 — Merkez Kasa")
    # Yeni bir satır: POS tipi, Banka Ödeme Planı'na bağlı, otomatik fiş kapalı.
    r = t.rowCount()
    t.insertRow(r)
    for c, val in enumerate(
        ["POSPLAN", "POS İLE ÖDEME", "0", "POS", "K01 — Merkez Kasa", "GARANTI3TAK — Garanti 3 Taksit", "Hayır", "Aktif"],
    ):
        t.setItem(r, c, QStandardItem(val))

    s.save_current_panel()
    s.close()

    nakit = db_session.query(PaymentPlan).filter_by(code="NAKIT").one()
    assert nakit.odeme_tipi == "nakit"
    assert nakit.hedef_finans_hesap_id == kasa.id
    assert nakit.otomatik_fis_olustur is True

    pos = db_session.query(PaymentPlan).filter_by(code="POSPLAN").one()
    assert pos.odeme_tipi == "pos"
    assert pos.hedef_finans_hesap_id == kasa.id
    assert pos.banka_odeme_plani_id == banka_plani.id
    assert pos.otomatik_fis_olustur is False

    s2 = GeneralSettingsScreen(db_session=db_session)
    s2.switch_panel("odeme_planlari")
    t2 = s2.tbl_odeme
    nakit_row2 = next(r for r in range(t2.rowCount()) if t2.item(r, 0).text() == "NAKIT")
    assert t2.item(nakit_row2, 4).text() == "K01 — Merkez Kasa"
    pos_row2 = next(r for r in range(t2.rowCount()) if t2.item(r, 0).text() == "POSPLAN")
    assert t2.item(pos_row2, 3).text() == "POS"
    assert t2.item(pos_row2, 5).text() == "GARANTI3TAK — Garanti 3 Taksit"
    assert t2.item(pos_row2, 6).text() == "Hayır"
    s2.close()


def test_odeme_plani_ekle_dialog_popup_grid_e_satir_ekler_ve_duzenler(qapp, db_session, monkeypatch):
    """2026-10-02: "➕ Yeni Plan Ekle" artık popup (Dönem'deki gibi) açıyor; grid hücreleri hâlâ doğrudan
    düzenlenebilir kalıyor (popup EK bir giriş yolu, mevcut hızlı düzenlemeyi kaldırmıyor). "✏️ Seçiliyi
    Düzenle" aynı popup'ı seçili satırla önceden doldurup açar."""
    from src.desktop.ui.widgets.odeme_plani_ekle_dialog import OdemePlaniEkleDialog

    s = GeneralSettingsScreen(db_session=db_session)
    s.switch_panel("odeme_planlari")
    before = s.tbl_odeme.rowCount()

    monkeypatch.setattr(OdemePlaniEkleDialog, "exec", lambda self: 1)
    monkeypatch.setattr(
        OdemePlaniEkleDialog, "deger",
        lambda self: {
            "kod": "YENIPLAN", "aciklama": "Yeni Plan", "gun": "15", "tip": "Havale/EFT",
            "hesap": s._HEDEF_HESAP_BOS, "banka_plani": s._BANKA_PLANI_BOS, "otomatik": "Evet", "aktif": "Aktif",
        },
    )
    dict(s._panel_actions("odeme_planlari"))["➕ Yeni Plan Ekle"]()
    assert s.tbl_odeme.rowCount() == before + 1
    son = s.tbl_odeme.rowCount() - 1
    assert s.tbl_odeme.item(son, 0).text() == "YENIPLAN"
    assert s.tbl_odeme.item(son, 3).text() == "Havale/EFT"
    assert s.tbl_odeme.selectedIndexes()[0].row() == son   # popup'tan sonra yeni satır seçili

    # Grid hücresi hâlâ doğrudan düzenlenebilir (popup bunu engellemiyor).
    s.tbl_odeme.item(son, 1).setText("Elle Düzenlendi")
    assert s.tbl_odeme.item(son, 1).text() == "Elle Düzenlendi"

    # "✏️ Seçiliyi Düzenle" — aynı satırı günceller, yeni satır eklemez.
    monkeypatch.setattr(
        OdemePlaniEkleDialog, "deger",
        lambda self: {
            "kod": "YENIPLAN", "aciklama": "Düzenlendi", "gun": "20", "tip": "Havale/EFT",
            "hesap": s._HEDEF_HESAP_BOS, "banka_plani": s._BANKA_PLANI_BOS, "otomatik": "Hayır", "aktif": "Pasif",
        },
    )
    dict(s._panel_actions("odeme_planlari"))["✏️ Seçiliyi Düzenle"]()
    assert s.tbl_odeme.rowCount() == before + 1              # satır sayısı artmadı
    assert s.tbl_odeme.item(son, 1).text() == "Düzenlendi"
    assert s.tbl_odeme.item(son, 7).text() == "Pasif"
    s.close()


def test_cok_turlu_satirlari_duzenle_kaydedilmemis_plani_uyarir_kaydedilmisi_acar(qapp, db_session, monkeypatch):
    """2026-10-02 (04.11): "📑 Çok Türlü Satırları Düzenle" — seçili satır henüz DB'ye kaydedilmemiş bir
    plansa (kod eşleşmiyor) kullanıcıyı önce kaydetmesi için uyarır; kaydedilmiş bir plansa
    `OdemePlaniSatirlariDialog`'u doğru `plan.id` ile açar."""
    from PyQt6.QtWidgets import QMessageBox

    from src.core.models import PaymentPlan
    from src.desktop.ui.widgets.odeme_plani_satirlari_dialog import (
        OdemePlaniSatirlariDialog,
    )

    s = GeneralSettingsScreen(db_session=db_session)
    s.switch_panel("odeme_planlari")
    t = s.tbl_odeme

    # Henüz kaydedilmemiş (DB'de karşılığı olmayan) bir kod seçelim.
    from PyQt6.QtGui import QStandardItem
    r = t.rowCount()
    t.insertRow(r)
    t.setItem(r, 0, QStandardItem("KAYITSIZ"))
    t.selectRow(r)
    uyari_gosterildi = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: uyari_gosterildi.append(1)))
    dict(s._panel_actions("odeme_planlari"))["📑 Çok Türlü Satırları Düzenle"]()
    assert uyari_gosterildi == [1]

    # Şimdi gerçek, DB'ye kayıtlı bir plan seçelim.
    plan = PaymentPlan(code="GERCEKPLAN", description="Test")
    db_session.add(plan)
    db_session.commit()
    r2 = t.rowCount()
    t.insertRow(r2)
    t.setItem(r2, 0, QStandardItem("GERCEKPLAN"))
    t.selectRow(r2)
    acilan = []
    monkeypatch.setattr(OdemePlaniSatirlariDialog, "exec", lambda self: acilan.append(self.plan_id) or 0)
    dict(s._panel_actions("odeme_planlari"))["📑 Çok Türlü Satırları Düzenle"]()
    assert acilan == [plan.id]
    s.close()


def test_banka_odeme_planlari_paneli_komisyon_bsmv_hizmet_bedeli_kaydedip_geri_yuklenir(qapp, db_session):
    """2026-10-02: Banka Ödeme Planları — taksit sayısına göre değişen komisyon/BSMV/hizmet bedeli, ayrı
    bir menü (FİNANS TANIMLARI > Banka Ödeme Planları, bkz. gelistirme/04_odeme_planlari/tasarim.md,
    04.11). `BankaOdemePlani.net_tutar()` komisyon TUTARI üzerinden BSMV hesaplar."""
    from PyQt6.QtGui import QStandardItem

    from src.core.models import BankaOdemePlani, FinansHesap

    pos_hesap = FinansHesap(tur="pos", kod="POS01", ad="Garanti POS", aktif=True)
    db_session.add(pos_hesap)
    db_session.commit()

    s = GeneralSettingsScreen(db_session=db_session)
    s.switch_panel("banka_odeme_planlari")
    t = s.tbl_banka_odeme
    assert [_baslik(t, i) for i in range(8)] == [
        "KOD", "AÇIKLAMA", "HESAP", "TAKSİT SAYISI", "KOMİSYON %", "BSMV %", "HİZMET BEDELİ", "DURUM",
    ]
    r = t.rowCount()
    t.insertRow(r)
    for c, val in enumerate(
        ["GARANTI3TAK", "Garanti 3 Taksit", "POS01 — Garanti POS", "3", "2.50", "5.00", "1.00", "Aktif"],
    ):
        t.setItem(r, c, QStandardItem(val))

    s.save_current_panel()
    s.close()
    qapp.processEvents()   # bu paneldeki ComboDelegate'ler ekranı canlı tutuyor; kapanışın gerçekten işlenmesi için

    plan = db_session.query(BankaOdemePlani).filter_by(kod="GARANTI3TAK").one()
    assert plan.finans_hesap_id == pos_hesap.id
    assert plan.taksit_sayisi == 3
    assert plan.komisyon_orani == pytest.approx(2.5)
    assert plan.bsmv_orani == pytest.approx(5.0)
    assert plan.hizmet_bedeli == pytest.approx(1.0)
    assert plan.is_active
    assert plan.net_tutar(1000) == pytest.approx(1000 - 25 - 1.25 - 1.0)   # 1000 - komisyon - bsmv - hizmet

    s2 = GeneralSettingsScreen(db_session=db_session)
    s2.switch_panel("banka_odeme_planlari")
    t2 = s2.tbl_banka_odeme
    row = next(r for r in range(t2.rowCount()) if t2.item(r, 0).text() == "GARANTI3TAK")
    assert t2.item(row, 2).text() == "POS01 — Garanti POS"
    assert t2.item(row, 4).text() == "2.50"
    s2.close()
    qapp.processEvents()



