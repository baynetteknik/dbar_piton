"""TOYA ERP - Genel Ayarlar Ekranı (General Settings Screen - sys.set.001).

Bu modül; Sol Sidebar (İşlemler + Menü Grupları), QStackedWidget Body ve Alt Bar
mimarisinde tüm ERP sistem ayarlarını yönetir.
"""

import hashlib
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QDate, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
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
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import (
    BankaOdemePlani,
    Category,
    Currency,
    FinansHesap,
    PaymentPlan,
    Site,
    SystemSetting,
    UnitDefinition,
    User,
)
from src.desktop.services import currency_rate_service
from src.desktop.services import settings_menu as sm
from src.desktop.services.currency_catalog import CURRENCY_CATALOG, get_currency_info
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.components.button_style import (
    DANGER_BG,
    DANGER_FG,
    PRIMARY,
    btn_style,
)
from src.desktop.ui.components.coded_button import CodedButton
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.entry_table_view import EntryTableView, standart_grid
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.components.git_tracker_widget import GitTrackerWidget
from src.desktop.ui.components.grid_delegates import ComboDelegate
from src.desktop.ui.components.layout_hint_helper import (
    is_layout_hints_enabled,
    register_layout_hint,
    set_layout_hints_enabled,
)
from src.desktop.ui.components.text_selection_helper import (
    is_global_text_selection_enabled,
    set_global_text_selection_enabled,
)
from src.desktop.ui.components.tooltip_style import apply_app_style, with_tooltip
from src.desktop.ui.screen_definitions_manager import (
    ScreenDefinitionsManagerWidget,
)
from src.desktop.ui.sites import SitesWidget
from src.desktop.ui.widgets.address_definitions_widget import (
    AddressDefinitionsWidget,
)
from src.desktop.ui.widgets.bank_definitions_widget import BankDefinitionsWidget
from src.desktop.ui.widgets.banka_odeme_plani_ekle_dialog import (
    BankaOdemePlaniEkleDialog,
)
from src.desktop.ui.widgets.currency_picker_dialog import pick_currency
from src.desktop.ui.widgets.currency_rate_report_widget import (
    CurrencyRateReportWidget,
)
from src.desktop.ui.widgets.document_numbering_widget import (
    DocumentNumberingWidget,
)
from src.desktop.ui.widgets.masked_decimal_field import MaskedDecimalField
from src.desktop.ui.widgets.odeme_plani_ekle_dialog import OdemePlaniEkleDialog
from src.desktop.ui.widgets.odeme_plani_satirlari_dialog import (
    OdemePlaniSatirlariDialog,
)
from src.desktop.ui.widgets.reorderable_sidebar import ReorderableSidebar
from src.desktop.ui.widgets.serbest_piyasa_kaynak_widget import SerbestPiyasaKaynakField
from src.desktop.ui.widgets.settings_hub_widget import SettingsHubWidget
from src.desktop.ui.widgets.tax_offices_widget import TaxOfficesWidget
from src.desktop.ui.widgets.yardim_widget import YardimWidget

logger = logging.getLogger(__name__)

