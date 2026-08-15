import hashlib
import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.models import Site, User
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.components.git_tracker_widget import GitTrackerWidget
from src.desktop.ui.components.layout_hint_helper import (
    is_layout_hints_enabled,
    register_layout_hint,
    set_layout_hints_enabled,
)
from src.desktop.ui.components.text_selection_helper import (
    is_global_text_selection_enabled,
    set_global_text_selection_enabled,
)
from src.desktop.ui.sites import SitesWidget

logger = logging.getLogger(__name__)


class SettingsWidget(QTabWidget):
    """Firma, kullanıcı ve görünüm ayarlarının sekmeli olarak yönetildiği genel ayarlar ekranı."""

    def __init__(self, db_session, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.init_ui()
        register_layout_hint(self, "Ayarlar", "Genel Ayarlar Sekmeli Panel")

    def init_ui(self):
        # 1. Firma Tanımları Sekmesi
        self.sites_tab = SitesWidget(self.db)
        self.addTab(self.sites_tab, "🏢 Firma Tanımları")
        register_layout_hint(self.sites_tab, "Ayarlar", "Firma Tanımları Sekmesi")

        # 2. Kullanıcı Tanımları Sekmesi
        self.users_tab = UserManagementWidget(self.db)
        self.addTab(self.users_tab, "👥 Kullanıcı Tanımları")
        register_layout_hint(self.users_tab, "Ayarlar", "Kullanıcı Tanımları Sekmesi")

        # Firma güncellendiğinde kullanıcı sekmesindeki firma yetkileri listesi tazelensin
        self.sites_tab.sites_updated.connect(self.users_tab.load_sites)

        # 3. Görünüm Profilleri Sekmesi
        self.view_settings_tab = ViewSettingsWidget()
        self.addTab(self.view_settings_tab, "🎨 Görünüm Profilleri")
        register_layout_hint(self.view_settings_tab, "Ayarlar", "Görünüm Profilleri Sekmesi")

        # 4. Git & Görev Takibi Sekmesi
        self.git_tracker_tab = GitTrackerWidget()
        self.addTab(self.git_tracker_tab, "📊 Sürüm & Git Takibi")
        register_layout_hint(self.git_tracker_tab, "Ayarlar", "Sürüm & Git Takibi Sekmesi")

        # Üst Sağ Köşe: Seçilebilir Metin & Modül İsim İpuçları Onay Kutuları
        corner_widget = QWidget()
        corner_lyt = QHBoxLayout(corner_widget)
        corner_lyt.setContentsMargins(0, 0, 10, 0)
        corner_lyt.setSpacing(12)

        self.chk_layout_hints = QCheckBox("🏷️ Modül / Bölüm İsim İpuçlarını (Layout Hints) Göster")
        self.chk_layout_hints.setStyleSheet("font-weight: bold; color: #15803d; font-size: 11px;")
        self.chk_layout_hints.setChecked(is_layout_hints_enabled())
        self.chk_layout_hints.toggled.connect(self.on_layout_hints_toggled)
        corner_lyt.addWidget(self.chk_layout_hints)

        self.chk_global_text_select = QCheckBox("🔍 Tüm Yazıları Seçilebilir/Kopyalanabilir Yap")
        self.chk_global_text_select.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px;")
        self.chk_global_text_select.setChecked(is_global_text_selection_enabled())
        self.chk_global_text_select.toggled.connect(self.on_text_selection_toggled)
        corner_lyt.addWidget(self.chk_global_text_select)

        self.setCornerWidget(corner_widget)

    def on_layout_hints_toggled(self, checked: bool):
        set_layout_hints_enabled(checked)

    def on_text_selection_toggled(self, checked: bool):
        set_global_text_selection_enabled(checked)


class UserDialog(QDialog):
    """DIA stiline uygun, 3 sekmeli ve gelişmiş şirket yetkilendirmeli Kullanıcı Ekleme / Düzenleme Ekranı."""

    def __init__(self, db_session, user_id=None, read_only=False, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.user_id = user_id
        self.read_only = read_only
        self.site_checkboxes = {}

        if self.user_id:
            self.setWindowTitle("Kullanıcı Detayı / Düzenle" if not read_only else "Kullanıcı Detayı İncele")
        else:
            self.setWindowTitle("Yeni Kullanıcı Tanımla")

        self.setMinimumWidth(880)
        self.setMinimumHeight(640)
        self.init_ui()

        if self.user_id:
            self.load_user_data()
        else:
            self.load_sites()

    def dia_btn_style(self, bg_color="#3b82f6", hover_color="#2563eb", text_color="#ffffff"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(10)

        # Sekme Yapısı
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::panel {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                color: #475569;
                padding: 8px 16px;
                border: 1px solid #cbd5e1;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: bold;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #1e3a8a;
                border-bottom: 2px solid white;
            }
        """)

        # Sekme 1: A. Kullanıcı Bilgileri
        tab_info = QWidget()
        tab_info_layout = QVBoxLayout(tab_info)
        tab_info_layout.setContentsMargins(12, 12, 12, 12)
        tab_info_layout.setSpacing(12)

        input_style = """
            QLineEdit, QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #f8fafc;
                color: #0f172a;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #3b82f6; background-color: white; }
        """

        # Üst Form Alanı (İki Kolonlu + Sağ Aksiyon Koyu)
        top_form_frame = QFrame()
        top_form_frame.setStyleSheet("background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;")
        top_form_lyt = QHBoxLayout(top_form_frame)
        top_form_lyt.setContentsMargins(12, 12, 12, 12)
        top_form_lyt.setSpacing(16)

        # Form Sol Kolon
        col_left = QVBoxLayout()
        col_left.setSpacing(8)

        # Kullanıcı Kodu / Adı
        lbl_uname = QLabel("Kullanıcı Kodu / Adı *:")
        lbl_uname.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("Örn: Baynet")
        self.txt_username.setStyleSheet(input_style)
        col_left.addWidget(lbl_uname)
        col_left.addWidget(self.txt_username)

        # Adı Soyadı
        lbl_fullname = QLabel("Adı Soyadı:")
        lbl_fullname.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.txt_fullname = QLineEdit()
        self.txt_fullname.setPlaceholderText("Örn: Baynet Bilişim")
        self.txt_fullname.setStyleSheet(input_style)
        col_left.addWidget(lbl_fullname)
        col_left.addWidget(self.txt_fullname)

        # Ünvanı
        lbl_title = QLabel("Ünvanı:")
        lbl_title.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Örn: Sistem Yöneticisi")
        self.txt_title.setStyleSheet(input_style)
        col_left.addWidget(lbl_title)
        col_left.addWidget(self.txt_title)

        top_form_lyt.addLayout(col_left, 1)

        # Form Sağ Kolon
        col_mid = QVBoxLayout()
        col_mid.setSpacing(8)

        # E-Posta Adresi
        lbl_email = QLabel("E-Posta Adresi:")
        lbl_email.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("info@example.com")
        self.txt_email.setStyleSheet(input_style)
        col_mid.addWidget(lbl_email)
        col_mid.addWidget(self.txt_email)

        # Şifre
        lbl_pwd = QLabel("Şifre:")
        lbl_pwd.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("Değiştirmek istemiyorsanız boş bırakın")
        self.txt_password.setStyleSheet(input_style)
        col_mid.addWidget(lbl_pwd)
        col_mid.addWidget(self.txt_password)

        # Rol & Durum
        role_status_lyt = QHBoxLayout()
        role_lyt = QVBoxLayout()
        lbl_role = QLabel("Rol:")
        lbl_role.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.cmb_role = QComboBox()
        self.cmb_role.addItem("Standart Kullanıcı", "user")
        self.cmb_role.addItem("Yönetici (Admin)", "admin")
        self.cmb_role.setStyleSheet(input_style)
        role_lyt.addWidget(lbl_role)
        role_lyt.addWidget(self.cmb_role)

        status_lyt = QVBoxLayout()
        lbl_status = QLabel("Durum:")
        lbl_status.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.cmb_status = QComboBox()
        self.cmb_status.addItem("Aktif", 1)
        self.cmb_status.addItem("Pasif", 0)
        self.cmb_status.setStyleSheet(input_style)
        status_lyt.addWidget(lbl_status)
        status_lyt.addWidget(self.cmb_status)

        role_status_lyt.addLayout(role_lyt, 1)
        role_status_lyt.addLayout(status_lyt, 1)
        col_mid.addLayout(role_status_lyt)

        top_form_lyt.addLayout(col_mid, 1)

        # Sağ Aksiyon Koyu (Şifre Değiştir, Güvenlik vb.)
        action_box = QFrame()
        action_box.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        action_box_lyt = QVBoxLayout(action_box)
        action_box_lyt.setContentsMargins(8, 8, 8, 8)
        action_box_lyt.setSpacing(6)

        btn_pwd_change = QPushButton("⚡ Şifre Değiştir")
        btn_pwd_change.setStyleSheet(self.dia_btn_style("#2563eb", "#1d4ed8"))
        btn_limits = QPushButton("🔒 Sınırlandırma")
        btn_limits.setStyleSheet(self.dia_btn_style("#475569", "#334155"))
        btn_2fa = QPushButton("🛡️ 2 Adımlı Güvenlik")
        btn_2fa.setStyleSheet(self.dia_btn_style("#0d9488", "#0f766e"))

        action_box_lyt.addWidget(btn_pwd_change)
        action_box_lyt.addWidget(btn_limits)
        action_box_lyt.addWidget(btn_2fa)
        action_box_lyt.addStretch()

        top_form_lyt.addWidget(action_box)
        tab_info_layout.addWidget(top_form_frame)

        # Alt Bölüm: Yetki ve Gruplar
        perm_frame = QFrame()
        perm_frame.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        perm_lyt = QVBoxLayout(perm_frame)
        perm_lyt.setContentsMargins(12, 10, 12, 10)
        perm_lyt.setSpacing(8)

        lbl_perm_title = QLabel("Yetki ve Gruplar")
        lbl_perm_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_perm_title.setStyleSheet("color: #1e3a8a;")
        perm_lyt.addWidget(lbl_perm_title)

        # Yetki Ara ve Firma Kopyala Çubuğu
        copy_bar_lyt = QHBoxLayout()
        copy_bar_lyt.addWidget(QLabel("Firma:"))
        self.cmb_sites_filter = QComboBox()
        self.cmb_sites_filter.setStyleSheet(input_style)
        copy_bar_lyt.addWidget(self.cmb_sites_filter, 1)

        btn_copy_perms = QPushButton("+ Yetkileri Kopyala >>")
        btn_copy_perms.setStyleSheet(self.dia_btn_style("#3b82f6", "#2563eb"))
        copy_bar_lyt.addWidget(btn_copy_perms)

        btn_apply_perms = QPushButton("≡ Uygula")
        btn_apply_perms.setStyleSheet(self.dia_btn_style("#059669", "#047857"))
        copy_bar_lyt.addWidget(btn_apply_perms)

        perm_lyt.addLayout(copy_bar_lyt)

        # Alt Bölüm 2 Kolonlu: Sol (Yetkili Şirketler Liste/Tree), Sağ (Üye Olduğu Gruplar)
        sites_groups_lyt = QHBoxLayout()

        # Sol: Erişebileceği Şirketler Scroll Kutu
        sites_box = QGroupBox("Erişebileceği Şirketler / Firmalar")
        sites_box.setStyleSheet("QGroupBox { font-weight: bold; color: #475569; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 6px; padding-top: 10px; }")
        sites_box_lyt = QVBoxLayout(sites_box)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(6, 6, 6, 6)
        self.scroll_layout.setSpacing(6)
        self.scroll_area.setWidget(self.scroll_content)
        sites_box_lyt.addWidget(self.scroll_area)

        sites_groups_lyt.addWidget(sites_box, 2)

        # Sağ: Üye Olduğu Gruplar
        groups_box = QGroupBox("Üye Olduğu Gruplar")
        groups_box.setStyleSheet("QGroupBox { font-weight: bold; color: #475569; border: 1px solid #cbd5e1; border-radius: 6px; margin-top: 6px; padding-top: 10px; }")
        groups_box_lyt = QVBoxLayout(groups_box)

        self.groups_list = QListWidget()
        self.groups_list.setStyleSheet("""
            QListWidget { border: 1px solid #cbd5e1; border-radius: 4px; background-color: white; color: #334155; }
            QListWidget::item { padding: 4px 8px; border-bottom: 1px solid #f1f5f9; }
            QListWidget::item:selected { background-color: #fef08a; color: #854d0e; font-weight: bold; }
        """)
        for grp in ["admin (Tam Yetkili)", "Gerekli Şirketler Yetkisi", "Görme ve Raporlama Yetkisi"]:
            item = QListWidgetItem(grp)
            item.setCheckState(Qt.CheckState.Checked if "admin" in grp else Qt.CheckState.Unchecked)
            self.groups_list.addItem(item)

        groups_box_lyt.addWidget(self.groups_list)
        sites_groups_lyt.addWidget(groups_box, 1)

        perm_lyt.addLayout(sites_groups_lyt)
        tab_info_layout.addWidget(perm_frame, 1)

        self.tab_widget.addTab(tab_info, "A. Kullanıcı Bilgileri")

        # Sekme 2: B. Diğer Bilgiler
        tab_other = QWidget()
        tab_other_lyt = QVBoxLayout(tab_other)
        tab_other_lyt.setContentsMargins(16, 16, 16, 16)
        lbl_other_info = QLabel("Ek kullanıcı sistem yetkileri ve kısıtlamaları bu alandan yapılandırılır.")
        lbl_other_info.setStyleSheet("color: #64748b; font-size: 12px;")
        tab_other_lyt.addWidget(lbl_other_info)
        tab_other_lyt.addStretch()
        self.tab_widget.addTab(tab_other, "B. Diğer Bilgiler")

        # Sekme 3: C. Ön Tanımlı Parametreler
        tab_params = QWidget()
        tab_params_lyt = QVBoxLayout(tab_params)
        tab_params_lyt.setContentsMargins(16, 16, 16, 16)
        lbl_params_info = QLabel("Kullanıcının varsayılan olarak açılmasını istediği firma ve mecra parametreleri.")
        lbl_params_info.setStyleSheet("color: #64748b; font-size: 12px;")
        tab_params_lyt.addWidget(lbl_params_info)
        tab_params_lyt.addStretch()
        self.tab_widget.addTab(tab_params, "C. Ön Tanımlı Parametreler")

        main_layout.addWidget(self.tab_widget, 1)

        # Alt Butonlar
        btn_box = QHBoxLayout()
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setStyleSheet(self.dia_btn_style("#3b82f6", "#2563eb"))
        self.btn_save.clicked.connect(self.save_user)

        self.btn_cancel = QPushButton("❌ Vazgeç")
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; border-radius: 4px; padding: 6px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        if self.read_only:
            self.txt_username.setReadOnly(True)
            self.txt_fullname.setReadOnly(True)
            self.txt_title.setReadOnly(True)
            self.txt_email.setReadOnly(True)
            self.txt_password.setReadOnly(True)
            self.cmb_role.setEnabled(False)
            self.cmb_status.setEnabled(False)
            self.btn_save.hide()

        btn_box.addStretch()
        btn_box.addWidget(self.btn_save)
        btn_box.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_box)

    def load_sites(self):
        for cb in self.site_checkboxes.values():
            self.scroll_layout.removeWidget(cb)
            cb.deleteLater()
        self.site_checkboxes.clear()
        self.cmb_sites_filter.clear()
        self.cmb_sites_filter.addItem("[Tüm Firmalar]", 0)

        try:
            sites = self.db.query(Site).filter(Site.is_active == True, Site.is_deleted == False).all()
            for site in sites:
                cb = QCheckBox(f"🏢 {site.name} ({site.cms_type.upper()})")
                cb.setStyleSheet("color: #334155; font-size: 12px; font-weight: 600;")
                self.scroll_layout.addWidget(cb)
                self.site_checkboxes[site.id] = cb
                self.cmb_sites_filter.addItem(site.name, site.id)
            self.scroll_layout.addStretch()
        except Exception as e:
            logger.error(f"Firma listesi yüklenemedi: {e}")

    def load_user_data(self):
        self.load_sites()
        try:
            user = self.db.query(User).filter(User.id == self.user_id).first()
            if user:
                self.txt_username.setText(user.username)
                self.txt_fullname.setText(user.username)
                idx = self.cmb_role.findData(user.role)
                if idx != -1:
                    self.cmb_role.setCurrentIndex(idx)
                status_idx = self.cmb_status.findData(1 if user.is_active else 0)
                if status_idx != -1:
                    self.cmb_status.setCurrentIndex(status_idx)

                allowed_ids = {s.id for s in user.allowed_sites}
                for site_id, cb in self.site_checkboxes.items():
                    cb.setChecked(site_id in allowed_ids)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kullanıcı detayları yüklenemedi: {e}")

    def save_user(self):
        username = self.txt_username.text().strip()
        password = self.txt_password.text()
        role = self.cmb_role.currentData()
        is_active = bool(self.cmb_status.currentData())

        if not username:
            QMessageBox.warning(self, "Uyarı", "Kullanıcı Kodu / Adı boş bırakılamaz.")
            return

        salt = "multi_cms_salt_key"
        try:
            if self.user_id:
                user = self.db.query(User).filter(User.id == self.user_id).first()
                if user:
                    user.username = username
                    if password:
                        user.password_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
                    user.role = role
                    user.is_active = is_active
            else:
                if not password:
                    QMessageBox.warning(self, "Uyarı", "Yeni kullanıcı için şifre girmelisiniz.")
                    return
                exists = self.db.query(User).filter(User.username == username).first()
                if exists:
                    QMessageBox.warning(self, "Uyarı", "Bu kullanıcı adı zaten mevcut.")
                    return

                pwd_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
                user = User(username=username, password_hash=pwd_hash, role=role, is_active=is_active)
                self.db.add(user)

            user.allowed_sites.clear()
            for site_id, cb in self.site_checkboxes.items():
                if cb.isChecked():
                    site = self.db.query(Site).filter(Site.id == site_id).first()
                    if site:
                        user.allowed_sites.append(site)

            self.db.commit()
            QMessageBox.information(self, "Başarılı", "Kullanıcı bilgileri kaydedildi.")
            self.accept()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {e}")


class UserManagementWidget(QWidget):
    """DIA stiline ve 3-Panelli Düzen mimarisine sahip Kullanıcı Tanımları Paneli."""

    def __init__(self, db_session, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.profile_key = "users"

        self.headers_dict = {
            0: ("ID", "id"),
            1: ("Kullanıcı Adı", "username"),
            2: ("Rol", "role"),
            3: ("Durum", "is_active"),
            4: ("Yetkili Firma Sayısı", "allowed_sites_count"),
        }

        self.init_ui()
        self.load_users()

    def toolbar_btn_style(self, bg_color="#ffffff", text_color="#1e293b"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{ background-color: #f1f5f9; }}
        """

    def dia_btn_style(self, bg_color="#3b82f6", hover_color="#2563eb", text_color="#ffffff"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # SOL PANEL (EdgeTriggeredPanel)
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)

        filter_content = QWidget()
        filter_lyt = QVBoxLayout(filter_content)
        filter_lyt.setContentsMargins(4, 4, 4, 4)
        filter_lyt.setSpacing(10)

        lbl_filter_title = QLabel("🔍 Filtre & Arama")
        lbl_filter_title.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 12px;")
        filter_lyt.addWidget(lbl_filter_title)

        lbl_search = QLabel("Kullanıcı Adı / İsim:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Arama yap...")
        self.txt_search.setStyleSheet("QLineEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background-color: white; font-size: 12px; }")
        self.txt_search.textChanged.connect(self.load_users)
        filter_lyt.addWidget(lbl_search)
        filter_lyt.addWidget(self.txt_search)

        combo_style = """
            QComboBox { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background-color: white; font-size: 12px; color: #0f172a; }
            QComboBox QAbstractItemView { border: 1px solid #94a3b8; background-color: #ffffff; color: #0f172a; outline: none; padding: 2px 0px; }
            QComboBox QAbstractItemView::item { min-height: 26px; padding: 4px 10px; background-color: #ffffff; color: #0f172a; border-radius: 0px; }
            QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected { background-color: #2563eb; color: #ffffff; }
        """

        lbl_role = QLabel("Rol Filtresi:")
        lbl_role.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_role = QComboBox()
        self.cmb_filter_role.addItems(["Tümü", "admin", "user"])
        self.cmb_filter_role.setStyleSheet(combo_style)
        self.cmb_filter_role.currentTextChanged.connect(self.load_users)
        filter_lyt.addWidget(lbl_role)
        filter_lyt.addWidget(self.cmb_filter_role)

        lbl_status = QLabel("Durum Filtresi:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_status = QComboBox()
        self.cmb_filter_status.addItem("Tümü", -1)
        self.cmb_filter_status.addItem("Aktif", 1)
        self.cmb_filter_status.addItem("Pasif", 0)
        self.cmb_filter_status.setStyleSheet(combo_style)
        self.cmb_filter_status.currentIndexChanged.connect(self.load_users)
        filter_lyt.addWidget(lbl_status)
        filter_lyt.addWidget(self.cmb_filter_status)
        filter_lyt.addStretch()

        self.left_panel.set_content(filter_content)
        main_layout.addWidget(self.left_panel)

        # ORTA PANEL (DBGrid & DIA Alt Buton Çubuğu)
        self.center_container = QWidget()
        center_lyt = QVBoxLayout(self.center_container)
        center_lyt.setContentsMargins(4, 0, 4, 0)
        center_lyt.setSpacing(8)

        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key="users",
            enable_profile_bar=False,
            parent=self,
        )
        self.table = self.filterable_table.table_view

        self.table_model = QStandardItemModel(self)
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
        self.table_model.setHorizontalHeaderLabels(headers)
        self.table.setModel(self.table_model)

        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setDefaultSectionSize(140)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.table.doubleClicked.connect(self.open_edit_user_dialog)

        self.table.setStyleSheet("""
            QTableView {
                border: 1px solid #cbd5e1;
                background-color: white;
                gridline-color: #f1f5f9;
                border-radius: 6px;
                font-size: 12px;
                color: #334155;
            }
            QTableView::item { padding: 6px; }
            QTableView::item:selected { background-color: #eff6ff; color: #1d4ed8; font-weight: 600; }
            QHeaderView::section { background-color: #f8fafc; color: #475569; padding: 8px; border: none; border-right: 1px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; font-weight: bold; }
        """)
        center_lyt.addWidget(self.filterable_table, 1)

        # DIA Alt Buton Çubuğu
        self.action_bar = QFrame()
        self.action_bar.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        action_bar_lyt = QHBoxLayout(self.action_bar)
        action_bar_lyt.setContentsMargins(8, 6, 8, 6)
        action_bar_lyt.setSpacing(8)

        self.btn_add = QPushButton("➕ Ekle")
        self.btn_add.setStyleSheet(self.dia_btn_style("#3b82f6", "#2563eb"))
        self.btn_add.clicked.connect(self.open_add_user_dialog)

        self.btn_edit = QPushButton("✏️ Değiştir")
        self.btn_edit.setStyleSheet(self.dia_btn_style("#2563eb", "#1d4ed8"))
        self.btn_edit.clicked.connect(self.open_edit_user_dialog)

        self.btn_inspect = QPushButton("🔍 İncele")
        self.btn_inspect.setStyleSheet(self.dia_btn_style("#475569", "#334155"))
        self.btn_inspect.clicked.connect(self.inspect_user_dialog)

        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setStyleSheet(self.dia_btn_style("#ef4444", "#dc2626"))
        self.btn_delete.clicked.connect(self.delete_user)

        self.btn_other = QPushButton("≡ Diğer")
        self.btn_other.setStyleSheet(self.dia_btn_style("#64748b", "#475569"))
        other_menu = QMenu(self)
        other_menu.addAction("🔄 Kullanıcı Listesini Yenile", self.load_users)
        self.btn_other.setMenu(other_menu)

        action_bar_lyt.addWidget(self.btn_add)
        action_bar_lyt.addWidget(self.btn_edit)
        action_bar_lyt.addWidget(self.btn_inspect)
        action_bar_lyt.addWidget(self.btn_delete)
        action_bar_lyt.addWidget(self.btn_other)
        action_bar_lyt.addStretch()

        self.lbl_record_count = QLabel("Toplam Kayıt: 0")
        self.lbl_record_count.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        action_bar_lyt.addWidget(self.lbl_record_count)

        center_lyt.addWidget(self.action_bar)
        main_layout.addWidget(self.center_container, 1)

        # SAĞ PANEL (EdgeTriggeredPanel)
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_content = QWidget()
        right_lyt = QVBoxLayout(right_content)
        right_lyt.setContentsMargins(4, 4, 4, 4)
        right_lyt.setSpacing(8)

        grp_user = QFrame()
        grp_user.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_user_lyt = QVBoxLayout(grp_user)
        grp_user_lyt.setContentsMargins(6, 8, 6, 8)
        grp_user_lyt.setSpacing(6)

        lbl_grp_user = QLabel("KULLANICI İŞLEMLERİ")
        lbl_grp_user.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_user.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_user_lyt.addWidget(lbl_grp_user)

        btn_r_add = QPushButton("➕ Yeni Kullanıcı Ekle")
        btn_r_add.setStyleSheet(self.toolbar_btn_style("#10b981", "#ffffff"))
        btn_r_add.clicked.connect(self.open_add_user_dialog)

        btn_r_edit = QPushButton("✏️ Değiştir")
        btn_r_edit.setStyleSheet(self.toolbar_btn_style())
        btn_r_edit.clicked.connect(self.open_edit_user_dialog)

        btn_r_inspect = QPushButton("🔍 İncele")
        btn_r_inspect.setStyleSheet(self.toolbar_btn_style())
        btn_r_inspect.clicked.connect(self.inspect_user_dialog)

        btn_r_delete = QPushButton("🗑️ Sil")
        btn_r_delete.setStyleSheet(self.toolbar_btn_style("#ef4444", "#ffffff"))
        btn_r_delete.clicked.connect(self.delete_user)

        grp_user_lyt.addWidget(btn_r_add)
        grp_user_lyt.addWidget(btn_r_edit)
        grp_user_lyt.addWidget(btn_r_inspect)
        grp_user_lyt.addWidget(btn_r_delete)
        right_lyt.addWidget(grp_user)

        grp_view = QFrame()
        grp_view.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_view_lyt = QVBoxLayout(grp_view)
        grp_view_lyt.setContentsMargins(6, 8, 6, 8)
        grp_view_lyt.setSpacing(6)

        lbl_grp_view = QLabel("GÖRÜNÜM")
        lbl_grp_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_view.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_view_lyt.addWidget(lbl_grp_view)

        btn_r_cols = QPushButton("⚙️ Kolonları Yapılandır")
        btn_r_cols.setStyleSheet(self.toolbar_btn_style())
        btn_r_cols.clicked.connect(self.filterable_table.open_column_manager_dialog)

        grp_view_lyt.addWidget(btn_r_cols)
        right_lyt.addWidget(grp_view)
        right_lyt.addStretch()

        right_scroll.setWidget(right_content)
        self.right_panel.set_content(right_scroll)
        main_layout.addWidget(self.right_panel)

    def load_users(self):
        self.table_model.removeRows(0, self.table_model.rowCount())
        try:
            query = self.db.query(User).filter(User.is_deleted == False)

            search = self.txt_search.text().strip().lower()
            if search:
                query = query.filter(User.username.ilike(f"%{search}%"))

            role_filter = self.cmb_filter_role.currentText()
            if role_filter != "Tümü":
                query = query.filter(User.role == role_filter)

            status_val = self.cmb_filter_status.currentData()
            if status_val != -1:
                query = query.filter(User.is_active == bool(status_val))

            users = query.all()
            for user in users:
                role_txt = "Yönetici (Admin)" if user.role == "admin" else "Standart Kullanıcı"
                status_txt = "Aktif" if user.is_active else "Pasif"
                row_items = [
                    QStandardItem(str(user.id)),
                    QStandardItem(user.username),
                    QStandardItem(role_txt),
                    QStandardItem(status_txt),
                    QStandardItem(f"{len(user.allowed_sites)} Şirket"),
                ]
                row_items[0].setData(user.id, Qt.ItemDataRole.UserRole)
                self.table_model.appendRow(row_items)

            self.lbl_record_count.setText(f"Toplam Kayıt: {len(users)}")
        except Exception as e:
            logger.error(f"Kullanıcılar yüklenemedi: {e}")

    def load_sites(self):
        self.load_users()

    def get_selected_user_id(self) -> int | None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            return None
        row = indexes[0].row()
        item = self.table_model.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def open_add_user_dialog(self):
        dlg = UserDialog(self.db, user_id=None, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_users()

    def open_edit_user_dialog(self):
        user_id = self.get_selected_user_id()
        if not user_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz kullanıcıyı seçin.")
            return
        dlg = UserDialog(self.db, user_id=user_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_users()

    def inspect_user_dialog(self):
        user_id = self.get_selected_user_id()
        if not user_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen incelemek istediğiniz kullanıcıyı seçin.")
            return
        dlg = UserDialog(self.db, user_id=user_id, read_only=True, parent=self)
        dlg.exec()

    def delete_user(self):
        user_id = self.get_selected_user_id()
        if not user_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz kullanıcıyı seçin.")
            return

        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                if user.username == "admin":
                    QMessageBox.warning(self, "Hata", "Ana admin kullanıcısı silinemez.")
                    return
                reply = QMessageBox.question(
                    self, "Onay", f"'{user.username}' kullanıcısını silmek istediğinize emin misiniz?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    user.is_deleted = True
                    self.db.commit()
                    QMessageBox.information(self, "Başarılı", "Kullanıcı silindi.")
                    self.load_users()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Silme hatası: {e}")

    def show_table_context_menu(self, pos):
        menu = QMenu(self)
        action_add = QAction("➕ Yeni Kullanıcı Ekle", self)
        action_add.triggered.connect(self.open_add_user_dialog)

        action_edit = QAction("✏️ Seçili Kullanıcıyı Değiştir", self)
        action_edit.triggered.connect(self.open_edit_user_dialog)

        action_inspect = QAction("🔍 Seçili Kullanıcıyı İncele", self)
        action_inspect.triggered.connect(self.inspect_user_dialog)

        action_delete = QAction("🗑️ Seçili Kullanıcıyı Sil", self)
        action_delete.triggered.connect(self.delete_user)

        action_cols = QAction("⚙️ Kolonları Yapılandır (DIA)", self)
        action_cols.triggered.connect(self.filterable_table.open_column_manager_dialog)

        menu.addAction(action_add)
        menu.addAction(action_edit)
        menu.addAction(action_inspect)
        menu.addSeparator()
        menu.addAction(action_delete)
        menu.addSeparator()
        menu.addAction(action_cols)
        menu.exec(self.table.viewport().mapToGlobal(pos))


class ViewSettingsWidget(QWidget):
    """DIA stiline ve 3-Panelli Düzen mimarisine sahip Görünüm Profilleri Paneli."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profiles: dict[str, Any] = {}
        self.headers_dict = {
            0: ("Profil Adı", "name"),
            1: ("Sürüm", "version"),
            2: ("Profil Tipi", "profile_type"),
            3: ("Aktiflik Durumu", "is_active"),
            4: ("Dondurulmuş Sütunlar", "frozen_columns"),
            5: ("Görsel Kural Sayısı", "rules_count"),
        }
        self.init_ui()

    def toolbar_btn_style(self, bg_color="#ffffff", text_color="#1e293b"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{ background-color: #f1f5f9; }}
        """

    def dia_btn_style(self, bg_color="#3b82f6", hover_color="#2563eb", text_color="#ffffff"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {hover_color}; }}
        """

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # SOL PANEL (EdgeTriggeredPanel)
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)

        filter_content = QWidget()
        filter_lyt = QVBoxLayout(filter_content)
        filter_lyt.setContentsMargins(4, 4, 4, 4)
        filter_lyt.setSpacing(10)

        lbl_module = QLabel("Ekran / Modül Seçin:")
        lbl_module.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 12px;")
        filter_lyt.addWidget(lbl_module)

        self.module_combo = QComboBox()
        self.module_combo.addItem("👥 Cariler / Müşteriler", "customers")
        self.module_combo.addItem("💾 Yedekleme Tanımları", "backup_tasks")
        self.module_combo.addItem("🔄 Geri Yükleme Tanımları", "restore_tasks")
        self.module_combo.addItem("🏢 Firma Tanımları", "sites")
        self.module_combo.addItem("👥 Kullanıcı Tanımları", "users")
        self.module_combo.addItem("📦 Ürünler / Stok", "products")
        self.module_combo.setStyleSheet("QComboBox { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background-color: white; font-weight: bold; font-size: 12px; }")
        self.module_combo.currentIndexChanged.connect(self.load_profiles)
        filter_lyt.addWidget(self.module_combo)

        lbl_search = QLabel("Profil Arama:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Profil ara...")
        self.txt_search.setStyleSheet("QLineEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background-color: white; font-size: 12px; }")
        self.txt_search.textChanged.connect(self.load_profiles)
        filter_lyt.addWidget(lbl_search)
        filter_lyt.addWidget(self.txt_search)

        filter_lyt.addStretch()
        self.left_panel.set_content(filter_content)
        main_layout.addWidget(self.left_panel)

        # ORTA PANEL (Dinamik Grid & Görsel Kural Detayları)
        self.center_container = QWidget()
        center_lyt = QVBoxLayout(self.center_container)
        center_lyt.setContentsMargins(4, 0, 4, 0)
        center_lyt.setSpacing(8)

        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key="view_settings",
            enable_profile_bar=False,
            parent=self,
        )
        self.table = self.filterable_table.table_view

        self.table_model = QStandardItemModel(self)
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
        self.table_model.setHorizontalHeaderLabels(headers)
        self.table.setModel(self.table_model)

        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setDefaultSectionSize(130)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self.on_profile_selected)

        self.table.setStyleSheet("""
            QTableView {
                border: 1px solid #cbd5e1;
                background-color: white;
                gridline-color: #f1f5f9;
                border-radius: 6px;
                font-size: 12px;
                color: #334155;
            }
            QTableView::item { padding: 6px; }
            QTableView::item:selected { background-color: #eff6ff; color: #1d4ed8; font-weight: 600; }
            QHeaderView::section { background-color: #f8fafc; color: #475569; padding: 8px; border: none; border-right: 1px solid #cbd5e1; border-bottom: 2px solid #cbd5e1; font-weight: bold; }
        """)
        center_lyt.addWidget(self.filterable_table, 1)

        # Alt Bölüm: Profil Detay Koyu & Görsel Kurallar
        detail_frame = QFrame()
        detail_frame.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        detail_lyt = QHBoxLayout(detail_frame)
        detail_lyt.setContentsMargins(10, 10, 10, 10)
        detail_lyt.setSpacing(12)

        info_box = QVBoxLayout()
        lbl_info_title = QLabel("Profil Detayları")
        lbl_info_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_info_title.setStyleSheet("color: #1e3a8a;")
        info_box.addWidget(lbl_info_title)

        self.lbl_profile_info = QLabel("Lütfen yukarıdaki tablodan bir profil seçiniz.")
        self.lbl_profile_info.setStyleSheet("color: #334155; font-size: 12px;")
        info_box.addWidget(self.lbl_profile_info)
        info_box.addStretch()
        detail_lyt.addLayout(info_box, 1)

        rules_box = QVBoxLayout()
        lbl_rules_title = QLabel("Aktif Görsel Kurallar:")
        lbl_rules_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_rules_title.setStyleSheet("color: #1e3a8a;")
        rules_box.addWidget(lbl_rules_title)

        self.rules_list = QListWidget()
        self.rules_list.setFixedHeight(100)
        self.rules_list.setStyleSheet("QListWidget { border: 1px solid #cbd5e1; border-radius: 4px; background-color: #f8fafc; color: #334155; } QListWidget::item { padding: 4px 8px; border-bottom: 1px solid #e2e8f0; }")
        rules_box.addWidget(self.rules_list)
        detail_lyt.addLayout(rules_box, 1)

        center_lyt.addWidget(detail_frame)

        # DIA Alt Buton Çubuğu
        self.action_bar = QFrame()
        self.action_bar.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        action_bar_lyt = QHBoxLayout(self.action_bar)
        action_bar_lyt.setContentsMargins(8, 6, 8, 6)
        action_bar_lyt.setSpacing(8)

        self.btn_set_active = QPushButton("⭐ Aktif Yap")
        self.btn_set_active.setStyleSheet(self.dia_btn_style("#3b82f6", "#2563eb"))
        self.btn_set_active.clicked.connect(self.set_selected_as_active)

        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setStyleSheet(self.dia_btn_style("#ef4444", "#dc2626"))
        self.btn_delete.clicked.connect(self.delete_selected_profile)

        self.btn_reset_all = QPushButton("💥 Tüm Görünüm Tanımlarını Sil")
        self.btn_reset_all.setStyleSheet(self.dia_btn_style("#dc2626", "#b91c1c"))
        self.btn_reset_all.clicked.connect(self.reset_all_profiles)

        self.btn_refresh = QPushButton("🔄 Yenile")
        self.btn_refresh.setStyleSheet(self.dia_btn_style("#64748b", "#475569"))
        self.btn_refresh.clicked.connect(self.load_profiles)

        action_bar_lyt.addWidget(self.btn_set_active)
        action_bar_lyt.addWidget(self.btn_delete)
        action_bar_lyt.addWidget(self.btn_reset_all)
        action_bar_lyt.addWidget(self.btn_refresh)
        action_bar_lyt.addStretch()

        self.lbl_record_count = QLabel("Toplam Profil: 0")
        self.lbl_record_count.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        action_bar_lyt.addWidget(self.lbl_record_count)

        center_lyt.addWidget(self.action_bar)
        main_layout.addWidget(self.center_container, 1)

        # SAĞ PANEL (EdgeTriggeredPanel)
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_content = QWidget()
        right_lyt = QVBoxLayout(right_content)
        right_lyt.setContentsMargins(4, 4, 4, 4)
        right_lyt.setSpacing(8)

        grp_prof = QFrame()
        grp_prof.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_prof_lyt = QVBoxLayout(grp_prof)
        grp_prof_lyt.setContentsMargins(6, 8, 6, 8)
        grp_prof_lyt.setSpacing(6)

        lbl_grp_prof = QLabel("PROFİL İŞLEMLERİ")
        lbl_grp_prof.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_prof.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_prof_lyt.addWidget(lbl_grp_prof)

        btn_r_active = QPushButton("⭐ Profili Aktif Yap")
        btn_r_active.setStyleSheet(self.toolbar_btn_style("#3b82f6", "#ffffff"))
        btn_r_active.clicked.connect(self.set_selected_as_active)

        btn_r_del = QPushButton("🗑️ Profili Sil")
        btn_r_del.setStyleSheet(self.toolbar_btn_style("#ef4444", "#ffffff"))
        btn_r_del.clicked.connect(self.delete_selected_profile)

        btn_r_reset = QPushButton("💥 Tüm Görünüm Tanımlarını Sil")
        btn_r_reset.setStyleSheet(self.toolbar_btn_style("#dc2626", "#ffffff"))
        btn_r_reset.clicked.connect(self.reset_all_profiles)

        grp_prof_lyt.addWidget(btn_r_active)
        grp_prof_lyt.addWidget(btn_r_del)
        grp_prof_lyt.addWidget(btn_r_reset)
        right_lyt.addWidget(grp_prof)

        grp_view = QFrame()
        grp_view.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_view_lyt = QVBoxLayout(grp_view)
        grp_view_lyt.setContentsMargins(6, 8, 6, 8)
        grp_view_lyt.setSpacing(6)

        lbl_grp_view = QLabel("GÖRÜNÜM")
        lbl_grp_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_view.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_view_lyt.addWidget(lbl_grp_view)

        btn_r_cols = QPushButton("⚙️ Kolonları Yapılandır")
        btn_r_cols.setStyleSheet(self.toolbar_btn_style())
        btn_r_cols.clicked.connect(self.filterable_table.open_column_manager_dialog)

        grp_view_lyt.addWidget(btn_r_cols)
        right_lyt.addWidget(grp_view)
        right_lyt.addStretch()

        right_scroll.setWidget(right_content)
        self.right_panel.set_content(right_scroll)
        main_layout.addWidget(self.right_panel)

        # Test uyumluluğu için gizli profile_list proxy nesnesi (QListWidget taklidi)
        self.profile_list = QListWidget()
        self.profile_list.hide()

        self.load_profiles()

    def get_current_profile_key(self) -> str:
        key = self.module_combo.currentData()
        return str(key or "customers")

    def load_profiles(self):
        self.table_model.removeRows(0, self.table_model.rowCount())
        self.profile_list.clear()

        profile_key = self.get_current_profile_key()
        from src.desktop.managers.profile_manager import ProfileManager
        pm = ProfileManager(profile_key=profile_key)
        self.current_profiles = pm.load_profiles()
        active_name = pm.get_active_profile_name()

        search_txt = self.txt_search.text().strip().lower()

        for name, profile in self.current_profiles.items():
            if search_txt and search_txt not in name.lower():
                continue

            is_active_str = "⭐ EVET (Aktif)" if name == active_name else "HAYIR"
            p_type = "Sistem Varsayılanı" if profile.profile.profile_type == "system_default" else "Kullanıcı Tanımlı"
            frozen = ", ".join(profile.column_settings.frozen_columns.columns) or "Yok"
            rules_cnt = str(len(profile.visual_rules))

            row_items = [
                QStandardItem(name),
                QStandardItem(str(profile.version)),
                QStandardItem(p_type),
                QStandardItem(is_active_str),
                QStandardItem(frozen),
                QStandardItem(rules_cnt),
            ]
            row_items[0].setData(name, Qt.ItemDataRole.UserRole)
            self.table_model.appendRow(row_items)

            # Test uyumluluğu proxy listesi
            item_text = f"⭐ {name} (Aktif)" if name == active_name else name
            self.profile_list.addItem(item_text)

        self.lbl_record_count.setText(f"Toplam Profil: {self.table_model.rowCount()}")
        if self.table_model.rowCount() > 0:
            self.table.selectRow(0)
            self.profile_list.setCurrentRow(0)

    def get_selected_profile_name(self) -> str | None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            return None
        row = indexes[0].row()
        item = self.table_model.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def on_profile_selected(self):
        raw_name = self.get_selected_profile_name()
        if not raw_name:
            self.lbl_profile_info.setText("Lütfen yukarıdaki tablodan bir profil seçiniz.")
            self.rules_list.clear()
            return

        profile = self.current_profiles.get(raw_name)
        if not profile:
            return

        info_text = (
            f"<b>Profil Adı:</b> {profile.profile.name}<br>"
            f"<b>Sürüm:</b> {profile.version}<br>"
            f"<b>Tip:</b> {'Sistem Varsayılanı' if profile.profile.profile_type == 'system_default' else 'Kullanıcı Tanımlı'}<br>"
            f"<b>Dondurulmuş Sütunlar:</b> {', '.join(profile.column_settings.frozen_columns.columns) or 'Yok'}"
        )
        self.lbl_profile_info.setText(info_text)

        self.rules_list.clear()
        if profile.visual_rules:
            for rule in profile.visual_rules:
                r_text = f"{rule.style.icon or '🎨'} {rule.name} (Öncelik: {rule.priority}) - {rule.condition.field} {rule.condition.operator} {rule.condition.value}"
                r_item = QListWidgetItem(r_text)
                if rule.style.background_color:
                    from PyQt6.QtGui import QColor
                    r_item.setBackground(QColor(rule.style.background_color))
                if rule.style.text_color:
                    from PyQt6.QtGui import QColor
                    r_item.setForeground(QColor(rule.style.text_color))
                self.rules_list.addItem(r_item)
        else:
            self.rules_list.addItem(QListWidgetItem("Bu profile ait özel görsel kural bulunmuyor."))

    def set_selected_as_active(self):
        raw_name = self.get_selected_profile_name()
        if not raw_name:
            QMessageBox.warning(self, "Uyarı", "Lütfen aktif yapmak istediğiniz profili seçin.")
            return

        profile_key = self.get_current_profile_key()
        from src.desktop.managers.profile_manager import ProfileManager
        pm = ProfileManager(profile_key=profile_key)
        pm.set_active_profile_name(raw_name)

        QMessageBox.information(self, "Başarılı", f"'{raw_name}' profili aktif görünüm olarak ayarlandı.")
        self.load_profiles()

    def delete_selected_profile(self):
        raw_name = self.get_selected_profile_name()
        if not raw_name:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz profili seçin.")
            return

        if raw_name == "Varsayılan":
            QMessageBox.warning(self, "Uyarı", "Varsayılan sistem profili silinemez.")
            return

        confirm = QMessageBox.question(
            self,
            "Profil Sil",
            f"'{raw_name}' profilini silmek istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            profile_key = self.get_current_profile_key()
            from src.desktop.managers.profile_manager import ProfileManager
            pm = ProfileManager(profile_key=profile_key)
            if pm.delete_profile(raw_name):
                QMessageBox.information(self, "Başarılı", f"'{raw_name}' profili başarıyla silindi.")
                self.load_profiles()

    def reset_all_profiles(self):
        """Asks confirmation and resets all view profile settings to factory defaults."""
        confirm = QMessageBox.question(
            self,
            "Tüm Görünüm Tanımlarını Sil",
            "Tüm özel görünüm profillerini ve ayarlarını silerek fabrika ayarlarına (Varsayılan) dönmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            from src.desktop.managers.profile_manager import ProfileManager
            ProfileManager.reset_all_profiles_to_factory_defaults()
            QMessageBox.information(
                self,
                "Başarılı",
                "Tüm görünüm tanımları başarıyla silindi ve sistem fabrika ayarlarına döndürüldü.",
            )
            self.load_profiles()

    def show_table_context_menu(self, pos):
        menu = QMenu(self)
        action_active = QAction("⭐ Seçili Profili Aktif Yap", self)
        action_active.triggered.connect(self.set_selected_as_active)

        action_delete = QAction("🗑️ Seçili Profili Sil", self)
        action_delete.triggered.connect(self.delete_selected_profile)

        action_cols = QAction("⚙️ Kolonları Yapılandır (DIA)", self)
        action_cols.triggered.connect(self.filterable_table.open_column_manager_dialog)

        menu.addAction(action_active)
        menu.addAction(action_delete)
        menu.addSeparator()
        menu.addAction(action_cols)
        menu.exec(self.table.viewport().mapToGlobal(pos))
