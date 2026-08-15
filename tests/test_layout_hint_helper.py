import sys

import pytest
from PyQt6.QtWidgets import QApplication, QWidget

from src.desktop.ui.components.layout_hint_helper import (
    GlobalLayoutHintManager,
    is_layout_hints_enabled,
    register_layout_hint,
    set_layout_hints_enabled,
)


@pytest.fixture(scope="session")
def qapp():
    """Provides a single QApplication instance for PyQt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_layout_hint_settings_toggle():
    """Tests saving and retrieving layout hints enabled state."""
    initial = is_layout_hints_enabled()
    try:
        set_layout_hints_enabled(True)
        assert is_layout_hints_enabled() is True

        set_layout_hints_enabled(False)
        assert is_layout_hints_enabled() is False
    finally:
        set_layout_hints_enabled(initial)


def test_register_layout_hint(qapp):
    """Tests widget property and tooltip registration via layout hint helper."""
    widget = QWidget()
    register_layout_hint(widget, "Müşteri Yönetimi", "Sol Filtre Paneli")

    assert widget.property("_layout_module") == "Müşteri Yönetimi"
    assert widget.property("_layout_section") == "Sol Filtre Paneli"
    assert "🏷️ [Müşteri Yönetimi ➔ Sol Filtre Paneli]" in widget.toolTip()


def test_layout_hint_manager_badges(qapp):
    """Tests layout hint manager badges toggling."""
    manager = GlobalLayoutHintManager.get_instance()
    widget = QWidget()
    manager.register(widget, "Test Module", "Test Section")

    manager.set_enabled(True)
    assert manager.is_enabled is True
    assert widget in manager._badges

    widget.show()
    assert manager._badges[widget].isVisible() is True

    manager.set_enabled(False)
    assert manager.is_enabled is False
    assert manager._badges[widget].isVisible() is False
