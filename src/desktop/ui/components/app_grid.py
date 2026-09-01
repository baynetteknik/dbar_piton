"""
TOYA ERP - AppGrid Sınıfı
Kurumsal ERP mimarisinin DEĞİŞMEZ temel liste/tablo bileşenidir.
Doğrudan QTableWidget kullanmak yasaktır; tüm tablolar AppGrid'den türetilir.
Merkezi ThemeManager'a bağlıdır ve isteğe bağlı ekran bazlı özel başlık yüksekliği (custom_header_height)
ve veri satır yüksekliği (custom_row_height) ayarlarını destekler.
"""

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)

from src.desktop.core.grid_presets import get_preset
from src.desktop.managers.theme_manager import ThemeManager


class AppGrid(QTableWidget):
    # Sinyaller
    row_double_clicked = pyqtSignal(int, dict)  # row_index, row_dict

    def __init__(
        self, 
        preset: str, 
        custom_row_height: int | None = None, 
        custom_header_height: int | None = None,
        parent=None,
    ):
        super().__init__(parent)
        
        self.preset_id = preset
        self.preset_config = get_preset(preset)
        self.theme = ThemeManager()
        self.custom_row_height = custom_row_height
        self.custom_header_height = custom_header_height
        self._raw_data: list[list[Any]] = []
        
        self._setup_table_properties()
        self._apply_preset_headers()
        self._connect_theme_signals()
        self._setup_context_menu()

    @property
    def effective_row_height(self) -> int:
        """Ekran özel veri satır yüksekliği tanımlıysa onu, değilse merkezi ThemeManager değerini kullanır."""
        return self.custom_row_height if self.custom_row_height is not None else self.theme.row_height

    @property
    def effective_header_height(self) -> int:
        """Ekran özel başlık yüksekliği tanımlıysa onu, değilse merkezi ThemeManager değerini kullanır."""
        return self.custom_header_height if self.custom_header_height is not None else self.theme.header_height

    def set_custom_row_height(self, height: int | None):
        """Ekran bazlı özel veri satır yüksekliğini ayarlar veya None ile merkezi temaya geri döner."""
        self.custom_row_height = height
        eff_height = self.effective_row_height
        self.verticalHeader().setDefaultSectionSize(eff_height)
        for r in range(self.rowCount()):
            self.setRowHeight(r, eff_height)
        self.viewport().update()

    def set_custom_header_height(self, height: int | None):
        """Ekran bazlı özel başlık satır yüksekliğini ayarlar veya None ile merkezi temaya geri döner."""
        self.custom_header_height = height
        eff_h_height = self.effective_header_height
        self.horizontalHeader().setFixedHeight(eff_h_height)
        self.viewport().update()

    def _setup_table_properties(self):
        """Temel ERP tablo standartlarını ayarlar."""
        self.setAlternatingRowColors(True)
        self.setShowGrid(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWordWrap(False)
        
        # Dikey başlık ve satır yüksekliği
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(self.effective_row_height)
        
        # Yatay başlık davranışı ve başlık satır yüksekliği
        h_header = self.horizontalHeader()
        h_header.setHighlightSections(False)
        h_header.setStretchLastSection(True)
        h_header.setFixedHeight(self.effective_header_height)
        h_header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        h_header.customContextMenuRequested.connect(self._show_header_context_menu)
        
        # Tema stilini uygula
        self.setStyleSheet(self.theme.get_table_stylesheet())
        
        # Çift tıklama olayı
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def _apply_preset_headers(self):
        """Preset içerisindeki sütun başlıklarını uygular."""
        cols = self.preset_config["columns"]
        self.setColumnCount(len(cols))
        self.setHorizontalHeaderLabels(cols)

    def _connect_theme_signals(self):
        """ThemeManager canlı güncellemelerine bağlanır."""
        self.theme.theme_changed.connect(self._on_theme_changed)
        self.theme.row_height_changed.connect(self._on_row_height_changed)
        self.theme.header_height_changed.connect(self._on_header_height_changed)

    def _on_theme_changed(self):
        self.setStyleSheet(self.theme.get_table_stylesheet())

    def _on_row_height_changed(self, height: int):
        """Merkezi tema satır yüksekliği değiştiğinde anında tepki verir (özel yükseklik yoksa)."""
        if self.custom_row_height is None:
            self.verticalHeader().setDefaultSectionSize(height)
            for r in range(self.rowCount()):
                self.setRowHeight(r, height)
            self.viewport().update()

    def _on_header_height_changed(self, height: int):
        """Merkezi tema başlık yüksekliği değiştiğinde anında tepki verir (özel başlık yüksekliği yoksa)."""
        if self.custom_header_height is None:
            self.horizontalHeader().setFixedHeight(height)
            self.viewport().update()

    def resizeEvent(self, event):  # noqa: N802
        """Pencere boyutu değiştiğinde sütunları preset oranlarına göre akıllıca dağıtır."""
        super().resizeEvent(event)
        self._apply_column_width_ratios()

    def _apply_column_width_ratios(self):
        """width_ratios listesine göre sütun genişliklerini hesaplar."""
        available_width = self.viewport().width()
        if available_width <= 0:
            return

        ratios = self.preset_config.get("width_ratios", [])
        num_cols = self.columnCount()

        for col_idx in range(min(len(ratios), num_cols)):
            ratio = ratios[col_idx]
            col_width = int(available_width * ratio)
            self.setColumnWidth(col_idx, max(col_width, 40))

    def setData(self, rows_data: list[list[Any]]):  # noqa: N802
        """
        Verileri tabloya yükler ve preset'e göre otomatik hizalama & tip formatlaması yapar.
        Performans için render döngüsü optimize edilmiştir.
        """
        self.setUpdatesEnabled(False)
        self._raw_data = rows_data
        self.setRowCount(len(rows_data))
        
        eff_height = self.effective_row_height
        align_map = {
            "L": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "R": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "C": Qt.AlignmentFlag.AlignCenter,
        }
        
        alignments = self.preset_config.get("alignments", ["L"] * self.columnCount())
        types = self.preset_config.get("types", ["text"] * self.columnCount())

        for row_idx, row in enumerate(rows_data):
            self.setRowHeight(row_idx, eff_height)
            for col_idx in range(self.columnCount()):
                val = row[col_idx] if col_idx < len(row) else ""
                formatted_text = self._format_cell_value(val, types[col_idx])
                
                item = QTableWidgetItem(formatted_text)
                align_key = alignments[col_idx] if col_idx < len(alignments) else "L"
                item.setTextAlignment(align_map.get(align_key, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
                
                self.setItem(row_idx, col_idx, item)

        self.setUpdatesEnabled(True)

    def _format_cell_value(self, val: Any, col_type: str) -> str:
        """ERP veri tiplerine göre otomatik formatlama yapar."""
        if val is None:
            return ""
        
        if col_type == "currency":
            try:
                num = float(val)
                # Standart 1.250,50 TL formatı
                return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except (ValueError, TypeError):
                return str(val)
        elif col_type == "percent":
            try:
                num = float(val)
                return f"%{num:g}"
            except (ValueError, TypeError):
                return str(val)
        return str(val)

    def _on_cell_double_clicked(self, row: int, column: int):
        """Satır çift tıklandığında veri sözlüğü ile sinyal yayar."""
        if 0 <= row < len(self._raw_data):
            cols = self.preset_config["columns"]
            row_vals = self._raw_data[row]
            row_dict = {cols[i]: row_vals[i] for i in range(min(len(cols), len(row_vals)))}
            self.row_double_clicked.emit(row, row_dict)

    def _setup_context_menu(self):
        """Standart ERP sağ tık menüsü (Kopyala, Excel, Kolon Göster/Gizle, Kolon Oranla)."""
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_header_context_menu(self, pos):
        """Tablo başlığına sağ tıklandığında sütun açma/kapama menüsünü açar."""
        menu = QMenu(self)
        menu.setStyleSheet(self.theme.get_context_menu_stylesheet())

        title_act = QAction("📊 SÜTUN GÖRÜNÜRLÜĞÜ", menu)
        title_act.setEnabled(False)
        menu.addAction(title_act)
        menu.addSeparator()

        cols = self.preset_config.get("columns", [])
        for col_idx, col_name in enumerate(cols):
            act = QAction(col_name, menu)
            act.setCheckable(True)
            act.setChecked(not self.isColumnHidden(col_idx))
            act.triggered.connect(
                lambda checked, idx=col_idx: self.toggle_column_visibility(idx, checked),
            )
            menu.addAction(act)

        menu.addSeparator()
        act_show_all = QAction("➕ Tüm Sütunları Göster", menu)
        act_show_all.triggered.connect(self.show_all_columns)
        menu.addAction(act_show_all)

        reset_cols_action = QAction("⚙️ Sütun Genişliklerini Oranla", menu)
        reset_cols_action.triggered.connect(self._apply_column_width_ratios)
        menu.addAction(reset_cols_action)

        menu.exec(self.horizontalHeader().mapToGlobal(pos))

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(self.theme.get_context_menu_stylesheet())
        
        copy_action = QAction("📋 Seçili Hücreleri Kopyala", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self._copy_selected_cells)
        menu.addAction(copy_action)
        
        menu.addSeparator()
        
        excel_action = QAction("📊 Excel'e Aktar (.xlsx)", self)
        excel_action.triggered.connect(lambda: print(f"[{self.preset_id}] Excel aktarımı tetiklendi."))
        menu.addAction(excel_action)

        # Sütunları Göster / Gizle Alt Menüsü
        col_menu = menu.addMenu("👁️ Sütunları Göster / Gizle")
        col_menu.setStyleSheet(self.theme.get_context_menu_stylesheet())
        cols = self.preset_config.get("columns", [])
        for col_idx, col_name in enumerate(cols):
            act = QAction(col_name, col_menu)
            act.setCheckable(True)
            act.setChecked(not self.isColumnHidden(col_idx))
            act.triggered.connect(
                lambda checked, idx=col_idx: self.toggle_column_visibility(idx, checked),
            )
            col_menu.addAction(act)

        col_menu.addSeparator()
        act_show_all = QAction("➕ Tüm Sütunları Göster", col_menu)
        act_show_all.triggered.connect(self.show_all_columns)
        col_menu.addAction(act_show_all)
        
        reset_cols_action = QAction("⚙️ Sütun Genişliklerini Oranla", menu)
        reset_cols_action.triggered.connect(self._apply_column_width_ratios)
        menu.addAction(reset_cols_action)
        
        menu.exec(self.viewport().mapToGlobal(pos))

    def toggle_column_visibility(self, col_idx: int, visible: bool):
        """Belirtilen sütunun görünürlüğünü ayarlar."""
        self.setColumnHidden(col_idx, not visible)

    def show_all_columns(self):
        """Tüm sütunları görünür yapar."""
        for col_idx in range(self.columnCount()):
            self.setColumnHidden(col_idx, False)

    def _copy_selected_cells(self):
        """Seçili hücreleri panoya kopyalar."""
        selected_ranges = self.selectedRanges()
        if not selected_ranges:
            return
        
        clipboard_text = ""
        for r_range in selected_ranges:
            for r in range(r_range.topRow(), r_range.bottomRow() + 1):
                row_items = []
                for c in range(r_range.leftColumn(), r_range.rightColumn() + 1):
                    item = self.item(r, c)
                    row_items.append(item.text() if item else "")
                clipboard_text += "\t".join(row_items) + "\n"
                
        QApplication.clipboard().setText(clipboard_text.strip())
