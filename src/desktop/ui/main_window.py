import logging
import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QPushButton,
    QLabel, QComboBox, QFormLayout, QLineEdit, QGridLayout,
    QGraphicsDropShadowEffect, QScrollArea, QTabWidget, QListWidget, QMenu, QGroupBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QKeySequence, QShortcut, QAction, QCursor

from src.desktop.ui.sites import SitesWidget
from src.desktop.ui.resources import ResourcesWidget
from src.desktop.ui.backup import BackupWidget
from src.desktop.ui.customers import MusteriYonetimiWidget


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
# MODERN TOAST BİLDİRİM SİSTEMİ (PyQt6 Uyumlu)
# ==========================================
class ToastNotification(QFrame):
    def __init__(self, parent, message, notification_type="info"):
        super().__init__(parent)
        self.parent_widget = parent
        self.message = message
        self.type = notification_type
        
        bg_colors = {
            "success": "#10b981",
            "warning": "#f59e0b",
            "error": "#ef4444",
            "info": "#3b82f6"
        }
        bg_color = bg_colors.get(notification_type, "#1e293b")
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                color: white;
                border-radius: 8px;
                padding: 12px 20px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        
        icon_emoji = "ℹ️"
        if notification_type == "success":
            icon_emoji = "✅"
        elif notification_type == "warning":
            icon_emoji = "⚠️"
        elif notification_type == "error":
            icon_emoji = "❌"
            
        icon_lbl = QLabel(icon_emoji)
        icon_lbl.setFont(QFont("Segoe UI", 12))
        layout.addWidget(icon_lbl)
        
        msg_lbl = QLabel(message)
        msg_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        layout.addWidget(msg_lbl)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        self.adjustSize()
        
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(400)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)
        
    def show_toast(self):
        parent_rect = self.parent_widget.rect()
        start_x = parent_rect.width() - self.width() - 24
        start_y = parent_rect.height()
        end_y = parent_rect.height() - self.height() - 40
        
        self.move(start_x, start_y)
        self.show()
        
        self.anim.setStartValue(QPoint(start_x, start_y))
        self.anim.setEndValue(QPoint(start_x, end_y))
        self.anim.start()
        
        self.timer.start(3000)
        
    def fade_out(self):
        parent_rect = self.parent_widget.rect()
        dest_x = self.x()
        dest_y = parent_rect.height()
        
        self.anim.setStartValue(QPoint(self.x(), self.y()))
        self.anim.setEndValue(QPoint(dest_x, dest_y))
        self.anim.finished.connect(self.deleteLater)
        self.anim.start()


# ==========================================
# HOVER İLE AÇILAN ALT POPUP MENÜ
# ==========================================
class MenuPopup(QFrame):
    def __init__(self, parent, category_name, items, on_item_click):
        super().__init__(parent)
        self.parent_widget = parent
        self.on_item_click = on_item_click
        
        self.setStyleSheet("""
            QFrame {
                background-color: #0b1120;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        cat_lbl = QLabel(category_name)
        cat_lbl.setStyleSheet("""
            color: #64748b;
            font-size: 10px;
            font-weight: 700;
            font-family: 'Segoe UI';
            padding: 4px 8px;
            letter-spacing: 1px;
        """)
        layout.addWidget(cat_lbl)
        
        for item in items:
            btn = QPushButton(item)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 8px 16px;
                    color: #e2e8f0;
                    background: transparent;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: 500;
                    font-family: 'Segoe UI';
                }
                QPushButton:hover {
                    background-color: #2563eb;
                    color: white;
                }
            """)
            btn.clicked.connect(lambda checked, i=item: self.item_clicked(i))
            layout.addWidget(btn)
            
        self.adjustSize()
        self.hide()
        
    def item_clicked(self, item_name):
        self.on_item_click(item_name)
        self.hide()

    def leaveEvent(self, event):
        self.hide()
        super().leaveEvent(event)


