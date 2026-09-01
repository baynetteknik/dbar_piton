import datetime
import logging

from PyQt6.QtCore import QSettings, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QCursor, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QSplitter,
    QTabBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.models import Site
from src.desktop.ui.backup import BackupWidget
from src.desktop.ui.cari_list_screen import CariListScreen
from src.desktop.ui.components.text_selection_helper import init_global_text_selection
from src.desktop.ui.settings import SettingsWidget
from src.desktop.ui.stok_list_screen import StokListScreen
from src.desktop.ui.toast import ToastNotification
from src.desktop.ui.widgets.favorite_actions_widget import FavoriteActionsWidget
from src.desktop.ui.widgets.menu_grid_widget import MenuGridWidget
from src.desktop.ui.widgets.quick_tiles_bar_widget import QuickTilesBarWidget

logger = logging.getLogger(__name__)


class QtLogHandler(logging.Handler):
    """Standart Python loglarını PyQt sinyallerine yönlendiren özel log işleyici."""

    def __init__(self, signal):
        super().__init__()
        self.signal = signal

    def emit(self, record):
        try:
            msg = self.format(record)
            self.signal.emit(msg)
        except Exception:
            self.handleError(record)


# ==========================================
# MENÜ VE SAĞ KLİK AÇILIR PENCERE STİLİ
# Kural: Zemin Mavi (#1e3a8a), Yazılar Beyaz (#ffffff)
# ==========================================
MENU_STYLESHEET = """
    QMenu {
        background-color: #1e3a8a;
        color: #ffffff;
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 6px;
        font-size: 12px;
        font-weight: 600;
        font-family: 'Segoe UI';
    }
    QMenu::item {
        background-color: transparent;
        color: #ffffff;
        padding: 8px 22px 8px 12px;
        border-radius: 4px;
        margin: 2px 0px;
    }
    QMenu::item:selected {
        background-color: #2563eb;
        color: #ffffff;
    }
    QMenu::separator {
        height: 1px;
        background-color: #3b82f6;
        margin: 4px 0px;
    }
"""


# ==========================================
# HOVER İLE YUKARI/AŞAĞI AÇILAN POPUP MENÜ
# Zemin Mavi (#1e3a8a), Yazılar Beyaz (#ffffff)
# ==========================================
class MenuPopup(QFrame):
    def __init__(self, parent, category_name, items, on_item_click):
        super().__init__(parent)
        self.parent_widget = parent
        self.on_item_click = on_item_click

        self.setStyleSheet("""
            QFrame {
                background-color: #1e3a8a;
                border: 1px solid #3b82f6;
                border-radius: 10px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, -4)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        cat_lbl = QLabel(category_name)
        cat_lbl.setStyleSheet("""
            color: #93c5fd;
            font-size: 11px;
            font-weight: 800;
            font-family: 'Segoe UI';
            padding: 4px 10px;
            letter-spacing: 1px;
            border-bottom: 1px solid #2563eb;
        """)
        layout.addWidget(cat_lbl)

        for item in items:
            btn = QPushButton(item)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 8px 14px;
                    color: #ffffff;
                    background: transparent;
                    border: none;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 600;
                    font-family: 'Segoe UI';
                }
                QPushButton:hover {
                    background-color: #2563eb;
                    color: #ffffff;
                }
                QPushButton:pressed {
                    background-color: #1d4ed8;
                }
            """)
            btn.clicked.connect(lambda checked, i=item: self.item_clicked(i))
            layout.addWidget(btn)

        self.adjustSize()
        self.hide()

    def item_clicked(self, item_name):
        self.on_item_click(item_name)
        self.hide()

    def leaveEvent(self, event):  # noqa: N802
        self.hide()
        super().leaveEvent(event)


