"""UI integration tests for ViewProfileBar and FilterableTableView."""

import pytest
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.components.view_profile_bar import ViewProfileBar


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication exists for Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_filterable_table_mandatory_columns_locked(qapp):
    """Verify that mandatory columns (id, cari_kodu, ticari_unvan) cannot be hidden."""
    headers = {
        0: ("ID", "id"),
        1: ("Cari Kodu", "cari_kodu"),
        2: ("Ticari Ünvan", "ticari_unvan"),
        3: ("Telefon", "telefon"),
    }
    table = FilterableTableView(headers_dict=headers, profile_key="test_table")

    # Set dummy model with 4 columns
    model = QStandardItemModel(1, 4)
    table.table_view.setModel(model)

    # Attempt to hide ID (mandatory)
    table.set_column_hidden(0, True)
    assert table.table_view.horizontalHeader().isSectionHidden(0) is False

    # Hide Telefon (non-mandatory)
    table.set_column_hidden(3, True)
    assert table.table_view.horizontalHeader().isSectionHidden(3) is True


def test_view_profile_bar_initialization(qapp):
    """Test ViewProfileBar initialization and profile switching."""
    headers = {
        0: ("ID", "id"),
        1: ("Cari Kodu", "cari_kodu"),
    }
    table = FilterableTableView(
        headers_dict=headers, profile_key="test_bar", enable_profile_bar=True,
    )

    assert hasattr(table, "profile_bar")
    assert isinstance(table.profile_bar, ViewProfileBar)
    assert table.profile_bar.combo_profiles.count() >= 2
