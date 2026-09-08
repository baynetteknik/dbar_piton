"""DocumentDetailScreen + DocumentExpensesGrid + save_payload/load_payload testleri."""

import sys

import pytest
from PyQt6.QtWidgets import QApplication

from src.core.database import DatabaseManager
from src.desktop.ui.screens.document_detail_screen import DocumentDetailScreen
from src.desktop.ui.widgets.document_expenses_grid import DocumentExpensesGrid


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def db():
    return DatabaseManager(db_path=":memory:").get_db()


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    """Testlerde QMessageBox modal diyalogları event loop'u kilitlemesin."""
    from PyQt6.QtWidgets import QMessageBox
    ok = QMessageBox.StandardButton.Ok
    yes = QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: yes))


def test_expenses_grid_percent_and_amount(qapp):
    g = DocumentExpensesGrid()
    g.set_base_amount(10_000)
    captured = {}
    g.expenses_changed.connect(lambda d: captured.update(d))
    g.add_row({"tur": "İndirim", "sekil": "Yüzde (%)", "deger": "5"})
    g.add_row({"tur": "Masraf", "sekil": "Tutar", "deger": "250"})
    g._recalc_all()
    assert captured["indirim"] == pytest.approx(500.0)
    assert captured["masraf"] == pytest.approx(250.0)


def test_screen_totals_wiring(qapp):
    s = DocumentDetailScreen()
    s.lines.add_row({"kod": "A", "miktar": "10", "birim_fiyat": "100",
                     "iskonto_yuzde": "0", "kdv_yuzde": "20"})
    s.lines._emit_totals()
    # 10*100 = 1000 matrah, 200 kdv -> 1200
    assert s.toplam.get_grand_total() == pytest.approx(1200.0)
    # "yapılan iş" (KDV yok) masraf -> yalnız matrahı artırır
    s.expenses.add_row({"tur": "Masraf", "sekil": "Tutar", "deger": "300", "kdv": "0"})
    s.expenses._recalc_all()
    # matrah 1300, kdv 200 -> 1500
    assert s.toplam.get_grand_total() == pytest.approx(1500.0)
    # "+ KDV" masraf -> matrah + oransal KDV
    s.expenses.add_row({"tur": "Masraf", "sekil": "Tutar", "deger": "100", "kdv": "20"})
    s.expenses._recalc_all()
    # matrah 1400, kdv 200 + 20 -> 1620
    assert s.toplam.get_grand_total() == pytest.approx(1620.0)
    # KDV dağılım tablosu 1 satır (%20 — kalemler + masraf birleşik)
    assert s.kdv_model.rowCount() == 1


def test_expenses_esitle_bidirectional(qapp):
    """'Eşitle' hem yukarı hem aşağı çalışır ve toplamı tam olarak hedefe getirir."""
    s = DocumentDetailScreen()
    s.lines.add_row({"kod": "A", "miktar": "1", "birim_fiyat": "3550",
                     "iskonto_yuzde": "0", "kdv_yuzde": "0"})
    s.lines._emit_totals()
    assert s.toplam.get_grand_total() == pytest.approx(3550.0)

    # ara toplamı 3550 -> 3600'e eşitle (yukarı: +50 masraf)
    s.expenses.clear_rows()
    s.expenses.add_row({"sekil": "Toplamı Eşitle", "deger": "3600"})
    s.expenses._recalc_all()
    assert s.toplam.get_grand_total() == pytest.approx(3600.0)

    # aynı satırı 3500'e çek (aşağı: -50 indirim)
    from src.desktop.ui.widgets.document_expenses_grid import COL_DEGER
    s.expenses.model.item(0, COL_DEGER).setText("3500")
    assert s.toplam.get_grand_total() == pytest.approx(3500.0)


def test_expenses_genel_toplam_esitle(qapp):
    """'G.Toplamı Eşitle' KDV dahil genel toplamı geri besleme döngüsüyle yakınsatır."""
    s = DocumentDetailScreen()
    s.lines.add_row({"kod": "A", "miktar": "1", "birim_fiyat": "3550",
                     "iskonto_yuzde": "0", "kdv_yuzde": "20"})
    s.lines._emit_totals()
    # 3550 matrah + 710 kdv -> 4260
    assert s.toplam.get_grand_total() == pytest.approx(4260.0)
    s.expenses.clear_rows()
    s.expenses.add_row({"sekil": "G.Toplamı Eşitle", "deger": "4300"})
    s.expenses._recalc_all()
    assert s.toplam.get_grand_total() == pytest.approx(4300.0, abs=0.01)


