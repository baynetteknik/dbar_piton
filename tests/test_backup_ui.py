import sys

import pytest
from PyQt6.QtCore import QPoint
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.desktop.ui.backup import BackupWidget, NewTaskDialog, TaskDetailPopupDialog
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.settings import ViewSettingsWidget


@pytest.fixture(scope="session")
def qapp():
    """Provides a single QApplication instance for PyQt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_backup_widget_initialization_and_panels(qapp, db_session):
    """Tests BackupWidget edge panels, category toggles and pagination structure."""
    widget = BackupWidget(db_session)

    # Initial sidebars check
    assert widget.left_panel.is_open is False
    assert widget.right_panel.is_open is False
    assert widget.selected_category == "Backup"

    # Category switch check
    widget.switch_category("Restore")
    assert widget.selected_category == "Restore"
    assert "Geri Yükleme" in widget.lbl_top_notification.text()

    widget.switch_category("Backup")
    assert widget.selected_category == "Backup"
    assert "Yedekleme" in widget.lbl_top_notification.text()


def test_backup_widget_context_menu_indexat_fix(qapp, db_session):
    """Verifies show_task_context_menu handles QTableView indexAt without AttributeError."""
    widget = BackupWidget(db_session)
    assert hasattr(widget, "task_table")

    # Call show_task_context_menu with a point outside rows - should return cleanly without error.
    # NOTE: BackupWidget seeds demo rows by default (see load_tasks_from_json's
    # fallback sample list), so QPoint(1, 1) actually lands on row 0 and opens a
    # real (blocking) QMenu.exec() — a large Y coordinate is reliably below any
    # seeded row and keeps indexAt(pos) invalid, matching the test's intent.
    widget.show_task_context_menu(QPoint(5, 9999))

    # Test get_selected_task when no selection
    assert widget.get_selected_task() is None


def test_new_task_dialog_duplicate_name_validation(qapp, db_session):
    """Tests duplicate name validation in NewTaskDialog (e.g. preventing 'Alp' duplicate task)."""
    widget = BackupWidget(db_session)
    widget.tasks_data.append({
        "id": "T-999",
        "name": "Alp",
        "type": "Backup",
        "source": "Dolibarr",
        "target_type": "Local Depolama",
        "schedule": "Manuel Tetikleme",
        "status": "manual",
        "history": [],
    })

    dlg = NewTaskDialog(mode="add", parent=widget)
    dlg.name_input.setText("Alp")
    dlg.dbar_dest_dir.setText("data/backups")

    # Attempt validation - duplicate "Alp" should be rejected
    dlg.validate_and_accept()
    assert dlg.result() != 1  # Dialog not accepted due to duplicate name warning


def test_backup_widget_quick_search_and_popups(qapp, db_session):
    """Tests quick search trigger and detail popup dialog initialization."""
    widget = BackupWidget(db_session)
    widget.show()
    widget.activateWindow()
    assert QTest.qWaitForWindowActive(widget, 2000)

    # Trigger quick search
    widget.trigger_quick_search()
    for _ in range(50):
        if widget.search_box.hasFocus():
            break
        QTest.qWait(20)
    assert widget.left_panel.is_open is True
    assert widget.search_box.hasFocus()

    # Detail popup test
    sample_task = widget.tasks_data[0]
    popup = TaskDetailPopupDialog(task=sample_task, active_tab=0, parent_widget=widget)
    assert popup.tabs.currentIndex() == 0
    assert sample_task["name"] in popup.windowTitle()


def test_backup_column_profile_persistence_and_settings(qapp, db_session):
    """Verifies column view profile persistence for backup profile key and settings module combo."""
    from PyQt6.QtGui import QStandardItemModel

    from src.desktop.managers.profile_manager import ProfileManager

    profile_key = "backup_tasks"
    profile_name = "TestBackupProfile"
    pm = ProfileManager(profile_key=profile_key)
    previous_active = pm.get_active_profile_name()
    ftv = FilterableTableView(headers_dict={0: ("Görev Adı", "name")}, profile_key=profile_key)
    model = QStandardItemModel(0, 1, ftv)
    model.setHorizontalHeaderLabels(["Görev Adı"])
    ftv.table_view.setModel(model)
    try:
        QTest.qWait(80)
        ftv.table_view.setColumnWidth(0, 173)
        ftv.save_column_profile(profile_name)
        reloaded = ProfileManager(profile_key=profile_key)
        assert reloaded.get_active_profile_name() == profile_name
        assert reloaded.load_profiles()[profile_name].column_settings.individual_columns["name"].width == 173

        view_settings = ViewSettingsWidget()
        idx = view_settings.module_combo.findData(profile_key)
        assert idx != -1
        view_settings.module_combo.setCurrentIndex(idx)
        assert view_settings.get_current_profile_key() == profile_key
        assert profile_name in view_settings.current_profiles
        assert "Yedekleme" in view_settings.module_combo.itemText(idx)
    finally:
        pm.delete_profile(profile_name)
        pm.set_active_profile_name(previous_active)
