"""Layout Hint (Dev/Inspector Mode) Helper.

This module provides parametric display of module and section titles/hints on UI components
so developers and users can reference specific parts of the layout easily.
"""

import logging

from PyQt6.QtCore import QObject, QSettings
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

logger = logging.getLogger(__name__)

SETTINGS_ORGANIZATION = "baynetteknik"
SETTINGS_APPLICATION = "dbar_piton"
KEY_ENABLE_LAYOUT_HINTS = "enable_layout_hints"


class LayoutHintBadge(QLabel):
    """Small overlay badge showing module and section names."""

    def __init__(self, module_name: str, section_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.module_name = module_name
        self.section_name = section_name
        self.setObjectName("LayoutHintBadge")
        self.setText(f"🏷️ [{module_name} ➔ {section_name}]")
        self.setToolTip(f"Modül: {module_name}\nBölüm: {section_name}")
        self.setStyleSheet("""
            QLabel#LayoutHintBadge {
                background-color: #1e3a8a;
                color: #ffffff;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
                font-family: 'Segoe UI', sans-serif;
            }
        """)
        self.setFixedHeight(20)


class GlobalLayoutHintManager(QObject):
    """Global manager for registering layout hints and toggling their visibility."""

    _instance = None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.is_enabled: bool = False
        self.registered_widgets: list[tuple[QWidget, str, str]] = []
        self._badges: dict[QWidget, LayoutHintBadge] = {}

    @classmethod
    def get_instance(cls) -> "GlobalLayoutHintManager":
        if cls._instance is None:
            cls._instance = GlobalLayoutHintManager()
        return cls._instance

    def register(self, widget: QWidget, module_name: str, section_name: str) -> None:
        """Register a widget with its module and section hint names."""
        if not widget:
            return

        widget.setProperty("_layout_module", module_name)
        widget.setProperty("_layout_section", section_name)

        # Combine tooltip
        existing_tooltip = widget.toolTip()
        hint_str = f"🏷️ [{module_name} ➔ {section_name}]"
        if not existing_tooltip:
            widget.setToolTip(hint_str)
        elif hint_str not in existing_tooltip:
            widget.setToolTip(f"{hint_str}\n{existing_tooltip}")

        self.registered_widgets.append((widget, module_name, section_name))

        if self.is_enabled:
            self._ensure_badge(widget, module_name, section_name)

    def _ensure_badge(self, widget: QWidget, module_name: str, section_name: str) -> None:
        """Add or show badge on the target widget if enabled."""
        if widget in self._badges:
            badge = self._badges[widget]
            badge.show()
            return

        badge = LayoutHintBadge(module_name, section_name, parent=widget)

        # Try to insert badge into widget layout if it exists
        layout = widget.layout()
        if layout is not None:
            if isinstance(layout, QHBoxLayout):
                layout.insertWidget(0, badge)
            else:
                layout.addWidget(badge)
            badge.show()
        else:
            # Place at top-left corner
            badge.move(4, 4)
            badge.show()

        self._badges[widget] = badge

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable layout hints application-wide."""
        self.is_enabled = enabled

        for _widget, badge in list(self._badges.items()):
            try:
                if enabled:
                    badge.show()
                else:
                    badge.hide()
            except RuntimeError:
                # Widget was deleted
                pass

        if enabled:
            for widget, mod, sec in self.registered_widgets:
                try:
                    if widget:
                        self._ensure_badge(widget, mod, sec)
                except RuntimeError:
                    pass

        logger.info(f"Global Layout Hint Inspector Mode: {'Enabled' if enabled else 'Disabled'}")


def set_layout_hints_enabled(enabled: bool) -> None:
    """Save setting to QSettings and update global manager."""
    settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
    settings.setValue(KEY_ENABLE_LAYOUT_HINTS, enabled)
    settings.sync()

    manager = GlobalLayoutHintManager.get_instance()
    manager.set_enabled(enabled)


def is_layout_hints_enabled() -> bool:
    """Return whether layout hints are enabled in QSettings."""
    settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
    return settings.value(KEY_ENABLE_LAYOUT_HINTS, False, type=bool)


def init_layout_hints() -> None:
    """Initialize layout hint manager on application startup."""
    enabled = is_layout_hints_enabled()
    manager = GlobalLayoutHintManager.get_instance()
    manager.set_enabled(enabled)


def register_layout_hint(widget: QWidget, module_name: str, section_name: str) -> None:
    """Helper function to register a widget with module & section hint."""
    manager = GlobalLayoutHintManager.get_instance()
    manager.register(widget, module_name, section_name)
