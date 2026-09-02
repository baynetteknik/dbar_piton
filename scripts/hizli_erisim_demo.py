import sys
import os
import datetime
import random
import tempfile
import gzip

# Proje ana dizinini python yoluna ekle (Yedekleme motoru servisleri için)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.core.backup.db_backup import DatabaseBackupService
    from src.core.backup.file_backup import FileBackupService
    from src.core.backup.orchestrator import BackupOrchestrator
    from src.core.backup.parsers import CMSConfigParser
    MOTOR_ACTIVE = True
except ImportError:
    MOTOR_ACTIVE = False

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QGridLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QGraphicsDropShadowEffect, QProgressBar,
    QScrollArea, QStackedWidget, QTabWidget, QComboBox, QListWidget, QListWidgetItem, QMenu, QRadioButton
)
from PySide6.QtCore import Qt, QTimer, QPoint, QSize, QDateTime, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor, QKeySequence, QShortcut, QCursor, QAction

# ==========================================
# MODERN TOAST BİLDİRİM SİSTEMİ
# ==========================================
class ToastNotification(QFrame):
    def __init__(self, parent, message, notification_type="info"):
        super().__init__(parent)
        self.parent = parent
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
        parent_rect = self.parent.rect()
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
        parent_rect = self.parent.rect()
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
        self.parent = parent
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