# ==========================================
# FOOTER BÜYÜK MENÜ BUTONU (TEK İKONLU & YUKARI AÇILIR)
# Zemin Mavi (#1e3a8a), Yazılar Beyaz (#ffffff)
# ==========================================
class FooterMenuButton(QPushButton):
    def __init__(self, emoji, category_name, items, parent_window):
        # Eğer category_name içinde önceden emoji varsa temizle (çift ikon önleme)
        clean_name = category_name
        for e in ["📊", "👥", "📦", "📄", "🔄", "⚙️", "🏢", "🏷️", "💾", "🤝", "💵", "📝", "🛒"]:
            clean_name = clean_name.replace(e, "").strip()
        super().__init__(f"{emoji}  {clean_name}")
        self.emoji = emoji
        self.category_name = clean_name
        self.items = items
        self.main_window = parent_window
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(42)

        self.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                font-weight: 700;
                color: #ffffff;
                font-family: 'Segoe UI';
                background-color: #1e3a8a;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #2563eb;
                color: #ffffff;
                border-color: #60a5fa;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)

    def enterEvent(self, event):  # noqa: N802
        self.trigger_popup()
        super().enterEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        self.trigger_popup()
        super().mousePressEvent(event)

    def trigger_popup(self):
        global_pos = self.parentWidget().mapTo(self.main_window, self.pos())
        x = global_pos.x()
        y_bottom = global_pos.y()
        self.main_window.show_popup(self.category_name, self.items, x, y_bottom, open_upwards=True)


# Geriye dönük uyumluluk referansı
HoverMenuButton = FooterMenuButton


# ==========================================
# ANA SAYFA BÜYÜK MODÜL BUTONU (SAĞ VE SOL KLİK DESTEKLİ)
# Kural: Zemin Beyaz Kart İçinde Butonların İçi Mavi (#2563eb), Yazıları Beyaz (#ffffff)
# ==========================================
class GridModuleButton(QPushButton):
    def __init__(self, mod_name, mod_emoji, target_menu, parent_window):
        super().__init__()
        self.mod_name = mod_name
        self.mod_emoji = mod_emoji
        self.target_menu = target_menu
        self.main_window = parent_window
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(115, 96)

        self.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                border: 1px solid #1d4ed8;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
                border-color: #1e3a8a;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)

        btn_lyt = QVBoxLayout(self)
        btn_lyt.setContentsMargins(8, 8, 8, 8)
        btn_lyt.setSpacing(4)
        btn_lyt.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.emoji_lbl = QLabel(mod_emoji)
        self.emoji_lbl.setFont(QFont("Segoe UI", 24))
        self.emoji_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.emoji_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        btn_lyt.addWidget(self.emoji_lbl)

        self.name_lbl = QLabel(mod_name)
        self.name_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #ffffff; font-family: 'Segoe UI';")
        self.name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_lbl.setWordWrap(True)
        self.name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        btn_lyt.addWidget(self.name_lbl)

        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(8)
        sh.setColor(QColor(0, 0, 0, 30))
        sh.setOffset(0, 2)
        self.setGraphicsEffect(sh)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
        elif event.button() == Qt.MouseButton.RightButton:
            self.main_window.show_grid_module_context_menu(event.pos(), self.target_menu, self)
            event.accept()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.main_window.alt_menu_tiklandi(self.target_menu)
            super().mouseReleaseEvent(event)


