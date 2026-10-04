"""DocumentLinesGrid (entry-modda FilterableTableView) davranış testleri."""

import sys

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.widgets.document_lines_grid import (
    COL_KOD,
    COL_MIKTAR,
    COL_NET,
    COL_SEQ,
    DocumentLinesGrid,
    parse_num,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_parse_num_turkish_format():
    assert parse_num("1.234,56") == pytest.approx(1234.56)
    assert parse_num("100") == 100.0
    assert parse_num("") == 0.0
    assert parse_num("2.500,00 ₺") == pytest.approx(2500.0)


def test_entry_mode_hides_filter_bar(qapp):
    g = DocumentLinesGrid()
    assert g.grid.mode == "entry"
    assert not g.grid.filter_bar_container.isVisible()
    assert not g.grid.table_view.isSortingEnabled()


def test_row_recalc_and_totals(qapp):
    g = DocumentLinesGrid()
    captured = {}
    g.totals_changed.connect(lambda d: captured.update(d))

    g.add_row({
        "kod": "A1", "aciklama": "Kamera", "miktar": "8",
        "birim_fiyat": "150", "iskonto_yuzde": "10", "kdv_yuzde": "20",
    })
    # 8 * 150 = 1200 brüt; %10 isk -> net 1080; %20 kdv -> 216
    assert g.model.item(0, COL_NET).text() == "1.080,00"
    assert captured["ara_toplam"] == pytest.approx(1200.0)
    assert captured["iskonto"] == pytest.approx(120.0)
    assert captured["kdv_matrahi"] == pytest.approx(1080.0)
    assert captured["kdv_toplam"] == pytest.approx(216.0)
    assert captured["genel_toplam"] == pytest.approx(1296.0)


def test_live_edit_updates_net(qapp):
    g = DocumentLinesGrid()
    g.add_row({"miktar": "2", "birim_fiyat": "100", "iskonto_yuzde": "0", "kdv_yuzde": "20"})
    assert g.model.item(0, COL_NET).text() == "200,00"
    g.model.item(0, COL_MIKTAR).setText("5")
    assert g.model.item(0, COL_NET).text() == "500,00"


def test_remove_checked_rows(qapp):
    from PyQt6.QtCore import Qt
    g = DocumentLinesGrid()
    g.add_row({"kod": "A"})
    g.add_row({"kod": "B"})
    g.add_row({"kod": "C"})
    g.model.item(1, 0).setCheckState(Qt.CheckState.Checked)
    g.remove_checked_rows()
    assert g.model.rowCount() == 2
    codes = [g.model.item(r, COL_KOD).text() for r in range(2)]
    assert codes == ["A", "C"]
    # sıra yeniden numaralandı
    assert [g.model.item(r, COL_SEQ).text() for r in range(2)] == ["1", "2"]


def test_tur_column_and_free_entry(qapp):
    g = DocumentLinesGrid()
    from src.desktop.ui.widgets.document_lines_grid import COL_TUR
    g.set_products([{"code": "P1", "name": "Kamera", "unit": "Adet", "price": 100}])
    # Serbest Giriş -> kart sorusu sorulmaz, stoga_ekle False
    g.add_row({"tur": "Serbest Giriş", "kod": "X", "aciklama": "elle"})
    lines = g.get_lines()
    assert lines[0]["tur"] == "Serbest Giriş"
    assert lines[0]["stoga_ekle"] is False
    # katalog eşleşen -> stoga_ekle False
    g.add_row({"kod": "P1", "aciklama": "Kamera"})
    assert g.get_lines()[1]["stoga_ekle"] is False
    # manuel işaretleme
    g.mark_row_for_stock_card(1)
    assert g.get_lines()[1]["stoga_ekle"] is True
    assert g.model.item(0, COL_TUR).text() == "Serbest Giriş"


def test_no_to_stock_card_switches_type_to_serbest(qapp, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from src.desktop.ui.widgets.document_lines_grid import COL_TUR, TUR_SERBEST
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    g = DocumentLinesGrid()
    g.set_products([])  # katalog boş
    g.add_row({"tur": "Malzeme", "kod": "serbest ürün 001"})
    # kod hücresi 'değişti' sinyalini tetikle
    g._maybe_offer_new_card(0)
    assert g.model.item(0, COL_TUR).text() == TUR_SERBEST
    assert g.get_lines()[0]["stoga_ekle"] is False


def test_empty_row_helpers(qapp):
    g = DocumentLinesGrid()
    g.clear_rows()
    g.add_row({"kod": "A1", "miktar": "1", "birim_fiyat": "10"})
    g.add_row({})                      # tamamen boş
    g.add_row({"aciklama": "elle satır"})
    assert g.empty_row_count() == 1
    assert g.is_row_empty(1) is True
    assert g.remove_empty_rows() == 1
    assert g.model.rowCount() == 2
    assert [g.model.item(r, COL_SEQ).text() for r in range(2)] == ["1", "2"]


def test_row_highlighter_applied(qapp):
    from PyQt6.QtWidgets import QAbstractItemView
    g = DocumentLinesGrid()
    assert g.grid.table_view.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows
    assert "item:selected" in g.grid.table_view.styleSheet()
    g.set_row_highlight_color("#fde68a")
    assert "#fde68a" in g.grid.table_view.styleSheet()


def test_line_currency_converts_totals_to_tl_and_uses_configured_decimals(qapp):
    """Satırda döviz seçilince kur otomatik gelir, net tutar satır dövizinde, belge toplamı TL karşılığında olur."""
    from src.desktop.services import sayi_bicimi
    from src.desktop.ui.widgets.document_lines_grid import COL_BFIYAT, COL_DOVIZ, COL_KUR

    sayi_bicimi._onbellek.clear()                                       # varsayılanlar: kur 4, fiyat 4, miktar 2, tutar 2
    g = DocumentLinesGrid()
    g.set_currencies({"USD": 40.0, "EUR": 45.5})
    assert g._doviz_kodlari() == ["TRY", "EUR", "USD"]
    got = {}
    g.totals_changed.connect(lambda d: got.update(d))
    g.add_row({"kod": "A", "aciklama": "TL kalem", "miktar": "2", "birim_fiyat": "100", "kdv_yuzde": "20"})
    g.add_row({"kod": "B", "aciklama": "USD kalem", "miktar": "1", "birim_fiyat": "10", "kdv_yuzde": "20"})
    assert g._cell(0, COL_MIKTAR) == "2,00" and g._cell(0, COL_BFIYAT) == "100,0000" and g._cell(0, COL_KUR) == "1,0000"
    g.model.item(1, COL_DOVIZ).setText("USD")                           # döviz seçimi kuru otomatik doldurur
    assert g._cell(1, COL_KUR) == "40,0000"
    assert g._cell(1, COL_NET) == "10,00"                               # net tutar satırın kendi dövizinde
    assert got["kdv_matrahi"] == pytest.approx(200.0 + 400.0)           # toplam TL karşılığı (10 USD × 40)
    assert got["kdv_toplam"] == pytest.approx(120.0)
    rec = g.get_lines()[1]
    assert rec["doviz"] == "USD" and rec["_num"]["kur"] == pytest.approx(40.0)
    g.model.item(1, COL_KUR).setText("41,5000")                         # kur elle değiştirilebilir
    assert got["kdv_matrahi"] == pytest.approx(200.0 + 415.0)
    g.model.item(1, COL_DOVIZ).setText("TRY")
    assert g.get_lines()[1]["_num"]["kur"] == 1.0                       # TL satırında kur her zaman 1


def test_number_format_settings_roundtrip(db_session):
    from src.desktop.services import sayi_bicimi

    sayi_bicimi._onbellek.clear()
    assert (sayi_bicimi.hane("kur"), sayi_bicimi.hane("fiyat"), sayi_bicimi.hane("miktar"), sayi_bicimi.hane("tutar")) == (4, 4, 2, 2)
    sayi_bicimi.kaydet(db_session, {"kur": 6, "fiyat": 3, "tutar": 0})
    sayi_bicimi._onbellek.clear()
    sayi_bicimi.yukle(db_session)
    assert (sayi_bicimi.hane("kur"), sayi_bicimi.hane("fiyat"), sayi_bicimi.hane("tutar")) == (6, 3, 0)
    sayi_bicimi._onbellek.clear()


def test_belge_gridi_enter_ile_sonraki_hucreye_gecer_ve_son_satirda_yeni_satir_acar(qapp):
    """Belge kalemleri de fiş gridi gibi standart giriş motorunu kullanır: Enter/Tab gezinme, son hücreden sonra yeni satır."""
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QKeyEvent

    from src.desktop.ui.widgets.document_lines_grid import COL_ACIKLAMA, COL_BARKOD, COL_KDV, COL_KUR

    g = DocumentLinesGrid()
    g.add_row({"kod": "A", "aciklama": "x"})
    tv = g.grid.table_view

    def tus(key):
        idx = tv.currentIndex()
        editor = tv.indexWidget(idx)
        d = tv.itemDelegateForColumn(idx.column()) or tv.itemDelegate()
        d.eventFilter(editor, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
        QApplication.processEvents()

    tv.setCurrentCell(0, COL_BARKOD)
    tv.editItem(g.model.item(0, COL_BARKOD))
    tus(Qt.Key.Key_Return)
    assert tv.currentColumn() == COL_ACIKLAMA and tv.state() == tv.State.EditingState        # barkod → açıklama
    n = g.model.rowCount()
    tv.setCurrentCell(n - 1, COL_KUR)
    tv.editItem(g.model.item(n - 1, COL_KUR))
    tus(Qt.Key.Key_Return)                                                                       # son satırın son hücresi → yeni satır
    assert g.model.rowCount() == n + 1 and tv.currentRow() == n
    assert g.model.item(0, COL_KDV) is not None
