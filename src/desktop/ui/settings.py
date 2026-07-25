import hashlib
import logging
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.models import Site, User
from src.desktop.ui.sites import SitesWidget

logger = logging.getLogger(__name__)


class SettingsWidget(QTabWidget):
    """Firma ve kullanıcı ayarlarının sekmeli olarak yönetildiği genel ayarlar ekranı."""

    def __init__(self, db_session, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.init_ui()

    def init_ui(self):
        # 1. Firma Tanımları Sekmesi
        self.sites_tab = SitesWidget(self.db)
        self.addTab(self.sites_tab, "🏢 Firma Tanımları")

        # 2. Kullanıcı Tanımları Sekmesi
        self.users_tab = UserManagementWidget(self.db)
        self.addTab(self.users_tab, "👥 Kullanıcı Yetkilendirme")

        # Firma güncellendiğinde kullanıcı sekmesindeki firma yetkileri listesi tazelensin
        self.sites_tab.sites_updated.connect(self.users_tab.load_sites)

        # 3. Görünüm Profilleri Sekmesi
        self.view_settings_tab = ViewSettingsWidget()
        self.addTab(self.view_settings_tab, "🎨 Görünüm Profilleri")


class UserManagementWidget(QWidget):
    """Kullanıcı ekleme/düzenleme ve firma bazlı yetkilendirme ekranı."""

    def __init__(self, db_session, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.selected_user_id = None
        self.site_checkboxes = {}
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background-color: #cbd5e1; width: 1px; }",
        )

        # SOL: Kullanıcı Listesi
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)

        lbl_list = QLabel("Kullanıcılar")
        lbl_list.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 13px;",
        )
        left_layout.addWidget(lbl_list)

        self.user_list = QListWidget()
        self.user_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
                color: #334155;
            }
            QListWidget::item { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }
            QListWidget::item:selected { background-color: #eff6ff; color: #1e40af; font-weight: bold; }
        """)
        self.user_list.itemSelectionChanged.connect(self.on_user_selected)
        left_layout.addWidget(self.user_list)

        self.btn_new = QPushButton("➕ Yeni Kullanıcı Ekle")
        self.btn_new.setStyleSheet("""
            QPushButton { background-color: #10b981; color: white; border: none; border-radius: 6px; padding: 8px; font-weight: bold; }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_new.clicked.connect(self.clear_form)
        left_layout.addWidget(self.btn_new)

        # SAĞ: Detay Formu ve Yetkiler
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.setSpacing(10)

        # Form Kartı
        form_frame = QFrame()
        form_frame.setStyleSheet(
            "background-color: white; border: 1px solid #e2e8f0; border-radius: 8px;",
        )
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(15, 15, 15, 15)
        form_layout.setSpacing(12)

        input_style = "QLineEdit, QComboBox { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background-color: white; color: #0f172a; }"

        # Kullanıcı Adı
        lbl_uname = QLabel("Kullanıcı Adı:")
        lbl_uname.setStyleSheet("font-weight: bold; color: #475569;")
        self.uname_input = QLineEdit()
        self.uname_input.setStyleSheet(input_style)
        form_layout.addWidget(lbl_uname)
        form_layout.addWidget(self.uname_input)

        # Şifre
        lbl_pwd = QLabel("Şifre:")
        lbl_pwd.setStyleSheet("font-weight: bold; color: #475569;")
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_input.setStyleSheet(input_style)
        self.pwd_input.setPlaceholderText("Değiştirmek istemiyorsanız boş bırakın")
        form_layout.addWidget(lbl_pwd)
        form_layout.addWidget(self.pwd_input)

        # Rol
        lbl_role = QLabel("Rol:")
        lbl_role.setStyleSheet("font-weight: bold; color: #475569;")
        self.role_combo = QComboBox()
        self.role_combo.addItem("Standart Kullanıcı", "user")
        self.role_combo.addItem("Yönetici (Admin)", "admin")
        self.role_combo.setStyleSheet(input_style)
        form_layout.addWidget(lbl_role)
        form_layout.addWidget(self.role_combo)

        # Durum
        self.active_check = QCheckBox("Hesap Aktif (Girişe İzin Ver)")
        self.active_check.setStyleSheet("font-weight: bold; color: #475569;")
        self.active_check.setChecked(True)
        form_layout.addWidget(self.active_check)

        # Firmalar Yetki Listesi
        lbl_sites = QLabel("Erişebileceği Şirketler:")
        lbl_sites.setStyleSheet(
            "font-weight: bold; color: #475569; margin-top: 10px;",
        )
        form_layout.addWidget(lbl_sites)

        # Kaydırılabilir Checkbox Listesi
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #cbd5e1; border-radius: 6px; }",
        )

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_layout.setSpacing(6)
        self.scroll_area.setWidget(self.scroll_content)
        form_layout.addWidget(self.scroll_area, 1)

        # Butonlar
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setStyleSheet("""
            QPushButton { background-color: #3b82f6; color: white; border: none; border-radius: 6px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.btn_save.clicked.connect(self.save_user)

        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setStyleSheet("""
            QPushButton { background-color: #ef4444; color: white; border: none; border-radius: 6px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #dc2626; }
            QPushButton:disabled { background-color: #cbd5e1; color: #94a3b8; }
        """)
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self.delete_user)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addStretch()
        form_layout.addLayout(btn_layout)

        right_layout.addWidget(form_frame)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([200, 500])
        main_layout.addWidget(splitter)

        self.load_users()
        self.load_sites()

    def load_users(self):
        self.user_list.clear()
        try:
            users = self.db.query(User).filter(User.is_deleted == False).all()
            for user in users:
                role_txt = "Admin" if user.role == "admin" else "Kullanıcı"
                status_txt = "Aktif" if user.is_active else "Pasif"
                item = QListWidgetItem(
                    f"👤 {user.username} ({role_txt}) - {status_txt}",
                )
                item.setData(Qt.ItemDataRole.UserRole, user.id)
                self.user_list.addItem(item)
        except Exception as e:
            QMessageBox.critical(
                self, "Hata", f"Kullanıcılar listelenirken hata oluştu: {e}",
            )

    def load_sites(self):
        # Temizle
        for cb in self.site_checkboxes.values():
            self.scroll_layout.removeWidget(cb)
            cb.deleteLater()
        self.site_checkboxes.clear()

        try:
            sites = (
                self.db.query(Site)
                .filter(Site.is_active == True, Site.is_deleted == False)
                .all()
            )
            for site in sites:
                cb = QCheckBox(site.name)
                cb.setStyleSheet("color: #334155; font-size: 12px;")
                self.scroll_layout.addWidget(cb)
                self.site_checkboxes[site.id] = cb
            self.scroll_layout.addStretch()
        except Exception as e:
            logger.error(f"Firma listesi yüklenemedi: {e}")

    def on_user_selected(self):
        selected = self.user_list.selectedItems()
        if not selected:
            self.clear_form()
            return

        user_id = selected[0].data(Qt.ItemDataRole.UserRole)
        self.selected_user_id = user_id

        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                self.uname_input.setText(user.username)
                self.pwd_input.clear()
                index = self.role_combo.findData(user.role)
                if index != -1:
                    self.role_combo.setCurrentIndex(index)
                self.active_check.setChecked(user.is_active)

                # Yetkili firmaları işaretle
                allowed_ids = {s.id for s in user.allowed_sites}
                for site_id, cb in self.site_checkboxes.items():
                    cb.setChecked(site_id in allowed_ids)

                self.btn_delete.setEnabled(user.username != "admin")
        except Exception as e:
            QMessageBox.critical(
                self, "Hata", f"Kullanıcı bilgileri yüklenemedi: {e}",
            )

    def clear_form(self):
        self.selected_user_id = None
        self.uname_input.clear()
        self.pwd_input.clear()
        self.role_combo.setCurrentIndex(0)
        self.active_check.setChecked(True)
        for cb in self.site_checkboxes.values():
            cb.setChecked(False)
        self.btn_delete.setEnabled(False)
        self.user_list.clearSelection()

    def save_user(self):
        username = self.uname_input.text().strip()
        password = self.pwd_input.text()
        role = self.role_combo.currentData()
        is_active = self.active_check.isChecked()

        if not username:
            QMessageBox.warning(self, "Uyarı", "Kullanıcı adı boş olamaz.")
            return

        salt = "multi_cms_salt_key"

        try:
            if self.selected_user_id:
                # Güncelleme
                user = (
                    self.db.query(User)
                    .filter(User.id == self.selected_user_id)
                    .first()
                )
                if user:
                    user.username = username
                    if password:
                        user.password_hash = hashlib.sha256(
                            (password + salt).encode("utf-8"),
                        ).hexdigest()
                    user.role = role
                    user.is_active = is_active
            else:
                # Yeni Ekleme
                if not password:
                    QMessageBox.warning(
                        self, "Uyarı", "Yeni kullanıcı için şifre girmelisiniz.",
                    )
                    return

                exists = (
                    self.db.query(User).filter(User.username == username).first()
                )
                if exists:
                    QMessageBox.warning(
                        self, "Uyarı", "Bu kullanıcı adı zaten mevcut.",
                    )
                    return

                pwd_hash = hashlib.sha256(
                    (password + salt).encode("utf-8"),
                ).hexdigest()
                user = User(
                    username=username,
                    password_hash=pwd_hash,
                    role=role,
                    is_active=is_active,
                )
                self.db.add(user)

            # Yetkileri güncelle
            user.allowed_sites.clear()
            for site_id, cb in self.site_checkboxes.items():
                if cb.isChecked():
                    site = (
                        self.db.query(Site).filter(Site.id == site_id).first()
                    )
                    if site:
                        user.allowed_sites.append(site)

            self.db.commit()
            QMessageBox.information(
                self, "Başarılı", "Kullanıcı bilgileri kaydedildi.",
            )
            self.load_users()
            self.clear_form()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {e}")

    def delete_user(self):
        if not self.selected_user_id:
            return

        reply = QMessageBox.question(
            self,
            "Onay",
            "Seçili kullanıcıyı silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                user = (
                    self.db.query(User)
                    .filter(User.id == self.selected_user_id)
                    .first()
                )
                if user:
                    if user.username == "admin":
                        QMessageBox.warning(
                            self, "Hata", "Ana admin kullanıcısı silinemez.",
                        )
                        return
                    user.is_deleted = True
                    self.db.commit()
                    QMessageBox.information(self, "Başarılı", "Kullanıcı silindi.")
                    self.load_users()
                    self.clear_form()
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Hata", f"Silme hatası: {e}")





class ViewSettingsWidget(QWidget):
    """Tablo sütun görünümleri ve koşullu renklendirme kurallarının yönetildiği genel ayarlar sekmesi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_profiles: dict[str, Any] = {}
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background-color: #cbd5e1; width: 1px; }",
        )

        # SOL: Sütun Görünüm Profilleri
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)

        lbl_module = QLabel("Ekran / Modül Seçin:")
        lbl_module.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")
        left_layout.addWidget(lbl_module)

        self.module_combo = QComboBox()
        self.module_combo.addItem("👥 Cariler / Müşteriler", "customers")
        self.module_combo.addItem("💾 Görevler / Yedekleme", "backup")
        self.module_combo.addItem("🏢 Firma Tanımları", "sites")
        self.module_combo.addItem("👥 Kullanıcı Tanımları", "users")
        self.module_combo.addItem("📦 Ürünler / Stok", "products")
        self.module_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                color: #334155;
                font-weight: bold;
            }
        """)
        self.module_combo.currentIndexChanged.connect(self.load_profiles)
        left_layout.addWidget(self.module_combo)

        lbl_list = QLabel("Kayıtlı Görünüm Profilleri")
        lbl_list.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 12px; margin-top: 6px;",
        )
        left_layout.addWidget(lbl_list)

        self.profile_list = QListWidget()
        self.profile_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background-color: white;
                color: #334155;
            }
            QListWidget::item { padding: 8px 12px; border-bottom: 1px solid #f1f5f9; }
            QListWidget::item:selected { background-color: #eff6ff; color: #2563eb; font-weight: bold; }
        """)
        self.profile_list.itemSelectionChanged.connect(self.on_profile_selected)
        left_layout.addWidget(self.profile_list)

        btn_action_layout = QHBoxLayout()

        self.btn_set_active = QPushButton("⭐ Aktif Yap")
        self.btn_set_active.setStyleSheet("""
            QPushButton { background-color: #3b82f6; color: white; border-radius: 6px; padding: 6px 10px; font-weight: bold; }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.btn_set_active.clicked.connect(self.set_selected_as_active)
        btn_action_layout.addWidget(self.btn_set_active)

        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setStyleSheet("""
            QPushButton { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; border-radius: 6px; padding: 6px 10px; font-weight: bold; }
            QPushButton:hover { background-color: #fca5a5; }
        """)
        self.btn_delete.clicked.connect(self.delete_selected_profile)
        btn_action_layout.addWidget(self.btn_delete)

        left_layout.addLayout(btn_action_layout)
        splitter.addWidget(left_widget)

        # SAĞ: Profil Detayları ve Görsel Kurallar
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)

        lbl_details = QLabel("Profil Detayları & Renklendirme Kuralları")
        lbl_details.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 13px;",
        )
        right_layout.addWidget(lbl_details)

        self.details_group = QGroupBox("Profil Detayları")
        self.details_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
                color: #475569;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        """)
        details_layout = QVBoxLayout(self.details_group)
        details_layout.setSpacing(10)

        self.lbl_profile_info = QLabel("Lütfen sol taraftan bir profil seçiniz.")
        self.lbl_profile_info.setStyleSheet("color: #334155; font-size: 12px;")
        details_layout.addWidget(self.lbl_profile_info)

        lbl_rules_title = QLabel("Aktif Görsel Kurallar:")
        lbl_rules_title.setStyleSheet("font-weight: bold; color: #475569; margin-top: 6px;")
        details_layout.addWidget(lbl_rules_title)

        self.rules_list = QListWidget()
        self.rules_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                color: #334155;
            }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #f1f5f9; }
        """)
        details_layout.addWidget(self.rules_list)

        right_layout.addWidget(self.details_group)
        splitter.addWidget(right_widget)

        main_layout.addWidget(splitter)
        self.load_profiles()

    def get_current_profile_key(self) -> str:
        key = self.module_combo.currentData()
        return str(key or "customers")

    def load_profiles(self):
        self.profile_list.clear()
        profile_key = self.get_current_profile_key()

        from src.desktop.managers.profile_manager import ProfileManager
        pm = ProfileManager(profile_key=profile_key)
        self.current_profiles = pm.load_profiles()
        active_name = pm.get_active_profile_name()

        for name in self.current_profiles.keys():
            item_text = f"⭐ {name} (Aktif)" if name == active_name else name
            item = QListWidgetItem(item_text)
            if name == active_name:
                item.setFont(self.font())
            self.profile_list.addItem(item)

        if self.profile_list.count() > 0:
            self.profile_list.setCurrentRow(0)

    def on_profile_selected(self):
        item = self.profile_list.currentItem()
        if not item:
            self.lbl_profile_info.setText("Lütfen sol taraftan bir profil seçiniz.")
            self.rules_list.clear()
            return

        raw_name = item.text().replace("⭐ ", "").replace(" (Aktif)", "")
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
        item = self.profile_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Uyarı", "Lütfen aktif yapmak istediğiniz profili seçin.")
            return

        raw_name = item.text().replace("⭐ ", "").replace(" (Aktif)", "")
        profile_key = self.get_current_profile_key()

        from src.desktop.managers.profile_manager import ProfileManager
        pm = ProfileManager(profile_key=profile_key)
        pm.set_active_profile_name(raw_name)

        QMessageBox.information(self, "Başarılı", f"'{raw_name}' profili aktif görünüm olarak ayarlandı.")
        self.load_profiles()

    def delete_selected_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz profili seçin.")
            return

        raw_name = item.text().replace("⭐ ", "").replace(" (Aktif)", "")
        if raw_name == "Varsayılan":
            QMessageBox.warning(self, "Uyarı", "Varsayılan sistem profili silinemez.")
            return

        confirm = QMessageBox.question(
            self,
            "Profil Sil",
            f"'{raw_name}' profilini silmek istediğinizden emin misiniz?",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            profile_key = self.get_current_profile_key()
            from src.desktop.managers.profile_manager import ProfileManager
            pm = ProfileManager(profile_key=profile_key)
            if pm.delete_profile(raw_name):
                QMessageBox.information(self, "Başarılı", f"'{raw_name}' profili başarıyla silindi.")
                self.load_profiles()

