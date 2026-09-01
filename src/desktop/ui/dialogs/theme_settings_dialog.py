"""
TOYA ERP - Yönetici Kontrol ve Ayar Paneli (Theme & Permission Settings)
Sadece Sistem Yöneticisinin (Admin) erişebileceği, canlı tema, satır yüksekliği
ve rol yetki simülasyon aracıdır. Hem bağımsız Dialog hem de gömülebilir Widget olarak çalışır.
"""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QSlider, QComboBox, QPushButton, QGroupBox, QSpinBox, QFrame
)
from PyQt6.QtCore import Qt

from src.desktop.managers.theme_manager import ThemeManager
from src.desktop.managers.permission_manager import PermissionManager


class AppGridThemeSettingsWidget(QWidget):
    """Genel Ayarlar altına sekmeli olarak gömülebilen Tema & Satır Yüksekliği Paneli."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = ThemeManager()
        self.perm_mgr = PermissionManager()
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Başlık ve Açıklama Kartı
        header_card = QFrame()
        header_card.setStyleSheet("background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px;")
        hc_lyt = QVBoxLayout(header_card)
        
        lbl_title = QLabel("📐 AppGrid Merkezi Stil ve Satır Yüksekliği Yönetimi")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 800; color: #1e3a8a;")
        hc_lyt.addWidget(lbl_title)
        
        lbl_desc = QLabel(
            "Tüm sistem genelinde AppGrid kullanan ekranların satır ferahlığı, başlık renkleri ve "
            "font metrikleri bu merkezden canlı olarak yönetilir. Değişiklikler açık pencerelere anında yansır."
        )
        lbl_desc.setStyleSheet("color: #475569; font-size: 11px;")
        lbl_desc.setWordWrap(True)
        hc_lyt.addWidget(lbl_desc)
        main_layout.addWidget(header_card)

        # 1. SATIR YÜKSEKLİĞİ AYARI (Tüm Gridleri Canlı Günceller)
        grp_height = QGroupBox("Genel Grid Satır Yüksekliği (Row Height)")
        grp_height.setStyleSheet("QGroupBox { font-weight: bold; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        h_layout = QVBoxLayout(grp_height)
        
        slider_row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(22, 60)
        self.slider.setValue(self.theme.row_height)
        
        self.spin = QSpinBox()
        self.spin.setRange(22, 60)
        self.spin.setValue(self.theme.row_height)
        self.spin.setStyleSheet("padding: 4px; font-weight: bold;")
        
        slider_row.addWidget(self.slider)
        slider_row.addWidget(self.spin)
        h_layout.addLayout(slider_row)
        
        lbl_hint = QLabel("💡 İpucu: Bu ayar açık olan tüm AppGrid tablolarının satır yüksekliğini anında yeniden boyutlandırır.")
        lbl_hint.setStyleSheet("color: #0369a1; font-size: 9pt; font-weight: 500;")
        h_layout.addWidget(lbl_hint)
        main_layout.addWidget(grp_height)

        # 2. KURUMSAL TEMA PALETİ SEÇİMİ
        grp_theme = QGroupBox("Kurumsal Renk Paleti")
        grp_theme.setStyleSheet("QGroupBox { font-weight: bold; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        t_layout = QVBoxLayout(grp_theme)
        
        self.combo_theme = QComboBox()
        self.combo_theme.addItems([
            "1. Kurumsal Lacivert (Varsayılan TOYA Paleti)",
            "2. Zümrüt Yeşili (Finans & Bankacılık)",
            "3. Modern Koyu Antrasit",
            "4. Klasik ERP Bordosu"
        ])
        self.combo_theme.setStyleSheet("padding: 6px; font-weight: bold; background: white; border: 1px solid #cbd5e1; border-radius: 4px;")
        t_layout.addWidget(self.combo_theme)
        main_layout.addWidget(grp_theme)

        # 3. YETKİ / ROL SİMÜLASYONU
        grp_role = QGroupBox("Yetki / Rol Test Simülasyonu (RBAC)")
        grp_role.setStyleSheet("QGroupBox { font-weight: bold; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 10px; padding-top: 15px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }")
        r_layout = QVBoxLayout(grp_role)
        
        self.combo_role = QComboBox()
        self.combo_role.addItems(["ADMIN", "MUHASEBE", "SATIS", "DEPO"])
        self.combo_role.setCurrentText(self.perm_mgr.current_role)
        self.combo_role.setStyleSheet("padding: 6px; font-weight: bold; background: white; border: 1px solid #cbd5e1; border-radius: 4px;")
        r_layout.addWidget(self.combo_role)
        
        lbl_role_hint = QLabel("💡 Rol seçildiğinde ekranlardaki aksiyon butonları (Yeni, Sil, Pasif vb.) yetki kuralına göre anında gizlenir/açılır.")
        lbl_role_hint.setStyleSheet("color: #475569; font-size: 9pt;")
        r_layout.addWidget(lbl_role_hint)
        main_layout.addWidget(grp_role)

        main_layout.addStretch()

        # Sinyaller
        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self._on_height_changed)
        
        self.combo_theme.currentIndexChanged.connect(self._on_theme_palette_changed)
        self.combo_role.currentTextChanged.connect(self._on_role_changed)

    def _on_height_changed(self, val: int):
        self.theme.set_row_height(val)

    def _on_theme_palette_changed(self, index: int):
        palettes = [
            # 1. Lacivert
            {"header_bg": "#2563eb", "row_bg": "#ffffff", "alt_row_bg": "#f8fafc", "grid_line_color": "#e2e8f0"},
            # 2. Zümrüt
            {"header_bg": "#059669", "row_bg": "#ffffff", "alt_row_bg": "#f0fdf4", "grid_line_color": "#dcfce7"},
            # 3. Antrasit
            {"header_bg": "#334155", "row_bg": "#ffffff", "alt_row_bg": "#f1f5f9", "grid_line_color": "#cbd5e1"},
            # 4. Bordo
            {"header_bg": "#991b1b", "row_bg": "#ffffff", "alt_row_bg": "#fef2f2", "grid_line_color": "#fee2e2"}
        ]
        chosen = palettes[index]
        self.theme.set_theme_colors(**chosen)

    def _on_role_changed(self, role: str):
        self.perm_mgr.set_role(role)


class ThemeSettingsDialog(QDialog):
    """Bağımsız pencere olarak açılan Admin Ayar Dialogu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sistem Yöneticisi: AppGrid & Yetki Ayarları")
        self.setFixedSize(480, 520)
        
        layout = QVBoxLayout(self)
        self.settings_widget = AppGridThemeSettingsWidget(self)
        layout.addWidget(self.settings_widget)
        
        btn_close = QPushButton("Kapat", self)
        btn_close.setStyleSheet("background: #334155; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
