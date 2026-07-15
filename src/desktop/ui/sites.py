from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QPushButton, QListWidget, QListWidgetItem, QMessageBox,
    QFormLayout, QGroupBox, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from src.core.models import Site
from src.core.security.keyring_store import save_api_key, get_api_key, delete_api_key
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.adapters.woocommerce.woocommerce_client import WooCommerceClient
from src.adapters.woocommerce.woocommerce_adapter import WooCommerceAdapter


class SitesWidget(QWidget):
    """CMS sitelerinin yönetildiği ve keyring API bağlantılarının test edildiği ekran."""

    sites_updated = pyqtSignal()

    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
        self.selected_site_id = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # Başlık
        title_label = QLabel("Site Yönetimi")
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2c3e50;")
        main_layout.addWidget(title_label)

        # Splitter ile sol liste, sağ detay/form yerleşimi
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Sol taraf: Liste
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        list_title = QLabel("Kayıtlı Siteler")
        list_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        left_layout.addWidget(list_title)

        self.site_list = QListWidget()
        self.site_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #dcdde1;
                border-radius: 6px;
                background-color: white;
            }
        """)
        self.site_list.itemSelectionChanged.connect(self.on_site_selected)
        left_layout.addWidget(self.site_list)

        # Yeni Ekle butonu list altına
        self.add_new_btn = QPushButton("Yeni Site Ekle")
        self.add_new_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        self.add_new_btn.clicked.connect(self.clear_form)
        left_layout.addWidget(self.add_new_btn)

        # Sağ taraf: Form
        right_widget = QGroupBox("Site Detayları / Giriş Formu")
        right_widget.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        
        form_layout = QFormLayout(right_widget)
        form_layout.setContentsMargins(15, 20, 15, 15)
        form_layout.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: Dolibarr ERP")
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://dolibarr.siteniz.com")

        self.cms_input = QComboBox()
        self.cms_input.addItems(["dolibarr", "woocommerce"])
        self.cms_input.currentTextChanged.connect(self.on_cms_changed)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("API Key veya Consumer Key:Consumer Secret")

        self.active_check = QCheckBox("Site Aktif")
        self.active_check.setChecked(True)

        form_layout.addRow("Site Adı:", self.name_input)
        form_layout.addRow("Site URL:", self.url_input)
        form_layout.addRow("CMS Tipi:", self.cms_input)
        form_layout.addRow("API Anahtarı:", self.api_key_input)
        form_layout.addRow("", self.active_check)

        # Bilgi Notu Label
        self.info_lbl = QLabel("")
        self.info_lbl.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        form_layout.addRow("", self.info_lbl)
        self.on_cms_changed(self.cms_input.currentText())

        # Form Butonları
        btn_layout = QHBoxLayout()
        
        self.test_btn = QPushButton("Bağlantıyı Test Et")
        self.test_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        self.test_btn.clicked.connect(self.test_connection)

        self.save_btn = QPushButton("Kaydet")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.save_btn.clicked.connect(self.save_site)

        self.delete_btn = QPushButton("Sil")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.delete_btn.clicked.connect(self.delete_site)
        self.delete_btn.setEnabled(False)

        btn_layout.addWidget(self.test_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.save_btn)
        form_layout.addRow("", btn_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 500])
        main_layout.addWidget(splitter)

        self.load_sites()

    def on_cms_changed(self, text):
        if text == "woocommerce":
            self.info_lbl.setText("Not: WooCommerce için ConsumerKey:ConsumerSecret giriniz (örn: ck_xx:cs_xx)")
        else:
            self.info_lbl.setText("Not: Dolibarr için panelden aldığınız REST API anahtarını giriniz.")

    def load_sites(self):
        self.site_list.clear()
        try:
            sites = self.db.query(Site).all()
            for site in sites:
                item = QListWidgetItem(f"{site.name} ({site.cms_type.upper()})")
                item.setData(Qt.ItemDataRole.UserRole, site.id)
                self.site_list.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Siteler listelenirken hata oluştu: {str(e)}")

    def on_site_selected(self):
        selected_items = self.site_list.selectedItems()
        if not selected_items:
            self.clear_form()
            return

        site_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
        self.selected_site_id = site_id
        
        try:
            site = self.db.query(Site).filter(Site.id == site_id).first()
            if site:
                self.name_input.setText(site.name)
                self.url_input.setText(site.url)
                self.cms_input.setCurrentText(site.cms_type)
                self.active_check.setChecked(site.is_active)
                
                # API Key'i keyring'den çek
                api_key = get_api_key(site.api_key_account)
                self.api_key_input.setText(api_key or "")
                
                self.delete_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Site detayları yüklenemedi: {str(e)}")

    def clear_form(self):
        self.selected_site_id = None
        self.name_input.clear()
        self.url_input.clear()
        self.api_key_input.clear()
        self.active_check.setChecked(True)
        self.delete_btn.setEnabled(False)
        self.site_list.clearSelection()

    def test_connection(self):
        url = self.url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        cms_type = self.cms_input.currentText()

        if not url or not api_key:
            QMessageBox.warning(self, "Uyarı", "Bağlantı testi için URL ve API anahtarı girilmelidir.")
            return

        self.test_btn.setText("Test Ediliyor...")
        self.test_btn.setEnabled(False)
        
        # Test İşlemi
        try:
            success = False
            if cms_type == "dolibarr":
                client = DolibarrClient(base_url=url, api_key=api_key)
                adapter = DolibarrAdapter(site_id=0, client=client)
                success = adapter.test_connection()
            elif cms_type == "woocommerce":
                if ":" not in api_key:
                    raise ValueError("API anahtarı ck:cs biçiminde olmalıdır.")
                ck, cs = api_key.split(":", 1)
                client = WooCommerceClient(base_url=url, consumer_key=ck, consumer_secret=cs)
                adapter = WooCommerceAdapter(site_id=0, client=client)
                success = adapter.test_connection()
                
            if success:
                QMessageBox.information(self, "Başarılı", "Bağlantı testi başarıyla tamamlandı!")
            else:
                QMessageBox.warning(self, "Başarısız", "Uzak sisteme bağlanılamadı. Bilgileri kontrol edin.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı sırasında hata oluştu:\n{str(e)}")
        finally:
            self.test_btn.setText("Bağlantıyı Test Et")
            self.test_btn.setEnabled(True)

    def save_site(self):
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()
        cms_type = self.cms_input.currentText()
        api_key = self.api_key_input.text().strip()
        is_active = self.active_check.isChecked()

        if not name or not url or not api_key:
            QMessageBox.warning(self, "Uyarı", "Lütfen tüm alanları doldurun.")
            return

        try:
            account_name = f"site_{name.lower().replace(' ', '_')}"
            
            if self.selected_site_id:
                # Güncelleme
                site = self.db.query(Site).filter(Site.id == self.selected_site_id).first()
                if site:
                    site.name = name
                    site.url = url
                    site.cms_type = cms_type
                    site.is_active = is_active
                    # Keyring'deki hesabı güncelle
                    save_api_key(site.api_key_account, api_key)
            else:
                # Yeni Ekleme
                site = Site(
                    name=name,
                    url=url,
                    cms_type=cms_type,
                    api_key_account=account_name,
                    is_active=is_active
                )
                self.db.add(site)
                save_api_key(account_name, api_key)

            self.db.commit()
            QMessageBox.information(self, "Başarılı", "Site ayarları kaydedildi.")
            self.load_sites()
            self.clear_form()
            self.sites_updated.emit()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Kaydetme hatası: {str(e)}")

    def delete_site(self):
        if not self.selected_site_id:
            return

        reply = QMessageBox.question(
            self, "Onay", "Seçili siteyi silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                site = self.db.query(Site).filter(Site.id == self.selected_site_id).first()
                if site:
                    # Keyring'den API key'i sil
                    delete_api_key(site.api_key_account)
                    self.db.delete(site)
                    self.db.commit()
                    QMessageBox.information(self, "Başarılı", "Site veritabanından ve keyring'den silindi.")
                    self.load_sites()
                    self.clear_form()
                    self.sites_updated.emit()
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Hata", f"Silme hatası: {str(e)}")
