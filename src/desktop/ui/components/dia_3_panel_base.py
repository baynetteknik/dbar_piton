"""Base class and layout template for DIA-Style 3-Panel Widgets.

Provides a unified 3-panel architecture:
1. Left Panel (EdgeTriggeredPanel - Filters / Tree Search)
2. Center Area (FilterableTableView + Pagination / Summary Footer)
3. Right Panel (EdgeTriggeredPanel - Fast Actions / Details)
"""

import logging
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.components.layout_hint_helper import register_layout_hint

logger = logging.getLogger(__name__)


class DIA3PanelBaseWidget(QWidget):
    """Generic 3-Panel DIA-Style Base Widget for documents, cards, and management screens."""

    status_message = pyqtSignal(str)
    data_changed = pyqtSignal()

    def __init__(
        self,
        db_session: Any = None,
        profile_key: str = "generic_3panel",
        module_name: str = "DIA 3-Panel Ekranı",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.db = db_session
        self.profile_key = profile_key
        self.module_name = module_name

        # Pagination & record state
        self.current_page: int = 1
        self.per_page: int = 25
        self.total_records: int = 0

        self.headers_dict: dict[int, tuple[str, str]] = self.setup_headers_dict()

        self.init_base_ui()
        register_layout_hint(self, self.module_name, "Ana Kapsayıcı (3-Panelli Düzen)")

    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        """Override to define header column structure. Index -> (Title, FieldName)."""
        return {
            0: ("ID", "id"),
            1: ("Başlık", "title"),
            2: ("Tarih", "created_at"),
        }

    def init_base_ui(self) -> None:
        """Construct the 3-panel layout structure."""
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(4)

        # --------------------------------------------------------
        # 1. SOL PANEL (EdgeTriggeredPanel) - FİLTRE VE ARAMA
        # --------------------------------------------------------
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)
        register_layout_hint(self.left_panel, self.module_name, "Sol Filtre Paneli")

        self.left_content_frame = QFrame()
        self.left_content_frame.setStyleSheet("background-color: transparent; border: none;")
        self.left_layout = QVBoxLayout(self.left_content_frame)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(6)

        self.setup_left_panel_content(self.left_content_frame, self.left_layout)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        left_scroll.setWidget(self.left_content_frame)
        self.left_panel.set_content(left_scroll)
        self.main_layout.addWidget(self.left_panel)

        # --------------------------------------------------------
        # 2. ORTA PANEL - FİLTRELENEBİLİR TABLO VE SAYFALAMA
        # --------------------------------------------------------
        self.center_container = QWidget()
        self.center_container.setObjectName("DIA3PanelCenterContainer")
        register_layout_hint(self.center_container, self.module_name, "Orta Tablo Paneli")

        self.center_layout = QVBoxLayout(self.center_container)
        self.center_layout.setContentsMargins(0, 0, 0, 0)
        self.center_layout.setSpacing(4)

        # Custom header widget / top bar insertion point
        self.top_bar_widget = QWidget()
        self.top_bar_layout = QHBoxLayout(self.top_bar_widget)
        self.top_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.top_bar_layout.setSpacing(6)
        self.center_layout.addWidget(self.top_bar_widget)

        # Main Table View
        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key=self.profile_key,
            enable_profile_bar=False,
            parent=self,
        )
        self.table_view = self.filterable_table.table_view
        self.table_model = QStandardItemModel(self)
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
        self.table_model.setHorizontalHeaderLabels(headers)
        self.table_view.setModel(self.table_model)

        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSelectionBehavior(QHeaderView.SelectionBehavior.SelectRows)

        self.center_layout.addWidget(self.filterable_table, 1)

        # Bottom bar / Pagination insertion point
        self.bottom_bar_widget = QWidget()
        self.bottom_bar_layout = QHBoxLayout(self.bottom_bar_widget)
        self.bottom_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.bottom_bar_layout.setSpacing(6)
        self.center_layout.addWidget(self.bottom_bar_widget)

        self.main_layout.addWidget(self.center_container, 1)

        # --------------------------------------------------------
        # 3. SAĞ PANEL (EdgeTriggeredPanel) - HIZLI İŞLEMLER
        # --------------------------------------------------------
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)
        register_layout_hint(self.right_panel, self.module_name, "Sağ İşlem Paneli")

        self.right_content_frame = QFrame()
        self.right_content_frame.setStyleSheet("background-color: transparent; border: none;")
        self.right_layout = QVBoxLayout(self.right_content_frame)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(6)

        self.setup_right_panel_content(self.right_content_frame, self.right_layout)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        right_scroll.setWidget(self.right_content_frame)
        self.right_panel.set_content(right_scroll)
        self.main_layout.addWidget(self.right_panel)

    def setup_left_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        """Override in subclasses to populate left filter panel."""
        lbl = QLabel("Filtreler")
        lbl.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(lbl)
        layout.addStretch()

    def setup_right_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        """Override in subclasses to populate right action panel."""
        lbl = QLabel("Hızlı İşlemler")
        lbl.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(lbl)
        layout.addStretch()

    def on_filter_changed(self) -> None:
        """Triggered when filters are changed."""
        self.current_page = 1
        self.load_data()

    def clear_filters(self) -> None:
        """Clear all active filters."""
        self.on_filter_changed()

    def load_data(self) -> None:
        """Load data into table model."""
        pass