# Placeholder Widgets for future tabs
class PlaceholderWidget(QWidget):
    def __init__(self, title_text, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel(title_text)
        lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(lbl)

        desc = QLabel(self.tr("Bu modül Faz planına göre bir sonraki aşamada aktif edilecektir."))
        desc.setFont(QFont("Segoe UI", 11))
        desc.setStyleSheet("color: #95a5a6;")
        layout.addWidget(desc)


class MainWindow(QMainWindow):
    """3 Dikey Bölümlü Ana Panel (Sol: Favori İşlemler, Orta: Favori Raporlar, Sağ: Ana İkonlar)

    ve Mavi/Beyaz Tasarım Kararlı Modern Kurumsal ERP Ana Penceresi.
    """

    log_signal = pyqtSignal(str)

    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
        self.active_popup = None
        self.favoriler = [self.tr("Ürün Yönetimi"), self.tr("Görevler"), self.tr("Teklif Yönetimi"), self.tr("Müşteriler & Cariler")]
        init_global_text_selection()

        self.menu_structure = {
            self.tr("GÖSTERGE"): ([self.tr("Ana Panel"), self.tr("Bildirimler")], "📊"),
            self.tr("CARİ"): ([self.tr("Müşteriler & Cariler"), self.tr("Cari Analiz")], "👥"),
            self.tr("STOK"): ([self.tr("Ürün Yönetimi"), self.tr("Fiyat Politikaları")], "📦"),
            self.tr("TEKLİF & SİPARİŞ"): ([self.tr("Teklif Yönetimi"), self.tr("Sipariş Yönetimi")], "📄"),
            self.tr("YEDEKLEME"): ([self.tr("Görevler")], "🔄"),
            self.tr("SİSTEM"): ([self.tr("Genel Ayarlar"), self.tr("İşlem Günlükleri")], "⚙️"),
        }

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(self.tr("Toya ERP"))
        self.resize(1480, 880)
        self.setStyleSheet("background-color: #f0f4f8;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ==========================================
        # 1. ÜST BAR (HEADER BAR)
        # ==========================================
        header_bar = QWidget()
        header_bar.setFixedHeight(56)
        header_bar.setStyleSheet("background-color: #0b1120;")

        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(18)

        self.logo = QLabel(self.tr("🏢 Toya ERP"))
        self.logo.setObjectName("pan.nav.logo")
        self.logo.setToolTip("[pan.nav.logo] Toya ERP Kurumsal Yönetim Platformu")
        self.logo.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff; font-family: 'Segoe UI';")
        header_layout.addWidget(self.logo)

        header_layout.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setObjectName("cmp.top.search")
        self.search_box.setToolTip("[cmp.top.search] Global Modül ve Kayıt Hızlı Arama (Ctrl+K)")
        self.search_box.setPlaceholderText(self.tr("🔍 Arama yap... (Ctrl+K)"))
        self.search_box.setMinimumWidth(280)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #1a2744;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 12px;
                color: white;
                font-size: 13px;
                font-family: 'Segoe UI';
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
        """)
        header_layout.addWidget(self.search_box)

        user_lbl = QLabel("👤 admin@baynet")
        user_lbl.setObjectName("sys.usr.001")
        user_lbl.setToolTip("[sys.usr.001] Oturum Açan Süper Yönetici Profili")
        user_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700; font-family: 'Segoe UI';")
        header_layout.addWidget(user_lbl)

        self.company_combo = QComboBox()
        self.company_combo.setObjectName("tan.cmp.001")
        self.company_combo.setToolTip("[tan.cmp.001] Aktif Şirket / Şube Seçimi")
        self.company_combo.setMinimumWidth(160)
        self.company_combo.setStyleSheet("""
            QComboBox {
                background-color: #1a2744;
                color: white;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
                font-family: 'Segoe UI';
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        header_layout.addWidget(self.company_combo)

        # Mimari Kodları Göster / Gizle Parametre Butonu
        self.btn_toggle_hints = QPushButton("🏷️ Kodlar: AÇIK")
        self.btn_toggle_hints.setObjectName("sys.cfg.hints")
        self.btn_toggle_hints.setCheckable(True)
        self.btn_toggle_hints.setChecked(True)
        self.btn_toggle_hints.setToolTip("[sys.cfg.hints] Standart Mimari Ekran ve Buton Kodlarını (act.* / cmp.*) Aç / Kapat")
        self.btn_toggle_hints.setStyleSheet("""
            QPushButton {
                background-color: #047857;
                color: #a7f3d0;
                border: 1px solid #10b981;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #059669;
                color: #ffffff;
            }
        """)
        self.btn_toggle_hints.clicked.connect(self.toggle_architecture_hints)
        header_layout.addWidget(self.btn_toggle_hints)

        btn_theme_settings = QPushButton("📐 " + self.tr("Grid & Tema"))
        btn_theme_settings.setObjectName("cmp.top.theme")
        btn_theme_settings.setToolTip("[cmp.top.theme] AppGrid Tema, Renk ve Satır Yüksekliği Ayarları")
        btn_theme_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_theme_settings.setStyleSheet("""
            QPushButton {
                background-color: #1e3a8a;
                color: #bfdbfe;
                border: 1px solid #3b82f6;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #2563eb;
                color: #ffffff;
            }
        """)
        btn_theme_settings.clicked.connect(self._open_theme_settings_dialog)
        header_layout.addWidget(btn_theme_settings)

        help_btn = QPushButton("❓")
        help_btn.setObjectName("cmp.top.help")
        help_btn.setToolTip("[cmp.top.help] Kullanıcı Kılavuzu & Yardım Dokümantasyonu")
        help_btn.setFixedSize(36, 36)
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a2744;
                border: none;
                border-radius: 18px;
                font-size: 14px;
                color: white;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        help_btn.clicked.connect(lambda: self.show_toast(self.tr("Kullanıcı kılavuzu ve yardım paneli yükleniyor..."), "info"))
        header_layout.addWidget(help_btn)

        main_layout.addWidget(header_bar)

        # ==========================================
        # 2. DİNAMİK SEKMELİ EKRAN ALANI & ESNEK FLEXBOX / SPLITTER ANA PANEL
        # ==========================================
        self.dashboard_container = QWidget()
        dash_main_vlyt = QVBoxLayout(self.dashboard_container)
        dash_main_vlyt.setContentsMargins(16, 16, 16, 16)
        dash_main_vlyt.setSpacing(12)

        # QSplitter ile serbestçe boyutlandırılabilen Flexbox Gövde (Resim 1 & 2)
        self.dash_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.dash_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #cbd5e1;
                width: 6px;
                margin: 4px 2px;
                border-radius: 3px;
            }
            QSplitter::handle:hover {
                background-color: #2563eb;
            }
        """)

        # 1. Sol: Favori İşlemler Widget'ı
        self.fav_widget = FavoriteActionsWidget(favorites=self.favoriler, parent=self)
        self.fav_widget.module_selected.connect(self.alt_menu_tiklandi)
        self.fav_widget.quick_action_triggered.connect(self.alt_menu_tiklandi)
        self.dash_splitter.addWidget(self.fav_widget)

        # 2. Sağ: Ana Menüler Modül Gridi Widget'ı
        self.menu_grid_widget = MenuGridWidget(parent=self)
        self.menu_grid_widget.module_selected.connect(self.alt_menu_tiklandi)
        self.menu_grid_widget.module_right_clicked.connect(
            lambda mod, pos: self.show_grid_module_context_menu(pos, mod, self),
        )
        self.menu_grid_widget.log_action_requested.connect(
            lambda: self.open_module_in_tab(self.tr("İşlem Günlükleri")),
        )
        self.dash_splitter.addWidget(self.menu_grid_widget)

        # Splitter Genişlik Oranlarını QSettings'ten Yükle / Kaydet
        self.dash_settings = QSettings("ToyaERP", "DashboardSettings")
        saved_sizes = self.dash_settings.value("dashboard/splitter_sizes", None)
        if saved_sizes:
            try:
                self.dash_splitter.setSizes([int(s) for s in saved_sizes])
            except Exception:
                self.dash_splitter.setSizes([380, 800])
        else:
            self.dash_splitter.setSizes([380, 800])

        self.dash_splitter.splitterMoved.connect(
            lambda: self.dash_settings.setValue("dashboard/splitter_sizes", self.dash_splitter.sizes()),
        )

        dash_main_vlyt.addWidget(self.dash_splitter, 1)

        # Geriye dönük uyumluluk için referanslar
        self.fav_screens_list = self.fav_widget.list_widget
        self.fav_count_badge = self.fav_widget.badge_count

        # ----------------------------------------------------
        # QTabWidget Ana Kapsayıcı
        # ----------------------------------------------------
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.tab_changed)

        # Tab 0: Sabit ve Kapatılamaz Dashboard
        self.tab_widget.addTab(self.dashboard_container, "🏠 " + self.tr("Ana Panel"))
        self.tab_widget.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.tab_widget.tabBar().setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)

        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #f0f4f8;
            }
            QTabBar::tab {
                background-color: #e2e8f0;
                color: #475569;
                font-weight: 600;
                font-family: 'Segoe UI';
                font-size: 11px;
                padding: 6px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
                min-height: 22px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #2563eb;
                border-bottom: 2px solid #2563eb;
                font-weight: 700;
            }
            QTabBar::tab:hover:!selected {
                background-color: #cbd5e1;
                color: #1e293b;
            }
        """)
        main_layout.addWidget(self.tab_widget, 1)

        # ==========================================
        # 2.5. FOOTER ÜSTÜ AÇILIR/KAPANIR HIZLI ERİŞİM BANDI (QuickTilesBarWidget - Resim 2)
        # ==========================================
        self.quick_tiles_bar = QuickTilesBarWidget(parent=self)
        self.quick_tiles_bar.tile_clicked.connect(self.alt_menu_tiklandi)
        main_layout.addWidget(self.quick_tiles_bar)

        # ==========================================
        # 3. BÜYÜK MODÜL MENÜLERİ VE DURUM ÇUBUĞU (FOOTER BAR)
        # ==========================================
        self.footer_bar = QFrame()
        self.footer_bar.setObjectName("pan.nav.footer")
        self.footer_bar.setFixedHeight(56)
        self.footer_bar.setStyleSheet("""
            QFrame#pan.nav.footer, QFrame {
                background-color: #0b1120;
                color: #94a3b8;
                border-top: 1px solid #1e293b;
            }
        """)
        footer_layout = QHBoxLayout(self.footer_bar)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        footer_layout.setSpacing(10)

        # Footer Menü Butonları (Büyük, Tek İkonlu ve Belirgin)
        self.menu_buttons = []
        for category_name, (sub_items, emoji) in self.menu_structure.items():
            btn = FooterMenuButton(emoji, category_name, sub_items, self)
            footer_layout.addWidget(btn)
            self.menu_buttons.append(btn)

        # Geriye dönük uyumluluk referansı
        self.menu_bar = self.footer_bar

        footer_layout.addStretch()

        # Sistem Durum Rozeti
        status_badge = QLabel("🟢 " + self.tr("Sistem Aktif"))
        status_badge.setStyleSheet("color: #34d399; font-size: 11px; font-weight: 700; font-family: 'Segoe UI'; padding-right: 12px;")
        footer_layout.addWidget(status_badge)

        # Canlı Saat & Tarih
        self.live_time_label = QLabel()
        self.live_time_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #38bdf8; font-family: 'Segoe UI';")
        footer_layout.addWidget(self.live_time_label)

        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_live_time)
        self.time_timer.start(1000)
        self.update_live_time()

        main_layout.addWidget(self.footer_bar)

        self.update_favorites_ui()

        self.ctrl_k = QShortcut(QKeySequence("Ctrl+K"), self)
        self.ctrl_k.activated.connect(self.focus_search)

        # Şirketleri yükle ve dinle
        self.load_companies()

        # Log Altyapısı
        self.setup_live_logs()

    def setup_live_logs(self):
        self.qt_log_handler = QtLogHandler(self.log_signal)
        self.qt_log_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
        logging.getLogger().addHandler(self.qt_log_handler)
        self.log_signal.connect(self.append_log)

    def closeEvent(self, event):  # noqa: N802
        if hasattr(self, "time_timer") and self.time_timer.isActive():
            self.time_timer.stop()
        if hasattr(self, "qt_log_handler"):
            try:
                logging.getLogger().removeHandler(self.qt_log_handler)
            except Exception:
                pass
        super().closeEvent(event)

    def append_log(self, message):
        pass

    def show_popup(self, category_name, items, x, y_bottom, open_upwards=True):
        if self.active_popup:
            self.active_popup.close()
        self.active_popup = MenuPopup(self, category_name, items, self.alt_menu_tiklandi)
        self.active_popup.adjustSize()
        popup_height = self.active_popup.sizeHint().height()

        if open_upwards:
            # Footer'ın hemen üzerinde açılır
            y = max(10, y_bottom - popup_height - 6)
        else:
            y = y_bottom

        self.active_popup.move(x, y)
        self.active_popup.show()
        self.active_popup.raise_()

    def show_toast(self, message, notification_type="info"):
        toast = ToastNotification(self, message, notification_type)
        toast.show_toast()

    def focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def toggle_architecture_hints(self, checked):
        if checked:
            self.btn_toggle_hints.setText("🏷️ Kodlar: AÇIK")
            self.btn_toggle_hints.setStyleSheet("""
                QPushButton {
                    background-color: #047857;
                    color: #a7f3d0;
                    border: 1px solid #10b981;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.show_toast(self.tr("🏷️ Standart mimari kod ve ipucu gösterimi AÇILDI."), "success")
        else:
            self.btn_toggle_hints.setText("🏷️ Kodlar: KAPALI")
            self.btn_toggle_hints.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #94a3b8;
                    border: 1px solid #475569;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.show_toast(self.tr("🏷️ Mimari kod gösterimi KAPATILDI (Kullanıcı Modu)."), "warning")

    def _open_theme_settings_dialog(self):
        self.open_module_in_tab(self.tr("Ekran & Grid Tanımları"))

    def update_live_time(self):
        self.live_time_label.setText(datetime.datetime.now().strftime("🕒 %d.%m.%Y %H:%M:%S"))

    def alt_menu_tiklandi(self, menu_name):
        self.open_module_in_tab(menu_name)

    def open_module_in_tab(self, menu_name):
        SCREEN_CODES = {
            self.tr("Teklif Yönetimi"): "📄 [isl.quo.001] " + self.tr("Teklif Yönetimi"),
            self.tr("Teklifler"): "📄 [isl.quo.001] " + self.tr("Teklif Yönetimi"),
            self.tr("Sipariş Yönetimi"): "🛒 [isl.ord.001] " + self.tr("Sipariş Yönetimi"),
            self.tr("Siparişler"): "🛒 [isl.ord.001] " + self.tr("Sipariş Yönetimi"),
            self.tr("Müşteriler & Cariler"): "👥 [tan.car.001] " + self.tr("Müşteriler & Cariler"),
            self.tr("Cari Listesi (AppGrid)"): "📐 [app.grd.001] " + self.tr("Cari Listesi (AppGrid)"),
            self.tr("Ekran & Grid Tanımları"): "📐 [sys.grd.001] " + self.tr("Ekran & Grid Tanımları"),
            self.tr("Ürün Yönetimi"): "🏷️ [tan.stk.001] " + self.tr("Ürün & Stok Yönetimi"),
            self.tr("Görevler"): "💾 [isl.tsk.001] " + self.tr("Görevler & İş Emirleri"),
            self.tr("Genel Ayarlar"): "⚙️ [sys.set.001] " + self.tr("Genel Ayarlar"),
            self.tr("İşlem Günlükleri"): "📝 [sys.log.001] " + self.tr("İşlem Günlükleri"),
            self.tr("Cari Analiz"): "📊 [rpt.car.001] " + self.tr("Cari Analiz"),
            self.tr("Fiyat Politikaları"): "💵 [tan.prc.001] " + self.tr("Fiyat Politikaları"),
            self.tr("Pazaryeri Bağlantıları"): "🤝 [int.mkt.001] " + self.tr("Pazaryeri Bağlantıları"),
        }
        tab_title = SCREEN_CODES.get(menu_name, f"📌 {menu_name}")

        # Eğer sekme zaten açıksa ona odaklan
        for idx in range(1, self.tab_widget.count()):
            t_text = self.tab_widget.tabText(idx)
            if menu_name in t_text or tab_title == t_text:
                self.tab_widget.setCurrentIndex(idx)
                return

        # Yeni sekme için widget oluştur
        new_widget = None
        company_id = self.company_combo.currentData()

        if menu_name in (self.tr("Görevler"), self.tr("Aktif Görevler"), self.tr("Yedekleme")):
            new_widget = BackupWidget(self.db)
        elif menu_name in (
            "Stok", "Stok Kartları", "Stok Yönetimi", "Ürün Yönetimi", "Stok Uyarısı",
            self.tr("Stok"), self.tr("Stok Kartları"), self.tr("Stok Yönetimi"),
            self.tr("Ürün Yönetimi"), self.tr("Stok Uyarısı"),
        ):
            new_widget = StokListScreen(
                db_session=self.db,
                company_id=company_id,
                parent=self,
            )
            new_widget.toast_requested.connect(self.show_toast)
        elif menu_name in (self.tr("Genel Ayarlar"), self.tr("Sistem Ayarları")):
            new_widget = SettingsWidget(self.db)
        elif menu_name == self.tr("Ekran & Grid Tanımları"):
            from src.desktop.ui.screen_definitions_manager import (
                ScreenDefinitionsManagerWidget,
            )
            new_widget = ScreenDefinitionsManagerWidget(self)
        elif menu_name in (self.tr("Cari Listesi (AppGrid)"), self.tr("AppGrid Demo")):
            from src.desktop.ui.demo_appgrid_screen import AppGridCariDemoScreen
            new_widget = AppGridCariDemoScreen(self)
        elif menu_name in (
            "Cari", "Müşteriler & Cariler", "Cari Bakiye", "Müşteriler",
            self.tr("Cari"), self.tr("Müşteriler & Cariler"), self.tr("Cari Bakiye"), self.tr("Müşteriler"),
        ):
            new_widget = CariListScreen(
                db_session=self.db,
                company_id=company_id,
                parent=self,
            )
            new_widget.toast_requested.connect(self.show_toast)
        elif menu_name in (self.tr("Teklif Yönetimi"), self.tr("Teklifler"), self.tr("Açık Teklifler"), self.tr("Yeni Teklif Hazırla")):
            from src.desktop.ui.quotations import QuotationsWidget
            new_widget = QuotationsWidget(self.db)
        elif menu_name in (self.tr("Sipariş Yönetimi"), self.tr("Siparişler"), self.tr("Bekleyen Sipariş")):
            from src.desktop.ui.quotations import OrdersWidget
            new_widget = OrdersWidget(self.db)
        elif menu_name in (self.tr("Faturalar"), self.tr("Hızlı Fatura"), self.tr("Bugün Ciro")):
            from src.desktop.ui.quotations import QuotationsWidget
            new_widget = QuotationsWidget(self.db, quotation_type="Invoice")
        else:
            new_widget = PlaceholderWidget(f"{menu_name} {self.tr('Modülü')}")

        if new_widget:
            new_idx = self.tab_widget.addTab(new_widget, tab_title)
            self.tab_widget.setCurrentIndex(new_idx)

    def close_tab(self, index):
        if index <= 0:
            return  # Sabit Dashboard kapatılamaz
        self.tab_widget.removeTab(index)

    def tab_changed(self, index):
        if index <= 0:
            self.logo.setText(self.tr("🏢 Toya ERP"))
            self.setWindowTitle(self.tr("Toya ERP"))
        else:
            tab_text = self.tab_widget.tabText(index)
            self.logo.setText(f"🏢 Toya ERP | {tab_text}")
            self.setWindowTitle(f"Toya ERP | {tab_text}")

    # Favori Yönetimi
    def favoriye_ekle(self, menu_name):
        if menu_name not in self.favoriler:
            self.favoriler.append(menu_name)
            self.update_favorites_ui()
            self.show_toast(f"'{menu_name}' {self.tr('favorilere eklendi.')}", "success")

    def favoriden_cikar(self, menu_name):
        clean_name = menu_name.split("  ")[-1].strip() if "  " in menu_name else menu_name.strip()
        if clean_name in self.favoriler:
            self.favoriler.remove(clean_name)
            self.update_favorites_ui()
            self.show_toast(f"'{clean_name}' {self.tr('favorilerden çıkarıldı.')}", "warning")
        elif menu_name in self.favoriler:
            self.favoriler.remove(menu_name)
            self.update_favorites_ui()
            self.show_toast(f"'{menu_name}' {self.tr('favorilerden çıkarıldı.')}", "warning")

    def update_favorites_ui(self):
        self.fav_screens_list.clear()
        SCREEN_ICONS = {
            "Teklif Yönetimi": "📄",
            "Sipariş Yönetimi": "🛒",
            "Müşteriler & Cariler": "👥",
            "Ürün Yönetimi": "📦",
            "Görevler": "💾",
            "Genel Ayarlar": "⚙️",
            "İşlem Günlükleri": "📝",
            "Pazaryeri Bağlantıları": "🤝",
            "Fiyat Politikaları": "💵",
            "Cari Analiz": "📊",
        }
        for fav in self.favoriler:
            icon = SCREEN_ICONS.get(fav, "⭐")
            item = QListWidgetItem(f"{icon}  {fav}")
            item.setData(Qt.ItemDataRole.UserRole, fav)
            self.fav_screens_list.addItem(item)

        if hasattr(self, "fav_count_badge"):
            self.fav_count_badge.setText(str(len(self.favoriler)))

    def create_styled_menu(self):
        """Kurala uygun mavi zeminli, beyaz yazılı sağ tık menüsü üretir."""
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLESHEET)
        return menu

    def show_grid_module_context_menu(self, pos, target_menu, sender_btn):
        menu = self.create_styled_menu()
        is_fav = target_menu in self.favoriler
        if not is_fav:
            add_action = QAction(self.tr("⭐ Favorilere Ekle"), self)
            add_action.triggered.connect(lambda: self.favoriye_ekle(target_menu))
            menu.addAction(add_action)
        else:
            remove_action = QAction(self.tr("❌ Favorilerden Çıkar"), self)
            remove_action.triggered.connect(lambda: self.favoriden_cikar(target_menu))
            menu.addAction(remove_action)
        menu.exec(sender_btn.mapToGlobal(pos))

    def show_favorites_context_menu(self, pos):
        item = self.fav_screens_list.itemAt(pos)
        if item:
            menu = self.create_styled_menu()
            target_text = item.data(Qt.ItemDataRole.UserRole) or item.text()
            remove_action = QAction(self.tr("❌ Favorilerden Çıkar"), self)
            remove_action.triggered.connect(lambda: self.favoriden_cikar(target_text))
            menu.addAction(remove_action)
            menu.exec(QCursor.pos())

    def load_companies(self):
        self.company_combo.clear()
        try:
            companies = self.db.query(Site).filter(Site.is_active == True).all()
            for comp in companies:
                self.company_combo.addItem(comp.name, comp.id)
        except Exception:
            pass
        self.company_combo.currentIndexChanged.connect(self.on_company_changed)

    def on_company_changed(self):
        # Şirket değiştiğinde tüm açık modül sekmelerini temizle
        while self.tab_widget.count() > 1:
            self.tab_widget.removeTab(1)
        self.tab_widget.setCurrentIndex(0)
