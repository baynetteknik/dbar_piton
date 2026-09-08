"""TOYA ERP - Genel Ayarlar Ekranı (General Settings Screen - sys.set.001).

Bu modül; Sol Sidebar (İşlemler + Menü Grupları), QStackedWidget Body ve Alt Bar
mimarisinde tüm ERP sistem ayarlarını yönetir.
"""

import hashlib
import json
import logging
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import (
    Category,
    Currency,
    PaymentPlan,
    Site,
    SystemSetting,
    UnitDefinition,
    User,
    WarehouseDefinition,
)
from src.desktop.ui.components.collapsible_section import CollapsibleSection
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
from src.desktop.ui.screen_definitions_manager import (
    ScreenDefinitionsManagerWidget,
)
from src.desktop.ui.sites import SitesWidget

logger = logging.getLogger(__name__)


class UserDialog(QDialog):
    """3-panelli düzene uygun Kullanıcı Ekleme / Düzenleme Ekranı."""

    def __init__(
        self, db_session, user_id=None, read_only=False, parent=None,
    ) -> None:
        super().__init__(parent)
        self.db = db_session
        self.user_id = user_id
        self.read_only = read_only
        self.site_checkboxes: dict[int, QCheckBox] = {}

        if self.user_id:
            title = (
                "Kullanıcı Detayı / Düzenle"
                if not read_only
                else "Kullanıcı Detayı İncele"
            )
            self.setWindowTitle(title)
        else:
            self.setWindowTitle("Yeni Kullanıcı Tanımla")

        self.setMinimumWidth(880)
        self.setMinimumHeight(640)
        self.init_ui()

        if self.user_id:
            self.load_user_data()
        else:
            self.load_sites()

    def dia_btn_style(
        self,
        bg_color="#3b82f6",
        hover_color="#2563eb",
        text_color="#ffffff",
    ) -> str:
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

    def init_ui(self) -> None:
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
            QLineEdit:focus, QComboBox:focus {
                border-color: #3b82f6;
                background-color: white;
            }
        """

        # Üst Form Alanı
        top_form_frame = QFrame()
        top_form_frame.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #e2e8f0; "
            "border-radius: 6px;",
        )
        top_form_lyt = QHBoxLayout(top_form_frame)
        top_form_lyt.setContentsMargins(12, 12, 12, 12)
        top_form_lyt.setSpacing(16)

        # Sol Kolon
        col_left = QVBoxLayout()
        col_left.setSpacing(8)

        lbl_uname = QLabel("Kullanıcı Kodu / Adı *:")
        lbl_uname.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 11px;",
        )
        self.txt_username = QLineEdit()
        self.txt_username.setPlaceholderText("Örn: Baynet")
        self.txt_username.setStyleSheet(input_style)
        col_left.addWidget(lbl_uname)
        col_left.addWidget(self.txt_username)

        lbl_fullname = QLabel("Adı Soyadı:")
        lbl_fullname.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 11px;",
        )
        self.txt_fullname = QLineEdit()
        self.txt_fullname.setPlaceholderText("Örn: Baynet Bilişim")
        self.txt_fullname.setStyleSheet(input_style)
        col_left.addWidget(lbl_fullname)
        col_left.addWidget(self.txt_fullname)

        lbl_title = QLabel("Ünvanı:")
        lbl_title.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 11px;",
        )
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Örn: Sistem Yöneticisi")
        self.txt_title.setStyleSheet(input_style)
        col_left.addWidget(lbl_title)
        col_left.addWidget(self.txt_title)

        top_form_lyt.addLayout(col_left, 1)

        # Sağ Kolon
        col_mid = QVBoxLayout()
        col_mid.setSpacing(8)

        lbl_email = QLabel("E-Posta Adresi:")
        lbl_email.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 11px;",
        )
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("info@example.com")
        self.txt_email.setStyleSheet(input_style)
        col_mid.addWidget(lbl_email)
        col_mid.addWidget(self.txt_email)

        lbl_pwd = QLabel("Şifre:")
        lbl_pwd.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 11px;",
        )
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText(
            "Değiştirmek istemiyorsanız boş bırakın",
        )
        self.txt_password.setStyleSheet(input_style)
        col_mid.addWidget(lbl_pwd)
        col_mid.addWidget(self.txt_password)

        role_status_lyt = QHBoxLayout()
        role_lyt = QVBoxLayout()
        lbl_role = QLabel("Rol:")
        lbl_role.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 11px;",
        )
        self.cmb_role = QComboBox()
        self.cmb_role.addItem("Standart Kullanıcı", "user")
        self.cmb_role.addItem("Yönetici (Admin)", "admin")
        self.cmb_role.setStyleSheet(input_style)
        role_lyt.addWidget(lbl_role)
        role_lyt.addWidget(self.cmb_role)

        status_lyt = QVBoxLayout()
        lbl_status = QLabel("Durum:")
        lbl_status.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 11px;",
        )
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

        # Sağ Aksiyon Koyu
        action_box = QFrame()
        action_box.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; "
            "border-radius: 6px;",
        )
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
        perm_frame.setStyleSheet(
            "background-color: white; border: 1px solid #cbd5e1; "
            "border-radius: 6px;",
        )
        perm_lyt = QVBoxLayout(perm_frame)
        perm_lyt.setContentsMargins(12, 10, 12, 10)
        perm_lyt.setSpacing(8)

        lbl_perm_title = QLabel("Yetki ve Gruplar")
        lbl_perm_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_perm_title.setStyleSheet("color: #1e3a8a;")
        perm_lyt.addWidget(lbl_perm_title)

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

        sites_groups_lyt = QHBoxLayout()

        # Sol: Erişebileceği Şirketler
        sites_box = QGroupBox("Erişebileceği Şirketler / Firmalar")
        sites_box.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #475569; "
            "border: 1px solid #cbd5e1; border-radius: 6px; "
            "margin-top: 6px; padding-top: 10px; }",
        )
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
        groups_box.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #475569; "
            "border: 1px solid #cbd5e1; border-radius: 6px; "
            "margin-top: 6px; padding-top: 10px; }",
        )
        groups_box_lyt = QVBoxLayout(groups_box)

        self.groups_list = QListWidget()
        self.groups_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                color: #334155;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #fef08a;
                color: #854d0e;
                font-weight: bold;
            }
        """)
        for grp in [
            "admin (Tam Yetkili)",
            "Gerekli Şirketler Yetkisi",
            "Görme ve Raporlama Yetkisi",
        ]:
            item = QListWidgetItem(grp)
            is_admin = "admin" in grp
            item.setCheckState(
                Qt.CheckState.Checked if is_admin else Qt.CheckState.Unchecked,
            )
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
        lbl_other_info = QLabel(
            "Ek kullanıcı sistem yetkileri ve kısıtlamaları bu alandan yapılandırılır.",
        )
        lbl_other_info.setStyleSheet("color: #64748b; font-size: 12px;")
        tab_other_lyt.addWidget(lbl_other_info)
        tab_other_lyt.addStretch()
        self.tab_widget.addTab(tab_other, "B. Diğer Bilgiler")

        # Sekme 3: C. Ön Tanımlı Parametreler
        tab_params = QWidget()
        tab_params_lyt = QVBoxLayout(tab_params)
        tab_params_lyt.setContentsMargins(16, 16, 16, 16)
        lbl_params_info = QLabel(
            "Kullanıcının varsayılan olarak açılmasını istediği firma ve mecra parametreleri.",
        )
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
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }
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

    def load_sites(self) -> None:
        for cb in self.site_checkboxes.values():
            self.scroll_layout.removeWidget(cb)
            cb.deleteLater()
        self.site_checkboxes.clear()
        self.cmb_sites_filter.clear()
        self.cmb_sites_filter.addItem("[Tüm Firmalar]", 0)

        try:
            sites = (
                self.db.query(Site)
                .filter(Site.is_active == True, Site.is_deleted == False)
                .all()
            )
            for site in sites:
                cb = QCheckBox(f"🏢 {site.name} ({site.cms_type.upper()})")
                cb.setStyleSheet(
                    "color: #334155; font-size: 12px; font-weight: 600;",
                )
                self.scroll_layout.addWidget(cb)
                self.site_checkboxes[site.id] = cb
                self.cmb_sites_filter.addItem(site.name, site.id)
            self.scroll_layout.addStretch()
        except Exception as e:
            logger.error(f"Firma listesi yüklenemedi: {e}")

    def load_user_data(self) -> None:
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
            QMessageBox.critical(
                self, "Hata", f"Kullanıcı detayları yüklenemedi: {e}",
            )

    def save_user(self) -> None:
        username = self.txt_username.text().strip()
        password = self.txt_password.text()
        role = self.cmb_role.currentData()
        is_active = bool(self.cmb_status.currentData())

        if not username:
            QMessageBox.warning(
                self, "Uyarı", "Kullanıcı Kodu / Adı boş bırakılamaz.",
            )
            return

        salt = "multi_cms_salt_key"
        try:
            if self.user_id:
                user = (
                    self.db.query(User).filter(User.id == self.user_id).first()
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
                if not password:
                    QMessageBox.warning(
                        self, "Uyarı", "Yeni kullanıcı için şifre girmelisiniz.",
                    )
                    return
                exists = (
                    self.db.query(User)
                    .filter(User.username == username)
                    .first()
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
            self.accept()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {e}")


class UserManagementWidget(QWidget):
    """Kullanıcı Tanımları Yönetim Paneli."""

    def __init__(self, db_session, parent=None, embedded: bool = False) -> None:
        super().__init__(parent)
        self.db = db_session
        self.profile_key = "users"
        # embedded=True: Genel Ayarlar kabuğu içinde — kendi üst filtre barını
        # ve alt aksiyon barını kurmaz; arama/aksiyonlar kabuk sidebar'larından
        # gelir (çift arama/filtre/buton olmasın).
        self.embedded = embedded

        self.headers_dict = {
            0: ("ID", "id"),
            1: ("Kullanıcı Adı", "username"),
            2: ("Rol", "role"),
            3: ("Durum", "is_active"),
            4: ("Yetkili Firma Sayısı", "allowed_sites_count"),
        }

        self.init_ui()
        self.load_users()

    def apply_quick_search(self, text: str):
        if hasattr(self, "txt_search"):
            self.txt_search.setText(text)

    def apply_status_filter(self, status: str):
        combo = getattr(self, "cmb_filter_status", None)
        if combo is not None:
            idx = combo.findText(status)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def record_count(self) -> int:
        return self.table_model.rowCount() if hasattr(self, "table_model") else 0

    def toolbar_btn_style(
        self, bg_color="#ffffff", text_color="#1e293b",
    ) -> str:
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

    def dia_btn_style(
        self,
        bg_color="#3b82f6",
        hover_color="#2563eb",
        text_color="#ffffff",
    ) -> str:
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

    def init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Üst Filtre ve Hızlı Arama Barı
        top_filter_frame = QFrame()
        top_filter_frame.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;",
        )
        top_filter_lyt = QHBoxLayout(top_filter_frame)
        top_filter_lyt.setContentsMargins(8, 6, 8, 6)
        top_filter_lyt.setSpacing(8)

        lbl_search = QLabel("🔍 Arama:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Kullanıcı adı, isim veya e-posta...")
        self.txt_search.setStyleSheet(
            "QLineEdit { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background-color: white; font-size: 11px; }",
        )
        self.txt_search.textChanged.connect(self.load_users)

        lbl_role = QLabel("Rol:")
        lbl_role.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_role = QComboBox()
        self.cmb_filter_role.addItems(["Tümü", "admin", "user"])
        self.cmb_filter_role.setStyleSheet(
            "QComboBox { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background-color: white; font-size: 11px; }",
        )
        self.cmb_filter_role.currentTextChanged.connect(self.load_users)

        lbl_status = QLabel("Durum:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_status = QComboBox()
        self.cmb_filter_status.addItem("Tümü", -1)
        self.cmb_filter_status.addItem("Aktif", 1)
        self.cmb_filter_status.addItem("Pasif", 0)
        self.cmb_filter_status.setStyleSheet(
            "QComboBox { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background-color: white; font-size: 11px; }",
        )
        self.cmb_filter_status.currentIndexChanged.connect(self.load_users)

        btn_add_user = QPushButton("➕ Yeni Kullanıcı")
        btn_add_user.setStyleSheet(self.dia_btn_style("#10b981", "#059669"))
        btn_add_user.clicked.connect(self.open_add_user_dialog)

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setStyleSheet(self.dia_btn_style("#64748b", "#475569"))
        btn_refresh.clicked.connect(self.load_users)

        top_filter_lyt.addWidget(lbl_search)
        top_filter_lyt.addWidget(self.txt_search, 1)
        top_filter_lyt.addWidget(lbl_role)
        top_filter_lyt.addWidget(self.cmb_filter_role)
        top_filter_lyt.addWidget(lbl_status)
        top_filter_lyt.addWidget(self.cmb_filter_status)
        top_filter_lyt.addWidget(btn_add_user)
        top_filter_lyt.addWidget(btn_refresh)

        if not self.embedded:
            main_layout.addWidget(top_filter_frame)
        else:
            # Layout'a eklenmeyince GC'ye gider ve içindeki QLineEdit/combo'lar
            # silinir; parent vererek canlı ama gizli tut (kabuk bunları sürer).
            self._top_filter_frame = top_filter_frame
            top_filter_frame.setParent(self)
            top_filter_frame.hide()

        # Tablo
        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key="users",
            enable_profile_bar=False,
            parent=self,
        )
        self.table = self.filterable_table.table_view

        self.table_model = QStandardItemModel(self)
        headers = [
            self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())
        ]
        self.table_model.setHorizontalHeaderLabels(headers)
        self.table.setModel(self.table_model)

        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self.table.horizontalHeader().setDefaultSectionSize(140)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self.table.customContextMenuRequested.connect(
            self.show_table_context_menu,
        )
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
            QTableView::item:selected {
                background-color: #eff6ff;
                color: #1d4ed8;
                font-weight: 600;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                padding: 8px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                font-weight: bold;
            }
        """)
        main_layout.addWidget(self.filterable_table, 1)

        # Alt Aksiyon Barı
        self.action_bar = QFrame()
        self.action_bar.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; "
            "border-radius: 6px;",
        )
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
        self.lbl_record_count.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 11px;",
        )
        action_bar_lyt.addWidget(self.lbl_record_count)
        if not self.embedded:
            main_layout.addWidget(self.action_bar)
        else:
            self.action_bar.hide()

    def load_users(self) -> None:
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
                role_txt = (
                    "Yönetici (Admin)"
                    if user.role == "admin"
                    else "Standart Kullanıcı"
                )
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

    def load_sites(self) -> None:
        self.load_users()

    def get_selected_user_id(self) -> int | None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            return None
        row = indexes[0].row()
        item = self.table_model.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def open_add_user_dialog(self) -> None:
        dlg = UserDialog(self.db, user_id=None, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_users()

    def open_edit_user_dialog(self) -> None:
        user_id = self.get_selected_user_id()
        if not user_id:
            QMessageBox.warning(
                self, "Uyarı", "Lütfen düzenlemek istediğiniz kullanıcıyı seçin.",
            )
            return
        dlg = UserDialog(self.db, user_id=user_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_users()

    def inspect_user_dialog(self) -> None:
        user_id = self.get_selected_user_id()
        if not user_id:
            QMessageBox.warning(
                self, "Uyarı", "Lütfen incelemek istediğiniz kullanıcıyı seçin.",
            )
            return
        dlg = UserDialog(self.db, user_id=user_id, read_only=True, parent=self)
        dlg.exec()

    def delete_user(self) -> None:
        user_id = self.get_selected_user_id()
        if not user_id:
            QMessageBox.warning(
                self, "Uyarı", "Lütfen silmek istediğiniz kullanıcıyı seçin.",
            )
            return

        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                if user.username == "admin":
                    QMessageBox.warning(
                        self, "Hata", "Ana admin kullanıcısı silinemez.",
                    )
                    return
                reply = QMessageBox.question(
                    self,
                    "Onay",
                    f"'{user.username}' kullanıcısını silmek istediğinize emin misiniz?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    user.is_deleted = True
                    self.db.commit()
                    QMessageBox.information(
                        self, "Başarılı", "Kullanıcı silindi.",
                    )
                    self.load_users()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Silme hatası: {e}")

    def show_table_context_menu(self, pos) -> None:
        menu = QMenu(self)
        action_add = QAction("➕ Yeni Kullanıcı Ekle", self)
        action_add.triggered.connect(self.open_add_user_dialog)

        action_edit = QAction("✏️ Seçili Kullanıcıyı Değiştir", self)
        action_edit.triggered.connect(self.open_edit_user_dialog)

        action_inspect = QAction("🔍 Seçili Kullanıcıyı İncele", self)
        action_inspect.triggered.connect(self.inspect_user_dialog)

        action_delete = QAction("🗑️ Seçili Kullanıcıyı Sil", self)
        menu.addAction(action_add)
        menu.addAction(action_edit)
        menu.addAction(action_inspect)
        menu.addSeparator()
        menu.addAction(action_delete)

        self.filterable_table.add_column_actions_to_menu(menu)
        menu.exec(self.table.viewport().mapToGlobal(pos))


class ViewSettingsWidget(QWidget):
    """Görünüm Profilleri Paneli."""

    def __init__(self, parent=None, embedded: bool = False) -> None:
        super().__init__(parent)
        self.embedded = embedded
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

    def apply_quick_search(self, text: str):
        if hasattr(self, "txt_search"):
            self.txt_search.setText(text)

    def apply_status_filter(self, status: str):
        pass  # profil listesinde durum filtresi yok

    def record_count(self) -> int:
        return self.table_model.rowCount() if hasattr(self, "table_model") else 0

    def toolbar_btn_style(
        self, bg_color="#ffffff", text_color="#1e293b",
    ) -> str:
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

    def dia_btn_style(
        self,
        bg_color="#3b82f6",
        hover_color="#2563eb",
        text_color="#ffffff",
    ) -> str:
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

    def init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Üst Modül & Arama Barı
        top_bar = QFrame()
        top_bar.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;",
        )
        top_bar_lyt = QHBoxLayout(top_bar)
        top_bar_lyt.setContentsMargins(8, 6, 8, 6)
        top_bar_lyt.setSpacing(10)

        lbl_module = QLabel("Ekran / Modül:")
        lbl_module.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 11px;")
        self.module_combo = QComboBox()
        self.module_combo.addItem("📄 Teklif Yönetimi (isl.quo.001)", "quotations")
        self.module_combo.addItem("👥 Cariler / Müşteriler (isl.car.001)", "customers")
        self.module_combo.addItem("📦 Stok Kartları (isl.stk.001)", "stok")
        self.module_combo.addItem("👥 Cari Hesaplar", "cari")
        self.module_combo.addItem("📑 Hareket / Evrak Kalemleri (isl.doc.001)", "document_items")
        self.module_combo.addItem("🏢 Firma Tanımları", "sites")
        self.module_combo.addItem("👥 Kullanıcı Tanımları", "users")
        self.module_combo.addItem("📐 Ekran Şablonları", "screen_definitions")
        self.module_combo.addItem("💾 Yedekleme Tanımları", "backup_tasks")
        self.module_combo.addItem("🔄 Geri Yükleme Tanımları", "restore_tasks")
        self.module_combo.setStyleSheet(
            "QComboBox { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background-color: white; font-weight: bold; font-size: 11px; }",
        )
        self.module_combo.currentIndexChanged.connect(self.load_profiles)

        lbl_search = QLabel("Profil Arama:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Profil ara...")
        self.txt_search.setStyleSheet(
            "QLineEdit { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background-color: white; font-size: 11px; }",
        )
        self.txt_search.textChanged.connect(self.load_profiles)

        btn_refresh = QPushButton("🔄 Yenile")
        btn_refresh.setStyleSheet(self.dia_btn_style("#64748b", "#475569"))
        btn_refresh.clicked.connect(self.load_profiles)

        top_bar_lyt.addWidget(lbl_module)
        top_bar_lyt.addWidget(self.module_combo)
        top_bar_lyt.addWidget(lbl_search)
        top_bar_lyt.addWidget(self.txt_search, 1)
        top_bar_lyt.addWidget(btn_refresh)

        if not self.embedded:
            main_layout.addWidget(top_bar)
        else:
            self._top_bar = top_bar
            top_bar.setParent(self)
            top_bar.hide()

        # Tablo
        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key="view_settings",
            enable_profile_bar=False,
            parent=self,
        )
        self.table = self.filterable_table.table_view

        self.table_model = QStandardItemModel(self)
        headers = [
            self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())
        ]
        self.table_model.setHorizontalHeaderLabels(headers)
        self.table.setModel(self.table_model)

        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self.table.horizontalHeader().setDefaultSectionSize(130)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self.table.customContextMenuRequested.connect(
            self.show_table_context_menu,
        )
        self.table.selectionModel().selectionChanged.connect(
            self.on_profile_selected,
        )

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
            QTableView::item:selected {
                background-color: #eff6ff;
                color: #1d4ed8;
                font-weight: 600;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                padding: 8px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                font-weight: bold;
            }
        """)
        main_layout.addWidget(self.filterable_table, 1)

        # Alt Bölüm: Profil Detay & Görsel Kurallar
        detail_frame = QFrame()
        detail_frame.setStyleSheet(
            "background-color: white; border: 1px solid #cbd5e1; "
            "border-radius: 6px;",
        )
        detail_lyt = QHBoxLayout(detail_frame)
        detail_lyt.setContentsMargins(10, 10, 10, 10)
        detail_lyt.setSpacing(12)

        info_box = QVBoxLayout()
        lbl_info_title = QLabel("Profil Detayları")
        lbl_info_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl_info_title.setStyleSheet("color: #1e3a8a;")
        info_box.addWidget(lbl_info_title)

        self.lbl_profile_info = QLabel(
            "Lütfen yukarıdaki tablodan bir profil seçiniz.",
        )
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
        self.rules_list.setFixedHeight(80)
        self.rules_list.setStyleSheet(
            "QListWidget { border: 1px solid #cbd5e1; border-radius: 4px; "
            "background-color: #f8fafc; color: #334155; } "
            "QListWidget::item { padding: 4px 8px; border-bottom: 1px solid #e2e8f0; }",
        )
        rules_box.addWidget(self.rules_list)
        detail_lyt.addLayout(rules_box, 1)

        main_layout.addWidget(detail_frame)

        # Alt Buton Çubuğu
        self.action_bar = QFrame()
        self.action_bar.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; "
            "border-radius: 6px;",
        )
        action_bar_lyt = QHBoxLayout(self.action_bar)
        action_bar_lyt.setContentsMargins(8, 6, 8, 6)
        action_bar_lyt.setSpacing(8)

        self.btn_set_active = QPushButton("⭐ Aktif Yap")
        self.btn_set_active.setStyleSheet(
            self.dia_btn_style("#3b82f6", "#2563eb"),
        )
        self.btn_set_active.clicked.connect(self.set_selected_as_active)

        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setStyleSheet(self.dia_btn_style("#ef4444", "#dc2626"))
        self.btn_delete.clicked.connect(self.delete_selected_profile)

        self.btn_reset_all = QPushButton("💥 Tüm Görünüm Tanımlarını Sil")
        self.btn_reset_all.setStyleSheet(
            self.dia_btn_style("#dc2626", "#b91c1c"),
        )
        self.btn_reset_all.clicked.connect(self.reset_all_profiles)

        self.btn_refresh = QPushButton("🔄 Yenile")
        self.btn_refresh.setStyleSheet(
            self.dia_btn_style("#64748b", "#475569"),
        )
        self.btn_refresh.clicked.connect(self.load_profiles)

        action_bar_lyt.addWidget(self.btn_set_active)
        action_bar_lyt.addWidget(self.btn_delete)
        action_bar_lyt.addWidget(self.btn_reset_all)
        action_bar_lyt.addWidget(self.btn_refresh)
        action_bar_lyt.addStretch()

        self.lbl_record_count = QLabel("Toplam Profil: 0")
        self.lbl_record_count.setStyleSheet(
            "font-weight: bold; color: #475569; font-size: 11px;",
        )
        action_bar_lyt.addWidget(self.lbl_record_count)
        if not self.embedded:
            main_layout.addWidget(self.action_bar)
        else:
            self.action_bar.hide()

        self.profile_list = QListWidget()
        self.profile_list.hide()

        self.load_profiles()

    def get_current_profile_key(self) -> str:
        key = self.module_combo.currentData()
        return str(key or "customers")

    def load_profiles(self) -> None:
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

            is_active_str = (
                "⭐ EVET (Aktif)" if name == active_name else "HAYIR"
            )
            p_type = (
                "Sistem Varsayılanı"
                if profile.profile.profile_type == "system_default"
                else "Kullanıcı Tanımlı"
            )
            frozen = (
                ", ".join(profile.column_settings.frozen_columns.columns)
                or "Yok"
            )
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

            item_text = f"⭐ {name} (Aktif)" if name == active_name else name
            self.profile_list.addItem(item_text)

        self.lbl_record_count.setText(
            f"Toplam Profil: {self.table_model.rowCount()}",
        )
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

    def on_profile_selected(self) -> None:
        raw_name = self.get_selected_profile_name()
        if not raw_name:
            self.lbl_profile_info.setText(
                "Lütfen yukarıdaki tablodan bir profil seçiniz.",
            )
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
                r_text = (
                    f"{rule.style.icon or '🎨'} {rule.name} (Öncelik: {rule.priority}) - "
                    f"{rule.condition.field} {rule.condition.operator} {rule.condition.value}"
                )
                r_item = QListWidgetItem(r_text)
                if rule.style.background_color:
                    from PyQt6.QtGui import QColor

                    r_item.setBackground(QColor(rule.style.background_color))
                if rule.style.text_color:
                    from PyQt6.QtGui import QColor

                    r_item.setForeground(QColor(rule.style.text_color))
                self.rules_list.addItem(r_item)
        else:
            self.rules_list.addItem(
                QListWidgetItem("Bu profile ait özel görsel kural bulunmuyor."),
            )

    def set_selected_as_active(self) -> None:
        raw_name = self.get_selected_profile_name()
        if not raw_name:
            QMessageBox.warning(
                self, "Uyarı", "Lütfen aktif yapmak istediğiniz profili seçin.",
            )
            return

        profile_key = self.get_current_profile_key()
        from src.desktop.managers.profile_manager import ProfileManager

        pm = ProfileManager(profile_key=profile_key)
        pm.set_active_profile_name(raw_name)

        QMessageBox.information(
            self, "Başarılı", f"'{raw_name}' profili aktif görünüm olarak ayarlandı.",
        )
        self.load_profiles()

    def delete_selected_profile(self) -> None:
        raw_name = self.get_selected_profile_name()
        if not raw_name:
            QMessageBox.warning(
                self, "Uyarı", "Lütfen silmek istediğiniz profili seçin.",
            )
            return

        if raw_name == "Varsayılan":
            QMessageBox.warning(
                self, "Uyarı", "Varsayılan sistem profili silinemez.",
            )
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
                QMessageBox.information(
                    self, "Başarılı", f"'{raw_name}' profili başarıyla silindi.",
                )
                self.load_profiles()

    def reset_all_profiles(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Tüm Görünüm Tanımlarını Sil",
            "Tüm özel görünüm profillerini ve ayarlarını silerek "
            "fabrika ayarlarına (Varsayılan) dönmek istediğinizden emin misiniz?\n\n"
            "Bu işlem geri alınamaz.",
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

    def show_table_context_menu(self, pos) -> None:
        menu = QMenu(self)
        action_active = QAction("⭐ Seçili Profili Aktif Yap", self)
        action_active.triggered.connect(self.set_selected_as_active)

        action_delete = QAction("🗑️ Seçili Profili Sil", self)
        action_delete.triggered.connect(self.delete_selected_profile)

        action_cols = QAction("⚙️ Kolonları Yapılandır", self)
        action_cols.triggered.connect(
            self.filterable_table.open_column_manager_dialog,
        )

        menu.addAction(action_active)
        menu.addAction(action_delete)

        self.filterable_table.add_column_actions_to_menu(menu)
        menu.exec(self.table.viewport().mapToGlobal(pos))


class GeneralSettingsScreen(QWidget):
    """Genel Ayarlar Ana Ekranı — sys.set.001.

    Sol sidebar (menü + işlemler) + Body (QStackedWidget) + Alt bar mimarisinde
    tüm sistem ayarlarını yönetir.
    """

    toast_requested = pyqtSignal(str, str)

    # Menü yapısı — (grup_adı, ikon, [(menü_adı, panel_id), ...])
    MENU_STRUCTURE = [
        (
            "FİRMA",
            "🏢",
            [
                ("Firma Bilgileri", "firma_bilgileri"),
                ("Şube Tanımları", "sube_tanimlari"),
            ],
        ),
        (
            "KULLANICI & YETKİ",
            "👤",
            [
                ("Kullanıcılar", "kullanicilar"),
                ("Rol Tanımları", "roller"),
                ("Yetki Matrisi", "yetkiler"),
            ],
        ),
        (
            "FİNANS TANIMLARI",
            "💱",
            [
                ("Döviz & Kur", "doviz_kur"),
                ("Ödeme Planları", "odeme_planlari"),
                ("Fiyat Listeleri", "fiyat_listeleri"),
            ],
        ),
        (
            "STOK TANIMLARI",
            "📦",
            [
                ("Kategoriler", "stok_kategoriler"),
                ("Markalar", "stok_markalar"),
                ("Birim Tanımları", "birim_tanimlari"),
                ("Depo Tanımları", "depo_tanimlari"),
                ("Özel Alanlar", "stok_ozel_alanlar"),
            ],
        ),
        (
            "CARİ TANIMLARI",
            "👥",
            [
                ("Cari Grupları", "cari_gruplari"),
                ("Özel Alanlar", "cari_ozel_alanlar"),
            ],
        ),
        (
            "SİSTEM",
            "🖥️",
            [
                ("CMS / ERP Bağlantıları", "cms_baglantilari"),
                ("Görünüm Profilleri", "gorunum_profilleri"),
                ("Ekran Grid Tanım.", "ekran_grid"),
                ("Sürüm & Git", "surum_git"),
            ],
        ),
    ]

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.active_panel_id: str | None = None
        self.panels: dict[str, QWidget] = {}
        self.menu_buttons: dict[str, QPushButton] = {}
        self.ozel_alan_inputs: dict[str, dict[str, QLineEdit]] = {
            "stok": {},
            "cari": {},
        }

        self.init_ui()
        register_layout_hint(self, "Ayarlar", "Genel Ayarlar Ana Ekranı")
        self.switch_panel("firma_bilgileri")

    def init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Üst Başlık & Corner Bar
        top_header = self.build_top_header()
        main_layout.addWidget(top_header)

        # 2. Orta Bölüm: Sol Sidebar + Sağ Stack + Sağ Sidebar
        content_widget = QWidget()
        content_lyt = QHBoxLayout(content_widget)
        content_lyt.setContentsMargins(6, 6, 6, 6)
        content_lyt.setSpacing(6)

        left_sidebar = self.build_left_sidebar()
        content_lyt.addWidget(left_sidebar)

        body_stack = self.build_body()
        content_lyt.addWidget(body_stack, 1)

        right_sidebar = self.build_right_sidebar()
        content_lyt.addWidget(right_sidebar)

        main_layout.addWidget(content_widget, 1)

        # 3. Alt Bar
        bottom_bar = self.build_bottom_bar()
        main_layout.addWidget(bottom_bar)

    def build_top_header(self) -> QWidget:
        """Üst başlık ve breadcrumb barı oluşturur."""
        header = QFrame()
        header.setFixedHeight(38)
        header.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border-bottom: 1px solid #cbd5e1;
            }
        """)
        lyt = QHBoxLayout(header)
        lyt.setContentsMargins(12, 4, 12, 4)
        lyt.setSpacing(12)

        self.lbl_breadcrumb = QLabel("⚙️ [sys.set.001] Genel Ayarlar > Firma Bilgileri")
        self.lbl_breadcrumb.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #1e3a8a;",
        )
        lyt.addWidget(self.lbl_breadcrumb)
        lyt.addStretch()

        self.chk_layout_hints = QCheckBox(
            "🏷️ Bölüm İsim İpuçları (Layout Hints)",
        )
        self.chk_layout_hints.setStyleSheet(
            "font-weight: bold; color: #15803d; font-size: 11px;",
        )
        self.chk_layout_hints.setChecked(is_layout_hints_enabled())
        self.chk_layout_hints.toggled.connect(self.on_layout_hints_toggled)
        lyt.addWidget(self.chk_layout_hints)

        self.chk_global_text_select = QCheckBox("🔍 Metinleri Seçilebilir Yap")
        self.chk_global_text_select.setStyleSheet(
            "font-weight: bold; color: #1e3a8a; font-size: 11px;",
        )
        self.chk_global_text_select.setChecked(is_global_text_selection_enabled())
        self.chk_global_text_select.toggled.connect(self.on_text_selection_toggled)
        lyt.addWidget(self.chk_global_text_select)

        return header

    def on_layout_hints_toggled(self, checked: bool) -> None:
        set_layout_hints_enabled(checked)

    def on_text_selection_toggled(self, checked: bool) -> None:
        set_global_text_selection_enabled(checked)

    def build_left_sidebar(self) -> QWidget:
        """Sol sidebar — Arama, daraltılmış menü grupları ve tıklandığında açılan alt eylemler."""
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)

        container = QWidget()
        container_lyt = QVBoxLayout(container)
        container_lyt.setContentsMargins(4, 4, 4, 4)
        container_lyt.setSpacing(6)

        # 1. Başlık & Arama Çubuğu
        header_title = QLabel("⚙️ AYARLAR MENÜSÜ")
        header_title.setStyleSheet("font-weight: 800; font-size: 11px; color: #1e3a8a; padding-left: 2px;")
        container_lyt.addWidget(header_title)

        self.menu_search_input = QLineEdit()
        self.menu_search_input.setPlaceholderText("🔍 Menü veya işlem ara...")
        self.menu_search_input.setClearButtonEnabled(True)
        self.menu_search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
                background-color: white;
                color: #0f172a;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.menu_search_input.textChanged.connect(self.filter_menu_tree)
        container_lyt.addWidget(self.menu_search_input)

        # 2. Menü Kaydırma Alanı
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        scroll.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        scroll.customContextMenuRequested.connect(self.show_sidebar_context_menu)

        frame = QFrame()
        frame.setStyleSheet("background:transparent; border:none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(2, 2, 2, 2)
        lyt.setSpacing(6)

        self.menu_sections = []
        self.menu_item_containers = {}
        self.menu_sub_boxes = {}

        # Menü Grupları (Tümü varsayılan KAPALI gelir)
        for grup_adi, ikon, menuler in self.MENU_STRUCTURE:
            sec = CollapsibleSection(f"{ikon} {grup_adi}", is_expanded=False)
            self.menu_sections.append(sec)

            for menu_adi, panel_id in menuler:
                item_widget = QWidget()
                item_lyt = QVBoxLayout(item_widget)
                item_lyt.setContentsMargins(0, 0, 0, 0)
                item_lyt.setSpacing(2)

                btn = QPushButton(f"  {menu_adi}")
                btn.setStyleSheet(self.menu_btn_style())
                btn.setCheckable(True)
                btn.clicked.connect(
                    lambda _, pid=panel_id, b=btn: self.on_menu_clicked(pid, b),
                )
                self.menu_buttons[panel_id] = btn
                item_lyt.addWidget(btn)

                # Alt Eylemler Kutusu (Sub-Action Container)
                sub_box = self._build_sub_action_box(panel_id)
                sub_box.hide()
                self.menu_sub_boxes[panel_id] = sub_box
                item_lyt.addWidget(sub_box)

                self.menu_item_containers[panel_id] = (item_widget, sec, menu_adi, grup_adi)
                sec.add_widget(item_widget)

            lyt.addWidget(sec)

        lyt.addStretch()
        scroll.setWidget(frame)
        container_lyt.addWidget(scroll, 1)

        self.left_panel.set_content(container)
        return self.left_panel

    def _build_sub_action_box(self, panel_id: str) -> QFrame:
        """Menünün hemen altında açılan alt eylem butonlarını oluşturur."""
        box = QFrame()
        box.setStyleSheet("""
            QFrame {
                background-color: #f1f5f9;
                border-left: 2px solid #3b82f6;
                border-radius: 0px 4px 4px 0px;
                margin-left: 8px;
                margin-top: 2px;
                margin-bottom: 4px;
            }
        """)
        lyt = QVBoxLayout(box)
        lyt.setContentsMargins(6, 4, 4, 4)
        lyt.setSpacing(3)

        # Tanımlara özel hızlı alt eylemler
        actions_map = {
            "firma_bilgileri": [
                ("➕ Yeni Firma", lambda: getattr(self, "firma_tab", None) and self.firma_tab.add_new()),
                ("✏️ Düzenle", lambda: getattr(self, "firma_tab", None) and self.firma_tab.edit_selected()),
                ("🗑️ Sil", lambda: getattr(self, "firma_tab", None) and self.firma_tab.delete_selected()),
                ("🔄 Yenile", lambda: getattr(self, "firma_tab", None) and self.firma_tab.load_data()),
            ],
            "cms_baglantilari": [
                ("➕ Yeni Bağlantı", lambda: getattr(self, "sites_tab", None) and self.sites_tab.open_add_site_dialog()),
                ("✏️ Değiştir", lambda: getattr(self, "sites_tab", None) and self.sites_tab.open_edit_site_dialog()),
                ("🔍 İncele", lambda: getattr(self, "sites_tab", None) and self.sites_tab.inspect_site_dialog()),
                ("🗑️ Sil", lambda: getattr(self, "sites_tab", None) and self.sites_tab.delete_site()),
                ("🔌 Bağlantıyı Test Et", lambda: getattr(self, "sites_tab", None) and self.sites_tab.test_selected_connection()),
                ("🔑 Jeton Çek", lambda: getattr(self, "sites_tab", None) and self.sites_tab.auto_fetch_token_selected()),
                ("🔄 Yenile", lambda: getattr(self, "sites_tab", None) and self.sites_tab.load_sites()),
            ],
            "sube_tanimlari": [
                ("➕ Yeni Şube Ekle", lambda: self._add_table_row(getattr(self, "tbl_sube", None), ["", "", "Toya ERP A.Ş.", "", "Aktif"])),
                ("🗑️ Seçili Şubeyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_sube", None))),
                ("💾 Şubeleri Kaydet", lambda: self.save_current_panel()),
            ],
            "kullanicilar": [
                ("➕ Yeni Kullanıcı", lambda: getattr(self, "users_tab", None) and self.users_tab.add_new()),
                ("✏️ Düzenle", lambda: getattr(self, "users_tab", None) and self.users_tab.edit_selected()),
                ("🗑️ Sil", lambda: getattr(self, "users_tab", None) and self.users_tab.delete_selected()),
                ("🔄 Yenile", lambda: getattr(self, "users_tab", None) and self.users_tab.load_data()),
            ],
            "roller": [
                ("➕ Yeni Rol", lambda: getattr(self, "roller_tab", None) and self.roller_tab.add_new()),
                ("✏️ Düzenle", lambda: getattr(self, "roller_tab", None) and self.roller_tab.edit_selected()),
                ("🗑️ Sil", lambda: getattr(self, "roller_tab", None) and self.roller_tab.delete_selected()),
                ("🔄 Yenile", lambda: getattr(self, "roller_tab", None) and self.roller_tab.load_data()),
            ],
            "yetkiler": [
                ("🔄 Yenile", lambda: self.switch_panel("yetkiler")),
            ],
            "doviz_kur": [
                ("➕ Yeni Döviz Ekle", lambda: self._add_table_row(getattr(self, "tbl_doviz", None), ["", "", "", "1.0000", "Aktif"])),
                ("🔄 TCMB Kurları Çek", lambda: self._fetch_tcmb_rates()),
                ("🗑️ Seçili Dövizi Sil", lambda: self._delete_table_row(getattr(self, "tbl_doviz", None))),
                ("💾 Kurları Kaydet", lambda: self.save_current_panel()),
            ],
            "odeme_planlari": [
                ("➕ Yeni Plan Ekle", lambda: self._add_table_row(getattr(self, "tbl_odeme", None), ["", "", "0", "Açık Hesap", "Aktif"])),
                ("🗑️ Seçili Planı Sil", lambda: self._delete_table_row(getattr(self, "tbl_odeme", None))),
                ("💾 Planları Kaydet", lambda: self.save_current_panel()),
            ],
            "fiyat_listeleri": [
                ("➕ Yeni Liste Ekle", lambda: self._add_table_row(getattr(self, "tbl_fiyat", None), ["", "", "Satış", "TRY", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_fiyat", None))),
                ("💾 Listeleri Kaydet", lambda: self.save_current_panel()),
            ],
            "stok_kategoriler": [
                ("➕ Yeni Kategori", lambda: self._add_table_row(getattr(self, "tbl_stok_kategori", None), ["", "", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_stok_kategori", None))),
                ("💾 Kaydet", lambda: self.save_current_panel()),
            ],
            "stok_markalar": [
                ("➕ Yeni Marka", lambda: self._add_table_row(getattr(self, "tbl_stok_marka", None), ["", "", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_stok_marka", None))),
                ("💾 Kaydet", lambda: self.save_current_panel()),
            ],
            "birim_tanimlari": [
                ("➕ Yeni Birim", lambda: self._add_table_row(getattr(self, "tbl_birim", None), ["", "", "1", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_birim", None))),
                ("💾 Kaydet", lambda: self.save_current_panel()),
            ],
            "depo_tanimlari": [
                ("➕ Yeni Depo", lambda: self._add_table_row(getattr(self, "tbl_depo", None), ["", "", "Merkez", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_depo", None))),
                ("💾 Kaydet", lambda: self.save_current_panel()),
            ],
            "stok_ozel_alanlar": [
                ("💾 Alanları Kaydet", lambda: self.save_current_panel()),
                ("🔄 Yenile", lambda: self._load_ozel_alanlar("stok")),
            ],
            "cari_gruplari": [
                ("➕ Yeni Grup Ekle", lambda: self._add_table_row(getattr(self, "tbl_cari_grup", None), ["", "", "0.00", "0", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_cari_grup", None))),
                ("💾 Kaydet", lambda: self.save_current_panel()),
            ],
            "cari_ozel_alanlar": [
                ("💾 Alanları Kaydet", lambda: self.save_current_panel()),
                ("🔄 Yenile", lambda: self._load_ozel_alanlar("cari")),
            ],
            "gorunum_profilleri": [
                ("⭐ Aktif Yap", lambda: getattr(self, "view_settings_tab", None) and self.view_settings_tab.set_selected_as_active()),
                ("🗑️ Profili Sil", lambda: getattr(self, "view_settings_tab", None) and self.view_settings_tab.delete_selected_profile()),
                ("🔄 Yenile", lambda: getattr(self, "view_settings_tab", None) and self.view_settings_tab.load_profiles()),
                ("💥 Tümünü Sıfırla", lambda: getattr(self, "view_settings_tab", None) and self.view_settings_tab.reset_all_profiles()),
            ],
            "ekran_grid": [
                ("📐 Şablonları Yenile", lambda: getattr(self, "screen_defs_tab", None) and self.screen_defs_tab.load_screen_definitions()),
            ],
            "surum_git": [
                ("🔄 Git Durumunu Yenile", lambda: getattr(self, "git_tracker_tab", None) and self.git_tracker_tab.refresh_all()),
            ],
        }

        items = actions_map.get(panel_id, [
            ("💾 Kaydet", lambda: self.save_current_panel()),
            ("➕ Yeni Ekle", lambda: self.new_current_panel()),
            ("❌ Sil", lambda: self.delete_current_panel()),
        ])

        for label, callback in items:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #334155;
                    border: none;
                    text-align: left;
                    padding: 3px 6px;
                    font-size: 10px;
                    font-weight: 600;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                    color: #1d4ed8;
                }
            """)
            btn.clicked.connect(callback)
            lyt.addWidget(btn)

        return box

    def show_sidebar_context_menu(self, pos):
        """Sol sidebar üzerinde sağ tıklandığında menü açar."""
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu

        from src.desktop.managers.theme_manager import ThemeManager

        menu = QMenu(self)
        try:
            menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())
        except Exception:
            pass

        act_expand = QAction("📂 Tüm Menüleri Aç (Genişlet)", self)
        act_expand.triggered.connect(self.expand_all_sections)
        menu.addAction(act_expand)

        act_collapse = QAction("📁 Tüm Menüleri Kapat (Daralt)", self)
        act_collapse.triggered.connect(self.collapse_all_sections)
        menu.addAction(act_collapse)

        menu.addSeparator()
        act_search = QAction("🔍 Menü Aramasına Git", self)
        act_search.triggered.connect(lambda: self.menu_search_input.setFocus())
        menu.addAction(act_search)

        menu.exec(self.left_panel.mapToGlobal(pos))

    def expand_all_sections(self):
        for sec in self.menu_sections:
            sec.set_expanded(True)

    def collapse_all_sections(self):
        for sec in self.menu_sections:
            sec.set_expanded(False)

    def filter_menu_tree(self, query: str):
        """Menü arama kutusuna göre menü ağacını filtreler."""
        q = query.strip().lower()
        if not q:
            for item_widget, _sec, _, _ in self.menu_item_containers.values():
                item_widget.show()
            self.collapse_all_sections()
            if self.active_panel_id in self.menu_item_containers:
                _, sec, _, _ = self.menu_item_containers[self.active_panel_id]
                sec.set_expanded(True)
            return

        for _panel_id, (item_widget, sec, menu_adi, grup_adi) in self.menu_item_containers.items():
            matches = (q in menu_adi.lower()) or (q in grup_adi.lower())
            item_widget.setVisible(matches)
            if matches:
                sec.set_expanded(True)

    def on_menu_clicked(self, panel_id: str, btn: QPushButton) -> None:
        """Menü butonuna tıklanınca panel değiştir ve alt eylemleri aç."""
        for b in self.menu_buttons.values():
            b.setChecked(False)
            b.setStyleSheet(self.menu_btn_style(active=False))
        btn.setChecked(True)
        btn.setStyleSheet(self.menu_btn_style(active=True))

        # Alt eylemler kutusunu aç ve diğerlerini kapat
        for pid, sub_box in self.menu_sub_boxes.items():
            if pid == panel_id:
                sub_box.show()
            else:
                sub_box.hide()

        # Ait olduğu grubu genişlet
        if panel_id in self.menu_item_containers:
            _, sec, _, _ = self.menu_item_containers[panel_id]
            sec.set_expanded(True)

        self.switch_panel(panel_id)

    def btn_style(self, bg="#ffffff", fg="#1e293b") -> str:
        return f"""
            QPushButton {{
                background:{bg}; color:{fg};
                border:1px solid #cbd5e1; border-radius:4px;
                padding:5px 8px; font-size:11px; font-weight:600;
                text-align:left; min-height:24px;
            }}
            QPushButton:hover {{ background:#f1f5f9; }}
        """

    def menu_btn_style(self, active: bool = False) -> str:
        if active:
            return """
                QPushButton {
                    background:#eff6ff; color:#1d4ed8;
                    border:none; border-left:3px solid #2563eb;
                    padding:5px 8px; font-size:11px; font-weight:700;
                    text-align:left; min-height:22px;
                }
            """
        return """
            QPushButton {
                background:transparent; color:#475569;
                border:none; border-left:3px solid transparent;
                padding:5px 8px; font-size:11px;
                text-align:left; min-height:22px;
            }
            QPushButton:hover {
                background:#f8fafc; color:#1e293b; font-weight:600;
            }
        """

    def build_right_sidebar(self) -> QWidget:
        """Sağ sidebar — Filtreleme, Yazdırma, PDF/Excel aktarımları ve Hızlı İşlemler."""
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border:none; background:transparent; }")

        frame = QFrame()
        frame.setStyleSheet("background:transparent; border:none;")
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(4, 4, 4, 4)
        lyt.setSpacing(10)

        # ── 1. FİLTRELEME & ARAMA ──
        sec_filter = CollapsibleSection("🔍 FİLTRELEME & ARAMA", is_expanded=True)

        lbl_s = QLabel("Tablo İçi Canlı Arama:")
        lbl_s.setStyleSheet("font-size:10px; font-weight:bold; color:#475569;")
        self.txt_right_filter = QLineEdit()
        self.txt_right_filter.setPlaceholderText("Aktif tabloda ara...")
        self.txt_right_filter.setClearButtonEnabled(True)
        self.txt_right_filter.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px; background: white; font-size: 11px;")
        self.txt_right_filter.textChanged.connect(self.filter_active_table)
        sec_filter.add_widget(lbl_s)
        sec_filter.add_widget(self.txt_right_filter)

        lbl_st = QLabel("Durum:")
        lbl_st.setStyleSheet("font-size:10px; font-weight:bold; color:#475569;")
        self.cmb_right_status = QComboBox()
        self.cmb_right_status.addItems(["Tümü", "Aktif", "Pasif"])
        self.cmb_right_status.setStyleSheet("border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px; background: white; font-size: 11px;")
        self.cmb_right_status.currentTextChanged.connect(self.filter_active_table_status)
        sec_filter.add_widget(lbl_st)
        sec_filter.add_widget(self.cmb_right_status)
        lyt.addWidget(sec_filter)

        # ── 2. YAZDIR & DIŞA/İÇE AKTAR ──
        sec_export = CollapsibleSection("🖨️ YAZDIR & AKTAR", is_expanded=True)

        btn_print = QPushButton("🖨️ Yazdır / Önizleme")
        btn_print.setStyleSheet(self.btn_style("#ffffff", "#0f172a"))
        btn_print.clicked.connect(self.print_active_panel)

        btn_pdf = QPushButton("📄 PDF Olarak Kaydet")
        btn_pdf.setStyleSheet(self.btn_style("#ffffff", "#0f172a"))
        btn_pdf.clicked.connect(self.export_active_to_pdf)

        btn_excel_export = QPushButton("📊 Excel'e Aktar (.xlsx)")
        btn_excel_export.setStyleSheet(self.btn_style("#f0fdf4", "#166534"))
        btn_excel_export.clicked.connect(self.export_active_to_excel)

        btn_excel_import = QPushButton("📥 Excel'den Al (.xlsx)")
        btn_excel_import.setStyleSheet(self.btn_style("#f0fdf4", "#166534"))
        btn_excel_import.clicked.connect(self.import_active_from_excel)

        sec_export.add_widget(btn_print)
        sec_export.add_widget(btn_pdf)
        sec_export.add_widget(btn_excel_export)
        sec_export.add_widget(btn_excel_import)
        lyt.addWidget(sec_export)

        # ── 3. HIZLI İŞLEMLER & GÖRÜNÜM ──
        sec_tools = CollapsibleSection("⚡ HIZLI İŞLEMLER", is_expanded=True)

        btn_refresh = QPushButton("🔄 Verileri Yenile (F5)")
        btn_refresh.setStyleSheet(self.btn_style())
        btn_refresh.clicked.connect(self.refresh_active_panel)

        # NOT: "Değişiklikleri Kaydet" burada YOK — Kaydet tek yerde (alt bar +
        # sol menü bağlam eylemi). Sağ sidebarda tekrar etmesi F2'yi çiftliyordu.

        btn_col_dia = QPushButton("⚙️ Sütunları Yapılandır")
        btn_col_dia.setStyleSheet(self.btn_style("#ffffff", "#475569"))
        btn_col_dia.clicked.connect(self.open_active_column_manager)

        sec_tools.add_widget(btn_refresh)
        sec_tools.add_widget(btn_col_dia)
        lyt.addWidget(sec_tools)

        lyt.addStretch()
        scroll.setWidget(frame)
        self.right_panel.set_content(scroll)
        return self.right_panel

    def _get_active_table(self):
        """Mevcut aktif paneldeki tablo bileşenini döner."""
        if self.active_panel_id == "firma_bilgileri":
            if hasattr(self, "firma_tab"):
                return getattr(self.firma_tab, "table_view", None)
        elif self.active_panel_id == "cms_baglantilari":
            if hasattr(self, "sites_tab") and hasattr(self.sites_tab, "table"):
                return self.sites_tab.table
        elif self.active_panel_id in ("kullanicilar", "users"):
            if hasattr(self, "users_tab"):
                return getattr(self.users_tab, "table_view", None)
        elif self.active_panel_id == "roller":
            if hasattr(self, "roller_tab"):
                return getattr(self.roller_tab, "table_view", None)
        elif self.active_panel_id in ("gorunum_profilleri", "view_settings"):
            if hasattr(self, "view_settings_tab") and hasattr(self.view_settings_tab, "table"):
                return self.view_settings_tab.table
        elif self.active_panel_id == "sube_tanimlari":
            return getattr(self, "tbl_sube", None)
        elif self.active_panel_id == "yetkiler":
            return getattr(self, "tbl_yetkiler", None)
        elif self.active_panel_id == "doviz_kur":
            return getattr(self, "tbl_doviz", None)
        elif self.active_panel_id == "odeme_planlari":
            return getattr(self, "tbl_odeme", None)
        elif self.active_panel_id == "fiyat_listeleri":
            return getattr(self, "tbl_fiyat", None)
        elif self.active_panel_id == "stok_kategoriler":
            return getattr(self, "tbl_stok_kategori", None)
        elif self.active_panel_id == "stok_markalar":
            return getattr(self, "tbl_stok_marka", None)
        elif self.active_panel_id == "birim_tanimlari":
            return getattr(self, "tbl_birim", None)
        elif self.active_panel_id == "depo_tanimlari":
            return getattr(self, "tbl_depo", None)
        elif self.active_panel_id == "cari_gruplari":
            return getattr(self, "tbl_cari_grup", None)
        return None

    def _add_table_row(self, table: QTableWidget | None, default_vals: list[str]):
        """Belirtilen QTableWidget tablosuna yeni bir satır ekler."""
        if not table:
            return
        r = table.rowCount()
        table.insertRow(r)
        for c, val in enumerate(default_vals):
            table.setItem(r, c, QTableWidgetItem(val))
        table.selectRow(r)

    def _delete_table_row(self, table: QTableWidget | None):
        """Belirtilen QTableWidget tablosundan seçili satırı siler."""
        if not table:
            return
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)
        else:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Lütfen silmek istediğiniz satırı seçin."))

    def _active_embedded_widget(self):
        """Aktif panel gömülü bir yönetim widget'ıysa onu döndürür."""
        m = {
            "firma_bilgileri": "firma_tab",
            "cms_baglantilari": "sites_tab",
            "kullanicilar": "users_tab",
            "roller": "roller_tab",
            "gorunum_profilleri": "view_settings_tab",
            "ekran_grid": "screen_defs_tab",
        }
        attr = m.get(self.active_panel_id)
        return getattr(self, attr, None) if attr else None

    def filter_active_table(self, query: str):
        """Aktif tablodaki satırları arama metnine göre filtreler."""
        emb = self._active_embedded_widget()
        if emb is not None and hasattr(emb, "apply_quick_search"):
            emb.apply_quick_search(query)
            return
        table = self._get_active_table()
        if not table or not isinstance(table, QTableWidget):
            return
        q = query.strip().lower()
        for r in range(table.rowCount()):
            match = False
            for c in range(table.columnCount()):
                it = table.item(r, c)
                if it and q in it.text().lower():
                    match = True
                    break
            table.setRowHidden(r, not match if q else False)

    def filter_active_table_status(self, status: str):
        """Aktif tablodaki satırları durum değerine göre filtreler."""
        emb = self._active_embedded_widget()
        if emb is not None and hasattr(emb, "apply_status_filter"):
            emb.apply_status_filter(status)
            return
        table = self._get_active_table()
        if not table or not isinstance(table, QTableWidget):
            return
        status = status.strip().lower()
        for r in range(table.rowCount()):
            if status == "tümü":
                table.setRowHidden(r, False)
                continue
            last_col = table.columnCount() - 1
            it = table.item(r, last_col)
            if it:
                row_status = it.text().strip().lower()
                table.setRowHidden(r, status not in row_status)

    def export_active_to_excel(self):
        """Aktif paneldeki verileri Excel (.xlsx) veya CSV dosyasına aktarır."""
        table = self._get_active_table()
        if not table:
            QMessageBox.information(self, self.tr("Bilgi"), self.tr("Bu panel için dışa aktarılacak tablo verisi bulunamadı."))
            return

        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Excel Olarak Dışa Aktar"),
            f"{self.active_panel_id or 'ayarlar'}_disa_aktarim.xlsx",
            "Excel Dosyası (*.xlsx);;CSV Dosyası (*.csv)",
        )
        if not path:
            return

        try:
            import pandas as pd

            headers = []
            if isinstance(table, QTableWidget):
                for c in range(table.columnCount()):
                    h = table.horizontalHeaderItem(c)
                    headers.append(h.text() if h else f"Sütun {c+1}")
                rows = []
                for r in range(table.rowCount()):
                    if table.isRowHidden(r):
                        continue
                    row_vals = []
                    for c in range(table.columnCount()):
                        item = table.item(r, c)
                        row_vals.append(item.text() if item else "")
                    rows.append(row_vals)
            else:
                model = table.model()
                if not model:
                    return
                for c in range(model.columnCount()):
                    headers.append(str(model.headerData(c, Qt.Orientation.Horizontal) or f"Sütun {c+1}"))
                rows = []
                for r in range(model.rowCount()):
                    if table.isRowHidden(r):
                        continue
                    row_vals = []
                    for c in range(model.columnCount()):
                        idx = model.index(r, c)
                        row_vals.append(str(model.data(idx) or ""))
                    rows.append(row_vals)

            df = pd.DataFrame(rows, columns=headers)
            if path.endswith(".csv"):
                df.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                df.to_excel(path, index=False)

            QMessageBox.information(self, self.tr("Başarılı"), self.tr(f"Veriler başarıyla dışa aktarıldı:\n{path}"))
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), self.tr(f"Dışa aktarma sırasında hata oluştu:\n{e}"))

    def import_active_from_excel(self):
        """Excel (.xlsx veya .csv) dosyasından aktif tabloya veri aktarır."""
        table = self._get_active_table()
        if not table or not isinstance(table, QTableWidget):
            QMessageBox.information(self, self.tr("Bilgi"), self.tr("Bu panel için Excel'den doğrudan veri alma desteklenmemektedir."))
            return

        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Excel'den Veri Al"),
            "",
            "Excel / CSV Dosyaları (*.xlsx *.xls *.csv)",
        )
        if not path:
            return

        try:
            import pandas as pd
            if path.endswith(".csv"):
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)

            df = df.fillna("")
            imported_count = 0
            for _, row in df.iterrows():
                r = table.rowCount()
                table.insertRow(r)
                for c in range(min(len(row), table.columnCount())):
                    table.setItem(r, c, QTableWidgetItem(str(row.iloc[c])))
                imported_count += 1

            QMessageBox.information(
                self,
                self.tr("Başarılı"),
                self.tr(f"{imported_count} adet kayıt başarıyla aktarıldı.\nDeğişiklikleri kalıcı yapmak için 'Kaydet' butonuna basınız."),
            )
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), self.tr(f"Excel'den aktarım başarısız:\n{e}"))

    def export_active_to_pdf(self):
        """Aktif panel verilerini PDF olarak kaydeder."""
        table = self._get_active_table()
        if not table:
            QMessageBox.information(self, self.tr("Bilgi"), self.tr("Bu panel için yazdırılacak veri bulunamadı."))
            return

        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("PDF Olarak Kaydet"),
            f"{self.active_panel_id or 'ayarlar'}_rapor.pdf",
            "PDF Dosyası (*.pdf)",
        )
        if not path:
            return

        try:
            html = self._generate_table_html(table, f"TOYA ERP — {self.lbl_breadcrumb.text()}")
            doc = QTextDocument()
            doc.setHtml(html)

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)
            doc.print(printer)

            QMessageBox.information(self, self.tr("Başarılı"), self.tr(f"PDF raporu oluşturuldu:\n{path}"))
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), self.tr(f"PDF oluşturulamadı:\n{e}"))

    def print_active_panel(self):
        """Aktif panel verilerini yazdırma önizleme diyaloğu ile açar."""
        table = self._get_active_table()
        if not table:
            QMessageBox.information(self, self.tr("Bilgi"), self.tr("Bu panel için yazdırılacak veri bulunamadı."))
            return

        try:
            from PyQt6.QtGui import QTextDocument
            from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog

            html = self._generate_table_html(table, f"TOYA ERP — {self.lbl_breadcrumb.text()}")
            doc = QTextDocument()
            doc.setHtml(html)

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            preview = QPrintPreviewDialog(printer, self)
            preview.setWindowTitle(self.tr("Yazdırma Önizleme"))
            preview.paintRequested.connect(lambda p: doc.print(p))
            preview.exec()
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), self.tr(f"Yazdırma hatası:\n{e}"))

    def _generate_table_html(self, table, title: str) -> str:
        """Tablodan şık bir kurumsal HTML rapor tablosu üretir."""
        headers = []
        rows = []
        if isinstance(table, QTableWidget):
            for c in range(table.columnCount()):
                h = table.horizontalHeaderItem(c)
                headers.append(h.text() if h else f"Sütun {c+1}")
            for r in range(table.rowCount()):
                if table.isRowHidden(r):
                    continue
                row_vals = []
                for c in range(table.columnCount()):
                    item = table.item(r, c)
                    row_vals.append(item.text() if item else "")
                rows.append(row_vals)
        else:
            model = table.model()
            if model:
                for c in range(model.columnCount()):
                    headers.append(str(model.headerData(c, Qt.Orientation.Horizontal) or f"Sütun {c+1}"))
                for r in range(model.rowCount()):
                    if table.isRowHidden(r):
                        continue
                    row_vals = []
                    for c in range(model.columnCount()):
                        idx = model.index(r, c)
                        row_vals.append(str(model.data(idx) or ""))
                    rows.append(row_vals)

        th_html = "".join(f"<th style='border:1px solid #cbd5e1; padding:6px 8px; background:#f1f5f9; color:#1e3a8a;'>{h}</th>" for h in headers)
        tr_html = ""
        for i, row in enumerate(rows):
            bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            tds = "".join(f"<td style='border:1px solid #e2e8f0; padding:5px 8px;'>{val}</td>" for val in row)
            tr_html += f"<tr style='background:{bg};'>{tds}</tr>"

        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; color: #334155; }}
                h2 {{ color: #1e3a8a; margin-bottom: 4px; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
            </style>
        </head>
        <body>
            <h2>{title}</h2>
            <hr style='border:none; border-top:1px solid #cbd5e1; margin-bottom:12px;' />
            <table>
                <thead><tr>{th_html}</tr></thead>
                <tbody>{tr_html}</tbody>
            </table>
        </body>
        </html>
        """

    def open_active_column_manager(self):
        """Aktif tablonun sütun yapılandırma diyaloğunu açar."""
        emb = self._active_embedded_widget()
        if emb is not None and hasattr(emb, "filterable_table"):
            emb.filterable_table.open_column_manager_dialog()
        else:
            QMessageBox.information(self, self.tr("Bilgi"), self.tr("Bu tablo için standart sütun yönetimi kullanılmaktadır."))

    def refresh_active_panel(self):
        """Aktif paneli yeniden yükler."""
        self.switch_panel(self.active_panel_id or "firma_bilgileri")

    def _fetch_tcmb_rates(self):
        """TCMB güncel kurlarını çeker (Mock / Simülasyon)."""
        QMessageBox.information(self, self.tr("TCMB"), self.tr("TCMB güncel döviz kurları başarıyla güncellendi."))

    def build_body(self) -> QStackedWidget:
        """Sağ body — paneller burada gösterilir."""
        self.stack = QStackedWidget()

        panel_builders = {
            "firma_bilgileri": self.build_firma_bilgileri_panel,
            "cms_baglantilari": self.build_cms_baglantilari_panel,
            "sube_tanimlari": self.build_sube_panel,
            "kullanicilar": self.build_kullanicilar_panel,
            "roller": self.build_roller_panel,
            "yetkiler": self.build_yetkiler_panel,
            "doviz_kur": self.build_doviz_panel,
            "odeme_planlari": self.build_odeme_planlari_panel,
            "fiyat_listeleri": self.build_fiyat_listeleri_panel,
            "stok_kategoriler": self.build_stok_kategoriler_panel,
            "stok_markalar": self.build_stok_markalar_panel,
            "birim_tanimlari": self.build_birim_panel,
            "depo_tanimlari": self.build_depo_panel,
            "stok_ozel_alanlar": lambda: self.build_ozel_alan_panel("stok"),
            "cari_gruplari": self.build_cari_gruplari_panel,
            "cari_ozel_alanlar": lambda: self.build_ozel_alan_panel("cari"),
            "gorunum_profilleri": self.build_gorunum_panel,
            "ekran_grid": self.build_ekran_grid_panel,
            "surum_git": self.build_surum_panel,
        }

        for panel_id, builder in panel_builders.items():
            panel = builder()
            self.panels[panel_id] = panel
            self.stack.addWidget(panel)

        return self.stack

    def switch_panel(self, panel_id: str) -> None:
        """Aktif paneli değiştirir."""
        self.active_panel_id = panel_id
        if panel_id in self.panels:
            self.stack.setCurrentWidget(self.panels[panel_id])

        # Buton aktifliğini ayarla
        if panel_id in self.menu_buttons:
            for pid, b in self.menu_buttons.items():
                is_cur = pid == panel_id
                b.setChecked(is_cur)
                b.setStyleSheet(self.menu_btn_style(active=is_cur))

        # Alt eylemler kutularını güncelle
        if hasattr(self, "menu_sub_boxes"):
            for pid, sub_box in self.menu_sub_boxes.items():
                if pid == panel_id:
                    sub_box.show()
                else:
                    sub_box.hide()

        # Başlığı güncelle
        menu_name = next(
            (
                m
                for _, _, ml in self.MENU_STRUCTURE
                for m, pid in ml
                if pid == panel_id
            ),
            panel_id,
        )
        if hasattr(self, "lbl_breadcrumb"):
            self.lbl_breadcrumb.setText(
                f"⚙️ [sys.set.001] Genel Ayarlar > {menu_name}",
            )

        self._update_bottom_count()

    def build_bottom_bar(self) -> QFrame:
        """Alt sabit aksiyon barı."""
        bar = QFrame()
        bar.setFixedHeight(42)
        bar.setStyleSheet("""
            QFrame {
                background:#f8fafc;
                border-top:1px solid #cbd5e1;
            }
        """)
        lyt = QHBoxLayout(bar)
        lyt.setContentsMargins(12, 4, 12, 4)
        lyt.setSpacing(8)

        lbl = QLabel("💡 <b>F2:</b> Kaydet | <b>Del:</b> Sil | <b>Esc:</b> Kapat")
        lbl.setStyleSheet("color:#64748b; font-size:11px;")

        self.lbl_bottom_count = QLabel("")
        self.lbl_bottom_count.setStyleSheet(
            "color:#1e3a8a; font-size:11px; font-weight:700; padding-left:14px;",
        )

        btn_cancel = QPushButton("↩️ Vazgeç")
        btn_cancel.setFixedHeight(28)
        btn_cancel.setStyleSheet(self.btn_style("#fee2e2", "#991b1b"))
        btn_cancel.clicked.connect(self.cancel_current_panel)

        btn_save = QPushButton("💾 KAYDET (F2)")
        btn_save.setShortcut("F2")
        btn_save.setFixedHeight(28)
        btn_save.setStyleSheet(self.btn_style("#2563eb", "#ffffff"))
        btn_save.clicked.connect(self.save_current_panel)

        lyt.addWidget(lbl)
        lyt.addWidget(self.lbl_bottom_count)
        lyt.addStretch()
        lyt.addWidget(btn_cancel)
        lyt.addWidget(btn_save)
        return bar

    def _update_bottom_count(self) -> None:
        """Alt bardaki kayıt sayacını aktif panele göre günceller (tek yer)."""
        if not hasattr(self, "lbl_bottom_count"):
            return
        emb = self._active_embedded_widget()
        n = None
        if emb is not None and hasattr(emb, "record_count"):
            n = emb.record_count()
        else:
            t = self._get_active_table()
            if isinstance(t, QTableWidget):
                n = t.rowCount()
        self.lbl_bottom_count.setText(f"📊 {n} kayıt" if n is not None else "")

    def _setup_table_style(self, table: QTableWidget) -> None:
        """Tablolara TOYA kurumsal görünüm stili uygular."""
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        table.verticalHeader().setDefaultSectionSize(28)
        table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #cbd5e1;
                background-color: white;
                gridline-color: #f1f5f9;
                border-radius: 6px;
                font-size: 12px;
                color: #334155;
                alternate-background-color: #f8fafc;
            }
            QTableWidget::item { padding: 4px 8px; }
            QTableWidget::item:selected {
                background-color: #eff6ff;
                color: #1d4ed8;
                font-weight: 600;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #475569;
                padding: 6px 8px;
                border: none;
                border-right: 1px solid #cbd5e1;
                border-bottom: 2px solid #cbd5e1;
                font-weight: bold;
                font-size: 11px;
            }
        """)

    # ─────────────────────────────────────────────────────────────
    # PANEL BUILDERS
    # ─────────────────────────────────────────────────────────────

    def build_firma_bilgileri_panel(self) -> QWidget:
        """Firma (Şirket) kimlik kartları listesi (kabuk içinde: yalnız içerik)."""
        from src.desktop.ui.screens.firma_list_widget import FirmaListWidget
        self.firma_tab = FirmaListWidget(self.db, embedded=True)
        return self.firma_tab

    def build_cms_baglantilari_panel(self) -> QWidget:
        """CMS / ERP dış bağlantı yönetimi (eski 'Firma Bilgileri' içeriği)."""
        self.sites_tab = SitesWidget(self.db, embedded=True)
        return self.sites_tab

    def build_sube_panel(self) -> QWidget:
        """Şube Tanımları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("🏢 Şube Tanımları")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel(
            "Firmanıza bağlı merkez, şube ve mağaza lokasyonlarını buradan yönetebilirsiniz.",
        )
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(lbl_info)

        self.tbl_sube = QTableWidget(0, 5)
        self.tbl_sube.setHorizontalHeaderLabels([
            "Şube Kodu", "Şube Adı", "İlgili Firma", "Yetkili", "Durum",
        ])
        self._setup_table_style(self.tbl_sube)
        self.tbl_sube.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )

        default_subeler = [
            ("01", "MERKEZ ŞUBE", "Toya ERP A.Ş.", "Ahmet Yılmaz", "Aktif"),
            ("02", "KADIKÖY ŞUBE", "Toya ERP A.Ş.", "Mehmet Demir", "Aktif"),
        ]
        self._load_generic_table(self.tbl_sube, "subeler", default_subeler)
        lyt.addWidget(self.tbl_sube, 1)
        return w

    def build_kullanicilar_panel(self) -> QWidget:
        """Kullanıcı tanımları listesi (kabuk içinde: yalnız içerik)."""
        from src.desktop.ui.screens.kullanici_list_widget import KullaniciListWidget
        self.users_tab = KullaniciListWidget(self.db, embedded=True)
        return self.users_tab

    def build_roller_panel(self) -> QWidget:
        """Rol (yetki rolü) tanımları listesi (kabuk içinde: yalnız içerik)."""
        from src.desktop.ui.screens.rol_list_widget import RolListWidget
        self.roller_tab = RolListWidget(self.db, embedded=True)
        return self.roller_tab

    def build_yetkiler_panel(self) -> QWidget:
        """Rol × yetki matrisi (salt görüntüleme; düzenleme rol editöründe)."""
        from src.desktop.security.permissions import PERMISSION_GROUPS, permission_label
        from src.desktop.services.role_service import RoleService

        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)
        lbl = QLabel("🛡️ Rol × Yetki Matrisi")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)
        info = QLabel("Her rolün hangi yetkilere sahip olduğunu gösterir. "
                      "Değişiklik için 'Rol Tanımları'ndaki rol editörünü kullanın.")
        info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(info)

        svc = RoleService(self.db)
        svc.seed_defaults()
        roles = svc.list_roles()
        role_perms = {r.name: set(svc.permissions_of(r)) for r in roles}

        codes = [f"{m}.{a}" for m, _mn, acts in PERMISSION_GROUPS for a, _an in acts]
        self.tbl_yetkiler = QTableWidget(len(codes), 1 + len(roles))
        self.tbl_yetkiler.setHorizontalHeaderLabels(["Yetki"] + [r.name for r in roles])
        self._setup_table_style(self.tbl_yetkiler)
        self.tbl_yetkiler.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch,
        )
        for row, code in enumerate(codes):
            self.tbl_yetkiler.setItem(row, 0, QTableWidgetItem(permission_label(code)))
            for col, r in enumerate(roles, start=1):
                has = "*" in role_perms[r.name] or code in role_perms[r.name]
                it = QTableWidgetItem("✔" if has else "—")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl_yetkiler.setItem(row, col, it)
        lyt.addWidget(self.tbl_yetkiler, 1)
        return w

    def build_doviz_panel(self) -> QWidget:
        """Döviz & Kur Tanımları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("💱 Döviz & Kur Tanımları")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel(
            "Tanımlanan para birimleri Teklif, Fatura ve Stok ekranlarında otomatik kullanılır.",
        )
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lbl_info.setWordWrap(True)
        lyt.addWidget(lbl_info)

        self.tbl_doviz = QTableWidget(0, 5)
        self.tbl_doviz.setHorizontalHeaderLabels([
            "Kod", "Açıklama", "Sembol", "Güncel Kur (TL)", "Durum",
        ])
        self._setup_table_style(self.tbl_doviz)
        self.tbl_doviz.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )

        default_currencies = [
            ("TRY", "Türk Lirası", "₺", "1.0000", "Aktif"),
            ("USD", "Amerikan Doları", "$", "38.5000", "Aktif"),
            ("EUR", "Euro", "€", "41.2000", "Aktif"),
            ("GBP", "İngiliz Sterlini", "£", "48.9000", "Aktif"),
        ]
        for row_data in default_currencies:
            r = self.tbl_doviz.rowCount()
            self.tbl_doviz.insertRow(r)
            for c, val in enumerate(row_data):
                self.tbl_doviz.setItem(r, c, QTableWidgetItem(val))

        lyt.addWidget(self.tbl_doviz, 1)
        self._load_doviz_from_db()
        return w

    def build_odeme_planlari_panel(self) -> QWidget:
        """Ödeme Planları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("💳 Ödeme Planı Tanımları")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel(
            "Teklif ve Fatura işlemlerinde kullanılan vade ve taksit planları.",
        )
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(lbl_info)

        self.tbl_odeme = QTableWidget(0, 5)
        self.tbl_odeme.setHorizontalHeaderLabels([
            "Kod", "Açıklama", "Gün", "Ödeme Tipi", "Durum",
        ])
        self._setup_table_style(self.tbl_odeme)
        self.tbl_odeme.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )

        default_planlar = [
            ("30GVD", "30 GÜN VADE", "30", "Açık Hesap", "Aktif"),
            ("45GVD", "45 GÜNLÜK VADE", "45", "Açık Hesap", "Aktif"),
            ("60GVD", "60 GÜNLÜK VADE", "60", "Açık Hesap", "Aktif"),
            ("60GUNKK", "60 GÜN KREDİ KARTI", "60", "Kredi Kartı", "Aktif"),
            ("AH", "AÇIK HESAP", "0", "Açık Hesap", "Aktif"),
            ("NAKIT", "NAKİT", "0", "Nakit", "Aktif"),
            ("CF3TAK", "CARDFINANS 3 TAKSİT", "90", "Taksit", "Aktif"),
        ]
        for row_data in default_planlar:
            r = self.tbl_odeme.rowCount()
            self.tbl_odeme.insertRow(r)
            for c, val in enumerate(row_data):
                self.tbl_odeme.setItem(r, c, QTableWidgetItem(val))

        lyt.addWidget(self.tbl_odeme, 1)
        self._load_odeme_planlari_from_db()
        return w

    def build_fiyat_listeleri_panel(self) -> QWidget:
        """Fiyat Listeleri Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("🏷️ Fiyat Listeleri")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel(
            "Toptan, perakende ve özel müşteri fiyat listesi tanımları.",
        )
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(lbl_info)

        self.tbl_fiyat = QTableWidget(0, 5)
        self.tbl_fiyat.setHorizontalHeaderLabels([
            "Liste Kodu", "Liste Adı", "Para Birimi", "KDV Durumu", "Durum",
        ])
        self._setup_table_style(self.tbl_fiyat)
        self.tbl_fiyat.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )

        default_fiyatlar = [
            ("PERAKENDE", "Perakende Satış Fiyatı", "TRY", "KDV Dahil", "Aktif"),
            ("TOPTAN", "Toptan Satış Fiyatı", "TRY", "KDV Hariç", "Aktif"),
            ("OZEL_BAYI", "Özel Bayi Fiyatı", "USD", "KDV Hariç", "Aktif"),
        ]
        self._load_generic_table(self.tbl_fiyat, "fiyat_listeleri", default_fiyatlar)
        lyt.addWidget(self.tbl_fiyat, 1)
        return w

    def build_stok_kategoriler_panel(self) -> QWidget:
        """Stok Kategorileri Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("📦 Stok Kategori Tanımları")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel("Ürün ve stok kartlarının hiyerarşik kategori ağacı.")
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(lbl_info)

        self.tbl_kategori = QTableWidget(0, 3)
        self.tbl_kategori.setHorizontalHeaderLabels([
            "Kategori Adı", "Üst Kategori", "Durum",
        ])
        self._setup_table_style(self.tbl_kategori)
        self.tbl_kategori.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch,
        )

        default_kategoriler = [
            ("Elektronik", "-", "Aktif"),
            ("Bilgisayar & Tablet", "Elektronik", "Aktif"),
            ("Yedek Parça & Sarf", "-", "Aktif"),
            ("Hizmet & Danışmanlık", "-", "Aktif"),
        ]
        for row_data in default_kategoriler:
            r = self.tbl_kategori.rowCount()
            self.tbl_kategori.insertRow(r)
            for c, val in enumerate(row_data):
                self.tbl_kategori.setItem(r, c, QTableWidgetItem(val))

        lyt.addWidget(self.tbl_kategori, 1)
        self._load_kategoriler_from_db()
        return w

    def build_stok_markalar_panel(self) -> QWidget:
        """Stok Markaları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("🏷️ Stok Marka Tanımları")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel("Stok kartlarında seçilecek marka ve üretici listesi.")
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(lbl_info)

        self.tbl_marka = QTableWidget(0, 4)
        self.tbl_marka.setHorizontalHeaderLabels([
            "Marka Kodu", "Marka Adı", "Ülke / Üretici", "Durum",
        ])
        self._setup_table_style(self.tbl_marka)
        self.tbl_marka.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )

        default_markalar = [
            ("MRK-01", "Samsung", "Güney Kore", "Aktif"),
            ("MRK-02", "Apple", "ABD", "Aktif"),
            ("MRK-03", "Siemens", "Almanya", "Aktif"),
            ("MRK-04", "Philips", "Hollanda", "Aktif"),
            ("MRK-05", "Yerli Üretim", "Türkiye", "Aktif"),
        ]
        self._load_generic_table(self.tbl_marka, "stok_markalar", default_markalar)
        lyt.addWidget(self.tbl_marka, 1)
        return w

    def build_birim_panel(self) -> QWidget:
        """Birim Tanımları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("📏 Birim Tanımları")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel(
            "Stok Kartı ve Evrak satırlarında kullanılan ölçü birimleri.",
        )
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(lbl_info)

        self.tbl_birim = QTableWidget(0, 3)
        self.tbl_birim.setHorizontalHeaderLabels(["Kod", "Açıklama", "Durum"])
        self._setup_table_style(self.tbl_birim)
        self.tbl_birim.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )

        default_units = [
            ("ADET", "Adet", "Aktif"),
            ("KG", "Kilogram", "Aktif"),
            ("GR", "Gram", "Aktif"),
            ("LT", "Litre", "Aktif"),
            ("MT", "Metre", "Aktif"),
            ("M2", "Metrekare", "Aktif"),
            ("M3", "Metreküp", "Aktif"),
            ("PKT", "Paket", "Aktif"),
            ("KTN", "Karton", "Aktif"),
            ("KLI", "Koli", "Aktif"),
            ("HZM", "Hizmet", "Aktif"),
            ("SFR", "Sefer", "Aktif"),
        ]
        for row_data in default_units:
            r = self.tbl_birim.rowCount()
            self.tbl_birim.insertRow(r)
            for c, val in enumerate(row_data):
                self.tbl_birim.setItem(r, c, QTableWidgetItem(val))

        lyt.addWidget(self.tbl_birim, 1)
        self._load_birimler_from_db()
        return w

    def build_depo_panel(self) -> QWidget:
        """Depo Tanımları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("🏭 Depo Tanımları")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel(
            "Teklif, Fatura ve Stok hareketlerinde kullanılan depo lokasyonları.",
        )
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(lbl_info)

        self.tbl_depo = QTableWidget(0, 4)
        self.tbl_depo.setHorizontalHeaderLabels([
            "Depo Kodu", "Depo Adı", "Adres", "Durum",
        ])
        self._setup_table_style(self.tbl_depo)
        self.tbl_depo.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )

        default_depolar = [
            ("2001", "MERKEZ DEPO", "Merkez", "Aktif"),
            ("2002", "ŞUBE DEPOSU", "Şube", "Aktif"),
            ("2003", "TEŞHİR DEPOSU", "Mağaza", "Aktif"),
        ]
        for row_data in default_depolar:
            r = self.tbl_depo.rowCount()
            self.tbl_depo.insertRow(r)
            for c, val in enumerate(row_data):
                self.tbl_depo.setItem(r, c, QTableWidgetItem(val))

        lyt.addWidget(self.tbl_depo, 1)
        self._load_depolar_from_db()
        return w

    def build_ozel_alan_panel(self, modul: str = "stok") -> QWidget:
        """Özel Alan Etiket Tanımları Paneli (Stok veya Cari)."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(10)

        modul_title = "Stok Kartı" if modul == "stok" else "Cari Hesap"
        lbl = QLabel(f"🏷️ {modul_title} Özel Alan Tanımları")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel(
            f"Özel kod ve alan etiketlerini sektörünüze göre özelleştirin.\n"
            f"Değişiklikler {modul_title} formunda anında yansır.",
        )
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lbl_info.setWordWrap(True)
        lyt.addWidget(lbl_info)

        form = QGridLayout()
        form.setSpacing(8)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(3, 1)

        ozel_alanlar = [
            ("Özel Kod 1", "ozel_kod_1", "Metin"),
            ("Özel Kod 2", "ozel_kod_2", "Metin"),
            ("Özel Kod 3", "ozel_kod_3", "Metin"),
            ("Özel Alan 1", "ozel_alan_1", "Metin"),
            ("Özel Alan 2", "ozel_alan_2", "Sayı"),
            ("Özel Alan 3", "ozel_alan_3", "Tarih"),
        ]

        lbl_style = "font-size:11px; font-weight:600; color:#475569;"
        self.ozel_alan_inputs[modul] = {}

        for i, (varsayilan, key, tip) in enumerate(ozel_alanlar):
            r = i // 2
            c_offset = (i % 2) * 2

            lbl_alan = QLabel(f"{varsayilan}:")
            lbl_alan.setStyleSheet(lbl_style)
            txt = QLineEdit()
            txt.setPlaceholderText(
                f"{varsayilan} (boş bırakırsanız varsayılan kullanılır)",
            )
            txt.setFixedHeight(26)
            txt.setStyleSheet(
                "border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px;",
            )
            txt.setToolTip(
                f"Varsayılan: '{varsayilan}'\nTip: {tip}\nÖrn: 'Çağrı Numarası', 'Proje Kodu'",
            )
            self.ozel_alan_inputs[modul][key] = txt

            form.addWidget(lbl_alan, r, c_offset)
            form.addWidget(txt, r, c_offset + 1)

        lyt.addLayout(form)
        lyt.addStretch()

        self._load_ozel_alanlar(modul)
        return w

    def build_cari_gruplari_panel(self) -> QWidget:
        """Cari Grupları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lbl = QLabel("👥 Cari Grup Tanımları")
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)

        lbl_info = QLabel(
            "Cari hesapların sınıflandırılması ve grup iskonto / vade tanımları.",
        )
        lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(lbl_info)

        self.tbl_cari_grup = QTableWidget(0, 5)
        self.tbl_cari_grup.setHorizontalHeaderLabels([
            "Grup Kodu", "Grup Adı", "İskonto (%)", "Vade (Gün)", "Durum",
        ])
        self._setup_table_style(self.tbl_cari_grup)
        self.tbl_cari_grup.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch,
        )

        default_gruplar = [
            ("GRP-01", "YURT İÇİ MÜŞTERİLER", "0.00", "30", "Aktif"),
            ("GRP-02", "TOPTAN / BAYİLER", "15.00", "60", "Aktif"),
            ("GRP-03", "YURT DIŞI ALICILAR", "5.00", "0", "Aktif"),
            ("GRP-04", "TEDARİKÇİLER", "0.00", "45", "Aktif"),
        ]
        self._load_generic_table(self.tbl_cari_grup, "cari_gruplari", default_gruplar)
        lyt.addWidget(self.tbl_cari_grup, 1)
        return w


    def build_gorunum_panel(self) -> QWidget:
        """Mevcut Görünüm Profilleri Paneli (kabuk içinde: yalnız içerik)."""
        self.view_settings_tab = ViewSettingsWidget(embedded=True)
        return self.view_settings_tab

    def build_ekran_grid_panel(self) -> QWidget:
        """Ekran Şablonları & Grid Tanımları Paneli (kabuk içinde: yalnız içerik)."""
        self.screen_defs_tab = ScreenDefinitionsManagerWidget(embedded=True)
        return self.screen_defs_tab

    def build_surum_panel(self) -> QWidget:
        """Sürüm & Git Takibi Paneli (kabuk içinde: yalnız içerik)."""
        self.git_tracker_tab = GitTrackerWidget(embedded=True)
        return self.git_tracker_tab

    # ─────────────────────────────────────────────────────────────
    # DB LOAD & SAVE METHODS
    # ─────────────────────────────────────────────────────────────

    def _load_doviz_from_db(self) -> None:
        """DB'den döviz tanımlarını yükler."""
        if not self.db:
            return
        try:
            currencies = self.db.scalars(
                select(Currency).where(Currency.is_deleted == False),
            ).all()
            if currencies:
                self.tbl_doviz.setRowCount(0)
                for c in currencies:
                    r = self.tbl_doviz.rowCount()
                    self.tbl_doviz.insertRow(r)
                    self.tbl_doviz.setItem(r, 0, QTableWidgetItem(c.code or ""))
                    self.tbl_doviz.setItem(r, 1, QTableWidgetItem(c.name or ""))
                    self.tbl_doviz.setItem(r, 2, QTableWidgetItem(c.symbol or ""))
                    self.tbl_doviz.setItem(
                        r, 3, QTableWidgetItem(f"{float(c.rate or 1.0):.4f}"),
                    )
                    self.tbl_doviz.setItem(
                        r, 4, QTableWidgetItem("Aktif" if c.is_active else "Pasif"),
                    )
        except Exception as e:
            logger.warning(f"Döviz listesi yüklenemedi: {e}")

    def _save_doviz(self) -> None:
        """Döviz tanımlarını DB'ye kaydeder."""
        if not self.db:
            return
        try:
            existing = {
                c.code: c
                for c in self.db.scalars(
                    select(Currency).where(Currency.is_deleted == False),
                ).all()
            }
            for r in range(self.tbl_doviz.rowCount()):
                code_item = self.tbl_doviz.item(r, 0)
                name_item = self.tbl_doviz.item(r, 1)
                sym_item = self.tbl_doviz.item(r, 2)
                rate_item = self.tbl_doviz.item(r, 3)
                status_item = self.tbl_doviz.item(r, 4)

                code = code_item.text().strip().upper() if code_item else ""
                if not code:
                    continue
                name = name_item.text().strip() if name_item else ""
                symbol = sym_item.text().strip() if sym_item else ""
                try:
                    rate_val = (
                        float(rate_item.text().replace(",", ".").strip())
                        if rate_item
                        else 1.0
                    )
                except ValueError:
                    rate_val = 1.0
                is_act = (
                    (status_item.text().strip().lower() != "pasif")
                    if status_item
                    else True
                )

                if code in existing:
                    c = existing[code]
                    c.name = name
                    c.symbol = symbol
                    c.rate = rate_val
                    c.is_active = is_act
                else:
                    new_c = Currency(
                        code=code,
                        name=name,
                        symbol=symbol,
                        rate=rate_val,
                        is_active=is_act,
                    )
                    self.db.add(new_c)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Döviz tanımları kaydedilemedi: {e}")
            raise

    def _load_birimler_from_db(self) -> None:
        """DB'den birim tanımlarını yükler."""
        if not self.db:
            return
        try:
            units = self.db.scalars(
                select(UnitDefinition).where(UnitDefinition.is_deleted == False),
            ).all()
            if units:
                self.tbl_birim.setRowCount(0)
                for u in units:
                    r = self.tbl_birim.rowCount()
                    self.tbl_birim.insertRow(r)
                    self.tbl_birim.setItem(r, 0, QTableWidgetItem(u.code or ""))
                    self.tbl_birim.setItem(r, 1, QTableWidgetItem(u.name or ""))
                    self.tbl_birim.setItem(
                        r, 2, QTableWidgetItem("Aktif" if u.is_active else "Pasif"),
                    )
        except Exception as e:
            logger.warning(f"Birim listesi yüklenemedi: {e}")

    def _save_birimler(self) -> None:
        """Birim tanımlarını DB'ye kaydeder."""
        if not self.db:
            return
        try:
            existing = {
                u.code: u
                for u in self.db.scalars(
                    select(UnitDefinition).where(
                        UnitDefinition.is_deleted == False,
                    ),
                ).all()
            }
            for r in range(self.tbl_birim.rowCount()):
                code_item = self.tbl_birim.item(r, 0)
                name_item = self.tbl_birim.item(r, 1)
                status_item = self.tbl_birim.item(r, 2)

                code = code_item.text().strip().upper() if code_item else ""
                if not code:
                    continue
                name = name_item.text().strip() if name_item else ""
                is_act = (
                    (status_item.text().strip().lower() != "pasif")
                    if status_item
                    else True
                )

                if code in existing:
                    u = existing[code]
                    u.name = name
                    u.is_active = is_act
                else:
                    new_u = UnitDefinition(
                        code=code,
                        name=name,
                        is_active=is_act,
                    )
                    self.db.add(new_u)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Birim tanımları kaydedilemedi: {e}")
            raise

    def _load_depolar_from_db(self) -> None:
        """DB'den depo tanımlarını yükler."""
        if not self.db:
            return
        try:
            warehouses = self.db.scalars(
                select(WarehouseDefinition).where(
                    WarehouseDefinition.is_deleted == False,
                ),
            ).all()
            if warehouses:
                self.tbl_depo.setRowCount(0)
                for w in warehouses:
                    r = self.tbl_depo.rowCount()
                    self.tbl_depo.insertRow(r)
                    self.tbl_depo.setItem(r, 0, QTableWidgetItem(w.code or ""))
                    self.tbl_depo.setItem(r, 1, QTableWidgetItem(w.name or ""))
                    self.tbl_depo.setItem(
                        r, 2, QTableWidgetItem(w.address or ""),
                    )
                    self.tbl_depo.setItem(
                        r, 3, QTableWidgetItem("Aktif" if w.is_active else "Pasif"),
                    )
        except Exception as e:
            logger.warning(f"Depo listesi yüklenemedi: {e}")

    def _save_depolar(self) -> None:
        """Depo tanımlarını DB'ye kaydeder."""
        if not self.db:
            return
        try:
            existing = {
                w.code: w
                for w in self.db.scalars(
                    select(WarehouseDefinition).where(
                        WarehouseDefinition.is_deleted == False,
                    ),
                ).all()
            }
            for r in range(self.tbl_depo.rowCount()):
                code_item = self.tbl_depo.item(r, 0)
                name_item = self.tbl_depo.item(r, 1)
                addr_item = self.tbl_depo.item(r, 2)
                status_item = self.tbl_depo.item(r, 3)

                code = code_item.text().strip() if code_item else ""
                if not code:
                    continue
                name = name_item.text().strip() if name_item else ""
                addr = addr_item.text().strip() if addr_item else ""
                is_act = (
                    (status_item.text().strip().lower() != "pasif")
                    if status_item
                    else True
                )

                if code in existing:
                    w = existing[code]
                    w.name = name
                    w.address = addr
                    w.is_active = is_act
                else:
                    new_w = WarehouseDefinition(
                        code=code,
                        name=name,
                        address=addr,
                        is_active=is_act,
                    )
                    self.db.add(new_w)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Depo tanımları kaydedilemedi: {e}")
            raise

    def _load_odeme_planlari_from_db(self) -> None:
        """DB'den ödeme planlarını yükler."""
        if not self.db:
            return
        try:
            plans = self.db.scalars(
                select(PaymentPlan).where(PaymentPlan.is_deleted == False),
            ).all()
            if plans:
                self.tbl_odeme.setRowCount(0)
                for p in plans:
                    r = self.tbl_odeme.rowCount()
                    self.tbl_odeme.insertRow(r)
                    self.tbl_odeme.setItem(r, 0, QTableWidgetItem(p.code or ""))
                    self.tbl_odeme.setItem(
                        r, 1, QTableWidgetItem(p.description or ""),
                    )
                    self.tbl_odeme.setItem(
                        r, 2, QTableWidgetItem(str(p.days or 0)),
                    )
                    self.tbl_odeme.setItem(
                        r, 3, QTableWidgetItem(p.payment_type or ""),
                    )
                    self.tbl_odeme.setItem(
                        r, 4, QTableWidgetItem("Aktif" if p.is_active else "Pasif"),
                    )
        except Exception as e:
            logger.warning(f"Ödeme planları yüklenemedi: {e}")

    def _save_odeme_planlari(self) -> None:
        """Ödeme planlarını DB'ye kaydeder."""
        if not self.db:
            return
        try:
            existing = {
                p.code: p
                for p in self.db.scalars(
                    select(PaymentPlan).where(PaymentPlan.is_deleted == False),
                ).all()
            }
            for r in range(self.tbl_odeme.rowCount()):
                code_item = self.tbl_odeme.item(r, 0)
                desc_item = self.tbl_odeme.item(r, 1)
                days_item = self.tbl_odeme.item(r, 2)
                type_item = self.tbl_odeme.item(r, 3)
                status_item = self.tbl_odeme.item(r, 4)

                code = code_item.text().strip() if code_item else ""
                if not code:
                    continue
                desc = desc_item.text().strip() if desc_item else ""
                try:
                    days_val = (
                        int(days_item.text().strip()) if days_item else 0
                    )
                except ValueError:
                    days_val = 0
                ptype = type_item.text().strip() if type_item else ""
                is_act = (
                    (status_item.text().strip().lower() != "pasif")
                    if status_item
                    else True
                )

                if code in existing:
                    p = existing[code]
                    p.description = desc
                    p.days = days_val
                    p.payment_type = ptype
                    p.is_active = is_act
                else:
                    new_p = PaymentPlan(
                        code=code,
                        description=desc,
                        days=days_val,
                        payment_type=ptype,
                        is_active=is_act,
                    )
                    self.db.add(new_p)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ödeme planları kaydedilemedi: {e}")
            raise

    def _load_ozel_alanlar(self, modul: str) -> None:
        """DB'den özel alan etiketlerini yükler."""
        if not self.db:
            return
        try:
            inputs = self.ozel_alan_inputs.get(modul, {})
            for key, txt in inputs.items():
                setting_key = f"{modul}.{key}.label"
                setting = self.db.scalar(
                    select(SystemSetting).where(
                        SystemSetting.key == setting_key,
                        SystemSetting.is_deleted == False,
                    ),
                )
                if setting and setting.value:
                    txt.setText(setting.value)
        except Exception as e:
            logger.warning(f"Özel alanlar yüklenemedi ({modul}): {e}")

    def _save_ozel_alanlar(self, modul: str) -> None:
        """Özel alan etiketlerini DB'ye kaydeder."""
        if not self.db:
            return
        try:
            inputs = self.ozel_alan_inputs.get(modul, {})
            for key, txt in inputs.items():
                setting_key = f"{modul}.{key}.label"
                val = txt.text().strip()
                setting = self.db.scalar(
                    select(SystemSetting).where(
                        SystemSetting.key == setting_key,
                        SystemSetting.is_deleted == False,
                    ),
                )
                if setting:
                    setting.value = val
                else:
                    new_setting = SystemSetting(key=setting_key, value=val)
                    self.db.add(new_setting)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Özel alanlar kaydedilemedi ({modul}): {e}")
            raise

    def _load_kategoriler_from_db(self) -> None:
        """DB'den stok kategorilerini yükler."""
        if not self.db:
            return
        try:
            categories = self.db.scalars(
                select(Category).where(Category.is_deleted == False),
            ).all()
            if categories:
                self.tbl_kategori.setRowCount(0)
                cat_dict = {c.id: c.name for c in categories}
                for c in categories:
                    r = self.tbl_kategori.rowCount()
                    self.tbl_kategori.insertRow(r)
                    parent_name = (
                        cat_dict.get(c.parent_id, "-") if c.parent_id else "-"
                    )
                    self.tbl_kategori.setItem(
                        r, 0, QTableWidgetItem(c.name or ""),
                    )
                    self.tbl_kategori.setItem(
                        r, 1, QTableWidgetItem(parent_name),
                    )
                    self.tbl_kategori.setItem(r, 2, QTableWidgetItem("Aktif"))
        except Exception as e:
            logger.warning(f"Kategoriler yüklenemedi: {e}")

    def _save_kategoriler(self) -> None:
        """Stok kategorilerini DB'ye kaydeder."""
        if not self.db:
            return
        try:
            existing = {
                c.name: c
                for c in self.db.scalars(
                    select(Category).where(Category.is_deleted == False),
                ).all()
            }
            for r in range(self.tbl_kategori.rowCount()):
                name_item = self.tbl_kategori.item(r, 0)
                name = name_item.text().strip() if name_item else ""
                if not name:
                    continue
                if name not in existing:
                    new_cat = Category(name=name)
                    self.db.add(new_cat)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Kategoriler kaydedilemedi: {e}")
            raise

    def _load_generic_table(
        self, tbl: QTableWidget, setting_key: str, default_data: list,
    ) -> None:
        """Genel tabloları SystemSetting JSON verisinden yükler."""
        if self.db:
            try:
                setting = self.db.scalar(
                    select(SystemSetting).where(
                        SystemSetting.key == f"generic_table.{setting_key}",
                        SystemSetting.is_deleted == False,
                    ),
                )
                if setting and setting.value:
                    data = json.loads(setting.value)
                    if isinstance(data, list) and data:
                        tbl.setRowCount(0)
                        for row_data in data:
                            r = tbl.rowCount()
                            tbl.insertRow(r)
                            for c, val in enumerate(row_data):
                                tbl.setItem(r, c, QTableWidgetItem(str(val)))
                        return
            except Exception as e:
                logger.warning(f"Tablo yüklenemedi ({setting_key}): {e}")

        # Varsayılan veriler
        tbl.setRowCount(0)
        for row_data in default_data:
            r = tbl.rowCount()
            tbl.insertRow(r)
            for c, val in enumerate(row_data):
                tbl.setItem(r, c, QTableWidgetItem(str(val)))

    def _save_generic_table(self, tbl: QTableWidget, setting_key: str) -> None:
        """Genel tablo verisini SystemSetting içine JSON olarak kaydeder."""
        if not self.db:
            return
        try:
            data = []
            for r in range(tbl.rowCount()):
                row = []
                for c in range(tbl.columnCount()):
                    it = tbl.item(r, c)
                    row.append(it.text().strip() if it else "")
                data.append(row)

            val = json.dumps(data, ensure_ascii=False)
            full_key = f"generic_table.{setting_key}"
            setting = self.db.scalar(
                select(SystemSetting).where(
                    SystemSetting.key == full_key,
                    SystemSetting.is_deleted == False,
                ),
            )
            if setting:
                setting.value = val
            else:
                new_setting = SystemSetting(key=full_key, value=val)
                self.db.add(new_setting)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Tablo kaydedilemedi ({setting_key}): {e}")
            raise

    # ─────────────────────────────────────────────────────────────
    # ACTIONS (SAVE, NEW, DELETE, CANCEL)
    # ─────────────────────────────────────────────────────────────

    def save_current_panel(self) -> None:
        """Aktif paneldeki veriyi kaydeder."""
        panel_save_map = {
            "doviz_kur": self._save_doviz,
            "birim_tanimlari": self._save_birimler,
            "depo_tanimlari": self._save_depolar,
            "odeme_planlari": self._save_odeme_planlari,
            "stok_ozel_alanlar": lambda: self._save_ozel_alanlar("stok"),
            "cari_ozel_alanlar": lambda: self._save_ozel_alanlar("cari"),
            "stok_kategoriler": self._save_kategoriler,
            "sube_tanimlari": lambda: self._save_generic_table(
                self.tbl_sube, "subeler",
            ),
            # roller / yetkiler: kayıt kendi editör diyaloglarında; panelde Kaydet no-op
            "roller": lambda: None,
            "yetkiler": lambda: None,
            "kullanicilar": lambda: None,
            "fiyat_listeleri": lambda: self._save_generic_table(
                self.tbl_fiyat, "fiyat_listeleri",
            ),
            "stok_markalar": lambda: self._save_generic_table(
                self.tbl_marka, "stok_markalar",
            ),
            "cari_gruplari": lambda: self._save_generic_table(
                self.tbl_cari_grup, "cari_gruplari",
            ),
        }

        fn = panel_save_map.get(self.active_panel_id)
        if fn:
            try:
                fn()
                self.toast_requested.emit("Ayarlar başarıyla kaydedildi.", "success")
                QMessageBox.information(
                    self, "Başarılı", "Ayarlar başarıyla kaydedildi.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {e}")
        elif self.active_panel_id == "kullanicilar":
            QMessageBox.information(
                self,
                "Bilgi",
                "Kullanıcı değişiklikleri için listeden 'Ekle' veya 'Değiştir' butonunu kullanınız.",
            )
        elif self.active_panel_id == "firma_bilgileri":
            QMessageBox.information(
                self,
                "Bilgi",
                "Firma değişiklikleri Firma Tanımları ekranındaki işlemlerle kaydedilir.",
            )
        elif self.active_panel_id == "gorunum_profilleri":
            QMessageBox.information(
                self,
                "Bilgi",
                "Görünüm profili değişiklikleri ilgili profil butonları ile yönetilir.",
            )
        else:
            QMessageBox.information(
                self, "Bilgi", "Bu panel için doğrudan kaydetme işlemi gerekmez.",
            )

    def new_current_panel(self) -> None:
        """Aktif panele yeni kayıt / satır ekler."""
        if self.active_panel_id == "kullanicilar":
            self.users_tab.add_new()
            return
        if self.active_panel_id == "roller":
            self.roller_tab.add_new()
            return
        if self.active_panel_id == "firma_bilgileri":
            self.firma_tab.add_new()
            return

        panel_table_map = {
            "sube_tanimlari": "tbl_sube",
            "doviz_kur": "tbl_doviz",
            "odeme_planlari": "tbl_odeme",
            "fiyat_listeleri": "tbl_fiyat",
            "stok_kategoriler": "tbl_kategori",
            "stok_markalar": "tbl_marka",
            "birim_tanimlari": "tbl_birim",
            "depo_tanimlari": "tbl_depo",
            "cari_gruplari": "tbl_cari_grup",
        }
        tbl_attr = panel_table_map.get(self.active_panel_id)
        if tbl_attr and hasattr(self, tbl_attr):
            tbl: QTableWidget = getattr(self, tbl_attr)
            r = tbl.rowCount()
            tbl.insertRow(r)
            for c in range(tbl.columnCount()):
                tbl.setItem(r, c, QTableWidgetItem(""))
            tbl.selectRow(r)

    def delete_current_panel(self) -> None:
        """Aktif panelden seçili kaydı / satırı siler."""
        if self.active_panel_id == "kullanicilar":
            self.users_tab.delete_selected()
            return
        if self.active_panel_id == "roller":
            self.roller_tab.delete_selected()
            return
        if self.active_panel_id == "firma_bilgileri":
            self.firma_tab.delete_selected()
            return

        if self.active_panel_id == "gorunum_profilleri":
            self.view_settings_tab.delete_selected_profile()
            return

        panel_table_map = {
            "sube_tanimlari": "tbl_sube",
            "doviz_kur": "tbl_doviz",
            "odeme_planlari": "tbl_odeme",
            "fiyat_listeleri": "tbl_fiyat",
            "stok_kategoriler": "tbl_kategori",
            "stok_markalar": "tbl_marka",
            "birim_tanimlari": "tbl_birim",
            "depo_tanimlari": "tbl_depo",
            "cari_gruplari": "tbl_cari_grup",
        }
        tbl_attr = panel_table_map.get(self.active_panel_id)
        if tbl_attr and hasattr(self, tbl_attr):
            tbl: QTableWidget = getattr(self, tbl_attr)
            row = tbl.currentRow()
            if row >= 0:
                reply = QMessageBox.question(
                    self,
                    "Sil",
                    "Seçili satır silinecek. Emin misiniz?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    tbl.removeRow(row)
            else:
                QMessageBox.warning(
                    self, "Uyarı", "Lütfen silmek istediğiniz satırı seçin.",
                )

    def cancel_current_panel(self) -> None:
        """Değişiklikleri iptal eder ve paneli yeniler."""
        if self.active_panel_id:
            self.switch_panel(self.active_panel_id)


# Geriye dönük uyumluluk alias'ı
SettingsWidget = GeneralSettingsScreen