# ==========================================
# ÖRNEK İÇERİK: MÜŞTERİ YÖNETİMİ EKRANI
# ==========================================
class MusteriYonetimiWidget(QWidget):
    def __init__(self, parent_window):
        super().__init__()
        self.main_window = parent_window
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        
        header_lbl = QLabel("👥 Müşteri Yönetimi")
        header_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #0f172a; font-family: 'Segoe UI';")
        layout.addWidget(header_lbl)
        
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)
        
        search_box = QLineEdit()
        search_box.setPlaceholderText("🔍 Müşteri ara...")
        search_box.setMinimumWidth(260)
        search_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: white;
                color: #0f172a;
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
        """)
        action_layout.addWidget(search_box)
        action_layout.addStretch()
        
        btn_new = QPushButton("➕ Yeni Müşteri")
        btn_new.setStyleSheet(self.btn_style("#10b981"))
        btn_new.clicked.connect(lambda: self.main_window.show_toast("Yeni müşteri kartı ekleme ekranı açıldı.", "success"))
        
        btn_import = QPushButton("📥 İçe Aktar")
        btn_import.setStyleSheet(self.btn_style("#3b82f6"))
        btn_import.clicked.connect(lambda: self.main_window.show_toast("Excel dosyasından veri aktarımı başlatıldı.", "info"))
        
        btn_export = QPushButton("📤 Dışa Aktar")
        btn_export.setStyleSheet(self.btn_style("#64748b"))
        btn_export.clicked.connect(lambda: self.main_window.show_toast("Müşteri listesi dışa aktarılıyor...", "info"))
        
        action_layout.addWidget(btn_new)
        action_layout.addWidget(btn_import)
        action_layout.addWidget(btn_export)
        layout.addLayout(action_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Ad / Cari Ünvan", "Vergi No / TCKN", "Telefon", "E-Posta Adresi", "Bakiye"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                background-color: white;
                border-radius: 8px;
                font-family: 'Segoe UI';
                font-size: 13px;
                color: #334155;
            }
            QTableWidget::item {
                padding: 12px;
                border-bottom: 1px solid #f1f5f9;
            }
            QTableWidget::item:hover {
                background-color: #f8fafc;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                padding: 10px 12px;
                font-weight: 700;
                font-family: 'Segoe UI';
                color: #475569;
                text-align: left;
            }
        """)
        
        sample_customers = [
            ("1", "Baynet Teknolojik Çözümler A.Ş.", "1234567890", "+90 212 555 0100", "info@baynet.com", "₺48,250.00"),
            ("2", "Kozmos Yazılım Ltd. Şti.", "9876543210", "+90 312 444 0200", "destek@kozmos.io", "₺12,800.00"),
            ("3", "Mavi Marketler Zinciri A.Ş.", "4561237890", "+90 232 333 0300", "muhasebe@mavimarket.com", "-₺4,150.00"),
            ("4", "ABC Dış Ticaret Ltd.", "7891234560", "+90 216 222 0400", "import@abctrade.com", "₺0.00"),
            ("5", "Lojistik Ulaşım Taşımacılık A.Ş.", "3216549870", "+90 224 111 0500", "operasyon@lojistik.com.tr", "₺112,900.00"),
        ]
        
        self.table.setRowCount(len(sample_customers))
        for row, data in enumerate(sample_customers):
            for col, text in enumerate(data):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                
                if col == 5:
                    item.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
                    if "-" in text:
                        item.setForeground(QColor("#ef4444"))
                    else:
                        item.setForeground(QColor("#10b981"))
                elif col == 0:
                    item.setForeground(QColor("#64748b"))
                    
                self.table.setItem(row, col, item)
                
        self.table.setMinimumHeight(280)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 10))
        shadow.setOffset(0, 2)
        self.table.setGraphicsEffect(shadow)
        
        layout.addWidget(self.table)
        layout.addStretch()

    def btn_style(self, bg_color):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """


# ==========================================
# ÇOKLU ALTYAPI & GÖRÜNÜM KONTROLLÜ YEDEKLEME WIDGET
# ==========================================
class YedeklemeYonetimiWidget(QWidget):
    """Kart/Liste görünüm geçişli, Webhook ve MSSQL destekli gelişmiş Yedekleme Modülü"""
    def __init__(self, selected_source, parent_window):
        super().__init__()
        self.main_window = parent_window
        self.selected_source = selected_source
        self.active_backup_timers = {}
        self.view_mode = "cards" # 'cards' veya 'list'
        
        # Her bir kaynak için ayrı bağımsız yapılandırma bilgileri
        self.backup_configs = {
            "Dolibarr": {
                "method": "Klasik Bağlantı",
                "db_host": "127.0.0.1", "db_port": "3306", "db_name": "dolibarr_prod", "db_user": "admin_cms", "db_pass": "şifre12345",
                "source_dir": "/var/www/dolibarr/documents", "dest_dir": "/backups/dolibarr",
                "webhook_url": "https://dolibarr.baynet.com/api/v1/backup-trigger", "webhook_token": "Bearer dolibarr_sec_token"
            },
            "WordPress": {
                "db_host": "localhost", "db_port": "3307", "db_name": "wp_db", "db_user": "wp_user", "db_pass": "wp_sifre",
                "source_dir": "/var/www/wordpress", "dest_dir": "/backups/wp"
            },
            "WooCommerce": {
                "db_host": "localhost", "db_port": "3307", "db_name": "wc_db", "db_user": "wc_user", "db_pass": "wc_sifre",
                "source_dir": "/var/www/woocommerce", "dest_dir": "/backups/wc"
            },
            "PrestaShop": {
                "db_host": "127.0.0.1", "db_port": "3306", "db_name": "ps_db", "db_user": "ps_user", "db_pass": "ps_sifre",
                "source_dir": "/var/www/prestashop", "dest_dir": "/backups/ps"
            },
            "MSSQL": {
                "db_host": "127.0.0.1", "db_port": "1433", "db_name": "mssql_master", "db_user": "sa", "db_pass": "SqlPass2026",
                "instance_name": "SQLEXPRESS", "win_auth": "Hayır", "dest_dir": "/backups/mssql"
            }
        }
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        
        # Üst Başlık ve Bilgi Çubuğu
        top_bar = QHBoxLayout()
        header_lbl = QLabel("🔄 Yedekleme Yönetim İstasyonu (Multi-CMS & MSSQL)")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: 800; color: #0f172a; font-family: 'Segoe UI';")
        top_bar.addWidget(header_lbl)
        top_bar.addStretch()
        
        motor_status_lbl = QLabel("Çekirdek Motor Aktif" if MOTOR_ACTIVE else "Simülasyon Modu")
        motor_color = "#10b981" if MOTOR_ACTIVE else "#f59e0b"
        motor_bg = "#d1fae5" if MOTOR_ACTIVE else "#fef3c7"
        motor_status_lbl.setStyleSheet(f"color: {motor_color}; background-color: {motor_bg}; font-size: 10px; font-weight: 700; padding: 4px 8px; border-radius: 4px;")
        top_bar.addWidget(motor_status_lbl)
        layout.addLayout(top_bar)
        
        # İç Sekmeli Yapı (Yedekleme & Yapılandırma)
        self.sub_tabs = QTabWidget()
        self.sub_tabs.setStyleSheet("""
            QTabWidget::panel {
                background-color: transparent;
                border: none;
            }
            QTabBar::tab {
                background-color: #cbd5e1;
                color: #475569;
                font-weight: 600;
                font-family: 'Segoe UI';
                font-size: 11px;
                padding: 6px 16px;
                border-radius: 4px;
                margin-right: 6px;
            }
            QTabBar::tab:selected {
                background-color: #1e293b;
                color: white;
            }
        """)
        
        # 1. SEKME: YEDEK İSTASYONU
        self.tab_backup_station = QWidget()
        self.init_backup_station_tab()
        self.sub_tabs.addTab(self.tab_backup_station, "⚡ Yedekleme İstasyonu")
        
        # 2. SEKME: YAPILANDIRMA AYARLARI
        self.tab_config_settings = QWidget()
        self.init_config_settings_tab()
        self.sub_tabs.addTab(self.tab_config_settings, "⚙️ Yapılandırma Ayarları")
        
        layout.addWidget(self.sub_tabs, 1)
        
    def init_backup_station_tab(self):
        lyt = QVBoxLayout(self.tab_backup_station)
        lyt.setContentsMargins(0, 10, 0, 0)
        lyt.setSpacing(14)
        
        # Üst Panel: Görünüm Seçici ve Toplu Buton
        top_panel = QHBoxLayout()
        
        # 🎛️ Kart ve 📋 Liste Görünüm Seçici Butonları
        self.btn_view_cards = QPushButton("🎛️ Kart Görünümü")
        self.btn_view_cards.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_cards.setStyleSheet(self.view_select_btn_style(True))
        self.btn_view_cards.clicked.connect(lambda: self.change_view_mode("cards"))
        
        self.btn_view_list = QPushButton("📋 Liste Görünümü")
        self.btn_view_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_list.setStyleSheet(self.view_select_btn_style(False))
        self.btn_view_list.clicked.connect(lambda: self.change_view_mode("list"))
        
        top_panel.addWidget(self.btn_view_cards)
        top_panel.addWidget(self.btn_view_list)
        top_panel.addStretch()
        
        btn_bulk_backup = QPushButton("⚡ Tümünü Sırayla Yedekle")
        btn_bulk_backup.setStyleSheet(self.btn_style("#ef4444"))
        btn_bulk_backup.clicked.connect(self.trigger_all_backups)
        top_panel.addWidget(btn_bulk_backup)
        lyt.addLayout(top_panel)
        
        # Kaynak Tanımları (MSSQL Dahil)
        self.sources = [
            {"name": "Dolibarr", "emoji": "💾", "desc": "ERP Veritabanı ve Medya Klasörü"},
            {"name": "WordPress", "emoji": "🌐", "desc": "Web Sitesi Dosyaları ve SQL"},
            {"name": "WooCommerce", "emoji": "🛒", "desc": "E-Ticaret Sipariş & Ürün API"},
            {"name": "PrestaShop", "emoji": "🛍️", "desc": "Entegrasyon Senkronizasyon Verisi"},
            {"name": "MSSQL", "emoji": "🗄️", "desc": "Kurumsal Microsoft SQL Server Veritabanı"}
        ]
        
        # --- 1. KART GÖRÜNÜMÜ ALANI ---
        self.cards_view_container = QWidget()
        self.cards_layout = QHBoxLayout(self.cards_view_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        
        # --- 2. LİSTE GÖRÜNÜMÜ ALANI ---
        self.list_view_container = QWidget()
        self.list_view_container.setVisible(False)
        self.list_layout = QVBoxLayout(self.list_view_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(8)
        
        # Kartlar ve Listeyi Doldur
        self.card_widgets = {}
        for src in self.sources:
            # 1. KART OLUŞTURMA
            card = QFrame()
            border_color = "#2563eb" if self.selected_source == src["name"] else "#e2e8f0"
            card.setStyleSheet(f"QFrame {{ background-color: white; border: 1px solid {border_color}; border-radius: 10px; }}")
            card_lyt = QVBoxLayout(card)
            card_lyt.setContentsMargins(12, 12, 12, 12)
            card_lyt.setSpacing(6)
            
            title_lyt = QHBoxLayout()
            em_lbl = QLabel(src["emoji"])
            em_lbl.setFont(QFont("Segoe UI", 18))
            name_lbl = QLabel(src["name"])
            name_lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #0f172a; font-family: 'Segoe UI';")
            title_lyt.addWidget(em_lbl)
            title_lyt.addWidget(name_lbl)
            title_lyt.addStretch()
            
            status_badge = QLabel("Ready")
            status_badge.setStyleSheet("color: #065f46; background-color: #d1fae5; font-size: 9px; font-weight: 700; padding: 2px 5px; border-radius: 3px;")
            title_lyt.addWidget(status_badge)
            card_lyt.addLayout(title_lyt)
            
            desc_lbl = QLabel(src["desc"])
            desc_lbl.setStyleSheet("font-size: 9px; color: #64748b; font-family: 'Segoe UI';")
            desc_lbl.setWordWrap(True)
            card_lyt.addWidget(desc_lbl)
            
            pbar = QProgressBar()
            pbar.setValue(0)
            pbar.setFixedHeight(5)
            pbar.setTextVisible(False)
            pbar.setStyleSheet("QProgressBar { background-color: #f1f5f9; border: none; border-radius: 2px; } QProgressBar::chunk { background-color: #3b82f6; border-radius: 2px; }")
            card_lyt.addWidget(pbar)
            
            btn_run = QPushButton("⚡ Yedek Al")
            btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_run.setStyleSheet(self.backup_action_btn_style())
            card_lyt.addWidget(btn_run)
            
            self.cards_layout.addWidget(card)
            
            # 2. COMPACT LİSTE SATIRI OLUŞTURMA
            list_row = QFrame()
            list_row.setStyleSheet("QFrame { background-color: white; border: 1px solid #e2e8f0; border-radius: 8px; }")
            list_row_lyt = QHBoxLayout(list_row)
            list_row_lyt.setContentsMargins(14, 8, 14, 8)
            list_row_lyt.setSpacing(16)
            
            list_em = QLabel(src["emoji"])
            list_em.setFont(QFont("Segoe UI", 16))
            list_row_lyt.addWidget(list_em)
            
            list_name = QLabel(src["name"])
            list_name.setFixedWidth(80)
            list_name.setStyleSheet("font-size: 12px; font-weight: 700; color: #0f172a; font-family: 'Segoe UI';")
            list_row_lyt.addWidget(list_name)
            
            list_desc = QLabel(src["desc"])
            list_desc.setStyleSheet("font-size: 9.5px; color: #64748b; font-family: 'Segoe UI';")
            list_row_lyt.addWidget(list_desc, 2)
            
            list_pbar = QProgressBar()
            list_pbar.setValue(0)
            list_pbar.setFixedHeight(5)
            list_pbar.setTextVisible(False)
            list_pbar.setStyleSheet("QProgressBar { background-color: #f1f5f9; border: none; border-radius: 2px; } QProgressBar::chunk { background-color: #3b82f6; border-radius: 2px; }")
            list_row_lyt.addWidget(list_pbar, 2)
            
            list_status = QLabel("Ready")
            list_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            list_status.setStyleSheet("color: #065f46; background-color: #d1fae5; font-size: 9px; font-weight: 700; padding: 2px 5px; border-radius: 3px;")
            list_row_lyt.addWidget(list_status)
            
            list_btn = QPushButton("⚡ Yedek Al")
            list_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            list_btn.setStyleSheet(self.backup_action_btn_style())
            list_btn.setFixedWidth(80)
            list_row_lyt.addWidget(list_btn)
            
            self.list_layout.addWidget(list_row)
            
            # Sinyalleri bağla (Kart ve liste butonları birbirini tetikler)
            btn_run.clicked.connect(lambda checked, n=src["name"], p=pbar, s=status_badge, b=btn_run, lp=list_pbar, ls=list_status, lb=list_btn: self.start_backup_chain(n, p, s, b, lp, ls, lb))
            list_btn.clicked.connect(lambda checked, n=src["name"], p=pbar, s=status_badge, b=btn_run, lp=list_pbar, ls=list_status, lb=list_btn: self.start_backup_chain(n, p, s, b, lp, ls, lb))
            
            # Nesneleri ortak takip için sakla
            self.card_widgets[src["name"]] = (pbar, status_badge, btn_run, list_pbar, list_status, list_btn)
            
        lyt.addWidget(self.cards_view_container)
        lyt.addWidget(self.list_view_container)
        
        # Loglar Tablosu
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Kaynak", "Dosya Adı", "Boyut", "Oluşturma Tarihi", "Durum"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e2e8f0;
                background-color: white;
                border-radius: 8px;
                font-family: 'Segoe UI';
                font-size: 12px;
                color: #334155;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #f1f5f9;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                padding: 8px 10px;
                font-weight: 700;
                color: #475569;
                text-align: left;
            }
        """)
        
        self.log_data = [
            ("L-804", "Dolibarr", "backup_dolibarr_20260714_1200.zip", "18.4 MB", "14.07.2026 12:00", "Başarılı"),
            ("L-803", "WordPress", "backup_wp_site_20260714_1145.zip", "142.8 MB", "14.07.2026 11:45", "Başarılı"),
            ("L-802", "WooCommerce", "backup_wc_api_20260714_1100.zip", "2.1 MB", "14.07.2026 11:00", "Başarılı"),
        ]
        self.update_log_table()
        lyt.addWidget(self.table)
        
        btn_lyt = QHBoxLayout()
        btn_download = QPushButton("💾 Seçili Yedeği İndir")
        btn_download.setStyleSheet(self.btn_style("#1e293b"))
        btn_download.clicked.connect(lambda: self.main_window.show_toast("Yedek dosyası indirme kuyruğuna alındı.", "info"))
        
        btn_delete = QPushButton("🗑️ Eski Yedekleri Temizle")
        btn_delete.setStyleSheet(self.btn_style("#64748b"))
        btn_delete.clicked.connect(self.clear_old_backups)
        btn_lyt.addWidget(btn_download)
        btn_lyt.addWidget(btn_delete)
        btn_lyt.addStretch()
        lyt.addLayout(btn_lyt)

    def change_view_mode(self, mode):
        """Kartlar ve dikey liste görünümleri arasında geçiş sağlar"""
        self.view_mode = mode
        if mode == "cards":
            self.cards_view_container.setVisible(True)
            self.list_view_container.setVisible(False)
            self.btn_view_cards.setStyleSheet(self.view_select_btn_style(True))
            self.btn_view_list.setStyleSheet(self.view_select_btn_style(False))
        else:
            self.cards_view_container.setVisible(False)
            self.list_view_container.setVisible(True)
            self.btn_view_cards.setStyleSheet(self.view_select_btn_style(False))
            self.btn_view_list.setStyleSheet(self.view_select_btn_style(True))

    def start_backup_chain(self, name, p, s, b, lp, ls, lb):
        """Kart ve listedeki ilişkili progress barları koordine ederek yedeği tetikler"""
        self.start_backup_process(name, p, s, b, lp, ls, lb)

    def init_config_settings_tab(self):
        lyt = QVBoxLayout(self.tab_config_settings)
        lyt.setContentsMargins(10, 10, 10, 10)
        lyt.setSpacing(10)
        
        # Üst Kaynak Seçim Barı
        select_lyt = QHBoxLayout()
        select_lyt.addWidget(QLabel("⚙️ Yapılandırılacak Kaynak / Ürün Seçin:"))
        
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Dolibarr", "WordPress", "WooCommerce", "PrestaShop", "MSSQL"])
        self.source_combo.setCurrentText(self.selected_source if self.selected_source in self.backup_configs else "Dolibarr")
        self.source_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                background-color: white;
            }
        """)
        self.source_combo.currentTextChanged.connect(self.update_config_form_fields)
        select_lyt.addWidget(self.source_combo)
        select_lyt.addStretch()
        lyt.addLayout(select_lyt)
        
        # Ana Form Çerçevesi
        self.form_frame = QFrame()
        self.form_frame.setStyleSheet("background-color: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px;")
        self.form_grid = QGridLayout(self.form_frame)
        self.form_grid.setSpacing(10)
        
        # --- DİNAMİK FORM ELEMANLARI (KONTROLLER) ---
        # 1. Dolibarr Yöntem Grubu
        self.method_lbl = QLabel("Yedekleme Yöntemi:")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Klasik Bağlantı (DB/Dosya)", "Webhook Entegrasyonu"])
        self.method_combo.currentTextChanged.connect(self.on_method_changed)
        
        # 2. Klasik Veritabanı Grubu (Ortak)
        self.db_host_lbl = QLabel("DB Host (Sunucu IP):")
        self.db_host_input = QLineEdit()
        self.apply_input_style(self.db_host_input)
        
        self.db_port_lbl = QLabel("DB Port:")
        self.db_port_input = QLineEdit()
        self.apply_input_style(self.db_port_input)
        
        self.db_name_lbl = QLabel("Veritabanı Adı (DB Name):")
        self.db_name_input = QLineEdit()
        self.apply_input_style(self.db_name_input)
        
        self.db_user_lbl = QLabel("Kullanıcı Adı (DB User):")
        self.db_user_input = QLineEdit()
        self.apply_input_style(self.db_user_input)
        
        self.db_pass_lbl = QLabel("Veritabanı Şifresi:")
        self.db_pass_input = QLineEdit()
        self.db_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.apply_input_style(self.db_pass_input)
        
        # 3. Webhook Grubu
        self.web_url_lbl = QLabel("Webhook / API URL:")
        self.web_url_input = QLineEdit()
        self.apply_input_style(self.web_url_input)
        
        self.web_token_lbl = QLabel("API Bearer Token:")
        self.web_token_input = QLineEdit()
        self.web_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.apply_input_style(self.web_token_input)
        
        # 4. MSSQL Ek Grubu
        self.mssql_instance_lbl = QLabel("MSSQL Instance Name:")
        self.mssql_instance_input = QLineEdit()
        self.apply_input_style(self.mssql_instance_input)
        
        self.mssql_auth_lbl = QLabel("Windows Authentication:")
        self.mssql_auth_combo = QComboBox()
        self.mssql_auth_combo.addItems(["Hayır (SQL Server Auth)", "Evet (Win Auth)"])
        self.mssql_auth_combo.currentTextChanged.connect(self.on_mssql_auth_changed)
        
        # 5. Dizin Grubu (Ortak)
        self.src_dir_lbl = QLabel("Kaynak Dizin (Dosyalar):")
        self.src_dir_input = QLineEdit()
        self.apply_input_style(self.src_dir_input)
        
        self.dest_dir_lbl = QLabel("Yedek Çıkış Dizini:")
        self.dest_dir_input = QLineEdit()
        self.apply_input_style(self.dest_dir_input)
        
        lyt.addWidget(self.form_frame)
        
        # Form Eylemleri
        btn_action_lyt = QHBoxLayout()
        btn_save = QPushButton("💾 Yapılandırmayı Kaydet")
        btn_save.setStyleSheet(self.btn_style("#2563eb"))
        btn_save.clicked.connect(self.save_configuration)
        
        btn_reset = QPushButton("🔄 Varsayılanlara Dön")
        btn_reset.setStyleSheet(self.btn_style("#64748b"))
        btn_reset.clicked.connect(self.reset_configuration)
        
        btn_action_lyt.addWidget(btn_save)
        btn_action_lyt.addWidget(btn_reset)
        btn_action_lyt.addStretch()
        lyt.addLayout(btn_action_lyt)
        
        # Formu ilk yükleme durumuna göre doldur
        self.update_config_form_fields(self.source_combo.currentText())

    def update_config_form_fields(self, source_name):
        """Seçilen yedekleme kaynağına göre form alanlarını dinamik gösterir / gizler"""
        # Önce formdaki tüm widgetları temizle/gizle
        for i in range(self.form_grid.count()):
            widget = self.form_grid.itemAt(i).widget()
            if widget:
                widget.setVisible(False)
                
        cfg = self.backup_configs[source_name]
        row = 0
        
        # 1. Dolibarr Metod Kontrolü
        if source_name == "Dolibarr":
            self.form_grid.addWidget(self.method_lbl, row, 0)
            self.form_grid.addWidget(self.method_combo, row, 1)
            self.method_lbl.setVisible(True)
            self.method_combo.setVisible(True)
            self.method_combo.setCurrentText(cfg.get("method", "Klasik Bağlantı (DB/Dosya)"))
            row += 1
            
            if cfg.get("method") == "Webhook Entegrasyonu":
                # Webhook Görünümü
                self.form_grid.addWidget(self.web_url_lbl, row, 0)
                self.form_grid.addWidget(self.web_url_input, row, 1)
                self.web_url_lbl.setVisible(True)
                self.web_url_input.setVisible(True)
                self.web_url_input.setText(cfg.get("webhook_url", ""))
                row += 1
                
                self.form_grid.addWidget(self.web_token_lbl, row, 0)
                self.form_grid.addWidget(self.web_token_input, row, 1)
                self.web_token_lbl.setVisible(True)
                self.web_token_input.setVisible(True)
                self.web_token_input.setText(cfg.get("webhook_token", ""))
                row += 1
            else:
                # Klasik Görünüm
                row = self.add_classic_db_fields(row, cfg)
                row = self.add_directory_fields(row, cfg)
                
        elif source_name == "MSSQL":
            # MSSQL Özel Görünümü
            row = self.add_classic_db_fields(row, cfg, is_mssql=True)
            
            # Instance & Auth alanları
            self.form_grid.addWidget(self.mssql_instance_lbl, row, 0)
            self.form_grid.addWidget(self.mssql_instance_input, row, 1)
            self.mssql_instance_lbl.setVisible(True)
            self.mssql_instance_input.setVisible(True)
            self.mssql_instance_input.setText(cfg.get("instance_name", "SQLEXPRESS"))
            row += 1
            
            self.form_grid.addWidget(self.mssql_auth_lbl, row, 0)
            self.form_grid.addWidget(self.mssql_auth_combo, row, 1)
            self.mssql_auth_lbl.setVisible(True)
            self.mssql_auth_combo.setVisible(True)
            self.mssql_auth_combo.setCurrentText(cfg.get("win_auth", "Hayır (SQL Server Auth)"))
            row += 1
            
            self.form_grid.addWidget(self.dest_dir_lbl, row, 0)
            self.form_grid.addWidget(self.dest_dir_input, row, 1)
            self.dest_dir_lbl.setVisible(True)
            self.dest_dir_input.setVisible(True)
            self.dest_dir_input.setText(cfg.get("dest_dir", ""))
            row += 1
            
            # Windows auth ise kullanıcı/şifre alanlarını pasifleştir
            is_win = cfg.get("win_auth") == "Evet (Win Auth)"
            self.db_user_input.setDisabled(is_win)
            self.db_pass_input.setDisabled(is_win)
            
        else:
            # Standart CMS (WordPress, WooCommerce, PrestaShop)
            row = self.add_classic_db_fields(row, cfg)
            row = self.add_directory_fields(row, cfg)

    def add_classic_db_fields(self, row, cfg, is_mssql=False):
        self.form_grid.addWidget(self.db_host_lbl, row, 0)
        self.form_grid.addWidget(self.db_host_input, row, 1)
        self.db_host_lbl.setVisible(True)
        self.db_host_input.setVisible(True)
        self.db_host_input.setText(cfg.get("db_host", ""))
        row += 1
        
        self.form_grid.addWidget(self.db_port_lbl, row, 0)
        self.form_grid.addWidget(self.db_port_input, row, 1)
        self.db_port_lbl.setVisible(True)
        self.db_port_input.setVisible(True)
        self.db_port_input.setText(cfg.get("db_port", ""))
        row += 1
        
        self.form_grid.addWidget(self.db_name_lbl, row, 0)
        self.form_grid.addWidget(self.db_name_input, row, 1)
        self.db_name_lbl.setVisible(True)
        self.db_name_input.setVisible(True)
        self.db_name_input.setText(cfg.get("db_name", ""))
        row += 1
        
        self.form_grid.addWidget(self.db_user_lbl, row, 0)
        self.form_grid.addWidget(self.db_user_input, row, 1)
        self.db_user_lbl.setVisible(True)
        self.db_user_input.setVisible(True)
        self.db_user_input.setText(cfg.get("db_user", ""))
        self.db_user_input.setDisabled(False)
        row += 1
        
        self.form_grid.addWidget(self.db_pass_lbl, row, 0)
        self.form_grid.addWidget(self.db_pass_input, row, 1)
        self.db_pass_lbl.setVisible(True)
        self.db_pass_input.setVisible(True)
        self.db_pass_input.setText(cfg.get("db_pass", ""))
        self.db_pass_input.setDisabled(False)
        row += 1
        return row

    def add_directory_fields(self, row, cfg):
        self.form_grid.addWidget(self.src_dir_lbl, row, 0)
        self.form_grid.addWidget(self.src_dir_input, row, 1)
        self.src_dir_lbl.setVisible(True)
        self.src_dir_input.setVisible(True)
        self.src_dir_input.setText(cfg.get("source_dir", ""))
        row += 1
        
        self.form_grid.addWidget(self.dest_dir_lbl, row, 0)
        self.form_grid.addWidget(self.dest_dir_input, row, 1)
        self.dest_dir_lbl.setVisible(True)
        self.dest_dir_input.setVisible(True)
        self.dest_dir_input.setText(cfg.get("dest_dir", ""))
        row += 1
        return row

    def on_method_changed(self, text):
        self.backup_configs["Dolibarr"]["method"] = text
        self.update_config_form_fields("Dolibarr")

    def on_mssql_auth_changed(self, text):
        self.backup_configs["MSSQL"]["win_auth"] = text
        self.update_config_form_fields("MSSQL")

    def save_configuration(self):
        source = self.source_combo.currentText()
        cfg = self.backup_configs[source]
        
        if source == "Dolibarr":
            cfg["method"] = self.method_combo.currentText()
            if cfg["method"] == "Webhook Entegrasyonu":
                cfg["webhook_url"] = self.web_url_input.text().strip()
                cfg["webhook_token"] = self.web_token_input.text().strip()
            else:
                self.read_common_fields(cfg)
                
        elif source == "MSSQL":
            cfg["win_auth"] = self.mssql_auth_combo.currentText()
            cfg["instance_name"] = self.mssql_instance_input.text().strip()
            cfg["dest_dir"] = self.dest_dir_input.text().strip()
            if cfg["win_auth"] == "Hayır (SQL Server Auth)":
                cfg["db_host"] = self.db_host_input.text().strip()
                cfg["db_port"] = self.db_port_input.text().strip()
                cfg["db_name"] = self.db_name_input.text().strip()
                cfg["db_user"] = self.db_user_input.text().strip()
                cfg["db_pass"] = self.db_pass_input.text().strip()
        else:
            self.read_common_fields(cfg)
            
        self.main_window.show_toast(f"'{source}' yapılandırma ayarları başarıyla kaydedildi.", "success")
        self.sub_tabs.setCurrentIndex(0)

    def read_common_fields(self, cfg):
        cfg["db_host"] = self.db_host_input.text().strip()
        cfg["db_port"] = self.db_port_input.text().strip()
        cfg["db_name"] = self.db_name_input.text().strip()
        cfg["db_user"] = self.db_user_input.text().strip()
        cfg["db_pass"] = self.db_pass_input.text().strip()
        cfg["source_dir"] = self.src_dir_input.text().strip()
        cfg["dest_dir"] = self.dest_dir_input.text().strip()

    def reset_configuration(self):
        source = self.source_combo.currentText()
        self.main_window.show_toast(f"'{source}' ayarları varsayılanlara döndürüldü.", "info")

    def apply_input_style(self, line_edit):
        line_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                background-color: white;
                color: #0f172a;
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
        """)

    def start_backup_process(self, source_name, progress_bar, status_label, trigger_button, list_pbar, list_status, list_btn):
        """Gerçek motor sınıflarını (DatabaseBackupService, FileBackupService vb.) dinamik QTimer adımlarıyla koordine eder"""
        if source_name in self.active_backup_timers:
            self.main_window.show_toast(f"'{source_name}' yedeklemesi zaten devam ediyor.", "warning")
            return
            
        # Hem karttaki hem listedeki barları sıfırla
        progress_bar.setValue(0)
        list_pbar.setValue(0)
        
        status_label.setText("Hazırlanıyor...")
        list_status.setText("Hazırlanıyor...")
        status_label.setStyleSheet("color: #854d0e; background-color: #fef9c3; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;")
        list_status.setStyleSheet("color: #854d0e; background-color: #fef9c3; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;")
        
        trigger_button.setEnabled(False)
        list_btn.setEnabled(False)
        
        timer = QTimer(self)
        self.active_backup_timers[source_name] = timer
        
        temp_dir_ctx = tempfile.TemporaryDirectory()
        tmpdir = temp_dir_ctx.name
        backup_step = {"val": 0}
        
        cfg = self.backup_configs.get(source_name, {})
        
        def run_step():
            step = backup_step["val"]
            if step == 0:
                # ADIM 1: YÖNTEM DOĞRULAMA (Webhook / Klasik PHP Parse)
                if source_name == "Dolibarr" and cfg.get("method") == "Webhook Entegrasyonu":
                    status_label.setText("Webhook Tetikleniyor...")
                    list_status.setText("Webhook Tetikleniyor...")
                    progress_bar.setValue(40)
                    list_pbar.setValue(40)
                    print(f"[Dolibarr] Webhook tetiklendi: {cfg.get('webhook_url')}")
                    backup_step["val"] = 3 # Doğrudan tamamlama aşamasına atla (Webhook API tek adımda biter)
                else:
                    status_label.setText("Config Ayrıştırılıyor...")
                    list_status.setText("Config Ayrıştırılıyor...")
                    progress_bar.setValue(20)
                    list_pbar.setValue(20)
                    
                    if MOTOR_ACTIVE and source_name != "MSSQL":
                        try:
                            mock_conf = os.path.join(tmpdir, "config.php")
                            with open(mock_conf, "w", encoding="utf-8") as f:
                                f.write(f"""<?php
                                $dolibarr_main_db_host='{cfg.get("db_host")}';
                                $dolibarr_main_db_name='{cfg.get("db_name")}';
                                """)
                            CMSConfigParser.parse_dolibarr(mock_conf)
                        except Exception as e:
                            print(f"Parser hatası: {e}")
                    backup_step["val"] += 1
                    
            elif step == 1:
                # ADIM 2: DOSYA ARŞİVLEME (FileBackupService)
                status_label.setText("Dosyalar Paketleniyor...")
                list_status.setText("Dosyalar Paketleniyor...")
                progress_bar.setValue(50)
                list_pbar.setValue(50)
                
                if MOTOR_ACTIVE and source_name != "MSSQL":
                    try:
                        web_dir = os.path.join(tmpdir, "web")
                        os.makedirs(web_dir)
                        with open(os.path.join(web_dir, "index.php"), "w") as f:
                            f.write("<?php echo 'CMS Engine'; ?>")
                        archive_zip = os.path.join(tmpdir, "files.tar.gz")
                        FileBackupService.compress_directory(web_dir, archive_zip)
                    except Exception as e:
                        print(f"File compress hatası: {e}")
                backup_step["val"] += 1
                
            elif step == 2:
                # ADIM 3: VERİTABANI YEDEKLEME (DatabaseBackupService / MSSQL)
                status_label.setText("DB Sıkıştırılıyor...")
                list_status.setText("DB Sıkıştırılıyor...")
                progress_bar.setValue(80)
                list_pbar.setValue(80)
                
                if source_name == "MSSQL":
                    print(f"[MSSQL] Windows Auth: {cfg.get('win_auth')}, Instance: {cfg.get('instance_name')}")
                elif MOTOR_ACTIVE:
                    try:
                        db_zip = os.path.join(tmpdir, "db.sql.gz")
                        with gzip.open(db_zip, "wb") as f:
                            f.write(f"CREATE DATABASE {cfg.get('db_name')};".encode('utf-8'))
                    except Exception as e:
                        print(f"DB compress hatası: {e}")
                backup_step["val"] += 1
                
            elif step == 3:
                # ADIM 4: TAMAMLAMA & DOĞRULAMA
                status_label.setText("Doğrulanıyor...")
                list_status.setText("Doğrulanıyor...")
                progress_bar.setValue(100)
                list_pbar.setValue(100)
                
                timer.stop()
                self.active_backup_timers.pop(source_name)
                
                status_label.setText("Hazır")
                list_status.setText("Hazır")
                status_label.setStyleSheet("color: #065f46; background-color: #d1fae5; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;")
                list_status.setStyleSheet("color: #065f46; background-color: #d1fae5; font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;")
                
                trigger_button.setEnabled(True)
                list_btn.setEnabled(True)
                
                temp_dir_ctx.cleanup()
                
                # Log listesini güncelle
                new_id = f"L-{random.randint(805, 999)}"
                new_file = f"backup_{source_name.lower()}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                new_size = f"{random.uniform(8.4, 210.5):.1f} MB"
                new_date = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
                
                self.log_data.insert(0, (new_id, source_name, new_file, new_size, new_date, "Başarılı"))
                self.update_log_table()
                
                self.main_window.show_toast(f"'{source_name}' yedekleme işlemi başarıyla tamamlandı.", "success")
                
        timer.timeout.connect(run_step)
        timer.start(400)

    def trigger_all_backups(self):
        for src_name, (pbar, status_lbl, btn, lp, ls, lb) in self.card_widgets.items():
            self.start_backup_process(src_name, pbar, status_lbl, btn, lp, ls, lb)
            
    def update_log_table(self):
        self.table.setRowCount(len(self.log_data))
        for row, data in enumerate(self.log_data):
            for col in range(5):
                item = QTableWidgetItem(data[col])
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                if col == 0:
                    item.setForeground(QColor("#64748b"))
                self.table.setItem(row, col, item)
                
            status_text = data[5]
            badge_lbl = QLabel(status_text)
            badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if status_text == "Başarılı":
                style = "color: #065f46; background-color: #d1fae5; border-radius: 4px; font-weight: 700; font-size: 9px; margin: 2px 6px;"
            else:
                style = "color: #991b1b; background-color: #fee2e2; border-radius: 4px; font-weight: 700; font-size: 9px; margin: 2px 6px;"
            badge_lbl.setStyleSheet(style)
            self.table.setCellWidget(row, 5, badge_lbl)
            
    def clear_old_backups(self):
        self.log_data = [self.log_data[0]] if self.log_data else []
        self.update_log_table()
        self.main_window.show_toast("Eski yedek log kayıtları başarıyla temizlendi.", "warning")

    def btn_style(self, bg_color):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """

    def view_select_btn_style(self, active):
        bg = "#1e293b" if active else "transparent"
        border = "1px solid #334155" if not active else "none"
        color = "white" if active else "#64748b"
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: {border};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{
                background-color: #334155;
                color: white;
            }}
        """

    def backup_action_btn_style(self):
        return """
            QPushButton {
                background-color: #1e293b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """


