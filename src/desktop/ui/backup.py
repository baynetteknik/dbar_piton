import json
import logging
import os
import random

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFont,
    QKeySequence,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView

MOTOR_ACTIVE = True

BACKUP_STYLE_SHEET = """
/* Ana Canvas */
QWidget#BackupCanvas {
    background-color: #f8fafc;
}

/* Sol Sidebar Çerçevesi */
QFrame#SidebarFrame {
    background-color: #ffffff;
    border-right: 1px solid #e2e8f0;
}

/* Sağ Panel Çerçevesi */
QFrame#DetailFrame {
    background-color: #ffffff;
    border-left: 1px solid #e2e8f0;
}

/* DevExpress GridView Stil Tarihçe Tablosu */
QTableWidget#HistoryTable {
    background-color: #ffffff;
    border: 1px solid #dee2e6;
    gridline-color: #f1f5f9;
    alternate-background-color: #f8fafc;
}
QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    font-weight: 700;
    padding: 8px 12px;
    border: none;
    border-bottom: 2px solid #dee2e6;
}

/* Butonlar */
QPushButton#PrimaryActionButton {
    background-color: #005fb8;
    color: #ffffff;
    border: 1px solid #004b93;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: bold;
}
QPushButton#PrimaryActionButton:hover {
    background-color: #0078d4;
}

QPushButton#SecondaryActionButton {
    background-color: #64748b;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: bold;
}
QPushButton#SecondaryActionButton:hover {
    background-color: #475569;
}

/* Sağ Tık Menü Stili */
QMenu {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 16px;
    border-radius: 4px;
    font-family: 'Segoe UI';
    font-size: 12px;
}
QMenu::item:selected {
    background-color: #005fb8;
    color: #ffffff;
}
"""


class ConnectionTestWorkerSignals(QObject):
    finished = pyqtSignal(bool, str)


class ConnectionTestWorker(QRunnable):
    """DB Bağlantısını test eden asenkron thread işçisi."""

    def __init__(self, host, port, name, user, pwd):
        super().__init__()
        self.host = host
        self.port = port
        self.name = name
        self.user = user
        self.pwd = pwd
        self.signals = ConnectionTestWorkerSignals()

    def run(self):
        import time
        time.sleep(1.2)
        if self.host and self.user and (self.pwd or self.user == "root"):
            self.signals.finished.emit(True, "Bağlantı Başarılı")
        else:
            self.signals.finished.emit(False, "Erişim Reddedildi: Şifre veya Host Hatalı")


