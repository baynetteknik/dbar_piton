"""
ToyaUI — FilterableTableView (Geliştirilmiş)
isl.quo.001 ve tüm liste ekranları için DIA tarzı grid bileşeni.

Özellikler:
    - Başlık yüksekliği 26px
    - Satır yüksekliği ThemeManager'dan
    - Sağ tık menüsü (sırala/gizle/göster/profil)
    - Header sağ tık menüsü
    - Profil kaydet/yükle (JSON)
    - Çoklu seçim
    - Artan/azalan sıralama (başlığa tıkla)
    - Filtre satırı (başlık altında)
    - Kolon yönetimi
"""

import json
import logging
import os
from typing import Any

from PyQt6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import QAction, QColor, QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class FilterableTableView(QWidget):
    """
    DIA tarzı gelişmiş liste/tablo bileşeni.

    Sinyaller:
        row_double_clicked(int): Satıra çift tıklanınca — satır indeksi
        selection_changed(list): Seçim değişince — seçili satır indeksleri
        header_clicked(int): Başlığa tıklanınca — sütun indeksi
    """

    row_double_clicked = pyqtSignal(int)
    selection_changed  = pyqtSignal(list)
    header_clicked     = pyqtSignal(int)

    def __init__(
        self,
        headers_dict: dict[int, tuple[str, str]] | None = None,
        profile_key: str = "default_table",
        enable_profile_bar: bool = True,
        enable_filter_row: bool = False,
        row_height: int = 26,
        parent=None,
    ):
        super().__init__(parent)
        self.headers_dict      = headers_dict or {}
        self.profile_key       = profile_key
        self.enable_profile_bar = enable_profile_bar
        self.enable_filter_row  = enable_filter_row
        self._row_height        = row_height
        self._sort_col          = -1
        self._sort_asc          = True

        self._init_ui()
        self._load_profile()

    # ─────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────

    def _init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(0)

        # Filtre satırı (opsiyonel)
        if self.enable_filter_row:
            filter_frame = QFrame()
            filter_frame.setFixedHeight(28)
            filter_frame.setStyleSheet(
                "QFrame { background:#f8fafc; border-bottom:1px solid #e2e8f0; }"
            )
            filter_lyt = QHBoxLayout(filter_frame)
            filter_lyt.setContentsMargins(4, 2, 4, 2)
            filter_lyt.setSpacing(4)

            lbl = QLabel("🔍")
            lbl.setStyleSheet("font-size:12px;")
            self.txt_filter = QLineEdit()
            self.txt_filter.setPlaceholderText("Hızlı filtre...")
            self.txt_filter.setFixedHeight(22)
            self.txt_filter.setStyleSheet(
                "border:1px solid #cbd5e1; border-radius:3px; "
                "padding:1px 6px; font-size:10px; background:white;"
            )
            self.txt_filter.textChanged.connect(self._on_filter_changed)

            btn_clear = QPushButton("✕")
            btn_clear.setFixedSize(22, 22)
            btn_clear.setStyleSheet(
                "background:#e2e8f0; border:none; border-radius:3px; "
                "font-size:10px; color:#64748b;"
            )
            btn_clear.clicked.connect(lambda: self.txt_filter.clear())

            filter_lyt.addWidget(lbl)
            filter_lyt.addWidget(self.txt_filter, 1)
            filter_lyt.addWidget(btn_clear)
            lyt.addWidget(filter_frame)

        # Ana tablo
        self.table_view = QTableView()
        self.model = QStandardItemModel(self)

        # Proxy model (filtreleme + sıralama)
        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setFilterKeyColumn(-1)  # Tüm sütunlarda filtrele
        self.table_view.setModel(self.proxy_model)

        # Header ayarları
        hh = self.table_view.horizontalHeader()
        hh.setFixedHeight(26)  # ← Başlık yüksekliği 26px
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        hh.setSectionsMovable(True)
        hh.setSortIndicatorShown(True)
        hh.sectionClicked.connect(self._on_header_clicked)
        hh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hh.customContextMenuRequested.connect(self._show_header_menu)

        # Dikey header
        vh = self.table_view.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(self._row_height)

        # Seçim
        self.table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_view.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table_view.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        # Görünüm
        self.table_view.setShowGrid(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setWordWrap(False)
        self.table_view.setSortingEnabled(False)  # Manuel sıralama
        self.table_view.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table_view.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

        # Stil
        self.table_view.setStyleSheet("""
            QTableView {
                border: 1px solid #cbd5e1;
                background-color: white;
                gridline-color: #f1f5f9;
                border-radius: 4px;
                font-family: 'Segoe UI';
                font-size: 11px;
                color: #334155;
                alternate-background-color: #f8fafc;
            }
            QTableView::item {
                padding: 3px 6px;
                border: none;
            }
            QTableView::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
                font-weight: 600;
            }
            QTableView::item:hover {
                background-color: #eff6ff;
            }
            QHeaderView::section {
                background-color: #1e3a8a;
                color: #ffffff;
                padding: 3px 6px;
                border: none;
                border-right: 1px solid #2d4fa0;
                border-bottom: 2px solid #1e40af;
                font-weight: bold;
                font-size: 10px;
                font-family: 'Segoe UI';
            }
            QHeaderView::section:hover {
                background-color: #2563eb;
            }
            QHeaderView::section:checked {
                background-color: #1d4ed8;
            }
            QScrollBar:horizontal {
                height: 8px; background: #f1f5f9;
            }
            QScrollBar:vertical {
                width: 8px; background: #f1f5f9;
            }
            QScrollBar::handle {
                background: #cbd5e1; border-radius: 4px;
            }
        """)

        # Sağ tık
        self.table_view.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table_view.customContextMenuRequested.connect(
            self._show_body_menu
        )

        # Sinyaller
        self.table_view.doubleClicked.connect(self._on_double_clicked)
        self.table_view.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )

        lyt.addWidget(self.table_view, 1)

        # Header sütunlarını ayarla
        if self.headers_dict:
            self._setup_headers()

    def _setup_headers(self):
        """headers_dict'ten sütun başlıklarını ayarla."""
        headers = [
            self.headers_dict[i][0]
            for i in sorted(self.headers_dict.keys())
        ]
        self.model.setHorizontalHeaderLabels(headers)

        # Varsayılan genişlikler
        hh = self.table_view.horizontalHeader()
        for i in range(len(headers)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

    # ─────────────────────────────────────────────
    # SIRALAMA
    # ─────────────────────────────────────────────

    def _on_header_clicked(self, col: int):
        """Başlığa tıklanınca sırala."""
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        order = (
            Qt.SortOrder.AscendingOrder
            if self._sort_asc
            else Qt.SortOrder.DescendingOrder
        )
        self.proxy_model.sort(col, order)
        self.table_view.horizontalHeader().setSortIndicator(col, order)
        self.header_clicked.emit(col)

    def sort_by_column(self, col: int, ascending: bool = True):
        """Dışarıdan sıralama tetikle."""
        self._sort_col = col
        self._sort_asc = ascending
        order = (
            Qt.SortOrder.AscendingOrder if ascending
            else Qt.SortOrder.DescendingOrder
        )
        self.proxy_model.sort(col, order)
        self.table_view.horizontalHeader().setSortIndicator(col, order)

    # ─────────────────────────────────────────────
    # FİLTRELEME
    # ─────────────────────────────────────────────

    def _on_filter_changed(self, text: str):
        """Filtre metnine göre satırları gizle/göster."""
        self.proxy_model.setFilterFixedString(text)

    def set_filter(self, text: str, col: int = -1):
        """Dışarıdan filtre uygula."""
        self.proxy_model.setFilterKeyColumn(col)
        self.proxy_model.setFilterFixedString(text)
        if hasattr(self, "txt_filter"):
            self.txt_filter.setText(text)

    def clear_filter(self):
        """Filtreyi temizle."""
        self.proxy_model.setFilterFixedString("")
        if hasattr(self, "txt_filter"):
            self.txt_filter.clear()

    # ─────────────────────────────────────────────
    # SAĞ TIK MENÜSÜ — GÖVDE
    # ─────────────────────────────────────────────

    def _menu_style(self) -> str:
        return """
            QMenu {
                background: #ffffff;
                border: 1px solid #cbd5e1;
                font-size: 10px;
                padding: 2px;
            }
            QMenu::item { padding: 5px 20px 5px 10px; }
            QMenu::item:selected {
                background: #2563eb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #e2e8f0;
                margin: 2px 0;
            }
        """

    def _show_body_menu(self, pos):
        """Tablo gövdesi sağ tık menüsü."""
        index = self.table_view.indexAt(pos)
        row = index.row() if index.isValid() else -1
        col = index.column() if index.isValid() else -1
        sel_rows = self._get_selected_rows()

        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())

        # Sıralama
        if col >= 0:
            col_name = self._get_col_name(col)
            act_asc  = QAction(f"🔼 '{col_name}' Artan Sırala", self)
            act_desc = QAction(f"🔽 '{col_name}' Azalan Sırala", self)
            menu.addAction(act_asc)
            menu.addAction(act_desc)
            menu.addSeparator()

            act_asc.triggered.connect(
                lambda: self.sort_by_column(col, True)
            )
            act_desc.triggered.connect(
                lambda: self.sort_by_column(col, False)
            )

            # Sütun gizle
            act_hide = QAction(f"🙈 '{col_name}' Sütununu Gizle", self)
            menu.addAction(act_hide)
            act_hide.triggered.connect(
                lambda: self.table_view.setColumnHidden(col, True)
            )

        # Gizli sütunları göster
        hidden = [
            i for i in range(self.model.columnCount())
            if self.table_view.isColumnHidden(i)
        ]
        if hidden:
            show_m = menu.addMenu("👁️ Gizli Sütunları Göster")
            for hc in hidden:
                hn = self._get_col_name(hc)
                a = QAction(hn, self)
                a.triggered.connect(
                    lambda _, c=hc: self.table_view.setColumnHidden(c, False)
                )
                show_m.addAction(a)

        menu.addSeparator()

        # Kopyala
        if row >= 0:
            act_copy = QAction("📋 Satırı Kopyala", self)
            act_copy.triggered.connect(lambda: self._copy_row(row))
            menu.addAction(act_copy)

        act_copy_all = QAction("📋 Tümünü Kopyala (Excel)", self)
        act_copy_all.triggered.connect(self._copy_all)
        menu.addAction(act_copy_all)
        menu.addSeparator()

        # Profil
        act_save  = QAction("💾 Görünümü Kaydet", self)
        act_reset = QAction("↩️ Görünümü Sıfırla", self)
        act_save.triggered.connect(self._save_profile)
        act_reset.triggered.connect(self._reset_view)
        menu.addAction(act_save)
        menu.addAction(act_reset)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    # ─────────────────────────────────────────────
    # SAĞ TIK MENÜSÜ — HEADER
    # ─────────────────────────────────────────────

    def _show_header_menu(self, pos):
        """Header sağ tık menüsü."""
        col = self.table_view.horizontalHeader().logicalIndexAt(pos)
        col_name = self._get_col_name(col)

        menu = QMenu(self)
        menu.setStyleSheet(self._menu_style())

        act_asc  = QAction("🔼 Artan Sırala", self)
        act_desc = QAction("🔽 Azalan Sırala", self)
        act_asc.triggered.connect(lambda: self.sort_by_column(col, True))
        act_desc.triggered.connect(lambda: self.sort_by_column(col, False))
        menu.addAction(act_asc)
        menu.addAction(act_desc)
        menu.addSeparator()

        # Bu sütunu gizle
        act_hide = QAction(f"🙈 '{col_name}' Gizle", self)
        act_hide.triggered.connect(
            lambda: self.table_view.setColumnHidden(col, True)
        )
        menu.addAction(act_hide)

        # Gizli sütunları göster
        hidden = [
            i for i in range(self.model.columnCount())
            if self.table_view.isColumnHidden(i)
        ]
        if hidden:
            menu.addSeparator()
            show_m = menu.addMenu("👁️ Gizlileri Göster")
            for hc in hidden:
                hn = self._get_col_name(hc)
                a = QAction(hn, self)
                a.triggered.connect(
                    lambda _, c=hc: self.table_view.setColumnHidden(c, False)
                )
                show_m.addAction(a)

        menu.addSeparator()

        # Tüm sütunları göster
        act_show_all = QAction("👁️ Tüm Sütunları Göster", self)
        act_show_all.triggered.connect(self._show_all_columns)
        menu.addAction(act_show_all)

        menu.addSeparator()
        act_save  = QAction("💾 Görünümü Kaydet", self)
        act_reset = QAction("↩️ Varsayılana Dön", self)
        act_save.triggered.connect(self._save_profile)
        act_reset.triggered.connect(self._reset_view)
        menu.addAction(act_save)
        menu.addAction(act_reset)

        menu.exec(
            self.table_view.horizontalHeader().mapToGlobal(pos)
        )

    # ─────────────────────────────────────────────
    # KOPYALAMA
    # ─────────────────────────────────────────────

    def _copy_row(self, row: int):
        """Satır verilerini panoya kopyala."""
        src_row = self.proxy_model.mapToSource(
            self.proxy_model.index(row, 0)
        ).row()
        cols = self.model.columnCount()
        data = "\t".join(
            self.model.item(src_row, c).text()
            if self.model.item(src_row, c) else ""
            for c in range(cols)
        )
        QApplication.clipboard().setText(data)

    def _copy_all(self):
        """Tüm görünür satırları Excel formatında panoya kopyala."""
        rows = self.proxy_model.rowCount()
        cols = self.model.columnCount()

        # Başlıklar
        headers = "\t".join(
            self.model.horizontalHeaderItem(c).text()
            if self.model.horizontalHeaderItem(c) else ""
            for c in range(cols)
            if not self.table_view.isColumnHidden(c)
        )

        # Satırlar
        lines = [headers]
        for r in range(rows):
            src_row = self.proxy_model.mapToSource(
                self.proxy_model.index(r, 0)
            ).row()
            row_data = "\t".join(
                self.model.item(src_row, c).text()
                if self.model.item(src_row, c) else ""
                for c in range(cols)
                if not self.table_view.isColumnHidden(c)
            )
            lines.append(row_data)

        QApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(
            self, "Kopyalandı",
            f"{rows} satır panoya kopyalandı (Excel'e yapıştırabilirsiniz)."
        )

    # ─────────────────────────────────────────────
    # PROFİL — GÖRÜNÜM KAYDET/YÜKLE
    # ─────────────────────────────────────────────

    def _save_profile(self):
        """Sütun genişlikleri ve gizliliğini JSON'a kaydet."""
        profile = {}
        hh = self.table_view.horizontalHeader()
        for c in range(self.model.columnCount()):
            profile[str(c)] = {
                "width":    self.table_view.columnWidth(c),
                "hidden":   self.table_view.isColumnHidden(c),
                "visual":   hh.visualIndex(c),
            }
        path = self._profile_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        QMessageBox.information(
            self, "Kaydedildi", "Sütun görünümü kaydedildi."
        )

    def _load_profile(self):
        """Kaydedilmiş profili yükle."""
        try:
            with open(self._profile_path(), encoding="utf-8") as f:
                profile = json.load(f)
            for c_str, info in profile.items():
                c = int(c_str)
                if 0 <= c < self.model.columnCount():
                    w = info.get("width", 100)
                    if w > 10:
                        self.table_view.setColumnWidth(c, w)
                    self.table_view.setColumnHidden(c, info.get("hidden", False))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Profil yüklenemedi: {e}")

    def _reset_view(self):
        """Görünümü varsayılana döndür."""
        for c in range(self.model.columnCount()):
            self.table_view.setColumnHidden(c, False)
            self.table_view.setColumnWidth(c, 100)
        self.proxy_model.sort(-1, Qt.SortOrder.AscendingOrder)
        self._sort_col = -1
        self._sort_asc = True

    def _show_all_columns(self):
        """Tüm gizli sütunları göster."""
        for c in range(self.model.columnCount()):
            self.table_view.setColumnHidden(c, False)

    def _profile_path(self) -> str:
        return os.path.join(
            os.path.expanduser("~"),
            ".toya_erp", "profiles",
            f"table_{self.profile_key}.json",
        )

    # ─────────────────────────────────────────────
    # YARDIMCI
    # ─────────────────────────────────────────────

    def _get_col_name(self, col: int) -> str:
        """Sütun başlığını döndür."""
        item = self.model.horizontalHeaderItem(col)
        return item.text() if item else str(col)

    def _get_selected_rows(self) -> list[int]:
        """Seçili kaynak satır indekslerini döndür."""
        proxy_rows = {
            idx.row()
            for idx in self.table_view.selectionModel().selectedRows()
        }
        return [
            self.proxy_model.mapToSource(
                self.proxy_model.index(r, 0)
            ).row()
            for r in proxy_rows
        ]

    def _on_double_clicked(self, index):
        src = self.proxy_model.mapToSource(index)
        self.row_double_clicked.emit(src.row())

    def _on_selection_changed(self):
        self.selection_changed.emit(self._get_selected_rows())

    # ─────────────────────────────────────────────
    # DIŞARIDAN ERİŞİM
    # ─────────────────────────────────────────────

    def set_data(self, rows: list[list[Any]], headers: list[str] | None = None):
        """
        Tablo verilerini toplu yükle.

        rows: [[satır1kol1, satır1kol2, ...], [satır2...], ...]
        """
        self.model.removeRows(0, self.model.rowCount())
        if headers:
            self.model.setHorizontalHeaderLabels(headers)

        for row_data in rows:
            items = []
            for val in row_data:
                item = QStandardItem(str(val) if val is not None else "")
                item.setEditable(False)
                items.append(item)
            self.model.appendRow(items)

    def clear_data(self):
        """Tüm satırları temizle."""
        self.model.removeRows(0, self.model.rowCount())

    def get_row_data(self, row: int) -> list[str]:
        """Kaynak satır verilerini döndür."""
        return [
            self.model.item(row, c).text()
            if self.model.item(row, c) else ""
            for c in range(self.model.columnCount())
        ]

    def get_selected_data(self) -> list[list[str]]:
        """Seçili satırların verilerini döndür."""
        return [self.get_row_data(r) for r in self._get_selected_rows()]

    def set_column_width(self, col: int, width: int):
        """Sütun genişliğini ayarla."""
        self.table_view.setColumnWidth(col, width)

    def set_stretch_column(self, col: int):
        """Belirtilen sütunu esnet."""
        self.table_view.horizontalHeader().setSectionResizeMode(
            col, QHeaderView.ResizeMode.Stretch
        )

    def set_fixed_column(self, col: int, width: int):
        """Sütunu sabit genişlikte yap."""
        self.table_view.horizontalHeader().setSectionResizeMode(
            col, QHeaderView.ResizeMode.Fixed
        )
        self.table_view.setColumnWidth(col, width)

    def hide_column(self, col: int):
        self.table_view.setColumnHidden(col, True)

    def show_column(self, col: int):
        self.table_view.setColumnHidden(col, False)

    def set_row_height(self, height: int):
        """Tüm satır yüksekliğini güncelle."""
        self._row_height = height
        self.table_view.verticalHeader().setDefaultSectionSize(height)

    def row_count(self) -> int:
        return self.proxy_model.rowCount()

    def source_row_count(self) -> int:
        return self.model.rowCount()

    def apply_view_profile(self, profile):
        """ProfileManager'dan gelen profili uygula."""
        if not profile or not hasattr(profile, "column_settings"):
            return
        cs = profile.column_settings
        if not cs or not cs.individual_columns:
            return
        for c_str, info in cs.individual_columns.items():
            try:
                c = int(c_str)
                if 0 <= c < self.model.columnCount():
                    if hasattr(info, "visible"):
                        self.table_view.setColumnHidden(c, not info.visible)
                    if hasattr(info, "width") and info.width and info.width > 10:
                        self.table_view.setColumnWidth(c, info.width)
            except Exception:
                pass

    def get_current_view_as_profile(self, name: str = "Varsayılan"):
        """Mevcut görünümü profil olarak döndür."""
        try:
            from src.desktop.models.profile_models import (
                ColumnSettings, IndividualColumn, ProfileData, ViewProfile,
            )
            indiv = {}
            for c in range(self.model.columnCount()):
                indiv[str(c)] = IndividualColumn(
                    visible=not self.table_view.isColumnHidden(c),
                    width=self.table_view.columnWidth(c),
                    order=self.table_view.horizontalHeader().visualIndex(c),
                )
            return ViewProfile(
                profile=ProfileData(name=name),
                column_settings=ColumnSettings(individual_columns=indiv),
            )
        except Exception as e:
            logger.warning(f"Profil dönüştürme hatası: {e}")
            return None

    def open_column_manager_dialog(self):
        """Sütun yönetim dialogunu aç."""
        from PyQt6.QtWidgets import QCheckBox, QDialog, QScrollArea

        dlg = QDialog(self)
        dlg.setWindowTitle("⚙️ Sütun Görünümü Yönet")
        dlg.setMinimumWidth(280)
        dlg.setStyleSheet(
            "QDialog { background:#f8fafc; font-family:'Segoe UI'; }"
        )

        lyt = QVBoxLayout(dlg)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("Görünür sütunları seçin:")
        lbl.setStyleSheet("font-weight:600; color:#1e3a8a;")
        lyt.addWidget(lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; }")
        inner = QWidget()
        inner_lyt = QVBoxLayout(inner)
        inner_lyt.setSpacing(4)

        checkboxes = []
        for c in range(self.model.columnCount()):
            name = self._get_col_name(c)
            chk = QCheckBox(name)
            chk.setChecked(not self.table_view.isColumnHidden(c))
            chk.setStyleSheet("font-size:11px;")
            inner_lyt.addWidget(chk)
            checkboxes.append((c, chk))

        scroll.setWidget(inner)
        lyt.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("✅ Uygula")
        btn_ok.setStyleSheet(
            "background:#2563eb; color:white; border:none; "
            "border-radius:4px; padding:5px 14px; font-weight:600;"
        )
        btn_cancel = QPushButton("İptal")
        btn_cancel.setStyleSheet(
            "background:#f1f5f9; color:#475569; border:1px solid #cbd5e1; "
            "border-radius:4px; padding:5px 14px;"
        )
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        lyt.addLayout(btn_row)

        if dlg.exec():
            for c, chk in checkboxes:
                self.table_view.setColumnHidden(c, not chk.isChecked())
