"""
TOYA ERP - Ekran ve Şablon Tanımı Detay Penceresi (ScreenDefinitionDetailDialog)
Tam ekran (Maximized) açılan, sol tarafında işlem ve kayıt butonları barındıran,
üstte minimum yer kaplayan kompakt başlık ve sağda ferah sekmeli çalışma alanına sahip
kurumsal Master-Detail şablon düzenleme penceresidir.
"""

from typing import Dict, Any, List, Optional
import copy
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QTabWidget, QCheckBox, QComboBox, 
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, 
    QFrame, QMessageBox, QGroupBox, QSpinBox, QRadioButton, 
    QButtonGroup, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QKeySequence, QShortcut

from src.desktop.core.grid_presets import GRID_PRESETS, get_preset
from src.desktop.core.screen_registry import (
    SCREEN_DEFINITIONS, DEFAULT_SYSTEM_TEMPLATES, 
    register_screen_definition, get_screen_definition
)
from src.desktop.managers.theme_manager import ThemeManager
from src.desktop.ui.components.app_grid import AppGrid


class ScreenDefinitionDetailDialog(QDialog):
    """Tam Ekran (Maximized) ve Sol İşlem Paneline Sahip Ekran Şablonu Düzenleme Penceresi."""

    definition_saved = pyqtSignal(str)  # Kaydedilen screen_id

    def __init__(self, screen_id: str = None, parent=None):
        super().__init__(parent)
        self.screen_id = screen_id
        self.is_new = screen_id is None
        self.theme = ThemeManager()
        
        # Mevcut veriyi yükle veya boş şablon oluştur
        if not self.is_new:
            self.data = get_screen_definition(screen_id)
            self.setWindowTitle(f"📐 Ekran Şablonu Düzenle - [{screen_id}]")
        else:
            self.screen_id = f"scr_yeni_{len(SCREEN_DEFINITIONS)+1}"
            self.data = copy.deepcopy(DEFAULT_SYSTEM_TEMPLATES["tpl_default_list"])
            self.data["title"] = "Yeni Ekran Şablonu"
            self.data["is_system_template"] = False
            self.data["base_template"] = "tpl_default_list"
            self.setWindowTitle("📐 Yeni Ekran Şablonu Tanımla")

        self.setMinimumSize(1100, 720)
        self.setWindowState(Qt.WindowState.WindowMaximized)  # Tam Ekran Aç
        
        self._setup_ui()
        self._setup_shortcuts()
        self._populate_fields()

    def _setup_shortcuts(self):
        """Klavye kısayolları (F2: Kaydet, Esc: Kapat, F5: Önizleme)."""
        sc_save = QShortcut(QKeySequence("F2"), self)
        sc_save.activated.connect(self._save_definition)

        sc_prev = QShortcut(QKeySequence("F5"), self)
        sc_prev.activated.connect(lambda: self.tabs.setCurrentIndex(4))

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # ----------------------------------------------------
        # 1. ÜST KOMPAKT BAŞLIK ŞERİDİ (Minimum Dikey Yer Kaplar)
        # ----------------------------------------------------
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background-color: #1e3a8a;
                border-radius: 6px;
                padding: 4px 10px;
            }
            QLabel { color: white; }
        """)
        top_lyt = QHBoxLayout(top_bar)
        top_lyt.setContentsMargins(8, 4, 8, 4)

        lbl_app_logo = QLabel("📐 TOYA ERP")
        lbl_app_logo.setStyleSheet("font-weight: 900; font-size: 13px; color: #93c5fd;")
        top_lyt.addWidget(lbl_app_logo)

        lbl_sep = QLabel("|")
        lbl_sep.setStyleSheet("color: #60a5fa; font-weight: bold;")
        top_lyt.addWidget(lbl_sep)

        self.lbl_card_title = QLabel(self.data.get("title", "Ekran Şablonu"))
        self.lbl_card_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff;")
        top_lyt.addWidget(self.lbl_card_title)

        self.lbl_code_badge = QLabel(f"[{self.screen_id}]")
        self.lbl_code_badge.setStyleSheet("font-size: 11px; color: #bfdbfe; font-family: monospace; font-weight: bold;")
        top_lyt.addWidget(self.lbl_code_badge)

        top_lyt.addStretch()

        is_sys = self.data.get("is_system_template", False)
        type_text = "🏷️ Sistem Varsayılan Şablonu" if is_sys else "⭐ Özel Modül Şablonu"
        type_bg = "#3b82f6" if is_sys else "#10b981"
        lbl_type_badge = QLabel(type_text)
        lbl_type_badge.setStyleSheet(f"background-color: {type_bg}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: bold;")
        top_lyt.addWidget(lbl_type_badge)

        lbl_shortcut_hint = QLabel("⌨️ F2: Kaydet | F5: Canlı Önizle | Esc: Vazgeç")
        lbl_shortcut_hint.setStyleSheet("font-size: 10px; color: #cbd5e1; margin-left: 10px;")
        top_lyt.addWidget(lbl_shortcut_hint)

        main_layout.addWidget(top_bar)

        # ----------------------------------------------------
        # 2. ANA GÖVDE: SOL AKSİYON SIDEBAR + SAĞ GENİŞ ÇALIŞMA ALANI
        # ----------------------------------------------------
        body_layout = QHBoxLayout()
        body_layout.setSpacing(8)

        # 👈 SOL AKSİYON & BİLGİ SIDEBAR'I
        left_sidebar = QFrame()
        left_sidebar.setFixedWidth(260)
        left_sidebar.setStyleSheet("""
            QFrame#left_sidebar {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
        """)
        left_sidebar.setObjectName("left_sidebar")
        
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        left_content = QWidget()
        left_lyt = QVBoxLayout(left_content)
        left_lyt.setContentsMargins(10, 10, 10, 10)
        left_lyt.setSpacing(10)

        # Grup 1: İŞLEMLER / AKSİYONLAR
        grp_actions = QGroupBox("ŞABLON İŞLEMLERİ")
        grp_actions.setStyleSheet("QGroupBox { font-weight: bold; color: #1e3a8a; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 4px; padding-top: 10px; }")
        act_box_lyt = QVBoxLayout(grp_actions)
        act_box_lyt.setSpacing(6)

        self.btn_save = QPushButton("💾 Şablonu Kaydet (F2)")
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: 800;
                padding: 10px 14px;
                border-radius: 6px;
                font-size: 12px;
                border: 1px solid #059669;
                text-align: left;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_save.clicked.connect(self._save_definition)
        act_box_lyt.addWidget(self.btn_save)

        self.btn_goto_preview = QPushButton("👁️ Canlı Ekran Simülasyonu (F5)")
        self.btn_goto_preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_goto_preview.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 11px;
                border: 1px solid #1d4ed8;
                text-align: left;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_goto_preview.clicked.connect(lambda: self.tabs.setCurrentIndex(4))
        act_box_lyt.addWidget(self.btn_goto_preview)

        self.btn_cancel = QPushButton("🚪 Vazgeç / Kapat (Esc)")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #475569;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 11px;
                border: 1px solid #cbd5e1;
                font-weight: bold;
                text-align: left;
            }
            QPushButton:hover { background-color: #f1f5f9; color: #0f172a; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        act_box_lyt.addWidget(self.btn_cancel)

        left_lyt.addWidget(grp_actions)

        # Grup 2: MİRAS ALINAN TEMEL ŞABLON
        grp_inherit = QGroupBox("MİRAS & ŞABLON TÜRÜ")
        grp_inherit.setStyleSheet("QGroupBox { font-weight: bold; color: #1e3a8a; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 4px; padding-top: 10px; }")
        inh_lyt = QVBoxLayout(grp_inherit)
        inh_lyt.setSpacing(6)

        lbl_base = QLabel("Temel Sistem Şablonu:")
        lbl_base.setStyleSheet("font-size: 10px; font-weight: bold; color: #475569;")
        inh_lyt.addWidget(lbl_base)

        self.cmb_base_template = QComboBox()
        for tpl_id, tpl_info in DEFAULT_SYSTEM_TEMPLATES.items():
            self.cmb_base_template.addItem(f"{tpl_info.get('title')}", tpl_id)
        self.cmb_base_template.setStyleSheet("padding: 5px; border: 1px solid #cbd5e1; border-radius: 4px; background: white; font-weight: bold; font-size: 11px;")
        self.cmb_base_template.currentIndexChanged.connect(self._on_base_template_changed)
        inh_lyt.addWidget(self.cmb_base_template)

        left_lyt.addWidget(grp_inherit)

        # Grup 3: ANLIK ÖZET KARTI
        grp_summary = QGroupBox("ŞABLON ÖZETİ")
        grp_summary.setStyleSheet("QGroupBox { font-weight: bold; color: #1e3a8a; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 4px; padding-top: 10px; }")
        sum_lyt = QVBoxLayout(grp_summary)
        sum_lyt.setSpacing(4)

        self.lbl_sum_id = QLabel(f"<b>Kod:</b> {self.screen_id}")
        self.lbl_sum_preset = QLabel("<b>Preset:</b> -")
        self.lbl_sum_hh = QLabel("<b>Başlık Yük.:</b> -")
        self.lbl_sum_rh = QLabel("<b>Satır Yük.:</b> -")
        self.lbl_sum_acts = QLabel("<b>Eylem Sayısı:</b> -")

        for lbl in [self.lbl_sum_id, self.lbl_sum_preset, self.lbl_sum_hh, self.lbl_sum_rh, self.lbl_sum_acts]:
            lbl.setStyleSheet("font-size: 10px; color: #334155;")
            sum_lyt.addWidget(lbl)

        left_lyt.addWidget(grp_summary)
        left_lyt.addStretch()

        left_scroll.setWidget(left_content)
        l_wrap = QVBoxLayout(left_sidebar)
        l_wrap.setContentsMargins(0, 0, 0, 0)
        l_wrap.addWidget(left_scroll)
        body_layout.addWidget(left_sidebar)

        # 👉 SAĞ GENİŞ ÇALIŞMA ALANI (SEKMELER)
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::panel {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
                padding: 12px;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #475569;
                padding: 8px 20px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #1e3a8a;
                border-bottom: 2px solid white;
            }
        """)

        # Sekme 1: Genel Bilgiler & Kimlik
        self.tab_general = self._create_general_tab()
        self.tabs.addTab(self.tab_general, "📋 1. Genel Bilgiler & Kimlik")

        # Sekme 2: Bölüm & Panel Yerleşimi (Layout)
        self.tab_layout = self._create_layout_tab()
        self.tabs.addTab(self.tab_layout, "🧩 2. Bölüm & Panel Düzeni")

        # Sekme 3: Grid, Sütun & Yükseklik Yapılandırması
        self.tab_grid = self._create_grid_tab()
        self.tabs.addTab(self.tab_grid, "📊 3. Grid, Sütun & Yükseklikler")

        # Sekme 4: Eylemler & Buton Yetki Matrisi
        self.tab_actions = self._create_actions_tab()
        self.tabs.addTab(self.tab_actions, "⚡ 4. Eylemler & İzinler")

        # Sekme 5: Canlı Önizleme (Live Preview)
        self.tab_preview = self._create_preview_tab()
        self.tabs.addTab(self.tab_preview, "👁️ 5. Canlı Ekran Simülasyonu")

        body_layout.addWidget(self.tabs, 1)
        main_layout.addLayout(body_layout, 1)

    def _create_general_tab(self) -> QWidget:
        tab = QWidget()
        lyt = QVBoxLayout(tab)
        lyt.setSpacing(12)

        grp_id = QGroupBox("Ekran Kimliği ve Temel Bilgileri")
        grp_id.setStyleSheet("QGroupBox { font-weight: bold; color: #1e3a8a; }")
        form_lyt = QVBoxLayout(grp_id)
        form_lyt.setSpacing(8)

        # Şablon ID
        form_lyt.addWidget(QLabel("Ekran / Şablon ID (Benzersiz Kısakod):"))
        self.txt_screen_id = QLineEdit()
        self.txt_screen_id.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px;")
        if not self.is_new:
            self.txt_screen_id.setReadOnly(True)
            self.txt_screen_id.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: #f1f5f9;")
        form_lyt.addWidget(self.txt_screen_id)

        # Ekran Başlığı
        form_lyt.addWidget(QLabel("Ekran Başlığı (Kullanıcıya Görünecek İsim):"))
        self.txt_title = QLineEdit()
        self.txt_title.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px;")
        self.txt_title.textChanged.connect(lambda t: self.lbl_card_title.setText(t or "Ekran Şablonu"))
        form_lyt.addWidget(self.txt_title)

        # Modül Kategorisi
        form_lyt.addWidget(QLabel("Modül Grubu:"))
        self.cmb_module_group = QComboBox()
        self.cmb_module_group.addItems(["Kart Tanımları (Cari/Stok)", "Evrak & Fişler (Fatura/Teklif/Sipariş)", "Finans & Kasa", "Raporlar & Analiz"])
        self.cmb_module_group.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        form_lyt.addWidget(self.cmb_module_group)

        # Açıklama
        form_lyt.addWidget(QLabel("Şablon Açıklaması / Geliştirici Notu:"))
        self.txt_desc = QTextEdit()
        self.txt_desc.setPlaceholderText("Bu ekran şablonunun kullanım amacı...")
        self.txt_desc.setFixedHeight(80)
        self.txt_desc.setStyleSheet("padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        form_lyt.addWidget(self.txt_desc)

        lyt.addWidget(grp_id)
        lyt.addStretch()
        return tab

    def _create_layout_tab(self) -> QWidget:
        tab = QWidget()
        lyt = QVBoxLayout(tab)
        lyt.setSpacing(12)

        grp_regions = QGroupBox("Bölüm ve Panel Görünürlükleri")
        grp_regions.setStyleSheet("QGroupBox { font-weight: bold; color: #1e3a8a; }")
        reg_lyt = QVBoxLayout(grp_regions)
        reg_lyt.setSpacing(10)

        self.chk_header = QCheckBox("📌 Üst Header Bar (Başlık + Anlık Arama + Aksiyon Butonları)")
        self.chk_header.setChecked(True)
        reg_lyt.addWidget(self.chk_header)

        # Sol Sidebar
        h_left = QHBoxLayout()
        self.chk_left_sidebar = QCheckBox("👈 Sol Sidebar Paneli:")
        self.cmb_left_comp = QComboBox()
        self.cmb_left_comp.addItems(["leftsidebar001 (Kategori & Filtre Ağacı)", "Özel Sol Panel"])
        self.cmb_left_comp.setStyleSheet("padding: 4px; background: white; border: 1px solid #cbd5e1; border-radius: 4px;")
        h_left.addWidget(self.chk_left_sidebar)
        h_left.addWidget(self.cmb_left_comp, 1)
        reg_lyt.addLayout(h_left)

        # Sağ Sidebar
        h_right = QHBoxLayout()
        self.chk_right_sidebar = QCheckBox("👉 Sağ Sidebar Paneli:")
        self.cmb_right_comp = QComboBox()
        self.cmb_right_comp.addItems(["rightsidebar001 (Bakiye & Detay Özet Kartı)", "Özel Sağ Panel"])
        self.cmb_right_comp.setStyleSheet("padding: 4px; background: white; border: 1px solid #cbd5e1; border-radius: 4px;")
        h_right.addWidget(self.chk_right_sidebar)
        h_right.addWidget(self.cmb_right_comp, 1)
        reg_lyt.addLayout(h_right)

        self.chk_footer = QCheckBox("📊 Alt Footer Bar (Toplam Kayıt Sayısı + Durum Çubuğu)")
        self.chk_footer.setChecked(True)
        reg_lyt.addWidget(self.chk_footer)

        lyt.addWidget(grp_regions)
        lyt.addStretch()
        return tab

    def _create_grid_tab(self) -> QWidget:
        tab = QWidget()
        lyt = QVBoxLayout(tab)
        lyt.setSpacing(10)

        # 1. Preset Seçimi
        h_preset = QHBoxLayout()
        h_preset.addWidget(QLabel("Temel Grid Preseti Seçin:"))
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems(list(GRID_PRESETS.keys()))
        self.cmb_preset.setStyleSheet("padding: 6px; font-weight: bold; background: white; border: 1px solid #cbd5e1; border-radius: 4px;")
        self.cmb_preset.currentTextChanged.connect(self._on_preset_selected)
        h_preset.addWidget(self.cmb_preset, 1)
        lyt.addLayout(h_preset)

        # 2. BAŞLIK SATIR YÜKSEKLİĞİ
        grp_header_h = QGroupBox("📐 Başlık Satır Yüksekliği (Header Row Height)")
        grp_header_h.setStyleSheet("QGroupBox { font-weight: bold; color: #1e3a8a; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 4px; padding-top: 10px; }")
        hh_lyt = QVBoxLayout(grp_header_h)

        self.btn_group_header_h = QButtonGroup(self)
        self.rb_header_h_global = QRadioButton(f"Merkezi Tema Başlık Yüksekliğini Kullan (Şu anki: {self.theme.header_height} px)")
        self.rb_header_h_custom = QRadioButton("Bu Ekrana Özel Başlık Yüksekliği Belirle:")
        
        self.btn_group_header_h.addButton(self.rb_header_h_global, 0)
        self.btn_group_header_h.addButton(self.rb_header_h_custom, 1)
        hh_lyt.addWidget(self.rb_header_h_global)

        h_custom_header_box = QHBoxLayout()
        h_custom_header_box.addWidget(self.rb_header_h_custom)
        
        self.spin_custom_header_h = QSpinBox()
        self.spin_custom_header_h.setRange(20, 80)
        self.spin_custom_header_h.setValue(self.theme.header_height)
        self.spin_custom_header_h.setEnabled(False)
        self.spin_custom_header_h.setStyleSheet("padding: 4px; font-weight: bold; border: 1px solid #cbd5e1; border-radius: 4px;")
        h_custom_header_box.addWidget(self.spin_custom_header_h)
        h_custom_header_box.addWidget(QLabel("px"))
        h_custom_header_box.addStretch()
        hh_lyt.addLayout(h_custom_header_box)

        self.rb_header_h_custom.toggled.connect(self.spin_custom_header_h.setEnabled)
        self.rb_header_h_custom.toggled.connect(lambda checked: self._on_height_config_changed())
        self.spin_custom_header_h.valueChanged.connect(lambda v: self._on_height_config_changed())
        lyt.addWidget(grp_header_h)

        # 3. VERİ SATIR YÜKSEKLİĞİ
        grp_height = QGroupBox("📐 Veri Satır Yüksekliği (Data Row Height)")
        grp_height.setStyleSheet("QGroupBox { font-weight: bold; color: #1e3a8a; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 4px; padding-top: 10px; }")
        h_lyt = QVBoxLayout(grp_height)

        self.btn_group_height = QButtonGroup(self)
        self.rb_height_global = QRadioButton(f"Merkezi Tema Veri Satır Yüksekliğini Kullan (Şu anki: {self.theme.row_height} px)")
        self.rb_height_custom = QRadioButton("Bu Ekrana Özel Veri Satır Yüksekliği Belirle:")
        
        self.btn_group_height.addButton(self.rb_height_global, 0)
        self.btn_group_height.addButton(self.rb_height_custom, 1)
        h_lyt.addWidget(self.rb_height_global)

        h_custom_box = QHBoxLayout()
        h_custom_box.addWidget(self.rb_height_custom)
        
        self.spin_custom_height = QSpinBox()
        self.spin_custom_height.setRange(20, 80)
        self.spin_custom_height.setValue(self.theme.row_height)
        self.spin_custom_height.setEnabled(False)
        self.spin_custom_height.setStyleSheet("padding: 4px; font-weight: bold; border: 1px solid #cbd5e1; border-radius: 4px;")
        h_custom_box.addWidget(self.spin_custom_height)
        h_custom_box.addWidget(QLabel("px"))
        h_custom_box.addStretch()
        h_lyt.addLayout(h_custom_box)

        self.rb_height_custom.toggled.connect(self.spin_custom_height.setEnabled)
        self.rb_height_custom.toggled.connect(lambda checked: self._on_height_config_changed())
        self.spin_custom_height.valueChanged.connect(lambda v: self._on_height_config_changed())
        lyt.addWidget(grp_height)

        # 4. Sütun Tablosu
        lbl_cols = QLabel("Preset Sütun Yapılandırması (Genişlik Oranları & Hizalamalar):")
        lbl_cols.setStyleSheet("font-weight: bold; color: #1e3a8a; margin-top: 4px;")
        lyt.addWidget(lbl_cols)

        self.col_table = QTableWidget()
        self.col_table.setColumnCount(4)
        self.col_table.setHorizontalHeaderLabels(["SÜTUN BAŞLIĞI", "GENİŞLİK ORANI (%)", "HİZALAMA", "VERİ TİPİ"])
        self.col_table.horizontalHeader().setStretchLastSection(True)
        self.col_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.col_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                background: white;
                border-radius: 4px;
            }
            QHeaderView::section {
                background: #f1f5f9;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #cbd5e1;
            }
        """)
        lyt.addWidget(self.col_table, 1)

        return tab

    def _create_actions_tab(self) -> QWidget:
        tab = QWidget()
        lyt = QVBoxLayout(tab)
        lyt.setSpacing(10)

        lbl_acts = QLabel("Ekran Aksiyon Butonları & Yetkilendirme Kuralları:")
        lbl_acts.setStyleSheet("font-weight: bold; color: #1e3a8a;")
        lyt.addWidget(lbl_acts)

        self.act_table = QTableWidget()
        self.act_table.setColumnCount(4)
        self.act_table.setHorizontalHeaderLabels(["EYLEM ID", "BUTON ETİKETİ", "YETKİ KODU", "STİL VARYANTI"])
        self.act_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.act_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                background: white;
                border-radius: 4px;
            }
            QHeaderView::section {
                background: #f1f5f9;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #cbd5e1;
            }
        """)
        lyt.addWidget(self.act_table, 1)

        # Buton ekleme çubuğu
        h_btn_bar = QHBoxLayout()
        btn_add_act = QPushButton("➕ Yeni Eylem Butonu Ekle")
        btn_add_act.setStyleSheet("background: #e2e8f0; padding: 6px 12px; font-weight: bold; border-radius: 4px;")
        btn_add_act.clicked.connect(self._add_action_row)
        h_btn_bar.addWidget(btn_add_act)
        h_btn_bar.addStretch()
        lyt.addLayout(h_btn_bar)

        return tab

    def _create_preview_tab(self) -> QWidget:
        tab = QWidget()
        lyt = QVBoxLayout(tab)
        lyt.setSpacing(10)

        lbl_info = QLabel("👁️ Canlı Ekran Simülasyonu: Seçtiğiniz preset, başlık ve satır yükseklikleri tam ekran ferahlığında render edilmektedir.")
        lbl_info.setStyleSheet("color: #0369a1; font-weight: bold; font-size: 11px;")
        lyt.addWidget(lbl_info)

        custom_h = self.data.get("custom_row_height")
        custom_hh = self.data.get("custom_header_height")
        self.preview_grid = AppGrid(
            preset=self.data.get("grid_preset", "dbgrid_cari"), 
            custom_row_height=custom_h,
            custom_header_height=custom_hh
        )
        dummy_rows = [
            ["001", "ÖRNEK FİRMA A.Ş.", "1122334455", "0212 111 2233", 45000.0, 0.0, "Aktif"],
            ["002", "DEMO TEKNOLOJİ LTD.", "9988776655", "0216 222 3344", 1200.5, 5000.0, "Aktif"],
            ["003", "GLOBAL DAĞITIM PAZARLAMA", "5544332211", "0312 333 4455", 0.0, 89000.0, "Pasif"],
            ["004", "ANADOLU LOJİSTİK A.Ş.", "4433221100", "0232 444 5566", 78000.0, 2300.0, "Aktif"],
            ["005", "BATI TİCARET VE SANAYİ", "7788990011", "0224 555 6677", 12000.0, 0.0, "Aktif"],
        ]
        self.preview_grid.setData(dummy_rows)
        lyt.addWidget(self.preview_grid, 1)

        btn_refresh_preview = QPushButton("🔄 Önizlemeyi Yenile / Güncelle")
        btn_refresh_preview.setStyleSheet("background: #2563eb; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_refresh_preview.clicked.connect(self._refresh_preview)
        lyt.addWidget(btn_refresh_preview)

        return tab

    def _populate_fields(self):
        """Mevcut verileri form alanlarına doldurur."""
        self.txt_screen_id.setText(self.screen_id)
        self.txt_title.setText(self.data.get("title", ""))
        self.txt_desc.setText(self.data.get("description", ""))
        
        # Temel şablon seçimi
        base_tpl = self.data.get("base_template", "tpl_default_list")
        idx = self.cmb_base_template.findData(base_tpl)
        if idx >= 0:
            self.cmb_base_template.setCurrentIndex(idx)

        # Bölgeler
        regions = self.data.get("regions", {})
        self.chk_header.setChecked(regions.get("header", True))
        self.chk_left_sidebar.setChecked(regions.get("left_sidebar", True))
        self.chk_right_sidebar.setChecked(regions.get("right_sidebar", True))
        self.chk_footer.setChecked(regions.get("footer", True))

        # Başlık Yüksekliği
        custom_hh = self.data.get("custom_header_height")
        if custom_hh is not None and isinstance(custom_hh, int):
            self.rb_header_h_custom.setChecked(True)
            self.spin_custom_header_h.setValue(custom_hh)
        else:
            self.rb_header_h_global.setChecked(True)

        # Veri Satır Yüksekliği
        custom_h = self.data.get("custom_row_height")
        if custom_h is not None and isinstance(custom_h, int):
            self.rb_height_custom.setChecked(True)
            self.spin_custom_height.setValue(custom_h)
        else:
            self.rb_height_global.setChecked(True)

        # Preset
        current_preset = self.data.get("grid_preset", "dbgrid_cari")
        self.cmb_preset.setCurrentText(current_preset)
        self._load_preset_columns(current_preset)

        # Eylemler
        self._load_actions(self.data.get("actions", []))
        self._update_summary_labels()

    def _update_summary_labels(self):
        """Sol paneldeki özet kartını günceller."""
        self.lbl_sum_id.setText(f"<b>Kod:</b> {self.screen_id}")
        self.lbl_sum_preset.setText(f"<b>Preset:</b> {self.cmb_preset.currentText()}")
        
        hh = f"{self.spin_custom_header_h.value()} px (Özel)" if self.rb_header_h_custom.isChecked() else f"{self.theme.header_height} px (Merkezi)"
        self.lbl_sum_hh.setText(f"<b>Başlık Yük.:</b> {hh}")

        rh = f"{self.spin_custom_height.value()} px (Özel)" if self.rb_height_custom.isChecked() else f"{self.theme.row_height} px (Merkezi)"
        self.lbl_sum_rh.setText(f"<b>Satır Yük.:</b> {rh}")
        self.lbl_sum_acts.setText(f"<b>Eylem Sayısı:</b> {self.act_table.rowCount()} Buton")

    def _on_base_template_changed(self, idx: int):
        """Kullanıcı temel sistem şablonunu değiştirdiğinde alanları doldurur."""
        if not self.is_new:
            return
        tpl_id = self.cmb_base_template.currentData()
        if tpl_id in DEFAULT_SYSTEM_TEMPLATES:
            tpl = copy.deepcopy(DEFAULT_SYSTEM_TEMPLATES[tpl_id])
            self.data = tpl
            self.txt_title.setText(tpl.get("title", ""))
            self.txt_desc.setText(tpl.get("description", ""))
            self.cmb_preset.setCurrentText(tpl.get("grid_preset", "dbgrid_cari"))
            
            regions = tpl.get("regions", {})
            self.chk_header.setChecked(regions.get("header", True))
            self.chk_left_sidebar.setChecked(regions.get("left_sidebar", True))
            self.chk_right_sidebar.setChecked(regions.get("right_sidebar", True))
            self.chk_footer.setChecked(regions.get("footer", True))

            self._load_preset_columns(tpl.get("grid_preset", "dbgrid_cari"))
            self._load_actions(tpl.get("actions", []))
            self._update_summary_labels()
            self._refresh_preview()

    def _on_preset_selected(self, preset_name: str):
        self._load_preset_columns(preset_name)
        self._update_summary_labels()
        self._refresh_preview()

    def _on_height_config_changed(self):
        """Başlık veya satır yüksekliği ayarı değiştiğinde canlı önizlemeyi anında günceller."""
        if hasattr(self, "preview_grid"):
            if self.rb_height_custom.isChecked():
                h = self.spin_custom_height.value()
                self.preview_grid.set_custom_row_height(h)
            else:
                self.preview_grid.set_custom_row_height(None)

            if self.rb_header_h_custom.isChecked():
                hh = self.spin_custom_header_h.value()
                self.preview_grid.set_custom_header_height(hh)
            else:
                self.preview_grid.set_custom_header_height(None)
        self._update_summary_labels()

    def _load_preset_columns(self, preset_name: str):
        if preset_name not in GRID_PRESETS:
            return
        conf = GRID_PRESETS[preset_name]
        cols = conf.get("columns", [])
        ratios = conf.get("width_ratios", [])
        aligns = conf.get("alignments", [])
        types = conf.get("types", [])

        self.col_table.setRowCount(len(cols))
        for i, col in enumerate(cols):
            self.col_table.setItem(i, 0, QTableWidgetItem(col))
            ratio_pct = f"{int(ratios[i] * 100)}%" if i < len(ratios) else "10%"
            self.col_table.setItem(i, 1, QTableWidgetItem(ratio_pct))
            self.col_table.setItem(i, 2, QTableWidgetItem(aligns[i] if i < len(aligns) else "L"))
            self.col_table.setItem(i, 3, QTableWidgetItem(types[i] if i < len(types) else "text"))

    def _load_actions(self, actions: List[Dict[str, Any]]):
        self.act_table.setRowCount(len(actions))
        for i, act in enumerate(actions):
            self.act_table.setItem(i, 0, QTableWidgetItem(act.get("id", "")))
            self.act_table.setItem(i, 1, QTableWidgetItem(act.get("label", "")))
            self.act_table.setItem(i, 2, QTableWidgetItem(act.get("permission", "")))
            self.act_table.setItem(i, 3, QTableWidgetItem(act.get("variant", "default")))

    def _add_action_row(self):
        row = self.act_table.rowCount()
        self.act_table.insertRow(row)
        self.act_table.setItem(row, 0, QTableWidgetItem(f"act_custom_{row+1}"))
        self.act_table.setItem(row, 1, QTableWidgetItem("Yeni İşlem"))
        self.act_table.setItem(row, 2, QTableWidgetItem("general.view"))
        self.act_table.setItem(row, 3, QTableWidgetItem("default"))
        self._update_summary_labels()

    def _refresh_preview(self):
        preset = self.cmb_preset.currentText()
        if preset in GRID_PRESETS:
            custom_h = self.spin_custom_height.value() if self.rb_height_custom.isChecked() else None
            custom_hh = self.spin_custom_header_h.value() if self.rb_header_h_custom.isChecked() else None
            
            parent_lyt = self.tab_preview.layout()
            parent_lyt.removeWidget(self.preview_grid)
            self.preview_grid.deleteLater()
            
            self.preview_grid = AppGrid(preset=preset, custom_row_height=custom_h, custom_header_height=custom_hh)
            dummy_rows = [
                ["001", "ÖRNEK FİRMA A.Ş.", "1122334455", "0212 111 2233", 45000.0, 0.0, "Aktif"],
                ["002", "DEMO TEKNOLOJİ LTD.", "9988776655", "0216 222 3344", 1200.5, 5000.0, "Aktif"],
                ["003", "GLOBAL DAĞITIM PAZARLAMA", "5544332211", "0312 333 4455", 0.0, 89000.0, "Pasif"],
                ["004", "ANADOLU LOJİSTİK A.Ş.", "4433221100", "0232 444 5566", 78000.0, 2300.0, "Aktif"],
                ["005", "BATI TİCARET VE SANAYİ", "7788990011", "0224 555 6677", 12000.0, 0.0, "Aktif"],
            ]
            self.preview_grid.setData(dummy_rows)
            parent_lyt.insertWidget(1, self.preview_grid, 1)

    def _save_definition(self):
        screen_id = self.txt_screen_id.text().strip()
        title = self.txt_title.text().strip()

        if not screen_id or not title:
            QMessageBox.warning(self, "Uyarı", "Lütfen Ekran ID ve Başlık alanlarını doldurunuz.")
            return

        # Aksiyonları topla
        actions = []
        for r in range(self.act_table.rowCount()):
            act_id = self.act_table.item(r, 0).text() if self.act_table.item(r, 0) else f"act_{r}"
            label = self.act_table.item(r, 1).text() if self.act_table.item(r, 1) else "İşlem"
            perm = self.act_table.item(r, 2).text() if self.act_table.item(r, 2) else ""
            variant = self.act_table.item(r, 3).text() if self.act_table.item(r, 3) else "default"
            actions.append({"id": act_id, "label": label, "permission": perm, "variant": variant})

        custom_h = self.spin_custom_height.value() if self.rb_height_custom.isChecked() else None
        custom_hh = self.spin_custom_header_h.value() if self.rb_header_h_custom.isChecked() else None

        updated_def = {
            "title": title,
            "description": self.txt_desc.toPlainText().strip(),
            "base_template": self.cmb_base_template.currentData(),
            "is_system_template": self.data.get("is_system_template", False),
            "grid_preset": self.cmb_preset.currentText(),
            "custom_row_height": custom_h,
            "custom_header_height": custom_hh,
            "regions": {
                "header": self.chk_header.isChecked(),
                "left_sidebar": self.chk_left_sidebar.isChecked(),
                "right_sidebar": self.chk_right_sidebar.isChecked(),
                "footer": self.chk_footer.isChecked()
            },
            "components": {
                "left_sidebar": "leftsidebar001",
                "right_sidebar": "rightsidebar001"
            },
            "actions": actions
        }

        # Kayıt defterine yaz (otomatik JSON diske kaydeder)
        register_screen_definition(screen_id, updated_def, auto_save=True)
        self.definition_saved.emit(screen_id)
        QMessageBox.information(self, "Başarılı", f"'{title}' ({screen_id}) ekran şablonu başarıyla kaydedildi.")
        self.accept()
