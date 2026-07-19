import base64
import json
from pathlib import Path

from PyQt6.QtCore import QByteArray, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QDialog,
    QLineEdit,
    QMenu,
    QTableView,
    QWidget,
)

from src.desktop.ui.column_manager import ColumnManagerDialog


class MultiColumnSortFilterProxyModel(QSortFilterProxyModel):
    """Custom sort filter proxy model that supports independent filters for multiple columns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.column_filters: dict[int, str] = {}

    def set_column_filter(self, column: int, text: str):
        """Sets or clears the filter text for a specific column index."""
        cleaned_text = text.lower().strip()
        if not cleaned_text:
            self.column_filters.pop(column, None)
        else:
            self.column_filters[column] = cleaned_text
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        if not self.column_filters:
            return True

        source_model = self.sourceModel()
        if not source_model:
            return True

        for col_idx, filter_text in self.column_filters.items():
            index = source_model.index(source_row, col_idx, source_parent)
            data = source_model.data(index, Qt.ItemDataRole.DisplayRole)
            data_str = str(data).lower() if data is not None else ""
            if filter_text not in data_str:
                return False

        return True


class FilterBarWidget(QWidget):
    """A container widget holding filter QLineEdits that stay aligned with table columns."""

    def __init__(self, table_view: 'ManagedTableView', parent=None):
        super().__init__(parent)
        self.table_view = table_view
        self.line_edits: dict[int, QLineEdit] = {}
        self.init_ui()

    def init_ui(self):
        # We manually position the line edits using absolute coordinates (setGeometry)
        # to ensure perfect alignment with QHeaderView sections during resizing and scrolling.
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFixedHeight(28)
        self.update_filters()

        # Connect synchronization signals
        header = self.table_view.horizontalHeader()
        header.sectionResized.connect(self.adjust_positions)
        header.sectionMoved.connect(self.adjust_positions)
        
        # Connect scroll signal
        scroll_bar = self.table_view.horizontalScrollBar()
        scroll_bar.valueChanged.connect(self.adjust_positions)

    def update_filters(self):
        """Re-creates line edits based on the current model columns."""
        # Clear existing line edits
        for widget in self.line_edits.values():
            widget.deleteLater()
        self.line_edits.clear()

        model = self.table_view.model()
        if not model:
            return

        column_count = model.columnCount()
        for col_idx in range(column_count):
            line_edit = QLineEdit(self)
            line_edit.setPlaceholderText(self.tr("Filtrele..."))
            line_edit.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 2px 5px;
                    background-color: white;
                    font-size: 11px;
                }
                QLineEdit:focus {
                    border: 1px solid #14b8a6;
                }
            """)
            # Capture logical index in lambda to apply filters correctly
            logical_idx = col_idx
            line_edit.textChanged.connect(
                lambda text, idx=logical_idx: self.table_view.set_column_filter(idx, text),
            )
            self.line_edits[col_idx] = line_edit

        self.adjust_positions()

    def adjust_positions(self):
        """Repositions and resizes QLineEdits to match the visual position of sections."""
        header = self.table_view.horizontalHeader()
        if not header:
            return

        # Viewport width of the table
        viewport_width = self.table_view.viewport().width()

        for col_idx, line_edit in self.line_edits.items():
            if header.isSectionHidden(col_idx):
                line_edit.hide()
                continue

            # Get current viewport coordinate
            x_pos = header.sectionViewportPosition(col_idx)
            width = header.sectionSize(col_idx)

            # Only show and position the filter if it falls within the visible viewport bounds
            if x_pos + width < 0 or x_pos > viewport_width:
                line_edit.hide()
            else:
                line_edit.show()
                # Leave a tiny margin between fields for aesthetic separation
                line_edit.setGeometry(x_pos + 1, 2, width - 2, 24)


