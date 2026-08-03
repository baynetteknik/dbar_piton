"""
Tests for git_tracker.py and GitTrackerWidget component.
"""

import pytest
import sqlite3
import os
import git_tracker
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


def test_git_tracker_widget_instantiation(qapp, tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_git_tracker.db")
    monkeypatch.setattr(git_tracker, "DB_PATH", test_db)

    from src.desktop.ui.components.git_tracker_widget import GitTrackerWidget

    widget = GitTrackerWidget()
    assert widget is not None
    assert widget.tbl_tasks.rowCount() > 0
    assert widget.tbl_commits.columnCount() == 5