def test_screen_has_sidebars_and_bottom_tabs(qapp):
    s = DocumentDetailScreen()
    assert s.left_panel is not None
    assert s.right_panel is not None
    tabs = [s.bottom_tabs.tabText(i).strip() for i in range(s.bottom_tabs.count())]
    assert tabs[0].startswith("A")
    assert len(tabs) == 4
    # F7 / F6 katlanır bölümler
    assert "F7" in s.sec_ust_form.title_text
    assert "F6" in s.sec_alt.title_text


def test_bottom_area_sections_equal_height(qapp):
    s = DocumentDetailScreen()
    h = s.toplam.minimumHeight()
    assert s.bottom_tabs.minimumHeight() == h == s.bottom_tabs.maximumHeight()
    assert s.notlar.minimumHeight() == h == s.notlar.maximumHeight()
    assert h > 200  # tek satıra sıkışmayacak kadar


def test_share_export_handlers_wired(qapp):
    s = DocumentDetailScreen()
    for name in ("_on_export_excel", "_on_email", "_on_whatsapp",
                 "_on_copy_link", "_on_share", "_require_saved"):
        assert callable(getattr(s, name))


def test_require_saved_returns_none_when_user_declines(qapp, db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))
    s = DocumentDetailScreen(db_session=db)
    s.lines.clear_rows()
    s.lines.add_row({"kod": "K1", "miktar": "1", "birim_fiyat": "10"})
    assert s._require_saved("Test") is None
    assert s.doc_id is None


def test_column_profile_combo_and_save(qapp, monkeypatch):
    import PyQt6.QtWidgets as W
    s = DocumentDetailScreen()
    assert s.cmb_profile.count() >= 1
    pname = "PytestKolonProfili"
    monkeypatch.setattr(W.QInputDialog, "getText",
                        staticmethod(lambda *a, **k: (pname, True)))
    try:
        s._on_save_column_profile()
        names = [s.cmb_profile.itemText(i) for i in range(s.cmb_profile.count())]
        assert pname in names
    finally:
        try:
            s.lines.grid.delete_column_profile(pname)
        except Exception:
            pass


def test_expenses_grid_row_highlight(qapp):
    from PyQt6.QtWidgets import QAbstractItemView
    s = DocumentDetailScreen()
    tv = s.expenses.grid.table_view
    assert tv.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows
    assert "item:selected" in tv.styleSheet()


def test_row_move_up_down(qapp):
    s = DocumentDetailScreen()
    s.lines.clear_rows()
    for c in ("A", "B", "C"):
        s.lines.add_row({"kod": c, "miktar": "1", "birim_fiyat": "10"})
    from src.desktop.ui.widgets.document_lines_grid import COL_KOD, COL_SEQ
    s.lines.grid.table_view.selectRow(2)  # C
    s.lines.move_selected_up()
    codes = [s.lines.model.item(r, COL_KOD).text() for r in range(s.lines.model.rowCount())]
    assert codes == ["A", "C", "B"]
    seqs = [s.lines.model.item(r, COL_SEQ).text() for r in range(s.lines.model.rowCount())]
    assert seqs == ["1", "2", "3"]


def test_save_new_resets(qapp, db):
    s = DocumentDetailScreen(db_session=db)
    s.cari.txt_cari_unvan.setText("X LTD")
    s.lines.add_row({"kod": "K1", "miktar": "2", "birim_fiyat": "10", "kdv_yuzde": "20"})
    s.lines._emit_totals()
    s._on_save_new()
    assert s.doc_id is None
    assert s.txt_doc_no.text() == ""
    assert s.lines.model.rowCount() == 1
    assert not [x for x in s.lines.get_lines() if x["kod"]]


def test_build_print_data_maps_live_form(qapp):
    s = DocumentDetailScreen()
    s.cari.txt_cari_unvan.setText("ACME ENDÜSTRİ A.Ş.")
    s.cari.txt_sevk_adres.setText("OSB 4. Cad. No:18 BURSA")
    s.txt_doc_no.setText("TK-2026-0042")
    s.lines.clear_rows()
    s.lines.add_row({"kod": "STK-01", "aciklama": "Ürün A", "miktar": "2",
                     "birim": "Adet", "birim_fiyat": "100", "iskonto_yuzde": "0",
                     "kdv_yuzde": "20"})
    s.lines.add_row({"kod": "", "aciklama": "", "miktar": "1"})  # boş satır -> atlanmalı
    s.lines._emit_totals()

    data = s._build_print_data()
    assert data["musteri"]["adi"] == "ACME ENDÜSTRİ A.Ş."
    assert data["belge"]["teklif_no"] == "TK-2026-0042"
    assert len(data["kalemler"]) == 1
    k = data["kalemler"][0]
    assert (k["kod"], k["sira_no"], k["miktar"]) == ("STK-01", 1, 2.0)
    assert data["toplamlar"]["genel_toplam"] == pytest.approx(240.0)