#: Ödeme Planı > Ödeme Tipi — yapılandırılmış kod ↔ görünen etiket (bkz. gelistirme/04_odeme_planlari/
#: tasarim.md). Fatura/İrsaliye kaydedilince bu tipe göre otomatik kasa/banka fişi oluşturulacak (04.07+);
#: "cek"/"senet" şimdilik yalnızca seçilebilir, Çek/Senet modülü kodlanana kadar otomatik fiş üretmez.
ODEME_TIPI_SECENEKLERI: list[tuple[str, str]] = [
    ("nakit", "Nakit"),
    ("havale_eft", "Havale/EFT"),
    ("kredi_karti", "Kredi Kartı"),
    ("pos", "POS"),
    ("acik_hesap", "Açık Hesap"),
    ("cek", "Çek"),
    ("senet", "Senet"),
]
_ODEME_TIPI_KOD_TO_ETIKET: dict[str, str] = dict(ODEME_TIPI_SECENEKLERI)
_ODEME_TIPI_ETIKET_TO_KOD: dict[str, str] = {v: k for k, v in ODEME_TIPI_SECENEKLERI}
#: Eski (serbest metin) "Ödeme Tipi" değerlerinin yeni koda eşlenmesi — mevcut 7 varsayılan plan için.
_ODEME_TIPI_ESKI_ESLEME: dict[str, str] = {
    "açık hesap": "acik_hesap", "nakit": "nakit", "kredi kartı": "kredi_karti",
    "taksit": "kredi_karti",   # taksitli kredi kartı ödemesi (ör. CF3TAK) — description'da taksit bilgisi kalır
}


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
            QComboBox {
                combobox-popup: 0;
            }
            QComboBox QAbstractItemView {
                outline: 0;
                padding: 0px;
                border: 1px solid #cbd5e1;
                background-color: white;
            }
            QComboBox QAbstractItemView::item {
                padding: 3px 6px;
                min-height: 20px;
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
        return btn_style(bg_color, text_color)

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
            "QComboBox { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background-color: white; font-size: 11px; combobox-popup: 0; }"
            " QComboBox QAbstractItemView { outline: 0; padding: 0px; border: 1px solid #cbd5e1; background-color: white; }"
            " QComboBox QAbstractItemView::item { padding: 3px 6px; min-height: 20px; }",
        )
        self.cmb_filter_role.currentTextChanged.connect(self.load_users)

        lbl_status = QLabel("Durum:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_status = QComboBox()
        self.cmb_filter_status.addItem("Tümü", -1)
        self.cmb_filter_status.addItem("Aktif", 1)
        self.cmb_filter_status.addItem("Pasif", 0)
        self.cmb_filter_status.setStyleSheet(
            "QComboBox { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background-color: white; font-size: 11px; combobox-popup: 0; }"
            " QComboBox QAbstractItemView { outline: 0; padding: 0px; border: 1px solid #cbd5e1; background-color: white; }"
            " QComboBox QAbstractItemView::item { padding: 3px 6px; min-height: 20px; }",
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
            "QComboBox { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background-color: white; font-weight: bold; font-size: 11px; combobox-popup: 0; }"
            " QComboBox QAbstractItemView { outline: 0; padding: 0px; border: 1px solid #cbd5e1; background-color: white; }"
            " QComboBox QAbstractItemView::item { padding: 3px 6px; min-height: 20px; }",
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

    def showEvent(self, event) -> None:  # noqa: N802
        """Başka ekrandan kaydedilen / silinen profiller, bu liste açıldığında (görününce) güncel görünsün."""
        super().showEvent(event)
        if getattr(self, "_profiles_ready", False):
            self.load_profiles()
        self._profiles_ready = True                  # ilk gösterimde liste zaten kurulumda yüklendi

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


class YeniDovizDialog(QDialog):
    """Döviz & Kur panelinde 'Yeni Döviz Ekle' — kod/isim/sembol serbest
    metinle elden yazılmaz; ISO 4217 kataloğundan (bkz. `currency_catalog.py`
    / `CurrencyPickerDialog`) aranıp seçilir. Seçim sonrası ad/sembol gerekirse
    elle düzeltilebilir (özel/yerel bir kullanım için)."""

    def __init__(self, parent=None, *, exclude_codes: set[str] | None = None) -> None:
        super().__init__(parent)
        self._exclude_codes = exclude_codes or set()
        self._code = ""
        self._flag = ""
        self.setWindowTitle("➕ Yeni Döviz Ekle")
        self.setFixedSize(340, 230)
        lyt = QVBoxLayout(self)
        form = QFormLayout()

        row_kod = QHBoxLayout()
        self.txt_kod = QLineEdit()
        self.txt_kod.setReadOnly(True)
        self.txt_kod.setPlaceholderText("Listeden seçin...")
        btn_sec = QPushButton("🔍 Listeden Seç")
        btn_sec.clicked.connect(self._secim_yap)
        row_kod.addWidget(self.txt_kod, 1)
        row_kod.addWidget(btn_sec)

        self.txt_ad = QLineEdit()
        self.txt_ad.setPlaceholderText("Amerikan Doları")
        self.txt_sembol = QLineEdit()
        self.txt_sembol.setPlaceholderText("$")
        self.chk_aktif = QCheckBox("Aktif")
        self.chk_aktif.setChecked(True)

        form.addRow("Döviz:", row_kod)
        form.addRow("Ad:", self.txt_ad)
        form.addRow("Sembol:", self.txt_sembol)
        form.addRow("", self.chk_aktif)
        lyt.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        lyt.addWidget(buttons)

    def _secim_yap(self) -> None:
        info = pick_currency(self, exclude_codes=self._exclude_codes)
        if info is None:
            return
        self._code = info.code
        self._flag = info.flag
        self.txt_kod.setText(f"{info.flag}  {info.code}".strip())
        self.txt_ad.setText(info.name)
        self.txt_sembol.setText(info.symbol)

    def _on_accept(self) -> None:
        if not self._code:
            QMessageBox.warning(self, "Uyarı", "Lütfen listeden bir döviz seçin.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "code": self._code,
            "name": self.txt_ad.text().strip(),
            "symbol": self.txt_sembol.text().strip(),
            "flag": self._flag,
            "is_active": self.chk_aktif.isChecked(),
        }


class KurGirDialog(QDialog):
    """Döviz & Kur panelinde 'Kur Gir' — belirli döviz + tarih için M.B./S.P.
    alış-satış değerlerini elle girmek için popup form."""

    def __init__(self, currency_codes: list[str], initial_date: QDate,
                 initial_code: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("✏️ Kur Gir")
        self.setFixedSize(340, 280)
        lyt = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_doviz = QComboBox()
        self.cmb_doviz.setStyleSheet("QComboBox { combobox-popup: 0; padding: 2px 6px; font-size: 11px; } QComboBox QAbstractItemView { outline: 0; padding: 0px; } QComboBox QAbstractItemView::item { padding: 3px 6px; }")
        self.cmb_doviz.addItems(currency_codes)
        if initial_code and initial_code in currency_codes:
            self.cmb_doviz.setCurrentText(initial_code)

        self.dt_tarih = QDateEdit(initial_date)
        self.dt_tarih.setCalendarPopup(True)
        self.dt_tarih.setDisplayFormat("dd.MM.yyyy")

        self.spn_mb_alis = self._make_spin()
        self.spn_mb_satis = self._make_spin()
        self.spn_sp_alis = self._make_spin()
        self.spn_sp_satis = self._make_spin()

        form.addRow("Döviz:", self.cmb_doviz)
        form.addRow("Tarih:", self.dt_tarih)
        form.addRow("M.B. Alış:", self.spn_mb_alis)
        form.addRow("M.B. Satış:", self.spn_mb_satis)
        form.addRow("S.P. Alış:", self.spn_sp_alis)
        form.addRow("S.P. Satış:", self.spn_sp_satis)
        lyt.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lyt.addWidget(buttons)

    @staticmethod
    def _make_spin() -> MaskedDecimalField:
        # Kur değerleri 4 ondalık hane ister (Genel Ayarlar'daki fiyat/tutar
        # ondalık hane tercihinden bağımsız — kur hassasiyeti farklı bir
        # gereksinim), bu yüzden sabit `decimals=4` ile oluşturulur.
        return MaskedDecimalField(decimals=4)

    def get_data(self) -> dict:
        def val(spn):
            return None if spn.value() == 0.0 else spn.value()

        return {
            "code": self.cmb_doviz.currentText(),
            "rate_date": self.dt_tarih.date().toPyDate(),
            "mb_alis": val(self.spn_mb_alis),
            "mb_satis": val(self.spn_mb_satis),
            "sp_alis": val(self.spn_sp_alis),
            "sp_satis": val(self.spn_sp_satis),
        }


class _LazyActionBoxes(dict):
    """{panel_id: işlem kutusu}; kutu ilk erişimde üretilir. Ekran açılırken ~30 menü × onlarca stilli düğmeyi
    baştan üretmek her açılışı saniyelerce yavaşlatıyordu; yalnızca girilen menünün kutusu kurulur."""

    def __init__(self, screen, layout) -> None:
        super().__init__()
        self._screen, self._layout = screen, layout

    def __missing__(self, panel_id: str):
        box = self._screen._build_sub_action_box(panel_id)
        box.hide()
        self._layout.addWidget(box)
        self[panel_id] = box
        return box


class GeneralSettingsScreen(QWidget):
    """Genel Ayarlar Ana Ekranı — sys.set.001.

    Sol sidebar (menü + işlemler) + Body (QStackedWidget) + Alt bar mimarisinde
    tüm sistem ayarlarını yönetir.
    """

    toast_requested = pyqtSignal(str, str)
    companies_updated = pyqtSignal()

    # Menü yapısı — (grup_adı, ikon, [(menü_adı, panel_id), ...])
    MENU_STRUCTURE = [
        (
            "ŞİRKET TANIMLARI",
            "🏢",
            [
                ("Firma Bilgileri", "firma_bilgileri"),
                ("Belge & Seri No", "numara_serileri"),
            ],
        ),
        (
            "ADRES & VERGİ",
            "🌍",
            [
                ("Adres Tanımları", "adres_tanimlari"),
                ("Vergi Daireleri", "vergi_daireleri"),
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
                ("Banka & Şube Tanımları", "banka_tanimlari"),
                ("Ödeme Planları", "odeme_planlari"),
                ("Banka Ödeme Planları", "banka_odeme_planlari"),
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
                ("Merkez", "yedek_merkezi"),
                ("Portal", "portal_yedek"),
                ("CMS / ERP", "cms_baglantilari"),
                ("Portal Yayın", "portal_yayin"),
                ("Online Portal", "online_portal"),
                ("Profiller", "gorunum_profilleri"),
                ("Ekran Gridleri", "ekran_grid"),
                ("Form Tasarımları", "form_tasarimlari"),
                ("E-Posta", "eposta_smtp"),
                ("KDV", "kdv_oranlari"),
                ("Kuruş Hanesi", "sayi_bicimi"),
                ("Güvenlik", "guvenlik"),
                ("Sürüm & Git", "surum_git"),
                ("Yardım", "yardim"),
            ],
        ),
    ]

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.code_mode = sm.code_mode(db_session)
        self.show_codes = self.code_mode == "rozet"
        self.active_panel_id: str | None = None
        self.panels: dict[str, QWidget] = {}
        self.menu_buttons: dict[str, QPushButton] = {}
        self.ozel_alan_inputs: dict[str, dict[str, QLineEdit]] = {
            "stok": {},
            "cari": {},
        }
        self._oranli_gridler: list = []                # `_new_grid` ile kurulan tanım tablolarının oranlı genişlik uygulayıcıları

        apply_app_style()                              # ipuçları: mavi zemin, beyaz yazı (bkz. tooltip_style)
        self.init_ui()
        register_layout_hint(self, "Ayarlar", "Genel Ayarlar Ana Ekranı")
        self.switch_panel("settings_hub")

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

        # Sol/sağ paneller açık gelir: sol panel asıl gezinme menüsünü, sağ panel İŞLEMLER'i
        # barındırıyor (document_detail_screen.py'deki yardımcı kenar panellerinden farklı —
        # onlar kapalı gelebiliyordu çünkü asıl işlev sağ tık/başka yerdeydi). 1366x768 taşması asıl
        # `PortalDeployWidget`'ın (QStackedWidget TÜM sayfaların en genişine göre boyutlanıyor)
        # eski tek satırlık 5 buton satırından kaynaklanıyordu — o yeniden tasarlandı (bkz.
        # portal_deploy_widget.py), burada paneller kapatılmadı.
        self.left_panel.open_panel()
        self.right_panel.open_panel()

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

        self.btn_hub = QPushButton("🏠 Ayarlar Panosu")
        self.btn_hub.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        self.btn_hub.setToolTip("İkonlu Genel Ayarlar Panosuna / Karşılama Ekranına Dön")
        self.btn_hub.clicked.connect(lambda: self.switch_panel("settings_hub"))
        lyt.addWidget(self.btn_hub)
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

        lbl_kod = QLabel("🔢 Kodlar:")
        lbl_kod.setStyleSheet("font-weight: bold; color: #7c3aed; font-size: 11px;")
        self.cmb_code_mode = QComboBox()
        for key, label in sm.CODE_MODES:
            self.cmb_code_mode.addItem(label, key)
        self.cmb_code_mode.setCurrentIndex(max(0, self.cmb_code_mode.findData(self.code_mode)))
        self.cmb_code_mode.setToolTip("Menü/işlem kodlarının gösterimi: İpucu (üzerine gelince), Rozet (adın altında) veya Gizli.")
        self.cmb_code_mode.setStyleSheet("font-size: 11px; padding: 2px 6px; combobox-popup: 0;")
        self.cmb_code_mode.currentIndexChanged.connect(lambda _i: self.set_code_mode(self.cmb_code_mode.currentData()))
        lyt.addWidget(lbl_kod)
        lyt.addWidget(self.cmb_code_mode)

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
        self.menu_search_input.setPlaceholderText("🔍 Menü adı veya kodu ara (örn. cari, 501)...")
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

        # Menü Grupları (Tümü varsayılan KAPALI gelir). Alt eylemler sol menüde değil: sağ panelde ve sağ tık menüsünde.
        # Bir grup `SUBGROUPS` ile açılır alt menülere bölünebilir; alt menüde olmayan öğeler grupta düz kalır.
        self._group_sections = []
        self.menu_inner_sections = {}      # panel_id → alt menü bölümü
        self.menu_inner_all = []           # (bölüm, başlık, kod)
        for grup_adi, ikon, menuler in self.MENU_STRUCTURE:
            gcode = sm.GROUP_CODES.get(grup_adi, "")
            sec = CollapsibleSection(f"{ikon} {grup_adi}", is_expanded=False)
            sec.set_code(gcode if self.show_codes else "")
            sec.header_btn.setToolTip(sm.tooltip(f"{ikon} {grup_adi}", gcode, self.code_mode))
            self.menu_sections.append(sec)
            self._group_sections.append((sec, f"{ikon} {grup_adi}", gcode))

            inner_by_title: dict[str, CollapsibleSection] = {}
            for menu_adi, panel_id in menuler:
                sub = sm.subgroup_of(grup_adi, panel_id)
                host = sec
                if sub:
                    title, scode = sub
                    if title not in inner_by_title:
                        inner = CollapsibleSection(title, is_expanded=False, compact=True)
                        inner.set_code(scode if self.show_codes else "")
                        inner.header_btn.setToolTip(sm.tooltip(title, scode, self.code_mode))
                        inner_by_title[title] = inner
                        self.menu_inner_all.append((inner, title, scode))
                        self._group_sections.append((inner, title, scode))
                        sec.add_widget(inner)
                    host = inner_by_title[title]
                    self.menu_inner_sections[panel_id] = host
                code = sm.item_code(panel_id)
                btn = CodedButton(menu_adi, code, show_code=self.show_codes, left_padding=11)
                btn.setStyleSheet(self.menu_btn_style())
                btn.setCheckable(True)
                btn.setToolTip(sm.tooltip(menu_adi, code, self.code_mode))
                btn.clicked.connect(
                    lambda _, pid=panel_id, b=btn: self.on_menu_clicked(pid, b),
                )
                self.menu_buttons[panel_id] = btn
                self.menu_item_containers[panel_id] = (btn, sec, menu_adi, grup_adi)
                host.add_widget(btn)

            lyt.addWidget(sec)

        lyt.addStretch()
        scroll.setWidget(frame)
        container_lyt.addWidget(scroll, 1)

        self.left_panel.set_content(container)
        return self.left_panel

    def _actions_map(self) -> dict:
        """Menü (panel) başına işlemler: {panel_id: [(etiket, geri çağrı), ...]}. Sağ panel ve sağ tık menüsü AYNI kaynağı kullanır."""
        return {
            "firma_bilgileri": [
                ("🧙 Şirket Sihirbazı", lambda: getattr(self, "firma_tab", None) and self.firma_tab.add_wizard()),
                ("➕ Yeni Firma (Manuel)", lambda: getattr(self, "firma_tab", None) and self.firma_tab.add_new()),
                ("✏️ Düzenle", lambda: getattr(self, "firma_tab", None) and self.firma_tab.edit_selected()),
                ("🗑️ Sil", lambda: getattr(self, "firma_tab", None) and self.firma_tab.delete_selected()),
                ("🔄 Yenile", lambda: getattr(self, "firma_tab", None) and self.firma_tab.load_data()),
            ],
            "numara_serileri": [
                ("➕ Yeni Seri Ekle", lambda: getattr(self, "doc_num_tab", None) and self.doc_num_tab._on_add()),
                ("✏️ Seriyi Düzenle", lambda: getattr(self, "doc_num_tab", None) and self.doc_num_tab._on_edit()),
                ("⭐ Varsayılan Yap", lambda: getattr(self, "doc_num_tab", None) and self.doc_num_tab._on_set_default()),
                ("🔍 Boşluk Analizi", lambda: getattr(self, "doc_num_tab", None) and self.doc_num_tab._on_gaps_dialog()),
                ("🗑️ Seriyi Sil", lambda: getattr(self, "doc_num_tab", None) and self.doc_num_tab._on_delete()),
                ("🔄 Yenile", lambda: getattr(self, "doc_num_tab", None) and self.doc_num_tab.load_data()),
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
            "adres_tanimlari": [
                ("➕ Yeni Ekle", lambda: getattr(self, "address_tab", None) and self.address_tab.add_new()),
                ("✏️ Düzenle", lambda: getattr(self, "address_tab", None) and self.address_tab.edit_selected()),
                ("🗑️ Sil", lambda: getattr(self, "address_tab", None) and self.address_tab.delete_selected()),
                ("🔄 Yenile", lambda: getattr(self, "address_tab", None) and self.address_tab.refresh_all()),
            ],
            "vergi_daireleri": [
                ("➕ Yeni Vergi Dairesi", lambda: getattr(self, "tax_tab", None) and self.tax_tab.add_new()),
                ("✏️ Düzenle", lambda: getattr(self, "tax_tab", None) and self.tax_tab.edit_selected()),
                ("🗑️ Sil", lambda: getattr(self, "tax_tab", None) and self.tax_tab.delete_selected()),
                ("🔄 Yenile", lambda: getattr(self, "tax_tab", None) and self.tax_tab.load_data()),
            ],
            "banka_tanimlari": [
                ("➕ Yeni Banka / Şube", lambda: getattr(self, "bank_tab", None) and self.bank_tab.add_new()),
                ("✏️ Düzenle", lambda: getattr(self, "bank_tab", None) and self.bank_tab.edit_selected()),
                ("🗑️ Sil", lambda: getattr(self, "bank_tab", None) and self.bank_tab.delete_selected()),
                ("🔄 Yenile", lambda: getattr(self, "bank_tab", None) and self.bank_tab.refresh_all()),
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
                ("➕ Yeni Döviz Ekle", lambda: self._open_yeni_doviz_dialog()),
                ("✏️ Kur Gir", lambda: self._open_kur_gir_dialog()),
                ("🗑️ Seçili Dövizi Sil", lambda: self._delete_selected_doviz_currency()),
                ("💾 Kurları Kaydet", lambda: self.save_current_panel()),
            ],
            "odeme_planlari": [
                ("➕ Yeni Plan Ekle", lambda: self._yeni_odeme_plani_ekle()),
                ("✏️ Seçiliyi Düzenle", lambda: self._yeni_odeme_plani_ekle(duzenle=True)),
                ("📑 Çok Türlü Satırları Düzenle", lambda: self._odeme_plani_satirlarini_duzenle()),
                ("🗑️ Seçili Planı Sil", lambda: self._delete_table_row(getattr(self, "tbl_odeme", None))),
                ("💾 Planları Kaydet", lambda: self.save_current_panel()),
            ],
            "banka_odeme_planlari": [
                ("➕ Yeni Banka Ödeme Planı Ekle", lambda: self._yeni_banka_odeme_plani_ekle()),
                ("✏️ Seçiliyi Düzenle", lambda: self._yeni_banka_odeme_plani_ekle(duzenle=True)),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_banka_odeme", None))),
                ("💾 Planları Kaydet", lambda: self.save_current_panel()),
            ],
            "fiyat_listeleri": [
                ("➕ Yeni Liste Ekle", lambda: self._add_table_row(getattr(self, "tbl_fiyat", None), ["", "", "Satış", "TRY", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_fiyat", None))),
                ("💾 Listeleri Kaydet", lambda: self.save_current_panel()),
            ],
            "stok_kategoriler": [
                ("➕ Yeni Kategori", lambda: self._add_table_row(getattr(self, "tbl_kategori", None), ["", "", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_kategori", None))),
                ("💾 Kaydet", lambda: self.save_current_panel()),
            ],
            "stok_markalar": [
                ("➕ Yeni Marka", lambda: self._add_table_row(getattr(self, "tbl_marka", None), ["", "", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_marka", None))),
                ("💾 Kaydet", lambda: self.save_current_panel()),
            ],
            "birim_tanimlari": [
                ("➕ Yeni Birim", lambda: self._add_table_row(getattr(self, "tbl_birim", None), ["", "", "1", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_birim", None))),
                ("💾 Kaydet", lambda: self.save_current_panel()),
            ],
            "stok_ozel_alanlar": [
                ("💾 Alanları Kaydet", lambda: self.save_current_panel()),
                ("🔄 Yenile", lambda: self._load_ozel_alanlar("stok")),
            ],
            "kdv_oranlari": [
                ("➕ Yeni KDV Ekle", lambda: self._add_table_row(getattr(self, "tbl_kdv", None), ["", "", "0", "Aktif"])),
                ("🗑️ Seçiliyi Sil", lambda: self._delete_table_row(getattr(self, "tbl_kdv", None))),
                ("💾 Kaydet", lambda: self.save_current_panel()),
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
            "portal_yayin": [
                # 👤 PROFİL İŞLEMLERİ
                ("➕ Yeni Profil Ekle", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab.new_profile()),
                ("💾 Profili Kaydet", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab.save()),
                ("🗑️ Profili Sil", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab._on_delete_profile()),
                # 🚀 GÖNDERİM
                ("🔌 Bağlantıyı Test Et", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab._on_test()),
                ("📦 Paketi Üret ve Gönder", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab._on_send()),
                ("🧩 Softaculous Paketi Üret", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab._on_softaculous()),
                # 🔑 GÜNCELLEME ANAHTARI
                ("🔑 Güncelleme Anahtarını Kopyala", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab._on_copy_secret()),
                ("📥 Anahtarı Yapıştır", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab._on_paste_secret()),
                # ❓ YARDIM & GEÇMİŞ
                ("❓ Yardım / Nasıl Kullanılır?", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab.show_help()),
                ("🗂️ Sürüm Geçmişi", lambda: getattr(self, "portal_deploy_tab", None) and self.portal_deploy_tab.show_history()),
            ],
            "form_tasarimlari": [
                ("➕ Yeni Form Ekle", lambda: self._form_tasarim_ekle()),
                ("🎨 Tasarımcıda Aç", lambda: self._form_tasarim_ac()),
                ("🗑️ Sil", lambda: self._form_tasarim_sil()),
                ("🔄 Yenile", lambda: self._load_form_tasarimlari()),
            ],
            "surum_git": [
                # ── 👤 PROFİL İŞLEMLERİ ──
                ("➕ Profil Ekle", lambda: self._git_profile_call("add_profile")),
                ("✏️ Profil Düzenle", lambda: self._git_profile_call("edit_profile")),
                ("🗑 Profil Sil", lambda: self._git_profile_call("hide_selected")),
                ("🔵 Google ile Giriş Yap", lambda: self._git_profile_call("btn_login")),
                ("🔌 Bağlantıyı Test Et", lambda: self._git_profile_call("btn_test")),
                # ── 🌿 GİT İŞLEMLERİ ──
                ("🚀 Git'e Gönder (Push)", lambda: self._git_call("on_commit_push_clicked")),
                ("🔄 Fetch (Durum Tara)", lambda: self._git_call("_start_worker", "fetch")),
                ("📥 Değişiklikleri Çek (Pull)", lambda: self._git_call("_start_worker", "pull")),
                ("📦 Geçici Sakla (Stash)", lambda: self._git_call("_start_worker", "stash")),
                ("📤 Geri Al (Stash Pop)", lambda: self._git_call("_start_worker", "stash_pop")),
                ("📊 Git Raporu", lambda: self._git_call("on_report_clicked")),
                ("🔄 Git Durumunu Yenile", lambda: self._git_refresh()),
            ],
        }

    def _git_call(self, method: str, *args) -> None:
        """Sürüm & Git ekranındaki (gömülü) GitTrackerScreen yöntemini çağırır."""
        tab = getattr(self, "git_tracker_tab", None)
        screen = getattr(tab, "screen", None)
        fn = getattr(screen, method, None)
        if fn is None:
            logger.warning("Git ekranı işlemi bulunamadı: %s", method)
            return
        fn(*args)

    def _git_profile_call(self, name: str) -> None:
        """Git bağlantı profili panelinin (sağ paneldeki GİT BAĞLANTISI) bir işlemini çalıştırır."""
        tab = getattr(self, "git_tracker_tab", None)
        panel = getattr(getattr(tab, "screen", None), "profile_panel", None)
        target = getattr(panel, name, None)
        if target is None:
            logger.warning("Git profil işlemi bulunamadı: %s", name)
            return
        target.click() if name.startswith("btn_") else target()

    def _git_refresh(self) -> None:
        """'Git Durumunu Yenile': işlem sonucunu ekranda ve bildirimde açıkça gösterir."""
        tab = getattr(self, "git_tracker_tab", None)
        if tab is None:
            return
        self.toast_requested.emit(tab.refresh_all(), "success")

    #: uzun işlem listelerini açılır alt menülere böler: {panel_id: [(başlık, işlem sayısı, açık mı)]}
    ACTION_GROUPS = {
        "surum_git": [("👤 PROFİL İŞLEMLERİ", 5, False), ("🌿 GİT İŞLEMLERİ", 7, True)],
        "portal_yayin": [
            ("👤 PROFİL İŞLEMLERİ", 3, True), ("🚀 GÖNDERİM", 3, True),
            ("🔑 GÜNCELLEME ANAHTARI", 2, False), ("❓ YARDIM & GEÇMİŞ", 2, False),
        ],
    }

    def _panel_actions(self, panel_id: str) -> list:
        return self._actions_map().get(panel_id, [
            ("💾 Kaydet", lambda: self.save_current_panel()),
            ("➕ Yeni Ekle", lambda: self.new_current_panel()),
            ("❌ Sil", lambda: self.delete_current_panel()),
        ])

    def _panel_context_actions(self) -> list:
        """Sağ tık menüsü için (kodlu etiket, geri çağrı) listesi — aktif menünün işlemleri."""
        pid = self.active_panel_id or ""
        return [
            (sm.with_code(label, sm.action_code(pid, i), self.show_codes), cb, sm.tooltip(label, sm.action_code(pid, i), self.code_mode))
            for i, (label, cb) in enumerate(self._panel_actions(pid), start=1)
        ]

    def _build_sub_action_box(self, panel_id: str) -> QFrame:
        """Bir menünün işlem butonlarını (sağ paneldeki İŞLEMLER bölümünde) oluşturur. Her butonun bir kodu vardır.
        Uzun listeler `ACTION_GROUPS` ile açılır alt menülere bölünür."""
        box = QFrame()
        box.setStyleSheet("QFrame { background: transparent; border: none; }")
        lyt = QVBoxLayout(box)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(3)
        box.action_buttons = []   # (buton, etiket, kod)
        box.groups = []           # (bölüm, varsayılan açık mı)
        actions = self._panel_actions(panel_id)
        plan = self.ACTION_GROUPS.get(panel_id) or [(None, len(actions), True)]
        pos = 0
        for title, count, opened in plan:
            target = lyt
            if title:
                sec = CollapsibleSection(title, is_expanded=opened, compact=True)
                lyt.addWidget(sec)
                box.groups.append((sec, opened))
            for label, callback in actions[pos:pos + count]:
                pos += 1
                code = sm.action_code(panel_id, pos)
                btn = CodedButton(label, code, show_code=self.show_codes)
                btn.setToolTip(sm.tooltip(label, code, self.code_mode))
                btn.setStyleSheet(self.btn_style())
                btn.clicked.connect(lambda _=False, cb=callback: cb())
                (sec.add_widget(btn) if title else target.addWidget(btn))
                box.action_buttons.append((btn, label, code))
        return box

    def _expand_action_groups(self, query: str) -> None:
        """Sağ panel araması sürerken alt menüler açılır (eşleşen işlem gizli kalmasın); temizlenince varsayılana döner."""
        for box in getattr(self, "menu_sub_boxes", {}).values():
            for sec, opened in getattr(box, "groups", []):
                sec.set_expanded(True if query.strip() else opened)

    def set_code_mode(self, mode: str) -> None:
        """Kod gösterimi: 'ipucu' (üzerine gelince), 'rozet' (adın altında), 'gizli'. Tercih kaydedilir."""
        if mode not in dict(sm.CODE_MODES):
            mode = "ipucu"
        self.code_mode = mode
        self.show_codes = mode == "rozet"
        sm.set_code_mode(self.db, mode)
        badge = self.show_codes
        for sec, _base, code in getattr(self, "_group_sections", []):
            sec.set_code(code if badge else "")
            sec.header_btn.setToolTip(sm.tooltip(_base, code, mode))
        for pid, (btn, name, _g) in ((p, (v[0], v[2], v[3])) for p, v in self.menu_item_containers.items()):
            btn.set_code_visible(badge)
            btn.setToolTip(sm.tooltip(name, sm.item_code(pid), mode))
        for box in getattr(self, "menu_sub_boxes", {}).values():
            for btn, label, code in box.action_buttons:
                btn.set_code_visible(badge)
                btn.setToolTip(sm.tooltip(label, code, mode))
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.set_code_mode(mode)
        if hasattr(self, "cmb_code_mode") and self.cmb_code_mode.currentData() != mode:
            self.cmb_code_mode.setCurrentIndex(self.cmb_code_mode.findData(mode))
        self._refresh_breadcrumb()

    def _refresh_breadcrumb(self) -> None:
        pid = self.active_panel_id
        if pid and hasattr(self, "lbl_breadcrumb"):
            self.lbl_breadcrumb.setText(self._breadcrumb_text(pid))

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
        for inner, _t, _c in self.menu_inner_all:
            inner.set_expanded(True)

    def collapse_all_sections(self):
        for sec in self.menu_sections:
            sec.set_expanded(False)
        for inner, _t, _c in self.menu_inner_all:
            inner.set_expanded(False)

    def _open_menu_path(self, panel_id: str) -> None:
        """Menünün bağlı olduğu grubu ve (varsa) alt menüyü açar."""
        if panel_id in self.menu_item_containers:
            self.menu_item_containers[panel_id][1].set_expanded(True)
        inner = self.menu_inner_sections.get(panel_id)
        if inner is not None:
            inner.set_expanded(True)

    def filter_menu_tree(self, query: str):
        """Menü arama kutusu: menü adı, alt menü, grup adı VE kodları ile eşleşenleri gösterir."""
        q = query.strip()
        if not q:
            for item_widget, _sec, _, _ in self.menu_item_containers.values():
                item_widget.show()
            for inner, _t, _c in self.menu_inner_all:
                inner.show()
            self.collapse_all_sections()
            if self.active_panel_id:
                self._open_menu_path(self.active_panel_id)
            return

        for panel_id, (item_widget, _sec, menu_adi, grup_adi) in self.menu_item_containers.items():
            sub = sm.subgroup_of(grup_adi, panel_id) or ("", "")
            matches = sm.matches(q, menu_adi, grup_adi, sm.item_code(panel_id), sm.GROUP_CODES.get(grup_adi, ""), sub[0], sub[1])
            item_widget.setVisible(matches)
            if matches:
                self._open_menu_path(panel_id)
        for inner, _t, _c in self.menu_inner_all:
            visible = any(pid for pid, host in self.menu_inner_sections.items()
                          if host is inner and not self.menu_item_containers[pid][0].isHidden())
            inner.setVisible(visible)

    def on_menu_clicked(self, panel_id: str, btn: QPushButton) -> None:
        """Menü butonuna tıklanınca panel değiştir ve alt eylemleri aç."""
        for b in self.menu_buttons.values():
            b.setChecked(False)
            b.setStyleSheet(self.menu_btn_style(active=False))
        btn.setChecked(True)
        btn.setStyleSheet(self.menu_btn_style(active=True))

        self._open_menu_path(panel_id)        # ait olduğu grup + alt menü açılır
        self.switch_panel(panel_id)

    def _breadcrumb_text(self, panel_id: str) -> str:
        """'Genel Ayarlar > [Alt menü >] Menü' — adlar kısa tutulur, bağlamı üst menüler verir."""
        if panel_id == "settings_hub":
            return f"⚙️ [{sm.SCREEN_CODE}] Genel Ayarlar > 🏠 Ayarlar Panosu"
        name, group = next(((m, g) for g, _i, ml in self.MENU_STRUCTURE for m, p in ml if p == panel_id), (panel_id, ""))
        sub = sm.subgroup_of(group, panel_id)
        path = " > ".join(x for x in ((sub[0].split(" ", 1)[-1] if sub else ""), name) if x)
        code = sm.item_code(panel_id)
        return (f"⚙️ [{sm.SCREEN_CODE}] Genel Ayarlar > {path}"
                + (f"  [{code}]" if self.code_mode != "gizli" and code else ""))

    @staticmethod
    def _darken_hex(hex_color: str, amount: float = 0.15) -> str:
        """Hex rengi hover durumu için koyulaştırır. Sabit açık gri hover
        (#f1f5f9) beyaz metinli renkli butonlarda (ör. mor "Getir") metni
        okunmaz hale getiriyordu; onun yerine her buton kendi renginin koyu
        tonuna geçer, böylece metin kontrastı her renkte korunur."""
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return hex_color
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        r, g, b = (max(0, int(c * (1 - amount))) for c in (r, g, b))
        return f"#{r:02x}{g:02x}{b:02x}"

    def btn_style(self, bg="#ffffff", fg="#1e293b") -> str:
        """Derinlikli düğme: alt kenar kalın (gölge hissi), üzerine gelince koyulaşır, basınca çöker."""
        return btn_style(bg, fg)

    def menu_btn_style(self, active: bool = False) -> str:
        """Asıl menü düğmesi: kart görünümlü, derinlikli; aktif olan mavi vurgulu."""
        if active:
            return """
                QPushButton {
                    background:#dbeafe; color:#1d4ed8;
                    border:1px solid #60a5fa; border-bottom:3px solid #2563eb; border-left:4px solid #2563eb;
                    border-radius:6px; padding:5px 8px; font-size:11px; font-weight:800;
                    text-align:left; min-height:24px;
                }
            """
        return """
            QPushButton {
                background:#ffffff; color:#334155;
                border:1px solid #cbd5e1; border-bottom:3px solid #94a3b8; border-left:4px solid #e2e8f0;
                border-radius:6px; padding:5px 8px; font-size:11px; font-weight:600;
                text-align:left; min-height:24px;
            }
            QPushButton:hover {
                background:#eff6ff; color:#1d4ed8; border-color:#93c5fd; border-left:4px solid #60a5fa;
            }
            QPushButton:pressed { border-bottom:1px solid #94a3b8; padding-top:7px; }
        """

    def _current_user_key(self) -> str:
        """Sıralama tercihi kullanıcıya göre saklanır (ana pencereden oturum kullanıcısı)."""
        try:
            return str((getattr(self.window(), "user_config", None) or {}).get("username", "") or "")
        except Exception:  # noqa: BLE001
            return ""

    def build_right_sidebar(self) -> QWidget:
        """Sağ sidebar — sürükle-bırak ile sıralanabilen, TÜMÜ KAPALI gelen, isim/kod aranabilen bölümler:
        İşlemler (seçili menünün), Filtreleme, Yazdır & Aktar, Hızlı İşlemler, Döviz."""
        self.right_panel = EdgeTriggeredPanel(side="right", default_width=300, parent=self)
        store = sm.SidebarOrderStore(self.db, self._current_user_key())
        self.right_sidebar = ReorderableSidebar(store, show_codes=self.show_codes)
        sb = self.right_sidebar
        lbl_style = "font-size:10px; font-weight:bold; color:#475569;"

        def section(key: str, title: str) -> CollapsibleSection:
            return CollapsibleSection(title, is_expanded=False)

        def reg(key: str, items: list, widget, text: str) -> None:
            """Bölüme ait aranabilir/kodlu bir öğe kaydeder (kod: sys.rp.<bölüm>.<sıra>)."""
            code = f"{sm.SIDEBAR_SECTIONS[key][0]}.{len(items) + 1:02d}"
            widget.setToolTip(sm.tooltip(text, code, self.code_mode))
            items.append((widget, text, code))

        # ── İŞLEMLER: seçili menünün işlemleri (menü değişince içerik değişir) ──
        sec_ops = section("islemler", "⚡ İŞLEMLER")
        # Yalnızca seçili menünün kutusu görünür (QStackedWidget en uzun sayfa kadar boşluk bırakırdı).
        self.actions_stack = QWidget()
        stack_lyt = QVBoxLayout(self.actions_stack)
        stack_lyt.setContentsMargins(0, 0, 0, 0)
        self.menu_sub_boxes = _LazyActionBoxes(self, stack_lyt)   # kutular menüye girilince kurulur
        sec_ops.add_widget(self.actions_stack)
        sb.add_section("islemler", sec_ops, sm.SIDEBAR_SECTIONS["islemler"][0])

        # ── FİLTRELEME & ARAMA ──
        sec_filter = section("filtre", "🔍 FİLTRE & ARAMA")
        items: list = []
        lbl_s = QLabel("Tablo İçi Canlı Arama:")
        lbl_s.setStyleSheet(lbl_style)
        self.txt_right_filter = QLineEdit()
        self.txt_right_filter.setPlaceholderText("Aktif tabloda ara...")
        self.txt_right_filter.setClearButtonEnabled(True)
        self.txt_right_filter.setStyleSheet(with_tooltip("border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px; background: white; font-size: 11px;"))
        self.txt_right_filter.textChanged.connect(self.filter_active_table)
        lbl_st = QLabel("Durum:")
        lbl_st.setStyleSheet(lbl_style)
        self.cmb_right_status = QComboBox()
        self.cmb_right_status.addItems(["Tümü", "Aktif", "Pasif"])
        self.cmb_right_status.setStyleSheet(with_tooltip("border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px; background: white; font-size: 11px; combobox-popup: 0;"))
        self.cmb_right_status.currentTextChanged.connect(self.filter_active_table_status)
        for w in (lbl_s, self.txt_right_filter, lbl_st, self.cmb_right_status):
            sec_filter.add_widget(w)
        reg("filtre", items, self.txt_right_filter, "Tablo içi canlı arama")
        reg("filtre", items, self.cmb_right_status, "Durum filtresi")
        sb.add_section("filtre", sec_filter, sm.SIDEBAR_SECTIONS["filtre"][0], items)

        # ── YAZDIR & AKTAR ──
        sec_export = section("yazdir", "🖨️ YAZDIR & AKTAR")
        items = []
        for text, style, cb in (
            ("🖨️ Yazdır / Önizleme", self.btn_style("#ffffff", "#0f172a"), self.print_active_panel),
            ("📄 PDF Olarak Kaydet", self.btn_style("#ffffff", "#0f172a"), self.export_active_to_pdf),
            ("📊 Excel'e Aktar (.xlsx)", self.btn_style("#f0fdf4", "#166534"), self.export_active_to_excel),
            ("📥 Excel'den Al (.xlsx)", self.btn_style("#f0fdf4", "#166534"), self.import_active_from_excel),
        ):
            b = CodedButton(text, f"{sm.SIDEBAR_SECTIONS['yazdir'][0]}.{len(items) + 1:02d}", show_code=self.show_codes)
            b.setStyleSheet(style)
            b.clicked.connect(cb)
            sec_export.add_widget(b)
            reg("yazdir", items, b, text)
        sb.add_section("yazdir", sec_export, sm.SIDEBAR_SECTIONS["yazdir"][0], items)

        # ── HIZLI İŞLEMLER ── ("Kaydet" burada YOK: alt bar + F2 tek yer)
        sec_tools = section("hizli", "⚡ HIZLI İŞLEMLER")
        items = []
        for text, style, cb in (
            ("🔄 Verileri Yenile (F5)", self.btn_style(), self.refresh_active_panel),
            ("⚙️ Sütunları Yapılandır", self.btn_style("#ffffff", "#475569"), self.open_active_column_manager),
        ):
            b = CodedButton(text, f"{sm.SIDEBAR_SECTIONS['hizli'][0]}.{len(items) + 1:02d}", show_code=self.show_codes)
            b.setStyleSheet(style)
            b.clicked.connect(cb)
            sec_tools.add_widget(b)
            reg("hizli", items, b, text)
        sb.add_section("hizli", sec_tools, sm.SIDEBAR_SECTIONS["hizli"][0], items)

        # ── DÖVİZ & KUR'A ÖZGÜ BÖLÜMLER — yalnız "Döviz & Kur" paneli aktifken görünür ──
        sec_doviz = self._build_doviz_sag_panel_islemler()
        sec_doviz.set_expanded(False)
        sb.add_section("doviz", sec_doviz, sm.SIDEBAR_SECTIONS["doviz"][0])
        sec_rapor = self._build_doviz_sag_panel_raporlar()
        sb.add_section("kur_rapor", sec_rapor, sm.SIDEBAR_SECTIONS["kur_rapor"][0])
        sb.set_section_visible("doviz", False)
        sb.set_section_visible("kur_rapor", False)

        # ── GİT BAĞLANTISI: profil ekle/düzenle/sil + Google ile giriş (yalnız Sürüm & Git menüsünde) ──
        # Bu bölüm gömülü Git ekranının (kabukta gizli) sol panelindeydi; kullanıcı ulaşamıyordu.
        sec_git = section("git_baglanti", "🌐 GİT BAĞLANTISI")
        git_screen = self.git_tracker_tab.screen
        panel = git_screen.profile_panel
        sec_git.add_widget(panel)
        git_items: list = []
        for widget, text in ((panel.btn_add, "Bağlantı profili ekle"), (panel.btn_edit, "Profili düzenle"),
                             (panel.btn_hide, "Profili sil (gizle)"), (panel.btn_activate, "Etkin yap"),
                             (panel.btn_test, "Bağlantıyı test et"), (panel.btn_login, "Google ile giriş yap")):
            git_items.append((widget, text, f"{sm.SIDEBAR_SECTIONS['git_baglanti'][0]}.{len(git_items) + 1:02d}"))
        sb.add_section("git_baglanti", sec_git, sm.SIDEBAR_SECTIONS["git_baglanti"][0], git_items)
        sb.set_code_mode(self.code_mode)
        sb.set_section_visible("git_baglanti", False)
        sb.search.textChanged.connect(self._expand_action_groups)
        panel.message.connect(lambda text, ok: self.toast_requested.emit(text, "success" if ok else "error"))

        wrap = QWidget()
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(4, 4, 4, 4)
        wl.addWidget(sb)
        self.right_panel.set_content(wrap)
        return self.right_panel

    def _build_doviz_sag_panel_islemler(self) -> QWidget:
        """Sağ panel > 💱 Döviz İşlemleri — Toplu Kur Çek/Sil ve Serbest Piyasa
        adres yönetimi burada toplanır; bunlar günlük değil, ara sıra
        yapılan işlemler olduğundan üst araç çubuğunu kalabalıklaştırmazlar."""
        sec = CollapsibleSection("💱 DÖVİZ İŞLEMLERİ", is_expanded=False)

        lbl_style = "font-size:10px; font-weight:bold; color:#475569;"

        lbl_adres = QLabel("Serbest Piyasa Kaynağı:")
        lbl_adres.setStyleSheet(lbl_style)
        # Serbest metin/tekil adres yerine adlandırılmış, test edilebilir
        # kaynak kayıtları — ⚙ butonu Ekle/Düzenle/Test Et/Sil penceresini açar.
        self.txt_doviz_kaynak_url = SerbestPiyasaKaynakField(db_session=self.db)
        self.txt_doviz_kaynak_url.setToolTip(
            "Serbest Piyasa kaynağı için kayıtlı adres. ⚙ ile kaynak ekleyin, "
            "düzenleyin, test edin ya da silin.",
        )
        sec.add_widget(lbl_adres)
        sec.add_widget(self.txt_doviz_kaynak_url)

        # ⚙ ikonu fark edilmiyordu: ekle/düzenle/test/sil yönetimi görünür bir butonla da açılır.
        btn_kaynak_yonet = QPushButton("🌐 Kaynakları Yönet (Ekle / Düzenle / Sil)")
        btn_kaynak_yonet.setStyleSheet(self.btn_style("#0f766e", "#ffffff"))
        btn_kaynak_yonet.setToolTip(
            "Serbest Piyasa kaynak adreslerini ekleyin, düzenleyin, test edin veya silin.",
        )
        btn_kaynak_yonet.clicked.connect(self.txt_doviz_kaynak_url._manage)
        sec.add_widget(btn_kaynak_yonet)

        lbl_toplu = QLabel("Toplu İşlem Tarih Aralığı:")
        lbl_toplu.setStyleSheet(lbl_style)
        sec.add_widget(lbl_toplu)

        tarih_row = QHBoxLayout()
        self.dt_toplu_bas = QDateEdit(QDate.currentDate().addDays(-7))
        self.dt_toplu_bas.setCalendarPopup(True)
        self.dt_toplu_bas.setDisplayFormat("dd.MM.yyyy")
        self.dt_toplu_bit = QDateEdit(QDate.currentDate())
        self.dt_toplu_bit.setCalendarPopup(True)
        self.dt_toplu_bit.setDisplayFormat("dd.MM.yyyy")
        tarih_row.addWidget(self.dt_toplu_bas)
        tarih_row.addWidget(QLabel("—"))
        tarih_row.addWidget(self.dt_toplu_bit)
        sec.add_layout(tarih_row)

        btn_cek = QPushButton("⚡ Toplu Kur Çek")
        btn_cek.setStyleSheet(self.btn_style("#0284c7", "#ffffff"))
        btn_cek.setToolTip(
            "Seçili tarih aralığındaki her gün için, üst çubukta seçili "
            "kaynaktan kur çekip geçmişe kaydeder.",
        )
        btn_cek.clicked.connect(self._on_doviz_toplu_cek_clicked)
        sec.add_widget(btn_cek)

        btn_sil = QPushButton("🗑️ Aralığı Sil")
        btn_sil.setStyleSheet(self.btn_style("#fee2e2", "#991b1b"))
        btn_sil.setToolTip(
            "Seçili döviz gridde işaretliyse yalnız o dövizin, değilse tüm "
            "dövizlerin bu tarih aralığındaki geçmiş kur kayıtlarını siler.",
        )
        btn_sil.clicked.connect(self._on_doviz_toplu_sil_clicked)
        sec.add_widget(btn_sil)

        # Kaynak/adres ayarları, hem üst çubuktaki Kaynak combosu hem de bu
        # adres alanı kurulduktan SONRA yüklenir/bağlanır.
        self._load_doviz_kaynak_ayarlari()
        self.txt_doviz_kaynak_url.changed.connect(self._save_doviz_kaynak_ayarlari)

        return sec

    def _build_doviz_sag_panel_raporlar(self) -> QWidget:
        """Sağ panel > 📊 Kur Raporları — şimdilik sağ panele gömülü değil,
        `CurrencyRateReportWidget`'ı tam ekran bir popup pencerede açan bir
        buton olarak sunulur (bkz. `_open_doviz_rapor_popup`)."""
        sec = CollapsibleSection("📊 KUR RAPORLARI", is_expanded=False)
        info = QLabel(
            "Çekilen kurları döviz kodu ve tarih aralığına göre tam ekran "
            "raporda görüntüleyin.",
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748b; font-size:11px;")
        sec.add_widget(info)
        btn_ac = QPushButton("🔍 Tam Ekran Görüntüle")
        btn_ac.setStyleSheet(self.btn_style("#0891b2", "#ffffff"))
        btn_ac.clicked.connect(self._open_doviz_rapor_popup)
        sec.add_widget(btn_ac)
        self.doviz_rapor_widget = None
        return sec

    def _open_doviz_rapor_popup(self) -> None:
        """Kur Raporları'nı bağımsız, tam ekran (maximized) bir pencerede açar."""
        dlg = QDialog(self)
        dlg.setWindowTitle("📊 Kur Raporları")
        lyt = QVBoxLayout(dlg)
        lyt.setContentsMargins(12, 12, 12, 12)
        self.doviz_rapor_widget = CurrencyRateReportWidget(db_session=self.db)
        lyt.addWidget(self.doviz_rapor_widget)
        dlg.showMaximized()
        from src.desktop.ui.components.window_fit_helper import zorla_ilk_yerlesim
        zorla_ilk_yerlesim(dlg)
        dlg.exec()
        self.doviz_rapor_widget = None

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
        elif self.active_panel_id == "yetkiler":
            return getattr(self, "tbl_yetkiler", None)
        elif self.active_panel_id == "doviz_kur":
            grid = getattr(self, "doviz_grid", None)
            return grid.table_view if grid is not None else None
        elif self.active_panel_id == "odeme_planlari":
            return getattr(self, "tbl_odeme", None)
        elif self.active_panel_id == "banka_odeme_planlari":
            return getattr(self, "tbl_banka_odeme", None)
        elif self.active_panel_id == "fiyat_listeleri":
            return getattr(self, "tbl_fiyat", None)
        elif self.active_panel_id == "stok_kategoriler":
            return getattr(self, "tbl_kategori", None)
        elif self.active_panel_id == "stok_markalar":
            return getattr(self, "tbl_marka", None)
        elif self.active_panel_id == "birim_tanimlari":
            return getattr(self, "tbl_birim", None)
        elif self.active_panel_id == "cari_gruplari":
            return getattr(self, "tbl_cari_grup", None)
        elif self.active_panel_id == "kdv_oranlari":
            return getattr(self, "tbl_kdv", None)
        elif self.active_panel_id == "form_tasarimlari":
            return getattr(self, "tbl_form_tasarim", None)
        elif self.active_panel_id == "numara_serileri":
            if hasattr(self, "doc_num_tab") and hasattr(self.doc_num_tab, "grid"):
                return getattr(
                    self.doc_num_tab.grid,
                    "table_view",
                    getattr(self.doc_num_tab.grid, "table", None),
                )
        return None

    def _add_table_row(self, table: QTableWidget | None, default_vals: list[str]):
        """Belirtilen QTableWidget tablosuna yeni bir satır ekler."""
        if not table:
            return
        r = table.rowCount()
        table.insertRow(r)
        for c, val in enumerate(default_vals):
            table.setItem(r, c, QStandardItem(val))
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
            "numara_serileri": "doc_num_tab",
            "cms_baglantilari": "sites_tab",
            "kullanicilar": "users_tab",
            "roller": "roller_tab",
            "gorunum_profilleri": "view_settings_tab",
            "ekran_grid": "screen_defs_tab",
            "portal_yayin": "portal_deploy_tab",
            "adres_tanimlari": "address_tab",
            "vergi_daireleri": "tax_tab",
            "banka_tanimlari": "bank_tab",
            "settings_hub": "hub_tab",
        }
        attr = m.get(self.active_panel_id)
        return getattr(self, attr, None) if attr else None

    @staticmethod
    def _tablo_boyut(table) -> tuple[int, int]:
        """`QTableWidget` (AppGrid) ya da model'li `QTableView` (standart tanım tablosu) fark etmeden (satır, sütun)."""
        if isinstance(table, QTableWidget):
            return table.rowCount(), table.columnCount()
        model = table.model()
        return (model.rowCount(), model.columnCount()) if model else (0, 0)

    @staticmethod
    def _tablo_metin(table, r: int, c: int) -> str:
        if isinstance(table, QTableWidget):
            it = table.item(r, c)
            return it.text() if it else ""
        model = table.model()
        return str(model.data(model.index(r, c)) or "") if model else ""

    def filter_active_table(self, query: str):
        """Aktif tablodaki satırları arama metnine göre filtreler."""
        emb = self._active_embedded_widget()
        if emb is not None and hasattr(emb, "apply_quick_search"):
            emb.apply_quick_search(query)
            return
        table = self._get_active_table()
        if not table:
            return
        rows, cols = self._tablo_boyut(table)
        q = query.strip().lower()
        for r in range(rows):
            match = any(q in self._tablo_metin(table, r, c).lower() for c in range(cols))
            table.setRowHidden(r, not match if q else False)

    def filter_active_table_status(self, status: str):
        """Aktif tablodaki satırları durum değerine göre filtreler."""
        emb = self._active_embedded_widget()
        if emb is not None and hasattr(emb, "apply_status_filter"):
            emb.apply_status_filter(status)
            return
        table = self._get_active_table()
        if not table:
            return
        status = status.strip().lower()
        rows, cols = self._tablo_boyut(table)
        for r in range(rows):
            if status == "tümü":
                table.setRowHidden(r, False)
                continue
            row_status = self._tablo_metin(table, r, cols - 1).strip().lower()
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
        if not table or not hasattr(table, "insertRow"):  # AppGrid (QTableWidget) ve EntryTableView ikisi de destekler
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
                    table.setItem(r, c, QStandardItem(str(row.iloc[c])))
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
        html = self._generate_table_html(table, f"TOYA ERP — {self.lbl_breadcrumb.text()}")
        self._show_print_preview(html)

    def _show_print_preview(self, html: str) -> None:
        """Verilen HTML içeriğini yazdırma önizleme diyaloğunda açar —
        panel tablosu (`print_active_panel`) ve özel raporlar (ör. Döviz &
        Kur'un tarih aralığı çıktısı) tarafından ortak kullanılır."""
        try:
            from PyQt6.QtGui import QTextDocument
            from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog

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
        """Tablodan (QTableWidget veya model'li QTableView) başlık+satırları
        çıkarıp `_generate_html_table` ile şık bir kurumsal HTML rapor üretir."""
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

        return self._generate_html_table(headers, rows, title)

    @staticmethod
    def _generate_html_table(headers: list[str], rows: list[list[str]], title: str) -> str:
        """Başlık + satır listelerinden şık bir kurumsal HTML rapor tablosu üretir."""
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

    def build_body(self) -> QStackedWidget:
        """Sağ body — paneller burada gösterilir."""
        self.stack = QStackedWidget()

        panel_builders = {
            "settings_hub": self.build_settings_hub_panel,
            "firma_bilgileri": self.build_firma_bilgileri_panel,
            "numara_serileri": self.build_numara_serileri_panel,
            "cms_baglantilari": self.build_cms_baglantilari_panel,
            "adres_tanimlari": self.build_adres_tanimlari_panel,
            "vergi_daireleri": self.build_vergi_daireleri_panel,
            "banka_tanimlari": self.build_banka_tanimlari_panel,
            "kullanicilar": self.build_kullanicilar_panel,
            "roller": self.build_roller_panel,
            "yetkiler": self.build_yetkiler_panel,
            "doviz_kur": self.build_doviz_panel,
            "odeme_planlari": self.build_odeme_planlari_panel,
            "banka_odeme_planlari": self.build_banka_odeme_planlari_panel,
            "fiyat_listeleri": self.build_fiyat_listeleri_panel,
            "stok_kategoriler": self.build_stok_kategoriler_panel,
            "stok_markalar": self.build_stok_markalar_panel,
            "birim_tanimlari": self.build_birim_panel,
            "stok_ozel_alanlar": lambda: self.build_ozel_alan_panel("stok"),
            "cari_gruplari": self.build_cari_gruplari_panel,
            "cari_ozel_alanlar": lambda: self.build_ozel_alan_panel("cari"),
            "eposta_smtp": self.build_eposta_smtp_panel,
            "online_portal": self.build_online_portal_panel,
            "portal_yayin": self.build_portal_yayin_panel,
            "yedek_merkezi": self.build_yedek_merkezi_panel,
            "portal_yedek": self.build_portal_yedek_panel,
            "guvenlik": self.build_guvenlik_panel,
            "kdv_oranlari": self.build_kdv_panel,
            "sayi_bicimi": self.build_sayi_bicimi_panel,
            "gorunum_profilleri": self.build_gorunum_panel,
            "ekran_grid": self.build_ekran_grid_panel,
            "form_tasarimlari": self.build_form_tasarimlari_panel,
            "surum_git": self.build_surum_panel,
            "yardim": self.build_yardim_panel,
        }

        for panel_id, builder in panel_builders.items():
            panel = builder()
            self.panels[panel_id] = panel
            self.stack.addWidget(panel)
            self._install_panel_context_menu(panel)

        return self.stack

    def _install_panel_context_menu(self, panel: QWidget) -> None:
        """Düz (kendi bağlam menüsü olmayan) panellerin boş alanına sağ tık: seçili menünün işlemleri."""
        if isinstance(panel, (AppGrid, QTableWidget)) or getattr(panel, "embedded", False):
            return
        panel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        panel.customContextMenuRequested.connect(lambda pos, p=panel: self._show_panel_context_menu(p, pos))

    def _show_panel_context_menu(self, source: QWidget, pos) -> None:
        from src.desktop.managers.theme_manager import ThemeManager

        menu = QMenu(self)
        try:
            menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())
        except Exception:  # noqa: BLE001
            pass
        menu.setToolTipsVisible(True)
        for label, cb, tip in self._panel_context_actions():
            act = menu.addAction(label)
            act.setToolTip(tip)
            act.triggered.connect(lambda _=False, c=cb: c())
        if not menu.isEmpty():
            menu.exec(source.mapToGlobal(pos))

    def switch_panel(self, panel_id: str) -> None:
        """Aktif paneli değiştirir."""
        self.active_panel_id = panel_id
        if panel_id in self.panels:
            self.stack.setCurrentWidget(self.panels[panel_id])
        if self._oranli_gridler:
            QTimer.singleShot(0, self._oranli_yenile)

        # Settings Hub aktifken kenar panelleri kapatıp geniş ferah bir görünüm sunar
        if panel_id == "settings_hub":
            if hasattr(self, "left_panel") and self.left_panel.is_open:
                self.left_panel.close_panel()
            if hasattr(self, "right_panel") and self.right_panel.is_open:
                self.right_panel.close_panel()
        else:
            if hasattr(self, "left_panel") and not self.left_panel.is_open:
                self.left_panel.open_panel()
            if hasattr(self, "right_panel") and not self.right_panel.is_open:
                self.right_panel.open_panel()

        # Panele özgü sağ panel bölümleri — yalnız ilgili panel aktifken görünür.
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.set_section_visible("doviz", panel_id == "doviz_kur")
            self.right_sidebar.set_section_visible("kur_rapor", panel_id == "doviz_kur")
            self.right_sidebar.set_section_visible("git_baglanti", panel_id == "surum_git")
        if panel_id == "doviz_kur":
            self._maybe_prompt_initial_currencies()
            if getattr(self, "doviz_rapor_widget", None):
                self.doviz_rapor_widget.refresh()

        # Buton aktifliğini ayarla
        if panel_id in self.menu_buttons:
            for pid, b in self.menu_buttons.items():
                is_cur = pid == panel_id
                b.setChecked(is_cur)
                b.setStyleSheet(self.menu_btn_style(active=is_cur))

        # İşlemler bölümünü seçili menünün işlemlerine çevir
        if hasattr(self, "menu_sub_boxes"):
            box = self.menu_sub_boxes[panel_id]           # ilk erişimde kurulur
            for pid, other in self.menu_sub_boxes.items():
                other.setVisible(pid == panel_id)
            self.right_sidebar.set_items("islemler", [(b, label, code) for b, label, code in box.action_buttons])

        # Başlığı güncelle
        if hasattr(self, "lbl_breadcrumb"):
            self.lbl_breadcrumb.setText(self._breadcrumb_text(panel_id))

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
            if t is not None:
                n, _c = self._tablo_boyut(t)
        self.lbl_bottom_count.setText(f"📊 {n} kayıt" if n is not None else "")

    @staticmethod
    def _tr_upper(text: str) -> str:
        return text.replace("i", "İ").replace("ı", "I").upper()

    @staticmethod
    def _panel_baslik(lyt: QVBoxLayout, ikon_baslik: str, aciklama: str) -> None:
        """Panel başlığı standardı: `<emoji> Başlık` (koyu lacivert) + altında gri açıklama. Tüm tanım panelleri
        bunu kullanır (bkz. `gelistirme/00_mimari/GRID_STANDARDI.md`, YZ2 Görev 27 madde B)."""
        lbl = QLabel(ikon_baslik)
        lbl.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(lbl)
        if aciklama:
            lbl_info = QLabel(aciklama)
            lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
            lbl_info.setWordWrap(True)
            lyt.addWidget(lbl_info)

    def _aktif_firma_uyar(self, ne_icin: str) -> None:
        """Firmaya bağlı bir ayar (Şube/Dönem/Birim/...) kaydedilmek istendiğinde aktif firma yoksa çağrılır;
        hiç firma tanımlanmamışsa ve birden çok firma olup hiçbiri seçilmemişse FARKLI mesaj gösterir
        (2026-09-30) — "birden fazla dönem/şube olabilir" isteğiyle aynı oturumda, aktif_firma() belirsiz
        (>1 firma, hiçbiri seçilmemiş) durumunda kullanıcıyı yanlış yönlendirmemek için."""
        from src.desktop.services.company_service import CompanyService
        if len(CompanyService(self.db).list_companies()) > 1:
            QMessageBox.warning(self, "Aktif Firma Seçilmedi",
                                 f"{ne_icin} için önce Firma Bilgileri'nden çalışacağınız firmayı aktif olarak seçin.")
        else:
            QMessageBox.warning(self, "Firma Seçili Değil",
                                 f"{ne_icin} için önce Firma Bilgileri'nden bir firma tanımlayın.")

    def _new_grid(self, name: str, labels: list[str], stretch: int | None = None, editable: bool = True) -> EntryTableView:
        """Standart tanım tablosu (`standart_grid`, bkz. `gelistirme/00_mimari/GRID_STANDARDI.md`). Sütun anahtarları
        `c0..cN` (KOD İÇİNDE DEĞİŞTİRME — kayıtlı görünüm profilleri buna bağlı), başlıklar BÜYÜK harf. `stretch` sütunu
        ilk gösterimde diğerlerinin 3 katı genişlik alır; kullanıcı bir sütunu elle boyutlandırınca oran durur (bkz.
        `_oranli_kur`, `FisKalemGrid._oranli_genislik`/`showEvent` deseniyle aynı fikir). `editable=False` ise çağıran
        taraf hücreleri salt okunur yapar (bkz. `tv._toya_editable`, örn. rol × yetki matrisi).
        Dönen değer `EntryTableView`; ekleme için kapsayıcı `tablo.container` (`FilterableTableView`) niteliğindedir."""
        pid = f"dbgrid_ayar_{name}"
        kolonlar = [(f"c{i}", self._tr_upper(lbl)) for i, lbl in enumerate(labels)]
        entry = standart_grid(pid, kolonlar)
        tv = entry.table_view
        tv.container = entry
        tv._toya_editable = editable
        tv.context_actions_provider = self._panel_context_actions
        tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tv.customContextMenuRequested.connect(lambda pos, t=tv: self._ayar_grid_menu(t, pos))
        self._oranli_kur(tv, [3.0 if i == stretch else 1.0 for i in range(len(labels))])
        return tv

    def _oranli_kur(self, tv: EntryTableView, weights: list[float]) -> None:
        """`stretch` sütununun ilk gösterimde oranlı genişlemesini kurar; kullanıcı bir sütunu elle boyutlandırınca
        kalıcı olarak durur (bkz. `FisKalemGrid._oranli_genislik`/`showEvent` deseni — burada `EntryGridBase`'e
        bağlanmadan aynı fikir dışarıdan, `switch_panel`'in tetiklediği tek noktadan uygulanır)."""
        durum = {"oranli": True, "uyguluyor": False}

        def uygula() -> None:
            if not durum["oranli"] or not tv.isVisible():
                return
            toplam = sum(weights) or 1.0
            w = max(tv.viewport().width(), 300)
            durum["uyguluyor"] = True
            for i, wt in enumerate(weights):
                tv.setColumnWidth(i, max(40, int(w * wt / toplam)))
            durum["uyguluyor"] = False

        def kullanici_boyutlandirdi(*_a) -> None:
            if not durum["uyguluyor"]:
                durum["oranli"] = False

        tv.horizontalHeader().sectionResized.connect(kullanici_boyutlandirdi)
        self._oranli_gridler.append(uygula)

    def _oranli_yenile(self) -> None:
        """Panel değişince (`switch_panel`) az önce görünür olan tanım tablolarının oranlı genişliğini uygular."""
        for uygula in self._oranli_gridler:
            uygula()

    def _ayar_grid_menu(self, tv: EntryTableView, pos) -> None:
        """Tanım tablosu sağ tık menüsü: panel eylemleri (Kaydet/Ekle/Sil…) + ayırıcı + sütun/profil yönetimi
        (bkz. `FisKalemGrid._baglam_menusu` deseni: eylemler + ayırıcı + `entry.add_column_actions_to_menu(menu)`)."""
        from src.desktop.managers.theme_manager import ThemeManager
        menu = QMenu(self)
        try:
            menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())
        except Exception:  # noqa: BLE001
            pass
        menu.setToolTipsVisible(True)
        for label, cb, tip in tv.context_actions_provider():
            act = menu.addAction(label)
            act.setToolTip(tip)
            act.triggered.connect(lambda _=False, c=cb: c())
        menu.addSeparator()
        tv.container.add_column_actions_to_menu(menu)
        if not menu.isEmpty():
            menu.exec(tv.viewport().mapToGlobal(pos))

    # ─────────────────────────────────────────────────────────────
    # PANEL BUILDERS
    # ─────────────────────────────────────────────────────────────

    def build_settings_hub_panel(self) -> QWidget:
        """Ayarlar Panosu / Karşılama Ekranı (3D İkon Grid)."""
        self.hub_tab = SettingsHubWidget(parent=self)
        self.hub_tab.navigate_requested.connect(self.switch_panel)
        return self.hub_tab

    def build_adres_tanimlari_panel(self) -> QWidget:
        """Ülkeler, İller, İlçeler, Semtler/Mahalleler Yönetimi."""
        self.address_tab = AddressDefinitionsWidget(db_session=self.db, parent=self)
        self.address_tab.toast_requested.connect(self.toast_requested)
        return self.address_tab

    def build_vergi_daireleri_panel(self) -> QWidget:
        """Vergi Daireleri Yönetimi."""
        self.tax_tab = TaxOfficesWidget(db_session=self.db, parent=self)
        self.tax_tab.toast_requested.connect(self.toast_requested)
        return self.tax_tab

    def build_banka_tanimlari_panel(self) -> QWidget:
        """Banka ve Şube Tanımları Yönetimi."""
        self.bank_tab = BankDefinitionsWidget(db_session=self.db, parent=self)
        self.bank_tab.toast_requested.connect(self.toast_requested)
        return self.bank_tab

    def build_firma_bilgileri_panel(self) -> QWidget:
        """Firma (Şirket) kimlik kartları listesi (kabuk içinde: yalnız içerik)."""
        from src.desktop.ui.screens.firma_list_widget import FirmaListWidget
        self.firma_tab = FirmaListWidget(self.db, embedded=True)
        self.firma_tab.companies_updated.connect(self.companies_updated.emit)
        return self.firma_tab

    def build_numara_serileri_panel(self) -> QWidget:
        """Belge ve Seri Numaralandırma Yönetimi (Firma bazlı, e-Fatura / GİB uyumlu)."""
        self.doc_num_tab = DocumentNumberingWidget(db_session=self.db, parent=self)
        self.doc_num_tab.toast_requested.connect(self.toast_requested)
        return self.doc_num_tab

    def build_cms_baglantilari_panel(self) -> QWidget:
        """CMS / ERP dış bağlantı yönetimi (eski 'Firma Bilgileri' içeriği)."""
        self.sites_tab = SitesWidget(self.db, embedded=True)
        return self.sites_tab

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
        self._panel_baslik(lyt, "🛡️ Rol × Yetki Matrisi", "Her rolün hangi yetkilere sahip olduğunu gösterir. "
                          "Değişiklik için 'Rol Tanımları'ndaki rol editörünü kullanın.")

        svc = RoleService(self.db)
        svc.seed_defaults()
        roles = svc.list_roles()
        role_perms = {r.name: set(svc.permissions_of(r)) for r in roles}

        codes = [f"{m}.{a}" for m, _mn, acts in PERMISSION_GROUPS for a, _an in acts]
        self.tbl_yetkiler = self._new_grid(
            "tbl_yetkiler", ["Yetki"] + [r.name for r in roles], stretch=0, editable=False,
        )
        salt_okunur = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        self.tbl_yetkiler.setRowCount(len(codes))
        for row, code in enumerate(codes):
            ad = QStandardItem(permission_label(code))
            ad.setFlags(salt_okunur)
            self.tbl_yetkiler.setItem(row, 0, ad)
            for col, r in enumerate(roles, start=1):
                has = "*" in role_perms[r.name] or code in role_perms[r.name]
                it = QStandardItem("✔" if has else "—")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it.setFlags(salt_okunur)
                self.tbl_yetkiler.setItem(row, col, it)
        lyt.addWidget(self.tbl_yetkiler.container, 1)
        return w

    #: Döviz & Kur grid kolonları — M.B. (T.C. Merkez Bankası) ve S.P. (Serbest
    #: Piyasa) alış/satış değerleri ayrı ayrı gösterilir (bkz. CurrencyRateHistory).
    DOVIZ_COLS = (
        "Kod", "Ad", "Sembol", "M.B. Alış", "M.B. Satış",
        "S.P. Alış", "S.P. Satış", "Güncel Kur", "Durum",
    )

    #: Panel başlığı üstteki breadcrumb'da ("Genel Ayarlar > Döviz & Kur")
    #: zaten gösterildiği için panel içinde tekrar edilmez; bu metin de artık
    #: sayfaya gömülü bir paragraf değil, üst çubuktaki ℹ️ ikonunun ipucudur.
    DOVIZ_YARDIM_METNI = (
        "Tanımlanan para birimleri ve 'Güncel Kur' sütunu Teklif, Fatura ve Stok "
        "ekranlarında otomatik kullanılır. Alttaki tablo, seçili 'Kur Tarihi'ndeki "
        "M.B. (T.C. Merkez Bankası) ve S.P. (Serbest Piyasa) kurlarını gösterir."
    )

    #: İlk kurulumda "kullanmak istediğiniz dövizleri seçin" popup'ında bu
    #: kodlar ön işaretli gelir (en sık kullanılan dövizler); tam liste
    #: `currency_catalog.CURRENCY_CATALOG`'dan (ISO 4217) aranıp seçilir.
    ILK_SECIM_ON_TANIMLI_KODLAR = {"USD", "EUR"}

    def build_doviz_panel(self) -> QWidget:
        """Döviz & Kur Tanımları Paneli — günlük kur geçmişi takibi.

        Üstte tek satırlık kaynak+tarih çubuğu (Kaynak, Serbest Piyasa XML
        adresi, Kur Tarihi, Getir, ◀▶, Tarihe Kopyala), altta toplu
        çekme/silme kutusu, ortada Teklif kalem gridiyle aynı bileşeni
        (FilterableTableView — sütun genişlikleri kalıcı, sıralanabilir,
        kendi filtre satırı var) kullanan tarih bazlı kur tablosu.
        """
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        lyt.addWidget(self._build_doviz_ust_bar())

        self.doviz_grid = FilterableTableView(
            headers_dict={i: (h, h) for i, h in enumerate(self.DOVIZ_COLS)},
            profile_key="genel_ayarlar_doviz",
            enable_profile_bar=False,
            parent=w,
        )
        self.doviz_model = QStandardItemModel(self)
        self.doviz_model.setHorizontalHeaderLabels(list(self.DOVIZ_COLS))
        self.doviz_grid.table_view.setModel(self.doviz_model)
        self.doviz_grid.table_view.verticalHeader().setVisible(False)
        self.doviz_grid.table_view.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )
        self.doviz_grid.table_view.customContextMenuRequested.connect(
            self._show_doviz_context_menu,
        )
        lyt.addWidget(self.doviz_grid, 1)

        self._load_doviz_grid_for_date(self.dt_kur_tarihi.date().toPyDate())
        return w

    def _build_doviz_ust_bar(self) -> QWidget:
        """Kaynak + tarih gezinme — tek satır (Kaynak | Adres | Kur Tarihi |
        Getir | ◀ ▶ | Tarihe Kopyala), referans ekrandaki üst çubukla aynı
        düzen. Güncelleme tetikleyicisi ayrıca sol sidebar'da da vardır
        ("🔄 Kurları Güncelle") — aksiyon tekrarı değil, burada "Getir" yalnızca
        seçili TARİH için çeker, sidebar'daki ise bugünün kurudur.
        """
        bar = QFrame()
        bar.setStyleSheet(
            "QFrame { background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; }",
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(6)
        lbl_style = "font-size:11px; color:#334155;"

        def _lbl(text: str) -> QLabel:
            lab = QLabel(text)
            lab.setStyleSheet(lbl_style)
            return lab

        self.cmb_doviz_kaynak = QComboBox()
        self.cmb_doviz_kaynak.setStyleSheet("combobox-popup:0;")
        self.cmb_doviz_kaynak.setToolTip(
            "Kurların hangi kaynaktan çekileceği — serbest metin değil, sabit "
            "seçeneklerden biri: TCMB (Resmi), Serbest Piyasa veya Manuel Giriş.",
        )
        for kind, label in currency_rate_service.SOURCE_LABELS.items():
            self.cmb_doviz_kaynak.addItem(label, kind)

        # Adres tanımlama/yönetme (ekle/seç/sil) artık burada değil, sağ
        # paneldeki "💱 Döviz İşlemleri" bölümünde (bkz. build_right_sidebar) —
        # üst çubukta yalnızca seçili adresin kısa bir hatırlatıcısı kalır.
        self.lbl_doviz_adres_hint = QLabel("")
        self.lbl_doviz_adres_hint.setStyleSheet("color:#64748b; font-size:10px; font-style:italic;")
        self.lbl_doviz_adres_hint.setToolTip(
            "Serbest Piyasa kaynak adresi — sağ panel > 💱 Döviz İşlemleri'nden yönetilir.",
        )

        self.dt_kur_tarihi = QDateEdit(QDate.currentDate())
        self.dt_kur_tarihi.setCalendarPopup(True)
        self.dt_kur_tarihi.setDisplayFormat("dd.MM.yyyy")
        self.dt_kur_tarihi.setToolTip("Tablo ve 'Getir' işleminin uygulanacağı kur tarihi.")

        btn_getir = QPushButton("⚡ Getir")
        btn_getir.setStyleSheet(self.btn_style("#7c3aed", "#ffffff"))
        btn_getir.setToolTip("Seçili 'Kur Tarihi' için kaynaktan kur çeker.")
        btn_getir.clicked.connect(self._on_doviz_getir_clicked)

        btn_prev = QPushButton("◀")
        btn_prev.setFixedWidth(28)
        btn_prev.setStyleSheet(self.btn_style())
        btn_prev.setToolTip("Kur tarihini bir gün geri alır.")
        btn_prev.clicked.connect(lambda: self._shift_doviz_tarih(-1))
        btn_next = QPushButton("▶")
        btn_next.setFixedWidth(28)
        btn_next.setStyleSheet(self.btn_style())
        btn_next.setToolTip("Kur tarihini bir gün ileri alır.")
        btn_next.clicked.connect(lambda: self._shift_doviz_tarih(1))

        self.dt_doviz_kopyala_hedef = QDateEdit(QDate.currentDate().addDays(1))
        self.dt_doviz_kopyala_hedef.setCalendarPopup(True)
        self.dt_doviz_kopyala_hedef.setDisplayFormat("dd.MM.yyyy")
        self.dt_doviz_kopyala_hedef.setToolTip("Kopyalamanın hedef tarihi.")
        btn_kopyala = QPushButton("+ Kopyala")
        btn_kopyala.setStyleSheet(self.btn_style())
        btn_kopyala.setToolTip(
            "Görüntülenen tarihteki kurları hedef tarihe kopyalar "
            "(ör. hafta sonu/tatil günleri için).",
        )
        btn_kopyala.clicked.connect(self._on_doviz_kopyala_clicked)

        lbl_yardim = QLabel("ℹ️")
        lbl_yardim.setStyleSheet("font-size:13px;")
        lbl_yardim.setToolTip(self.DOVIZ_YARDIM_METNI)

        row.addWidget(_lbl("Kaynak:"))
        row.addWidget(self.cmb_doviz_kaynak)
        row.addWidget(self.lbl_doviz_adres_hint, 1)
        row.addWidget(_lbl("Kur Tarihi:"))
        row.addWidget(self.dt_kur_tarihi)
        row.addWidget(btn_getir)
        row.addWidget(btn_prev)
        row.addWidget(btn_next)
        row.addWidget(_lbl("→ Tarihe:"))
        row.addWidget(self.dt_doviz_kopyala_hedef)
        row.addWidget(btn_kopyala)
        row.addWidget(lbl_yardim)

        # NOT: Kaynak/adres ayarlarının DB'den yüklenmesi (_load_doviz_kaynak_ayarlari)
        # burada değil, sağ paneldeki adres alanı (txt_doviz_kaynak_url) inşa
        # edildikten SONRA çağrılır (bkz. _build_doviz_sag_panel_islemler) —
        # aksi halde henüz var olmayan bir widget'a erişilmiş olurdu.
        self.cmb_doviz_kaynak.currentIndexChanged.connect(self._on_doviz_kaynak_changed)
        self.dt_kur_tarihi.dateChanged.connect(
            lambda qd: self._load_doviz_grid_for_date(qd.toPyDate()),
        )
        return bar

    # ---- Kaynak Ayarları -------------------------------------------------
    def _update_doviz_adres_hint(self, kind: str, url: str) -> None:
        """Üst çubuktaki kısa adres hatırlatıcısını günceller — düzenleme
        artık sağ paneldeki 💱 Döviz İşlemleri bölümünden yapılır."""
        if not hasattr(self, "lbl_doviz_adres_hint"):
            return
        if kind != currency_rate_service.SOURCE_SERBEST:
            self.lbl_doviz_adres_hint.setText("")
            return
        kisa = url if len(url) <= 48 else url[:45] + "…"
        self.lbl_doviz_adres_hint.setText(f"🌐 {kisa}" if kisa else "🌐 (adres tanımlı değil)")

    def _load_doviz_kaynak_ayarlari(self) -> None:
        """DB'deki kayıtlı kur kaynağı ayarlarını (tip/adres) forma yükler."""
        kind, url = currency_rate_service.get_source_config(self.db)
        idx = self.cmb_doviz_kaynak.findData(kind)
        self.cmb_doviz_kaynak.blockSignals(True)
        self.cmb_doviz_kaynak.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_doviz_kaynak.blockSignals(False)
        self.txt_doviz_kaynak_url.setText(url)
        self._update_doviz_adres_hint(kind, url)
        self.txt_doviz_kaynak_url.setEnabled(kind == currency_rate_service.SOURCE_SERBEST)

    def _on_doviz_kaynak_changed(self) -> None:
        kind = self.cmb_doviz_kaynak.currentData()
        self.txt_doviz_kaynak_url.setEnabled(kind == currency_rate_service.SOURCE_SERBEST)
        self._save_doviz_kaynak_ayarlari()

    def _save_doviz_kaynak_ayarlari(self) -> None:
        if not self.db:
            return
        kind = self.cmb_doviz_kaynak.currentData() or currency_rate_service.SOURCE_TCMB
        url = self.txt_doviz_kaynak_url.text().strip()
        currency_rate_service.set_source_config(self.db, kind, url)
        self._update_doviz_adres_hint(kind, url)

    # ---- Tarih Gezinme / Getir / Kopyala ----------------------------------
    def _shift_doviz_tarih(self, delta_days: int) -> None:
        self.dt_kur_tarihi.setDate(self.dt_kur_tarihi.date().addDays(delta_days))

    def _on_doviz_getir_clicked(self) -> None:
        """Seçili 'Kur Tarihi' için kaynaktan kur çeker (tekil tarih)."""
        if not self.db:
            return
        target = self.dt_kur_tarihi.date().toPyDate()
        result = currency_rate_service.refresh_and_apply(self.db, for_date=target)
        self._load_doviz_grid_for_date(target)
        if result.success:
            self.toast_requested.emit(result.message, "success")
        else:
            QMessageBox.warning(self, "Döviz Kuru", result.message)

    def _on_doviz_kopyala_clicked(self) -> None:
        """Görüntülenen tarihteki kurları hedef tarihe kopyalar (hafta
        sonu/tatil günleri için yeni kur yayınlanmadığında kullanışlıdır)."""
        if not self.db:
            return
        src = self.dt_kur_tarihi.date().toPyDate()
        dst = self.dt_doviz_kopyala_hedef.date().toPyDate()
        rows = currency_rate_service.get_rate_history_range(self.db, src, src)
        if not rows:
            QMessageBox.information(
                self, "Tarihe Kopyala", f"{src.strftime('%d.%m.%Y')} için kayıtlı kur yok.",
            )
            return
        for r in rows:
            currency_rate_service.upsert_rate_history(
                self.db, dst, r.code, commit=False,
                mb_alis=r.mb_alis, mb_satis=r.mb_satis,
                sp_alis=r.sp_alis, sp_satis=r.sp_satis,
            )
        self.db.commit()
        self.toast_requested.emit(
            f"{len(rows)} döviz kuru {dst.strftime('%d.%m.%Y')} tarihine kopyalandı.", "success",
        )
        if self.dt_kur_tarihi.date().toPyDate() == dst:
            self._load_doviz_grid_for_date(dst)

    # ---- Toplu Çekme / Silme ----------------------------------------------
    def _on_doviz_toplu_cek_clicked(self) -> None:
        if not self.db:
            return
        d1 = self.dt_toplu_bas.date().toPyDate()
        d2 = self.dt_toplu_bit.date().toPyDate()
        result = currency_rate_service.bulk_fetch_range(self.db, d1, d2)
        self._load_doviz_grid_for_date(self.dt_kur_tarihi.date().toPyDate())
        if getattr(self, "doviz_rapor_widget", None):
            self.doviz_rapor_widget.refresh()
        if result.success:
            QMessageBox.information(self, "Toplu Kur Çekme", result.message)
        else:
            QMessageBox.warning(self, "Toplu Kur Çekme", result.message)

    def _on_doviz_toplu_sil_clicked(self) -> None:
        if not self.db:
            return
        d1 = self.dt_toplu_bas.date().toPyDate()
        d2 = self.dt_toplu_bit.date().toPyDate()
        code = self._selected_doviz_code()
        etiket = f"{code} dövizinin" if code else "tüm dövizlerin"
        reply = QMessageBox.question(
            self, "Aralığı Sil",
            f"{d1.strftime('%d.%m.%Y')} — {d2.strftime('%d.%m.%Y')} arasında "
            f"{etiket} geçmiş kur kayıtları silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        deleted = currency_rate_service.delete_rate_history(self.db, d1, d2, code=code)
        self._load_doviz_grid_for_date(self.dt_kur_tarihi.date().toPyDate())
        if getattr(self, "doviz_rapor_widget", None):
            self.doviz_rapor_widget.refresh()
        self.toast_requested.emit(f"{deleted} kayıt silindi.", "success")

    # ---- Grid: yükleme / kaydetme / yardımcılar ---------------------------
    def _load_doviz_grid_for_date(self, d: date) -> None:
        """Grid'i verilen tarihteki kurlarla doldurur (her Currency için bir
        satır; o tarihte geçmiş kaydı yoksa M.B./S.P. hücreleri boş kalır)."""
        if not self.db or not hasattr(self, "doviz_model"):
            return
        self.doviz_model.removeRows(0, self.doviz_model.rowCount())
        try:
            currencies = self.db.scalars(
                select(Currency).where(Currency.is_deleted == False),  # noqa: E712
            ).all()
            hist_by_code = {
                h.code: h
                for h in currency_rate_service.get_rate_history_range(self.db, d, d)
            }
            for c in currencies:
                h = hist_by_code.get((c.code or "").upper())
                row = [
                    QStandardItem(c.code or ""),
                    QStandardItem(c.name or ""),
                    QStandardItem(c.symbol or ""),
                    self._rate_item(h.mb_alis if h else None),
                    self._rate_item(h.mb_satis if h else None),
                    self._rate_item(h.sp_alis if h else None),
                    self._rate_item(h.sp_satis if h else None),
                    self._rate_item(c.rate),
                    QStandardItem("Aktif" if c.is_active else "Pasif"),
                ]
                self.doviz_model.appendRow(row)
        except Exception as e:
            logger.warning("Döviz geçmişi yüklenemedi: %s", e)

    @staticmethod
    def _fmt_rate(value: float | None) -> str:
        return f"{value:.4f}" if value is not None else ""

    @classmethod
    def _rate_item(cls, value: float | None) -> QStandardItem:
        """Sayısal kur hücreleri — tüm sayısal alanlarda olduğu gibi sağa
        yaslı gösterilir."""
        item = QStandardItem(cls._fmt_rate(value))
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    @staticmethod
    def _parse_rate(text: str) -> float | None:
        text = (text or "").strip().replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _doviz_cell(self, row: int, col: int) -> str:
        it = self.doviz_model.item(row, col)
        return it.text() if it else ""

    def _selected_doviz_code(self) -> str | None:
        idx = self.doviz_grid.table_view.currentIndex()
        if not idx.isValid():
            return None
        return self._doviz_cell(idx.row(), 0).strip().upper() or None

    def _save_doviz(self) -> None:
        """Grid'deki tüm satırları kaydeder: Currency tanımı (kod/ad/sembol/
        güncel kur/durum) + görüntülenen tarih için geçmiş kur (M.B./S.P.)."""
        if not self.db or not hasattr(self, "doviz_model"):
            return
        view_date = self.dt_kur_tarihi.date().toPyDate()
        existing_by_code = {
            c.code: c
            for c in self.db.scalars(
                select(Currency).where(Currency.is_deleted == False),  # noqa: E712
            ).all()
        }
        for r in range(self.doviz_model.rowCount()):
            code = self._doviz_cell(r, 0).strip().upper()
            if not code:
                continue
            cur = existing_by_code.get(code)
            if cur is None:
                cur = Currency(code=code)
                self.db.add(cur)
                existing_by_code[code] = cur
            cur.name = self._doviz_cell(r, 1).strip()
            cur.symbol = self._doviz_cell(r, 2).strip()
            guncel = self._parse_rate(self._doviz_cell(r, 7))
            if guncel is not None:
                cur.rate = guncel
            cur.is_active = self._doviz_cell(r, 8).strip().lower() != "pasif"

            history_kwargs = {
                "mb_alis": self._parse_rate(self._doviz_cell(r, 3)),
                "mb_satis": self._parse_rate(self._doviz_cell(r, 4)),
                "sp_alis": self._parse_rate(self._doviz_cell(r, 5)),
                "sp_satis": self._parse_rate(self._doviz_cell(r, 6)),
            }
            if any(v is not None for v in history_kwargs.values()):
                currency_rate_service.upsert_rate_history(
                    self.db, view_date, code, commit=False, **history_kwargs,
                )
        self.db.commit()

    # ---- İlk Kurulum: Standart Dövizler ------------------------------------
    def _ensure_try_currency(self) -> None:
        """TRY, kurulum paketiyle gelen standart bir tanım olmalı — Döviz &
        Kur paneli açıldığında eksikse burada otomatik oluşturulur."""
        if not self.db:
            return
        exists = self.db.scalar(
            select(Currency).where(Currency.code == "TRY", Currency.is_deleted == False),  # noqa: E712
        )
        if not exists:
            try_info = get_currency_info("TRY")
            self.db.add(Currency(
                code="TRY", name="Türk Lirası", symbol="₺",
                flag=try_info.flag if try_info else "🇹🇷", rate=1.0, is_active=True,
            ))
            self.db.commit()

    def _maybe_prompt_initial_currencies(self) -> None:
        """Hiç döviz tanımlı değilse (TRY hariç), kullanıcıya kullanmak
        istediği dövizleri seçtiren bir popup gösterir — panel her açıldığında
        değil, ekran ömründe yalnızca bir kez sorulur.

        `self.isVisible()` koşulu, ekran gerçekten kullanıcıya gösterilmeden
        (ör. `.show()` hiç çağrılmamış otomatik testlerde) bu bloklayıcı
        popup'ın sessizce açılıp asılı kalmasını engeller; ekran gerçekten
        görünür olduğunda tekrar denenir (bayrak henüz set edilmediği için)."""
        if not self.db or getattr(self, "_doviz_ilk_secim_soruldu", False):
            return
        if not self.isVisible():
            return
        self._doviz_ilk_secim_soruldu = True
        self._ensure_try_currency()
        diger = self.db.scalars(
            select(Currency).where(Currency.code != "TRY", Currency.is_deleted == False),  # noqa: E712
        ).all()
        if diger:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Kullanılacak Dövizleri Seçin")
        dlg.resize(380, 520)
        lyt = QVBoxLayout(dlg)

        info = QLabel(
            "Henüz hiç döviz tanımlı değil (TL hariç — TL zaten standart olarak "
            "hazır gelir). Bu firmada kullanmak istediğiniz dövizleri arayıp "
            "işaretleyin; dilediğiniz zaman sağ tık > 'Yeni Döviz Ekle' ile "
            "başka döviz de ekleyebilirsiniz.",
        )
        info.setWordWrap(True)
        lyt.addWidget(info)

        txt_ara = QLineEdit()
        txt_ara.setPlaceholderText("Kod veya isimle ara... (ör. USD, Euro)")
        lyt.addWidget(txt_ara)

        lst = QListWidget()
        for c in CURRENCY_CATALOG:
            item = QListWidgetItem(f"{c.flag}  {c.code} — {c.name} ({c.symbol})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if c.code in self.ILK_SECIM_ON_TANIMLI_KODLAR
                else Qt.CheckState.Unchecked,
            )
            item.setData(Qt.ItemDataRole.UserRole, c)
            lst.addItem(item)
        lyt.addWidget(lst, 1)

        def _filtrele(text: str) -> None:
            q = text.strip().lower()
            for i in range(lst.count()):
                it = lst.item(i)
                c = it.data(Qt.ItemDataRole.UserRole)
                it.setHidden(bool(q) and q not in f"{c.code} {c.name}".lower())

        txt_ara.textChanged.connect(_filtrele)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        box.accepted.connect(dlg.accept)
        box.rejected.connect(dlg.reject)
        lyt.addWidget(box)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        eklenen = 0
        for i in range(lst.count()):
            it = lst.item(i)
            if it.checkState() != Qt.CheckState.Checked:
                continue
            c = it.data(Qt.ItemDataRole.UserRole)
            self.db.add(Currency(
                code=c.code, name=c.name, symbol=c.symbol, flag=c.flag,
                rate=1.0, is_active=True,
            ))
            eklenen += 1
        if eklenen:
            self.db.commit()
            self._load_doviz_grid_for_date(self.dt_kur_tarihi.date().toPyDate())
            self.toast_requested.emit(f"{eklenen} döviz eklendi.", "success")

    # ---- Sağ tık menüsü + popup diyaloglar --------------------------------
    def _show_doviz_context_menu(self, pos) -> None:
        menu = QMenu(self)
        a_yeni = QAction("➕ Yeni Döviz Ekle...", self)
        a_yeni.triggered.connect(self._open_yeni_doviz_dialog)
        a_kur = QAction("✏️ Kur Gir...", self)
        a_kur.triggered.connect(self._open_kur_gir_dialog)
        a_sil = QAction("🗑️ Bu Tarihteki Satırı Sil", self)
        a_sil.triggered.connect(self._delete_selected_doviz_history_row)
        a_yazdir_tek = QAction("🖨️ Yazdır (Bu Tarih)", self)
        a_yazdir_tek.triggered.connect(self.print_active_panel)
        a_yazdir_aralik = QAction("🖨️ Yazdır (Tarih Aralığı...)", self)
        a_yazdir_aralik.triggered.connect(self._print_doviz_range)
        a_yenile = QAction("🔄 Yenile", self)
        a_yenile.triggered.connect(
            lambda: self._load_doviz_grid_for_date(self.dt_kur_tarihi.date().toPyDate()),
        )
        a_toplu = QAction("⚡ Toplu Kur Çek / Adres Yönetimi...", self)
        a_toplu.setToolTip("Sağ paneldeki 💱 Döviz İşlemleri bölümünü açar.")
        a_toplu.triggered.connect(self._open_doviz_sag_panel_islemler)
        for a in (a_yeni, a_kur, a_sil):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(a_yazdir_tek)
        menu.addAction(a_yazdir_aralik)
        menu.addSeparator()
        menu.addAction(a_yenile)
        menu.addAction(a_toplu)
        menu.exec(self.doviz_grid.table_view.viewport().mapToGlobal(pos))

    def _open_doviz_sag_panel_islemler(self) -> None:
        """Sağ tık menüsündeki 'Toplu Kur Çek / Adres Yönetimi' — Toplu Kur
        Çek ve Serbest Piyasa adres yönetimi sık kullanılmadığı için ana
        araç çubuğundan sağ panele taşındı; bu eylem o paneli açar."""
        if hasattr(self, "right_panel"):
            self.right_panel.open_panel()
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.set_section_visible("doviz", True)
            self.right_sidebar.section("doviz").set_expanded(True)

    def _open_yeni_doviz_dialog(self) -> None:
        exclude_codes = set()
        if self.db:
            exclude_codes = {
                c for c in self.db.scalars(
                    select(Currency.code).where(Currency.is_deleted == False),  # noqa: E712
                ).all()
            }
        dlg = YeniDovizDialog(parent=self, exclude_codes=exclude_codes)
        if dlg.exec() != QDialog.DialogCode.Accepted or not self.db:
            return
        data = dlg.get_data()
        exists = self.db.scalar(
            select(Currency).where(
                Currency.code == data["code"], Currency.is_deleted == False,  # noqa: E712
            ),
        )
        if exists:
            QMessageBox.warning(self, "Uyarı", f"'{data['code']}' zaten tanımlı.")
            return
        self.db.add(Currency(
            code=data["code"], name=data["name"], symbol=data["symbol"],
            flag=data.get("flag", ""), rate=1.0, is_active=data["is_active"],
        ))
        self.db.commit()
        self._load_doviz_grid_for_date(self.dt_kur_tarihi.date().toPyDate())

    def _open_kur_gir_dialog(self) -> None:
        if not self.db:
            return
        codes = [
            c.code for c in self.db.scalars(
                select(Currency).where(Currency.is_deleted == False),  # noqa: E712
            ).all()
        ]
        if not codes:
            QMessageBox.information(self, "Kur Gir", "Önce bir döviz tanımlayın.")
            return
        dlg = KurGirDialog(
            codes, self.dt_kur_tarihi.date(),
            initial_code=self._selected_doviz_code() or "", parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        currency_rate_service.upsert_rate_history(
            self.db, data["rate_date"], data["code"],
            mb_alis=data["mb_alis"], mb_satis=data["mb_satis"],
            sp_alis=data["sp_alis"], sp_satis=data["sp_satis"],
        )
        if data["rate_date"] == self.dt_kur_tarihi.date().toPyDate():
            self._load_doviz_grid_for_date(data["rate_date"])

    def _delete_selected_doviz_history_row(self) -> None:
        code = self._selected_doviz_code()
        if not code or not self.db:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz satırı seçin.")
            return
        d = self.dt_kur_tarihi.date().toPyDate()
        deleted = currency_rate_service.delete_rate_history(self.db, d, d, code=code)
        self._load_doviz_grid_for_date(d)
        if deleted:
            self.toast_requested.emit(
                f"{code} — {d.strftime('%d.%m.%Y')} kur kaydı silindi.", "success",
            )

    def _delete_selected_doviz_currency(self) -> None:
        """Sol sidebar > 'Seçili Dövizi Sil' — döviz TANIMINI (Currency) siler."""
        code = self._selected_doviz_code()
        if not code or not self.db:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz satırı seçin.")
            return
        cur = self.db.scalar(
            select(Currency).where(Currency.code == code, Currency.is_deleted == False),  # noqa: E712
        )
        if cur:
            cur.is_deleted = True
            self.db.commit()
        self._load_doviz_grid_for_date(self.dt_kur_tarihi.date().toPyDate())

    def _print_doviz_range(self) -> None:
        """Toplu işlem kutusundaki tarih aralığını (ve seçiliyse tek dövizi)
        yazdırma önizlemesinde açar."""
        if not self.db:
            return
        d1 = self.dt_toplu_bas.date().toPyDate()
        d2 = self.dt_toplu_bit.date().toPyDate()
        code = self._selected_doviz_code()
        rows = currency_rate_service.get_rate_history_range(self.db, d1, d2, code=code)
        if not rows:
            QMessageBox.information(self, "Yazdır", "Seçili aralıkta kur kaydı yok.")
            return
        headers = ["Tarih", "Kod", "M.B. Alış", "M.B. Satış", "S.P. Alış", "S.P. Satış"]
        body_rows = [
            [
                r.rate_date.strftime("%d.%m.%Y"), r.code,
                self._fmt_rate(r.mb_alis), self._fmt_rate(r.mb_satis),
                self._fmt_rate(r.sp_alis), self._fmt_rate(r.sp_satis),
            ]
            for r in rows
        ]
        baslik = f"Döviz Kuru — {d1.strftime('%d.%m.%Y')} — {d2.strftime('%d.%m.%Y')}"
        if code:
            baslik += f" ({code})"
        html = self._generate_html_table(headers, body_rows, f"TOYA ERP — {baslik}")
        self._show_print_preview(html)

    #: Ödeme Planı / Banka Ödeme Planı grid'lerinde boş/seçilmemiş hesap-plan değeri.
    _HEDEF_HESAP_BOS = "(Seçilmedi)"
    _BANKA_PLANI_BOS = "(Seçilmedi)"

    def _hedef_hesap_secenekleri(self) -> list[str]:
        """FinansHesap listesinden "KOD — Ad" seçenekleri (ComboDelegate'e canlı/her açılışta sorulur)."""
        secenekler = [self._HEDEF_HESAP_BOS]
        if self.db:
            try:
                hesaplar = self.db.scalars(
                    select(FinansHesap).where(FinansHesap.aktif == True).order_by(FinansHesap.kod),  # noqa: E712
                ).all()
                secenekler += [f"{h.kod} — {h.ad}" for h in hesaplar]
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Finans hesapları yüklenemedi: {e}")
        return secenekler

    def _banka_odeme_plani_secenekleri(self) -> list[str]:
        """BankaOdemePlani listesinden "KOD — Açıklama" seçenekleri — Ödeme Planı > Kredi Kartı/POS/Havale
        gibi banka ile ilgili tiplerde isteğe bağlı bağlanır (bkz. gelistirme/04_odeme_planlari/tasarim.md)."""
        secenekler = [self._BANKA_PLANI_BOS]
        if self.db:
            try:
                planlar = self.db.scalars(
                    select(BankaOdemePlani).where(
                        BankaOdemePlani.is_deleted == False, BankaOdemePlani.is_active == True,  # noqa: E712
                    ).order_by(BankaOdemePlani.kod),
                ).all()
                secenekler += [f"{p.kod} — {p.aciklama or ''}".rstrip(" —") for p in planlar]
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Banka ödeme planları yüklenemedi: {e}")
        return secenekler

    def build_odeme_planlari_panel(self) -> QWidget:
        """Ödeme Planları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        self._panel_baslik(
            lyt, "💳 Ödeme Planı Tanımları",
            "Teklif ve Fatura işlemlerinde kullanılan vade/taksit planları — Ödeme Tipi ve Hedef Hesap, "
            "faturadan otomatik kasa/banka fişi oluşturmak için kullanılır. Kredi Kartı/POS/Havale gibi "
            "banka ile ilgili tiplerde isteğe bağlı bir Banka Ödeme Planı'na (komisyon/BSMV/hizmet bedeli) "
            "bağlanabilir.",
        )

        self.tbl_odeme = self._new_grid(
            'tbl_odeme',
            ['Kod', 'Açıklama', 'Gün', 'Ödeme Tipi', 'Hedef Hesap', 'Banka Ödeme Planı', 'Otomatik Fiş', 'Durum'],
            stretch=1,
        )
        self.tbl_odeme.setItemDelegateForColumn(
            3, ComboDelegate(lambda: [e for _k, e in ODEME_TIPI_SECENEKLERI], self.tbl_odeme),
        )
        self.tbl_odeme.setItemDelegateForColumn(
            4, ComboDelegate(self._hedef_hesap_secenekleri, self.tbl_odeme),
        )
        self.tbl_odeme.setItemDelegateForColumn(
            5, ComboDelegate(self._banka_odeme_plani_secenekleri, self.tbl_odeme),
        )
        self.tbl_odeme.setItemDelegateForColumn(
            6, ComboDelegate(lambda: ["Evet", "Hayır"], self.tbl_odeme),
        )
        self.tbl_odeme.setItemDelegateForColumn(
            7, ComboDelegate(lambda: ["Aktif", "Pasif"], self.tbl_odeme),
        )

        default_planlar = [
            ("30GVD", "30 GÜN VADE", "30", "Açık Hesap", self._HEDEF_HESAP_BOS, self._BANKA_PLANI_BOS, "Evet", "Aktif"),
            ("45GVD", "45 GÜNLÜK VADE", "45", "Açık Hesap", self._HEDEF_HESAP_BOS, self._BANKA_PLANI_BOS, "Evet", "Aktif"),
            ("60GVD", "60 GÜNLÜK VADE", "60", "Açık Hesap", self._HEDEF_HESAP_BOS, self._BANKA_PLANI_BOS, "Evet", "Aktif"),
            ("60GUNKK", "60 GÜN KREDİ KARTI", "60", "Kredi Kartı", self._HEDEF_HESAP_BOS, self._BANKA_PLANI_BOS, "Evet", "Aktif"),
            ("AH", "AÇIK HESAP", "0", "Açık Hesap", self._HEDEF_HESAP_BOS, self._BANKA_PLANI_BOS, "Evet", "Aktif"),
            ("NAKIT", "NAKİT", "0", "Nakit", self._HEDEF_HESAP_BOS, self._BANKA_PLANI_BOS, "Evet", "Aktif"),
            ("CF3TAK", "CARDFINANS 3 TAKSİT", "90", "Kredi Kartı", self._HEDEF_HESAP_BOS, self._BANKA_PLANI_BOS, "Evet", "Aktif"),
        ]
        for row_data in default_planlar:
            r = self.tbl_odeme.rowCount()
            self.tbl_odeme.insertRow(r)
            for c, val in enumerate(row_data):
                self.tbl_odeme.setItem(r, c, QStandardItem(val))

        lyt.addWidget(self.tbl_odeme.container, 1)
        self._load_odeme_planlari_from_db()
        return w

    def _yeni_odeme_plani_ekle(self, duzenle: bool = False) -> None:
        """"Ödeme Planı" popup'ı: yeni kayıt ekler, ya da seçili satırı önceden doldurarak düzenler.
        Grid hücreleri hâlâ doğrudan da düzenlenebilir — bu popup ek bir giriş yolu."""
        t = getattr(self, "tbl_odeme", None)
        if not t:
            return
        mevcut = None
        row = t.currentRow()
        if duzenle:
            if row < 0:
                QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz satırı seçin.")
                return
            mevcut = {
                "kod": t.item(row, 0).text() if t.item(row, 0) else "",
                "aciklama": t.item(row, 1).text() if t.item(row, 1) else "",
                "gun": t.item(row, 2).text() if t.item(row, 2) else "0",
                "tip": t.item(row, 3).text() if t.item(row, 3) else "",
                "hesap": t.item(row, 4).text() if t.item(row, 4) else "",
                "banka_plani": t.item(row, 5).text() if t.item(row, 5) else "",
                "otomatik": t.item(row, 6).text() if t.item(row, 6) else "Evet",
                "aktif": t.item(row, 7).text() if t.item(row, 7) else "Aktif",
            }
        dlg = OdemePlaniEkleDialog(
            [e for _k, e in ODEME_TIPI_SECENEKLERI],
            self._hedef_hesap_secenekleri(),
            self._banka_odeme_plani_secenekleri(),
            deger=mevcut,
            parent=self,
        )
        if not dlg.exec():
            return
        d = dlg.deger()
        vals = [d["kod"], d["aciklama"], d["gun"], d["tip"], d["hesap"], d["banka_plani"], d["otomatik"], d["aktif"]]
        r = row if duzenle and row >= 0 else t.rowCount()
        if not (duzenle and row >= 0):
            t.insertRow(r)
        for c, val in enumerate(vals):
            t.setItem(r, c, QStandardItem(val))
        t.selectRow(r)

    def _odeme_plani_satirlarini_duzenle(self) -> None:
        """04.11: Seçili Ödeme Planı'nın ÇOK TÜRLÜ bölüştürme satırlarını düzenler (bkz.
        `OdemePlaniSatirlariDialog`) — "yarısı nakit yarısı kredi kartı" gibi karma planlar için.
        Plan önce kaydedilmiş (DB'de gerçek bir ID'si) olmalı."""
        t = getattr(self, "tbl_odeme", None)
        row = t.currentRow() if t else -1
        if row < 0:
            QMessageBox.warning(self, "Uyarı", "Lütfen satırlarını düzenlemek istediğiniz planı seçin.")
            return
        kod = (t.item(row, 0).text() if t.item(row, 0) else "").strip()
        if not kod or not self.db:
            return
        plan = self.db.scalar(select(PaymentPlan).where(PaymentPlan.code == kod, PaymentPlan.is_deleted == False))  # noqa: E712
        if plan is None:
            QMessageBox.information(
                self, "Önce Kaydedin",
                "Satırları düzenlemeden önce bu Ödeme Planı'nı bir kez kaydedin (💾 Planları Kaydet).",
            )
            return
        OdemePlaniSatirlariDialog(
            self.db, plan.id, plan.code,
            [e for _k, e in ODEME_TIPI_SECENEKLERI],
            self._hedef_hesap_secenekleri(),
            self._banka_odeme_plani_secenekleri(),
            parent=self,
        ).exec()

    def build_banka_odeme_planlari_panel(self) -> QWidget:
        """Banka Ödeme Planları Paneli — taksit sayısına göre değişen komisyon/BSMV/hizmet bedeli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        self._panel_baslik(
            lyt, "🏦 Banka Ödeme Planı Tanımları",
            "Taksit sayısına göre değişen komisyon/BSMV/hizmet bedeli planları — Ödeme Planları'ndaki "
            "Kredi Kartı/POS/Havale gibi banka ile ilgili tiplere bağlanır.",
        )

        self.tbl_banka_odeme = self._new_grid(
            'tbl_banka_odeme',
            ['Kod', 'Açıklama', 'Hesap', 'Taksit Sayısı', 'Komisyon %', 'BSMV %', 'Hizmet Bedeli', 'Durum'],
            stretch=1,
        )
        self.tbl_banka_odeme.setItemDelegateForColumn(
            2, ComboDelegate(self._hedef_hesap_secenekleri, self.tbl_banka_odeme),
        )
        self.tbl_banka_odeme.setItemDelegateForColumn(
            7, ComboDelegate(lambda: ["Aktif", "Pasif"], self.tbl_banka_odeme),
        )

        lyt.addWidget(self.tbl_banka_odeme.container, 1)
        self._load_banka_odeme_planlari_from_db()
        return w

    def _yeni_banka_odeme_plani_ekle(self, duzenle: bool = False) -> None:
        """"Banka Ödeme Planı" popup'ı: yeni kayıt ekler, ya da seçili satırı önceden doldurarak düzenler."""
        t = getattr(self, "tbl_banka_odeme", None)
        if not t:
            return
        mevcut = None
        row = t.currentRow()
        if duzenle:
            if row < 0:
                QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz satırı seçin.")
                return
            mevcut = {
                "kod": t.item(row, 0).text() if t.item(row, 0) else "",
                "aciklama": t.item(row, 1).text() if t.item(row, 1) else "",
                "hesap": t.item(row, 2).text() if t.item(row, 2) else "",
                "taksit": t.item(row, 3).text() if t.item(row, 3) else "1",
                "komisyon": t.item(row, 4).text() if t.item(row, 4) else "0",
                "bsmv": t.item(row, 5).text() if t.item(row, 5) else "5",
                "hizmet": t.item(row, 6).text() if t.item(row, 6) else "0",
                "aktif": t.item(row, 7).text() if t.item(row, 7) else "Aktif",
            }
        dlg = BankaOdemePlaniEkleDialog(self._hedef_hesap_secenekleri(), deger=mevcut, parent=self)
        if not dlg.exec():
            return
        d = dlg.deger()
        vals = [d["kod"], d["aciklama"], d["hesap"], d["taksit"], d["komisyon"], d["bsmv"], d["hizmet"], d["aktif"]]
        r = row if duzenle and row >= 0 else t.rowCount()
        if not (duzenle and row >= 0):
            t.insertRow(r)
        for c, val in enumerate(vals):
            t.setItem(r, c, QStandardItem(val))
        t.selectRow(r)

    def build_fiyat_listeleri_panel(self) -> QWidget:
        """Fiyat Listeleri Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        self._panel_baslik(lyt, "🏷️ Fiyat Listeleri", "Toptan, perakende ve özel müşteri fiyat listesi tanımları.")

        self.tbl_fiyat = self._new_grid('tbl_fiyat', ['Liste Kodu', 'Liste Adı', 'Para Birimi', 'KDV Durumu', 'Durum'], stretch=1)

        default_fiyatlar = [
            ("PERAKENDE", "Perakende Satış Fiyatı", "TRY", "KDV Dahil", "Aktif"),
            ("TOPTAN", "Toptan Satış Fiyatı", "TRY", "KDV Hariç", "Aktif"),
            ("OZEL_BAYI", "Özel Bayi Fiyatı", "USD", "KDV Hariç", "Aktif"),
        ]
        self._load_generic_table(self.tbl_fiyat, "fiyat_listeleri", default_fiyatlar)
        lyt.addWidget(self.tbl_fiyat.container, 1)
        return w

    def build_stok_kategoriler_panel(self) -> QWidget:
        """Stok Kategorileri Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        self._panel_baslik(lyt, "📦 Stok Kategori Tanımları", "Ürün ve stok kartlarının hiyerarşik kategori ağacı.")

        self.tbl_kategori = self._new_grid('tbl_kategori', ['Kategori Adı', 'Üst Kategori', 'Durum'], stretch=0)

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
                self.tbl_kategori.setItem(r, c, QStandardItem(val))

        lyt.addWidget(self.tbl_kategori.container, 1)
        self._load_kategoriler_from_db()
        return w

    def build_stok_markalar_panel(self) -> QWidget:
        """Stok Markaları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        self._panel_baslik(lyt, "🏷️ Stok Marka Tanımları", "Stok kartlarında seçilecek marka ve üretici listesi.")

        self.tbl_marka = self._new_grid('tbl_marka', ['Marka Kodu', 'Marka Adı', 'Ülke / Üretici', 'Durum'], stretch=1)

        default_markalar = [
            ("MRK-01", "Samsung", "Güney Kore", "Aktif"),
            ("MRK-02", "Apple", "ABD", "Aktif"),
            ("MRK-03", "Siemens", "Almanya", "Aktif"),
            ("MRK-04", "Philips", "Hollanda", "Aktif"),
            ("MRK-05", "Yerli Üretim", "Türkiye", "Aktif"),
        ]
        self._load_generic_table(self.tbl_marka, "stok_markalar", default_markalar)
        lyt.addWidget(self.tbl_marka.container, 1)
        return w

    def build_birim_panel(self) -> QWidget:
        """Birim Tanımları Paneli."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        self._panel_baslik(lyt, "📏 Birim Tanımları", "Stok Kartı ve Evrak satırlarında kullanılan ölçü birimleri.")

        self.tbl_birim = self._new_grid('tbl_birim', ['Kod', 'Açıklama', 'Durum'], stretch=1)
        lyt.addWidget(self.tbl_birim.container, 1)
        self._load_birimler_from_db()
        return w

    #: Bir firmanın hiç birimi yoksa (yeni firma) ekrana ilk açılışta örnek olarak önerilir — henüz
    #: kaydedilmez, kullanıcı "Kaydet" demeden DB'ye yazılmaz.
    _VARSAYILAN_BIRIMLER = [
        ("ADET", "Adet", "Aktif"), ("KG", "Kilogram", "Aktif"), ("GR", "Gram", "Aktif"),
        ("LT", "Litre", "Aktif"), ("MT", "Metre", "Aktif"), ("M2", "Metrekare", "Aktif"),
        ("M3", "Metreküp", "Aktif"), ("PKT", "Paket", "Aktif"), ("KTN", "Karton", "Aktif"),
        ("KLI", "Koli", "Aktif"), ("HZM", "Hizmet", "Aktif"), ("SFR", "Sefer", "Aktif"),
    ]

    def build_ozel_alan_panel(self, modul: str = "stok") -> QWidget:
        """Özel Alan Etiket Tanımları Paneli (Stok veya Cari)."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(10)

        modul_title = "Stok Kartı" if modul == "stok" else "Cari Hesap"
        self._panel_baslik(lyt, f"🏷️ {modul_title} Özel Alan Tanımları",
                           f"Özel kod ve alan etiketlerini sektörünüze göre özelleştirin.\nDeğişiklikler {modul_title} formunda anında yansır.")

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

        self._panel_baslik(lyt, "👥 Cari Grup Tanımları", "Cari hesapların sınıflandırılması ve grup iskonto / vade tanımları.")

        self.tbl_cari_grup = self._new_grid('tbl_cari_grup', ['Grup Kodu', 'Grup Adı', 'İskonto (%)', 'Vade (Gün)', 'Durum'], stretch=1)

        default_gruplar = [
            ("GRP-01", "YURT İÇİ MÜŞTERİLER", "0.00", "30", "Aktif"),
            ("GRP-02", "TOPTAN / BAYİLER", "15.00", "60", "Aktif"),
            ("GRP-03", "YURT DIŞI ALICILAR", "5.00", "0", "Aktif"),
            ("GRP-04", "TEDARİKÇİLER", "0.00", "45", "Aktif"),
        ]
        self._load_generic_table(self.tbl_cari_grup, "cari_gruplari", default_gruplar)
        lyt.addWidget(self.tbl_cari_grup.container, 1)
        return w


    def build_kdv_panel(self) -> QWidget:
        """KDV Oranları Paneli: programda genel kullanılacak KDV tanımları (Stok, Teklif, Fatura seçim listeleri için)."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)
        self._panel_baslik(lyt, "🧾 KDV Oranları", "Aktif firmanızda kullanılacak KDV oranı tanımları. Oran yüzde olarak girilir (ör. 20).")
        self.tbl_kdv = self._new_grid("tbl_kdv", ["Kod", "Açıklama", "Oran (%)", "Durum"], stretch=1)
        self._load_kdv_tablosu()
        lyt.addWidget(self.tbl_kdv.container, 1)
        return w

    #: Bir firmanın hiç KDV tanımı yoksa (yeni firma) ekrana ilk açılışta örnek olarak önerilir.
    _VARSAYILAN_KDV = [
        ("KDV0", "KDV %0 (İstisna)", "0", "Aktif"), ("KDV1", "KDV %1", "1", "Aktif"),
        ("KDV10", "KDV %10", "10", "Aktif"), ("KDV20", "KDV %20", "20", "Aktif"),
    ]

    def _load_kdv_tablosu(self) -> None:
        """Aktif firmanın KDV tanımlarını gerçek `KdvTanimi` tablosundan yükler (2026-09-30)."""
        tbl = self.tbl_kdv
        tbl.setRowCount(0)
        if not self.db:
            return
        from src.core.models import KdvTanimi
        from src.desktop.services.company_service import CompanyService
        firma = CompanyService(self.db).aktif_firma()
        kayitlar = self.db.scalars(
            select(KdvTanimi).where(KdvTanimi.company_id == firma.id, KdvTanimi.is_deleted == False)  # noqa: E712
            .order_by(KdvTanimi.code),
        ).all() if firma else []
        kaynak = [(k.code, k.description or "", f"{k.rate:g}", "Aktif" if k.is_active else "Pasif")
                  for k in kayitlar] if kayitlar else (self._VARSAYILAN_KDV if firma else [])
        for row_data in kaynak:
            r = tbl.rowCount()
            tbl.insertRow(r)
            for c, val in enumerate(row_data):
                tbl.setItem(r, c, QStandardItem(val))

    def _save_kdv_tablosu(self) -> None:
        if not self.db:
            return
        from src.core.models import KdvTanimi
        from src.desktop.services.company_service import CompanyService
        firma = CompanyService(self.db).aktif_firma()
        if firma is None:
            self._aktif_firma_uyar("KDV tanımlayabilmek")
            return
        try:
            existing = {
                k.code: k
                for k in self.db.scalars(
                    select(KdvTanimi).where(KdvTanimi.company_id == firma.id, KdvTanimi.is_deleted == False),  # noqa: E712
                ).all()
            }
            gelen_kodlar: set[str] = set()
            for r in range(self.tbl_kdv.rowCount()):
                def hucre(c, _r=r):
                    it = self.tbl_kdv.item(_r, c)
                    return it.text().strip() if it else ""
                code = hucre(0)
                if not code:
                    continue
                gelen_kodlar.add(code)
                try:
                    rate = float(hucre(2).replace(",", "."))
                except ValueError:
                    rate = 0.0
                is_act = hucre(3).lower() != "pasif"
                if code in existing:
                    k = existing[code]
                    k.description, k.rate, k.is_active = hucre(1), rate, is_act
                else:
                    self.db.add(KdvTanimi(company_id=firma.id, code=code, description=hucre(1),
                                           rate=rate, is_active=is_act))
            for code, k in existing.items():
                if code not in gelen_kodlar:
                    k.is_deleted = True
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"KDV tanımları kaydedilemedi: {e}")
            raise

    def build_gorunum_panel(self) -> QWidget:
        """Mevcut Görünüm Profilleri Paneli (kabuk içinde: yalnız içerik)."""
        self.view_settings_tab = ViewSettingsWidget(embedded=True)
        return self.view_settings_tab

    def build_ekran_grid_panel(self) -> QWidget:
        """Ekran Şablonları & Grid Tanımları Paneli (kabuk içinde: yalnız içerik)."""
        self.screen_defs_tab = ScreenDefinitionsManagerWidget(embedded=True)
        return self.screen_defs_tab

    def build_form_tasarimlari_panel(self) -> QWidget:
        """Baskı formu şablonları — diğer tanım tabloları gibi standart dbgrid; yeni ekleme/
        tasarımcıda açma/silme İŞLEMLER panelinden ve sağ tıktan yapılır (bkz. `_panel_actions`)."""
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(12, 12, 12, 12)
        lyt.setSpacing(8)

        self._panel_baslik(
            lyt, "🖨️ Form Tasarımları",
            "Teklif / Sipariş / İrsaliye / Fatura baskı formları. Yeni form eklerken hangi modül "
            "için tasarlandığı seçilir; belge ekranındaki şablon seçici o forma göre otomatik "
            "öneride bulunur. Ekle / Tasarımcıda Aç / Sil işlemleri sağdaki İŞLEMLER'den ya da "
            "satıra sağ tıklayarak yapılır.",
        )

        self.tbl_form_tasarim = self._new_grid(
            "form_tasarim", ["Form Adı", "Modül", "Sayfa Boyutu", "Dosya"], stretch=0, editable=False,
        )
        self.tbl_form_tasarim.doubleClicked.connect(lambda _i: self._form_tasarim_ac())
        self._load_form_tasarimlari()
        lyt.addWidget(self.tbl_form_tasarim.container, 1)
        return w

    def _load_form_tasarimlari(self) -> None:
        """`form_tasarimlari` dbgrid'ini şablon dosyalarından yeniden doldurur."""
        from src.core.belge_turleri import BELGE_TURLERI
        from src.desktop.designer.services.teklif_print_service import (
            TeklifPrintService,
        )

        tbl = getattr(self, "tbl_form_tasarim", None)
        if tbl is None:
            return
        salt_okunur = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        tbl.setRowCount(0)
        for title, path_str, module in TeklifPrintService.available_templates_full():
            path = Path(path_str)
            try:
                size = json.loads(path.read_text(encoding="utf-8")).get("page", {}).get("size", "A4")
            except (OSError, ValueError):
                size = "A4"
            r = tbl.rowCount()
            tbl.insertRow(r)
            for c, text in enumerate((title, BELGE_TURLERI.get(module, module or "—"), size, path.name)):
                it = QStandardItem(text)
                it.setFlags(salt_okunur)
                if c == 3:
                    it.setData(str(path), Qt.ItemDataRole.UserRole)
                tbl.setItem(r, c, it)

    def _form_tasarim_secili_yol(self) -> Path | None:
        tbl = getattr(self, "tbl_form_tasarim", None)
        if tbl is None:
            return None
        row = tbl.currentRow()
        if row < 0:
            return None
        it = tbl.item(row, 3)
        data = it.data(Qt.ItemDataRole.UserRole) if it else None
        return Path(data) if data else None

    def _form_tasarim_ekle(self) -> None:
        from src.desktop.ui.widgets.form_designs_widget import (
            YeniFormDialog,
            create_blank_form,
        )

        dlg = YeniFormDialog(self)
        if not dlg.exec():
            return
        ad, modul, boyut = dlg.values()
        path = create_blank_form(ad, modul, boyut)
        self._load_form_tasarimlari()
        self._form_tasarim_ac_yol(path)

    def _form_tasarim_ac(self) -> None:
        path = self._form_tasarim_secili_yol()
        if path is None:
            QMessageBox.information(self, "Form Tasarımları", "Önce bir form seçin.")
            return
        self._form_tasarim_ac_yol(path)

    def _form_tasarim_ac_yol(self, path: Path) -> None:
        from src.desktop.designer.ui.designer_window import ReportDesignerWindow

        self._form_designer_win = ReportDesignerWindow(template_path=path, parent=self)
        self._form_designer_win.setWindowModality(Qt.WindowModality.NonModal)
        self._form_designer_win.destroyed.connect(self._load_form_tasarimlari)
        self._form_designer_win.show()

    def _form_tasarim_sil(self) -> None:
        path = self._form_tasarim_secili_yol()
        if path is None:
            QMessageBox.information(self, "Form Tasarımları", "Önce bir form seçin.")
            return
        if QMessageBox.question(
            self, "Formu Sil", f"'{path.name}' silinsin mi? Bu işlem geri alınamaz.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError as exc:
            QMessageBox.critical(self, "Hata", f"Dosya silinemedi:\n{exc}")
            return
        self._load_form_tasarimlari()
        self.toast_requested.emit(f"'{path.name}' silindi.", "info")

    def build_surum_panel(self) -> QWidget:
        """Sürüm & Git Takibi Paneli (kabuk içinde: yalnız içerik)."""
        self.git_tracker_tab = GitTrackerWidget(embedded=True, defer_load=True)
        return self.git_tracker_tab

    def build_yardim_panel(self) -> QWidget:
        """Yardım Paneli — bugüne kadar tamamlanan bölümlerin kullanıcıya yönelik kısa kılavuzu."""
        self.yardim_tab = YardimWidget()
        return self.yardim_tab

    def build_eposta_smtp_panel(self) -> QWidget:
        """E-Posta / SMTP giden sunucu ayarları."""
        from src.desktop.ui.widgets.smtp_settings_widget import SmtpSettingsWidget
        w = SmtpSettingsWidget(self.db)
        w.toast_requested.connect(self.toast_requested)
        return w

    def build_online_portal_panel(self) -> QWidget:
        """Online teklif portalı (cPanel) adresi ve API anahtarı."""
        from src.desktop.ui.widgets.portal_settings_widget import PortalSettingsWidget
        w = PortalSettingsWidget(self.db)
        w.toast_requested.connect(self.toast_requested)
        return w

    def build_portal_yayin_panel(self) -> QWidget:
        """Portal güncelleme paketini üretip FTP ile cPanel'e gönderme — birden çok site/sunucu profili
        standart dbgrid'de listelenir; işlemler sağdaki İŞLEMLER'den ve sağ tıktan yapılır (bkz. `_panel_actions`)."""
        from src.desktop.ui.widgets.portal_deploy_widget import PortalDeployWidget
        w = PortalDeployWidget(self.db)
        w.toast_requested.connect(self.toast_requested)
        tv = w.tbl_profil.table_view
        tv.container = w.tbl_profil
        tv.context_actions_provider = self._panel_context_actions
        tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tv.customContextMenuRequested.connect(lambda pos, t=tv: self._ayar_grid_menu(t, pos))
        self.portal_deploy_tab = w
        return w

    def build_yedek_merkezi_panel(self) -> QWidget:
        """TOYA veritabanı/dosya yedekleme işleri, zamanlama, şifreleme ve dış hedefler."""
        from src.desktop.ui.widgets.backup_center_widget import BackupCenterWidget
        w = BackupCenterWidget(self.db)
        w.toast_requested.connect(self.toast_requested)
        return w

    def build_portal_yedek_panel(self) -> QWidget:
        """Portal veritabanı yedeğini bu bilgisayara indirme (dış kopya)."""
        from src.desktop.ui.widgets.portal_backup_widget import PortalBackupWidget
        w = PortalBackupWidget(self.db)
        w.toast_requested.connect(self.toast_requested)
        return w

    def build_guvenlik_panel(self) -> QWidget:
        """Giriş güvenliği: kilit programı, uyarı penceresi ve kurtarma yöntemleri."""
        from src.desktop.services import settings_store
        from src.desktop.services.auth_service import (
            DEFAULT_AUTOCLOSE_SECONDS,
            DEFAULT_LOCKOUT_SCHEDULE,
            KEY_AUTOCLOSE_SECONDS,
            KEY_LOCKOUT_ENABLED,
            KEY_LOCKOUT_SCHEDULE,
            KEY_RECOVERY_EMAIL_ENABLED,
            KEY_RECOVERY_SQ_ENABLED,
        )

        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(16, 14, 16, 14)
        lyt.setSpacing(10)

        self._panel_baslik(lyt, "🔐 Güvenlik & Giriş", "")

        # --- Giriş kilidi ---
        self.chk_lockout_enabled = QCheckBox("Ard arda hatalı girişte geçici kilit uygula")
        self.chk_lockout_enabled.setChecked(
            settings_store.get_bool(self.db, KEY_LOCKOUT_ENABLED, True),
        )
        lyt.addWidget(self.chk_lockout_enabled)

        lyt.addWidget(QLabel("Kilit programı (hatalı deneme sayısı → kilit saniyesi):"))
        self.tbl_lockout = self._new_grid("tbl_lockout", ["Deneme Sayısı", "Kilit (sn)"])
        self.tbl_lockout.container.setMaximumHeight(160)
        schedule = settings_store.get_json(self.db, KEY_LOCKOUT_SCHEDULE, DEFAULT_LOCKOUT_SCHEDULE)
        for pair in schedule:
            try:
                r = self.tbl_lockout.rowCount()
                self.tbl_lockout.insertRow(r)
                self.tbl_lockout.setItem(r, 0, QStandardItem(str(int(pair[0]))))
                self.tbl_lockout.setItem(r, 1, QStandardItem(str(int(pair[1]))))
            except (TypeError, ValueError, IndexError):
                continue
        lyt.addWidget(self.tbl_lockout.container)

        row_btns = QHBoxLayout()
        b_add = QPushButton("➕ Satır")
        b_add.setStyleSheet(self.btn_style())
        b_add.clicked.connect(lambda: self._add_table_row(self.tbl_lockout, ["6", "600"]))
        b_del = QPushButton("🗑️ Sil")
        b_del.setStyleSheet(self.btn_style(DANGER_BG, DANGER_FG))
        b_del.clicked.connect(lambda: self._delete_table_row(self.tbl_lockout))
        row_btns.addWidget(b_add)
        row_btns.addWidget(b_del)
        row_btns.addStretch()
        lyt.addLayout(row_btns)

        # --- Uyarı penceresi ---
        form = QFormLayout()
        self.spin_autoclose = QSpinBox()
        self.spin_autoclose.setRange(0, 120)
        self.spin_autoclose.setValue(
            settings_store.get_int(self.db, KEY_AUTOCLOSE_SECONDS, DEFAULT_AUTOCLOSE_SECONDS),
        )
        self.spin_autoclose.setSuffix(" sn")
        self.spin_autoclose.setSpecialValueText("Kapalı")
        form.addRow("Hatalı giriş penceresi otomatik kapanma", self.spin_autoclose)
        lyt.addLayout(form)

        # --- Kurtarma yöntemleri ---
        lyt.addWidget(QLabel("'Şifremi Unuttum' yöntemleri:"))
        self.chk_recovery_sq = QCheckBox("Güvenlik soruları")
        self.chk_recovery_sq.setChecked(
            settings_store.get_bool(self.db, KEY_RECOVERY_SQ_ENABLED, True),
        )
        self.chk_recovery_email = QCheckBox("E-posta ile sıfırlama (SMTP gerektirir)")
        self.chk_recovery_email.setChecked(
            settings_store.get_bool(self.db, KEY_RECOVERY_EMAIL_ENABLED, True),
        )
        lyt.addWidget(self.chk_recovery_sq)
        lyt.addWidget(self.chk_recovery_email)

        b_save = QPushButton("💾 Kaydet")
        b_save.setStyleSheet(self.btn_style(PRIMARY, "#ffffff"))
        b_save.clicked.connect(self._save_guvenlik_panel)
        row_save = QHBoxLayout()
        row_save.addStretch()
        row_save.addWidget(b_save)
        lyt.addLayout(row_save)
        lyt.addStretch()
        return w

    def _save_guvenlik_panel(self) -> None:
        from src.desktop.services import settings_store
        from src.desktop.services.auth_service import (
            KEY_AUTOCLOSE_SECONDS,
            KEY_LOCKOUT_ENABLED,
            KEY_LOCKOUT_SCHEDULE,
            KEY_RECOVERY_EMAIL_ENABLED,
            KEY_RECOVERY_SQ_ENABLED,
        )

        schedule: list[list[int]] = []
        for r in range(self.tbl_lockout.rowCount()):
            try:
                attempts = int(self.tbl_lockout.item(r, 0).text().strip())
                secs = int(self.tbl_lockout.item(r, 1).text().strip())
                schedule.append([attempts, secs])
            except (AttributeError, ValueError):
                continue
        schedule.sort()

        try:
            settings_store.set_setting(
                self.db, KEY_LOCKOUT_ENABLED,
                "1" if self.chk_lockout_enabled.isChecked() else "0", commit=False,
            )
            settings_store.set_setting(
                self.db, KEY_LOCKOUT_SCHEDULE, json.dumps(schedule), commit=False,
            )
            settings_store.set_setting(
                self.db, KEY_AUTOCLOSE_SECONDS, self.spin_autoclose.value(), commit=False,
            )
            settings_store.set_setting(
                self.db, KEY_RECOVERY_SQ_ENABLED,
                "1" if self.chk_recovery_sq.isChecked() else "0", commit=False,
            )
            settings_store.set_setting(
                self.db, KEY_RECOVERY_EMAIL_ENABLED,
                "1" if self.chk_recovery_email.isChecked() else "0", commit=True,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Güvenlik", f"Kaydedilemedi: {exc}")
            return
        self.toast_requested.emit("Güvenlik ayarları kaydedildi", "success")
        QMessageBox.information(self, "Güvenlik", "Ayarlar kaydedildi.")

    def build_sayi_bicimi_panel(self) -> QWidget:
        """Sayısal/fiyat alanlarının ondalık hane sayısını (maske) belirler.

        Burada seçilen değer `MaskedDecimalField` tabanlı tüm alanlara
        (stok/cari fiyat alanları vb.) otomatik olarak yansır — alan bazlı
        ayrı bir ayar yoktur, tek bir global tercih tüm ekranları biçimlendirir.
        """
        from src.desktop.services import settings_store

        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(16, 14, 16, 14)
        lyt.setSpacing(10)

        self._panel_baslik(lyt, "🔢 Sayı Biçimi", "Fiyat/tutar alanlarında virgülden sonra kaç hane girileceğini belirler. "
                          "'Genel' değer kartlardaki (Stok, Cari) fiyat alanlarına; 'Belge satırı' değerleri teklif / sipariş / "
                          "irsaliye / fatura kalemlerindeki kur, birim fiyat, miktar ve tutar hücrelerine uygulanır "
                          "(önerilen: kur 4, fiyat 4, miktar 2, toplam 2).")

        form = QFormLayout()
        self.spin_ondalik_hane = QSpinBox()
        self.spin_ondalik_hane.setRange(0, 6)
        self.spin_ondalik_hane.setValue(
            settings_store.get_int(
                self.db, settings_store.DECIMAL_PLACES_KEY,
                settings_store.DEFAULT_DECIMAL_PLACES,
            ),
        )
        self.spin_ondalik_hane.setSuffix(" hane")
        form.addRow("Genel (kartlardaki fiyat alanları)", self.spin_ondalik_hane)
        from src.desktop.services import sayi_bicimi
        sayi_bicimi.yukle(self.db)
        self.spin_hane = {}
        for tur, (_anahtar, _varsayilan, ad) in sayi_bicimi.TURLER.items():
            sp = QSpinBox()
            sp.setRange(0, 6)
            sp.setSuffix(" hane")
            sp.setValue(sayi_bicimi.hane(tur))
            self.spin_hane[tur] = sp
            form.addRow(f"Belge satırı: {ad}", sp)
        lyt.addLayout(form)

        self.lbl_ondalik_ornek = QLabel()
        self.lbl_ondalik_ornek.setStyleSheet("color:#334155; font-size:11px;")
        self.spin_ondalik_hane.valueChanged.connect(self._update_ondalik_ornek)
        self._update_ondalik_ornek(self.spin_ondalik_hane.value())
        lyt.addWidget(self.lbl_ondalik_ornek)

        b_save = QPushButton("💾 Kaydet")
        b_save.setStyleSheet(self.btn_style(PRIMARY, "#ffffff"))
        b_save.clicked.connect(self._save_sayi_bicimi_panel)
        row_save = QHBoxLayout()
        row_save.addStretch()
        row_save.addWidget(b_save)
        lyt.addLayout(row_save)
        lyt.addStretch()
        return w

    def _update_ondalik_ornek(self, decimals: int) -> None:
        ornek = f"{1585686.5:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.lbl_ondalik_ornek.setText(f"Örnek görünüm: {ornek}")

    def _save_sayi_bicimi_panel(self) -> None:
        from src.desktop.services import settings_store

        try:
            settings_store.set_setting(
                self.db, settings_store.DECIMAL_PLACES_KEY,
                self.spin_ondalik_hane.value(),
            )
            from src.desktop.services import sayi_bicimi
            sayi_bicimi.kaydet(self.db, {t: sp.value() for t, sp in self.spin_hane.items()})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Sayı Biçimi", f"Kaydedilemedi: {exc}")
            return
        self.toast_requested.emit("Sayı biçimi kaydedildi", "success")
        QMessageBox.information(
            self, "Sayı Biçimi",
            "Ayar kaydedildi. Açık ekranlara yansıması için ekranın yeniden "
            "açılması gerekir.",
        )

    # ─────────────────────────────────────────────────────────────
    # DB LOAD & SAVE METHODS
    # ─────────────────────────────────────────────────────────────

    def _load_birimler_from_db(self) -> None:
        """Aktif firmanın birim tanımlarını yükler (2026-09-30: artık `company_id` ile firmaya bağlı).
        Firmanın hiç birimi yoksa, kaydedilmeden ekrana örnek varsayılan liste önerilir."""
        if not self.db:
            return
        from src.desktop.services.company_service import CompanyService
        firma = CompanyService(self.db).aktif_firma()
        self.tbl_birim.setRowCount(0)
        try:
            units = self.db.scalars(
                select(UnitDefinition).where(UnitDefinition.is_deleted == False,  # noqa: E712
                                              UnitDefinition.company_id == (firma.id if firma else None)),
            ).all() if firma else []
            kaynak = [(u.code or "", u.name or "", "Aktif" if u.is_active else "Pasif") for u in units] \
                if units else self._VARSAYILAN_BIRIMLER
            for row_data in kaynak:
                r = self.tbl_birim.rowCount()
                self.tbl_birim.insertRow(r)
                for c, val in enumerate(row_data):
                    self.tbl_birim.setItem(r, c, QStandardItem(val))
        except Exception as e:
            logger.warning(f"Birim listesi yüklenemedi: {e}")

    def _save_birimler(self) -> None:
        """Birim tanımlarını aktif firmaya bağlı olarak DB'ye kaydeder."""
        if not self.db:
            return
        from src.desktop.services.company_service import CompanyService
        firma = CompanyService(self.db).aktif_firma()
        if firma is None:
            self._aktif_firma_uyar("Birim tanımlayabilmek")
            return
        try:
            existing = {
                u.code: u
                for u in self.db.scalars(
                    select(UnitDefinition).where(
                        UnitDefinition.is_deleted == False, UnitDefinition.company_id == firma.id,  # noqa: E712
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
                        company_id=firma.id,
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
                    tip_etiket = _ODEME_TIPI_KOD_TO_ETIKET.get(p.odeme_tipi or "", p.payment_type or "")
                    hesap_metni = (
                        f"{p.hedef_hesap.kod} — {p.hedef_hesap.ad}" if p.hedef_hesap else self._HEDEF_HESAP_BOS
                    )
                    banka_plani_metni = (
                        f"{p.banka_odeme_plani.kod} — {p.banka_odeme_plani.aciklama or ''}".rstrip(" —")
                        if p.banka_odeme_plani else self._BANKA_PLANI_BOS
                    )
                    self.tbl_odeme.setItem(r, 0, QStandardItem(p.code or ""))
                    self.tbl_odeme.setItem(
                        r, 1, QStandardItem(p.description or ""),
                    )
                    self.tbl_odeme.setItem(
                        r, 2, QStandardItem(str(p.days or 0)),
                    )
                    self.tbl_odeme.setItem(r, 3, QStandardItem(tip_etiket))
                    self.tbl_odeme.setItem(r, 4, QStandardItem(hesap_metni))
                    self.tbl_odeme.setItem(r, 5, QStandardItem(banka_plani_metni))
                    self.tbl_odeme.setItem(
                        r, 6, QStandardItem("Evet" if p.otomatik_fis_olustur else "Hayır"),
                    )
                    self.tbl_odeme.setItem(
                        r, 7, QStandardItem("Aktif" if p.is_active else "Pasif"),
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
            hesap_by_kod = {
                h.kod: h.id
                for h in self.db.scalars(select(FinansHesap).where(FinansHesap.aktif == True))  # noqa: E712
            }
            banka_plani_by_kod = {
                p.kod: p.id
                for p in self.db.scalars(
                    select(BankaOdemePlani).where(
                        BankaOdemePlani.is_deleted == False, BankaOdemePlani.is_active == True,  # noqa: E712
                    ),
                )
            }
            for r in range(self.tbl_odeme.rowCount()):
                code_item = self.tbl_odeme.item(r, 0)
                desc_item = self.tbl_odeme.item(r, 1)
                days_item = self.tbl_odeme.item(r, 2)
                type_item = self.tbl_odeme.item(r, 3)
                hesap_item = self.tbl_odeme.item(r, 4)
                banka_plani_item = self.tbl_odeme.item(r, 5)
                oto_item = self.tbl_odeme.item(r, 6)
                status_item = self.tbl_odeme.item(r, 7)

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
                tip_etiket = type_item.text().strip() if type_item else ""
                tip_kod = _ODEME_TIPI_ETIKET_TO_KOD.get(
                    tip_etiket, _ODEME_TIPI_ESKI_ESLEME.get(tip_etiket.lower()),
                )
                hesap_metni = hesap_item.text().strip() if hesap_item else ""
                hesap_kod = hesap_metni.split(" — ", 1)[0].strip() if " — " in hesap_metni else ""
                hedef_hesap_id = hesap_by_kod.get(hesap_kod)
                banka_plani_metni = banka_plani_item.text().strip() if banka_plani_item else ""
                banka_plani_kod = (
                    banka_plani_metni.split(" — ", 1)[0].strip() if " — " in banka_plani_metni else banka_plani_metni
                )
                banka_odeme_plani_id = banka_plani_by_kod.get(banka_plani_kod)
                otomatik = (oto_item.text().strip().lower() != "hayır") if oto_item else True
                is_act = (
                    (status_item.text().strip().lower() != "pasif")
                    if status_item
                    else True
                )

                if code in existing:
                    p = existing[code]
                    p.description = desc
                    p.days = days_val
                    p.payment_type = tip_etiket
                    p.odeme_tipi = tip_kod
                    p.hedef_finans_hesap_id = hedef_hesap_id
                    p.banka_odeme_plani_id = banka_odeme_plani_id
                    p.otomatik_fis_olustur = otomatik
                    p.is_active = is_act
                else:
                    new_p = PaymentPlan(
                        code=code,
                        description=desc,
                        days=days_val,
                        payment_type=tip_etiket,
                        odeme_tipi=tip_kod,
                        hedef_finans_hesap_id=hedef_hesap_id,
                        banka_odeme_plani_id=banka_odeme_plani_id,
                        otomatik_fis_olustur=otomatik,
                        is_active=is_act,
                    )
                    self.db.add(new_p)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Ödeme planları kaydedilemedi: {e}")
            raise

    def _load_banka_odeme_planlari_from_db(self) -> None:
        """DB'den banka ödeme planlarını yükler."""
        if not self.db:
            return
        try:
            planlar = self.db.scalars(
                select(BankaOdemePlani).where(BankaOdemePlani.is_deleted == False),  # noqa: E712
            ).all()
            self.tbl_banka_odeme.setRowCount(0)
            for p in planlar:
                r = self.tbl_banka_odeme.rowCount()
                self.tbl_banka_odeme.insertRow(r)
                hesap_metni = (
                    f"{p.finans_hesap.kod} — {p.finans_hesap.ad}" if p.finans_hesap else self._HEDEF_HESAP_BOS
                )
                vals = [
                    p.kod or "", p.aciklama or "", hesap_metni, str(p.taksit_sayisi or 1),
                    f"{p.komisyon_orani or 0:.2f}", f"{p.bsmv_orani or 0:.2f}", f"{p.hizmet_bedeli or 0:.2f}",
                    "Aktif" if p.is_active else "Pasif",
                ]
                for c, val in enumerate(vals):
                    self.tbl_banka_odeme.setItem(r, c, QStandardItem(val))
        except Exception as e:
            logger.warning(f"Banka ödeme planları yüklenemedi: {e}")

    def _save_banka_odeme_planlari(self) -> None:
        """Banka ödeme planlarını DB'ye kaydeder."""
        if not self.db:
            return
        try:
            existing = {
                p.kod: p
                for p in self.db.scalars(
                    select(BankaOdemePlani).where(BankaOdemePlani.is_deleted == False),  # noqa: E712
                ).all()
            }
            hesap_by_kod = {
                h.kod: h.id
                for h in self.db.scalars(select(FinansHesap).where(FinansHesap.aktif == True))  # noqa: E712
            }
            for r in range(self.tbl_banka_odeme.rowCount()):
                def _metin(col: int, _r=r) -> str:
                    it = self.tbl_banka_odeme.item(_r, col)
                    return it.text().strip() if it else ""

                kod = _metin(0)
                if not kod:
                    continue
                hesap_metni = _metin(2)
                hesap_kod = hesap_metni.split(" — ", 1)[0].strip() if " — " in hesap_metni else ""

                def _sayi(col: int, varsayilan: float = 0.0, _r=r) -> float:
                    it = self.tbl_banka_odeme.item(_r, col)
                    try:
                        return float((it.text() if it else "").strip().replace(",", ".") or varsayilan)
                    except ValueError:
                        return varsayilan

                alanlar = {
                    "aciklama": _metin(1),
                    "finans_hesap_id": hesap_by_kod.get(hesap_kod),
                    "taksit_sayisi": int(_sayi(3, 1)),
                    "komisyon_orani": _sayi(4, 0.0),
                    "bsmv_orani": _sayi(5, 5.0),
                    "hizmet_bedeli": _sayi(6, 0.0),
                    "is_active": _metin(7).lower() != "pasif",
                }
                if kod in existing:
                    p = existing[kod]
                    for alan, deger in alanlar.items():
                        setattr(p, alan, deger)
                else:
                    self.db.add(BankaOdemePlani(kod=kod, **alanlar))
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Banka ödeme planları kaydedilemedi: {e}")
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
                        r, 0, QStandardItem(c.name or ""),
                    )
                    self.tbl_kategori.setItem(
                        r, 1, QStandardItem(parent_name),
                    )
                    self.tbl_kategori.setItem(r, 2, QStandardItem("Aktif"))
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
                                tbl.setItem(r, c, QStandardItem(str(val)))
                        return
            except Exception as e:
                logger.warning(f"Tablo yüklenemedi ({setting_key}): {e}")

        # Varsayılan veriler
        tbl.setRowCount(0)
        for row_data in default_data:
            r = tbl.rowCount()
            tbl.insertRow(r)
            for c, val in enumerate(row_data):
                tbl.setItem(r, c, QStandardItem(str(val)))

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
            "odeme_planlari": self._save_odeme_planlari,
            "banka_odeme_planlari": self._save_banka_odeme_planlari,
            "stok_ozel_alanlar": lambda: self._save_ozel_alanlar("stok"),
            "cari_ozel_alanlar": lambda: self._save_ozel_alanlar("cari"),
            "stok_kategoriler": self._save_kategoriler,
            # roller / yetkiler: kayıt kendi editör diyaloglarında; panelde Kaydet no-op
            "roller": lambda: None,
            "yetkiler": lambda: None,
            "kullanicilar": lambda: None,
            "fiyat_listeleri": lambda: self._save_generic_table(
                self.tbl_fiyat, "fiyat_listeleri",
            ),
            "kdv_oranlari": self._save_kdv_tablosu,
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
        if self.active_panel_id == "doviz_kur":
            self._open_yeni_doviz_dialog()
            return
        if self.active_panel_id == "odeme_planlari":
            self._yeni_odeme_plani_ekle()
            return
        if self.active_panel_id == "banka_odeme_planlari":
            self._yeni_banka_odeme_plani_ekle()
            return

        panel_table_map = {
            "fiyat_listeleri": "tbl_fiyat",
            "stok_kategoriler": "tbl_kategori",
            "stok_markalar": "tbl_marka",
            "birim_tanimlari": "tbl_birim",
            "cari_gruplari": "tbl_cari_grup",
        }
        tbl_attr = panel_table_map.get(self.active_panel_id)
        if tbl_attr and hasattr(self, tbl_attr):
            tbl: QTableWidget = getattr(self, tbl_attr)
            r = tbl.rowCount()
            tbl.insertRow(r)
            for c in range(tbl.columnCount()):
                tbl.setItem(r, c, QStandardItem(""))
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
        if self.active_panel_id == "doviz_kur":
            self._delete_selected_doviz_currency()
            return

        panel_table_map = {
            "odeme_planlari": "tbl_odeme",
            "banka_odeme_planlari": "tbl_banka_odeme",
            "fiyat_listeleri": "tbl_fiyat",
            "stok_kategoriler": "tbl_kategori",
            "stok_markalar": "tbl_marka",
            "birim_tanimlari": "tbl_birim",
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
