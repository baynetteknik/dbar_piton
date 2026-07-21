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
        from PyQt6.QtWidgets import QSizePolicy
        self.inputs_container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

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
        """Tablo başlığına sağ tıklandığında iki sütunlu, arama ve profil kayıt özellikli menüyü açar."""
        from PyQt6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMenu,
            QPushButton,
            QVBoxLayout,
            QWidget,
            QWidgetAction,
        )

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 6px;
            }
        """)

        # Ana widget ve dikey layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(8)

        # 1. Arama Kutusu
        self.menu_search_box = QLineEdit()
        self.menu_search_box.setPlaceholderText("Sütun ara...")
        self.menu_search_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                background-color: white;
                color: #0f172a;
            }
        """)
        self.menu_search_box.textChanged.connect(self.filter_column_checkboxes)
        main_layout.addWidget(self.menu_search_box)

        # 2. Checkbox'lar (Grid Layout)
        grid_widget = QWidget()
        grid_layout = QGridLayout(grid_widget)
        grid_layout.setContentsMargins(0, 4, 0, 4)
        grid_layout.setSpacing(6)

        header = self.table_view.horizontalHeader()
        cols = sorted(self.headers_dict.keys())
        self.menu_checkboxes = {}

        num_cols = 2
        for i, col_idx in enumerate(cols):
            label, _ = self.headers_dict[col_idx]
            cb = QCheckBox(label)
            cb.setChecked(not header.isSectionHidden(col_idx))
            cb.setStyleSheet("""
                QCheckBox {
                    font-size: 11px;
                    color: #334155;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                }
            """)
            cb.toggled.connect(
                lambda checked, idx=col_idx: self.toggle_column_visibility(idx, checked),
            )
            self.menu_checkboxes[col_idx] = cb

            row = i // num_cols
            col = i % num_cols
            grid_layout.addWidget(cb, row, col)

        main_layout.addWidget(grid_widget)

        # Ayırıcı çizgi
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #e2e8f0;")
        main_layout.addWidget(line)

        # 3. Görünüm Profilleri Bölümü
        profile_title = QLabel("Görünüm Profilleri")
        profile_title.setStyleSheet("font-weight: bold; font-size: 10px; color: #64748b;")
        main_layout.addWidget(profile_title)

        # Profil Seçme ve Silme Satırı
        prof_select_lyt = QHBoxLayout()
        prof_select_lyt.setSpacing(4)

        self.menu_profile_combo = QComboBox()
        self.menu_profile_combo.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        self.menu_profile_combo.addItem("Varsayılan")
        
        # Kayıtlı profilleri yükle
        profiles = self.load_column_profile_list()
        for p in profiles:
            self.menu_profile_combo.addItem(p)
            
        # Combo değiştiğinde profili yükle ve menüyü kapat
        self.menu_profile_combo.currentTextChanged.connect(
            lambda name, m=menu: self.on_profile_selected(name, m),
        )
        prof_select_lyt.addWidget(self.menu_profile_combo, 1)

        btn_delete_prof = QPushButton("🗑️")
        btn_delete_prof.setToolTip("Profili Sil")
        btn_delete_prof.setFixedSize(22, 22)
        btn_delete_prof.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                border: 1px solid #fca5a5;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #fca5a5; }
        """)
        btn_delete_prof.clicked.connect(
            lambda checked, combo=self.menu_profile_combo, m=menu: self.on_delete_profile_clicked(combo, m),
        )
        prof_select_lyt.addWidget(btn_delete_prof)
        main_layout.addLayout(prof_select_lyt)

        # Profil Kaydetme Satırı
        prof_save_lyt = QHBoxLayout()
        prof_save_lyt.setSpacing(4)

        self.menu_profile_input = QLineEdit()
        self.menu_profile_input.setPlaceholderText("Yeni profil adı...")
        self.menu_profile_input.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        prof_save_lyt.addWidget(self.menu_profile_input, 1)

        btn_save_prof = QPushButton("💾")
        btn_save_prof.setToolTip("Profili Kaydet")
        btn_save_prof.setFixedSize(22, 22)
        btn_save_prof.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #bfdbfe; }
        """)
        btn_save_prof.clicked.connect(
            lambda checked, inp=self.menu_profile_input, combo=self.menu_profile_combo, m=menu: self.on_save_profile_clicked(inp, combo, m),
        )
        prof_save_lyt.addWidget(btn_save_prof)
        main_layout.addLayout(prof_save_lyt)

        action = QWidgetAction(menu)
        action.setDefaultWidget(main_widget)
        menu.addAction(action)

        menu.exec(self.table_view.horizontalHeader().mapToGlobal(pos))

    def toggle_column_visibility(self, col_idx, visible):
        self.set_column_hidden(col_idx, not visible)

    def filter_column_checkboxes(self, text):
        """Arama kutusuna yazılan metne göre checkbox'ları filtreler."""
        text = text.lower()
        for _col_idx, cb in self.menu_checkboxes.items():
            if text in cb.text().lower():
                cb.show()
            else:
                cb.hide()

    def on_profile_selected(self, name, menu):
        """Profil seçildiğinde tabloya uygular ve menüyü kapatır."""
        if not menu.isVisible():
            return
        self.load_profile(name)
        menu.close()

    def on_save_profile_clicked(self, name_input, combo, menu):
        """Mevcut görünümü yeni isimle kaydeder ve menüyü kapatır."""
        name = name_input.text().strip()
        if not name or name == "Varsayılan":
            return
        self.save_column_profile(name)
        name_input.clear()
        menu.close()

    def on_delete_profile_clicked(self, combo, menu):
        """Seçili profili siler ve menüyü kapatır."""
        name = combo.currentText()
        if not name or name == "Varsayılan":
            return
        self.delete_column_profile(name)
        menu.close()

    def save_column_profile(self, name):
        """Sütun durumlarını QSettings ile JSON olarak saklar."""
        import json

        from PyQt6.QtCore import QSettings
        settings = QSettings("baynetteknik", "dbar_piton")
        
        header = self.table_view.horizontalHeader()
        state = {}
        for col_idx in self.headers_dict.keys():
            state[str(col_idx)] = not header.isSectionHidden(col_idx)

        profiles_json = settings.value("column_profiles", "{}", type=str)
        try:
            profiles = json.loads(profiles_json)
        except Exception:
            profiles = {}

        profiles[name] = state
        settings.setValue("column_profiles", json.dumps(profiles))
        settings.sync()

    def delete_column_profile(self, name):
        """Belirtilen profili QSettings'ten siler."""
        import json

        from PyQt6.QtCore import QSettings
        settings = QSettings("baynetteknik", "dbar_piton")
        
        profiles_json = settings.value("column_profiles", "{}", type=str)
        try:
            profiles = json.loads(profiles_json)
        except Exception:
            profiles = {}

        if name in profiles:
            del profiles[name]
            settings.setValue("column_profiles", json.dumps(profiles))
            settings.sync()

    def load_column_profile_list(self) -> list[str]:
        """Kayıtlı profillerin isimlerini döner."""
        import json

        from PyQt6.QtCore import QSettings
        settings = QSettings("baynetteknik", "dbar_piton")
        
        profiles_json = settings.value("column_profiles", "{}", type=str)
        try:
            profiles = json.loads(profiles_json)
            return list(profiles.keys())
        except Exception:
            return []

    def load_profile(self, name):
        """Belirtilen görünüm profilini tabloya yükler."""
        if not name or name == "Varsayılan":
            for col_idx in self.headers_dict.keys():
                self.set_column_hidden(col_idx, False)
            return

        import json

        from PyQt6.QtCore import QSettings
        settings = QSettings("baynetteknik", "dbar_piton")
        
        profiles_json = settings.value("column_profiles", "{}", type=str)
        try:
            profiles = json.loads(profiles_json)
            state = profiles.get(name)
            if state:
                for col_str, visible in state.items():
                    col_idx = int(col_str)
                    self.set_column_hidden(col_idx, not visible)
        except Exception as e:
            logger.error(f"Profile loading error: {e}")
