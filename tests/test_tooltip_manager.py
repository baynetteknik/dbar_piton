"""Uygulama geneli ipucu yöneticisi: her tür widget'ta ipucu okunur (sabit lacivert zemin / beyaz yazı) pencerede gösterilir."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QHelpEvent, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QApplication, QPushButton, QTableView, QTabWidget, QToolTip, QWidget

from src.desktop.ui.components.tooltip_manager import STYLE, TooltipManager


@pytest.fixture
def tm(qapp):
    m = TooltipManager.install(qapp)
    yield m
    TooltipManager.uninstall()


def _hover(w: QWidget, pos: QPoint) -> None:
    QApplication.sendEvent(w, QHelpEvent(QEvent.Type.ToolTip, pos, w.mapToGlobal(pos)))


def test_widget_tooltip_uses_own_fixed_style_even_with_hostile_stylesheet(qapp, tm):
    w = QWidget()
    w.setStyleSheet("QWidget { background:#000000; color:#000000; }")       # Qt'nin kendi ipucunu okunmaz yapan tür stil
    b = QPushButton("Kaydet", w)
    b.setToolTip("Belgeyi kaydeder")
    w.show()
    _hover(b, QPoint(5, 5))
    assert tm.label.isVisible() and tm.label.text() == "Belgeyi kaydeder"
    assert tm.label.styleSheet() == STYLE and "#1e3a8a" in STYLE and "#ffffff" in STYLE
    w.close()


def test_no_tooltip_hides_and_propagates(qapp, tm):
    w = QWidget()
    b = QPushButton("Yok", w)
    w.show()
    tm.show("eski", QPoint(10, 10))
    _hover(b, QPoint(5, 5))                       # ipucusuz widget: yeni ipucu çıkmaz
    assert tm.label.text() == "eski"


def test_table_cell_header_and_tab_tooltips(qapp, tm):
    model = QStandardItemModel(2, 2)
    it = QStandardItem("A")
    it.setToolTip("Hücre ipucu")
    model.setItem(0, 0, it)
    model.setHeaderData(1, Qt.Orientation.Horizontal, "Başlık ipucu", Qt.ItemDataRole.ToolTipRole)
    t = QTableView()
    t.setModel(model)
    t.resize(400, 200)
    t.show()
    QApplication.processEvents()
    cell = t.visualRect(model.index(0, 0)).center()
    _hover(t.viewport(), cell)
    assert tm.label.isVisible() and tm.label.text() == "Hücre ipucu"
    h = t.horizontalHeader()
    x = h.sectionViewportPosition(1) + 5
    tm.hide()
    _hover(h.viewport(), QPoint(x, 5))
    assert tm.label.text() == "Başlık ipucu"
    tabs = QTabWidget()
    tabs.addTab(QWidget(), "Bir")
    tabs.setTabToolTip(0, "Sekme ipucu")
    tabs.show()
    bar = tabs.tabBar()
    _hover(bar, bar.tabRect(0).center())
    assert tm.label.text() == "Sekme ipucu"
    t.close()
    tabs.close()


def test_direct_showtext_calls_use_manager_and_uninstall_restores(qapp):
    orijinal = QToolTip.showText
    m = TooltipManager.install(qapp)
    QToolTip.showText(QPoint(50, 50), "Doğrudan çağrı")
    assert m.label.isVisible() and m.label.text() == "Doğrudan çağrı"
    QToolTip.hideText()
    assert not m.label.isVisible()
    TooltipManager.uninstall()
    assert QToolTip.showText == orijinal


def test_standart_grid_yardimcisi_kucuk_tablolar_icin_hazir_kurar(qapp):
    from PyQt6.QtGui import QStandardItem

    from src.desktop.ui.components.entry_table_view import EntryTableView, standart_grid
    g = standart_grid("test_standart_grid", [("a", "A"), ("b", "B")], tam_adlar={"b": "Bee"})
    t = g.table_view
    assert isinstance(t, EntryTableView) and t.columnCount() == 2
    t.insertRow(0)
    t.setItem(0, 0, QStandardItem("x"))
    assert t.rowCount() == 1 and t.item(0, 0).text() == "x"
    assert t.model().headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole) == "Bee"
