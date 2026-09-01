"""
TOYA ERP - Modüler Sol Sidebar Bileşeni: leftsidebar001
Filtreleme ağacı, durum seçimi ve grup filtreleme panelidir.
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QTreeWidget, 
    QTreeWidgetItem, QRadioButton, QButtonGroup, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.desktop.managers.theme_manager import ThemeManager


class FilterTreeSidebar001(QFrame):
    filter_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar_frame")
        self.theme = ThemeManager()
        self.setFixedWidth(210)
        
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Başlık
        title_label = QLabel("FİLTRE & GRUPLAR")
        title_label.setObjectName("sidebar_title")
        layout.addWidget(title_label)

        # Hızlı Grup Arama
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Grup ara...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 4px 8px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background: white;
            }
        """)
        layout.addWidget(self.search_input)

        # Kategori Ağacı
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #e2e8f0;
                background: white;
                border-radius: 4px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
        """)
        
        # Standart ERP Grupları
        root_all = QTreeWidgetItem(self.tree, ["Tüm Kayıtlar"])
        root_all.setSelected(True)
        
        grp_musteri = QTreeWidgetItem(root_all, ["Müşteriler"])
        QTreeWidgetItem(grp_musteri, ["Toptan Müşteriler"])
        QTreeWidgetItem(grp_musteri, ["Perakende Müşteriler"])
        
        grp_tedarikci = QTreeWidgetItem(root_all, ["Tedarikçiler"])
        QTreeWidgetItem(grp_tedarikci, ["Hammadde Tedarik"])
        QTreeWidgetItem(grp_tedarikci, ["Hizmet Tedarik"])
        
        QTreeWidgetItem(root_all, ["Personel"])
        QTreeWidgetItem(root_all, ["Bayiler"])
        
        self.tree.expandAll()
        layout.addWidget(self.tree)

        # Durum Filtresi
        status_label = QLabel("Kayıt Durumu")
        status_label.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(status_label)

        self.btn_group = QButtonGroup(self)
        self.rb_all = QRadioButton("Tümü")
        self.rb_active = QRadioButton("Sadece Aktifler")
        self.rb_passive = QRadioButton("Sadece Pasifler")
        self.rb_active.setChecked(True)

        self.btn_group.addButton(self.rb_all, 0)
        self.btn_group.addButton(self.rb_active, 1)
        self.btn_group.addButton(self.rb_passive, 2)

        layout.addWidget(self.rb_active)
        layout.addWidget(self.rb_passive)
        layout.addWidget(self.rb_all)

        # Stil uygulama
        self.setStyleSheet(self.theme.get_sidebar_stylesheet())

    def _connect_signals(self):
        self.tree.itemSelectionChanged.connect(self._emit_filters)
        self.btn_group.buttonClicked.connect(self._emit_filters)
        self.theme.theme_changed.connect(lambda: self.setStyleSheet(self.theme.get_sidebar_stylesheet()))

    def _emit_filters(self):
        selected_items = self.tree.selectedItems()
        group_name = selected_items[0].text(0) if selected_items else "Tüm Kayıtlar"
        
        status_id = self.btn_group.checkedId()
        status_map = {0: "ALL", 1: "ACTIVE", 2: "PASSIVE"}
        
        self.filter_changed.emit({
            "group": group_name,
            "status": status_map.get(status_id, "ACTIVE")
        })
