"""Unit tests for ViewSettingsWidget in Settings Window."""

import pytest
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.settings import ViewSettingsWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_view_settings_widget_initialization(qapp):
    """Test ViewSettingsWidget loads profiles from ProfileManager."""
    widget = ViewSettingsWidget()
    assert widget.module_combo.count() >= 5
    assert widget.profile_list.count() >= 1

    # Check profile info loaded
    widget.profile_list.setCurrentRow(0)
    assert "<b>Profil Adı:</b>" in widget.lbl_profile_info.text()


def test_view_settings_widget_module_change(qapp):
    """Test switching modules loads corresponding profile keys."""
    widget = ViewSettingsWidget()
    widget.module_combo.setCurrentIndex(1)  # backup
    assert widget.get_current_profile_key() == "backup"
    assert widget.profile_list.count() >= 1
