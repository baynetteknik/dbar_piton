import math
import os
from datetime import datetime

from PyQt6.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPixmap, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.data_manager import DataManager
from src.core.importer import CUSTOMER_FIELDS, export_to_excel_file
from src.core.models import Customer, Site
from src.core.repository import SqliteCustomerRepository
from src.core.sync.customer_sync import CustomerSyncEngine
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.import_dialog import ExcelImportDialog


class CustomerDialog(QDialog):
    """DIA stiline ve sekmeli yapısına sahip gelişmiş Cari Kart Ekle / Düzenle ekranı."""
    def __init__(self, db_session, company_id: int, customer_id=None, remote_id=None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.company_id = company_id
        self.customer_id = customer_id
        self.remote_id = remote_id
        self.photo_path = None
        
        from src.core.data_manager import DataManager
        self.working_mode = DataManager.get_company_mode(self.db, self.company_id)
        
        if self.customer_id or self.remote_id:
            self.setWindowTitle(self.tr("Cari Kart Düzenle"))
        else:
            self.setWindowTitle(self.tr("Yeni Cari Kart Ekle"))
        self.setMinimumWidth(850)
        self.setMinimumHeight(650)
        self.init_ui()
        if self.customer_id or self.remote_id:
            self.load_customer_data()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(18)

        # SOL TARAF: Sekmeler (TabWidget)
        left_layout = QVBoxLayout()
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
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

        # Sekme 1: Genel Bilgiler
        tab_general = QWidget()
        tab_general_layout = QVBoxLayout(tab_general)
        tab_general_layout.setSpacing(12)

        # Durum Grubu
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Durumu:"))
        self.chk_active = QCheckBox("Aktif")
        self.chk_active.setChecked(True)
        self.chk_rehber = QCheckBox("Rehber'de Gözüksün")
        status_layout.addWidget(self.chk_active)
        status_layout.addWidget(self.chk_rehber)
        status_layout.addStretch()
        tab_general_layout.addLayout(status_layout)

        # Temel Bilgiler Form
        from PyQt6.QtWidgets import QFormLayout
        form_gen = QFormLayout()
        form_gen.setSpacing(10)
        
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("CR00001 (Otomatik oluşturulur...)")
        self.txt_fullname = QLineEdit()
        self.txt_fullname.setPlaceholderText("AK İTHALAT İHRACAT LTD ŞTİ")
        self.txt_authorized = QLineEdit()
        self.txt_authorized.setPlaceholderText("Yetkili Adı Soyadı")
        self.txt_nickname = QLineEdit()
        self.txt_nickname.setPlaceholderText("Opsiyonel rumuz veya kısa not")
        
        self.cmb_group = QComboBox()
        self.cmb_group.addItems(["ALICI", "SATICI", "ALICI / SATICI", "POTANSİYEL"])
        self.cmb_subgroup1 = QComboBox()
        self.cmb_subgroup1.addItems(["ÖZEL", "PERAKENDE", "TOPTAN"])
        self.txt_subgroup2 = QLineEdit()
        self.txt_special_code1 = QLineEdit()

        form_gen.addRow("Cari Kodu:", self.txt_code)
        form_gen.addRow("Ticari Ünvan *:", self.txt_fullname)
        form_gen.addRow("Yetkili Kişi:", self.txt_authorized)
        form_gen.addRow("Kısa Rumuz:", self.txt_nickname)
        form_gen.addRow("Grubu:", self.cmb_group)
        form_gen.addRow("Ara Grubu:", self.cmb_subgroup1)
        form_gen.addRow("Alt Grubu:", self.txt_subgroup2)
        form_gen.addRow("Özel Kod 1:", self.txt_special_code1)

        tab_general_layout.addLayout(form_gen)
        tab_general_layout.addStretch()
        self.tabs.addTab(tab_general, "Genel Bilgiler")

        # Sekme 2: İletişim Bilgileri
        tab_contact = QWidget()
        tab_contact_layout = QVBoxLayout(tab_contact)
        form_contact = QFormLayout()
        form_contact.setSpacing(10)

        self.txt_phone1 = QLineEdit()
        self.txt_phone2 = QLineEdit()
        self.txt_phone_home = QLineEdit()
        self.txt_phone_cell = QLineEdit()
        self.txt_email = QLineEdit()
        self.txt_fax = QLineEdit()
        self.txt_website = QLineEdit()

        form_contact.addRow("Telefon 1:", self.txt_phone1)
        form_contact.addRow("Telefon 2:", self.txt_phone2)
        form_contact.addRow("Ev Telefonu:", self.txt_phone_home)
        form_contact.addRow("Cep Telefonu:", self.txt_phone_cell)
        form_contact.addRow("E-Posta:", self.txt_email)
        form_contact.addRow("Faks:", self.txt_fax)
        form_contact.addRow("Web Sitesi:", self.txt_website)

        tab_contact_layout.addLayout(form_contact)
        tab_contact_layout.addStretch()
        self.tabs.addTab(tab_contact, "İletişim")

        # Sekme 3: Adres Bilgileri
        tab_address = QWidget()
        tab_address_layout = QVBoxLayout(tab_address)
        form_address = QFormLayout()
        form_address.setSpacing(10)

        self.txt_address = QTextEdit()
        self.txt_address.setPlaceholderText("Fatura adresi satırı 1...")
        self.txt_address.setMaximumHeight(80)
        self.txt_address2 = QLineEdit()
        self.txt_address2.setPlaceholderText("Fatura adresi satırı 2...")
        self.txt_city = QLineEdit()
        self.txt_district = QLineEdit()
        self.txt_country = QLineEdit()
        self.txt_country.setText("TÜRKİYE")
        self.txt_postcode = QLineEdit()
        self.txt_region = QLineEdit()

        form_address.addRow("Adres 1:", self.txt_address)
        form_address.addRow("Adres 2:", self.txt_address2)
        form_address.addRow("Şehir:", self.txt_city)
        form_address.addRow("İlçe:", self.txt_district)
        form_address.addRow("Ülke:", self.txt_country)
        form_address.addRow("Posta Kodu:", self.txt_postcode)
        form_address.addRow("Bölge:", self.txt_region)

        tab_address_layout.addLayout(form_address)
        tab_address_layout.addStretch()
        self.tabs.addTab(tab_address, "Adresler")

        # Sekme 4: Vergi Bilgileri
        tab_tax = QWidget()
        tab_tax_layout = QVBoxLayout(tab_tax)
        form_tax = QFormLayout()
        form_tax.setSpacing(10)

        self.txt_tax_office = QLineEdit()
        self.txt_tax_number = QLineEdit()
        self.txt_tc_number = QLineEdit()

        form_tax.addRow("Vergi Dairesi:", self.txt_tax_office)
        form_tax.addRow("Vergi Numarası:", self.txt_tax_number)
        form_tax.addRow("T.C. Kimlik No:", self.txt_tc_number)

        tab_tax_layout.addLayout(form_tax)
        tab_tax_layout.addStretch()
        self.tabs.addTab(tab_tax, "Vergi Bilgileri")

        # Sekme 5: E-Fatura ve Diğer
        tab_efatura = QWidget()
        tab_efatura_layout = QVBoxLayout(tab_efatura)
        form_efatura = QFormLayout()
        form_efatura.setSpacing(10)

        self.cmb_efatura_user = QComboBox()
        self.cmb_efatura_user.addItems(["E-Fatura Kullanıcısı Değil", "E-Fatura Kullanıcısı"])
        self.txt_efatura_mailbox = QLineEdit()
        self.cmb_efatura_control = QComboBox()
        self.cmb_efatura_control.addItems(["Kayıtlı Değil", "Kayıtlı"])
        
        # Abone grup
        abone_layout = QHBoxLayout()
        self.chk_email_sub = QCheckBox("E-Posta Abone")
        self.chk_email_sub.setChecked(True)
        self.chk_sms_sub = QCheckBox("SMS Abone")
        abone_layout.addWidget(self.chk_email_sub)
        abone_layout.addWidget(self.chk_sms_sub)

        form_efatura.addRow("E-Fatura Durumu:", self.cmb_efatura_user)
        form_efatura.addRow("Posta Kutusu:", self.txt_efatura_mailbox)
        form_efatura.addRow("E-Fatura Kontrol:", self.cmb_efatura_control)
        form_efatura.addRow("Abonelikler:", abone_layout)

        tab_efatura_layout.addLayout(form_efatura)
        tab_efatura_layout.addStretch()
        self.tabs.addTab(tab_efatura, "E-Fatura")

        # Sekme 6: Özel Kodlar ve Notlar
        tab_notes = QWidget()
        tab_notes_layout = QVBoxLayout(tab_notes)
        form_notes = QFormLayout()
        form_notes.setSpacing(10)

        self.txt_special_code2 = QLineEdit()
        self.txt_special_code3 = QLineEdit()
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Genel notlar ve açıklamalar...")
        self.txt_notes.setMaximumHeight(150)
        
        self.date_record = QDateEdit()
        self.date_record.setCalendarPopup(True)
        self.date_record.setDate(QDate.currentDate())

        form_notes.addRow("Özel Kod 2:", self.txt_special_code2)
        form_notes.addRow("Özel Kod 3:", self.txt_special_code3)
        form_notes.addRow("Kayıt Tarihi:", self.date_record)
        form_notes.addRow("Notlar:", self.txt_notes)

        tab_notes_layout.addLayout(form_notes)
        tab_notes_layout.addStretch()
        self.tabs.addTab(tab_notes, "Özel Kodlar & Notlar")

        left_layout.addWidget(self.tabs)

        # Girdilerin CSS stilleri
        input_style = """
            QLineEdit, QComboBox, QTextEdit, QDateEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                color: #0f172a;
            }
            QLineEdit:focus, QTextEdit:focus { border-color: #3b82f6; }
        """
        for tab in [tab_general, tab_contact, tab_address, tab_tax, tab_efatura, tab_notes]:
            for widget in tab.findChildren((QLineEdit, QComboBox, QTextEdit, QDateEdit)):
                widget.setStyleSheet(input_style)

        # Alt Buton Grubu
        btn_group_layout = QHBoxLayout()
        btn_group_layout.setSpacing(8)
        
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.btn_save.clicked.connect(self.save_customer)

        self.btn_cancel = QPushButton("✖ Vazgeç")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #64748b;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        btn_group_layout.addWidget(self.btn_save)
        btn_group_layout.addWidget(self.btn_cancel)
        btn_group_layout.addStretch()
        
        left_layout.addLayout(btn_group_layout)
        main_layout.addLayout(left_layout, 7)

        # SAĞ TARAF: Profil Resmi (Avatar) & Fotoğraf Paneli
        right_panel = QFrame()
        right_panel.setObjectName("RightPanel")
        right_panel.setStyleSheet("""
            QFrame#RightPanel {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(12)

        pic_title = QLabel("Cari Fotoğrafı")
        pic_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        pic_title.setStyleSheet("color: #475569;")
        pic_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(pic_title)

        # Resim Çerçevesi
        self.photo_label = QLabel()
        self.photo_label.setFixedSize(160, 210)
        self.photo_label.setStyleSheet("background-color: #cbd5e1; border: 1px solid #94a3b8; border-radius: 6px;")
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_default_avatar()
        right_layout.addWidget(self.photo_label)

        # Kamera / Dosya Seç butonları
        self.btn_change_photo = QPushButton("📷 Resmi Değiştir")
        self.btn_change_photo.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.btn_change_photo.clicked.connect(self.change_photo)
        right_layout.addWidget(self.btn_change_photo)

        self.btn_remove_photo = QPushButton("🗑️ Resmi Sil")
        self.btn_remove_photo.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #dc2626; }
        """)
        self.btn_remove_photo.clicked.connect(self.remove_photo)
        right_layout.addWidget(self.btn_remove_photo)

        right_layout.addStretch()
        main_layout.addWidget(right_panel, 3)

    def set_default_avatar(self):
        self.photo_label.setText("👤 Resim Yok")
        self.photo_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.photo_label.setStyleSheet("background-color: #e2e8f0; color: #64748b; border: 1px dashed #cbd5e1; border-radius: 6px;")

    def change_photo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Cari Fotoğrafı Seç"), "",
            "Görsel Dosyaları (*.png *.jpg *.jpeg *.bmp)",
        )
        if file_path:
            self.photo_path = file_path
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.photo_label.setPixmap(pixmap.scaled(self.photo_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.photo_label.setStyleSheet("border: 1px solid #94a3b8; border-radius: 6px;")

    def remove_photo(self):
        self.photo_path = None
        self.set_default_avatar()

    def load_customer_data(self):
        from src.adapters.mappers import DolibarrMapper
        from src.core.data_manager import DataManager
        
        if self.working_mode == "direct_online" and self.remote_id:
            try:
                adapter = DataManager._get_adapter(self.db, self.company_id)
                raw = adapter.fetch_customer_by_id(self.remote_id)
                if raw:
                    cust = DolibarrMapper.to_customer_orm(self.company_id, raw)
                else:
                    cust = None
            except Exception as e:
                QMessageBox.critical(self, self.tr("Hata"), f"Müşteri bilgileri uzak sunucudan çekilemedi: {e}")
                return
        else:
            cust = self.db.query(Customer).filter(Customer.id == self.customer_id).first()
            
        if cust:
            self.txt_code.setText(cust.customer_code or "")
            self.txt_fullname.setText(cust.fullname)
            self.txt_authorized.setText(cust.authorized_person or "")
            self.txt_nickname.setText(cust.nickname or "")
            
            self.cmb_group.setCurrentText(cust.group_name or "ALICI")
            self.cmb_subgroup1.setCurrentText(cust.sub_group_1 or "ÖZEL")
            self.txt_subgroup2.setText(cust.sub_group_2 or "")
            self.txt_special_code1.setText(cust.special_code_1 or "")
            self.txt_special_code2.setText(cust.special_code_2 or "")
            self.txt_special_code3.setText(cust.special_code_3 or "")
            
            self.chk_active.setChecked(cust.status == 1)
            
            # İletişim
            self.txt_phone1.setText(cust.phone or "")
            self.txt_phone2.setText(cust.phone2 or "")
            self.txt_phone_home.setText(cust.phone_home or "")
            self.txt_phone_cell.setText(cust.phone or "")
            self.txt_email.setText(cust.email or "")
            self.txt_fax.setText(cust.fax or "")
            self.txt_website.setText(cust.website or "")

            # Adres
            self.txt_address.setPlainText(cust.address or "")
            self.txt_address2.setText(cust.address2 or "")
            self.txt_city.setText(cust.city or "")
            self.txt_district.setText(cust.district or "")
            self.txt_country.setText(cust.country or "TÜRKİYE")
            self.txt_postcode.setText(cust.postcode or "")
            self.txt_region.setText(cust.region or "")

            # Vergi
            self.txt_tax_office.setText(cust.tax_office or "")
            self.txt_tax_number.setText(cust.tax_number or "")

            # E-Fatura
            self.cmb_efatura_user.setCurrentText(cust.efatura_user or "E-Fatura Kullanıcısı Değil")
            self.txt_efatura_mailbox.setText(cust.efatura_mailbox or "")

            # Notlar & Tarih
            self.txt_notes.setPlainText(cust.notes or "")
            if cust.record_date:
                self.date_record.setDate(QDate(cust.record_date.year, cust.record_date.month, cust.record_date.day))
                
            # Fotoğraf
            if cust.photo_path and os.path.exists(cust.photo_path):
                self.photo_path = cust.photo_path
                pixmap = QPixmap(cust.photo_path)
                self.photo_label.setPixmap(pixmap.scaled(self.photo_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.photo_label.setStyleSheet("border: 1px solid #94a3b8; border-radius: 6px;")

    def save_customer(self):
        fullname = self.txt_fullname.text().strip()
        if not fullname:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Lütfen Ticari Ünvan alanını doldurun."))
            return
            
        try:
            from src.core.data_manager import DataManager
            from src.core.models import ChangeLog
            
            if self.working_mode == "direct_online":
                cust = Customer(marketplace="dolibarr")
                if self.remote_id:
                    cust.remote_id = self.remote_id
            else:
                if self.customer_id:
                    cust = self.db.query(Customer).filter(Customer.id == self.customer_id).first()
                else:
                    cust = Customer(marketplace="local")
                    self.db.add(cust)
                    self.db.flush()

            cust.customer_code = self.txt_code.text().strip() or None
            cust.fullname = fullname
            cust.authorized_person = self.txt_authorized.text().strip() or None
            cust.nickname = self.txt_nickname.text().strip() or None
            cust.group_name = self.cmb_group.currentText()
            cust.sub_group_1 = self.cmb_subgroup1.currentText()
            cust.sub_group_2 = self.txt_subgroup2.text().strip() or None
            cust.special_code_1 = self.txt_special_code1.text().strip() or None
            cust.special_code_2 = self.txt_special_code2.text().strip() or None
            cust.special_code_3 = self.txt_special_code3.text().strip() or None
            cust.status = 1 if self.chk_active.isChecked() else 0

            # İletişim
            cust.phone = self.txt_phone1.text().strip() or None
            cust.phone2 = self.txt_phone2.text().strip() or None
            cust.phone_home = self.txt_phone_home.text().strip() or None
            cust.email = self.txt_email.text().strip() or None
            cust.fax = self.txt_fax.text().strip() or None
            cust.website = self.txt_website.text().strip() or None

            # Adres
            cust.address = self.txt_address.toPlainText().strip() or None
            cust.address2 = self.txt_address2.text().strip() or None
            cust.city = self.txt_city.text().strip() or None
            cust.district = self.txt_district.text().strip() or None
            cust.country = self.txt_country.text().strip() or None
            cust.postcode = self.txt_postcode.text().strip() or None
            cust.region = self.txt_region.text().strip() or None

            # Vergi
            cust.tax_office = self.txt_tax_office.text().strip() or None
            cust.tax_number = self.txt_tax_number.text().strip() or None

            # E-Fatura
            cust.efatura_user = self.cmb_efatura_user.currentText()
            cust.efatura_mailbox = self.txt_efatura_mailbox.text().strip() or None

            # Notlar
            cust.notes = self.txt_notes.toPlainText().strip() or None
            
            # Tarih
            qdate = self.date_record.date()
            cust.record_date = datetime(qdate.year(), qdate.month(), qdate.day())
            cust.photo_path = self.photo_path
            cust.updated_at = datetime.utcnow()

            # Kaydetme işlemi
            if self.working_mode == "direct_online":
                success = DataManager.save_customer(self.db, self.company_id, cust)
                if not success:
                    raise Exception("Uzak sunucuya kayıt gönderilemedi.")
            else:
                from src.core.models import Site
                active_dolibarr = self.db.query(Site).filter(Site.cms_type == "dolibarr", Site.is_active == True).first()
                if active_dolibarr:
                    action = "update" if self.customer_id else "create"
                    changelog = ChangeLog(
                        entity_type="customer",
                        entity_id=cust.id,
                        action=action,
                        status="PENDING_PUSH",
                        retry_count=0,
                    )
                    self.db.add(changelog)
                self.db.commit()

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), f"Cari kart kaydedilemedi: {e}")


class SyncWorker(QThread):
    """Senkronizasyon işlemini arayüzü kilitlemeden arka planda (QThread) çalıştıran işçi."""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(bool, str, int)  # success, message, undo_point_id

    def __init__(self, db_session, direction, site_id, conflict_strategy, selected_ids=None):
        super().__init__()
        self.db = db_session
        self.direction = direction
        self.site_id = site_id
        self.conflict_strategy = conflict_strategy
        self.selected_ids = selected_ids
        
        self.engine = CustomerSyncEngine(self.db)

    def run(self):
        try:
            if self.direction == "pull":
                undo_id = self.engine.pull_customers_from_dolibarr(
                    conflict_strategy=self.conflict_strategy,
                    log_callback=self.log_signal.emit,
                    progress_callback=self.progress_signal.emit,
                    site_id=self.site_id,
                )
                self.finished_signal.emit(True, "Cari Çekme (Pull) işlemi başarıyla tamamlandı!", undo_id or 0)
            else:
                pushed = self.engine.push_customers_to_dolibarr(
                    conflict_strategy=self.conflict_strategy,
                    log_callback=self.log_signal.emit,
                    progress_callback=self.progress_signal.emit,
                    site_id=self.site_id,
                    selected_ids=self.selected_ids,
                )
                self.finished_signal.emit(True, f"Cari Gönderme (Push) işlemi başarıyla tamamlandı! Toplam {pushed} cari güncellendi.", 0)
        except InterruptedError as ie:
            self.finished_signal.emit(False, f"Senkronizasyon kullanıcı tarafından durduruldu: {str(ie)}", 0)
        except Exception as e:
            self.finished_signal.emit(False, f"Kritik Hata: {str(e)}", 0)


class SyncDialog(QDialog):
    """QThread tabanlı çalışan, duraklat/durdur/vazgeç kontrolleri barındıran büyük ekranlı (800x600) Sync Dialog."""
    
    sync_finished_popup = pyqtSignal(str, str) # title, message

    def __init__(self, db_session, direction="pull", selected_ids=None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.direction = direction
        self.selected_ids = selected_ids
        self.undo_point_id = None
        self.worker = None
        
        # Ebeveyn (Parent) widget referansı
        self.parent_widget = parent
        
        self.setWindowTitle(self.tr("Gelişmiş Cari Senkronizasyonu (Arka Planda)"))
        self.setMinimumSize(800, 600)
        self.init_ui()
        
        # Eğer parent üzerinde zaten aktif bir worker varsa ona bağlan!
        if self.parent_widget and self.parent_widget.active_sync_worker:
            self.attach_active_worker()

    def attach_active_worker(self):
        self.worker = self.parent_widget.active_sync_worker
        self.direction = self.parent_widget.sync_direction
        self.selected_ids = self.parent_widget.sync_selected_ids
        
        # Birikmiş log geçmişini log konsoluna yaz
        self.log_console.clear()
        for log_line in self.parent_widget.sync_logs_cache:
            self.write_log(log_line)
            
        # Son ilerleme durumunu güncelle
        val, total = self.parent_widget.sync_progress_cache
        self.update_progress(val, total)
        
        # Sinyalleri bu dialogun slotlarına bağla
        self.worker.log_signal.connect(self.write_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_sync_finished_dialog_only)
        
        # Buton durumlarını güncelle
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_undo.setEnabled(False)
        
        # Duraklatılmışsa butonu güncelle
        if self.worker.engine and self.worker.engine.is_paused:
            self.btn_pause.setText("▶️ Devam Et")
            
        self.write_log("\n🔄 Çalışan arka plan işlemine başarıyla bağlanıldı.")

    def on_sync_finished_dialog_only(self, success, message, undo_id):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setText("⏸️ Duraklat")
        if success and undo_id > 0:
            self.undo_point_id = undo_id
            self.btn_undo.setEnabled(True)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # 🎯 SİTE SEÇİMİ
        site_layout = QHBoxLayout()
        site_layout.addWidget(QLabel("<b>Hedef Sistem:</b>"))
        self.combo_site = QComboBox()
        self.combo_site.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
                font-weight: bold;
            }
        """)
        self.load_active_sites()
        site_layout.addWidget(self.combo_site)
        layout.addLayout(site_layout)

        # Yön Bilgisi Raporu
        direction_text = "Dolibarr -> Yerel Veritabanı (Cari Kartları Çek)" if self.direction == "pull" else "Yerel Veritabanı -> Dolibarr (Cari Kartları Gönder)"
        if self.direction == "push":
            cnt = len(self.selected_ids) if self.selected_ids else self.db.query(Customer).filter(Customer.remote_id.is_(None), Customer.is_deleted == False).count()
            direction_text += f" | <b>Gönderilecek Cari Kart Adedi: {cnt}</b>"
            
        info_lbl = QLabel(f"<b>Yön:</b> {direction_text}")
        info_lbl.setStyleSheet("color: #1e293b; font-size: 13px;")
        layout.addWidget(info_lbl)

        # Çakışma Grubu
        self.conflict_group = QFrame()
        self.conflict_group.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;")
        conflict_layout = QVBoxLayout(self.conflict_group)
        conflict_layout.setSpacing(6)

        conflict_title = QLabel("<b>Çakışma / Eşleşme Yönetimi (Kayıt Zaten Varsa):</b>")
        conflict_title.setStyleSheet("color: #475569;")
        conflict_layout.addWidget(conflict_title)

        self.radio_ignore = QRadioButton("🟡 Bir Şey Yapma (Atla / Yerel Kaydı Koru)")
        self.radio_ignore.setChecked(True)
        self.radio_overwrite = QRadioButton("🟢 Değiştir (Üzerine Yaz / Uzak Veriyle Güncelle)")
        conflict_layout.addWidget(self.radio_ignore)
        conflict_layout.addWidget(self.radio_overwrite)
        
        layout.addWidget(self.conflict_group)

        # İlerleme Çubuğu (Progress Bar)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                text-align: center;
                background-color: #f1f5f9;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Log Konsolu (Büyük)
        log_lbl = QLabel("<b>Canlı Senkronizasyon Konsolu:</b>")
        log_lbl.setStyleSheet("color: #475569;")
        layout.addWidget(log_lbl)

        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #38bdf8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #334155;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.log_console)

        # Alt Kontrol Butonları
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.btn_start = QPushButton("🚀 Başlat")
        self.btn_start.setStyleSheet(self.btn_style("#3b82f6", "#2563eb"))
        self.btn_start.clicked.connect(self.start_sync)

        self.btn_pause = QPushButton("⏸️ Duraklat")
        self.btn_pause.setEnabled(False)
        self.btn_pause.setStyleSheet(self.btn_style("#f59e0b", "#d97706"))
        self.btn_pause.clicked.connect(self.toggle_pause)

        self.btn_stop = QPushButton("⏹️ Durdur / İptal")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(self.btn_style("#ef4444", "#dc2626"))
        self.btn_stop.clicked.connect(self.stop_sync)

        self.btn_undo = QPushButton("↩️ Geri Al")
        self.btn_undo.setEnabled(False)
        self.btn_undo.setStyleSheet(self.btn_style("#8b5cf6", "#7c3aed"))
        self.btn_undo.clicked.connect(self.trigger_undo)

        self.btn_close = QPushButton("Kapat (Arka Planda Çalış)")
        self.btn_close.setStyleSheet(self.btn_style("#64748b", "#475569"))
        self.btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_pause)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_undo)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def btn_style(self, bg, hover):
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:disabled {{ background-color: #cbd5e1; color: #94a3b8; }}
        """

    def load_active_sites(self):
        self.combo_site.clear()
        try:
            sites = self.db.query(Site).filter(Site.cms_type == "dolibarr", Site.is_active == True).all()
            for site in sites:
                self.combo_site.addItem(f"🔴 {site.name}", site.id)
        except Exception:
            pass

    def write_log(self, text: str):
        self.log_console.append(text)
        self.log_console.verticalScrollBar().setValue(
            self.log_console.verticalScrollBar().maximum(),
        )

    def update_progress(self, val, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(val)

    def start_sync(self):
        site_id = self.combo_site.currentData()
        if not site_id:
            self.write_log("❌ Hata: Seçilmiş aktif Dolibarr sitemiz bulunmuyor.")
            return

        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_stop.setEnabled(True)
        self.btn_undo.setEnabled(False)

        strategy = "overwrite" if self.radio_overwrite.isChecked() else "ignore"
        
        # Parent cache'lerini sıfırla ve durumu güncelle
        if self.parent_widget:
            self.parent_widget.sync_logs_cache.clear()
            self.parent_widget.sync_progress_cache = (0, 0)
            self.parent_widget.sync_direction = self.direction
            self.parent_widget.sync_selected_ids = self.selected_ids
            self.parent_widget.sync_strategy = strategy
            self.parent_widget.sync_site_id = site_id
            self.parent_widget.lbl_sync_status.setText("🔄 Arka planda Dolibarr senkronizasyonu başladı...")
            self.parent_widget.sync_status_panel.show()
        
        # Thread başlatılıyor
        self.worker = SyncWorker(
            db_session=self.db,
            direction=self.direction,
            site_id=site_id,
            conflict_strategy=strategy,
            selected_ids=self.selected_ids,
        )
        
        # Dialog slotları
        self.worker.log_signal.connect(self.write_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.on_sync_finished)
        
        # Parent slotları
        if self.parent_widget:
            self.parent_widget.active_sync_worker = self.worker
            self.worker.log_signal.connect(self.parent_widget.handle_worker_log)
            self.worker.progress_signal.connect(self.parent_widget.handle_worker_progress)
            self.worker.finished_signal.connect(self.parent_widget.handle_worker_finished)
            
        self.worker.start()

    def toggle_pause(self):
        if self.worker and self.worker.engine:
            state = not self.worker.engine.is_paused
            self.worker.engine.is_paused = state
            if state:
                self.btn_pause.setText("▶️ Devam Et")
                self.write_log("\n⏸️ Senkronizasyon işlemi geçici olarak duraklatıldı.")
            else:
                self.btn_pause.setText("⏸️ Duraklat")
                self.write_log("\n▶️ Senkronizasyon devam ettiriliyor...")

    def stop_sync(self):
        if self.worker and self.worker.engine:
            self.worker.engine.is_cancelled = True
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.write_log("\n🛑 İptal sinyali gönderildi, işlem durduruluyor...")

    def on_sync_finished(self, success, message, undo_id):
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_pause.setText("⏸️ Duraklat")
        
        if success:
            self.write_log(f"\n🎉 Başarılı: {message}")
            if undo_id > 0:
                self.undo_point_id = undo_id
                self.btn_undo.setEnabled(True)
        else:
            self.write_log(f"\n❌ Başarısız: {message}")

    def trigger_undo(self):
        if not self.undo_point_id:
            return
            
        reply = QMessageBox.question(
            self, "Onay",
            "Az önce yapılan tüm ekleme ve güncellemeleri geri alarak veritabanını eski haline getirmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.btn_undo.setEnabled(False)
            success = self.worker.engine.rollback_operation(self.undo_point_id, log_callback=self.write_log)
            if success:
                QMessageBox.information(self, "Başarılı", "Yapılan senkronizasyon işlemleri başarıyla geri alındı (Rollback)!")
                self.undo_point_id = None
            else:
                QMessageBox.critical(self, "Hata", "Geri alma işlemi sırasında bir hata oluştu.")


class MusteriYonetimiWidget(QWidget):
    """DIA stiline, sayfalama yapısına (lazy loading) ve Dolibarr pull/push senkronizasyon özelliklerine sahip Cari Yönetim paneli."""

    toast_requested = pyqtSignal(str, str) # message, type

    def __init__(self, db_session, company_id: int):
        super().__init__()
        self.db = db_session
        self.company_id = company_id
        self.hidden_columns = set()
        
        # Sayfalama Değişkenleri (Lazy Load)
        self.current_page = 1
        self.per_page = 25
        self.total_records = 0
        
        # Arka planda senkronizasyon değişkenleri (Singleton / Persistent Worker)
        self.active_sync_worker = None
        self.sync_logs_cache = []
        self.sync_progress_cache = (0, 0)
        self.sync_direction = "pull"
        self.sync_selected_ids = None
        self.sync_strategy = "ignore"
        self.sync_site_id = 1
        
        self.headers_dict = {
            0: ("ID", "id"),
            1: ("Cari Kodu", "customer_code"),
            2: ("Ticari Ünvan", "fullname"),
            3: ("Vergi Dairesi", "tax_office"),
            4: ("Vergi No / TCKN", "tax_number"),
            5: ("Telefon", "phone"),
            6: ("E-Posta", "email"),
            7: ("Adres", "address"),
            8: ("Durum", "status"),
            9: ("Mecra", "marketplace"),
            10: ("Grubu", "group_name"),
            11: ("Ara Grubu", "sub_group_1"),
            12: ("Alt Grubu", "sub_group_2"),
            13: ("Özel Kod 1", "special_code_1"),
            14: ("Özel Kod 2", "special_code_2"),
            15: ("Özel Kod 3", "special_code_3"),
        }
        
        self.init_ui()

    def init_ui(self):
        # Ana Yatay Layout (Sol Panel, Orta Tablo, Sağ Panel)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(5)

        # Sol Filtre Paneli (Edge-Triggered Overlay/Dock)
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)
        self.left_panel.pinned_changed.connect(self.on_panel_pin_changed)
        
        self.filter_frame = QFrame()
        self.filter_frame.setStyleSheet("background-color: transparent; border: none;")
        filter_lyt = QVBoxLayout(self.filter_frame)
        filter_lyt.setContentsMargins(0, 0, 0, 0)
        filter_lyt.setSpacing(8)

        # Genel Arama
        lbl_search = QLabel("Ünvan / Kod Arama:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText(self.tr("Hızlı ara..."))
        self.search_box.textChanged.connect(self.on_search_changed)
        self.search_box.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
                color: #0f172a;
            }
        """)
        filter_lyt.addWidget(lbl_search)
        filter_lyt.addWidget(self.search_box)

        combo_style = """
            QComboBox, QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
                color: #0f172a;
                font-size: 12px;
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
        """

        # Grubu Filtresi
        lbl_group = QLabel("Grubu:")
        lbl_group.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_group = QComboBox()
        self.cmb_filter_group.setObjectName("FilterGroupCombo")
        self.cmb_filter_group.addItems(["Tümü", "ALICI", "SATICI", "ALICI / SATICI", "POTANSİYEL"])
        self.cmb_filter_group.currentTextChanged.connect(self.on_search_changed)
        self.cmb_filter_group.setStyleSheet(combo_style)
        filter_lyt.addWidget(lbl_group)
        filter_lyt.addWidget(self.cmb_filter_group)

        # Durumu Filtresi
        lbl_status = QLabel("Durum:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_status = QComboBox()
        self.cmb_filter_status.setObjectName("FilterStatusCombo")
        self.cmb_filter_status.addItem("Tümü", -1)
        self.cmb_filter_status.addItem("Aktif", 1)
        self.cmb_filter_status.addItem("Pasif", 0)
        self.cmb_filter_status.currentIndexChanged.connect(self.on_search_changed)
        self.cmb_filter_status.setStyleSheet(combo_style)
        filter_lyt.addWidget(lbl_status)
        filter_lyt.addWidget(self.cmb_filter_status)

        # Mecra Filtresi
        lbl_marketplace = QLabel("Mecra:")
        lbl_marketplace.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_marketplace = QComboBox()
        self.cmb_filter_marketplace.setObjectName("FilterMarketplaceCombo")
        self.cmb_filter_marketplace.addItems(["Tümü", "LOCAL", "DOLIBARR"])
        self.cmb_filter_marketplace.currentTextChanged.connect(self.on_search_changed)
        self.cmb_filter_marketplace.setStyleSheet(combo_style)
        filter_lyt.addWidget(lbl_marketplace)
        filter_lyt.addWidget(self.cmb_filter_marketplace)

        # Özel Kod 1 Filtresi
        lbl_code1 = QLabel("Özel Kod 1:")
        lbl_code1.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.txt_filter_code1 = QLineEdit()
        self.txt_filter_code1.setObjectName("FilterCode1")
        self.txt_filter_code1.setPlaceholderText("Kod süz...")
        self.txt_filter_code1.textChanged.connect(self.on_search_changed)
        self.txt_filter_code1.setStyleSheet(combo_style)
        filter_lyt.addWidget(lbl_code1)
        filter_lyt.addWidget(self.txt_filter_code1)
        filter_lyt.addStretch()

        self.left_panel.set_content(self.filter_frame)

        # ORTA PANEL: Tablo, Sync Paneli ve Sayfalama
        self.center_container = QWidget()
        self.center_container.setObjectName("CenterContainer")
        center_layout = QVBoxLayout(self.center_container)
        center_layout.setContentsMargins(5, 0, 5, 0)
        center_layout.setSpacing(8)

        # Sync durum paneli
        self.sync_status_panel = QFrame()
        self.sync_status_panel.setObjectName("SyncStatusPanel")
        self.sync_status_panel.setStyleSheet("""
            QFrame#SyncStatusPanel {
                background-color: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 8px;
            }
        """)
        self.sync_status_panel.setFixedHeight(45)
        sync_panel_layout = QHBoxLayout(self.sync_status_panel)
        sync_panel_layout.setContentsMargins(16, 0, 16, 0)
        
        self.lbl_sync_status = QLabel("🔄 Arka planda Dolibarr senkronizasyonu devam ediyor... (%0)")
        self.lbl_sync_status.setStyleSheet("color: #1d4ed8; font-weight: bold; font-size: 12px; font-family: 'Segoe UI';")
        
        btn_show_sync_log = QPushButton("Logları Göster")
        btn_show_sync_log.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        btn_show_sync_log.clicked.connect(self.show_active_sync_dialog)
        
        sync_panel_layout.addWidget(self.lbl_sync_status)
        sync_panel_layout.addStretch()
        sync_panel_layout.addWidget(btn_show_sync_log)
        self.sync_status_panel.hide()
        center_layout.addWidget(self.sync_status_panel)

        # Dinamik Filtrelenebilir Tablo (FilterableTableView)
        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key="customers",
            enable_profile_bar=False,
            parent=self,
        )
        self.filterable_table.setObjectName("FilterableTable")
        self.table = self.filterable_table.table_view  # Geriye dönük uyumluluk için atama yapıyoruz
        
        self.customer_model = QStandardItemModel(self)
        headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
        self.customer_model.setHorizontalHeaderLabels(headers)
        self.table.setModel(self.customer_model)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setAlternatingRowColors(True)
        from PyQt6.QtWidgets import QAbstractItemView
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.horizontalHeader().setDefaultSectionSize(120)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        
        self.table.setStyleSheet("""
            QTableView {
                border: 1px solid #cbd5e1;
                background-color: white;
                gridline-color: #f1f5f9;
                border-radius: 6px;
                font-family: 'Segoe UI';
                font-size: 12px;
                color: #334155;
            }
            QTableView::item {
                padding: 6px;
            }
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
            QHeaderView::up-arrow {
                width: 10px;
                height: 10px;
                padding-right: 4px;
            }
            QHeaderView::down-arrow {
                width: 10px;
                height: 10px;
                padding-right: 4px;
            }
        """)
        self.filterable_table.filter_changed.connect(self.on_table_filter_changed)
        center_layout.addWidget(self.filterable_table, 1)

        # Sayfalama (Pagination) Barı
        self.pagination_layout = QHBoxLayout()
        self.pagination_layout.setContentsMargins(0, 4, 0, 0)
        self.pagination_layout.setSpacing(6)
        
        self.btn_first_page = QPushButton("⏮️")
        self.btn_first_page.setObjectName("BtnFirstPage")
        self.btn_first_page.setToolTip("İlk Sayfa")
        self.btn_first_page.clicked.connect(self.go_to_first_page)
        
        self.btn_prev_page = QPushButton("⬅️")
        self.btn_prev_page.setObjectName("BtnPrevPage")
        self.btn_prev_page.setToolTip("Önceki Sayfa")
        self.btn_prev_page.clicked.connect(self.go_to_prev_page)
        
        self.lbl_page_info = QLabel("Sayfa 1 / 1")
        self.lbl_page_info.setObjectName("LblPageInfo")
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #475569;")
        
        self.btn_next_page = QPushButton("➡️")
        self.btn_next_page.setObjectName("BtnNextPage")
        self.btn_next_page.setToolTip("Sonraki Sayfa")
        self.btn_next_page.clicked.connect(self.go_to_next_page)
        
        self.btn_last_page = QPushButton("⏭️")
        self.btn_last_page.setObjectName("BtnLastPage")
        self.btn_last_page.setToolTip("Son Sayfa")
        self.btn_last_page.clicked.connect(self.go_to_last_page)
        
        self.lbl_per_page = QLabel("Sayfa Başına:")
        self.lbl_per_page.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold;")

        self.combo_page_size = QComboBox()
        self.combo_page_size.setObjectName("ComboPageSize")
        self.combo_page_size.setToolTip("Sayfa başına gösterilecek kayıt sayısı")
        self.combo_page_size.addItems(["25 kayıt", "50 kayıt", "100 kayıt", "250 kayıt"])
        self.combo_page_size.setMinimumWidth(110)
        self.combo_page_size.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                padding: 3px 6px;
                color: #334155;
                font-weight: 600;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        # Varsayılan değere uygun elemanı seç
        for i in range(self.combo_page_size.count()):
            if str(self.per_page) in self.combo_page_size.itemText(i):
                self.combo_page_size.setCurrentIndex(i)
                break

        self.combo_page_size.currentTextChanged.connect(self.on_page_size_combo_changed)
        
        pg_btn_style = """
            QPushButton {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
                padding: 4px 10px;
                color: #475569;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #f1f5f9; }
        """
        for btn in [self.btn_first_page, self.btn_prev_page, self.btn_next_page, self.btn_last_page]:
            btn.setStyleSheet(pg_btn_style)
            
        self.pagination_layout.addWidget(self.btn_first_page)
        self.pagination_layout.addWidget(self.btn_prev_page)
        self.pagination_layout.addWidget(self.lbl_page_info)
        self.pagination_layout.addWidget(self.btn_next_page)
        self.pagination_layout.addWidget(self.btn_last_page)
        self.pagination_layout.addStretch()
        self.pagination_layout.addWidget(QLabel("Adet:"))
        self.pagination_layout.addWidget(self.combo_page_size)
        center_layout.addLayout(self.pagination_layout)

        # Sağ Panel: İşlem ve Kolon Yönetimi (Edge-Triggered Overlay/Dock)
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
        
        lbl_grp_data = QLabel("VERİ")
        lbl_grp_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_data.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 9px; border: none; background: transparent;")
        grp_data_lyt.addWidget(lbl_grp_data)

        btn_new = QPushButton("➕ Yeni")
        btn_new.setObjectName("BtnNewCustomer")
        btn_new.setStyleSheet(self.toolbar_btn_style())
        btn_new.clicked.connect(self.open_new_customer_dialog)
        
        btn_edit = QPushButton("✏️ Değiştir")
        btn_edit.setObjectName("BtnEditCustomer")
        btn_edit.setStyleSheet(self.toolbar_btn_style())
        btn_edit.clicked.connect(self.open_edit_customer_dialog)
        
        btn_delete = QPushButton("❌ Sil")
        btn_delete.setObjectName("BtnDeleteCustomer")
        btn_delete.setStyleSheet(self.toolbar_btn_style())
        btn_delete.clicked.connect(self.delete_customer)
        
        btn_copy = QPushButton("📋 Kopyala")
        btn_copy.setObjectName("BtnCopyCustomer")
        btn_copy.setStyleSheet(self.toolbar_btn_style())
        btn_copy.clicked.connect(self.copy_customer)
        
        btn_toggle_status = QPushButton("🔌 Durum")
        btn_toggle_status.setObjectName("BtnToggleStatus")
        btn_toggle_status.setStyleSheet(self.toolbar_btn_style())
        btn_toggle_status.clicked.connect(self.toggle_customer_status)

        btn_bulk_delete = QPushButton("🗑️ Toplu Sil")
        btn_bulk_delete.setObjectName("BtnBulkDelete")
        btn_bulk_delete.setStyleSheet(self.toolbar_btn_style())
        btn_bulk_delete.clicked.connect(self.bulk_delete_customers)

        grp_data_lyt.addWidget(btn_new)
        grp_data_lyt.addWidget(btn_edit)
        grp_data_lyt.addWidget(btn_delete)
        grp_data_lyt.addWidget(btn_copy)
        grp_data_lyt.addWidget(btn_toggle_status)
        grp_data_lyt.addWidget(btn_bulk_delete)
        toolbar_lyt.addWidget(grp_data)

        # 2. Grup: Senkronizasyon & Dışa Aktarım
        grp_sync = QFrame()
        grp_sync.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_sync_lyt = QVBoxLayout(grp_sync)
        grp_sync_lyt.setContentsMargins(4, 6, 4, 6)
        grp_sync_lyt.setSpacing(4)
        
        lbl_grp_sync = QLabel("SENK/DOSYA")
        lbl_grp_sync.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_sync.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 9px; border: none; background: transparent;")
        grp_sync_lyt.addWidget(lbl_grp_sync)

        btn_pull = QPushButton("🔄 Çek")
        btn_pull.setObjectName("BtnPull")
        btn_pull.setStyleSheet(self.toolbar_btn_style())
        btn_pull.clicked.connect(self.trigger_pull)

        btn_push = QPushButton("🚀 Gönder")
        btn_push.setObjectName("BtnPush")
        btn_push.setStyleSheet(self.toolbar_btn_style())
        btn_push.clicked.connect(self.trigger_push)
        
        btn_import = QPushButton("📥 İçe Aktar")
        btn_import.setObjectName("BtnImport")
        btn_import.setStyleSheet(self.toolbar_btn_style())
        btn_import.clicked.connect(self.open_import_dialog)
        
        btn_export = QPushButton("📤 Excel")
        btn_export.setObjectName("BtnExport")
        btn_export.setStyleSheet(self.toolbar_btn_style())
        btn_export.clicked.connect(self.export_customers)

        grp_sync_lyt.addWidget(btn_pull)
        grp_sync_lyt.addWidget(btn_push)
        grp_sync_lyt.addWidget(btn_import)
        grp_sync_lyt.addWidget(btn_export)
        toolbar_lyt.addWidget(grp_sync)



        # Kapat Butonu
        btn_close = QPushButton("🚪 Kapat")
        btn_close.setObjectName("BtnCloseTab")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                border: 1px solid #fca5a5;
                border-radius: 6px;
                padding: 4px 8px;
                font-family: 'Segoe UI';
                font-size: 11px;
                color: #991b1b;
                font-weight: bold;
                text-align: center;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #fca5a5; }
        """)
        btn_close.clicked.connect(self.close_tab)
        toolbar_lyt.addWidget(btn_close)
        
        toolbar_lyt.addStretch()
        right_scroll.setWidget(self.toolbar_frame)
        self.right_panel.set_content(right_scroll)

        # Başlangıçta panelleri ana layout'a varsayılan olarak ekleme (Overlay olarak başlayacaklar)
        main_layout.addWidget(self.center_container, 1)

        # Şirket Çalışma Moduna Göre Arayüzü Özelleştir
        self.working_mode = DataManager.get_company_mode(self.db, self.company_id)
        if self.working_mode == "direct_online":
            btn_pull.hide()
            btn_push.hide()
            btn_import.hide()

        # Panellerin açılma ve sabitlenme durumlarına göre pagination marjinlerini güncelle
        self.left_panel.opened_changed.connect(self.update_pagination_margins)
        self.left_panel.pinned_changed.connect(self.update_pagination_margins)
        self.right_panel.opened_changed.connect(self.update_pagination_margins)
        self.right_panel.pinned_changed.connect(self.update_pagination_margins)

        # Ctrl+F Kısayolu Entegrasyonu
        from PyQt6.QtGui import QKeySequence, QShortcut
        self.shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_search.activated.connect(self.trigger_quick_search)

        # Konumlandırmaları Overlay modda ilklendir
        self.left_panel.close_panel()
        self.right_panel.close_panel()
        self.refresh_customers()

    def on_panel_pin_changed(self, pinned):
        """Raptiye durumuna göre paneli normal layout'a ekler ya da çıkarır."""
        sender = self.sender()
        if not sender:
            return

        layout = self.layout()  # QHBoxLayout
        if pinned:
            # Sabitlendiyse overlay'den çıkar ve layout'a ekle
            sender.setParent(None)
            if sender == self.left_panel:
                layout.insertWidget(0, self.left_panel)
            else:
                layout.addWidget(self.right_panel)
        else:
            # Sabitlenmediyse layout'tan çıkar ve overlay yap
            layout.removeWidget(sender)
            sender.setParent(self)
            sender.update_position()
            sender.show()

    def on_table_filter_changed(self, filters):
        """Tablodaki QLineEdit'ler değiştiğinde sayfayı başa alıp listeyi tazeler."""
        self.current_page = 1
        self.refresh_customers()

    def toggle_filter_panel(self):
        self.left_panel.toggle_panel()

    def toggle_toolbar_panel(self):
        self.right_panel.toggle_panel()

    def toolbar_btn_style(self):
        return """
            QPushButton {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                font-family: 'Segoe UI';
                font-size: 11px;
                color: #334155;
                font-weight: bold;
                text-align: left;
                min-height: 28px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background-color: #cbd5e1;
            }
        """

    def open_new_customer_dialog(self):
        dlg = CustomerDialog(self.db, self.company_id, None, None, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.toast_requested.emit(self.tr("Yeni cari kart başarıyla oluşturuldu."), "success")
            self.refresh_customers()

    def open_edit_customer_dialog(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Lütfen düzenlemek istediğiniz cari kartı seçin."))
            return
            
        index = indexes[0]
        model = self.table.model()
        cust_id_val = model.index(index.row(), 0).data()
        
        item = model.item(index.row(), 0)
        remote_id = item.data(Qt.ItemDataRole.UserRole + 1) if item else None
        
        if cust_id_val is not None:
            cust_id = int(cust_id_val)
            dlg = CustomerDialog(self.db, self.company_id, cust_id, remote_id, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.toast_requested.emit(self.tr("Cari kart başarıyla güncellendi."), "success")
                self.refresh_customers()

    def copy_customer(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Lütfen kopyalamak istediğiniz cariyi seçin."))
            return
            
        index = indexes[0]
        model = self.table.model()
        cust_id_val = model.index(index.row(), 0).data()
        if cust_id_val is not None:
            cust_id = int(cust_id_val)
            source_cust = self.db.query(Customer).filter(Customer.id == cust_id).first()
            if source_cust:
                try:
                    copied_cust = Customer(
                        fullname=f"{source_cust.fullname} - Kopya",
                        customer_code=f"{source_cust.customer_code}-KOPYA" if source_cust.customer_code else "KOPYA",
                        authorized_person=source_cust.authorized_person,
                        nickname=source_cust.nickname,
                        tax_office=source_cust.tax_office,
                        tax_number=source_cust.tax_number,
                        phone=source_cust.phone,
                        phone2=source_cust.phone2,
                        phone_home=source_cust.phone_home,
                        email=source_cust.email,
                        address=source_cust.address,
                        address2=source_cust.address2,
                        city=source_cust.city,
                        district=source_cust.district,
                        country=source_cust.country,
                        postcode=source_cust.postcode,
                        status=source_cust.status,
                        group_name=source_cust.group_name,
                        sub_group_1=source_cust.sub_group_1,
                        sub_group_2=source_cust.sub_group_2,
                        special_code_1=source_cust.special_code_1,
                        special_code_2=source_cust.special_code_2,
                        special_code_3=source_cust.special_code_3,
                        marketplace="local",
                    )
                    self.db.add(copied_cust)
                    self.db.commit()
                    
                    # Open CustomerDialog to let user review and approve/edit
                    dlg = CustomerDialog(self.db, self.company_id, copied_cust.id, None, self)
                    if dlg.exec() == QDialog.DialogCode.Accepted:
                        self.toast_requested.emit(self.tr("Cari kart başarıyla kopyalandı."), "success")
                        self.refresh_customers()
                    else:
                        # User cancelled, delete the temporary copy
                        self.db.delete(copied_cust)
                        self.db.commit()
                        self.toast_requested.emit(self.tr("Kopyalama işlemi iptal edildi."), "info")
                        self.refresh_customers()
                        
                except Exception as e:
                    QMessageBox.critical(self, self.tr("Hata"), f"Kopyalama esnasında hata: {e}")

    def delete_customer(self):
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Lütfen silmek istediğiniz cari kartı seçin."))
            return
            
        index = indexes[0]
        model = self.table.model()
        
        item = model.item(index.row(), 0)
        remote_id = item.data(Qt.ItemDataRole.UserRole + 1) if item else None
        
        cust_id_val = model.index(index.row(), 0).data()
        if cust_id_val is not None:
            cust_id = int(cust_id_val)
            reply = QMessageBox.question(
                self, self.tr("Silme Onayı"),
                self.tr("Seçili cari kartı silmek istediğinize emin misiniz?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    success = DataManager.delete_customer(
                        db=self.db,
                        company_id=self.company_id,
                        customer_id=cust_id,
                        remote_id=remote_id,
                    )
                    if success:
                        self.toast_requested.emit(self.tr("Cari kart silindi."), "success")
                        self.refresh_customers()
                    else:
                        QMessageBox.critical(self, self.tr("Hata"), self.tr("Silme işlemi başarısız oldu."))
                except Exception as e:
                    QMessageBox.critical(self, self.tr("Hata"), f"Silme esnasında hata oluştu: {e}")

    def bulk_delete_customers(self):
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Lütfen silmek istediğiniz cari kartları seçin."))
            return
            
        reply = QMessageBox.question(
            self, self.tr("Toplu Silme Onayı"),
            self.tr(f"Seçilen {len(selected_rows)} adet cari kartı silmek istediğinize emin misiniz?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from src.core.models import ChangeLog, Site
                active_dolibarr = self.db.query(Site).filter(Site.cms_type == "dolibarr", Site.is_active == True).first()
                
                for cust_id in selected_rows:
                    cust = self.db.query(Customer).filter(Customer.id == cust_id).first()
                    if cust:
                        cust.is_deleted = True
                        cust.updated_at = datetime.utcnow()
                        if active_dolibarr:
                            changelog = ChangeLog(
                                entity_type="customer",
                                entity_id=cust.id,
                                action="delete",
                                status="PENDING_PUSH",
                            )
                            self.db.add(changelog)
                self.db.commit()
                self.toast_requested.emit(self.tr("Seçilen cari kartlar başarıyla silindi."), "success")
                self.refresh_customers()
            except Exception as e:
                QMessageBox.critical(self, self.tr("Hata"), f"Toplu silme esnasında hata: {e}")

    def toggle_customer_status(self):
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, self.tr("Uyarı"), self.tr("Lütfen durumunu değiştirmek istediğiniz carileri seçin."))
            return
            
        try:
            from src.core.models import ChangeLog, Site
            active_dolibarr = self.db.query(Site).filter(Site.cms_type == "dolibarr", Site.is_active == True).first()
            
            for cust_id in selected_rows:
                cust = self.db.query(Customer).filter(Customer.id == cust_id).first()
                if cust:
                    cust.status = 0 if cust.status == 1 else 1
                    cust.updated_at = datetime.utcnow()
                    
                    if active_dolibarr:
                        changelog = ChangeLog(
                            entity_type="customer",
                            entity_id=cust.id,
                            action="update",
                            status="PENDING_PUSH",
                        )
                        self.db.add(changelog)
            self.db.commit()
            self.toast_requested.emit(self.tr("Seçilen carilerin durumları başarıyla değiştirildi."), "success")
            self.refresh_customers()
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), f"Durum değiştirme esnasında hata: {e}")

    def get_selected_rows(self) -> list[int]:
        indexes = self.table.selectionModel().selectedRows()
        ids = []
        model = self.table.model()
        for idx in indexes:
            val = model.index(idx.row(), 0).data()
            if val is not None:
                try:
                    ids.append(int(val))
                except ValueError:
                    pass
        return list(set(ids))

    def trigger_pull(self):
        """Platform seçimli Dolibarr'dan cari kartları çeker."""
        if self.active_sync_worker:
            self.show_active_sync_dialog()
            return
        self.sync_direction = "pull"
        self.sync_selected_ids = None
        dlg = SyncDialog(self.db, direction="pull", parent=self)
        dlg.sync_finished_popup.connect(self.show_sync_finished_popup)
        dlg.exec()
        self.refresh_customers()

    def trigger_push(self):
        """Seçilen platforma seçili veya bekleyen tüm carileri gönderir."""
        if self.active_sync_worker:
            self.show_active_sync_dialog()
            return
        self.sync_direction = "push"
        self.sync_selected_ids = self.get_selected_rows()
        dlg = SyncDialog(self.db, direction="push", selected_ids=self.sync_selected_ids, parent=self)
        dlg.sync_finished_popup.connect(self.show_sync_finished_popup)
        dlg.exec()
        self.refresh_customers()

    def show_sync_finished_popup(self, title, message):
        """Senkronizasyon arka planda veya dialog kapalıyken bittiğinde popup ile bildirim yapar."""
        QMessageBox.information(self, title, message)
        self.refresh_customers()

    def handle_worker_log(self, text):
        self.sync_logs_cache.append(text)
        clean_text = text.strip().replace("\n", " ")
        if clean_text:
            if len(clean_text) > 60:
                clean_text = clean_text[:60] + "..."
            self.lbl_sync_status.setText(f"🔄 Arka planda çalışıyor: {clean_text}")

    def handle_worker_progress(self, val, total):
        self.sync_progress_cache = (val, total)
        percent = int((val / total) * 100) if total > 0 else 0
        self.lbl_sync_status.setText(f"🔄 Arka planda Dolibarr senkronizasyonu devam ediyor... %{percent} ({val}/{total})")

    def handle_worker_finished(self, success, message, undo_id):
        self.sync_status_panel.hide()
        self.active_sync_worker = None
        
        # Cache içerisindeki başarılı, hatalı vb logları özetleyelim
        pushed_count = 0
        skipped_count = 0
        error_count = 0
        
        for log_line in self.sync_logs_cache:
            if "✅" in log_line:
                pushed_count += 1
            elif "🟡" in log_line or "ATLANDI" in log_line or "Geçildi" in log_line:
                skipped_count += 1
            elif "❌" in log_line:
                error_count += 1
                
        summary_title = "Senkronizasyon Raporu"
        summary_msg = "⏱️ <b>Durum:</b> İşlem Tamamlandı.<br><br>"
        if not success:
            summary_title = "Senkronizasyon Durduruldu / Hata"
            summary_msg = f"⚠️ <b>Durum:</b> {message}<br><br>"
            
        summary_msg += (
            f"📈 <b>Detaylı Özet:</b><br>"
            f"✅ Başarılı İşlenen: <b>{pushed_count}</b> adet<br>"
            f"🟡 Çakışan / Atlanan: <b>{skipped_count}</b> adet<br>"
            f"❌ Hatalı / Başarısız: <b>{error_count}</b> adet<br><br>"
            f"ℹ️ Yapılan tüm detaylı log kayıtlarını log konsolundan izleyebilirsiniz."
        )
        
        QMessageBox.information(self, summary_title, summary_msg)
        self.refresh_customers()
        self.sync_logs_cache.clear()
        self.sync_progress_cache = (0, 0)

    def show_active_sync_dialog(self):
        """Çalışan aktif senkronizasyon dialogunu tüm log geçmişiyle tekrar açar."""
        if self.active_sync_worker:
            dlg = SyncDialog(self.db, direction=self.sync_direction, selected_ids=self.sync_selected_ids, parent=self)
            dlg.sync_finished_popup.connect(self.show_sync_finished_popup)
            dlg.exec()

    def open_import_dialog(self):
        dlg = ExcelImportDialog(self.db, entity_type="customer", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.toast_requested.emit(self.tr("Cari aktarım işlemi başarıyla tamamlandı."), "success")
            self.refresh_customers()

    def export_customers(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Cari Listesini Kaydet"), "cariler.xlsx",
            "Excel Dosyası (*.xlsx)",
        )
        if file_path:
            try:
                customers = self.db.query(Customer).filter(Customer.is_deleted == False).all()
                export_to_excel_file(file_path, CUSTOMER_FIELDS, customers)
                self.toast_requested.emit(self.tr("Cari listesi başarıyla dışa aktarıldı."), "success")
            except Exception as e:
                QMessageBox.critical(self, self.tr("Hata"), f"Dışa aktarım hatası: {e}")

    def close_tab(self):
        self.close()

    def on_search_changed(self):
        self.current_page = 1
        self.refresh_customers()

    # Sayfalama
    def go_to_first_page(self):
        self.current_page = 1
        self.refresh_customers()

    def go_to_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_customers()

    def go_to_next_page(self):
        total_pages = max(1, math.ceil(self.total_records / self.per_page))
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_customers()

    def go_to_last_page(self):
        total_pages = max(1, math.ceil(self.total_records / self.per_page))
        self.current_page = total_pages
        self.refresh_customers()

    def on_page_size_combo_changed(self, text):
        try:
            val = int(text.split()[0])
            self.per_page = val
            self.current_page = 1
            self.refresh_customers()
        except Exception:
            pass

    def on_page_size_changed(self, text):
        try:
            self.per_page = int(text)
            self.current_page = 1
            self.refresh_customers()
        except ValueError:
            pass

    def refresh_customers(self):
        try:
            # Hem sol panel filtreleri hem de tablo altı filtreleri birleştiriyoruz
            filters = dict(self.filterable_table.filters)

            search_text = self.search_box.text().strip()
            if search_text:
                filters["fullname"] = search_text

            group_filter = self.cmb_filter_group.currentText()
            if group_filter != "Tümü":
                filters["group_name"] = group_filter

            status_filter = self.cmb_filter_status.currentData()
            if status_filter != -1:
                filters["status"] = status_filter

            marketplace_filter = self.cmb_filter_marketplace.currentText()
            if marketplace_filter != "Tümü":
                filters["marketplace"] = marketplace_filter

            code1_filter = self.txt_filter_code1.text().strip()
            if code1_filter:
                filters["special_code_1"] = code1_filter

            # Repository üzerinden sayfalanmış verileri al
            repo = SqliteCustomerRepository(self.db, self.company_id)
            customers, total_records = repo.get_page_data(
                filters=filters,
                sort_by=None,
                sort_order="asc",
                page=self.current_page,
                per_page=self.per_page,
            )

            self.total_records = total_records
            total_pages = max(1, math.ceil(self.total_records / self.per_page))

            if self.current_page > total_pages:
                self.current_page = total_pages

            self.lbl_page_info.setText(f"Sayfa {self.current_page} / {total_pages} (Toplam: {self.total_records} Kayıt)")

            self.btn_prev_page.setEnabled(self.current_page > 1)
            self.btn_first_page.setEnabled(self.current_page > 1)
            self.btn_next_page.setEnabled(self.current_page < total_pages)
            self.btn_last_page.setEnabled(self.current_page < total_pages)
            
            self.customer_model.removeRows(0, self.customer_model.rowCount())
            
            for cust in customers:
                row_items = []
                for _col_idx, (_header_name, field_name) in self.headers_dict.items():
                    val = getattr(cust, field_name, "")
                    
                    if field_name == "status":
                        status_str = "Aktif" if val == 1 else "Pasif"
                        item = QStandardItem(status_str)
                        if val == 1:
                            item.setForeground(QColor("#10B981"))
                        else:
                            item.setForeground(QColor("#EF4444"))
                    elif field_name == "marketplace":
                        item = QStandardItem(str(val).upper() if val else "LOCAL")
                        item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                        item.setForeground(QColor("#2563eb"))
                    else:
                        item = QStandardItem(str(val) if val is not None else "")
                        if field_name == "id":
                            item.setForeground(QColor("#64748b"))
                            
                    item.setEditable(False)
                    row_items.append(item)
                if row_items:
                    row_items[0].setData(cust.remote_id, Qt.ItemDataRole.UserRole + 1)
                self.customer_model.appendRow(row_items)
                
            # Tablo yüklendikten sonra filtre boyutlarını senkronize et
            self.filterable_table.sync_filter_widths()
            
        except Exception as e:
            QMessageBox.critical(self, self.tr("Hata"), f"Müşteriler listelenemedi: {e}")

    def trigger_quick_search(self):
        if not self.left_panel.is_open:
            self.left_panel.open_panel()
        self.search_box.setFocus()
        self.search_box.selectAll()

    def show_table_context_menu(self, pos):
        """Tablodaki satırlara sağ tıklandığında düzenleme ve yönetim kısayol menüsünü açar."""
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        
        # Seçili satır var mı kontrol et
        indexes = self.table.selectionModel().selectedRows()
        has_selection = len(indexes) > 0

        action_new = QAction("➕ Yeni Cari Kart Ekle", self)
        action_new.triggered.connect(self.open_new_customer_dialog)
        menu.addAction(action_new)

        if has_selection:
            action_edit = QAction("✏️ Düzenle / Değiştir", self)
            action_edit.triggered.connect(self.open_edit_customer_dialog)
            menu.addAction(action_edit)

            action_copy = QAction("📋 Kopyala", self)
            action_copy.triggered.connect(self.copy_customer)
            menu.addAction(action_copy)

            action_status = QAction("🔌 Durum Değiştir", self)
            action_status.triggered.connect(self.toggle_customer_status)
            menu.addAction(action_status)

            menu.addSeparator()

            action_delete = QAction("❌ Sil", self)
            action_delete.triggered.connect(self.delete_customer)
            menu.addAction(action_delete)

        action_search = QAction("🔍 Hızlı Ara (Ctrl+F)", self)
        action_search.triggered.connect(self.trigger_quick_search)
        menu.addSeparator()
        menu.addAction(action_search)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def update_pagination_margins(self):
        """Yan panellerin (Overlay moddayken) pagination barını kapatmasını marjin vererek engeller."""
        left_margin = 0
        right_margin = 0
        
        # Sol panel açık ve overlay (sabitlenmemiş) ise sol marjini aç
        if self.left_panel.is_open and not self.left_panel.is_pinned:
            left_margin = self.left_panel.panel_width
            
        # Sağ panel açık ve overlay (sabitlenmemiş) ise sağ marjini aç
        if self.right_panel.is_open and not self.right_panel.is_pinned:
            right_margin = self.right_panel.panel_width
            
        self.pagination_layout.setContentsMargins(left_margin, 4, right_margin, 0)




