import sys

import pytest
from PyQt6.QtWidgets import QApplication

from src.core.models import Site
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.customers import MusteriYonetimiWidget


@pytest.fixture(scope="session")
def qapp():
    """Provides a single QApplication instance for PyQt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_edge_triggered_panel_pin_and_tooltips(qapp):
    """Tests the pin toggle behavior, tooltips, and style changes of EdgeTriggeredPanel."""
    panel = EdgeTriggeredPanel(side="right")
    
    # Verify initial settings
    assert panel.is_pinned is False
    assert panel.pin_btn.toolTip() == "Paneli Sabitle"
    assert panel.close_btn.toolTip() == "Paneli Kapat"

    # Toggle pin
    panel.toggle_pin()
    assert panel.is_pinned is True
    assert panel.pin_btn.toolTip() == "Sabitlemeyi Kaldır"
    
    # Verify style sheet changes (should contain background-color #3b82f6)
    style = panel.pin_btn.styleSheet()
    assert "#3b82f6" in style

    # Toggle pin back
    panel.toggle_pin()
    assert panel.is_pinned is False
    assert panel.pin_btn.toolTip() == "Paneli Sabitle"
    assert "#ffffff" in panel.pin_btn.styleSheet()


def test_musteri_yonetimi_widget_pagination_margins(qapp, db_session):
    """Tests the dynamic margins applied to the pagination layout based on panel state."""
    # Insert a dummy Site to avoid DB errors when looking up company working mode
    site = Site(
        id=1,
        name="Test Co",
        cms_type="dolibarr",
        working_mode="local_master",
        url="http://test.url",
        api_key_account="test-api-key"
    )
    db_session.add(site)
    db_session.commit()

    widget = MusteriYonetimiWidget(db_session, company_id=1)

    # Initial state (both panels closed, overlay mode)
    assert widget.left_panel.is_open is False
    assert widget.right_panel.is_open is False
    
    # Check margins (left, top, right, bottom)
    margins = widget.pagination_layout.contentsMargins()
    assert margins.left() == 0
    assert margins.right() == 0

    # Open left panel in overlay mode (not pinned)
    widget.left_panel.open_panel()
    widget.update_pagination_margins()
    margins = widget.pagination_layout.contentsMargins()
    assert margins.left() == widget.left_panel.panel_width
    assert margins.right() == 0

    # Open right panel in overlay mode (not pinned)
    widget.right_panel.open_panel()
    widget.update_pagination_margins()
    margins = widget.pagination_layout.contentsMargins()
    assert margins.left() == widget.left_panel.panel_width
    assert margins.right() == widget.right_panel.panel_width

    # Pin right panel (margin for right should become 0 because it's now in the layout flow)
    widget.right_panel.is_pinned = True
    widget.update_pagination_margins()
    margins = widget.pagination_layout.contentsMargins()
    assert margins.left() == widget.left_panel.panel_width
    assert margins.right() == 0
