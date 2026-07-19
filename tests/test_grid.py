import pytest
from PyQt6.QtCore import QAbstractTableModel, Qt
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.grid import ManagedTableView, MultiColumnSortFilterProxyModel


# Ensure QApplication is initialized for widgets tests
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class DummyModel(QAbstractTableModel):
    """Simple model for testing columns and data."""
    def __init__(self):
        super().__init__()
        self._data = [
            ["1", "Alice", "potansiyel"],
            ["2", "Bob", "aktif"],
            ["3", "Charlie", "pasif"],
        ]
        self._headers = ["ID", "Isim", "Durum"]

    def rowCount(self, parent=None):  # noqa: N802
        return len(self._data)

    def columnCount(self, parent=None):  # noqa: N802
        return len(self._headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        return self._data[index.row()][index.column()]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self._headers[section]
        return None


def test_multi_column_proxy_filtering(qapp):
    """Tests if MultiColumnSortFilterProxyModel filters rows correctly across columns."""
    source_model = DummyModel()
    proxy = MultiColumnSortFilterProxyModel()
    proxy.setSourceModel(source_model)

    # Initially, no filters are set, so all rows are visible
    assert proxy.rowCount() == 3

    # Filter column 1 (Isim) for 'Al'
    proxy.set_column_filter(1, "Al")
    assert proxy.rowCount() == 1  # Only Alice
    assert proxy.data(proxy.index(0, 1)) == "Alice"

    # Filter column 2 (Durum) for 'aktif'
    proxy.set_column_filter(1, "")  # Clear column 1 filter
    proxy.set_column_filter(2, "aktif")
    assert proxy.rowCount() == 1  # Only Bob
    assert proxy.data(proxy.index(0, 1)) == "Bob"

    # Multiple columns filtering combined
    proxy.set_column_filter(1, "Charlie")
    proxy.set_column_filter(2, "pasif")
    assert proxy.rowCount() == 1  # Only Charlie
    assert proxy.data(proxy.index(0, 1)) == "Charlie"

    # If criteria doesn't match, rowCount should be 0
    proxy.set_column_filter(2, "aktif")  # Charlie is pasif, so no match
    assert proxy.rowCount() == 0


def test_managed_table_view_settings_save_restore(qapp, tmp_path):
    """Tests state saving, state restoring, and guard mechanism verification in ManagedTableView."""
    table = ManagedTableView("test_settings")
    # Redirect state storage to a temp directory
    table.settings_path = tmp_path / "grid_test_settings.json"

    model = DummyModel()
    table.set_source_model(model)

    # Change table state visually (e.g., hide column 1)
    table.hidden_columns.add(1)
    table.apply_hidden_columns()
    table.save_view_settings()

    # Create a new table and verify it restores the hidden column state
    new_table = ManagedTableView("test_settings")
    new_table.settings_path = table.settings_path
    new_table.set_source_model(model)

    assert 1 in new_table.hidden_columns
    assert new_table.isColumnHidden(1) is True
    assert new_table.isColumnHidden(0) is False


def test_managed_table_view_state_guard_mechanism(qapp, tmp_path):
    """Tests if guard mechanism correctly discards incompatible view states."""
    table = ManagedTableView("test_settings")
    table.settings_path = tmp_path / "grid_test_settings.json"

    model = DummyModel()
    table.set_source_model(model)

    # Save state for a 3-column table
    table.save_view_settings()

    # Create a new table with a DIFFERENT model (e.g., 2 columns instead of 3)
    class SmallerModel(QAbstractTableModel):
        def rowCount(self, parent=None):  # noqa: N802
            return 1
        def columnCount(self, parent=None):  # noqa: N802
            return 2
        def data(self, index, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
            return "Test"

    smaller_table = ManagedTableView("test_settings")
    smaller_table.settings_path = table.settings_path

    # Try setting the new model. The restore should NOT crash and should ignore the incompatible state
    smaller_table.set_source_model(SmallerModel())
    assert smaller_table.settings_path.exists()