# ==========================================
# ANA PENCERE (TAB SİSTEMİ & HOVER NAVBAR)
# ==========================================
class DolibarrPlusDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dolibarr+ ERP - Profesyonel Masaüstü Paneli")
        self.setGeometry(100, 100, 1480, 880)
        self.setStyleSheet("background-color: #f0f4f8;")
        
        self.active_popup = None
        self.favoriler = ["Müşteriler", "Giden Fatura", "Ürünler"]
        
        self.menu_structure = {
            "📊 DASHBOARD": (["Ana Panel", "Takvim", "Bildirimler"], "📊"),
            "👥 CARİ": (["Müşteriler", "Tedarikçiler", "Cari Hareket"], "👥"),
            "📦 STOK": (["Ürünler", "Depolar", "Stok Giriş/Çıkış"], "📦"),
            "🧾 FATURA": (["Giden Fatura", "Gelen Fatura", "İade Faturaları"], "🧾"),
            "📋 TEKLİF": (["Teklifler", "Sözleşmeler"], "📋"),
            "💰 KASA": (["Kasa", "Banka"], "💰"),
            "👔 PERSONEL": (["Personel Listesi", "Maaşlar"], "👔"),
            "📚 MUHASEBE": (["Muhasebe", "Defter-i Kebir"], "📚"),
            "🔄 YEDEKLEME": (["Dolibarr", "WordPress", "WooCommerce", "PrestaShop"], "🔄"),
            "⚙️ SİSTEM": (["Ayarlar", "Loglar", "Destek"], "⚙️")
        }
        
        self.init_ui()

    def init_ui(self):
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
        
        logo = QLabel("🏢 Dolibarr+")
        logo.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff; font-family: 'Segoe UI';")
        header_layout.addWidget(logo)
        
        header_layout.addStretch()
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Arama yap... (Ctrl+K)")
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
        
        user_lbl = QLabel("👤 dia@testalper")
        user_lbl.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 700; font-family: 'Segoe UI';")
        header_layout.addWidget(user_lbl)
        
        self.company_combo = QComboBox()
        self.company_combo.addItems(["Baynet Teknik A.Ş.", "Kozmos Yazılım Ltd.", "Özel Yönetim A.Ş."])
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
        help_btn.clicked.connect(lambda: self.show_toast("Destek ve yardım kılavuzu yükleniyor...", "info"))
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
        # 4. ANA SAYFA / GRID MENÜ + FAVORİLER
        # ==========================================
        self.dashboard_container = QScrollArea()
        self.dashboard_container.setWidgetResizable(True)
        self.dashboard_container.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        
        dash_scroll_content = QWidget()
        dash_scroll_content.setStyleSheet("background: transparent;")
        self.dash_layout = QVBoxLayout(dash_scroll_content)
        self.dash_layout.setContentsMargins(32, 24, 32, 24)
        self.dash_layout.setSpacing(20)
        
        welcome_lbl = QLabel("Hoş Geldiniz!")
        welcome_lbl.setStyleSheet("font-size: 24px; font-weight: 800; color: #0f172a; font-family: 'Segoe UI';")
        today_lbl = QLabel(f"📅 Bugünün Tarihi: {QDateTime.currentDateTime().toString('dd MMMM yyyy')}")
        today_lbl.setStyleSheet("font-size: 13px; color: #64748b; font-family: 'Segoe UI';")
        self.dash_layout.addWidget(welcome_lbl)
        self.dash_layout.addWidget(today_lbl)
        
        grid_title = QLabel("🎛️ Modül Kataloğu (Favorilere eklemek için modüllere sağ tıklayın)")
        grid_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0f172a; font-family: 'Segoe UI'; margin-top: 10px;")
        self.dash_layout.addWidget(grid_title)
        
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(14)
        
        dia_modules = [
            ("Panel", "📊", "Ana Panel"),
            ("Takvim", "📅", "Takvim"),
            ("Bildirimler", "🔔", "Bildirimler"),
            ("Müşteriler", "👥", "Müşteriler"),
            ("Tedarikçiler", "🤝", "Tedarikçiler"),
            ("Cari Hareket", "🔄", "Cari Hareket"),
            ("Ürünler", "📦", "Ürünler"),
            ("Depolar", "🏢", "Depolar"),
            ("Stok Giriş/Çıkış", "🚚", "Stok Giriş/Çıkış"),
            ("Giden Fatura", "🧾", "Giden Fatura"),
            ("Gelen Fatura", "💸", "Gelen Fatura"),
            ("Teklifler", "📋", "Teklifler"),
            ("Sözleşmeler", "✒️", "Sözleşmeler"),
            ("Kasa", "💰", "Kasa"),
            ("Banka", "🏦", "Banka"),
            ("Personel", "👔", "Personel Listesi"),
            ("Maaşlar", "💵", "Maaşlar"),
            ("Muhasebe", "📚", "Muhasebe"),
            ("Defter-i Kebir", "📖", "Defter-i Kebir"),
            ("Yedekleme", "💾", "Dolibarr"),
            ("Ayarlar", "⚙️", "Ayarlar"),
            ("Loglar", "📝", "Loglar"),
        ]
        
        cols_count = 6
        for idx, (mod_name, mod_emoji, target_menu) in enumerate(dia_modules):
            mod_btn = GridModuleButton(mod_name, mod_emoji, target_menu, self)
            mod_btn.clicked.connect(lambda checked, t=target_menu: self.alt_menu_tiklandi(t))
            self.grid_layout.addWidget(mod_btn, idx // cols_count, idx % cols_count)
            
        self.dash_layout.addLayout(self.grid_layout)
        
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
        fs_title = QLabel("⭐ Favori Ekranlar (Sağ tıkla kaldır)")
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
        fr_title = QLabel("📊 Favori Raporlar")
        fr_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #0f172a; font-family: 'Segoe UI'; border-bottom: 2px solid #f1f5f9; padding-bottom: 6px;")
        fr_layout.addWidget(fr_title)
        
        self.fav_reports_list = QListWidget()
        self.fav_reports_list.setStyleSheet("QListWidget { border: none; font-size: 12px; color: #334155; } QListWidget::item { padding: 6px 0px; }")
        self.fav_reports_list.addItems(["Aylık Satış Analizi Raporu", "Kasa Bakiye Durum Raporu", "Depo Kontrol Raporu"])
        self.fav_reports_list.itemClicked.connect(lambda item: self.show_toast(f"'{item.text()}' raporu yükleniyor...", "info"))
        fr_layout.addWidget(self.fav_reports_list)
        
        fav_layout.addWidget(fav_screens_frame)
        fav_layout.addWidget(fav_reports_frame)
        self.dash_layout.addLayout(fav_layout)
        self.dash_layout.addStretch()
        
        self.dashboard_container.setWidget(dash_scroll_content)
        main_layout.addWidget(self.dashboard_container, 1)
        
        # ==========================================
        # 🏢 GÜNCEL TARIH / SAAT DURUM ÇUBUĞU (FOOTER BAR)
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
        
        footer_info = QLabel("🏢 Dolibarr+ ERP Yazılım A.Ş. | İyi çalışmalar dileriz...")
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

    # ==========================================
    # SAĞ KLİK FAVORİ YÖNETİM METODLARI
    # ==========================================
    def show_grid_module_context_menu(self, pos, target_menu, sender_btn):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0b1120;
                color: white;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
            }
        """)
        is_fav = target_menu in self.favoriler
        if not is_fav:
            add_action = QAction("⭐ Favorilere Ekle", self)
            add_action.triggered.connect(lambda: self.favoriye_ekle(target_menu))
            menu.addAction(add_action)
        else:
            remove_action = QAction("❌ Favorilerden Çıkar", self)
            remove_action.triggered.connect(lambda: self.favoriden_cikar(target_menu))
            menu.addAction(remove_action)
        menu.exec(sender_btn.mapToGlobal(pos))

    def show_favorites_context_menu(self, pos):
        item = self.fav_screens_list.itemAt(pos)
        if not item:
            return
        item_name = item.text()
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0b1120;
                color: white;
                border: 1px solid #1e293b;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #ef4444;
            }
        """)
        remove_action = QAction("❌ Favorilerden Çıkar", self)
        remove_action.triggered.connect(lambda: self.favoriden_cikar(item_name))
        menu.addAction(remove_action)
        self.fav_screens_list.setCurrentItem(item)
        menu.exec(self.fav_screens_list.mapToGlobal(pos))

    def favoriye_ekle(self, item_name):
        if item_name not in self.favoriler:
            self.favoriler.append(item_name)
            self.update_favorites_ui()
            self.show_toast(f"'{item_name}' favorilere başarıyla eklendi.", "success")

    def favoriden_cikar(self, item_name):
        if item_name in self.favoriler:
            self.favoriler.remove(item_name)
            self.update_favorites_ui()
            self.show_toast(f"'{item_name}' favorilerden çıkarıldı.", "warning")

    def update_favorites_ui(self):
        self.fav_screens_list.clear()
        self.fav_screens_list.addItems(self.favoriler)

    # ==========================================
    # DİNAMİK POPUP GÖSTERİM METODU
    # ==========================================
    def show_popup(self, category_name, items, x, y):
        if self.active_popup:
            self.active_popup.deleteLater()
        self.active_popup = MenuPopup(self, category_name, items, self.alt_menu_tiklandi)
        self.active_popup.move(x, y)
        self.active_popup.show()
        self.active_popup.raise_()

    # ==========================================
    # SEKMELİ EKRAN VE GÖRÜNÜM GEÇİŞ METODLARI
    # ==========================================
    def alt_menu_tiklandi(self, item_name):
        self.show_toast(f"'{item_name}' ekranı sekmede açılıyor...", "success")
        self.menu_bar.setVisible(False)
        self.dashboard_container.setVisible(False)
        self.tab_widget.setVisible(True)
        
        # 'Yedekleme' veya alt kaynaklar seçildiğinde panel aç
        if item_name in ["Dolibarr", "WordPress", "WooCommerce", "PrestaShop", "Yedekleme", "MSSQL"]:
            tab_content = YedeklemeYonetimiWidget(item_name, self)
        elif item_name == "Müşteriler":
            tab_content = MusteriYonetimiWidget(self)
        else:
            tab_content = QWidget()
            lyt = QVBoxLayout(tab_content)
            lyt.setContentsMargins(32, 32, 32, 32)
            lbl = QLabel(f"👥 {item_name} Yönetim Modülü\n\nBu ekranın geliştirilmesi devam ediyor.")
            lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
            lbl.setStyleSheet("color: #64748b;")
            lyt.addWidget(lbl)
            lyt.addStretch()
            
        emoji = "📂"
        for cat, (items, em) in self.menu_structure.items():
            if item_name in items:
                emoji = em
                break
        if item_name in ["Dolibarr", "WordPress", "WooCommerce", "PrestaShop", "Yedekleme", "MSSQL"]:
            emoji = "🔄"
                
        idx = self.tab_widget.addTab(tab_content, f"{emoji} {item_name}")
        self.rebuild_plus_tab()
        self.tab_widget.setCurrentIndex(idx)

    def rebuild_plus_tab(self):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "+":
                self.tab_widget.removeTab(i)
                break
        plus_idx = self.tab_widget.addTab(QWidget(), "+")
        tab_bar = self.tab_widget.tabBar()
        tab_bar.setTabButton(plus_idx, QTabBar.ButtonPosition.RightSide, None)

    def close_tab(self, index):
        if self.tab_widget.tabText(index) == "+":
            return
        self.tab_widget.removeTab(index)
        if self.tab_widget.count() <= 1:
            self.show_main_menu()

    def tab_changed(self, index):
        if index >= 0 and self.tab_widget.tabText(index) == "+":
            self.show_main_menu()

    def show_main_menu(self):
        self.tab_widget.clear()
        self.tab_widget.setVisible(False)
        
        self.menu_bar.setVisible(True)
        self.dashboard_container.setVisible(True)

    # ==========================================
    # DİNAMİK YARDIMCI METODLAR
    # ==========================================
    def show_toast(self, message, notif_type="success"):
        toast = ToastNotification(self, message, notif_type)
        toast.show_toast()

    def focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()
        self.show_toast("Arama kutusuna odaklanıldı.", "info")

    def update_live_time(self):
        current_dt = QDateTime.currentDateTime().toString("dd.MM.yyyy HH:mm:ss")
        self.live_time_label.setText(current_dt)

    def mousePressEvent(self, event):
        if self.active_popup and self.active_popup.isVisible():
            if not self.active_popup.geometry().contains(self.mapFromGlobal(QCursor.pos())):
                self.active_popup.hide()
        super().mousePressEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    from PySide6.QtWidgets import QTabBar
    
    window = DolibarrPlusDashboard()
    window.show()
    sys.exit(app.exec())
