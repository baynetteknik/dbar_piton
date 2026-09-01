"""
TOYA ERP - Modüler Temel Liste Ekranı (BaseListScreen)
Tüm ERP liste ekranlarının ana çatı sınıfıdır.
Screen Registry'den aldığı şemaya göre Header, Sol Panel, Grid, Sağ Panel ve Footer'ı
otomatik olarak birleştirir ve yetkileri denetler.
"""

from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QFrame
)
from PyQt6.QtCore import Qt

from src.desktop.managers.theme_manager import ThemeManager
from src.desktop.managers.permission_manager import PermissionManager
from src.desktop.core.screen_registry import get_screen_definition
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.components.sidebars import SIDEBAR_COMPONENTS


class BaseListScreen(QWidget):
    def __init__(self, screen_id: str, parent=None):
        super().__init__(parent)
        
        self.screen_id = screen_id
        self.schema = get_screen_definition(screen_id)
        self.theme = ThemeManager()
        self.perm_mgr = PermissionManager()
        
        self._action_buttons: Dict[str, QPushButton] = {}
        self.left_sidebar_widget: Optional[QWidget] = None
        self.right_sidebar_widget: Optional[QWidget] = None
        
        self._build_ui()
        self._apply_permissions()
        self._connect_signals()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. HEADER REGION (Başlık + Arama + Aksiyon Butonları)
        if self.schema.get("regions", {}).get("header", True):
            header_widget = self._create_header_region()
            main_layout.addWidget(header_widget)

        # 2. BODY CONTAINER (Sol Sidebar + AppGrid + Sağ Sidebar)
        body_container = QHBoxLayout()
        body_container.setSpacing(10)

        # Sol Sidebar
        if self.schema.get("regions", {}).get("left_sidebar", False):
            left_comp_id = self.schema.get("components", {}).get("left_sidebar")
            if left_comp_id in SIDEBAR_COMPONENTS:
                self.left_sidebar_widget = SIDEBAR_COMPONENTS[left_comp_id]()
                body_container.addWidget(self.left_sidebar_widget)

        # Ana Gövde: Değişmez Kuralımız -> AppGrid
        grid_preset = self.schema.get("grid_preset", "dbgrid_search")
        custom_row_height = self.schema.get("custom_row_height")
        custom_header_height = self.schema.get("custom_header_height")
        self.grid = AppGrid(
            preset=grid_preset, 
            custom_row_height=custom_row_height,
            custom_header_height=custom_header_height
        )
        body_container.addWidget(self.grid, 1) # Ağırlık 1 (Genişleyen alan)

        # Sağ Sidebar
        if self.schema.get("regions", {}).get("right_sidebar", False):
            right_comp_id = self.schema.get("components", {}).get("right_sidebar")
            if right_comp_id in SIDEBAR_COMPONENTS:
                self.right_sidebar_widget = SIDEBAR_COMPONENTS[right_comp_id]()
                body_container.addWidget(self.right_sidebar_widget)

        main_layout.addLayout(body_container, 1)

        # 3. FOOTER REGION (Toplam Kayıt Sayısı + Bilgi Çubuğu)
        if self.schema.get("regions", {}).get("footer", True):
            footer_widget = self._create_footer_region()
            main_layout.addWidget(footer_widget)

    def _create_header_region(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.setSpacing(8)

        # Ekran Başlığı
        lbl_title = QLabel(self.schema.get("title", "ERP Listesi"))
        lbl_title.setStyleSheet("font-size: 13pt; font-weight: bold; color: #0f172a; border: none;")
        h_layout.addWidget(lbl_title)

        h_layout.addSpacing(15)

        # Hızlı Tablo Arama Kutusu
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Tabloda anlık ara...")
        self.txt_search.setFixedWidth(220)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                padding: 5px 8px;
                border: 1px solid #94a3b8;
                border-radius: 4px;
                background: white;
            }
        """)
        h_layout.addWidget(self.txt_search)

        h_layout.addStretch()

        # Şemadaki Butonları Otomatik Oluştur
        for action in self.schema.get("actions", []):
            btn = QPushButton(action["label"])
            btn.setProperty("action_id", action["id"])
            btn.setProperty("permission", action.get("permission", ""))
            
            # Variant stilleri
            variant = action.get("variant", "default")
            if variant == "primary":
                btn.setStyleSheet("background: #2563eb; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
            elif variant == "danger":
                btn.setStyleSheet("background: #ef4444; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
            elif variant == "warning":
                btn.setStyleSheet("background: #f59e0b; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
            else:
                btn.setStyleSheet("background: #e2e8f0; color: #1e293b; padding: 6px 12px; border-radius: 4px; border: 1px solid #cbd5e1;")

            btn.clicked.connect(lambda checked, act_id=action["id"]: self.on_action_triggered(act_id))
            self._action_buttons[action["id"]] = btn
            h_layout.addWidget(btn)

        return header

    def _create_footer_region(self) -> QWidget:
        footer = QFrame()
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(4, 2, 4, 2)

        self.lbl_record_count = QLabel("Toplam: 0 Kayıt")
        self.lbl_record_count.setStyleSheet("color: #64748b; font-weight: 500;")
        f_layout.addWidget(self.lbl_record_count)

        f_layout.addStretch()

        self.lbl_status_msg = QLabel("Hazır")
        self.lbl_status_msg.setStyleSheet("color: #64748b; font-style: italic;")
        f_layout.addWidget(self.lbl_status_msg)

        return footer

    def _apply_permissions(self):
        """Kullanıcının aktif rolüne göre butonların görünürlüğünü uygular."""
        for action_id, btn in self._action_buttons.items():
            perm_key = btn.property("permission")
            has_perm = self.perm_mgr.has_permission(perm_key)
            btn.setVisible(has_perm)

    def _connect_signals(self):
        # Yetki değiştiğinde butonları yeniden filtrele
        self.perm_mgr.role_changed.connect(lambda: self._apply_permissions())
        
        # Grid satır çift tıklama
        self.grid.row_double_clicked.connect(self.on_row_double_clicked)
        
        # Grid satır seçimi değiştiğinde sağ paneli güncelle
        self.grid.itemSelectionChanged.connect(self._on_grid_selection_changed)

        # Sol panel filtre değiştiğinde
        if self.left_sidebar_widget and hasattr(self.left_sidebar_widget, "filter_changed"):
            self.left_sidebar_widget.filter_changed.connect(self.on_filter_changed)

        # Anlık arama
        self.txt_search.textChanged.connect(self._filter_grid_text)

    def _filter_grid_text(self, text: str):
        """Grid üzerinde anlık metin araması yapar."""
        text = text.lower().strip()
        for row in range(self.grid.rowCount()):
            row_visible = False
            for col in range(self.grid.columnCount()):
                item = self.grid.item(row, col)
                if item and text in item.text().lower():
                    row_visible = True
                    break
            self.grid.setRowHidden(row, not row_visible)

    def _on_grid_selection_changed(self):
        selected_rows = self.grid.selectionModel().selectedRows()
        if selected_rows and self.right_sidebar_widget and hasattr(self.right_sidebar_widget, "update_summary"):
            row_idx = selected_rows[0].row()
            if 0 <= row_idx < len(self.grid._raw_data):
                cols = self.grid.preset_config["columns"]
                row_vals = self.grid._raw_data[row_idx]
                row_dict = {cols[i]: row_vals[i] for i in range(min(len(cols), len(row_vals)))}
                self.right_sidebar_widget.update_summary(row_dict)
                self.on_row_selected(row_dict)

    # GELİŞTİRİCİNİN VEYA ALT SINIFLARIN OVERRIDE EDECEĞİ KANALLAR
    def on_action_triggered(self, action_id: str):
        print(f"[{self.screen_id}] Buton tetiklendi: {action_id}")

    def on_filter_changed(self, filters: dict):
        print(f"[{self.screen_id}] Filtre değişti: {filters}")

    def on_row_selected(self, row_dict: dict):
        pass

    def on_row_double_clicked(self, row_idx: int, row_dict: dict):
        print(f"[{self.screen_id}] Satır çift tıklandı: {row_dict}")

    def set_data(self, rows: list):
        """Veriyi grid'e basar ve footer sayısını günceller."""
        self.grid.setData(rows)
        self.lbl_record_count.setText(f"Toplam: {len(rows)} Kayıt")
