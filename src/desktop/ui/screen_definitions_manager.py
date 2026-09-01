"""
TOYA ERP - Ekran Şablonları ve Grid Yönetim Ekranı (ScreenDefinitionsManagerWidget)
Teklif Yönetimi (QuotationsWidget) ve DIA 3-Panel standartlarına %100 UYUMLU olarak tasarlanmıştır.
Sistem Varsayılan Şablonları (tpl_*), Özel Ekran Tanımları (scr_*), Fabrika Ayarlarına Sıfırlama,
FilterableTableView, Sütun Arama Filtreleri, Görünüm Profilleri (ProfileManager),
Başlık Satır Yüksekliği (Header Height), Veri Satır Yüksekliği (Row Height) ve
Mavi Zemin / Beyaz Yazı / Kırmızı Hover Sağ Tık Menüsü içerir.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QKeySequence,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.core.module_taxonomy import taxonomy_manager
from src.desktop.core.screen_registry import (
    SCREEN_DEFINITIONS,
    register_screen_definition,
    reset_to_factory_defaults,
)
from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.managers.theme_manager import ThemeManager
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.dialogs.screen_definition_dialog import ScreenDefinitionDetailDialog


class ScreenDefinitionsManagerWidget(QWidget):
    """Teklif Yönetimi ile birebir aynı mimari ve yetenekte Ekran & Grid Tanımları Modülü."""

    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile_key = "screen_definitions"
        self.theme = ThemeManager()
        self.profile_manager = ProfileManager(profile_key=self.profile_key)
        
        self.headers_dict = {
            0: (self.tr("Seç"), "select"),
            1: (self.tr("Kod"), "id"),
            2: (self.tr("Ekran Başlığı"), "title"),
            3: (self.tr("Şablon Türü"), "template_type"),
            4: (self.tr("Grid Preseti"), "grid_preset"),
            5: (self.tr("Başlık Yük."), "header_height"),
            6: (self.tr("Satır Yük."), "row_height"),
            7: (self.tr("Sol Panel"), "left_sidebar"),
            8: (self.tr("Sağ Panel"), "right_sidebar"),
            9: (self.tr("Eylem Sayısı"), "actions_count"),
            10: (self.tr("Durum"), "status"),
        }

        self.init_ui()
        self._setup_shortcuts()
        self.load_profiles()
        self.load_screen_definitions()

    def toolbar_btn_style(self, bg_color="#ffffff", text_color="#1e293b", border_color="#cbd5e1"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 700;
                text-align: left;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{ background-color: #f1f5f9; }}
        """

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        combo_style = """
            QComboBox, QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                color: #0f172a;
                font-size: 12px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #94a3b8;
                background-color: #ffffff;
                color: #0f172a;
                outline: none;
                padding: 2px 0px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 26px;
                padding: 4px 10px;
                background-color: #ffffff;
                color: #0f172a;
                border-radius: 0px;
            }
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
        """

        # ----------------------------------------------------
        # 1. SOL PANEL (EdgeTriggeredPanel) - İŞLEMLER, PROFİLLER & TEMA
        # ----------------------------------------------------
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        left_frame = QFrame()
        left_frame.setStyleSheet("background-color: transparent; border: none;")
        left_lyt = QVBoxLayout(left_frame)
        left_lyt.setContentsMargins(0, 0, 0, 0)
        left_lyt.setSpacing(8)

        # 1. GRUP: ŞABLON İŞLEMLERİ (Collapsible Section)
        sec_actions = CollapsibleSection("ŞABLON İŞLEMLERİ", is_expanded=True)
        self.btn_new = QPushButton("➕ Yeni Şablon Tanımla (F3)")
        self.btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new.setStyleSheet(self.toolbar_btn_style("#2563eb", "#ffffff", "#1d4ed8"))
        self.btn_new.clicked.connect(self.open_new_screen_dialog)

        self.btn_edit = QPushButton("✏️ Değiştir / Düzenle (F4)")
        self.btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_edit.setStyleSheet(self.toolbar_btn_style())
        self.btn_edit.clicked.connect(self.open_edit_screen_dialog)

        self.btn_duplicate = QPushButton("📋 Şablonu Kopyala")
        self.btn_duplicate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_duplicate.setStyleSheet(self.toolbar_btn_style())
        self.btn_duplicate.clicked.connect(self.duplicate_screen_definition)

        self.btn_delete = QPushButton("🗑️ Şablonu Sil (Del)")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setStyleSheet(self.toolbar_btn_style("#fee2e2", "#dc2626", "#fca5a5"))
        self.btn_delete.clicked.connect(self.delete_screen_definition)

        self.btn_reset_defaults = QPushButton("🏭 Fabrika Varsayılanlarına Sıfırla")
        self.btn_reset_defaults.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset_defaults.setStyleSheet(self.toolbar_btn_style("#fef3c7", "#92400e", "#fcd34d"))
        self.btn_reset_defaults.clicked.connect(self.on_reset_to_defaults_clicked)

        self.btn_excel = QPushButton("📊 Excel'e Aktar (F9)")
        self.btn_excel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_excel.setStyleSheet(self.toolbar_btn_style())
        self.btn_excel.clicked.connect(self.export_to_excel)

        self.btn_refresh = QPushButton("🔄 Listeyi Yenile")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet(self.toolbar_btn_style())
        self.btn_refresh.clicked.connect(self.load_screen_definitions)

        sec_actions.add_widget(self.btn_new)
        sec_actions.add_widget(self.btn_edit)
        sec_actions.add_widget(self.btn_duplicate)
        sec_actions.add_widget(self.btn_delete)
        sec_actions.add_widget(self.btn_reset_defaults)
        sec_actions.add_widget(self.btn_excel)
        sec_actions.add_widget(self.btn_refresh)
        left_lyt.addWidget(sec_actions)

        # 2. GRUP: KATEGORİ & FİLTRE
        sec_filter = CollapsibleSection("ŞABLON KATEGORİSİ", is_expanded=True)
        lbl_cat = QLabel("Gösterilecek Şablon Grubu:")
        lbl_cat.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        
        self.combo_category = QComboBox()
        self.combo_category.addItems([
            "Tüm Şablonlar (Hepsi)",
            "🏷️ Sistem Varsayılan Şablonları (tpl_*)",
            "⭐ Modül Ekran Tanımları (scr_*)",
        ])
        self.combo_category.setStyleSheet(combo_style)
        self.combo_category.currentIndexChanged.connect(self._on_category_filter_changed)
        sec_filter.add_widget(lbl_cat)
        sec_filter.add_widget(self.combo_category)
        left_lyt.addWidget(sec_filter)

        # 2.5 GRUP: DİNAMİK MODÜL AĞACI (Taxonomy Tree View)
        sec_taxonomy = CollapsibleSection("🌳 DİNAMİK MODÜL AĞACI", is_expanded=True)
        self.tree_taxonomy = QTreeWidget()
        self.tree_taxonomy.setHeaderHidden(True)
        self.tree_taxonomy.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                font-size: 11px;
            }
            QTreeWidget::item { padding: 4px; }
            QTreeWidget::item:hover { background-color: #f1f5f9; }
            QTreeWidget::item:selected { background-color: #2563eb; color: white; font-weight: bold; }
        """)
        self._populate_taxonomy_tree()
        self.tree_taxonomy.itemDoubleClicked.connect(self._on_tree_item_double_clicked)
        sec_taxonomy.add_widget(self.tree_taxonomy)
        left_lyt.addWidget(sec_taxonomy)

        # 3. GRUP: GÖRÜNÜM PROFİLLERİ (Teklif Yönetimi ile Birebir Aynı)
        self.sec_profiles = CollapsibleSection("GÖRÜNÜM PROFİLLERİ", is_expanded=True)
        lbl_prof = QLabel("Aktif Görünüm Profili:")
        lbl_prof.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        
        self.combo_sidebar_profiles = QComboBox()
        self.combo_sidebar_profiles.setStyleSheet(combo_style)
        self.combo_sidebar_profiles.currentTextChanged.connect(self._on_profile_changed)

        prof_btn_lyt = QHBoxLayout()
        prof_btn_lyt.setSpacing(4)
        btn_save_prof = QPushButton("💾 Kaydet")
        btn_save_prof.setStyleSheet(self.toolbar_btn_style())
        btn_save_prof.clicked.connect(self.save_current_profile)
        
        btn_manage_prof = QPushButton("⚙️ Sütunlar")
        btn_manage_prof.setStyleSheet(self.toolbar_btn_style())
        btn_manage_prof.clicked.connect(self.open_column_manager)
        
        prof_btn_lyt.addWidget(btn_save_prof)
        prof_btn_lyt.addWidget(btn_manage_prof)

        self.sec_profiles.add_widget(lbl_prof)
        self.sec_profiles.add_widget(self.combo_sidebar_profiles)
        self.sec_profiles.add_layout(prof_btn_lyt)
        left_lyt.addWidget(self.sec_profiles)

        # 4. GRUP: MERKEZİ TEMA, BAŞLIK, SATIR YÜKSEKLİĞİ & SAĞ TIK MENÜ AYARLARI
        sec_theme = CollapsibleSection("MERKEZİ TEMA & GRID AYARLARI", is_expanded=True)
        
        # Başlık Satır Yüksekliği
        lbl_hh_title = QLabel("Başlık Satır Yüksekliği (Header Height):")
        lbl_hh_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #1e3a8a;")
        sec_theme.add_widget(lbl_hh_title)

        h_slider_hh = QHBoxLayout()
        self.slider_header_h = QSlider(Qt.Orientation.Horizontal)
        self.slider_header_h.setRange(20, 70)
        self.slider_header_h.setValue(self.theme.header_height)
        
        self.spin_header_h = QSpinBox()
        self.spin_header_h.setRange(20, 70)
        self.spin_header_h.setValue(self.theme.header_height)
        self.spin_header_h.setStyleSheet("padding: 2px; font-weight: bold; border: 1px solid #cbd5e1; border-radius: 4px;")
        
        h_slider_hh.addWidget(self.slider_header_h)
        h_slider_hh.addWidget(self.spin_header_h)
        self.slider_header_h.valueChanged.connect(self.spin_header_h.setValue)
        self.spin_header_h.valueChanged.connect(self.slider_header_h.setValue)
        self.slider_header_h.valueChanged.connect(lambda v: self.theme.set_header_height(v))
        sec_theme.add_layout(h_slider_hh)

        # Veri Satır Yüksekliği
        lbl_h_title = QLabel("Veri Satır Yüksekliği (Row Height):")
        lbl_h_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #1e3a8a; margin-top: 4px;")
        sec_theme.add_widget(lbl_h_title)

        h_slider_box = QHBoxLayout()
        self.slider_height = QSlider(Qt.Orientation.Horizontal)
        self.slider_height.setRange(20, 70)
        self.slider_height.setValue(self.theme.row_height)
        
        self.spin_height = QSpinBox()
        self.spin_height.setRange(20, 70)
        self.spin_height.setValue(self.theme.row_height)
        self.spin_height.setStyleSheet("padding: 2px; font-weight: bold; border: 1px solid #cbd5e1; border-radius: 4px;")
        
        h_slider_box.addWidget(self.slider_height)
        h_slider_box.addWidget(self.spin_height)
        self.slider_height.valueChanged.connect(self.spin_height.setValue)
        self.spin_height.valueChanged.connect(self.slider_height.setValue)
        self.slider_height.valueChanged.connect(lambda v: self.theme.set_row_height(v))
        sec_theme.add_layout(h_slider_box)

        # Tablo Kurumsal Renk Teması
        lbl_t_title = QLabel("Kurumsal Tablo Teması:")
        lbl_t_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #1e3a8a; margin-top: 6px;")
        sec_theme.add_widget(lbl_t_title)

        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["1. Kurumsal Lacivert", "2. Zümrüt Yeşili", "3. Koyu Antrasit", "4. Klasik Bordo"])
        self.combo_theme.setStyleSheet("padding: 5px; background: white; border: 1px solid #cbd5e1; border-radius: 4px; font-weight: bold;")
        self.combo_theme.currentIndexChanged.connect(self._on_theme_changed)
        sec_theme.add_widget(self.combo_theme)

        # SAĞ TIK MENÜ TEMASI
        lbl_cm_title = QLabel("Sağ Tık Menü Renk Düzeni:")
        lbl_cm_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #1e3a8a; margin-top: 8px;")
        sec_theme.add_widget(lbl_cm_title)

        self.combo_menu_theme = QComboBox()
        self.combo_menu_theme.addItems([
            "🔵 Mavi Zemin - 🔴 Kırmızı Hover (Varsayılan)",
            "🟢 Zümrüt Zemin - 🟠 Turuncu Hover",
            "⚫ Koyu Antrasit - 🔵 Mavi Hover",
            "🔴 Klasik Bordo - 🔵 Lacivert Hover",
        ])
        self.combo_menu_theme.setStyleSheet("padding: 5px; background: white; border: 1px solid #cbd5e1; border-radius: 4px; font-weight: bold;")
        self.combo_menu_theme.currentIndexChanged.connect(self._on_menu_theme_changed)
        sec_theme.add_widget(self.combo_menu_theme)

        btn_test_menu = QPushButton("👁️ Sağ Tık Menü Tasarımını Önizle")
        btn_test_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test_menu.setStyleSheet(self.toolbar_btn_style("#f8fafc", "#0f172a", "#cbd5e1"))
        btn_test_menu.clicked.connect(lambda: self.show_context_menu(self.table_view.rect().center()))
        sec_theme.add_widget(btn_test_menu)

        left_lyt.addWidget(sec_theme)
        left_lyt.addStretch()

        left_scroll.setWidget(left_frame)
        self.left_panel.set_content(left_scroll)
        main_layout.addWidget(self.left_panel)

        # ----------------------------------------------------
        # 2. ORTA PANEL - FilterableTableView (Teklif Yönetimi ile Birebir Aynı)
        # ----------------------------------------------------
        self.center_container = QWidget()
        center_lyt = QVBoxLayout(self.center_container)
        center_lyt.setContentsMargins(4, 0, 4, 0)
        center_lyt.setSpacing(6)

        # Header-Filter-Row yapısına ve scroll senkronizasyonuna sahip FilterableTableView
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
        self.table_view.verticalHeader().setDefaultSectionSize(self.theme.row_height)
        self.table_view.horizontalHeader().setFixedHeight(self.theme.header_height)
        self.table_view.setSelectionBehavior(QHeaderView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table_view.setShowGrid(True)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.setStyleSheet(self.theme.get_table_stylesheet())

        # Sağ Tık Menüsü
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)

        # Çift tıklama ve Seçim Olayları
        self.table_view.doubleClicked.connect(lambda idx: self.open_edit_screen_dialog())
        self.table_view.selectionModel().selectionChanged.connect(self._on_row_selected)
        self.filterable_table.filter_changed.connect(self._on_filter_changed)

        center_lyt.addWidget(self.filterable_table, 1)

        # Alt Footer Çubuğu
        footer_bar = QFrame()
        footer_lyt = QHBoxLayout(footer_bar)
        footer_lyt.setContentsMargins(4, 2, 4, 2)
        
        self.lbl_count = QLabel("Toplam: 0 Ekran Şablonu")
        self.lbl_count.setStyleSheet("font-weight: bold; color: #64748b;")
        footer_lyt.addWidget(self.lbl_count)
        footer_lyt.addStretch()

        center_lyt.addWidget(footer_bar)
        main_layout.addWidget(self.center_container, 1)

        # ----------------------------------------------------
        # 3. SAĞ PANEL (EdgeTriggeredPanel) - DETAY VE CANLI TEST KARTI
        # ----------------------------------------------------
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_frame = QFrame()
        right_lyt = QVBoxLayout(right_frame)
        right_lyt.setContentsMargins(6, 6, 6, 6)
        right_lyt.setSpacing(10)

        lbl_summary_title = QLabel("ŞABLON ÖZETİ")
        lbl_summary_title.setObjectName("sidebar_title")
        lbl_summary_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e3a8a; padding-bottom: 4px; border-bottom: 2px solid #cbd5e1;")
        right_lyt.addWidget(lbl_summary_title)

        self.lbl_sel_title = QLabel("Lütfen listeden bir ekran seçin")
        self.lbl_sel_title.setWordWrap(True)
        self.lbl_sel_title.setStyleSheet("font-weight: bold; font-size: 11pt; color: #0f172a;")
        right_lyt.addWidget(self.lbl_sel_title)

        # Detay Kartı
        detail_box = QFrame()
        detail_box.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px;")
        db_lyt = QVBoxLayout(detail_box)
        db_lyt.setSpacing(6)

        self.lbl_info_id = QLabel("Kod: -")
        self.lbl_info_type = QLabel("Tür: -")
        self.lbl_info_preset = QLabel("Grid Preseti: -")
        self.lbl_info_header_height = QLabel("Başlık Yüksekliği: -")
        self.lbl_info_row_height = QLabel("Satır Yüksekliği: -")
        self.lbl_info_panels = QLabel("Paneller: -")
        self.lbl_info_actions = QLabel("Aksiyonlar: -")

        for lbl in [self.lbl_info_id, self.lbl_info_type, self.lbl_info_preset, self.lbl_info_header_height, self.lbl_info_row_height, self.lbl_info_panels, self.lbl_info_actions]:
            lbl.setStyleSheet("color: #334155; font-size: 11px;")
            db_lyt.addWidget(lbl)

        right_lyt.addWidget(detail_box)

        # Buton: Canlı Aç / Test Et
        self.btn_live_test = QPushButton("🚀 Bu Ekranı Canlı Test Et")
        self.btn_live_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_live_test.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 6px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_live_test.clicked.connect(self._launch_live_test_screen)
        right_lyt.addWidget(self.btn_live_test)

        right_lyt.addStretch()
        right_scroll.setWidget(right_frame)
        self.right_panel.set_content(right_scroll)
        main_layout.addWidget(self.right_panel)

        # Sinyaller: Tema, Başlık ve Satır Yüksekliği canlı bağlantısı
        self.theme.theme_changed.connect(lambda: self.table_view.setStyleSheet(self.theme.get_table_stylesheet()))
        self.theme.row_height_changed.connect(self._on_global_row_height_changed)
        self.theme.header_height_changed.connect(self._on_global_header_height_changed)

    def _setup_shortcuts(self):
        """Klavye kısayollarını ayarlar."""
        sc_f3 = QShortcut(QKeySequence("F3"), self)
        sc_f3.activated.connect(self.open_new_screen_dialog)

        sc_f4 = QShortcut(QKeySequence("F4"), self)
        sc_f4.activated.connect(self.open_edit_screen_dialog)

        sc_del = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        sc_del.activated.connect(self.delete_screen_definition)

        sc_f9 = QShortcut(QKeySequence("F9"), self)
        sc_f9.activated.connect(self.export_to_excel)

    def _on_global_row_height_changed(self, height: int):
        """Veri satır yüksekliği slider'ı hareket ettiği anda tablodaki tüm satırları anında canlı günceller."""
        self.table_view.verticalHeader().setDefaultSectionSize(height)
        for r in range(self.table_model.rowCount()):
            self.table_view.setRowHeight(r, height)
        self.table_view.viewport().update()

    def _on_global_header_height_changed(self, height: int):
        """Başlık satır yüksekliği slider'ı hareket ettiği anda başlık alanını canlı günceller."""
        self.table_view.horizontalHeader().setFixedHeight(height)
        self.table_view.viewport().update()

    def load_profiles(self):
        """Kayıtlı görünüm profillerini yükler."""
        if not hasattr(self, "combo_sidebar_profiles"):
            return
        self.combo_sidebar_profiles.blockSignals(True)
        self.combo_sidebar_profiles.clear()
        profiles = self.profile_manager.load_profiles()
        for name in profiles.keys():
            self.combo_sidebar_profiles.addItem(name)
        active = self.profile_manager.get_active_profile_name()
        idx = self.combo_sidebar_profiles.findText(active)
        if idx >= 0:
            self.combo_sidebar_profiles.setCurrentIndex(idx)
        self.combo_sidebar_profiles.blockSignals(False)

    def _on_profile_changed(self, profile_name: str):
        if not profile_name:
            return
        p = self.profile_manager.get_profile(profile_name)
        if p and hasattr(self, "filterable_table"):
            self.filterable_table.apply_view_profile(p)

    def save_current_profile(self):
        """Mevcut sütun genişliklerini aktif profile kaydeder."""
        active_name = self.combo_sidebar_profiles.currentText() or "Varsayılan"
        current_p = self.filterable_table.capture_current_view_profile(active_name)
        self.profile_manager.save_profile(current_p)
        QMessageBox.information(self, "Profil Kaydedildi", f"'{active_name}' görünüm profili ve sütun ayarları kaydedildi.")

    def open_column_manager(self):
        """Sütun Göster/Gizle ve Genişlik Yönetim Diyaloğunu açar."""
        if hasattr(self, "filterable_table"):
            self.filterable_table.open_column_manager_dialog()

    def _on_category_filter_changed(self, index: int):
        self.load_screen_definitions()

    def load_screen_definitions(self):
        """Kayıtlı tüm ekran şablonlarını QStandardItemModel üzerinden listeler."""
        self.table_model.removeRows(0, self.table_model.rowCount())
        self.table_view.setUpdatesEnabled(False)
        
        cat_filter = self.combo_category.currentIndex() if hasattr(self, "combo_category") else 0
        
        for screen_id, data in SCREEN_DEFINITIONS.items():
            is_sys = data.get("is_system_template", False)
            
            # Kategori filtresi
            if cat_filter == 1 and not is_sys:
                continue
            elif cat_filter == 2 and is_sys:
                continue

            title = data.get("title", "")
            preset = data.get("grid_preset", "")
            tpl_type = "🏷️ Sistem Varsayılanı" if is_sys else "⭐ Özel Ekran Tanımı"
            
            custom_hh = data.get("custom_header_height")
            hh_text = f"{custom_hh} px (Özel)" if custom_hh else f"{self.theme.header_height} px (Merkezi)"

            custom_h = data.get("custom_row_height")
            h_text = f"{custom_h} px (Özel)" if custom_h else f"{self.theme.row_height} px (Merkezi)"

            regions = data.get("regions", {})
            left_p = "Aktif (Filtre)" if regions.get("left_sidebar") else "Kapalı"
            right_p = "Aktif (Özet)" if regions.get("right_sidebar") else "Kapalı"
            act_count = f"{len(data.get('actions', []))} Buton"

            chk = QStandardItem("")
            chk.setCheckable(True)
            chk.setCheckState(Qt.CheckState.Unchecked)

            id_item = QStandardItem(screen_id)
            id_item.setData(screen_id, Qt.ItemDataRole.UserRole)

            status_item = QStandardItem("🟢 Aktif")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            row = [
                chk,
                id_item,
                QStandardItem(title),
                QStandardItem(tpl_type),
                QStandardItem(preset),
                QStandardItem(hh_text),
                QStandardItem(h_text),
                QStandardItem(left_p),
                QStandardItem(right_p),
                QStandardItem(act_count),
                status_item,
            ]
            self.table_model.appendRow(row)

        for r in range(self.table_model.rowCount()):
            self.table_view.setRowHeight(r, self.theme.row_height)

        self.table_view.setUpdatesEnabled(True)
        self.lbl_count.setText(f"Toplam: {self.table_model.rowCount()} Ekran Şablonu")
        
        if self.table_model.rowCount() > 0:
            self.table_view.selectRow(0)

    def _on_filter_changed(self, filter_dict: dict):
        """Kolon bazlı arama filtreleri değiştiğinde satırları süzer."""
        for r in range(self.table_model.rowCount()):
            row_visible = True
            for col_idx, filter_text in filter_dict.items():
                item = self.table_model.item(r, col_idx)
                if item:
                    cell_text = item.text().lower()
                    if filter_text.lower() not in cell_text:
                        row_visible = False
                        break
            self.table_view.setRowHidden(r, not row_visible)

    def get_selected_screen_id(self) -> str | None:
        sel = self.table_view.selectionModel().selectedRows()
        if not sel:
            return None
        row = sel[0].row()
        item = self.table_model.item(row, 1)  # 1. sütun ID'dir
        return item.text() if item else None

    def _on_row_selected(self):
        screen_id = self.get_selected_screen_id()
        if not screen_id or screen_id not in SCREEN_DEFINITIONS:
            return
        
        data = SCREEN_DEFINITIONS[screen_id]
        self.lbl_sel_title.setText(data.get("title", screen_id))
        self.lbl_info_id.setText(f"<b>Şablon Kodu:</b> {screen_id}")
        
        is_sys = data.get("is_system_template", False)
        type_str = "🏷️ Sistem Varsayılan Şablonu (Fabrika Çıkışı)" if is_sys else "⭐ Modüle Özel Ekran Tanımı"
        self.lbl_info_type.setText(f"<b>Tür:</b> {type_str}")
        self.lbl_info_preset.setText(f"<b>Grid Preseti:</b> {data.get('grid_preset')}")
        
        custom_hh = data.get("custom_header_height")
        hh_str = f"{custom_hh} px (Özel)" if custom_hh else f"{self.theme.header_height} px (Merkezi)"
        self.lbl_info_header_height.setText(f"<b>Başlık Yüksekliği:</b> {hh_str}")

        custom_h = data.get("custom_row_height")
        h_str = f"{custom_h} px (Özel)" if custom_h else f"{self.theme.row_height} px (Merkezi)"
        self.lbl_info_row_height.setText(f"<b>Satır Yüksekliği:</b> {h_str}")
        
        reg = data.get("regions", {})
        panels = []
        if reg.get("header"):
            panels.append("Header")
        if reg.get("left_sidebar"):
            panels.append("Sol Filtre")
        if reg.get("right_sidebar"):
            panels.append("Sağ Özet")
        if reg.get("footer"):
            panels.append("Footer")
        self.lbl_info_panels.setText(f"<b>Aktif Paneller:</b> {', '.join(panels)}")
        
        acts = [a.get("label") for a in data.get("actions", [])]
        self.lbl_info_actions.setText(f"<b>Eylemler:</b> {', '.join(acts)}")

    def show_context_menu(self, pos):
        """Teklif Yönetimi kalitesinde dinamik temalı zengin sağ tık menüsü."""
        index = self.table_view.indexAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(self.theme.get_context_menu_stylesheet())

        act_new = QAction("➕ Yeni Şablon Tanımla (F3)", self)
        act_new.triggered.connect(self.open_new_screen_dialog)
        menu.addAction(act_new)

        if index.isValid():
            self.table_view.selectRow(index.row())

            act_edit = QAction("✏️ Değiştir / Düzenle (F4)", self)
            act_edit.triggered.connect(self.open_edit_screen_dialog)

            act_dup = QAction("📋 Şablonu Kopyala / Çoğalt", self)
            act_dup.triggered.connect(self.duplicate_screen_definition)

            act_del = QAction("🗑️ Şablonu Sil (Del)", self)
            act_del.triggered.connect(self.delete_screen_definition)

            act_test = QAction("🚀 Bu Ekranı Canlı Test Et", self)
            act_test.triggered.connect(self._launch_live_test_screen)

            menu.addAction(act_edit)
            menu.addAction(act_dup)
            menu.addAction(act_del)
            menu.addSeparator()
            menu.addAction(act_test)

        menu.addSeparator()
        
        act_reset = QAction("🏭 Fabrika Varsayılanlarına Sıfırla", self)
        act_reset.triggered.connect(self.on_reset_to_defaults_clicked)
        menu.addAction(act_reset)

        act_xls = QAction("📊 Excel'e Aktar (F9)", self)
        act_xls.triggered.connect(self.export_to_excel)
        menu.addAction(act_xls)

        self.filterable_table.add_column_actions_to_menu(menu)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def open_new_screen_dialog(self):
        dlg = ScreenDefinitionDetailDialog(screen_id=None, parent=self)
        dlg.definition_saved.connect(lambda: self.load_screen_definitions())
        dlg.exec()

    def open_edit_screen_dialog(self):
        screen_id = self.get_selected_screen_id()
        if not screen_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz ekran şablonunu seçin.")
            return
        dlg = ScreenDefinitionDetailDialog(screen_id=screen_id, parent=self)
        dlg.definition_saved.connect(lambda: self.load_screen_definitions())
        dlg.exec()

    def duplicate_screen_definition(self):
        screen_id = self.get_selected_screen_id()
        if not screen_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen kopyalamak istediğiniz ekran şablonunu seçin.")
            return
        
        if screen_id in SCREEN_DEFINITIONS:
            new_id = f"{screen_id}_kopya"
            copy_data = dict(SCREEN_DEFINITIONS[screen_id])
            copy_data["title"] = f"{copy_data.get('title')} (Kopya)"
            copy_data["is_system_template"] = False
            register_screen_definition(new_id, copy_data, auto_save=True)
            self.load_screen_definitions()
            QMessageBox.information(self, "Başarılı", f"'{new_id}' adıyla şablon çoğaltıldı.")

    def delete_screen_definition(self):
        screen_id = self.get_selected_screen_id()
        if not screen_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz ekran şablonunu seçin.")
            return

        data = SCREEN_DEFINITIONS.get(screen_id, {})
        if data.get("is_system_template"):
            QMessageBox.warning(self, "Sistem Koruması", "Sistem Varsayılan Şablonları (tpl_*) silinemez. Ancak ayarlarını düzenleyebilirsiniz.")
            return

        reply = QMessageBox.question(
            self, "Onay", f"'{screen_id}' ekran şablonunu silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            SCREEN_DEFINITIONS.pop(screen_id, None)
            from src.desktop.core.screen_registry import save_screen_definitions_to_disk
            save_screen_definitions_to_disk()
            self.load_screen_definitions()

    def on_reset_to_defaults_clicked(self):
        reply = QMessageBox.question(
            self, "Fabrika Ayarlarına Sıfırla",
            "Tüm ekran şablonları fabrika çıkışı varsayılan ayarlarına sıfırlanacak.\nÖzel tanımlarınız kaldırılacak. Devam etmek istiyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            reset_to_factory_defaults()
            self.load_screen_definitions()
            QMessageBox.information(self, "Sıfırlandı", "Tüm ekran şablonları fabrika varsayılanlarına başarıyla sıfırlandı.")

    def export_to_excel(self):
        """Listedeki şablonları panoya/Excel formatında kopyalar."""
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys()) if i > 0]
        text = "\t".join(headers) + "\n"
        for r in range(self.table_model.rowCount()):
            row_items = []
            for c in range(1, self.table_model.columnCount()):
                item = self.table_model.item(r, c)
                row_items.append(item.text() if item else "")
            text += "\t".join(row_items) + "\n"
        QApplication.clipboard().setText(text.strip())
        QMessageBox.information(self, "Excel Aktarımı", "Tablo verileri Excel formatında panoya kopyalandı (Ctrl+V ile Excel'e yapıştırabilirsiniz).")

    def _launch_live_test_screen(self):
        screen_id = self.get_selected_screen_id()
        if not screen_id:
            return
        
        from PyQt6.QtWidgets import QDialog

        from src.desktop.ui.components.base_list_screen import BaseListScreen
        diag = QDialog(self)
        diag.setWindowTitle(f"🚀 Canlı Ekran Simülasyonu - [{screen_id}]")
        diag.resize(1050, 620)
        lyt = QVBoxLayout(diag)
        lyt.setContentsMargins(0, 0, 0, 0)
        
        screen_widget = BaseListScreen(screen_id=screen_id, parent=diag)
        dummy_data = [
            ["001", "TEST KAYDI A.Ş.", "1122334455", "0212 555 0101", 125000.0, 0.0, "Aktif"],
            ["002", "DENEME LOJİSTİK LTD.", "9988776655", "0216 444 0202", 45000.0, 12000.0, "Aktif"],
            ["003", "GLOBAL SANAYİ TİC.", "4567891230", "0312 333 0303", 0.0, 89500.5, "Pasif"],
        ]
        screen_widget.set_data(dummy_data)
        lyt.addWidget(screen_widget)
        diag.exec()

    def _populate_taxonomy_tree(self):
        """Hiyerarşik Modül Ağacını doldurur."""
        if not hasattr(self, "tree_taxonomy"):
            return
        self.tree_taxonomy.clear()
        
        categories = taxonomy_manager.get_categories()
        for cat in categories:
            cat_item = QTreeWidgetItem(self.tree_taxonomy)
            cat_item.setText(0, f"{cat.get('icon', '📁')} {cat.get('name')}")
            cat_item.setExpanded(True)
            
            for mod in cat.get("modules", []):
                mod_item = QTreeWidgetItem(cat_item)
                mod_item.setText(0, f"📄 {mod.get('name')} [{mod.get('code')}]")
                mod_item.setData(0, Qt.ItemDataRole.UserRole, mod)
                
                screens = mod.get("screens", {})
                if "list" in screens:
                    sub_item = QTreeWidgetItem(mod_item)
                    scr = screens["list"]
                    sub_item.setText(0, f"  1- İşlem Liste: {scr.get('title')}")
                    sub_item.setData(0, Qt.ItemDataRole.UserRole, scr.get("id"))
                if "detail" in screens:
                    sub_item = QTreeWidgetItem(mod_item)
                    scr = screens["detail"]
                    sub_item.setText(0, f"  2- Fiş Detay: {scr.get('title')}")
                    sub_item.setData(0, Qt.ItemDataRole.UserRole, scr.get("id"))
                if "report" in screens:
                    sub_item = QTreeWidgetItem(mod_item)
                    scr = screens["report"]
                    sub_item.setText(0, f"  3- Rapor Analiz: {scr.get('title')}")
                    sub_item.setData(0, Qt.ItemDataRole.UserRole, scr.get("id"))

    def _on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Ağaçta bir ekrana çift tıklandığında tanım diyaloğunu açar."""
        screen_id = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(screen_id, str):
            diag = ScreenDefinitionDetailDialog(screen_id=screen_id, parent=self)
            diag.definition_saved.connect(lambda sid: self.load_screen_definitions())
            diag.exec()

    def _on_theme_changed(self, index: int):
        palettes = [
            {"header_bg": "#2563eb", "row_bg": "#ffffff", "alt_row_bg": "#f8fafc", "grid_line_color": "#e2e8f0"},
            {"header_bg": "#059669", "row_bg": "#ffffff", "alt_row_bg": "#f0fdf4", "grid_line_color": "#dcfce7"},
            {"header_bg": "#334155", "row_bg": "#ffffff", "alt_row_bg": "#f1f5f9", "grid_line_color": "#cbd5e1"},
            {"header_bg": "#991b1b", "row_bg": "#ffffff", "alt_row_bg": "#fef2f2", "grid_line_color": "#fee2e2"},
        ]
        chosen = palettes[index]
        self.theme.set_theme_colors(**chosen)

    def _on_menu_theme_changed(self, index: int):
        palettes = [
            {"bg": "#1e3a8a", "color": "#ffffff", "hover_bg": "#dc2626", "hover_color": "#ffffff", "border": "#3b82f6"},
            {"bg": "#065f46", "color": "#ffffff", "hover_bg": "#d97706", "hover_color": "#ffffff", "border": "#10b981"},
            {"bg": "#0f172a", "color": "#ffffff", "hover_bg": "#2563eb", "hover_color": "#ffffff", "border": "#475569"},
            {"bg": "#881337", "color": "#ffffff", "hover_bg": "#1e40af", "hover_color": "#ffffff", "border": "#f43f5e"},
        ]
        chosen = palettes[index]
        self.theme.set_context_menu_colors(**chosen)
