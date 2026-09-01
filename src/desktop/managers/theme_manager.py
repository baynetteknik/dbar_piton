"""
TOYA ERP - Merkezi Tema ve Stil Yöneticisi (ThemeManager)
Singleton mimarisi ile çalışır. Tüm stiller, renkler, font metrikleri,
başlık yükseklikleri (Header Height), satır yükseklikleri (Row Height) ve
sağ tık menü (Context Menu) renk şablonları buradan okunur ve yönetilir.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QSettings
from PyQt6.QtGui import QFont, QFontMetrics


class ThemeManager(QObject):
    _instance = None
    
    # Canlı güncelleme sinyalleri
    theme_changed = pyqtSignal()
    row_height_changed = pyqtSignal(int)
    header_height_changed = pyqtSignal(int)

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        super().__init__()
        self._initialized = True
        
        self.settings = QSettings("ToyaERP", "ThemeSettings")
        self._load_theme_settings()

    def _load_theme_settings(self):
        """Ayarları QSettings veya varsayılan kurumsal ERP paletinden yükler."""
        # Font & Font Metrikleri
        font_family = self.settings.value("theme/font_family", "Segoe UI")
        font_size = int(self.settings.value("theme/font_size", 10))
        self.app_font = QFont(font_family, font_size)
        self.font_metrics = QFontMetrics(self.app_font)

        # Otomatik varsayılan satır yüksekliği: font yüksekliği + ferah padding
        default_calc_height = self.font_metrics.height() + 14
        self.row_height = int(self.settings.value("grid/row_height", default_calc_height))
        
        # Başlık satır yüksekliği (Header Height)
        default_header_height = self.font_metrics.height() + 18
        self.header_height = int(self.settings.value("grid/header_height", default_header_height))

        # Kurumsal Renk Paleti (Varsayılan: TOYA Modern Lacivert / Gri Kurumsal)
        self.primary_color = self.settings.value("theme/primary_color", "#1e3a8a")      # Kurumsal Lacivert
        self.header_bg = self.settings.value("grid/header_bg", "#2563eb")               # Tablo Başlık Rengi
        self.header_text_color = self.settings.value("grid/header_color", "#ffffff")     # Başlık Metin Rengi
        self.row_bg = self.settings.value("grid/row_bg", "#ffffff")                     # Satır Arkaplanı
        self.alt_row_bg = self.settings.value("grid/alt_row_bg", "#f8fafc")             # Alternatif Satır Rengi
        self.grid_line_color = self.settings.value("grid/line_color", "#e2e8f0")        # Izgara Çizgi Rengi
        self.selection_bg = self.settings.value("grid/selection_bg", "#3b82f6")         # Seçili Satır Rengi
        self.selection_color = self.settings.value("grid/selection_color", "#ffffff")   # Seçili Metin Rengi
        self.sidebar_bg = self.settings.value("theme/sidebar_bg", "#f1f5f9")            # Yan Panel Arkaplanı
        self.border_color = self.settings.value("theme/border_color", "#cbd5e1")        # Standart Kenarlık

        # Sağ Tık Menüsü (Context Menu) Renkleri (Varsayılan: Mavi Zemin, Beyaz Yazı, Kırmızı Hover)
        self.menu_bg = self.settings.value("menu/bg", "#1e3a8a")                        # Sağ Tık Mavi Zemin
        self.menu_color = self.settings.value("menu/color", "#ffffff")                  # Sağ Tık Beyaz Yazılar
        self.menu_hover_bg = self.settings.value("menu/hover_bg", "#dc2626")            # Sağ Tık Kırmızı Hover
        self.menu_hover_color = self.settings.value("menu/hover_color", "#ffffff")      # Sağ Tık Hover Beyaz Yazı
        self.menu_border = self.settings.value("menu/border", "#3b82f6")                # Sağ Tık Kenarlık

    def set_row_height(self, height: int):
        """Tüm açık AppGrid örneklerinde veri satır yüksekliğini anında günceller."""
        if height < 18:
            height = 18
        self.row_height = height
        self.settings.setValue("grid/row_height", height)
        self.row_height_changed.emit(height)

    def set_header_height(self, height: int):
        """Tüm tablolarda kolon başlığı satır yüksekliğini (Header Height) anında günceller."""
        if height < 20:
            height = 20
        self.header_height = height
        self.settings.setValue("grid/header_height", height)
        self.header_height_changed.emit(height)
        self.theme_changed.emit()

    def set_context_menu_colors(self, bg: str = None, color: str = None, 
                                hover_bg: str = None, hover_color: str = None, 
                                border: str = None):
        """Sağ tık menü renklerini dinamik olarak günceller."""
        if bg:
            self.menu_bg = bg
            self.settings.setValue("menu/bg", bg)
        if color:
            self.menu_color = color
            self.settings.setValue("menu/color", color)
        if hover_bg:
            self.menu_hover_bg = hover_bg
            self.settings.setValue("menu/hover_bg", hover_bg)
        if hover_color:
            self.menu_hover_color = hover_color
            self.settings.setValue("menu/hover_color", hover_color)
        if border:
            self.menu_border = border
            self.settings.setValue("menu/border", border)
        self.theme_changed.emit()

    def set_theme_colors(self, header_bg: str = None, row_bg: str = None, 
                         alt_row_bg: str = None, grid_line_color: str = None):
        """Tema renklerini günceller ve açık pencerelere sinyal yayar."""
        if header_bg:
            self.header_bg = header_bg
            self.settings.setValue("grid/header_bg", header_bg)
        if row_bg:
            self.row_bg = row_bg
            self.settings.setValue("grid/row_bg", row_bg)
        if alt_row_bg:
            self.alt_row_bg = alt_row_bg
            self.settings.setValue("grid/alt_row_bg", alt_row_bg)
        if grid_line_color:
            self.grid_line_color = grid_line_color
            self.settings.setValue("grid/line_color", grid_line_color)
            
        self.theme_changed.emit()

    def get_table_stylesheet(self) -> str:
        """AppGrid ve QTableView için merkezi QSS çıktısı üretir."""
        return f"""
            QTableWidget, QTableView {{
                background-color: {self.row_bg};
                alternate-background-color: {self.alt_row_bg};
                gridline-color: {self.grid_line_color};
                border: 1px solid {self.border_color};
                font-family: "{self.app_font.family()}";
                font-size: {self.app_font.pointSize()}pt;
                selection-background-color: {self.selection_bg};
                selection-color: {self.selection_color};
                outline: 0;
            }}
            QTableWidget::item, QTableView::item {{
                padding-left: 6px;
                padding-right: 6px;
                border: none;
            }}
            QTableWidget::item:selected, QTableView::item:selected {{
                background-color: {self.selection_bg};
                color: {self.selection_color};
            }}
            QHeaderView::section {{
                background-color: {self.header_bg};
                color: {self.header_text_color};
                padding: 4px 8px;
                min-height: {self.header_height}px;
                height: {self.header_height}px;
                border: 1px solid {self.grid_line_color};
                font-family: "{self.app_font.family()}";
                font-size: {self.app_font.pointSize()}pt;
                font-weight: bold;
            }}
            QHeaderView::section:hover {{
                background-color: {self.primary_color};
            }}
            QScrollBar:vertical {{
                border: none;
                background: #f1f5f9;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #94a3b8;
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #64748b;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """

    def get_context_menu_stylesheet(self) -> str:
        """Sağ tık menüleri (QMenu) için merkezi kurumsal stil çıktısı üretir."""
        return f"""
            QMenu {{
                background-color: {self.menu_bg};
                color: {self.menu_color};
                border: 1px solid {self.menu_border};
                border-radius: 6px;
                padding: 5px;
                font-family: "{self.app_font.family()}";
                font-size: {self.app_font.pointSize()}pt;
                font-weight: 600;
            }}
            QMenu::item {{
                padding: 6px 20px 6px 12px;
                border-radius: 4px;
                background-color: transparent;
                color: {self.menu_color};
            }}
            QMenu::item:selected {{
                background-color: {self.menu_hover_bg};
                color: {self.menu_hover_color};
                font-weight: bold;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {self.menu_border};
                margin: 4px 2px;
            }}
            QMenu::icon {{
                padding-left: 4px;
            }}
        """

    def get_sidebar_stylesheet(self) -> str:
        """Sidebar panelleri için standart stil."""
        return f"""
            QFrame#sidebar_frame {{
                background-color: {self.sidebar_bg};
                border: 1px solid {self.border_color};
                border-radius: 4px;
            }}
            QLabel#sidebar_title {{
                font-family: "{self.app_font.family()}";
                font-size: {self.app_font.pointSize() + 1}pt;
                font-weight: bold;
                color: {self.primary_color};
                padding-bottom: 6px;
                border-bottom: 2px solid {self.border_color};
            }}
        """
