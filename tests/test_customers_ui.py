import sys

import pytest
from PyQt6.QtWidgets import QApplication

from src.core.models import Site
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.customers import MusteriYonetimiWidget


@pytest.fixture(scope="session")
def qapp():
    """Provides a single QApplication instance for PyQt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_edge_triggered_panel_pin_and_tooltips(qapp):
    """Tests the pin toggle behavior, tooltips, and style changes of EdgeTriggeredPanel."""
    panel = EdgeTriggeredPanel(side="right")
    
    # Verify initial settings
    assert panel.is_pinned is False
    assert panel.pin_btn.toolTip() == "Paneli Sabitle"
    assert panel.pin_btn.text() == "📌 Sabitle"
    assert panel.close_btn.toolTip() == "Paneli Kapat"
    assert panel.close_btn.text() == "❌ Gizle"

    # Toggle pin
    panel.toggle_pin()
    assert panel.is_pinned is True
    assert panel.pin_btn.toolTip() == "Sabitlemeyi Kaldır"
    assert panel.pin_btn.text() == "📍 Serbest"
    
    # Verify style sheet changes (should contain background-color #3b82f6)
    style = panel.pin_btn.styleSheet()
    assert "#3b82f6" in style

    # Toggle pin back
    panel.toggle_pin()
    assert panel.is_pinned is False
    assert panel.pin_btn.toolTip() == "Paneli Sabitle"
    assert panel.pin_btn.text() == "📌 Sabitle"
    assert "#ffffff" in panel.pin_btn.styleSheet()


def test_musteri_yonetimi_widget_pagination_margins(qapp, db_session):
    """Tests the dynamic margins applied to the pagination layout based on panel state."""
    # Insert a dummy Site to avoid DB errors when looking up company working mode
    site = Site(
        id=1,
        name="Test Co",
        cms_type="dolibarr",
        working_mode="local_master",
        url="http://test.url",
        api_key_account="test-api-key",
    )
    db_session.add(site)
    db_session.commit()

    widget = MusteriYonetimiWidget(db_session, company_id=1)

    # Initial state (both panels closed, overlay mode)
    assert widget.left_panel.is_open is False
    assert widget.right_panel.is_open is False
    
    # Check margins (left, top, right, bottom)
    margins = widget.pagination_layout.contentsMargins()
    assert margins.left() == 0
    assert margins.right() == 0

    # Open left panel in overlay mode (not pinned)
    widget.left_panel.open_panel()
    widget.update_pagination_margins()
    margins = widget.pagination_layout.contentsMargins()
    assert margins.left() == widget.left_panel.panel_width
    assert margins.right() == 0

    # Open right panel in overlay mode (not pinned)
    widget.right_panel.open_panel()
    widget.update_pagination_margins()
    margins = widget.pagination_layout.contentsMargins()
    assert margins.left() == widget.left_panel.panel_width
    assert margins.right() == widget.right_panel.panel_width

    # Pin right panel (margin for right should become 0 because it's now in the layout flow)
    widget.right_panel.is_pinned = True
    widget.update_pagination_margins()
    margins = widget.pagination_layout.contentsMargins()
    assert margins.left() == widget.left_panel.panel_width
    assert margins.right() == 0


def test_musteri_yonetimi_widget_selection_and_proxy_model_fix(qapp, db_session):
    """Verifies table selection behavior and get_selected_rows correctness after proxy model fix."""
    from PyQt6.QtGui import QStandardItem
    from PyQt6.QtWidgets import QAbstractItemView
    
    site = Site(
        id=1,
        name="Test Co",
        cms_type="dolibarr",
        working_mode="local_master",
        url="http://test.url",
        api_key_account="test-api-key",
    )
    db_session.add(site)
    db_session.commit()

    widget = MusteriYonetimiWidget(db_session, company_id=1)
    
    # Assert selection behavior is correct
    assert widget.table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows
    assert widget.table.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection

    # Mock selection data and verify get_selected_rows
    item_id = QStandardItem("123")
    widget.customer_model.appendRow([item_id])

    # Select the row
    widget.table.selectRow(0)
    
    selected_ids = widget.get_selected_rows()
    assert selected_ids == [123]


def test_filterable_table_view_column_profiles(qapp):
    """Tests saving, deleting, and loading column profiles using QSettings."""
    from PyQt6.QtGui import QStandardItemModel

    from src.desktop.ui.components.filterable_table import FilterableTableView
    
    headers = {0: ("ID", "id"), 1: ("Ad", "name"), 2: ("Soyad", "surname")}
    table = FilterableTableView(headers)
    
    # Set a model so the table horizontalHeader actually has columns
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["ID", "Ad", "Soyad"])
    table.table_view.setModel(model)
    
    # Verify initial visibility
    assert table.table_view.horizontalHeader().isSectionHidden(0) is False
    assert table.table_view.horizontalHeader().isSectionHidden(1) is False
    
    # Hide column 1 and save profile "TestProfile"
    table.set_column_hidden(1, True)
    table.save_column_profile("TestProfile")
    
    # Ensure profile list contains "TestProfile"
    profiles = table.load_column_profile_list()
    assert "TestProfile" in profiles
    
    # Show column 1 again
    table.set_column_hidden(1, False)
    assert table.table_view.horizontalHeader().isSectionHidden(1) is False
    
    # Load profile and verify column 1 is hidden again
    table.load_profile("TestProfile")
    assert table.table_view.horizontalHeader().isSectionHidden(1) is True
    
    # Delete profile and verify it is removed from list
    table.delete_column_profile("TestProfile")
    profiles = table.load_column_profile_list()
    assert "TestProfile" not in profiles


def test_filterable_table_view_column_moving(qapp):
    """Tests that moving columns reorders filter line edits properly."""
    from PyQt6.QtGui import QStandardItemModel

    from src.desktop.ui.components.filterable_table import FilterableTableView
    
    headers = {0: ("ID", "id"), 1: ("Ad", "name"), 2: ("Soyad", "surname")}
    table = FilterableTableView(headers)
    
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["ID", "Ad", "Soyad"])
    table.table_view.setModel(model)
    table.table_view.horizontalHeader().setSectionsMovable(True)
    
    # Initially visualIndex matches logicalIndex
    assert table.table_view.horizontalHeader().visualIndex(0) == 0
    assert table.table_view.horizontalHeader().visualIndex(1) == 1
    
    # Move section 0 to index 1 (ID moves after Ad)
    table.table_view.horizontalHeader().moveSection(0, 1)
    
    # Verify visual index changed
    assert table.table_view.horizontalHeader().visualIndex(0) == 1
    assert table.table_view.horizontalHeader().visualIndex(1) == 0
    
    # Trigger sync
    table.sync_filter_positions()
    
    # Verify layout item order changed (the first widget in layout is now for 'Ad')
    first_widget = table.inputs_layout.itemAt(0).widget()
    assert first_widget.placeholderText() == "Ad..."


def test_view_settings_widget_integration(qapp):
    """Tests the ViewSettingsWidget profile listing and deletion interface."""
    from unittest.mock import patch

    from src.desktop.ui.components.filterable_table import FilterableTableView
    from src.desktop.ui.settings import ViewSettingsWidget
    
    # Save a temporary profile "SettingsTest"
    headers = {0: ("ID", "id")}
    table = FilterableTableView(headers)
    table.save_column_profile("SettingsTest")
    
    widget = ViewSettingsWidget()
    
    # Check that "SettingsTest" is listed
    items = [widget.profile_list.item(i).text() for i in range(widget.profile_list.count())]
    assert any("SettingsTest" in item for item in items)
    
    # Select the item and delete it
    for i in range(widget.profile_list.count()):
        if "SettingsTest" in widget.profile_list.item(i).text():
            widget.profile_list.setCurrentRow(i)
            widget.table.selectRow(i)
            break
            
    from PyQt6.QtWidgets import QMessageBox
    with patch('PyQt6.QtWidgets.QMessageBox.information') as mock_info, \
         patch('PyQt6.QtWidgets.QMessageBox.warning') as mock_warn, \
         patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
        widget.delete_selected_profile()
        assert mock_info.called
        assert not mock_warn.called
    
    # Verify removed
    items = [widget.profile_list.item(i).text() for i in range(widget.profile_list.count())]
    assert "SettingsTest" not in items
