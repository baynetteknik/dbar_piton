import sys

import pytest
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.components.dia_3_panel_base import DIA3PanelBaseWidget


@pytest.fixture(scope="session")
def qapp():
    """Provides a single QApplication instance for PyQt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_dia_3_panel_base_widget_structure(qapp):
    """Tests layout components and structure of DIA3PanelBaseWidget."""
    widget = DIA3PanelBaseWidget(profile_key="test_panel", module_name="Test Modülü")

    assert widget.profile_key == "test_panel"
    assert widget.module_name == "Test Modülü"
    assert widget.left_panel is not None
    assert widget.center_container is not None
    assert widget.right_panel is not None
    assert widget.filterable_table is not None
    assert widget.table_view is not None

    # Verify registered layout hint properties
    assert widget.property("_layout_module") == "Test Modülü"
    assert widget.left_panel.property("_layout_module") == "Test Modülü"
    assert widget.center_container.property("_layout_module") == "Test Modülü"
    assert widget.right_panel.property("_layout_module") == "Test Modülü"