def test_tr_date_helper():
    from src.desktop.ui.screens.document_detail_screen import _tr_date
    assert _tr_date("2026-09-07") == "07.09.2026"
    assert _tr_date("") == ""
    assert _tr_date("garbage") == "garbage"


def test_print_preview_opens_with_live_data(qapp, monkeypatch):
    """_open_print_preview, seçili şablon + canlı veriyle önizleme servisini çağırır."""
    import src.desktop.designer.services.teklif_print_service as svc_mod

    captured = {}

    def fake_preview(self, data, parent=None):
        captured["data"] = data
        captured["template"] = str(self.template_path)
        return 0

    monkeypatch.setattr(svc_mod.TeklifPrintService, "preview_with_data", fake_preview)

    s = DocumentDetailScreen()
    s.lines.clear_rows()
    s.lines.add_row({"kod": "K1", "aciklama": "X", "miktar": "1", "birim_fiyat": "10",
                     "kdv_yuzde": "20"})
    s.lines._emit_totals()
    s._open_print_preview()

    assert "data" in captured
    assert captured["template"].endswith(".json")
    assert captured["data"]["kalemler"][0]["kod"] == "K1"


def test_template_selector_populated(qapp):
    s = DocumentDetailScreen()
    assert s._tpl_selector.count() >= 1
    # ilk kayıt bir şablon yolu (json) taşımalı
    assert str(s._tpl_selector.itemData(0)).endswith(".json")


def test_persist_removes_empty_rows(qapp, db):
    s = DocumentDetailScreen(db_session=db)
    s.lines.clear_rows()
    s.lines.add_row({"kod": "K1", "miktar": "1", "birim_fiyat": "100", "kdv_yuzde": "20"})
    s.lines.add_row({})          # boş -> kayıtta silinmeli
    s.lines.add_row({})          # boş -> kayıtta silinmeli
    s.lines._emit_totals()
    assert s._persist() is True
    assert s.lines.model.rowCount() == 1
    assert s.lines.get_lines()[0]["kod"] == "K1"


def test_footer_and_context_actions_exist(qapp):
    from PyQt6.QtWidgets import QToolButton
    s = DocumentDetailScreen()
    # alt bar: bölünmüş Kaydet butonu (birincil = kaydet+kapat) + menü
    assert isinstance(s.btn_save, QToolButton)
    assert "Kapat" in s.btn_save.text()
    assert s.btn_preview.text().startswith("👁️")
    save_menu_labels = [a.text() for a in s._save_menu.actions() if a.text()]
    assert any("Kaydet ve Kapat" in x for x in save_menu_labels)
    assert any("Devam" in x for x in save_menu_labels)
    assert any("Yeni" in x for x in save_menu_labels)
    assert any("Yazdır" in x for x in save_menu_labels)
    # sağ tık menüsü belge eylemlerini üretir
    from PyQt6.QtWidgets import QMenu
    m = QMenu()
    s._populate_document_actions(m)
    labels = [a.text() for a in m.actions() if a.text()]
    assert any("Kaydet ve Yazdır" in x for x in labels)
    assert any("PDF" in x for x in labels)
    assert callable(s.lines.document_actions_provider)


def test_empty_document_cannot_be_saved(qapp, db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: (warned.append(a[2] if len(a) > 2 else ""),
                                                      QMessageBox.StandardButton.Ok)[1]))
    s = DocumentDetailScreen(db_session=db)
    s.lines.clear_rows()
    s.lines.add_row()  # tek boş satır
    assert s._persist() is False
    assert any("Boş belge" in t for t in warned)
    assert s.doc_id is None


def test_save_without_cari_warns_but_allows(qapp, db, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    asked = []

    def q(*a, **k):
        asked.append(a[2] if len(a) > 2 else "")
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, "question", staticmethod(q))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    s = DocumentDetailScreen(db_session=db)
    s.lines.clear_rows()
    s.lines.add_row({"kod": "K1", "miktar": "1", "birim_fiyat": "10", "kdv_yuzde": "20"})
    assert s._persist() is True   # Yes -> kaydedilir
    assert any("cari" in t.lower() for t in asked)
    assert s.doc_id is not None


