"""FilterableTableView seçim kolonu (CheckableHeaderView) davranış testleri."""

import sys

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.components.checkable_header_view import CheckableHeaderView
from src.desktop.ui.components.filterable_table import FilterableTableView


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


HEADERS = {
    0: ("☑", "select"),
    1: ("ID", "id"),
    2: ("Ad", "name"),
}


def _build_table(select_column):
    table = FilterableTableView(
        headers_dict=HEADERS,
        profile_key="test_sel",
        select_column=select_column,
    )
    model = QStandardItemModel()
    model.setColumnCount(3)
    for i in range(4):
        chk = QStandardItem("")
        chk.setCheckable(True)
        chk.setCheckState(Qt.CheckState.Unchecked)
        id_item = QStandardItem(str(i + 1))
        id_item.setData(i + 1, Qt.ItemDataRole.UserRole)
        table.table_view.model()  # noqa: B018
        model.appendRow([chk, id_item, QStandardItem(f"Kayıt {i + 1}")])
    table.table_view.setModel(model)
    return table, model


def test_no_select_column_keeps_plain_header(qapp):
    table, _ = _build_table(select_column=None)
    assert table._checkable_header is None
    assert not isinstance(table.table_view.horizontalHeader(), CheckableHeaderView)


def test_select_all_checks_every_row(qapp):
    table, model = _build_table(select_column=0)
    assert isinstance(table.table_view.horizontalHeader(), CheckableHeaderView)

    table.set_all_checked(True)
    assert table.checked_count() == 4
    assert table.get_checked_values(1) == [1, 2, 3, 4]
    assert table._checkable_header.check_state() == Qt.CheckState.Checked

    table.set_all_checked(False)
    assert table.checked_count() == 0
    assert table._checkable_header.check_state() == Qt.CheckState.Unchecked


def test_partial_selection_sets_tristate(qapp):
    table, model = _build_table(select_column=0)
    model.item(0, 0).setCheckState(Qt.CheckState.Checked)
    model.item(2, 0).setCheckState(Qt.CheckState.Checked)
    assert table.checked_count() == 2
    assert table._checkable_header.check_state() == Qt.CheckState.PartiallyChecked
    assert sorted(table.get_checked_values(1)) == [1, 3]


def test_selection_survives_sort(qapp):
    table, model = _build_table(select_column=0)
    model.item(3, 0).setCheckState(Qt.CheckState.Checked)  # ID 4
    model.sort(1, Qt.SortOrder.DescendingOrder)
    # ID 4 hangi satıra taşındıysa, işaretli değer hâlâ 4 olmalı
    assert table.get_checked_values(1) == [4]
