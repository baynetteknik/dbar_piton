import json
import os
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QCheckBox, QPushButton, QListWidget, QListWidgetItem, QMessageBox,
    QSplitter, QFrame, QDialog, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect

from src.core.models import Site
from src.core.security.keyring_store import save_api_key, get_api_key, delete_api_key
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.adapters.woocommerce.woocommerce_client import WooCommerceClient
from src.adapters.woocommerce.woocommerce_adapter import WooCommerceAdapter


def clean_and_build_api_url(raw_url: str, cms_type: str) -> str:
    """Girilen ham URL'yi ayıklar ve CMS tipine göre doğru API adresini otomatik oluşturur."""
    raw_url = str(raw_url).strip()
    if not raw_url:
        return ""
        
    # Protokol yoksa ekle
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        raw_url = "https://" + raw_url
        
    try:
        parsed = urlparse(raw_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.rstrip("/")
        
        if cms_type == "dolibarr":
            # Dolibarr API her zaman api/index.php ile bitmelidir
            if "api/index.php" in path:
                idx = path.find("api/index.php")
                clean_path = path[:idx] + "api/index.php"
            elif "/api" in path:
                idx = path.find("/api")
                clean_path = path[:idx] + "/api/index.php"
            else:
                clean_path = path + "/api/index.php"
                
            return f"{base_domain}/{clean_path.lstrip('/')}"
        else:
            # WooCommerce WooCommerceAdapter için ana dizin gereklidir
            if "/wp-json" in path:
                idx = path.find("/wp-json")
                clean_path = path[:idx]
            else:
                clean_path = path
            return f"{base_domain}/{clean_path.lstrip('/')}".rstrip("/")
    except Exception:
        return raw_url


class TokenFetchDialog(QDialog):
    """Dolibarr kullanıcı adı ve şifresi alarak arka planda API Jetonu (token) alan dialog penceresi."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dolibarr Giriş Bilgileri")
        self.setMinimumWidth(320)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        info = QLabel("Dolibarr kullanıcı adı ve şifrenizi girerek API anahtarını sistemden otomatik çekebilirsiniz:")
        info.setWordWrap(True)
        info.setStyleSheet("color: #475569; font-size: 12px; line-height: 16px;")
        layout.addWidget(info)
        
        form = QFormLayout()
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Kullanıcı Adı / Login")
        
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_input.setPlaceholderText("Şifre / Password")
        
        input_style = """
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: white;
            }
        """
        self.user_input.setStyleSheet(input_style)
        self.pass_input.setStyleSheet(input_style)
        
        form.addRow("Kullanıcı Adı:", self.user_input)
        form.addRow("Şifre:", self.pass_input)
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Jetonu Al")
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.btn_ok.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #475569;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)
        
    def get_credentials(self) -> tuple[str, str]:
        return self.user_input.text().strip(), self.pass_input.text().strip()


class SitesWidget(QWidget):
    """CMS sitelerinin yönetildiği, keyring API bağlantılarının test edildiği ve Dolibarr API dökümantasyon rehberinin bulunduğu modern ekran."""

    sites_updated = pyqtSignal()

    def __init__(self, db_session):
        super().__init__()
        self.db = db_session
        self.selected_site_id = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Başlık
        title_label = QLabel("🔗 Entegre CMS & Pazaryeri Bağlantıları")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1e293b;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(title_label)

        # Splitter ile sol liste, sağ detay/form yerleşimi
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #cbd5e1;
                width: 2px;
            }
        """)
        
        # ==========================================
        # SOL TARAF: LİSTE
        # ==========================================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(10)
        
        # Yeni Ekle butonu Sol Tarafta EN ÜSTE alındı
        self.add_new_btn = QPushButton("➕ Yeni Bağlantı Ekle")
        self.add_new_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.add_new_btn.clicked.connect(self.clear_form)
        left_layout.addWidget(self.add_new_btn)
        
        list_title = QLabel("Kayıtlı Bağlantılar")
        list_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        list_title.setStyleSheet("color: #475569;")
        left_layout.addWidget(list_title)

        self.site_list = QListWidget()
        self.site_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                background-color: white;
                font-family: 'Segoe UI';
                font-size: 13px;
                color: #334155;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #f1f5f9;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                color: #1e40af;
                font-weight: bold;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #f8fafc;
            }
        """)
        self.site_list.itemSelectionChanged.connect(self.on_site_selected)
        left_layout.addWidget(self.site_list)

        # ==========================================
        # SAĞ TARAF: FORM & YARDIMCI PANEL
        # ==========================================
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(14)

        # 🛠️ GÖREVLER EKRANI STİLİNDE ÜST TOOLBAR BUTONLARI (Formun Üstüne Alındı)
        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(8, 8, 8, 8)
        toolbar_layout.setSpacing(8)
        
        self.save_btn = QPushButton("💾 Kaydet")
        self.save_btn.setStyleSheet(self.toolbar_btn_style("#3b82f6", "#2563eb"))
        self.save_btn.clicked.connect(self.save_site)

        self.test_btn = QPushButton("🔌 Bağlantıyı Test Et")
        self.test_btn.setStyleSheet(self.toolbar_btn_style("#8b5cf6", "#7c3aed"))
        self.test_btn.clicked.connect(self.test_connection)

        self.delete_btn = QPushButton("🗑️ Sil")
        self.delete_btn.setStyleSheet(self.toolbar_btn_style("#ef4444", "#dc2626"))
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.delete_site)

        toolbar_layout.addWidget(self.save_btn)
        toolbar_layout.addWidget(self.test_btn)
        toolbar_layout.addWidget(self.delete_btn)
        toolbar_layout.addStretch()
        right_layout.addWidget(toolbar_frame)

        # Detay Form Paneli (Şık Gölgeli Kutu)
        form_frame = QFrame()
        form_frame.setObjectName("FormFrame")
        form_frame.setStyleSheet("""
            QFrame#FormFrame {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
        """)
        
        # Modern dikey hizalama
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(14)

        form_title = QLabel("Bağlantı Parametreleri")
        form_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        form_title.setStyleSheet("color: #1e293b; margin-bottom: 4px;")
        form_layout.addWidget(form_title)

        input_style = """
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 12px;
                background-color: white;
                color: #0f172a;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #3b82f6; }
        """

        # Site Adı
        name_group = QVBoxLayout()
        name_lbl = QLabel("Site Adı:")
        name_lbl.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: Dolibarr ERP veya WooCommerce Sitem")
        self.name_input.setStyleSheet(input_style)
        name_group.addWidget(name_lbl)
        name_group.addWidget(self.name_input)
        form_layout.addLayout(name_group)

        # URL (Otomatik temizleme bağlandı)
        url_group = QVBoxLayout()
        url_lbl = QLabel("Bağlantı (API) URL:")
        url_lbl.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://siteniz.com")
        self.url_input.setStyleSheet(input_style)
        self.url_input.editingFinished.connect(self.format_and_clean_url)
        self.url_input.textChanged.connect(self.update_helper_links)
        url_group.addWidget(url_lbl)
        url_group.addWidget(self.url_input)
        form_layout.addLayout(url_group)

        # CMS Tipi
        cms_group = QVBoxLayout()
        cms_lbl = QLabel("CMS / Sistem Tipi:")
        cms_lbl.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")
        self.cms_input = QComboBox()
        self.cms_input.addItems(["dolibarr", "woocommerce"])
        self.cms_input.currentTextChanged.connect(self.on_cms_changed)
        self.cms_input.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px;
                background-color: white;
                color: #0f172a;
                font-size: 13px;
            }
        """)
        cms_group.addWidget(cms_lbl)
        cms_group.addWidget(self.cms_input)
        form_layout.addLayout(cms_group)

        # API Anahtarı
        key_group = QVBoxLayout()
        key_lbl = QLabel("API Anahtarı / Şifre:")
        key_lbl.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")
        
        key_input_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("API Key veya Consumer Key:Consumer Secret")
        self.api_key_input.setStyleSheet(input_style)
        self.api_key_input.textChanged.connect(self.update_helper_links)
        
        self.btn_get_token = QPushButton("🔑 Jetonu Otomatik Al")
        self.btn_get_token.setStyleSheet("""
            QPushButton {
                background-color: #0f766e;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #0d9488; }
        """)
        self.btn_get_token.clicked.connect(self.auto_fetch_token)
        
        key_input_layout.addWidget(self.api_key_input)
        key_input_layout.addWidget(self.btn_get_token)
        key_group.addWidget(key_lbl)
        key_group.addLayout(key_input_layout)
        form_layout.addLayout(key_group)

        # Active Check & Bilgi Notu
        chk_layout = QHBoxLayout()
        self.active_check = QCheckBox("Bağlantı Aktif (Senkronizasyona İzin Ver)")
        self.active_check.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        self.active_check.setChecked(True)
        chk_layout.addWidget(self.active_check)
        chk_layout.addStretch()
        form_layout.addLayout(chk_layout)

        self.info_lbl = QLabel("")
        self.info_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        form_layout.addWidget(self.info_lbl)

        # Bağlantı Durumu Göstergesi
        status_layout = QHBoxLayout()
        status_lbl = QLabel("Bağlantı Durumu:")
        status_lbl.setStyleSheet("font-weight: bold; color: #475569; font-size: 12px;")
        self.conn_status_badge = QLabel("Bekleniyor 💤")
        self.conn_status_badge.setStyleSheet("""
            QLabel {
                background-color: #f1f5f9;
                color: #64748b;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        status_layout.addWidget(status_lbl)
        status_layout.addWidget(self.conn_status_badge)
        status_layout.addStretch()
        form_layout.addLayout(status_layout)

        right_layout.addWidget(form_frame)

        # ==========================================
        # DOLIBARR YARDIMCI PANEL & DÖKÜMANTASYON LİNKLERİ
        # ==========================================
        self.help_frame = QFrame()
        self.help_frame.setObjectName("HelpFrame")
        self.help_frame.setStyleSheet("""
            QFrame#HelpFrame {
                background-color: #f8fafc;
                border: 1px dashed #cbd5e1;
                border-radius: 8px;
            }
        """)
        help_layout = QVBoxLayout(self.help_frame)
        help_layout.setSpacing(8)
        help_layout.setContentsMargins(16, 16, 16, 16)

        help_title = QLabel("ℹ️ Dolibarr API Entegrasyon Rehberi & Canlı Linkler")
        help_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        help_title.setStyleSheet("color: #0f172a;")
        help_layout.addWidget(help_title)

        help_desc = QLabel(
            "Dolibarr REST API eklentisini aktif ettiğinizde, sisteminiz otomatik olarak Swagger API ve Token adreslerini üretir. "
            "Aşağıdaki linkler girmiş olduğunuz URL adresine göre otomatik olarak oluşturulmuştur:"
        )
        help_desc.setWordWrap(True)
        help_desc.setStyleSheet("color: #475569; font-size: 12px; line-height: 16px;")
        help_layout.addWidget(help_desc)

        # Canlı Linkler
        self.lbl_token_link = QLabel("")
        self.lbl_token_link.setOpenExternalLinks(True)
        self.lbl_token_link.setStyleSheet("font-size: 12px; color: #1e3a8a;")
        
        self.lbl_explorer_link = QLabel("")
        self.lbl_explorer_link.setOpenExternalLinks(True)
        self.lbl_explorer_link.setStyleSheet("font-size: 12px; color: #1e3a8a;")
        
        self.lbl_swagger_link = QLabel("")
        self.lbl_swagger_link.setOpenExternalLinks(True)
        self.lbl_swagger_link.setStyleSheet("font-size: 12px; color: #1e3a8a;")

        help_layout.addWidget(self.lbl_token_link)
        help_layout.addWidget(self.lbl_explorer_link)
        help_layout.addWidget(self.lbl_swagger_link)

        right_layout.addWidget(self.help_frame)
        
        # Gölgelendirme
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 2)
        form_frame.setGraphicsEffect(shadow)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_container)
        splitter.setSizes([240, 560])
        main_layout.addWidget(splitter)

        self.on_cms_changed(self.cms_input.currentText())
        self.load_sites()

    def toolbar_btn_style(self, bg, bg_hover):
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{ background-color: {bg_hover}; }}
            QPushButton:disabled {{ background-color: #cbd5e1; color: #94a3b8; }}
        """

    def on_cms_changed(self, text):
        if text == "woocommerce":
            self.info_lbl.setText("Not: WooCommerce için ConsumerKey:ConsumerSecret giriniz (örn: ck_xx:cs_xx)")
            self.help_frame.setVisible(False)
            self.btn_get_token.setVisible(False)
        else:
            self.info_lbl.setText("Not: Dolibarr için panelden aldığınız REST API anahtarını giriniz.")
            self.help_frame.setVisible(True)
            self.btn_get_token.setVisible(True)
            self.update_helper_links()

    def format_and_clean_url(self):
        """Kullanıcının girdiği URL'yi anında temizleyip standart API endpoint'ine çevirir."""
        raw_url = self.url_input.text().strip()
        if not raw_url:
            return
            
        cms_type = self.cms_input.currentText()
        clean_url = clean_and_build_api_url(raw_url, cms_type)
        
        # Sadece değiştiyse yaz ki textChanged sürekli tetiklenmesin
        if clean_url != raw_url:
            self.url_input.setText(clean_url)

    def update_helper_links(self):
        """Kullanıcının girdiği URL ve API Key bilgilerine göre canlı API döküman linklerini oluşturur."""
        if self.cms_input.currentText() != "dolibarr":
            return
            
        raw_url = self.url_input.text().strip()
        api_key = self.api_key_input.text().strip() or "YOUR_API_KEY"
        
        # API key olarak url yapıştırıldıysa linki temiz göster
        if api_key.startswith("http://") or api_key.startswith("https://"):
            api_key = "YOUR_API_KEY"

        if not raw_url:
            self.lbl_token_link.setText("🔑 <b>Jeton Alma URL:</b> Lütfen önce geçerli bir URL adresi girin.")
            self.lbl_explorer_link.setText("🌐 <b>Swagger Explorer:</b> Lütfen önce geçerli bir URL adresi girin.")
            self.lbl_swagger_link.setText("📄 <b>Swagger JSON:</b> Lütfen önce geçerli bir URL adresi girin.")
            return

        # Dolibarr API'sinin kök dizinini belirle (api/index.php yok edilerek explorer'a gidilir)
        clean_url = raw_url.rstrip("/")
        if "api/index.php" in clean_url:
            base_api_root = clean_url
        else:
            # Temizlenmiş URL üzerinden git
            base_api_root = clean_and_build_api_url(clean_url, "dolibarr")
            
        token_url = f"{base_api_root}/login?login=KULLANICI_ADI&password=SIFRE"
        explorer_url = f"{base_api_root}/explorer"
        swagger_url = f"{base_api_root}/explorer/swagger.json?DOLAPIKEY={api_key}"

        self.lbl_token_link.setText(
            f"🔑 <b>Jeton Alma URL:</b> <a href='{token_url}' style='color: #2563eb; text-decoration: none;'>{token_url}</a>"
        )
        self.lbl_explorer_link.setText(
            f"🌐 <b>Swagger Explorer:</b> <a href='{explorer_url}' style='color: #2563eb; text-decoration: none;'>{explorer_url}</a>"
        )
        self.lbl_swagger_link.setText(
            f"📄 <b>Swagger JSON:</b> <a href='{swagger_url}' style='color: #2563eb; text-decoration: none;'>{swagger_url}</a>"
        )

    def auto_fetch_token(self):
        """Dolibarr API'sine istek atarak token değerini otomatik çeker."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce Dolibarr bağlantı URL'sini girin.")
            return
            
        # URL'yi anında temizle
        clean_url = clean_and_build_api_url(url, "dolibarr")
        if clean_url != url:
            self.url_input.setText(clean_url)
            url = clean_url

        dlg = TokenFetchDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            username, password = dlg.get_credentials()
            if not username or not password:
                QMessageBox.warning(self, "Uyarı", "Kullanıcı adı ve şifre boş bırakılamaz.")
                return
                
            self.conn_status_badge.setText("🔑 Jeton Çekiliyor...")
            self.conn_status_badge.setStyleSheet("""
                QLabel { background-color: #fef3c7; color: #d97706; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
            """)
            
            try:
                login_url = f"{url}/login"
                params = {
                    "login": username,
                    "password": password
                }
                
                # WAF ve Cloudflare engellerini aşmak için gerçek bir browser User-Agent'ı ekliyoruz!
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                
                response = requests.get(login_url, params=params, headers=headers, timeout=10, allow_redirects=True)
                
                if response.status_code == 200:
                    data = response.json()
                    if "success" in data and "token" in data["success"]:
                        token = data["success"]["token"]
                        self.api_key_input.setText(token)
                        self.conn_status_badge.setText("✅ Jeton Alındı")
                        self.conn_status_badge.setStyleSheet("""
                            QLabel { background-color: #dcfce7; color: #166534; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
                        """)
                        
                        # Otomatik kaydetme sorusu
                        reply = QMessageBox.question(
                            self, "Başarılı",
                            "API Jetonu (Token) Dolibarr'dan başarıyla çekildi ve alana yerleştirildi.\n\n"
                            "Bu site/bağlantı ayarlarını otomatik olarak kaydetmek istiyor musunuz?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        if reply == QMessageBox.StandardButton.Yes:
                            self.save_site()
                            
                            # Bağlantıyı test edelim mi sorusu
                            test_reply = QMessageBox.question(
                                self, "Bağlantı Testi",
                                "Bağlantı ayarları kaydedildi. Bağlantıyı şimdi test etmek ister misiniz?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                            )
                            if test_reply == QMessageBox.StandardButton.Yes:
                                self.test_connection()
                    else:
                        raise ValueError("Sunucu başarı döndürdü fakat jeton/token bilgisi alınamadı.")
                else:
                    error_msg = f"HTTP {response.status_code}"
                    try:
                        err_data = response.json()
                        if "error" in err_data and "message" in err_data["error"]:
                            error_msg = err_data["error"]["message"]
                    except Exception:
                        try:
                            root = ET.fromstring(response.text)
                            msg_node = root.find(".//message")
                            if msg_node is not None:
                                error_msg = msg_node.text
                        except Exception:
                            pass
                            
                    raise ValueError(error_msg)
                    
            except Exception as e:
                self.conn_status_badge.setText("❌ Hata (Jeton Alınamadı)")
                self.conn_status_badge.setStyleSheet("""
                    QLabel { background-color: #fee2e2; color: #991b1b; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
                """)
                QMessageBox.critical(self, "Hata", f"Jeton alma sırasında hata oluştu:\n{str(e)}")

    def load_sites(self):
        self.site_list.clear()
        try:
            sites = self.db.query(Site).all()
            for site in sites:
                icon = "🔴" if site.cms_type == "dolibarr" else "🟣"
                status_char = " [Aktif]" if site.is_active else " [Pasif]"
                item = QListWidgetItem(f"{icon} {site.name} {status_char}")
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
                # Form yüklenirken URL'yi formatla/temizle
                self.url_input.setText(clean_and_build_api_url(site.url, site.cms_type))
                self.cms_input.setCurrentText(site.cms_type)
                self.active_check.setChecked(site.is_active)
                
                # API Key'i keyring'den çek
                api_key = get_api_key(site.api_key_account)
                self.api_key_input.setText(api_key or "")
                
                self.delete_btn.setEnabled(True)
                self.conn_status_badge.setText("Bekleniyor 💤")
                self.conn_status_badge.setStyleSheet("""
                    QLabel { background-color: #f1f5f9; color: #64748b; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
                """)
                self.update_helper_links()
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
        self.conn_status_badge.setText("Bekleniyor 💤")
        self.conn_status_badge.setStyleSheet("""
            QLabel { background-color: #f1f5f9; color: #64748b; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
        """)
        self.update_helper_links()

    def test_connection(self):
        url = self.url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        cms_type = self.cms_input.currentText()

        if not url or not api_key:
            QMessageBox.warning(self, "Uyarı", "Bağlantı testi için URL ve API anahtarı girilmelidir.")
            return

        # Test öncesi URL'yi temizle
        clean_url = clean_and_build_api_url(url, cms_type)
        if clean_url != url:
            self.url_input.setText(clean_url)
            url = clean_url

        self.test_btn.setText("⚡ Test Ediliyor...")
        self.test_btn.setEnabled(False)
        self.conn_status_badge.setText("🔄 Test Ediliyor...")
        self.conn_status_badge.setStyleSheet("""
            QLabel { background-color: #fef3c7; color: #d97706; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
        """)
        
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
                self.conn_status_badge.setText("✅ Başarılı (Aktif)")
                self.conn_status_badge.setStyleSheet("""
                    QLabel { background-color: #dcfce7; color: #166534; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
                """)
                QMessageBox.information(self, "Başarılı", "Bağlantı testi başarıyla tamamlandı!")
            else:
                self.conn_status_badge.setText("❌ Hata (Bağlantı Yok)")
                self.conn_status_badge.setStyleSheet("""
                    QLabel { background-color: #fee2e2; color: #991b1b; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
                """)
                QMessageBox.warning(self, "Başarısız", "Uzak sisteme bağlanılamadı. Bilgileri kontrol edin.")
        except Exception as e:
            self.conn_status_badge.setText("⚠️ Bağlantı Hatası")
            self.conn_status_badge.setStyleSheet("""
                QLabel { background-color: #fee2e2; color: #991b1b; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px; }
            """)
            QMessageBox.critical(self, "Hata", f"Bağlantı sırasında hata oluştu:\n{str(e)}")
        finally:
            self.test_btn.setText("🔌 Bağlantıyı Test Et")
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

        # Kaydetmeden önce URL'yi temizle
        clean_url = clean_and_build_api_url(url, cms_type)
        if clean_url != url:
            self.url_input.setText(clean_url)
            url = clean_url

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
