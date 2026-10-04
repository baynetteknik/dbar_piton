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
    from src.desktop.managers.profile_manager import ProfileManager
    from src.desktop.ui.components.filterable_table import FilterableTableView
    from src.desktop.ui.settings import ViewSettingsWidget

    managers = {key: ProfileManager(profile_key=key) for key in ("customers", "sites")}
    previous_active = {key: pm.get_active_profile_name() for key, pm in managers.items()}
    try:
        table_cust = FilterableTableView({0: ("ID", "id")}, profile_key="customers")
        table_cust.save_column_profile("CustProfile")
        table_sites = FilterableTableView({0: ("ID", "id")}, profile_key="sites")
        table_sites.save_column_profile("SiteProfile")
        settings_widget = ViewSettingsWidget()

        for key, expected, excluded in (
            ("customers", "CustProfile", "SiteProfile"),
            ("sites", "SiteProfile", "CustProfile"),
        ):
            idx = settings_widget.module_combo.findData(key)
            assert idx != -1
            settings_widget.module_combo.setCurrentIndex(idx)
            assert settings_widget.get_current_profile_key() == key
            items = [
                settings_widget.profile_list.item(i).text()
                for i in range(settings_widget.profile_list.count())
            ]
            assert any(expected in item for item in items)
            assert not any(excluded in item for item in items)
    finally:
        for key, profile_name in (("customers", "CustProfile"), ("sites", "SiteProfile")):
            managers[key].delete_profile(profile_name)
            managers[key].set_active_profile_name(previous_active[key])