class ManagedTableView(QTableView):
    """Advanced QTableView with inline column filtering, custom header saving and column configuration."""

    def __init__(self, settings_key: str, parent=None):
        super().__init__(parent)
        self.settings_key = settings_key
        self.settings_path = Path("data") / f"grid_{settings_key}.json"
        
        self.proxy_model = MultiColumnSortFilterProxyModel(self)
        self.filter_bar: FilterBarWidget = None
        self.headers_dict: dict[int, tuple[str, str]] = {}
        self.hidden_columns: set[int] = set()

        # Selection configuration
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)

        # Setup context menu on header
        header = self.horizontalHeader()
        header.setSectionsMovable(True)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_header_context_menu)

    def set_source_model(self, model):
        """Binds the source model to the view via the multi-column proxy model."""
        self.proxy_model.setSourceModel(model)
        self.setModel(self.proxy_model)

        # Initialize headers_dict from model
        self.headers_dict.clear()
        for idx in range(model.columnCount()):
            display_name = model.headerData(idx, Qt.Orientation.Horizontal) or f"Kolon {idx}"
            self.headers_dict[idx] = (display_name, "")

        # Try to restore user state
        self.restore_view_settings()

        # Update dynamic filters if enabled
        if self.filter_bar:
            self.filter_bar.update_filters()

    def set_column_filter(self, column: int, text: str):
        """Updates the proxy model filters."""
        self.proxy_model.set_column_filter(column, text)

    def enable_filters(self, enabled: bool):
        """Shows or hides the inline filter row."""
        if enabled:
            if not self.filter_bar:
                self.filter_bar = FilterBarWidget(self, parent=self)
                self.setViewportMargins(0, 28, 0, 0)
                self.adjust_filter_geometry()
        else:
            if self.filter_bar:
                self.filter_bar.deleteLater()
                self.filter_bar = None
                self.setViewportMargins(0, 0, 0, 0)

    def adjust_filter_geometry(self):
        """Repositions the filter bar within the viewport margins."""
        if self.filter_bar:
            header_height = self.horizontalHeader().height()
            frame_width = self.frameWidth()
            self.filter_bar.setGeometry(
                frame_width,
                header_height + frame_width,
                self.viewport().width(),
                28,
            )
            self.filter_bar.adjust_positions()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.adjust_filter_geometry()

    def save_view_settings(self):
        """Saves current columns configuration (ordering, widths, hidden status) to a JSON file."""
        header = self.horizontalHeader()
        header_state = header.saveState()
        
        # Guard mechanism data
        source_model = self.proxy_model.sourceModel()
        column_count = source_model.columnCount() if source_model else 0
        
        # Base64 encode the binary QByteArray for clean JSON storage
        state_b64 = base64.b64encode(header_state.data()).decode('utf-8')

        settings = {
            "version": 1,
            "column_count": column_count,
            "header_state": state_b64,
            "hidden_columns": list(self.hidden_columns),
        }

        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f)
        except Exception:
            pass

    def restore_view_settings(self):
        """Restores grid state from saved JSON file after ensuring validation checks pass."""
        if not self.settings_path.exists():
            return

        try:
            with open(self.settings_path, encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            return

        source_model = self.proxy_model.sourceModel()
        column_count = source_model.columnCount() if source_model else 0

        # Guard Checks: Verify version and matching column count
        if settings.get("version") != 1 or settings.get("column_count") != column_count:
            return

        state_b64 = settings.get("header_state")
        if state_b64:
            try:
                state_bytes = base64.b64decode(state_b64.encode('utf-8'))
                q_byte_array = QByteArray(state_bytes)
                self.horizontalHeader().restoreState(q_byte_array)
            except Exception:
                pass

        self.hidden_columns = set(settings.get("hidden_columns", []))
        self.apply_hidden_columns()

    def apply_hidden_columns(self):
        for col_idx in range(len(self.headers_dict)):
            is_hidden = col_idx in self.hidden_columns
            self.setColumnHidden(col_idx, is_hidden)
        if self.filter_bar:
            self.filter_bar.adjust_positions()

    def show_header_context_menu(self, pos):
        """Shows custom column management context menu on horizontal header right click."""
        menu = QMenu(self)

        for col_idx, (display_name, _) in self.headers_dict.items():
            action = QAction(display_name, menu, checkable=True)
            action.setChecked(col_idx not in self.hidden_columns)
            # Dynamic slot mapping for toggling visibility
            action.triggered.connect(lambda checked, idx=col_idx: self.toggle_column(idx, checked))
            menu.addAction(action)

        menu.addSeparator()
        
        dia_action = QAction(self.tr("⚙️ Kolonları Yapılandır (DIA)"), menu)
        dia_action.triggered.connect(self.open_column_manager_dialog)
        menu.addAction(dia_action)

        menu.exec(self.horizontalHeader().mapToGlobal(pos))

    def toggle_column(self, col_idx: int, show: bool):
        if show:
            self.hidden_columns.discard(col_idx)
        else:
            self.hidden_columns.add(col_idx)
        self.apply_hidden_columns()
        self.save_view_settings()

    def open_column_manager_dialog(self):
        """Opens the standard ColumnManagerDialog and saves configuration on success."""
        dlg = ColumnManagerDialog(self.headers_dict, self.hidden_columns, f"grid_{self.settings_key}", self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.hidden_columns = dlg.get_hidden_columns()
            self.apply_hidden_columns()
            self.save_view_settings()