# ==========================================
# HOVER TETİKLEMELİ YATAY MENÜ BUTONU
# ==========================================
class HoverMenuButton(QPushButton):
    def __init__(self, emoji, category_name, items, parent_window):
        super().__init__(emoji)
        self.category_name = category_name
        self.items = items
        self.main_window = parent_window
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(56, 44)
        
        self.setStyleSheet("""
            QPushButton {
                font-size: 20px;
                background-color: transparent;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        
    def enterEvent(self, event):
        global_pos = self.parentWidget().mapTo(self.main_window, self.pos())
        x = global_pos.x()
        y = global_pos.y() + self.height() + 2
        
        self.main_window.show_popup(self.category_name, self.items, x, y)
        super().enterEvent(event)


# ==========================================
# ANA SAYFA BÜYÜK MODÜL BUTONU (SAĞ KLİK DESTEKLİ)
# ==========================================
class GridModuleButton(QPushButton):
    def __init__(self, mod_name, mod_emoji, target_menu, parent_window):
        super().__init__()
        self.mod_name = mod_name
        self.mod_emoji = mod_emoji
        self.target_menu = target_menu
        self.main_window = parent_window
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(125, 105)
        
        self.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #eff6ff;
                border-color: #3b82f6;
            }
            QPushButton:pressed {
                background-color: #dbeafe;
            }
        """)
        
        btn_lyt = QVBoxLayout(self)
        btn_lyt.setContentsMargins(10, 10, 10, 10)
        btn_lyt.setSpacing(4)
        btn_lyt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.emoji_lbl = QLabel(mod_emoji)
        self.emoji_lbl.setFont(QFont("Segoe UI", 26))
        self.emoji_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_lyt.addWidget(self.emoji_lbl)
        
        self.name_lbl = QLabel(mod_name)
        self.name_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #334155; font-family: 'Segoe UI';")
        self.name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_lyt.addWidget(self.name_lbl)
        
        sh = QGraphicsDropShadowEffect()
        sh.setBlurRadius(8)
        sh.setColor(QColor(0, 0, 0, 8))
        sh.setOffset(0, 2)
        self.setGraphicsEffect(sh)
        
    def contextMenuEvent(self, event):
        self.main_window.show_grid_module_context_menu(event.pos(), self.target_menu, self)
        event.accept()


# Placeholder Widgets for the new tabs
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


class SettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        
        title = QLabel(self.tr("Genel Ayarlar"))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; margin-bottom: 20px;")
        layout.addWidget(title)
        
        form_group = QGroupBox(self.tr("Uygulama Tercihleri"))
        form_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        form_layout = QFormLayout(form_group)
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Türkçe (TR)", "tr")
        self.lang_combo.addItem("English (EN)", "en")
        
        form_layout.addRow(self.tr("Arayüz Dili:"), self.lang_combo)
        
        layout.addWidget(form_group)
        layout.addStretch()


