"""
Tests for git_tracker.py and DIA 3-Panel GitTrackerScreen / GitTrackerWidget components.
"""

import pytest
import sqlite3
import os
import git_tracker
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_git_tracker_db_init_and_seed(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_git_tracker.db")
    monkeypatch.setattr(git_tracker, "DB_PATH", test_db)

    git_tracker.init_db()
    git_tracker.seed_initial_tasks()

    assert os.path.exists(test_db)

    conn = git_tracker.get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM tasks")
    tasks_count = cursor.fetchone()["count"]
    assert tasks_count > 0

    cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'Yapıldı'")
    completed_count = cursor.fetchone()["count"]
    assert completed_count > 0

    conn.close()


def test_repository_and_account_crud(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_git_tracker.db")
    monkeypatch.setattr(git_tracker, "DB_PATH", test_db)

    git_tracker.init_db()

    # Repositories
    repo_id = git_tracker.add_repository(name="Test Repo", remote_url="https://github.com/test/repo.git", default_branch="develop", is_default=1)
    assert repo_id > 0
    repos = git_tracker.get_repositories()
    assert len(repos) >= 1
    assert any(r["name"] == "Test Repo" for r in repos)

    # Accounts
    acc_id = git_tracker.add_account(username="testuser", email="test@toya.com", token="ghp_12345", is_default=1)
    assert acc_id > 0
    accs = git_tracker.get_accounts()
    assert len(accs) >= 1
    assert any(a["username"] == "testuser" for a in accs)

    # Delete
    git_tracker.delete_repository(repo_id)
    assert not any(r["id"] == repo_id for r in git_tracker.get_repositories())

    git_tracker.delete_account(acc_id)
    assert not any(a["id"] == acc_id for a in git_tracker.get_accounts())


def test_git_status_and_branches():
    status_info = git_tracker.get_git_status()
    assert isinstance(status_info, dict)
    assert "branch" in status_info
    assert "changed_files" in status_info
    assert "ahead_count" in status_info

    branches = git_tracker.get_git_branches()
    assert isinstance(branches, list)


def test_git_worker_instantiation():
    worker = git_tracker.GitWorker(action="fetch")
    assert worker.action == "fetch"
    assert hasattr(worker, "stage_progress")
    assert hasattr(worker, "log_line")
    assert hasattr(worker, "finished")


def test_git_tracker_3panel_screen_instantiation(qapp, tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_git_tracker.db")
    monkeypatch.setattr(git_tracker, "DB_PATH", test_db)

    from src.desktop.ui.components.git_tracker_screen import GitTrackerScreen, GitRepositoryDialog, GitAccountDialog
    from src.desktop.ui.components.git_tracker_widget import GitTrackerWidget
    from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
    from src.desktop.ui.components.filterable_table import FilterableTableView

    screen = GitTrackerScreen()
    assert screen is not None
    assert isinstance(screen.left_panel, EdgeTriggeredPanel)
    assert isinstance(screen.right_panel, EdgeTriggeredPanel)
    assert isinstance(screen.filterable_table, FilterableTableView)
    assert screen.progress_bar is not None
    assert screen.console_drawer is not None

    # Check header column 0 is '☑' and tooltip is 'Seçim Yapın'
    assert screen.headers_dict[0][0] == "☑"
    assert screen.table_model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole) == "Seçim Yapın"

    # Dialogs
    dlg_repo = GitRepositoryDialog()
    assert dlg_repo is not None

    dlg_acc = GitAccountDialog()
    assert dlg_acc is not None

    widget = GitTrackerWidget()
    assert widget is not None
    assert widget.screen is not None


def test_collapsible_section_set_expanded(qapp):
    from src.desktop.ui.components.collapsible_section import CollapsibleSection

    sec = CollapsibleSection("Test Grubu", is_expanded=True)
    sec.show()
    assert sec.is_expanded is True
    assert not sec.content_frame.isHidden()

    sec.set_expanded(False)
    assert sec.is_expanded is False
    assert sec.content_frame.isHidden()

    sec.set_expanded(True)
    assert sec.is_expanded is True
    assert not sec.content_frame.isHidden()