def test_repeated_save_no_unique_clash(qapp, db):
    s = DocumentDetailScreen(db_session=db)
    s.cari.txt_cari_unvan.setText("ACME")
    s.lines.clear_rows()
    s.lines.add_row({"kod": "K1", "miktar": "1", "birim_fiyat": "10", "kdv_yuzde": "20"})
    assert s._persist() is True
    no1 = s.txt_doc_no.text()
    assert s._persist() is True          # ikinci kez -> UPDATE, çakışma yok
    assert s.txt_doc_no.text() == no1


def test_primary_save_closes_screen(qapp, db):
    s = DocumentDetailScreen(db_session=db)
    s.lines.clear_rows()
    s.lines.add_row({"kod": "K1", "miktar": "1", "birim_fiyat": "10", "kdv_yuzde": "20"})
    s.lines._emit_totals()
    closed = []
    s.closed.connect(lambda: closed.append(True))
    s.btn_save.click()               # birincil tık = kaydet + kapat
    assert s.doc_id is not None      # kaydedildi
    assert closed == [True]          # listeye dön (ekran kapandı)


def test_save_print_confirms_when_unsaved(qapp, db, monkeypatch):
    s = DocumentDetailScreen(db_session=db)
    s.cari.txt_cari_unvan.setText("ACME LTD")  # cari uyarısı çıkmasın
    s.lines.clear_rows()
    s.lines.add_row({"kod": "K1", "miktar": "1", "birim_fiyat": "50", "kdv_yuzde": "20"})
    s.lines._emit_totals()

    seen = {}
    monkeypatch.setattr(
        type(s), "_open_print_preview",
        lambda self: seen.setdefault("preview", True),
    )
    texts = []

    def fake_question(*a, **k):
        texts.append(a[2] if len(a) > 2 else k.get("text", ""))
        from PyQt6.QtWidgets import QMessageBox
        return QMessageBox.StandardButton.Yes

    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))

    s._on_save_print()
    assert any("otomatik kaydedilecek" in t for t in texts)
    assert seen.get("preview") is True
    assert s.doc_id is not None  # kaydedildi


def test_mini_preview_collapsed_by_default_and_renders_on_expand(qapp, db):
    from src.desktop.designer.ui.preview_widget import ReportPreviewWidget

    s = DocumentDetailScreen(db_session=db)
    s.lines.clear_rows()
    s.lines.add_row({"kod": "K1", "aciklama": "Kalem", "miktar": "2",
                     "birim_fiyat": "100", "kdv_yuzde": "20"})
    s.lines._emit_totals()

    assert isinstance(s.mini_preview, ReportPreviewWidget)
    assert s.mini_preview.compact is True
    # kapalıyken çizim yok (boşuna render maliyeti alınmaz)
    assert s.sec_mini_preview.is_expanded is False
    assert s.mini_preview.rendered_pages == []

    s.sec_mini_preview.set_expanded(True)
    assert len(s.mini_preview.rendered_pages) >= 1


def test_mini_preview_refresh_is_debounced_and_guarded(qapp, db):
    s = DocumentDetailScreen(db_session=db)
    # kapalıyken tetikleme timer'ı başlatmaz
    s._schedule_preview_refresh()
    assert not s._preview_timer.isActive()

    s.sec_mini_preview.set_expanded(True)
    s.cari.txt_cari_unvan.setText("Yeni Cari")  # _refresh_summary -> schedule
    assert s._preview_timer.isActive()
    s._preview_timer.stop()
    s._refresh_mini_preview()
    assert s._build_print_data()["musteri"]["adi"] == "Yeni Cari"


def test_save_and_reload_payload(qapp, db):
    s = DocumentDetailScreen(db_session=db)
    s.cari.txt_cari_unvan.setText("ACME LTD")
    s.lines.add_row({"kod": "STK9", "aciklama": "Ürün 9", "miktar": "3",
                     "birim_fiyat": "50", "iskonto_yuzde": "0", "kdv_yuzde": "20"})
    s.lines._emit_totals()
    res = s.service.save_payload(s._collect_payload(), doc_id=None)
    assert res.success, res.error
    assert res.quotation_number

    s2 = DocumentDetailScreen(db_session=db, doc_id=res.quotation_id)
    lines = [x for x in s2.lines.get_lines() if x["kod"]]
    assert len(lines) == 1
    assert lines[0]["kod"] == "STK9"
    assert s2.cari.get_data()["name"] == "ACME LTD"
    assert s2.txt_doc_no.text() == res.quotation_number
