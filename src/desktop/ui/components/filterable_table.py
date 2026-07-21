import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class FilterableTableView(QWidget):
    """Header-Filter-Row yapısına ve scroll/width senkronizasyonuna sahip dinamik tablo."""

    filter_changed = pyqtSignal(dict)  # Aktif filtre sözlüğünü yayar
    column_visibility_changed = pyqtSignal(int, bool)  # Sütun göster/gizle durumunu yayar (col_idx, visible)

    def __init__(self, headers_dict, parent=None):
        super().__init__(parent)
        self.headers_dict = headers_dict  # {col_idx: (label, field_name)}
        self.filters = {}
        self.filter_widgets = {}

        self.setObjectName("FilterableTableContainer")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Filtre Çubuğu Paneli (Senkronize Scroll & Width barındıracak)
        self.filter_bar_container = QWidget()
        self.filter_bar_container.setObjectName("FilterBarContainer")
        self.filter_bar_container.setFixedHeight(30)

        filter_bar_layout = QHBoxLayout(self.filter_bar_container)
        filter_bar_layout.setContentsMargins(0, 0, 0, 0)
        filter_bar_layout.setSpacing(0)

        # Global Reset (Sol Üst Çöp Kutusu)
        self.reset_btn = QPushButton("🗑️")
        self.reset_btn.setObjectName("FilterResetBtn")
        self.reset_btn.setFixedSize(30, 30)
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setToolTip("Tüm Filtreleri Temizle")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 0px;
                font-size: 11px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #fee2e2;
                border-color: #fca5a5;
            }
        """)
        self.reset_btn.clicked.connect(self.clear_all_filters)

        # Kaydırılabilir Filtre Giriş Kutuları Konteyneri
        self.inputs_container = QWidget()
        self.inputs_container.setObjectName("FilterInputsContainer")

        self.inputs_layout = QHBoxLayout(self.inputs_container)
        self.inputs_layout.setContentsMargins(0, 0, 0, 0)
        self.inputs_layout.setSpacing(0)

        # Her kolon için bir filtre kutusu (QLineEdit) oluştur
        for col_idx in sorted(self.headers_dict.keys()):
            label, field_name = self.headers_dict[col_idx]
            le = QLineEdit()
            le.setObjectName(f"FilterInput_{field_name}")
            le.setPlaceholderText(f"{label}...")
            le.setMinimumWidth(10)
            le.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #cbd5e1;
                    border-radius: 0px;
                    padding: 2px 6px;
                    font-size: 11px;
                    background-color: #ffffff;
                    color: #0f172a;
                }
                QLineEdit:focus {
                    border-color: #3b82f6;
                    background-color: #eff6ff;
                }
            """)
            # Hızlı filtre tetikleyicisi
            le.textChanged.connect(
                lambda text, col=field_name: self.on_filter_text_changed(col, text),
            )
            self.inputs_layout.addWidget(le)
            self.filter_widgets[col_idx] = le

        self.inputs_layout.addStretch()  # En sağda kalan boşluk için esneme
        filter_bar_layout.addWidget(self.inputs_container, 1)
        filter_bar_layout.addWidget(self.reset_btn)

        layout.addWidget(self.filter_bar_container)

        # 2. Asıl QTableView
        self.table_view = QTableView()
        self.table_view.setObjectName("MainTableView")
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)
        layout.addWidget(self.table_view, 1)

        # Sütun genişlikleri ve kaydırma senkronizasyonu
        self.table_view.horizontalHeader().sectionResized.connect(
            self.sync_filter_widths,
        )
        self.table_view.horizontalScrollBar().valueChanged.connect(
            self.sync_filter_scroll,
        )

    def sync_filter_widths(self):
        """Tablo sütun genişliği değiştiğinde filtre kutularının genişliğini senkronize eder."""
        header = self.table_view.horizontalHeader()
        for col_idx, le in self.filter_widgets.items():
            if header.isSectionHidden(col_idx):
                le.hide()
            else:
                le.show()
                col_width = header.sectionSize(col_idx)
                le.setFixedWidth(col_width)
        # Scroll senkronizasyonunu da tetikle
        self.sync_filter_scroll(self.table_view.horizontalScrollBar().value())

    def sync_filter_scroll(self, val):
        """Yatay kaydırma yapıldığında filtre giriş kutularını da sola kaydırır."""
        self.inputs_layout.setContentsMargins(-val, 0, 0, 0)

    def on_filter_text_changed(self, field_name, text):
        """Filtre girdilerinde değişim olduğunda veritabanını tetikler."""
        self.filters[field_name] = text
        self.filter_changed.emit(self.filters)

    def clear_all_filters(self):
        """Çöp kutusuna basıldığında tüm filtreleri temizler."""
        self.filters.clear()
        for le in self.filter_widgets.values():
            le.blockSignals(True)
            le.clear()
            le.blockSignals(False)
        self.filter_changed.emit(self.filters)

    def set_column_hidden(self, col_idx, hidden):
        """Sağ paneldeki Kolon Yönetimi checkbox'larına göre sütunları gizler."""
        self.table_view.horizontalHeader().setSectionHidden(col_idx, hidden)
        self.sync_filter_widths()
        self.column_visibility_changed.emit(col_idx, not hidden)

    def show_header_context_menu(self, pos):
        """Tablo başlığına sağ tıklandığında sütun göster/gizle menüsünü açar."""
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        header = self.table_view.horizontalHeader()

        for col_idx in sorted(self.headers_dict.keys()):
            label, _ = self.headers_dict[col_idx]
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(col_idx))
            
            # Action tetiklendiğinde sütun gizleme fonksiyonunu çağır
            action.triggered.connect(
                lambda checked, idx=col_idx: self.toggle_column_visibility(idx, checked),
            )
            menu.addAction(action)

        menu.exec(self.table_view.horizontalHeader().mapToGlobal(pos))

    def toggle_column_visibility(self, col_idx, visible):
        self.set_column_hidden(col_idx, not visible)
