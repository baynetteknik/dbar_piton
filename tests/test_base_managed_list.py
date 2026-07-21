import sys

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Provides a single QApplication instance for PyQt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_base_managed_list_widget_initialization(qapp):
    """Tests proper creation of BaseManagedListWidget template."""
    from src.desktop.ui.components.base_managed_list import BaseManagedListWidget

    headers = {0: ("ID", "id"), 1: ("Ad", "name")}
    widget = BaseManagedListWidget(profile_key="test_module", headers_dict=headers)

    assert widget.profile_key == "test_module"
    assert widget.filterable_table.profile_key == "test_module"
    assert widget.current_page == 1
    assert widget.per_page == 25


def test_view_settings_widget_module_switching(qapp):
    """Tests module profile switching in ViewSettingsWidget."""
    from src.desktop.ui.components.filterable_table import FilterableTableView
    from src.desktop.ui.settings import ViewSettingsWidget

    # Save profiles for two different modules
    table_cust = FilterableTableView({0: ("ID", "id")}, profile_key="customers")
    table_cust.save_column_profile("CustProfile")

    table_sites = FilterableTableView({0: ("ID", "id")}, profile_key="sites")
    table_sites.save_column_profile("SiteProfile")

    settings_widget = ViewSettingsWidget()

    # Select "customers" in combo
    idx_cust = settings_widget.module_combo.findData("customers")
    settings_widget.module_combo.setCurrentIndex(idx_cust)
    items_cust = [
        settings_widget.profile_list.item(i).text()
        for i in range(settings_widget.profile_list.count())
    ]
    assert "CustProfile" in items_cust

    # Switch to "sites" in combo
    idx_sites = settings_widget.module_combo.findData("sites")
    settings_widget.module_combo.setCurrentIndex(idx_sites)
    items_sites = [
        settings_widget.profile_list.item(i).text()
        for i in range(settings_widget.profile_list.count())
    ]
    assert "SiteProfile" in items_sites
    assert "CustProfile" not in items_sites

    # Clean up profiles
    table_cust.delete_column_profile("CustProfile")
    table_sites.delete_column_profile("SiteProfile")
