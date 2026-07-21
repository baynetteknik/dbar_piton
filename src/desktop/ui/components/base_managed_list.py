import math

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.ui.components.filterable_table import FilterableTableView


class BaseManagedListWidget(QWidget):
    """Sütun profili desteği, QScrollArea filtre senkronizasyonu ve sayfalama barına sahip jenerik liste ekranı şablonu."""

    toast_requested = pyqtSignal(str, str)  # (message, level)

    def __init__(self, profile_key: str, headers_dict: dict, parent=None):
        super().__init__(parent)
        self.profile_key = profile_key
        self.headers_dict = headers_dict

        # Sayfalama durum değişkenleri
        self.current_page = 1
        self.per_page = 25
        self.total_records = 0

        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)

        # 1. Filtrelenebilir Tablo Bileşeni
        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key=self.profile_key,
            parent=self,
        )
        self.filterable_table.filter_changed.connect(self.on_filter_changed)
        self.main_layout.addWidget(self.filterable_table, 1)

        # 2. Sayfalama (Pagination) Barı
        self.init_pagination_bar()

    def init_pagination_bar(self):
        self.pagination_layout = QHBoxLayout()
        self.pagination_layout.setContentsMargins(0, 4, 0, 0)
        self.pagination_layout.setSpacing(6)

        self.btn_first_page = QPushButton("⏮️")
        self.btn_first_page.setToolTip(self.tr("İlk Sayfa"))
        self.btn_first_page.clicked.connect(self.go_to_first_page)

        self.btn_prev_page = QPushButton("⬅️")
        self.btn_prev_page.setToolTip(self.tr("Önceki Sayfa"))
        self.btn_prev_page.clicked.connect(self.go_to_prev_page)

        self.lbl_page_info = QLabel(self.tr("Sayfa 1 / 1"))
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #475569;")

        self.btn_next_page = QPushButton("➡️")
        self.btn_next_page.setToolTip(self.tr("Sonraki Sayfa"))
        self.btn_next_page.clicked.connect(self.go_to_next_page)

        self.btn_last_page = QPushButton("⏭️")
        self.btn_last_page.setToolTip(self.tr("Son Sayfa"))
        self.btn_last_page.clicked.connect(self.go_to_last_page)

        self.lbl_per_page = QLabel(self.tr("Sayfa Başına:"))
        self.lbl_per_page.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold;")

        self.combo_page_size = QComboBox()
        self.combo_page_size.setToolTip(self.tr("Sayfa başına gösterilecek kayıt sayısı"))
        self.combo_page_size.addItems(["25 kayıt", "50 kayıt", "100 kayıt", "250 kayıt"])
        self.combo_page_size.setMinimumWidth(110)
        self.combo_page_size.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                padding: 3px 6px;
                color: #334155;
                font-weight: 600;
                font-size: 11px;
            }
            QComboBox::drop-down { border: none; }
        """)
        self.combo_page_size.currentTextChanged.connect(self.on_page_size_combo_changed)

        btn_style = """
            QPushButton {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                padding: 4px 10px;
                color: #475569;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #f1f5f9; }
        """
        for btn in [self.btn_first_page, self.btn_prev_page, self.lbl_page_info, self.btn_next_page, self.btn_last_page]:
            if isinstance(btn, QPushButton):
                btn.setStyleSheet(btn_style)
            self.pagination_layout.addWidget(btn)

        self.pagination_layout.addStretch()
        self.pagination_layout.addWidget(self.lbl_per_page)
        self.pagination_layout.addWidget(self.combo_page_size)

        self.main_layout.addLayout(self.pagination_layout)

    def on_filter_changed(self, filters):
        self.current_page = 1
        self.refresh_data()

    def on_page_size_combo_changed(self, text):
        try:
            val = int(text.split()[0])
            self.per_page = val
            self.current_page = 1
            self.refresh_data()
        except Exception:
            pass

    def go_to_first_page(self):
        self.current_page = 1
        self.refresh_data()

    def go_to_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_data()

    def go_to_next_page(self):
        total_pages = max(1, math.ceil(self.total_records / self.per_page))
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_data()

    def go_to_last_page(self):
        total_pages = max(1, math.ceil(self.total_records / self.per_page))
        self.current_page = total_pages
        self.refresh_data()

    def update_pagination_controls(self):
        total_pages = max(1, math.ceil(self.total_records / self.per_page))
        self.lbl_page_info.setText(
            f"{self.tr('Sayfa')} {self.current_page} / {total_pages} ({self.tr('Toplam')} {self.total_records} {self.tr('Kayıt')})",
        )
        self.btn_first_page.setEnabled(self.current_page > 1)
        self.btn_prev_page.setEnabled(self.current_page > 1)
        self.btn_next_page.setEnabled(self.current_page < total_pages)
        self.btn_last_page.setEnabled(self.current_page < total_pages)

    def refresh_data(self):
        """Alt sınıflar veritabanından veri yüklemek için bu metodu ezmelidir (override)."""
        pass
