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
    widget.module_combo.setCurrentIndex(1)  # backup_tasks
    assert widget.get_current_profile_key() == "backup_tasks"
    assert widget.profile_list.count() >= 1


def test_view_settings_widget_reset_all_profiles(qapp):
    """Test reset_all_profiles prompts confirmation and resets profiles."""
    from unittest.mock import patch
    from PyQt6.QtWidgets import QMessageBox
    from src.desktop.managers.profile_manager import ProfileManager

    # Create custom profile
    pm = ProfileManager(profile_key="backup_tasks")
    custom_p = pm.create_default_profile()
    custom_p.profile.name = "TestCustomReset"
    pm.save_profile(custom_p)

    widget = ViewSettingsWidget()
    widget.module_combo.setCurrentIndex(1)

    with patch("PyQt6.QtWidgets.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), \
         patch("PyQt6.QtWidgets.QMessageBox.information") as mock_info:
        widget.reset_all_profiles()
        assert mock_info.called

    items = [widget.profile_list.item(i).text() for i in range(widget.profile_list.count())]
    assert "TestCustomReset" not in items


def test_embedded_mode_hides_own_chrome(qapp):
    """embedded=True: kendi üst filtre barı ve alt aksiyon barı gizli olmalı."""
    plain = ViewSettingsWidget()
    emb = ViewSettingsWidget(embedded=True)
    assert plain.action_bar.isVisibleTo(plain) is True
    assert emb.action_bar.isVisibleTo(emb) is False
    # kabuğun süreceği yardımcılar
    emb.apply_quick_search("abc")
    assert emb.txt_search.text() == "abc"
    assert isinstance(emb.record_count(), int)
