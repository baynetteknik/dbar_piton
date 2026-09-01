import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.models.profile_models import IndividualColumn, ViewProfile
from src.desktop.ui.components.profile_style_delegate import ProfileStyleDelegate
from src.desktop.ui.components.view_profile_bar import ViewProfileBar

logger = logging.getLogger(__name__)


class FilterableTableView(QWidget):
    """Header-Filter-Row yapısına ve scroll/width senkronizasyonuna sahip dinamik tablo."""

    filter_changed = pyqtSignal(dict)  # Aktif filtre sözlüğünü yayar
    column_visibility_changed = pyqtSignal(int, bool)  # Sütun göster/gizle durumunu yayar (col_idx, visible)

    MANDATORY_COLUMNS = set()  # Kullanıcı istediği sütunu (ID dahil) gizleyebilmeli

    def __init__(
        self,
        headers_dict,
        profile_key="customers",
        enable_profile_bar=False,
        parent=None,
    ):
        super().__init__(parent)
        self.headers_dict = headers_dict  # {col_idx: (label, field_name)}
        self.profile_key = profile_key
        self.enable_profile_bar = enable_profile_bar
        self.filters = {}
        self.filter_widgets = {}

        self.setObjectName("FilterableTableContainer")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 0. Görünüm Profili Araç Çubuğu (ViewProfileBar)
        if self.enable_profile_bar:
            self.profile_bar = ViewProfileBar(
                profile_key=self.profile_key, table_view=self, parent=self,
            )
            layout.addWidget(self.profile_bar)

        # 1. Filtre Çubuğu Paneli (Doğrudan Viewport Piksel Senkronlu Konteyner)
        self.filter_bar_container = QWidget()
        self.filter_bar_container.setObjectName("FilterBarContainer")
        self.filter_bar_container.setFixedHeight(28)
        self.filter_bar_container.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-bottom: none;")

        # Kompakt Filtre Sıfırlama Butonu (Çöp Kutusu)
        self.reset_btn = QPushButton("🗑️", self.filter_bar_container)
        self.reset_btn.setObjectName("act.rst.001")
        self.reset_btn.setToolTip("[act.rst.001] " + self.tr("Tüm Kolon Filtrelerini Sıfırla (Temizle)"))
        self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #dc2626;
                border: 1px solid #fca5a5;
                border-radius: 0px;
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #fecaca;
                color: #991b1b;
            }
            QPushButton:pressed {
                background-color: #f87171;
                color: #ffffff;
            }
        """)
        self.reset_btn.clicked.connect(self.clear_all_filters)

        # Her kolon için bir filtre kutusu (veya Seçim kolonu için Çöp Kutusu) oluştur
        has_select_col = any(f.lower() in ("select", "sec", "seç", "chk", "check", "action", "actions") for _, f in self.headers_dict.values())
        
        for col_idx in sorted(self.headers_dict.keys()):
            label, field_name = self.headers_dict[col_idx]
            if (col_idx == 0 and has_select_col) or field_name.lower() in ("select", "sec", "seç", "chk", "check", "action", "actions"):
                self.filter_widgets[col_idx] = self.reset_btn
            else:
                le = QLineEdit(self.filter_bar_container)
                le.setObjectName(f"FilterInput_{field_name}")
                le.setPlaceholderText(f"{label}...")
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
                le.textChanged.connect(
                    lambda text, col=field_name: self.on_filter_text_changed(col, text),
                )
                self.filter_widgets[col_idx] = le

        layout.addWidget(self.filter_bar_container)

        # 3. Asıl QTableView
        self.table_view = QTableView()
        self.table_view.setObjectName("MainTableView")
        self.table_view.setSortingEnabled(True)  # ARTAN / AZALAN SIRALAMA AKTİF
        
        hheader = self.table_view.horizontalHeader()
        hheader.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hheader.customContextMenuRequested.connect(self.show_header_context_menu)
        hheader.setSortIndicatorShown(True)
        hheader.setSectionsClickable(True)
        hheader.setFixedHeight(26)  # Başlık yüksekliği sabit 26px
        
        # Sütun ayırıcı çizgileri ve hover efektini QHeaderView stili ile uygulayalım
        hheader.setStyleSheet("""
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                padding: 2px 6px;
                border: none;
                border-right: 2px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                font-weight: bold;
                font-size: 10px;
                min-height: 22px;
                max-height: 26px;
            }
            QHeaderView::section:last {
                border-right: none;
            }
            QHeaderView::section:hover {
                background-color: #e2e8f0;
            }
        """)
        # Satır yüksekliği
        try:
            from src.desktop.managers.theme_manager import ThemeManager
            row_h = ThemeManager().row_height
        except Exception:
            row_h = 26
        self.table_view.verticalHeader().setDefaultSectionSize(row_h)
        self.table_view.verticalHeader().setMinimumSectionSize(row_h)

        layout.addWidget(self.table_view, 1)

        # Style delegate for visual rules
        self.style_delegate = ProfileStyleDelegate(self.table_view)
        self.table_view.setItemDelegate(self.style_delegate)

        # Sütun genişlikleri, kaydırma ve yer değiştirme senkronizasyonu
        hheader.sectionResized.connect(self.sync_filter_widths)
        hheader.sectionMoved.connect(self.sync_filter_widths)
        hheader.geometriesChanged.connect(self.sync_filter_widths)
        self.table_view.horizontalScrollBar().valueChanged.connect(self.sync_filter_widths)
        self.table_view.horizontalScrollBar().rangeChanged.connect(lambda *_: self.sync_filter_widths())

        # En son kullanılan aktif profili otomatik yükle
        from PyQt6.QtCore import QTimer
        pm = ProfileManager(profile_key=self.profile_key)
        QTimer.singleShot(0, lambda: self.apply_view_profile(pm.get_active_profile()))

    def sync_filter_widths(self, *args):
        """Tablo yatay kaydırıldığında veya sütunlar yeniden boyutlandırıldığında filtre kutularını pikseli pikseline hizalar."""
        header = self.table_view.horizontalHeader()
        if not header or header.count() == 0:
            return
        for col_idx in sorted(self.headers_dict.keys()):
            if col_idx >= header.count():
                continue
            le = self.filter_widgets.get(col_idx)
            if not le:
                continue
            if header.isSectionHidden(col_idx):
                le.hide()
            else:
                x = header.sectionViewportPosition(col_idx)
                w = header.sectionSize(col_idx)
                le.setGeometry(x, 0, w, 28)
                le.show()

    def sync_filter_scroll(self, val):
        self.sync_filter_widths()

    def sync_filter_positions(self, *args):
        self.sync_filter_widths()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_filter_widths()

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self.sync_filter_widths)

    @property
    def inputs_layout(self):
        """Geriye dönük test uyumluluğu için visualIndex sırasına göre filtre elemanlarını sunar."""
        class DummyLayout:
            def __init__(self, table):
                self.table = table

            def itemAt(self, visual_idx):  # noqa: N802
                header = self.table.table_view.horizontalHeader()
                logical_idx = header.logicalIndex(visual_idx)
                w = self.table.filter_widgets.get(logical_idx)

                class DummyItem:
                    def __init__(self, widget):
                        self._widget = widget

                    def widget(self):
                        return self._widget

                return DummyItem(w)

        return DummyLayout(self)

    def update_menu_checkboxes(self):
        """Menüdeki checkbox durumlarını tablonun anlık sütun görünürlük durumlarına göre eşitler."""
        if hasattr(self, 'menu_checkboxes') and self.menu_checkboxes:
            header = self.table_view.horizontalHeader()
            for col_idx, cb in self.menu_checkboxes.items():
                cb.blockSignals(True)
                cb.setChecked(not header.isSectionHidden(col_idx))
                cb.blockSignals(False)

    def on_filter_text_changed(self, field_name, text):
        """Filtre girdilerinde değişim olduğunda veritabanını tetikler."""
        self.filters[field_name] = text
        self.filter_changed.emit(self.filters)

    def clear_all_filters(self):
        """Çöp kutusuna basıldığında tüm filtreleri temizler."""
        self.filters.clear()
        for w in self.filter_widgets.values():
            if isinstance(w, QLineEdit):
                w.blockSignals(True)
                w.clear()
                w.blockSignals(False)
        self.filter_changed.emit(self.filters)

    def get_mandatory_columns(self) -> set[str]:
        """Returns mandatory column field names for this table."""
        table_fields = {field for _label, field in self.headers_dict.values()}
        mandatory = self.MANDATORY_COLUMNS.intersection(table_fields)
        if not mandatory and 0 in self.headers_dict:
            mandatory = {self.headers_dict[0][1]}
        return mandatory

    def set_column_hidden(self, col_idx, hidden):
        """Sağ paneldeki Kolon Yönetimi checkbox'larına göre sütunları gizler."""
        if hidden and col_idx in self.headers_dict:
            _label, field_name = self.headers_dict[col_idx]
            if field_name in self.get_mandatory_columns():
                logger.warning(f"Zorunlu sütun '{field_name}' gizlenemez.")
                return
        self.table_view.horizontalHeader().setSectionHidden(col_idx, hidden)
        self.sync_filter_widths()
        self.column_visibility_changed.emit(col_idx, not hidden)

    def set_profile_key(self, new_key: str):
        """Sets a new profile_key and applies the active profile."""
        self.profile_key = new_key
        if hasattr(self, "profile_bar") and self.profile_bar:
            self.profile_bar.set_profile_key(new_key)
        else:
            pm = ProfileManager(profile_key=self.profile_key)
            self.apply_view_profile(pm.get_active_profile())

    def apply_view_profile(self, profile: ViewProfile):
        """Applies a ViewProfile v2.0.0 instance to the table and style delegate."""
        if not profile or not hasattr(profile, "column_settings"):
            return
        header = self.table_view.horizontalHeader()
        if not header or header.count() == 0:
            return
        mandatory_cols = self.get_mandatory_columns()

        # 1. Apply column positions (orders)
        target_positions = []
        for col_idx, (_label, field_name) in self.headers_dict.items():
            if field_name in profile.column_settings.individual_columns:
                target_v_idx = profile.column_settings.individual_columns[field_name].order
            else:
                target_v_idx = col_idx
            target_positions.append((col_idx, target_v_idx))

        sorted_positions = sorted(target_positions, key=lambda x: x[1])
        for target_v_idx, (col_idx, _) in enumerate(sorted_positions):
            current_v_idx = header.visualIndex(col_idx)
            if current_v_idx != target_v_idx:
                header.moveSection(current_v_idx, target_v_idx)

        # 2. Apply column visibilities and widths
        for col_idx, (_label, field_name) in self.headers_dict.items():
            if field_name in mandatory_cols:
                self.set_column_hidden(col_idx, False)
            elif field_name in profile.column_settings.individual_columns:
                indiv = profile.column_settings.individual_columns[field_name]
                self.set_column_hidden(col_idx, not indiv.visible)
                if indiv.width > 0:
                    self.table_view.setColumnWidth(col_idx, indiv.width)
            else:
                self.set_column_hidden(col_idx, False)

        # 3. Apply Visual Rules to Delegate
        field_map = {idx: field for idx, (_lbl, field) in self.headers_dict.items()}
        self.style_delegate.set_rules(profile.visual_rules, field_map)
        self.table_view.viewport().update()

        self.update_menu_checkboxes()
        self.sync_filter_widths()
        self.sync_filter_positions()

    def capture_current_view_profile(self, profile_name: str) -> ViewProfile:
        """Captures current table column states into a ViewProfile v2.0.0 object."""
        header = self.table_view.horizontalHeader()
        indiv_cols = {}
        for col_idx, (_label, field_name) in self.headers_dict.items():
            vis = not header.isSectionHidden(col_idx)
            w = self.table_view.columnWidth(col_idx)
            v_idx = header.visualIndex(col_idx)
            indiv_cols[field_name] = IndividualColumn(visible=vis, width=w, order=v_idx)

        pm = ProfileManager(profile_key=self.profile_key)
        existing = pm.load_profiles().get(profile_name, pm.create_default_profile())
        existing.profile.name = profile_name
        existing.column_settings.individual_columns = indiv_cols
        return existing

    def open_column_manager_dialog(self):
        """Opens DIA column & view profile configuration menu."""
        header_view = self.table_view.horizontalHeader()
        pos = header_view.rect().center()
        self.show_header_context_menu(pos)

    def add_column_actions_to_menu(self, menu):
        """
        Sağ tık menüsüne sütun gizle/göster aksiyonları ekler.
        quotations.py ve diğer liste ekranları tarafından çağrılır.
        """
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu

        col_menu = menu.addMenu("👁️ Sütunlar")
        col_menu.setStyleSheet("""
            QMenu {
                background:#ffffff; border:1px solid #cbd5e1;
                font-size:10px; padding:2px;
            }
            QMenu::item { padding:4px 16px; }
            QMenu::item:selected { background:#2563eb; color:#ffffff; }
        """)

        header = self.table_view.horizontalHeader()
        for col_idx in sorted(self.headers_dict.keys()):
            label, _ = self.headers_dict[col_idx]
            is_visible = not header.isSectionHidden(col_idx)
            act = QAction(
                f"{'✅' if is_visible else '☐'} {label}", self
            )
            act.triggered.connect(
                lambda checked, c=col_idx, v=is_visible:
                self.set_column_hidden(c, v)
            )
            col_menu.addAction(act)

        col_menu.addSeparator()
        act_show_all = QAction("👁️ Tümünü Göster", self)
        act_show_all.triggered.connect(
            lambda: [
                self.set_column_hidden(c, False)
                for c in self.headers_dict.keys()
            ]
        )
        col_menu.addAction(act_show_all)

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
        main_widget.setMinimumWidth(300)
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

        # Kayıtlı profilleri yükle (En son aktif profil en üsttedir)
        profiles = self.load_column_profile_list()
        for p in profiles:
            if self.menu_profile_combo.findText(p) < 0:
                self.menu_profile_combo.addItem(p)

        pm = ProfileManager(profile_key=self.profile_key)
        active = pm.get_active_profile_name()
        idx = self.menu_profile_combo.findText(active)
        if idx >= 0:
            self.menu_profile_combo.blockSignals(True)
            self.menu_profile_combo.setCurrentIndex(idx)
            self.menu_profile_combo.blockSignals(False)

        # Combo değiştiğinde profili yükle ve menüyü kapat
        self.menu_profile_combo.currentTextChanged.connect(
            lambda name, m=menu: self.on_profile_selected(name, m),
        )
        prof_select_lyt.addWidget(self.menu_profile_combo, 1)

        btn_delete_prof = QPushButton("🗑️ Sil")
        btn_delete_prof.setToolTip("Profili Sil")
        btn_delete_prof.setFixedHeight(22)
        btn_delete_prof.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                border: 1px solid #fca5a5;
                border-radius: 4px;
                font-size: 11px;
                padding: 2px 4px;
            }
            QPushButton:hover { background-color: #fca5a5; }
        """)
        btn_delete_prof.clicked.connect(
            lambda checked, combo=self.menu_profile_combo, m=menu: self.on_delete_profile_clicked(combo, m),
        )
        prof_select_lyt.addWidget(btn_delete_prof)

        btn_manage_prof = QPushButton("⚙️ Yönet")
        btn_manage_prof.setToolTip("Görünüm Profillerini Yönet")
        btn_manage_prof.setFixedHeight(22)
        btn_manage_prof.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                font-size: 11px;
                padding: 2px 4px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        btn_manage_prof.clicked.connect(
            lambda checked, m=menu: self.on_manage_profiles_clicked(m),
        )
        prof_select_lyt.addWidget(btn_manage_prof)
        main_layout.addLayout(prof_select_lyt)

        # Profil Kaydetme Satırı
        prof_save_lyt = QHBoxLayout()
        prof_save_lyt.setSpacing(4)

        self.menu_profile_input = QLineEdit()
        if active != "Varsayılan":
            self.menu_profile_input.setText(active)
            self.menu_profile_input.setPlaceholderText(f"Mevcut '{active}' güncellenecek...")
        else:
            self.menu_profile_input.setPlaceholderText("Yeni profil adı...")
        self.menu_profile_input.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        prof_save_lyt.addWidget(self.menu_profile_input, 1)

        btn_save_prof = QPushButton("💾 Kaydet")
        btn_save_prof.setToolTip("Görünümü Kaydet / Güncelle")
        btn_save_prof.setFixedHeight(22)
        btn_save_prof.setStyleSheet("""
            QPushButton {
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 4px;
                font-size: 11px;
                padding: 2px 6px;
            }
            QPushButton:hover { background-color: #bfdbfe; }
        """)
        btn_save_prof.clicked.connect(
            lambda checked, inp=self.menu_profile_input, combo=self.menu_profile_combo, m=menu: self.on_save_profile_clicked(inp, combo, m),
        )
        prof_save_lyt.addWidget(btn_save_prof)
        main_layout.addLayout(prof_save_lyt)

        # 4. Otomatik Kapanmayı Engelleme / Menüyü Açık Tut Seçeneği
        from PyQt6.QtWidgets import QCheckBox
        self.menu_keep_open_cb = QCheckBox("📌 Menüyü Açık Tut")
        self.menu_keep_open_cb.setStyleSheet("font-size: 11px; font-weight: bold; color: #1e40af; padding-top: 4px;")
        
        from PyQt6.QtCore import QSettings
        settings = QSettings("baynetteknik", "dbar_piton")
        keep_open = settings.value("keep_profile_menu_open", False, type=bool)
        self.menu_keep_open_cb.setChecked(keep_open)
        self.menu_keep_open_cb.toggled.connect(
            lambda checked: settings.setValue("keep_profile_menu_open", checked),
        )
        main_layout.addWidget(self.menu_keep_open_cb)

        action = QWidgetAction(menu)
        action.setDefaultWidget(main_widget)
        menu.addAction(action)

        menu.exec(self.table_view.horizontalHeader().mapToGlobal(pos))

    def close_menu_if_needed(self, menu):
        """Eğer 'Menüyü Açık Tut' seçeneği işaretli değilse menüyü kapatır."""
        if hasattr(self, "menu_keep_open_cb") and self.menu_keep_open_cb.isChecked():
            return
        menu.close()

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
        """Profil seçildiğinde tabloya uygular ve istenirse menüyü kapatır."""
        if not menu.isVisible():
            return
        self.load_profile(name)
        self.close_menu_if_needed(menu)

    def on_save_profile_clicked(self, name_input, combo, menu):
        """Mevcut görünümü yeni isimle veya seçili profile kaydeder (günceller)."""
        name = name_input.text().strip()
        if not name:
            name = combo.currentText()

        if not name or name == "Varsayılan":
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(menu, self.tr("Uyarı"), self.tr("Lütfen kaydedilecek profil için bir isim girin veya listeden bir profil seçin."))
            return

        import json

        from PyQt6.QtCore import QSettings
        settings = QSettings("baynetteknik", "dbar_piton")
        profiles_json = settings.value(f"column_profiles_{self.profile_key}", "{}", type=str)
        try:
            profiles = json.loads(profiles_json)
            if name in profiles:
                from PyQt6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    menu,
                    self.tr("Profil Güncellensin mi?"),
                    self.tr(f"'{name}' isimli görünüm profili zaten mevcut.\nYaptığınız görünüm değişikliklerini '{name}' profilinin üzerine kaydetmek istediğinizden emin misiniz?"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
        except Exception:
            pass

        self.save_column_profile(name)
        name_input.clear()
        self.close_menu_if_needed(menu)

    def on_delete_profile_clicked(self, combo, menu):
        """Seçili profili siler ve menüyü kapatır."""
        name = combo.currentText()
        if not name or name == "Varsayılan":
            return
        self.delete_column_profile(name)
        self.close_menu_if_needed(menu)

    def save_column_profile(self, name):
        """Sütun durumlarını ProfileManager (v2.0.0) ile saklar."""
        pm = ProfileManager(profile_key=self.profile_key)
        profile = self.capture_current_view_profile(profile_name=name)
        pm.save_profile(profile)
        pm.set_active_profile_name(name)
        if hasattr(self, "profile_bar") and self.profile_bar:
            self.profile_bar.reload_profiles()

    def delete_column_profile(self, name):
        """Belirtilen profili ProfileManager'dan siler."""
        pm = ProfileManager(profile_key=self.profile_key)
        pm.delete_profile(name)
        if hasattr(self, "profile_bar") and self.profile_bar:
            self.profile_bar.reload_profiles()

    def load_column_profile_list(self) -> list[str]:
        """Kayıtlı profillerin isimlerini döner (En son aktif profil ilk sıradadır)."""
        pm = ProfileManager(profile_key=self.profile_key)
        profiles = pm.load_profiles()
        active_profile = pm.get_active_profile_name()
        p_list = list(profiles.keys())
        if active_profile in p_list:
            p_list.remove(active_profile)
            p_list.insert(0, active_profile)
        return p_list

    def load_profile(self, name):
        """Belirtilen görünüm profilini tabloya yükler."""
        pm = ProfileManager(profile_key=self.profile_key)
        pm.set_active_profile_name(name)
        profile = pm.get_active_profile()
        self.apply_view_profile(profile)
        if hasattr(self, "profile_bar") and self.profile_bar:
            self.profile_bar.reload_profiles()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self.sync_filter_widths()

    def on_manage_profiles_clicked(self, menu):
        """Profil yönetimi popup penceresini açar."""
        menu.close()
        pm = ProfileManager(profile_key=self.profile_key)
        from src.desktop.ui.dialogs.profile_manager_dialog import ProfileManagerDialog
        dlg = ProfileManagerDialog(profile_manager=pm, parent=self)
        dlg.exec()
        
        # En son aktif kalan profili tabloya uygula
        active = pm.get_active_profile_name()
        self.load_profile(active)





class ColumnProfileManagerDialog(QDialog):
    """Kayıtlı sütun görünümleri profillerinin listelendiği ve silindiği popup yönetim penceresi."""

    def __init__(self, parent=None, profile_key="customers"):
        super().__init__(parent)
        self.profile_key = profile_key
        self.setWindowTitle(self.tr("Görünüm Profillerini Yönet"))
        self.setFixedSize(320, 240)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl = QLabel(self.tr("Kayıtlı Profiller"))
        lbl.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
                color: #334155;
            }
            QListWidget::item {
                padding: 6px 10px;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #fee2e2;
                color: #b91c1c;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.btn_delete = QPushButton(self.tr("❌ Seçili Profili Sil"))
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                color: #b91c1c;
                border: 1px solid #fca5a5;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #fca5a5;
            }
        """)
        self.btn_delete.clicked.connect(self.delete_selected_profile)
        btn_layout.addWidget(self.btn_delete, 1)

        self.btn_close = QPushButton(self.tr("Kapat"))
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)
        self.load_profiles()

    def load_profiles(self):
        self.list_widget.clear()
        import json

        from PyQt6.QtCore import QSettings
        settings = QSettings("baynetteknik", "dbar_piton")
        profiles_json = settings.value(f"column_profiles_{self.profile_key}", "{}", type=str)
        try:
            profiles = json.loads(profiles_json)
            for p_name in profiles.keys():
                self.list_widget.addItem(p_name)
        except Exception:
            pass

    def delete_selected_profile(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Lütfen silmek istediğiniz profili seçin."))
            return

        name = item.text()
        import json

        from PyQt6.QtCore import QSettings
        settings = QSettings("baynetteknik", "dbar_piton")
        
        profiles_json = settings.value(f"column_profiles_{self.profile_key}", "{}", type=str)
        try:
            profiles = json.loads(profiles_json)
            if name in profiles:
                del profiles[name]
                settings.setValue(f"column_profiles_{self.profile_key}", json.dumps(profiles))
                
                active = settings.value(f"active_column_profile_{self.profile_key}", "Varsayılan", type=str)
                if active == name:
                    settings.setValue(f"active_column_profile_{self.profile_key}", "Varsayılan")
                
                settings.sync()
                self.load_profiles()
                QMessageBox.information(self, self.tr("Başarılı"), f"'{name}' profili başarıyla silindi.")
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), f"Profil silinirken hata: {e}")