class MainWindow(QMainWindow):
    """DIA/Hızlı Erişim tasarımına sadık, zengin sekmeli ve favori yönetimli modern ana pencere."""

    log_signal = pyqtSignal(str)

    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
        self.active_popup = None
        self.favoriler = [self.tr("Ürün Yönetimi"), self.tr("Görevler")]
        
        self.menu_structure = {
            self.tr("📊 GÖSTERGE"): ([self.tr("Ana Panel"), self.tr("Bildirimler")], "📊"),
            self.tr("👥 CARİ"): ([self.tr("Müşteriler & Cariler"), self.tr("Cari Analiz")], "👥"),
            self.tr("📦 STOK"): ([self.tr("Ürün Yönetimi"), self.tr("Fiyat Politikaları")], "📦"),
            self.tr("🔄 YEDEKLEME"): ([self.tr("Görevler"), self.tr("Pazaryeri Bağlantıları")], "🔄"),
            self.tr("⚙️ SİSTEM"): ([self.tr("Genel Ayarlar"), self.tr("İşlem Günlükleri")], "⚙️")
        }
        
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(self.tr("Multi-Mecra Entegre Yönetim ve Yedekleme Platformu"))
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
        header_layout.setSpacing(20)
        
        logo = QLabel(self.tr("🏢 Multi-CMS Plus"))
        logo.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff; font-family: 'Segoe UI';")
        header_layout.addWidget(logo)
        
        header_layout.addStretch()
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(self.tr("🔍 Arama yap... (Ctrl+K)"))
        self.search_box.setMinimumWidth(280)
        self.search_box.setStyleSheet("""
            QLineEdit {
                background-color: #1a2744;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
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
        user_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700; font-family: 'Segoe UI';")
        header_layout.addWidget(user_lbl)
        
        self.company_combo = QComboBox()
        self.company_combo.addItems([self.tr("Baynet Teknik A.Ş."), self.tr("Kozmos Yazılım Ltd.")])
        self.company_combo.setMinimumWidth(180)
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
        
        help_btn = QPushButton("❓")
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
        # 2. YATAY İKON MENÜSÜ (NAVBAR BAR)
        # ==========================================
        self.menu_bar = QWidget()
        self.menu_bar.setFixedHeight(48)
        self.menu_bar.setStyleSheet("background-color: #1a2744;")
        
        menu_layout = QHBoxLayout(self.menu_bar)
        menu_layout.setContentsMargins(20, 0, 20, 0)
        menu_layout.setSpacing(12)
        
        for category_name, (sub_items, emoji) in self.menu_structure.items():
            btn = HoverMenuButton(emoji, category_name, sub_items, self)
            menu_layout.addWidget(btn)
            
        menu_layout.addStretch()
        grid_title_menu = QLabel(self.tr("🎛️ Modül Kataloğu (Favorilere eklemek/çıkarmak için sağ tıklayın)"))
        grid_title_menu.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 700; font-family: 'Segoe UI';")
        menu_layout.addWidget(grid_title_menu)
        main_layout.addWidget(self.menu_bar)

        # ==========================================
        # 3. DİNAMİK SEKMELİ EKRAN ALANI (QTabWidget)
        # ==========================================
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.tab_changed)
        self.tab_widget.setVisible(False)
        
        self.tab_widget.setStyleSheet("""
            QTabWidget::panel {
                border: none;
                background-color: #f0f4f8;
            }
            QTabBar::tab {
                background-color: #e2e8f0;
                color: #64748b;
                font-weight: 600;
                font-family: 'Segoe UI';
                font-size: 12px;
                padding: 10px 20px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #2563eb;
                border-bottom: 3px solid #2563eb;
            }
            QTabBar::tab:hover {
                background-color: #cbd5e1;
            }
        """)
        main_layout.addWidget(self.tab_widget, 1)

        # ==========================================
        # 4. ANA SAYFA / DIA TARZI GRID MENÜ + FAVORİLER
        # ==========================================
        self.dashboard_container = QScrollArea()
        self.dashboard_container.setWidgetResizable(True)
        self.dashboard_container.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        dash_scroll_content = QWidget()
        dash_scroll_content.setStyleSheet("background: transparent;")
        self.dash_layout = QVBoxLayout(dash_scroll_content)
        self.dash_layout.setContentsMargins(32, 24, 32, 24)
        self.dash_layout.setSpacing(20)
        
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(14)
        
        modules = [
            (self.tr("Görevler"), "💾", "Görevler"),
            (self.tr("Ürün Yönetimi"), "📦", "Ürün Yönetimi"),
            (self.tr("Pazaryeri Bağlantıları"), "🤝", "Pazaryeri Bağlantıları"),
            (self.tr("Müşteriler & Cariler"), "👥", "Müşteriler & Cariler"),
            (self.tr("Fiyat Politikaları"), "💵", "Fiyat Politikaları"),
            (self.tr("Genel Ayarlar"), "⚙️", "Genel Ayarlar"),
            (self.tr("İşlem Günlükleri"), "📝", "İşlem Günlükleri"),
        ]
        
        cols_count = 6
        for idx, (mod_name, mod_emoji, target_menu) in enumerate(modules):
            mod_btn = GridModuleButton(mod_name, mod_emoji, target_menu, self)
            mod_btn.clicked.connect(lambda checked, t=target_menu: self.alt_menu_tiklandi(t))
            self.grid_layout.addWidget(mod_btn, idx // cols_count, idx % cols_count)
            
        self.dash_layout.addLayout(self.grid_layout)
        self.dash_layout.addStretch() # Grid'in hemen altına boşluk ekleyerek favorileri en dibe yaslıyoruz.
        
        # Favoriler Bölümü
        fav_layout = QHBoxLayout()
        fav_layout.setSpacing(20)
        
        fav_screens_frame = QFrame()
        fav_screens_frame.setStyleSheet("background-color: white; border-radius: 12px; border: 1px solid #e2e8f0;")
        shadow_fs = QGraphicsDropShadowEffect()
        shadow_fs.setBlurRadius(8)
        shadow_fs.setColor(QColor(0, 0, 0, 10))
        shadow_fs.setOffset(0, 2)
        fav_screens_frame.setGraphicsEffect(shadow_fs)
        
        fs_layout = QVBoxLayout(fav_screens_frame)
        fs_title = QLabel(self.tr("⭐ Favori Ekranlar"))
        fs_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #0f172a; font-family: 'Segoe UI'; border-bottom: 2px solid #f1f5f9; padding-bottom: 6px;")
        fs_layout.addWidget(fs_title)
        
        self.fav_screens_list = QListWidget()
        self.fav_screens_list.setStyleSheet("QListWidget { border: none; font-size: 12px; color: #334155; } QListWidget::item { padding: 6px 0px; }")
        self.fav_screens_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.fav_screens_list.customContextMenuRequested.connect(self.show_favorites_context_menu)
        self.fav_screens_list.itemClicked.connect(lambda item: self.alt_menu_tiklandi(item.text()))
        fs_layout.addWidget(self.fav_screens_list)
        
        fav_reports_frame = QFrame()
        fav_reports_frame.setStyleSheet("background-color: white; border-radius: 12px; border: 1px solid #e2e8f0;")
        shadow_fr = QGraphicsDropShadowEffect()
        shadow_fr.setBlurRadius(8)
        shadow_fr.setColor(QColor(0, 0, 0, 10))
        shadow_fr.setOffset(0, 2)
        fav_reports_frame.setGraphicsEffect(shadow_fr)
        
        fr_layout = QVBoxLayout(fav_reports_frame)
        fr_title = QLabel(self.tr("📊 Favori Raporlar"))
        fr_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #0f172a; font-family: 'Segoe UI'; border-bottom: 2px solid #f1f5f9; padding-bottom: 6px;")
        fr_layout.addWidget(fr_title)
        
        self.fav_reports_list = QListWidget()
        self.fav_reports_list.setStyleSheet("QListWidget { border: none; font-size: 12px; color: #334155; } QListWidget::item { padding: 6px 0px; }")
        self.fav_reports_list.addItems([self.tr("Günlük Sipariş Analizi Raporu"), self.tr("Veritabanı Sağlık Durum Raporu")])
        self.fav_reports_list.itemClicked.connect(lambda item: self.show_toast(f"'{item.text()}' {self.tr('raporu yükleniyor...')}", "info"))
        fr_layout.addWidget(self.fav_reports_list)
        
        fav_layout.addWidget(fav_screens_frame)
        fav_layout.addWidget(fav_reports_frame)
        self.dash_layout.addLayout(fav_layout)
        
        self.dashboard_container.setWidget(dash_scroll_content)
        main_layout.addWidget(self.dashboard_container, 1)

        # ==========================================
        # 🏢 GÜNCEL TARİH / SAAT DURUM ÇUBUĞU (FOOTER BAR)
        # ==========================================
        self.footer_bar = QFrame()
        self.footer_bar.setFixedHeight(30)
        self.footer_bar.setStyleSheet("""
            QFrame {
                background-color: #0b1120;
                color: #94a3b8;
                border-top: 1px solid #1e293b;
            }
        """)
        footer_layout = QHBoxLayout(self.footer_bar)
        footer_layout.setContentsMargins(16, 0, 16, 0)
        
        footer_info = QLabel(self.tr("🏢 Multi-CMS Management Platform | Pair Programming Session"))
        footer_info.setStyleSheet("font-size: 11px; font-weight: 500; font-family: 'Segoe UI';")
        footer_layout.addWidget(footer_info)
        footer_layout.addStretch()
        
        self.live_time_label = QLabel()
        self.live_time_label.setStyleSheet("font-size: 11px; font-weight: 700; color: #38bdf8; font-family: 'Segoe UI';")
        footer_layout.addWidget(self.live_time_label)
        
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_live_time)
        self.time_timer.start(1000)
        self.update_live_time()
        
        main_layout.addWidget(self.footer_bar)
        self.update_favorites_ui()
        
        self.ctrl_k = QShortcut(QKeySequence("Ctrl+K"), self)
        self.ctrl_k.activated.connect(self.focus_search)

        # Modül sayfaları ön yükleme
        self.backup_page = BackupWidget(self.db)
        self.products_page = ResourcesWidget(self.db)
        self.connections_page = SitesWidget(self.db)
        self.settings_page = SettingsWidget()

        # Log Altyapısı
        self.setup_live_logs()

    def setup_live_logs(self):
        handler = QtLogHandler(self.log_signal)
        handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
        logging.getLogger().addHandler(handler)
        self.log_signal.connect(self.append_log)

    def append_log(self, message):
        pass # Sekme logu veya toast için kullanılabilir

    def show_popup(self, category_name, items, x, y):
        if self.active_popup:
            self.active_popup.close()
        self.active_popup = MenuPopup(self, category_name, items, self.alt_menu_tiklandi)
        self.active_popup.move(x, y)
        self.active_popup.show()

    def show_toast(self, message, notification_type="info"):
        toast = ToastNotification(self, message, notification_type)
        toast.show_toast()

    def focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def update_live_time(self):
        self.live_time_label.setText(datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"))

    def alt_menu_tiklandi(self, menu_name):
        self.open_module_in_tab(menu_name)

    def open_module_in_tab(self, menu_name):
        # Eğer sekme zaten açıksa ona odaklan
        for idx in range(self.tab_widget.count()):
            if self.tab_widget.tabText(idx) == menu_name:
                self.tab_widget.setCurrentIndex(idx)
                self.tab_widget.setVisible(True)
                self.dashboard_container.setVisible(False)
                return
                
        # Yeni sekme için widget oluştur
        new_widget = None
        if menu_name == self.tr("Görevler"):
            new_widget = self.backup_page
        elif menu_name == self.tr("Ürün Yönetimi"):
            new_widget = self.products_page
        elif menu_name == self.tr("Pazaryeri Bağlantıları"):
            new_widget = self.connections_page
        elif menu_name == self.tr("Genel Ayarlar"):
            new_widget = self.settings_page
        elif menu_name == self.tr("Müşteriler & Cariler"):
            new_widget = MusteriYonetimiWidget(self.db)
            new_widget.toast_requested.connect(self.show_toast)
        else:
            new_widget = PlaceholderWidget(f"{menu_name} {self.tr('Modülü')}")
            
        if new_widget:
            self.tab_widget.addTab(new_widget, menu_name)
            self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)
            self.tab_widget.setVisible(True)
            self.dashboard_container.setVisible(False)

    def close_tab(self, index):
        self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            self.tab_widget.setVisible(False)
            self.dashboard_container.setVisible(True)

    def tab_changed(self, index):
        if index == -1:
            self.tab_widget.setVisible(False)
            self.dashboard_container.setVisible(True)

    # Favori Yönetimi
    def favoriye_ekle(self, menu_name):
        if menu_name not in self.favoriler:
            self.favoriler.append(menu_name)
            self.update_favorites_ui()
            self.show_toast(f"'{menu_name}' {self.tr('favorilere eklendi.')}", "success")

    def favoriden_cikar(self, menu_name):
        if menu_name in self.favoriler:
            self.favoriler.remove(menu_name)
            self.update_favorites_ui()
            self.show_toast(f"'{menu_name}' {self.tr('favorilerden çıkarıldı.')}", "warning")

    def update_favorites_ui(self):
        self.fav_screens_list.clear()
        self.fav_screens_list.addItems(self.favoriler)

    def show_grid_module_context_menu(self, pos, target_menu, sender_btn):
        menu = QMenu(self)
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
            menu = QMenu(self)
            remove_action = QAction(self.tr("❌ Favorilerden Çıkar"), self)
            remove_action.triggered.connect(lambda: self.favoriden_cikar(item.text()))
            menu.addAction(remove_action)
            menu.exec(QCursor.pos())