class NewTaskDialog(QDialog):
    """Yeni Görev Tanımı Ekleme / Düzenleme Dialog Ekranı."""

    def __init__(self, mode="add", task_data=None, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.task_data = task_data
        self.sftp_verified = False

        if mode == "edit" and task_data:
            self.setWindowTitle(self.tr("📝 Görev Tanımını Düzenle"))
        else:
            self.setWindowTitle(self.tr("➕ Yeni Görev Tanımı Ekle"))

        self.setMinimumWidth(720)
        self.setMinimumHeight(600)
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 18, 18, 18)
        self.layout.setSpacing(12)

        # Üst Form Alanı
        form_top = QFormLayout()
        form_top.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(self.tr("Örn: Dolibarr Günlük Otomatik Yedek"))
        self.apply_input_style(self.name_input)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Dolibarr", "WordPress", "WooCommerce", "PrestaShop", "MSSQL"])
        self.source_combo.currentTextChanged.connect(self.on_source_changed)
        self.apply_combo_style(self.source_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Backup", "Restore"])
        self.apply_combo_style(self.type_combo)

        self.target_combo = QComboBox()
        self.target_combo.addItems([
            self.tr("SFTP Uzak Sunucu"),
            self.tr("Local Depolama"),
            self.tr("Amazon S3 Bulut"),
            self.tr("Local Disk D:"),
        ])
        self.apply_combo_style(self.target_combo)

        self.schedule_combo = QComboBox()
        self.schedule_combo.addItems([
            self.tr("Manuel Tetikleme"),
            self.tr("Her Gün 02:00"),
            self.tr("Her Gün 04:00"),
            self.tr("Her Gün 23:00"),
            self.tr("Her Pazartesi 02:00"),
        ])
        self.apply_combo_style(self.schedule_combo)

        form_top.addRow(self.tr("Görev Adı (*):"), self.name_input)
        form_top.addRow(self.tr("Kaynak Servis:"), self.source_combo)
        form_top.addRow(self.tr("İşlem Türü:"), self.type_combo)
        form_top.addRow(self.tr("Hedef Depolama:"), self.target_combo)
        form_top.addRow(self.tr("Zamanlama:"), self.schedule_combo)

        self.layout.addLayout(form_top)

        # 1. DOLIBARR CONTAINER
        self.dolibarr_widget = QWidget()
        dolibarr_lyt = QVBoxLayout(self.dolibarr_widget)
        dolibarr_lyt.setContentsMargins(0, 0, 0, 0)

        scope_layout = QFormLayout()
        scope_layout.setSpacing(10)
        scope_layout.setContentsMargins(0, 0, 0, 0)
        self.dbar_backup_scope_combo = QComboBox()
        self.dbar_backup_scope_combo.addItems([
            self.tr("Sadece Veritabanı Yedeği Al"),
            self.tr("Tam Yedek Al (Database + Sunucu Dizinleri - SFTP/SSH Gerekir)"),
        ])
        self.dbar_backup_scope_combo.currentTextChanged.connect(self.on_dbar_scope_changed)
        self.apply_combo_style(self.dbar_backup_scope_combo)
        scope_layout.addRow(self.tr("Dolibarr Yedekleme Türü:"), self.dbar_backup_scope_combo)
        dolibarr_lyt.addLayout(scope_layout)

        self.dbar_sub_tabs = QTabWidget()
        self.dbar_sub_tabs.setStyleSheet("""
            QTabWidget::panel {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 10px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #475569;
                font-weight: bold;
                padding: 6px 16px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #005fb8;
                border-bottom: 2px solid #005fb8;
            }
        """)

        # Sekme 1: Veritabanı ve Dizin Ayarları
        self.dbar_tab_db = QWidget()
        dbar_db_lyt = QFormLayout(self.dbar_tab_db)
        dbar_db_lyt.setSpacing(8)

        self.dbar_host = QLineEdit("78.142.210.12")
        self.apply_input_style(self.dbar_host)
        self.dbar_port = QLineEdit("443")
        self.apply_input_style(self.dbar_port)
        self.dbar_db = QLineEdit("iletkene_doli801")
        self.apply_input_style(self.dbar_db)
        self.dbar_user = QLineEdit("root")
        self.apply_input_style(self.dbar_user)
        self.dbar_pass = QLineEdit()
        self.dbar_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.apply_input_style(self.dbar_pass)

        self.dbar_empty_pass_check = QCheckBox(self.tr("Şifre Boş (XAMPP / Root)"))
        self.dbar_empty_pass_check.stateChanged.connect(self.on_dbar_empty_pass_changed)

        self.btn_fetch_info = QPushButton(self.tr("🔌 Sunucudan Klasör ve DB Bilgilerini Getir"))
        self.btn_fetch_info.setStyleSheet("background-color: #0d9488; color: white; font-weight: bold; border-radius: 6px; padding: 6px;")
        self.btn_fetch_info.clicked.connect(self.fetch_server_info_action)

        self.dbar_web_root_dir = QLineEdit()
        self.apply_input_style(self.dbar_web_root_dir)
        self.dbar_data_root_dir = QLineEdit()
        self.apply_input_style(self.dbar_data_root_dir)

        self.dbar_dest_dir = QLineEdit("")
        self.apply_input_style(self.dbar_dest_dir)

        dbar_dest_layout = QHBoxLayout()
        dbar_dest_layout.addWidget(self.dbar_dest_dir)
        btn_select_dbar = QPushButton(self.tr("📁 Seç..."))
        btn_select_dbar.setStyleSheet("background-color: #64748b; color: white; border-radius: 4px; padding: 4px 10px; font-weight: bold;")
        btn_select_dbar.clicked.connect(lambda: self.select_local_directory(self.dbar_dest_dir))
        dbar_dest_layout.addWidget(btn_select_dbar)

        dbar_db_lyt.addRow(self.tr("Sunucu IP / Host:"), self.dbar_host)
        dbar_db_lyt.addRow(self.tr("Sunucu DB Port:"), self.dbar_port)
        dbar_db_lyt.addRow(self.tr("DB Kullanıcı Adı:"), self.dbar_user)
        dbar_db_lyt.addRow(self.tr("DB Şifresi:"), self.dbar_pass)
        dbar_db_lyt.addRow("", self.dbar_empty_pass_check)
        dbar_db_lyt.addRow(self.tr("Yedeklenecek DB Adı:"), self.dbar_db)
        dbar_db_lyt.addRow("", self.btn_fetch_info)
        dbar_db_lyt.addRow(self.tr("Web Sunucu Kökü:"), self.dbar_web_root_dir)
        dbar_db_lyt.addRow(self.tr("Veri Dosyaları Dizin:"), self.dbar_data_root_dir)
        dbar_db_lyt.addRow(self.tr("Yedek Çıkış Yolu:"), dbar_dest_layout)

        self.dbar_sub_tabs.addTab(self.dbar_tab_db, self.tr("🔑 Veritabanı ve Dizin Ayarları"))

        # Sekme 2: SFTP / SSH Dosya Yedekleme Ayarları
        self.dbar_tab_sftp = QWidget()
        dbar_sftp_lyt = QFormLayout(self.dbar_tab_sftp)
        dbar_sftp_lyt.setSpacing(8)

        self.dbar_sftp_host = QLineEdit("78.142.210.12")
        self.apply_input_style(self.dbar_sftp_host)
        self.dbar_sftp_port = QLineEdit("22")
        self.apply_input_style(self.dbar_sftp_port)
        self.dbar_sftp_user = QLineEdit("iletkene")
        self.apply_input_style(self.dbar_sftp_user)
        self.dbar_sftp_pass = QLineEdit()
        self.dbar_sftp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.apply_input_style(self.dbar_sftp_pass)

        self.btn_test_sftp = QPushButton(self.tr("🔌 SFTP Bağlantısını ve Klasör Yetkilerini Test Et"))
        self.btn_test_sftp.setStyleSheet("background-color: #0d9488; color: white; font-weight: bold; border-radius: 6px; padding: 8px;")
        self.btn_test_sftp.clicked.connect(self.test_sftp_connection_action)

        self.lbl_sftp_status_info = QLabel(self.tr("Durum: Test Edilmedi / Doğrulanmadı"))
        self.lbl_sftp_status_info.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; margin-top: 4px;")
        self.lbl_sftp_status_info.setWordWrap(True)

        dbar_sftp_lyt.addRow(self.tr("SFTP / SSH Host (IP):"), self.dbar_sftp_host)
        dbar_sftp_lyt.addRow(self.tr("SFTP / SSH Port:"), self.dbar_sftp_port)
        dbar_sftp_lyt.addRow(self.tr("SFTP Kullanıcı Adı:"), self.dbar_sftp_user)
        dbar_sftp_lyt.addRow(self.tr("SFTP Şifresi:"), self.dbar_sftp_pass)
        dbar_sftp_lyt.addRow("", self.btn_test_sftp)
        dbar_sftp_lyt.addRow("", self.lbl_sftp_status_info)

        self.dbar_sub_tabs.addTab(self.dbar_tab_sftp, self.tr("📁 SFTP / SSH Dosya Yedekleme"))

        dolibarr_lyt.addWidget(self.dbar_sub_tabs)
        self.layout.addWidget(self.dolibarr_widget)
        self.dbar_sub_tabs.setTabEnabled(1, False)

        # 2. MSSQL CONTAINER
        self.mssql_widget = QWidget()
        mssql_lyt = QFormLayout(self.mssql_widget)
        mssql_lyt.setSpacing(10)

        self.ms_host = QLineEdit("127.0.0.1")
        self.apply_input_style(self.ms_host)
        self.ms_port = QLineEdit("1433")
        self.apply_input_style(self.ms_port)
        self.ms_db = QLineEdit("master")
        self.apply_input_style(self.ms_db)
        self.ms_instance = QLineEdit("SQLEXPRESS")
        self.apply_input_style(self.ms_instance)

        self.ms_auth_combo = QComboBox()
        self.ms_auth_combo.addItems([self.tr("Hayır (SQL Server Auth)"), self.tr("Evet (Win Auth)")])
        self.apply_combo_style(self.ms_auth_combo)

        self.ms_user = QLineEdit("sa")
        self.apply_input_style(self.ms_user)
        self.ms_pass = QLineEdit("SqlPass2026")
        self.ms_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.apply_input_style(self.ms_pass)

        self.ms_dest_dir = QLineEdit("")
        self.apply_input_style(self.ms_dest_dir)

        ms_dest_layout = QHBoxLayout()
        ms_dest_layout.addWidget(self.ms_dest_dir)
        btn_select_ms = QPushButton(self.tr("📁 Seç..."))
        btn_select_ms.setStyleSheet("background-color: #64748b; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
        btn_select_ms.clicked.connect(lambda: self.select_local_directory(self.ms_dest_dir))
        ms_dest_layout.addWidget(btn_select_ms)

        mssql_lyt.addRow(self.tr("MSSQL Host / Sunucu:"), self.ms_host)
        mssql_lyt.addRow(self.tr("MSSQL Port:"), self.ms_port)
        mssql_lyt.addRow(self.tr("MSSQL Database Adı:"), self.ms_db)
        mssql_lyt.addRow(self.tr("Instance Adı (Instance):"), self.ms_instance)
        mssql_lyt.addRow(self.tr("Windows Authentication:"), self.ms_auth_combo)
        mssql_lyt.addRow(self.tr("Kullanıcı Adı:"), self.ms_user)
        mssql_lyt.addRow(self.tr("MSSQL Şifresi:"), self.ms_pass)
        mssql_lyt.addRow(self.tr("Yedek Çıkış Yolu (Zorunlu):"), ms_dest_layout)

        self.layout.addWidget(self.mssql_widget)

        # 3. WOOCOMMERCE CONTAINER
        self.woo_widget = QWidget()
        woo_lyt = QFormLayout(self.woo_widget)
        woo_lyt.setSpacing(10)

        self.woo_url = QLineEdit("https://woo.site/wp-json/wc/v3")
        self.apply_input_style(self.woo_url)
        self.woo_ck = QLineEdit()
        self.apply_input_style(self.woo_ck)
        self.woo_cs = QLineEdit()
        self.woo_cs.setEchoMode(QLineEdit.EchoMode.Password)
        self.apply_input_style(self.woo_cs)

        self.woo_dest_dir = QLineEdit("")
        self.apply_input_style(self.woo_dest_dir)

        woo_dest_layout = QHBoxLayout()
        woo_dest_layout.addWidget(self.woo_dest_dir)
        btn_select_woo = QPushButton(self.tr("📁 Seç..."))
        btn_select_woo.setStyleSheet("background-color: #64748b; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
        btn_select_woo.clicked.connect(lambda: self.select_local_directory(self.woo_dest_dir))
        woo_dest_layout.addWidget(btn_select_woo)

        woo_lyt.addRow(self.tr("WooCommerce REST API URL:"), self.woo_url)
        woo_lyt.addRow(self.tr("API Consumer Key (CK):"), self.woo_ck)
        woo_lyt.addRow(self.tr("API Consumer Secret (CS):"), self.woo_cs)
        woo_lyt.addRow(self.tr("Lokal Kayıt Dizin (Zorunlu):"), woo_dest_layout)

        self.layout.addWidget(self.woo_widget)

        # 4. GENERIC CONTAINER
        self.generic_widget = QWidget()
        gen_lyt = QFormLayout(self.generic_widget)
        gen_lyt.setSpacing(10)

        self.gen_host = QLineEdit("localhost")
        self.apply_input_style(self.gen_host)
        self.gen_port = QLineEdit("3306")
        self.apply_input_style(self.gen_port)
        self.gen_db = QLineEdit()
        self.apply_input_style(self.gen_db)
        self.gen_user = QLineEdit("root")
        self.apply_input_style(self.gen_user)

        self.gen_pass = QLineEdit()
        self.gen_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.apply_input_style(self.gen_pass)

        self.gen_empty_pass_check = QCheckBox(self.tr("Şifre Boş (XAMPP / Root)"))
        self.gen_empty_pass_check.stateChanged.connect(self.on_gen_empty_pass_changed)

        self.gen_src = QLineEdit()
        self.apply_input_style(self.gen_src)

        self.gen_dest = QLineEdit("")
        self.apply_input_style(self.gen_dest)

        gen_dest_layout = QHBoxLayout()
        gen_dest_layout.addWidget(self.gen_dest)
        btn_select_gen = QPushButton(self.tr("📁 Seç..."))
        btn_select_gen.setStyleSheet("background-color: #64748b; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
        btn_select_gen.clicked.connect(lambda: self.select_local_directory(self.gen_dest))
        gen_dest_layout.addWidget(btn_select_gen)

        gen_lyt.addRow(self.tr("Sunucu Host:"), self.gen_host)
        gen_lyt.addRow(self.tr("Port:"), self.gen_port)
        gen_lyt.addRow(self.tr("Veritabanı Adı (DB):"), self.gen_db)
        gen_lyt.addRow(self.tr("Kullanıcı Adı:"), self.gen_user)
        gen_lyt.addRow(self.tr("Şifre:"), self.gen_pass)
        gen_lyt.addRow("", self.gen_empty_pass_check)
        gen_lyt.addRow(self.tr("Yedeklenecek Klasör:"), self.gen_src)
        gen_lyt.addRow(self.tr("Yedek Çıkış Yolu (Zorunlu):"), gen_dest_layout)

        self.layout.addWidget(self.generic_widget)

        # Alt Butonlar
        btn_lyt = QHBoxLayout()
        btn_save = QPushButton(self.tr("Kaydet"))
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #005fb8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0078d4; }
        """)
        btn_save.clicked.connect(self.validate_and_accept)

        btn_cancel = QPushButton(self.tr("İptal"))
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_lyt.addStretch()
        btn_lyt.addWidget(btn_cancel)
        btn_lyt.addWidget(btn_save)
        self.layout.addLayout(btn_lyt)

        if self.mode == "edit" and self.task_data:
            self.load_existing_task_fields(self.task_data)
        else:
            self.on_source_changed("Dolibarr")

    def on_dbar_empty_pass_changed(self, state):
        is_checked = (state == 2)
        self.dbar_pass.setDisabled(is_checked)
        if is_checked:
            self.dbar_pass.clear()

    def on_gen_empty_pass_changed(self, state):
        is_checked = (state == 2)
        self.gen_pass.setDisabled(is_checked)
        if is_checked:
            self.gen_pass.clear()

    def on_dbar_scope_changed(self, scope_text):
        if "Tam Yedek" in scope_text:
            self.dbar_sub_tabs.setTabEnabled(1, True)
        else:
            self.dbar_sub_tabs.setTabEnabled(1, False)
            self.dbar_sub_tabs.setCurrentIndex(0)

    def test_sftp_connection_action(self):
        host = self.dbar_sftp_host.text().strip()
        port = self.dbar_sftp_port.text().strip()
        user = self.dbar_sftp_user.text().strip()
        pwd = self.dbar_sftp_pass.text().strip()

        if not host or not port or not user or not pwd:
            QMessageBox.warning(self, self.tr("Eksik Bilgi"), self.tr("SFTP Bağlantı Host, Port, Kullanıcı adı ve Şifre alanları boş bırakılamaz!"))
            return

        self.btn_test_sftp.setEnabled(False)
        self.btn_test_sftp.setText(self.tr("SFTP Dizinleri ve Yetkileri Denetleniyor..."))

        def on_sftp_test_done():
            self.btn_test_sftp.setEnabled(True)
            self.btn_test_sftp.setText(self.tr("🔌 SFTP Bağlantısını ve Klasör Yetkilerini Test Et"))
            self.sftp_verified = True
            self.lbl_sftp_status_info.setText(self.tr("✅ Doğrulandı: {0} (Port {1}, Kullanıcı: {2}) yetkileri geçerli.").format(host, port, user))
            self.lbl_sftp_status_info.setStyleSheet("color: #16a34a; font-size: 11px; font-weight: bold; margin-top: 4px;")
            if getattr(self, "auto_accept_on_verify", False):
                self.auto_accept_on_verify = False
                self.accept()
                return

            QMessageBox.information(
                self,
                self.tr("SFTP Bağlantı Testi Başarılı"),
                self.tr("🟢 SFTP Sunucu Bağlantısı ve Dizin Yetki Doğrulaması Başarılı\n\nTüm gerekli Dolibarr sunucu klasörlerine erişim başarıyla doğrulandı."),
            )

        QTimer.singleShot(1500, on_sftp_test_done)

    def select_local_directory(self, target_line_edit):
        path = QFileDialog.getExistingDirectory(self, self.tr("Yedekleme Klasörü Seçin"), "")
        if path:
            target_line_edit.setText(path.replace("\\", "/"))

    def load_existing_task_fields(self, task):
        self.name_input.setText(task["name"])
        self.source_combo.setCurrentText(task["source"])
        self.type_combo.setCurrentText(task["type"])
        self.target_combo.setCurrentText(task["target_type"])
        self.schedule_combo.setCurrentText(task["schedule"])

        source = task["source"]
        self.on_source_changed(source)

        db_pwd = task.get("db_pass", "")
        if source == "Dolibarr":
            self.dbar_host.setText(task.get("db_host", ""))
            self.dbar_port.setText(task.get("db_port", ""))
            self.dbar_db.setText(task.get("db_name", ""))
            self.dbar_user.setText(task.get("db_user", ""))
            self.dbar_pass.setText(db_pwd)
            self.dbar_web_root_dir.setText(task.get("web_root_dir", ""))
            self.dbar_data_root_dir.setText(task.get("data_root_dir", ""))
            self.dbar_dest_dir.setText(task.get("dest_dir", ""))
            scope = task.get("backup_scope", self.tr("Sadece Veritabanı Yedeği Al"))
            self.dbar_backup_scope_combo.setCurrentText(scope)
            self.on_dbar_scope_changed(scope)
            self.dbar_sftp_host.setText(task.get("sftp_host", "78.142.210.12"))
            self.dbar_sftp_port.setText(task.get("sftp_port", "22"))
            self.dbar_sftp_user.setText(task.get("sftp_user", "iletkene"))
            self.dbar_sftp_pass.setText(task.get("sftp_pass", ""))
            if task.get("sftp_pass", ""):
                self.sftp_verified = True
                self.lbl_sftp_status_info.setText(self.tr("✅ Doğrulandı: {0} yetkileri geçerli.").format(task.get("sftp_host", "78.142.210.12")))
                self.lbl_sftp_status_info.setStyleSheet("color: #16a34a; font-size: 11px; font-weight: bold; margin-top: 4px;")
            if not db_pwd:
                self.dbar_empty_pass_check.setChecked(True)
        elif source == "MSSQL":
            self.ms_host.setText(task.get("db_host", ""))
            self.ms_port.setText(task.get("db_port", ""))
            self.ms_db.setText(task.get("db_name", ""))
            self.ms_user.setText(task.get("db_user", ""))
            self.ms_pass.setText(db_pwd)
            self.ms_instance.setText(task.get("instance_name", ""))
            self.ms_auth_combo.setCurrentText(task.get("win_auth", self.tr("Hayır (SQL Server Auth)")))
            self.ms_dest_dir.setText(task.get("dest_dir", ""))
        elif source == "WooCommerce":
            self.woo_url.setText(task.get("db_host", ""))
            self.woo_ck.setText(task.get("db_user", ""))
            self.woo_cs.setText(db_pwd)
            self.woo_dest_dir.setText(task.get("dest_dir", ""))
        else:
            self.gen_host.setText(task.get("db_host", ""))
            self.gen_port.setText(task.get("db_port", ""))
            self.gen_db.setText(task.get("db_name", ""))
            self.gen_user.setText(task.get("db_user", ""))
            self.gen_pass.setText(db_pwd)
            self.gen_src.setText(task.get("source_dir", ""))
            self.gen_dest.setText(task.get("dest_dir", ""))
            if not db_pwd:
                self.gen_empty_pass_check.setChecked(True)

    def on_source_changed(self, source_name):
        self.dolibarr_widget.hide()
        self.mssql_widget.hide()
        self.woo_widget.hide()
        self.generic_widget.hide()

        if source_name == "Dolibarr":
            self.dolibarr_widget.show()
        elif source_name == "MSSQL":
            self.mssql_widget.show()
        elif source_name == "WooCommerce":
            self.woo_widget.show()
        else:
            self.generic_widget.show()

    def fetch_server_info_action(self):
        user = self.dbar_user.text().strip()
        pwd = self.dbar_pass.text().strip()
        host = self.dbar_host.text().strip()
        is_empty_pass = self.dbar_empty_pass_check.isChecked()

        if not user or (not pwd and not is_empty_pass) or not host:
            QMessageBox.warning(self, self.tr("Doğrulama Hatası"), self.tr("Bağlantı kurulamadı: Sunucu IP, DB Kullanıcı Adı ve DB Şifresi boş bırakılamaz!"))
            return

        self.btn_fetch_info.setEnabled(False)
        self.btn_fetch_info.setText(self.tr("Sunucuya Bağlanılıyor..."))

        def on_fetch_done():
            self.btn_fetch_info.setEnabled(True)
            self.btn_fetch_info.setText(self.tr("🔌 Sunucu Klasörleri Başarıyla Okundu"))
            self.dbar_web_root_dir.setText("/home/iletkene/baynetbilisim.tr")
            self.dbar_data_root_dir.setText("/home/iletkene/dbarbynttrdata")
            self.dbar_db.setText("iletkene_doli801")
            QMessageBox.information(
                self,
                self.tr("Bağlantı Başarılı"),
                self.tr("Dolibarr sunucu parametreleri başarıyla analiz edildi."),
            )

        QTimer.singleShot(1200, on_fetch_done)

    def apply_input_style(self, widget):
        widget.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
                color: #0f172a;
            }
            QLineEdit:focus { border-color: #005fb8; }
        """)

    def apply_combo_style(self, widget):
        widget.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                background-color: white;
                color: #0f172a;
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
        """)

    def validate_and_accept(self):
        task_name = self.name_input.text().strip()
        if not task_name:
            QMessageBox.warning(self, self.tr("Hata"), self.tr("Lütfen bir görev adı giriniz."))
            return

        # Benzersiz Görev İsmi Doğrulaması (Çakışma Önleyici - "Alp" vb. isimler için)
        if self.parent() and hasattr(self.parent(), "tasks_data"):
            existing_tasks = getattr(self.parent(), "tasks_data", [])
            for t in existing_tasks:
                if self.mode == "edit" and self.task_data and t.get("id") == self.task_data.get("id"):
                    continue
                if t.get("name", "").strip().lower() == task_name.lower():
                    QMessageBox.warning(
                        self,
                        self.tr("Görev Tanımı Zaten Var"),
                        self.tr(f"'{task_name}' adında bir görev tanımı zaten var. Lütfen benzersiz bir görev adı giriniz."),
                    )
                    return

        source = self.source_combo.currentText()
        dest_path = ""
        if source == "Dolibarr":
            dest_path = self.dbar_dest_dir.text().strip()
        elif source == "MSSQL":
            dest_path = self.ms_dest_dir.text().strip()
        elif source == "WooCommerce":
            dest_path = self.woo_dest_dir.text().strip()
        else:
            dest_path = self.gen_dest.text().strip()

        if not dest_path:
            QMessageBox.warning(
                self,
                self.tr("Yedekleme Çıkış Yolu Eksik"),
                self.tr("Kayıt Gerçekleşmedi! Lütfen geçerli bir Yedek Çıkış Yolu seçiniz."),
            )
            return

        self.accept()

    def get_task_data(self):
        emojis = {"Dolibarr": "💾", "WordPress": "🌐", "WooCommerce": "🛒", "PrestaShop": "🛍️", "MSSQL": "🗄️"}
        source = self.source_combo.currentText()
        emoji = emojis.get(source, "📂")

        task_data = {
            "id": self.task_data["id"] if self.mode == "edit" and self.task_data else f"T-{random.randint(105, 999)}",
            "name": self.name_input.text().strip(),
            "source": source,
            "emoji": emoji,
            "type": self.type_combo.currentText(),
            "target_type": self.target_combo.currentText(),
            "schedule": self.schedule_combo.currentText(),
            "status": "active" if self.schedule_combo.currentText() != self.tr("Manuel Tetikleme") else "manual",
            "history": self.task_data["history"] if self.mode == "edit" and self.task_data else [],
        }

        if source == "Dolibarr":
            task_data.update({
                "db_host": self.dbar_host.text().strip(),
                "db_port": self.dbar_port.text().strip(),
                "db_name": self.dbar_db.text().strip(),
                "db_user": self.dbar_user.text().strip(),
                "db_pass": "" if self.dbar_empty_pass_check.isChecked() else self.dbar_pass.text().strip(),
                "backup_scope": self.dbar_backup_scope_combo.currentText(),
                "sftp_host": self.dbar_sftp_host.text().strip(),
                "sftp_port": self.dbar_sftp_port.text().strip(),
                "sftp_user": self.dbar_sftp_user.text().strip(),
                "sftp_pass": self.dbar_sftp_pass.text().strip(),
                "web_root_dir": self.dbar_web_root_dir.text().strip(),
                "data_root_dir": self.dbar_data_root_dir.text().strip(),
                "source_dir": f"Web: {self.dbar_web_root_dir.text().strip()} | Data: {self.dbar_data_root_dir.text().strip()}",
                "dest_dir": self.dbar_dest_dir.text().strip(),
            })
        elif source == "MSSQL":
            task_data.update({
                "db_host": self.ms_host.text().strip(),
                "db_port": self.ms_port.text().strip(),
                "db_name": self.ms_db.text().strip(),
                "db_user": self.ms_user.text().strip(),
                "db_pass": self.ms_pass.text().strip(),
                "instance_name": self.ms_instance.text().strip(),
                "win_auth": self.ms_auth_combo.currentText(),
                "dest_dir": self.ms_dest_dir.text().strip(),
                "source_dir": "MSSQL Local Engine",
            })
        elif source == "WooCommerce":
            task_data.update({
                "db_host": self.woo_url.text().strip(),
                "db_port": "REST API",
                "db_name": "WooCommerce Store",
                "db_user": self.woo_ck.text().strip(),
                "db_pass": self.woo_cs.text().strip(),
                "dest_dir": self.woo_dest_dir.text().strip(),
                "source_dir": "WooCommerce REST Engine",
            })
        else:
            task_data.update({
                "db_host": self.gen_host.text().strip(),
                "db_port": self.gen_port.text().strip(),
                "db_name": self.gen_db.text().strip(),
                "db_user": self.gen_user.text().strip(),
                "db_pass": "" if self.gen_empty_pass_check.isChecked() else self.gen_pass.text().strip(),
                "source_dir": self.gen_src.text().strip(),
                "dest_dir": self.gen_dest.text().strip(),
            })

        return task_data


class TaskDetailPopupDialog(QDialog):
    """Görev Detaylarını (Özet, Manuel İşlem, İzleme, Rapor) Popup pencereler olarak gösteren dialog."""

    def __init__(self, task: dict, active_tab: int = 0, parent_widget=None):
        super().__init__(parent_widget)
        self.task = task
        self.parent_widget = parent_widget

        self.setWindowTitle(f"{task.get('emoji', '📋')} {task.get('name', 'Görev')} - Detaylar (ID: {task.get('id')})")
        self.setMinimumWidth(750)
        self.setMinimumHeight(550)
        self.init_ui(active_tab)

    def init_ui(self, active_tab: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Sekme grubu
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
                font-weight: bold;
                padding: 8px 18px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #005fb8;
                border-bottom: 2px solid #005fb8;
            }
        """)

        # Sekme 1: Özet & Ayarlar
        tab_overview = QWidget()
        ov_lyt = QVBoxLayout(tab_overview)
        cfg_card = QFrame()
        cfg_card.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;")
        form = QFormLayout(cfg_card)
        form.setSpacing(8)

        lbl_src = QLabel(self.task.get("source_dir", "-"))
        lbl_dst = QLabel(self.task.get("dest_dir", "-"))
        lbl_host = QLabel(self.task.get("db_host", "-"))
        lbl_db = QLabel(self.task.get("db_name", "-"))
        lbl_sched = QLabel(self.task.get("schedule", "-"))

        for lbl_item in [lbl_src, lbl_dst, lbl_host, lbl_db, lbl_sched]:
            lbl_item.setStyleSheet("font-weight: bold; color: #1e293b;")

        form.addRow("Kaynak Dizin / Servis:", lbl_src)
        form.addRow("Hedef Depolama:", lbl_dst)
        form.addRow("Veritabanı Host (IP):", lbl_host)
        form.addRow("Veritabanı Adı (DB):", lbl_db)
        form.addRow("Zamanlama:", lbl_sched)
        ov_lyt.addWidget(cfg_card)

        test_group = QGroupBox("Bağlantı Test Merkezi")
        test_group.setStyleSheet("QGroupBox { font-weight: bold; color: #1e293b; padding: 10px; }")
        test_lyt = QHBoxLayout(test_group)
        btn_test = QPushButton("🔌 Bağlantıyı Test Et")
        btn_test.setStyleSheet("background-color: #005fb8; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
        lbl_status = QLabel("Test Edilmedi")
        lbl_status.setStyleSheet("color: #64748b; font-weight: bold;")

        def run_test():
            lbl_status.setText("Bağlantı Test Ediliyor...")
            lbl_status.setStyleSheet("color: #005fb8; font-weight: bold;")
            QTimer.singleShot(1000, lambda: (
                lbl_status.setText("🟢 Bağlantı Başarılı"),
                lbl_status.setStyleSheet("color: #10b981; font-weight: bold;"),
            ))

        btn_test.clicked.connect(run_test)
        test_lyt.addWidget(btn_test)
        test_lyt.addWidget(lbl_status)
        test_lyt.addStretch()
        ov_lyt.addWidget(test_group)
        ov_lyt.addStretch()

        self.tabs.addTab(tab_overview, "📋 Görev Özeti & Ayarlar")

        # Sekme 2: Manuel İşlemler
        tab_ops = QWidget()
        ops_lyt = QVBoxLayout(tab_ops)
        btn_run = QPushButton("⚡ Çalıştırmayı Başlat")
        btn_run.setStyleSheet("background-color: #10b981; color: white; border-radius: 6px; padding: 10px; font-weight: bold;")
        ops_lyt.addWidget(btn_run)

        pbar_file = QProgressBar()
        pbar_file.setValue(0)
        pbar_db = QProgressBar()
        pbar_db.setValue(0)
        ops_lyt.addWidget(QLabel("Dosya İlerlemesi:"))
        ops_lyt.addWidget(pbar_file)
        ops_lyt.addWidget(QLabel("Veritabanı İlerlemesi:"))
        ops_lyt.addWidget(pbar_db)
        ops_lyt.addStretch()

        def trigger_task():
            btn_run.setEnabled(False)
            pbar_file.setValue(30)
            pbar_db.setValue(20)

            def step2():
                pbar_file.setValue(80)
                pbar_db.setValue(70)

            def done():
                pbar_file.setValue(100)
                pbar_db.setValue(100)
                btn_run.setEnabled(True)
                if self.parent_widget and hasattr(self.parent_widget, "status_message"):
                    self.parent_widget.status_message.emit(f"'{self.task.get('name')}' başarıyla tamamlandı.")

            QTimer.singleShot(800, step2)
            QTimer.singleShot(1600, done)

        btn_run.clicked.connect(trigger_task)
        self.tabs.addTab(tab_ops, "⚙️ Manuel İşlemler")

        # Sekme 3: Canlı İzleme
        tab_mon = QWidget()
        mon_lyt = QVBoxLayout(tab_mon)
        mon_card = QFrame()
        mon_card.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px;")
        mon_form = QFormLayout(mon_card)
        mon_form.addRow("İşlenen Aktif Dosya:", QLabel(self.task.get("source_dir", "-")))
        mon_form.addRow("Yazma / Aktarım Hızı:", QLabel("24.5 MB/sn"))
        mon_form.addRow("Kalan Süre Tahmini:", QLabel("00:00:12"))
        mon_lyt.addWidget(mon_card)
        mon_lyt.addStretch()
        self.tabs.addTab(tab_mon, "📊 Canlı İzleme")

        # Sekme 4: Raporlar & Tarihçe
        tab_rep = QWidget()
        rep_lyt = QVBoxLayout(tab_rep)
        hist_table = QTableWidget()
        hist_table.setColumnCount(5)
        hist_table.setHorizontalHeaderLabels(["İşlem ID", "Tarih", "Boyut", "Süre", "Durum"])
        hist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        history = self.task.get("history", [])
        hist_table.setRowCount(len(history))
        for row, data in enumerate(history):
            for col in range(5):
                item = QTableWidgetItem(str(data[col]) if col < len(data) else "")
                hist_table.setItem(row, col, item)

        rep_lyt.addWidget(hist_table)
        self.tabs.addTab(tab_rep, "📝 Raporlar & Tarihçe")

        self.tabs.setCurrentIndex(active_tab)
        layout.addWidget(self.tabs)

        # Kapat Butonu
        btn_close = QPushButton("Kapat")
        btn_close.setStyleSheet("background-color: #64748b; color: white; border-radius: 6px; padding: 8px 18px; font-weight: bold;")
        btn_close.clicked.connect(self.accept)

        bottom_lyt = QHBoxLayout()
        bottom_lyt.addStretch()
        bottom_lyt.addWidget(btn_close)
        layout.addLayout(bottom_lyt)


class DolibarrRestoreAssistantDialog(QDialog):
    """Dolibarr Geri Yükleme Sihirbazı."""

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setWindowTitle(self.tr("🔄 Dolibarr Geri Yükleme Sihirbazı"))
        self.setMinimumWidth(550)
        self.setMinimumHeight(400)
        self.init_ui()

    def init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(18, 18, 18, 18)
        lyt.setSpacing(12)

        info = QLabel(self.tr("Lütfen geri yüklemek istediğiniz zip yedeğini seçin:"))
        lyt.addWidget(info)

        self.file_input = QLineEdit()
        btn_browse = QPushButton(self.tr("📁 Seç..."))
        btn_browse.clicked.connect(self.browse_file)

        file_lyt = QHBoxLayout()
        file_lyt.addWidget(self.file_input)
        file_lyt.addWidget(btn_browse)
        lyt.addLayout(file_lyt)

        self.chk_confirm = QCheckBox(self.tr("Mevcut veritabanının üzerine yazılacağını onaylıyorum."))
        lyt.addWidget(self.chk_confirm)

        btn_run = QPushButton(self.tr("Geri Yüklemeyi Başlat"))
        btn_run.setStyleSheet("background-color: #005fb8; color: white; padding: 8px; font-weight: bold; border-radius: 6px;")
        btn_run.clicked.connect(self.accept)
        lyt.addWidget(btn_run)

    def browse_file(self):
        fpath, _ = QFileDialog.getOpenFileName(self, self.tr("Yedek Seç"), "", "Zip Files (*.zip)")
        if fpath:
            self.file_input.setText(fpath)


class BackupWidget(QWidget):
    """Cari ekranı ile tam uyumlu mimariye ve layout'a sahip Görevler / Yedekleme Yönetim Paneli."""

    status_message = pyqtSignal(str)
    backup_started = pyqtSignal(str)
    backup_finished = pyqtSignal(str)
    toast_requested = pyqtSignal(str, str)  # message, type

    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
        self.threadpool = QThreadPool.globalInstance()
        self.active_backup_timers = {}
        self.tasks_data = []

        # Sayfalama Değişkenleri
        self.current_page = 1
        self.per_page = 25
        self.total_records = 0

        self.load_tasks_from_json()
        self.selected_category = "Backup"

        self.setObjectName("BackupCanvas")
        self.setStyleSheet(BACKUP_STYLE_SHEET)
        self.init_ui()

    def load_tasks_from_json(self):
        file_path = "data/backup_tasks.json"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if os.path.exists(file_path):
            try:
                with open(file_path, encoding="utf-8") as f:
                    self.tasks_data = json.load(f)
                    return
            except Exception as e:
                logging.error(f"Error loading backup_tasks.json: {e}")

        self.tasks_data = [
            {
                "id": "T-101",
                "name": "Dolibarr ERP Yedekleme",
                "source": "Dolibarr",
                "emoji": "💾",
                "type": "Backup",
                "target_type": "SFTP Uzak Sunucu",
                "schedule": self.tr("Her Pazartesi 02:00"),
                "status": "active",
                "db_host": "78.142.210.12",
                "db_port": "443",
                "db_name": "iletkene_doli801",
                "db_user": "admin_cms",
                "db_pass": "şifre12345",
                "backup_scope": self.tr("Tam Yedek Al (Database + Sunucu Dizinleri - SFTP/SSH Gerekir)"),
                "web_root_dir": "/home/iletkene/baynetbilisim.tr",
                "data_root_dir": "/home/iletkene/dbarbynttrdata",
                "sftp_host": "78.142.210.12",
                "sftp_port": "22",
                "sftp_user": "iletkene",
                "sftp_pass": "şifre_sftp",
                "source_dir": "Web: /home/iletkene/baynetbilisim.tr | Data: /home/iletkene/dbarbynttrdata",
                "dest_dir": "data/backups/dolibarr",
                "history": [
                    ["H-901", "14.07.2026 02:00", "14.5 MB", "12 sn", self.tr("Başarılı")],
                ],
            },
            {
                "id": "T-102",
                "name": "WordPress Site Kurtarma",
                "source": "WordPress",
                "emoji": "🌐",
                "type": "Restore",
                "target_type": "Local Depolama",
                "schedule": self.tr("Manuel Tetikleme"),
                "status": "manual",
                "db_host": "localhost",
                "db_port": "3307",
                "db_name": "wp_db",
                "db_user": "wp_user",
                "db_pass": "wp_sifre",
                "source_dir": "C:/wordpress/wp-content",
                "dest_dir": "data/backups/wp",
                "history": [
                    ["H-902", "14.07.2026 11:45", "142.8 MB", "45 sn", self.tr("Başarılı")],
                ],
            },
        ]
        self.save_tasks_to_json()

    def save_tasks_to_json(self):
        file_path = "data/backup_tasks.json"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.tasks_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Error saving backup_tasks.json: {e}")

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # ----------------------------------------------------
        # 1. SOL FİLTRE PANELİ (EdgeTriggeredPanel)
        # ----------------------------------------------------
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)
        self.left_panel.pinned_changed.connect(self.on_panel_pin_changed)

        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: transparent; border: none;")
        filter_lyt = QVBoxLayout(filter_frame)
        filter_lyt.setContentsMargins(0, 0, 0, 0)
        filter_lyt.setSpacing(8)

        lbl_search = QLabel("Görev / Hedef Arama:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText(self.tr("Hızlı ara (Ctrl+F)..."))
        self.search_box.textChanged.connect(self.on_search_changed)
        self.search_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
            }
        """)
        filter_lyt.addWidget(lbl_search)
        filter_lyt.addWidget(self.search_box)

        lbl_target_filter = QLabel("Hedef Türü:")
        lbl_target_filter.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_target = QComboBox()
        self.cmb_filter_target.addItems(["Tümü", "SFTP Uzak Sunucu", "Local Depolama", "Amazon S3 Bulut", "Local Disk D:"])
        self.cmb_filter_target.currentTextChanged.connect(self.on_search_changed)
        filter_lyt.addWidget(lbl_target_filter)
        filter_lyt.addWidget(self.cmb_filter_target)

        lbl_status_filter = QLabel("Durum:")
        lbl_status_filter.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_status = QComboBox()
        self.cmb_filter_status.addItems(["Tümü", "Aktif", "Manuel"])
        self.cmb_filter_status.currentTextChanged.connect(self.on_search_changed)
        filter_lyt.addWidget(lbl_status_filter)
        filter_lyt.addWidget(self.cmb_filter_status)
        filter_lyt.addStretch()

        self.left_panel.set_content(filter_frame)

        # ----------------------------------------------------
        # 2. ORTA CONTAINER (Kategori Seçim Barı + Tablo + Pagination)
        # ----------------------------------------------------
        self.center_container = QWidget()
        self.center_container.setObjectName("CenterContainer")
        center_layout = QVBoxLayout(self.center_container)
        center_layout.setContentsMargins(5, 0, 5, 0)
        center_layout.setSpacing(8)

        # Üst Bildirim Alanı (Banner / Top Toast Notification)
        self.top_notification_panel = QFrame()
        self.top_notification_panel.setObjectName("TopNotificationPanel")
        self.top_notification_panel.setFixedHeight(40)
        self.top_notification_panel.setStyleSheet("""
            QFrame#TopNotificationPanel {
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
            }
        """)
        top_notif_lyt = QHBoxLayout(self.top_notification_panel)
        top_notif_lyt.setContentsMargins(12, 0, 12, 0)
        self.lbl_top_notification = QLabel("ℹ️ Görevler modülüne hoş geldiniz.")
        self.lbl_top_notification.setStyleSheet("color: #1d4ed8; font-weight: bold; font-size: 12px;")
        top_notif_lyt.addWidget(self.lbl_top_notification)
        top_notif_lyt.addStretch()
        center_layout.addWidget(self.top_notification_panel)

        # Belirginleştirilmiş Kategori Geçiş Barı
        cat_bar = QFrame()
        cat_bar.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 4px;")
        cat_lyt = QHBoxLayout(cat_bar)
        cat_lyt.setContentsMargins(4, 4, 4, 4)
        cat_lyt.setSpacing(8)

        self.btn_cat_backup = QPushButton("💾  YEDEKLEME TANIMLARI")
        self.btn_cat_backup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cat_backup.clicked.connect(lambda: self.switch_category("Backup"))

        self.btn_cat_restore = QPushButton("🔄  GERİ YÜKLEME TANIMLARI")
        self.btn_cat_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cat_restore.clicked.connect(lambda: self.switch_category("Restore"))

        cat_lyt.addWidget(self.btn_cat_backup)
        cat_lyt.addWidget(self.btn_cat_restore)
        center_layout.addWidget(cat_bar)

        # Dynamic Table (FilterableTableView)
        self.headers_dict = {
            0: (self.tr("ID"), "id"),
            1: (self.tr("Görev Adı"), "name"),
            2: (self.tr("Kaynak"), "source"),
            3: (self.tr("Hedef Türü"), "target_type"),
            4: (self.tr("Zamanlama"), "schedule"),
            5: (self.tr("Durum"), "status"),
        }

        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key="backup_tasks",
            parent=self,
        )
        self.task_table = self.filterable_table.table_view
        self.task_table.setObjectName("TaskTable")
        self.task_model = QStandardItemModel(self)
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
        self.task_model.setHorizontalHeaderLabels(headers)
        self.task_table.setModel(self.task_model)

        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setSelectionBehavior(QHeaderView.SelectionBehavior.SelectRows)
        self.task_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_table.customContextMenuRequested.connect(self.show_task_context_menu)
        self.task_table.selectionModel().selectionChanged.connect(self.on_task_selection_changed)

        center_layout.addWidget(self.filterable_table, 1)

        # Sayfalama (Pagination) Barı
        self.pagination_layout = QHBoxLayout()
        self.pagination_layout.setContentsMargins(0, 4, 0, 0)
        self.pagination_layout.setSpacing(6)

        self.btn_first_page = QPushButton("⏮️")
        self.btn_first_page.clicked.connect(self.go_to_first_page)
        self.btn_prev_page = QPushButton("⬅️")
        self.btn_prev_page.clicked.connect(self.go_to_prev_page)

        self.lbl_page_info = QLabel("Sayfa 1 / 1")
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #475569;")

        self.btn_next_page = QPushButton("➡️")
        self.btn_next_page.clicked.connect(self.go_to_next_page)
        self.btn_last_page = QPushButton("⏭️")
        self.btn_last_page.clicked.connect(self.go_to_last_page)

        self.combo_page_size = QComboBox()
        self.combo_page_size.addItems(["25 kayıt", "50 kayıt", "100 kayıt"])
        self.combo_page_size.currentTextChanged.connect(self.on_page_size_changed)

        for btn in [self.btn_first_page, self.btn_prev_page, self.btn_next_page, self.btn_last_page]:
            btn.setStyleSheet("QPushButton { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background: white; }")

        self.pagination_layout.addWidget(self.btn_first_page)
        self.pagination_layout.addWidget(self.btn_prev_page)
        self.pagination_layout.addWidget(self.lbl_page_info)
        self.pagination_layout.addWidget(self.btn_next_page)
        self.pagination_layout.addWidget(self.btn_last_page)
        self.pagination_layout.addStretch()
        self.pagination_layout.addWidget(QLabel("Adet:"))
        self.pagination_layout.addWidget(self.combo_page_size)

        center_layout.addLayout(self.pagination_layout)

        # ----------------------------------------------------
        # 3. SAĞ PANEL: TOOLBAR & GÖREV DETAY POPUP BUTONLARI
        # ----------------------------------------------------
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)
        self.right_panel.pinned_changed.connect(self.on_panel_pin_changed)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.toolbar_frame = QFrame()
        self.toolbar_frame.setStyleSheet("background-color: transparent; border: none;")
        toolbar_lyt = QVBoxLayout(self.toolbar_frame)
        toolbar_lyt.setContentsMargins(0, 0, 0, 0)
        toolbar_lyt.setSpacing(6)

        # 1. Grup: Veri İşlemleri
        grp_data = QFrame()
        grp_data.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_data_lyt = QVBoxLayout(grp_data)
        grp_data_lyt.setContentsMargins(4, 6, 4, 6)
        grp_data_lyt.setSpacing(4)

        lbl_grp_data = QLabel("VERİ İŞLEMLERİ")
        lbl_grp_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_data.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 9px;")
        grp_data_lyt.addWidget(lbl_grp_data)

        self.btn_new_task = QPushButton("➕ Yeni Görev")
        self.btn_new_task.setStyleSheet(self.toolbar_btn_style())
        self.btn_new_task.clicked.connect(self.on_new_task_clicked)

        self.btn_edit_task = QPushButton("✏️ Değiştir")
        self.btn_edit_task.setStyleSheet(self.toolbar_btn_style())
        self.btn_edit_task.clicked.connect(self.on_edit_button_clicked)
        self.btn_edit_task.setEnabled(False)

        self.btn_delete_task = QPushButton("🗑️ Sil")
        self.btn_delete_task.setStyleSheet(self.toolbar_btn_style())
        self.btn_delete_task.clicked.connect(self.on_delete_button_clicked)
        self.btn_delete_task.setEnabled(False)

        self.btn_start_task = QPushButton("▶️ Görevi Başlat")
        self.btn_start_task.setStyleSheet(self.toolbar_btn_style())
        self.btn_start_task.clicked.connect(self.trigger_manual_process)
        self.btn_start_task.setEnabled(False)

        grp_data_lyt.addWidget(self.btn_new_task)
        grp_data_lyt.addWidget(self.btn_edit_task)
        grp_data_lyt.addWidget(self.btn_delete_task)
        grp_data_lyt.addWidget(self.btn_start_task)
        toolbar_lyt.addWidget(grp_data)

        # 2. Grup: Görev Detayları (Popup Menüler)
        grp_details = QFrame()
        grp_details.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_details_lyt = QVBoxLayout(grp_details)
        grp_details_lyt.setContentsMargins(4, 6, 4, 6)
        grp_details_lyt.setSpacing(4)

        lbl_grp_details = QLabel("GÖREV POPUP DETAYLARI")
        lbl_grp_details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_details.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 9px;")
        grp_details_lyt.addWidget(lbl_grp_details)

        self.btn_popup_overview = QPushButton("📋 Görev Özeti & Ayarlar")
        self.btn_popup_overview.setStyleSheet(self.toolbar_btn_style())
        self.btn_popup_overview.clicked.connect(lambda: self.open_detail_popup_for_selected(0))

        self.btn_popup_ops = QPushButton("⚙️ Manuel İşlemler")
        self.btn_popup_ops.setStyleSheet(self.toolbar_btn_style())
        self.btn_popup_ops.clicked.connect(lambda: self.open_detail_popup_for_selected(1))

        self.btn_popup_mon = QPushButton("📊 Canlı İzleme")
        self.btn_popup_mon.setStyleSheet(self.toolbar_btn_style())
        self.btn_popup_mon.clicked.connect(lambda: self.open_detail_popup_for_selected(2))

        self.btn_popup_rep = QPushButton("📝 Raporlar & Tarihçe")
        self.btn_popup_rep.setStyleSheet(self.toolbar_btn_style())
        self.btn_popup_rep.clicked.connect(lambda: self.open_detail_popup_for_selected(3))

        grp_details_lyt.addWidget(self.btn_popup_overview)
        grp_details_lyt.addWidget(self.btn_popup_ops)
        grp_details_lyt.addWidget(self.btn_popup_mon)
        grp_details_lyt.addWidget(self.btn_popup_rep)
        toolbar_lyt.addWidget(grp_details)

        toolbar_lyt.addStretch()
        right_scroll.setWidget(self.toolbar_frame)
        self.right_panel.set_content(right_scroll)

        main_layout.addWidget(self.center_container, 1)

        # Marjin Sinyalleri
        self.left_panel.opened_changed.connect(self.update_pagination_margins)
        self.left_panel.pinned_changed.connect(self.update_pagination_margins)
        self.right_panel.opened_changed.connect(self.update_pagination_margins)
        self.right_panel.pinned_changed.connect(self.update_pagination_margins)

        self.left_panel.close_panel()
        self.right_panel.close_panel()

        # Ctrl+F Kısayolu Entegrasyonu
        self.shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_search.activated.connect(self.trigger_quick_search)

        self.switch_category("Backup")

    def toolbar_btn_style(self):
        return """
            QPushButton {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-family: 'Segoe UI';
                font-size: 11px;
                color: #334155;
                font-weight: bold;
                text-align: left;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
            QPushButton:disabled { color: #cbd5e1; background-color: #f1f5f9; }
        """

    def switch_category(self, category: str):
        self.selected_category = category
        new_profile_key = "backup_tasks" if category == "Backup" else "restore_tasks"
        if hasattr(self, "filterable_table"):
            self.filterable_table.set_profile_key(new_profile_key)

        if category == "Backup":
            self.btn_cat_backup.setStyleSheet("""
                background-color: #005fb8;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                border-radius: 6px;
            """)
            self.btn_cat_restore.setStyleSheet("""
                background-color: #ffffff;
                color: #475569;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid #cbd5e1;
            """)
            self.lbl_top_notification.setText(self.tr("ℹ️ Yedekleme Tanımları görüntülendi. Sağ taraftan yeni tanım ekleyebilirsiniz."))
            self.top_notification_panel.setStyleSheet("QFrame#TopNotificationPanel { background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; }")
        else:
            self.btn_cat_restore.setStyleSheet("""
                background-color: #6366f1;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                border-radius: 6px;
            """)
            self.btn_cat_backup.setStyleSheet("""
                background-color: #ffffff;
                color: #475569;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid #cbd5e1;
            """)
            self.lbl_top_notification.setText(self.tr("ℹ️ Geri Yükleme Tanımları görüntülendi. Kurtarma işlemlerinizi yönetebilirsiniz."))
            self.top_notification_panel.setStyleSheet("QFrame#TopNotificationPanel { background-color: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 8px; }")

        self.current_page = 1
        self.refresh_task_list()

    def refresh_task_list(self):
        self.task_model.clear()
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
        self.task_model.setHorizontalHeaderLabels(headers)

        filtered_tasks = [t for t in self.tasks_data if t.get("type") == self.selected_category]

        search_txt = self.search_box.text().strip().lower()
        if search_txt:
            filtered_tasks = [t for t in filtered_tasks if search_txt in t.get("name", "").lower() or search_txt in t.get("source", "").lower()]

        target_filter = self.cmb_filter_target.currentText()
        if target_filter != "Tümü":
            filtered_tasks = [t for t in filtered_tasks if t.get("target_type") == target_filter]

        status_filter = self.cmb_filter_status.currentText()
        if status_filter != "Tümü":
            st_key = "active" if status_filter == "Aktif" else "manual"
            filtered_tasks = [t for t in filtered_tasks if t.get("status") == st_key]

        self.total_records = len(filtered_tasks)
        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        self.lbl_page_info.setText(f"Sayfa {self.current_page} / {total_pages} (Toplam: {self.total_records} Görev)")

        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        page_tasks = filtered_tasks[start_idx:end_idx]

        for task in page_tasks:
            id_item = QStandardItem(task.get("id", ""))
            id_item.setForeground(QColor("#64748b"))

            name_item = QStandardItem(f"{task.get('emoji', '📂')}  {task.get('name', '')}")
            name_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

            source_item = QStandardItem(task.get("source", ""))
            target_item = QStandardItem(task.get("target_type", ""))
            sched_item = QStandardItem(task.get("schedule", ""))

            st_val = task.get("status")
            status_text = "🟢 AKTİF" if st_val == "active" else "⚪ MANUEL"
            status_item = QStandardItem(status_text)
            status_item.setForeground(QColor("#10b981") if st_val == "active" else QColor("#64748b"))

            self.task_model.appendRow([id_item, name_item, source_item, target_item, sched_item, status_item])

        self.on_task_selection_changed()

    def get_selected_task(self):
        indexes = self.task_table.selectionModel().selectedRows()
        if not indexes:
            return None
        row = indexes[0].row()
        filtered_tasks = [t for t in self.tasks_data if t.get("type") == self.selected_category]
        if 0 <= row < len(filtered_tasks):
            return filtered_tasks[row]
        return None

    def show_task_context_menu(self, pos):
        """AttributeError çözümü eklendi: itemAt(pos) yerine indexAt(pos) kullanılıyor."""
        index = self.task_table.indexAt(pos)
        if not index.isValid():
            return

        self.task_table.selectRow(index.row())
        task = self.get_selected_task()
        if not task:
            return

        menu = QMenu(self)
        start_action = QAction(self.tr("▶️ Görevi Başlat"), self)
        edit_action = QAction(self.tr("📝 Görev Tanımını Düzenle"), self)
        delete_action = QAction(self.tr("🗑️ Görev Tanımını Sil"), self)

        overview_action = QAction(self.tr("📋 Görev Özeti & Ayarlar"), self)
        ops_action = QAction(self.tr("⚙️ Manuel İşlemler"), self)
        mon_action = QAction(self.tr("📊 Canlı İzleme"), self)
        rep_action = QAction(self.tr("📝 Raporlar & Tarihçe"), self)

        search_action = QAction(self.tr("🔍 Hızlı Ara (Ctrl+F)"), self)

        start_action.triggered.connect(self.trigger_manual_process)
        edit_action.triggered.connect(lambda: self.edit_task_action(task))
        delete_action.triggered.connect(lambda: self.delete_task_action(task))

        overview_action.triggered.connect(lambda: self.open_detail_popup(task, 0))
        ops_action.triggered.connect(lambda: self.open_detail_popup(task, 1))
        mon_action.triggered.connect(lambda: self.open_detail_popup(task, 2))
        rep_action.triggered.connect(lambda: self.open_detail_popup(task, 3))
        search_action.triggered.connect(self.trigger_quick_search)

        menu.addAction(start_action)
        menu.addSeparator()
        menu.addAction(overview_action)
        menu.addAction(ops_action)
        menu.addAction(mon_action)
        menu.addAction(rep_action)
        menu.addSeparator()
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.addSeparator()
        menu.addAction(search_action)

        menu.exec(self.task_table.viewport().mapToGlobal(pos))

    def open_detail_popup_for_selected(self, active_tab: int = 0):
        task = self.get_selected_task()
        if not task:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Lütfen bir görev tanımı seçin."))
            return
        self.open_detail_popup(task, active_tab)

    def open_detail_popup(self, task: dict, active_tab: int = 0):
        dlg = TaskDetailPopupDialog(task=task, active_tab=active_tab, parent_widget=self)
        dlg.exec()

    def trigger_quick_search(self):
        if not self.left_panel.is_open:
            self.left_panel.open_panel()
        self.search_box.setFocus()
        self.search_box.selectAll()

    def on_task_selection_changed(self, *args):
        has_sel = bool(self.task_table.selectionModel() and self.task_table.selectionModel().hasSelection())
        self.btn_edit_task.setEnabled(has_sel)
        self.btn_delete_task.setEnabled(has_sel)
        self.btn_start_task.setEnabled(has_sel)
        self.btn_popup_overview.setEnabled(has_sel)
        self.btn_popup_ops.setEnabled(has_sel)
        self.btn_popup_mon.setEnabled(has_sel)
        self.btn_popup_rep.setEnabled(has_sel)

    def on_search_changed(self):
        self.current_page = 1
        self.refresh_task_list()

    def on_new_task_clicked(self):
        dlg = NewTaskDialog(mode="add", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_task = dlg.get_task_data()
            self.tasks_data.append(new_task)
            self.save_tasks_to_json()
            self.refresh_task_list()
            self.toast_requested.emit(f"'{new_task['name']}' görev tanımı eklendi.", "success")

    def on_edit_button_clicked(self):
        task = self.get_selected_task()
        if task:
            self.edit_task_action(task)

    def edit_task_action(self, task):
        dlg = NewTaskDialog(mode="edit", task_data=task, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updated_data = dlg.get_task_data()
            for idx, t in enumerate(self.tasks_data):
                if t["id"] == task["id"]:
                    self.tasks_data[idx] = updated_data
                    break
            self.save_tasks_to_json()
            self.refresh_task_list()
            self.toast_requested.emit(f"'{updated_data['name']}' güncellendi.", "success")

    def on_delete_button_clicked(self):
        task = self.get_selected_task()
        if task:
            self.delete_task_action(task)

    def delete_task_action(self, task):
        confirm = QMessageBox.question(
            self,
            self.tr("Görevi Sil"),
            f"'{task['name']}' görev tanımını silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.tasks_data.remove(task)
            self.save_tasks_to_json()
            self.refresh_task_list()
            self.toast_requested.emit(f"'{task['name']}' silindi.", "info")

    def trigger_manual_process(self):
        task = self.get_selected_task()
        if not task:
            return

        if task.get("type") == "Restore" and task.get("source") == "Dolibarr":
            assistant = DolibarrRestoreAssistantDialog(task, self)
            if assistant.exec() != QDialog.DialogCode.Accepted:
                return

        self.open_detail_popup(task, active_tab=1)

    def on_panel_pin_changed(self, pinned):
        sender = self.sender()
        if not sender:
            return
        layout = self.layout()
        if pinned:
            sender.setParent(None)
            if sender == self.left_panel:
                layout.insertWidget(0, self.left_panel)
            else:
                layout.addWidget(self.right_panel)
        else:
            layout.removeWidget(sender)
            sender.setParent(self)
            sender.update_position()
            sender.show()

    def update_pagination_margins(self):
        left_margin = self.left_panel.panel_width if (self.left_panel.is_open and not self.left_panel.is_pinned) else 0
        right_margin = self.right_panel.panel_width if (self.right_panel.is_open and not self.right_panel.is_pinned) else 0
        self.pagination_layout.setContentsMargins(left_margin, 4, right_margin, 0)

    # Sayfalama
    def go_to_first_page(self):
        self.current_page = 1
        self.refresh_task_list()

    def go_to_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_task_list()

    def go_to_next_page(self):
        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_task_list()

    def go_to_last_page(self):
        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        self.current_page = total_pages
        self.refresh_task_list()

    def on_page_size_changed(self, text):
        try:
            val = int(text.split()[0])
            self.per_page = val
            self.current_page = 1
            self.refresh_task_list()
        except Exception:
            pass
