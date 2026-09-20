"""Genel Ayarlar: menü/işlem kodları, isim+kod araması, sağ panelin sürükle-bırak sıralaması, AppGrid, sağ tık işlemleri."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QTableWidget

from src.desktop.services import settings_menu as sm
from src.desktop.ui.components.app_grid import AppGrid
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


def test_codes_are_shown_as_badges_below_names_and_can_be_toggled(screen, db_session):
    m = screen.menu_buttons["cari_gruplari"]
    assert m.text() == "Cari Grupları" and m.code() == "sys.set.501" and m.code_visible()   # kod adın ALTINDA rozet, metne eklenmez
    grp = screen.menu_sections[4]
    assert grp.code_label.text() == "sys.set.50" and not grp.code_label.isHidden()
    screen.switch_panel("cari_gruplari")
    assert "[sys.set.501]" in screen.lbl_breadcrumb.text() and "sys.set.001" in screen.lbl_breadcrumb.text()
    btn, _label, code = screen.menu_sub_boxes["cari_gruplari"].action_buttons[0]
    assert code == "sys.set.501.01" and btn.code() == code and btn.code_visible() and code in btn.toolTip()
    assert "[" not in btn.text()
    assert screen.right_sidebar.section("filtre").code_label.text() == "sys.rp.02"
    yazdir = screen.right_sidebar._entries["yazdir"].items[0][0]
    assert yazdir.code() == "sys.rp.03.01" and yazdir.code_visible()
    screen.chk_show_codes.setChecked(False)
    assert not m.code_visible() and not btn.code_visible() and not yazdir.code_visible()
    assert grp.code_label.isHidden() and screen.right_sidebar.section("filtre").code_label.isHidden()
    assert code in btn.toolTip()                                                    # ipucunda kod kalır
    assert sm.show_codes(db_session) is False                                       # tercih kaydedildi
    screen.chk_show_codes.setChecked(True)
    assert m.code_visible() and not grp.code_label.isHidden() and yazdir.code_visible()


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
def test_all_definition_tables_are_standard_appgrids_with_theme_style(screen):
    screen.switch_panel("yetkiler")
    names = [n for n in dir(screen) if n.startswith("tbl_")]
    assert {"tbl_sube", "tbl_donem", "tbl_odeme", "tbl_fiyat", "tbl_kategori", "tbl_marka", "tbl_birim", "tbl_depo",
            "tbl_cari_grup", "tbl_yetkiler", "tbl_lockout"} <= set(names)
    for n in names:
        t = getattr(screen, n)
        assert isinstance(t, AppGrid) and type(t) is not QTableWidget, n
        assert "font-family" in t.styleSheet() and t.alternatingRowColors() and not t.verticalHeader().isVisible()
        assert t.horizontalHeaderItem(0).text() == t.horizontalHeaderItem(0).text().upper()      # standart BÜYÜK harf başlık
    assert screen.tbl_cari_grup.horizontalHeaderItem(0).text() == "GRUP KODU"
    assert screen.tbl_kategori.horizontalHeaderItem(1).text() == "ÜST KATEGORİ"                # Türkçe büyük harf (i → İ)
    assert screen.tbl_cari_grup.editTriggers() != QTableWidget.EditTrigger.NoEditTriggers      # tanımlar düzenlenebilir
    assert screen.tbl_yetkiler.editTriggers() == QTableWidget.EditTrigger.NoEditTriggers       # matris salt okunur
    assert screen.tbl_yetkiler.columnCount() >= 2


def test_context_actions_are_the_same_as_the_right_panel_and_actually_work(screen):
    screen.switch_panel("cari_gruplari")
    acts = screen.tbl_cari_grup.context_actions_provider()
    labels = [a[0] for a in acts]
    assert any("Yeni Grup Ekle" in x and "[sys.set.501.01]" in x for x in labels)
    right = [lab for _b, lab, _c in screen.menu_sub_boxes["cari_gruplari"].action_buttons]
    assert [x.split("  [")[0] for x in labels] == right                                       # tek kaynak
    n = screen.tbl_cari_grup.rowCount()
    dict((x.split("  [")[0], cb) for x, cb in acts)["➕ Yeni Grup Ekle"]()
    assert screen.tbl_cari_grup.rowCount() == n + 1
    screen.chk_show_codes.setChecked(False)
    assert all("[" not in a[0] for a in screen.tbl_cari_grup.context_actions_provider())


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
        if "Fetch" in lab or "Pull" in lab or lab.endswith("Stash") or "Stash Pop" in lab:
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
