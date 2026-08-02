import logging
from urllib.parse import urlparse

import requests
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.woocommerce.woocommerce_adapter import WooCommerceAdapter
from src.adapters.woocommerce.woocommerce_client import WooCommerceClient
from src.core.models import Site
from src.core.security.keyring_store import delete_api_key, get_api_key, save_api_key
from src.desktop.ui.components.edge_panel import EdgeTriggeredPanel
from src.desktop.ui.components.filterable_table import FilterableTableView

logger = logging.getLogger(__name__)


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
        self.setMinimumWidth(340)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel(
            "Dolibarr kullanıcı adı ve şifrenizi girerek API anahtarını sistemden otomatik çekebilirsiniz:",
        )
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


class SiteDialog(QDialog):
    """DIA stiline uygun Firma Tanımı (Site) Ekleme / Düzenleme / İnceleme Diyaloğu."""

    def __init__(self, db_session, site_id=None, read_only=False, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.site_id = site_id
        self.read_only = read_only

        if self.site_id:
            self.setWindowTitle("Firma / Şirket Bilgilerini Düzenle" if not read_only else "Firma Detayı İncele")
        else:
            self.setWindowTitle("Yeni Firma / Şirket Ekle")

        self.setMinimumWidth(680)
        self.init_ui()

        if self.site_id:
            self.load_site_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Başlık Kartı
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        header_lyt = QHBoxLayout(header_frame)
        header_lyt.setContentsMargins(12, 10, 12, 10)

        lbl_icon = QLabel("🏢")
        lbl_icon.setStyleSheet("font-size: 24px;")
        lbl_title = QLabel(self.windowTitle())
        lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #0f172a;")

        header_lyt.addWidget(lbl_icon)
        header_lyt.addWidget(lbl_title)
        header_lyt.addStretch()
        main_layout.addWidget(header_frame)

        # Form Alanı
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 8px;")
        form_layout = QVBoxLayout(form_frame)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(12)

        input_style = """
            QLineEdit, QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px 10px;
                background-color: #f8fafc;
                color: #0f172a;
                font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #3b82f6; background-color: white; }
        """

        # Site / Firma Adı
        lbl_name = QLabel("Firma / Şirket Adı *:")
        lbl_name.setStyleSheet("font-weight: bold; color: #475569;")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Örn: BAYNET BİLİŞİM TEK. A.Ş.")
        self.name_input.setStyleSheet(input_style)
        form_layout.addWidget(lbl_name)
        form_layout.addWidget(self.name_input)

        # CMS Platform Tipi
        lbl_cms = QLabel("CMS / Entegrasyon Platformu:")
        lbl_cms.setStyleSheet("font-weight: bold; color: #475569;")
        self.cms_input = QComboBox()
        self.cms_input.addItem("Dolibarr ERP / CRM", "dolibarr")
        self.cms_input.addItem("WooCommerce e-Ticaret", "woocommerce")
        self.cms_input.setStyleSheet(input_style)
        self.cms_input.currentTextChanged.connect(self.on_cms_changed)
        form_layout.addWidget(lbl_cms)
        form_layout.addWidget(self.cms_input)

        # Çalışma Modu
        lbl_mode = QLabel("Çalışma Modu:")
        lbl_mode.setStyleSheet("font-weight: bold; color: #475569;")
        self.mode_input = QComboBox()
        self.mode_input.addItem("Yerel Ana Sunucu (Local Master - Çevrimdışı Çalışabilir)", "local_master")
        self.mode_input.addItem("Doğrudan Online (Direct Online - Canlı Senkronizasyon)", "direct_online")
        self.mode_input.setStyleSheet(input_style)
        form_layout.addWidget(lbl_mode)
        form_layout.addWidget(self.mode_input)

        # API Bağlantı URL'si
        lbl_url = QLabel("API Bağlantı Adresi (URL):")
        lbl_url.setStyleSheet("font-weight: bold; color: #475569;")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://dolibarr.example.com/api/index.php")
        self.url_input.setStyleSheet(input_style)
        self.url_input.editingFinished.connect(self.format_and_clean_url)
        form_layout.addWidget(lbl_url)
        form_layout.addWidget(self.url_input)

        # API Anahtarı / Token
        lbl_key = QLabel("API Anahtarı / Jeton (Token):")
        lbl_key.setStyleSheet("font-weight: bold; color: #475569;")
        key_layout = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Dolibarr API Key veya ck_xxx:cs_xxx")
        self.api_key_input.setStyleSheet(input_style)

        self.btn_get_token = QPushButton("🔑 Jeton Otomatik Çek")
        self.btn_get_token.setStyleSheet("""
            QPushButton {
                background-color: #0d9488;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #0f766e; }
        """)
        self.btn_get_token.clicked.connect(self.auto_fetch_token)

        key_layout.addWidget(self.api_key_input)
        key_layout.addWidget(self.btn_get_token)
        form_layout.addWidget(lbl_key)
        form_layout.addLayout(key_layout)

        # Durumu
        self.active_check = QCheckBox("Bağlantı Aktif (Senkronizasyona İzin Ver)")
        self.active_check.setStyleSheet("font-weight: bold; color: #475569;")
        self.active_check.setChecked(True)
        form_layout.addWidget(self.active_check)

        # Durum Badge & Test Butonu
        status_lyt = QHBoxLayout()
        self.conn_status_badge = QLabel("Bekleniyor 💤")
        self.conn_status_badge.setStyleSheet("background-color: #f1f5f9; color: #64748b; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
        
        self.btn_test = QPushButton("🔌 Bağlantıyı Test Et")
        self.btn_test.setStyleSheet("""
            QPushButton { background-color: #8b5cf6; color: white; border: none; border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 11px; }
            QPushButton:hover { background-color: #7c3aed; }
        """)
        self.btn_test.clicked.connect(self.test_connection)

        status_lyt.addWidget(QLabel("Bağlantı Durumu:"))
        status_lyt.addWidget(self.conn_status_badge)
        status_lyt.addStretch()
        status_lyt.addWidget(self.btn_test)
        form_layout.addLayout(status_lyt)

        main_layout.addWidget(form_frame)

        # Alt Butonlar
        btn_box = QHBoxLayout()
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setStyleSheet("""
            QPushButton { background-color: #3b82f6; color: white; border: none; border-radius: 6px; padding: 8px 18px; font-weight: bold; }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.btn_save.clicked.connect(self.save_site)

        self.btn_cancel = QPushButton("❌ İptal")
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 18px; font-weight: bold; }
            QPushButton:hover { background-color: #e2e8f0; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        if self.read_only:
            self.name_input.setReadOnly(True)
            self.url_input.setReadOnly(True)
            self.api_key_input.setReadOnly(True)
            self.cms_input.setEnabled(False)
            self.mode_input.setEnabled(False)
            self.active_check.setEnabled(False)
            self.btn_get_token.setEnabled(False)
            self.btn_save.hide()

        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        main_layout.addLayout(btn_box)

        self.on_cms_changed(self.cms_input.currentText())

    def on_cms_changed(self, text):
        cms_type = self.cms_input.currentData() or "dolibarr"
        if cms_type == "woocommerce":
            self.btn_get_token.setVisible(False)
        else:
            self.btn_get_token.setVisible(True)

    def format_and_clean_url(self):
        raw_url = self.url_input.text().strip()
        if not raw_url:
            return
        cms_type = self.cms_input.currentData() or "dolibarr"
        clean_url = clean_and_build_api_url(raw_url, cms_type)
        if clean_url != raw_url:
            self.url_input.setText(clean_url)

    def auto_fetch_token(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce Dolibarr bağlantı URL'sini girin.")
            return

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
            self.conn_status_badge.setStyleSheet("background-color: #fef3c7; color: #d97706; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px;")

            try:
                login_url = f"{url}/login"
                params = {"login": username, "password": password}
                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
                response = requests.get(login_url, params=params, headers=headers, timeout=10, allow_redirects=True)

                if response.status_code == 200:
                    data = response.json()
                    if "success" in data and "token" in data["success"]:
                        token = data["success"]["token"]
                        self.api_key_input.setText(token)
                        self.conn_status_badge.setText("✅ Jeton Alındı")
                        self.conn_status_badge.setStyleSheet("background-color: #dcfce7; color: #166534; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
                        QMessageBox.information(self, "Başarılı", "API Jetonu (Token) Dolibarr'dan başarıyla çekildi.")
                    else:
                        raise ValueError("Sunucudan jeton bilgisi alınamadı.")
                else:
                    raise ValueError(f"HTTP {response.status_code}")
            except Exception as e:
                self.conn_status_badge.setText("❌ Hata (Jeton Alınamadı)")
                self.conn_status_badge.setStyleSheet("background-color: #fee2e2; color: #991b1b; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
                QMessageBox.critical(self, "Hata", f"Jeton alma sırasında hata oluştu:\n{str(e)}")

    def test_connection(self):
        url = self.url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        cms_type = self.cms_input.currentData() or "dolibarr"

        if not url or not api_key:
            QMessageBox.warning(self, "Uyarı", "Bağlantı testi için URL ve API anahtarı girilmelidir.")
            return

        clean_url = clean_and_build_api_url(url, cms_type)
        if clean_url != url:
            self.url_input.setText(clean_url)
            url = clean_url

        self.conn_status_badge.setText("🔄 Test Ediliyor...")
        self.conn_status_badge.setStyleSheet("background-color: #fef3c7; color: #d97706; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px;")

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
                self.conn_status_badge.setStyleSheet("background-color: #dcfce7; color: #166534; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
                QMessageBox.information(self, "Başarılı", "Bağlantı testi başarıyla tamamlandı!")
            else:
                self.conn_status_badge.setText("❌ Hata (Bağlantı Yok)")
                self.conn_status_badge.setStyleSheet("background-color: #fee2e2; color: #991b1b; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
                QMessageBox.warning(self, "Başarısız", "Uzak sisteme bağlanılamadı.")
        except Exception as e:
            self.conn_status_badge.setText("⚠️ Bağlantı Hatası")
            self.conn_status_badge.setStyleSheet("background-color: #fee2e2; color: #991b1b; font-weight: bold; padding: 4px 10px; border-radius: 4px; font-size: 11px;")
            QMessageBox.critical(self, "Hata", f"Bağlantı sırasında hata oluştu:\n{str(e)}")

    def load_site_data(self):
        try:
            site = self.db.query(Site).filter(Site.id == self.site_id).first()
            if site:
                self.name_input.setText(site.name)
                self.url_input.setText(clean_and_build_api_url(site.url, site.cms_type))
                idx = self.cms_input.findData(site.cms_type)
                if idx != -1:
                    self.cms_input.setCurrentIndex(idx)
                mode_idx = self.mode_input.findData(site.working_mode)
                if mode_idx != -1:
                    self.mode_input.setCurrentIndex(mode_idx)
                self.active_check.setChecked(site.is_active)
                api_key = get_api_key(site.api_key_account)
                self.api_key_input.setText(api_key or "")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Firma detayları yüklenemedi: {e}")

    def save_site(self):
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()
        cms_type = self.cms_input.currentData() or "dolibarr"
        working_mode = self.mode_input.currentData() or "local_master"
        api_key = self.api_key_input.text().strip()
        is_active = self.active_check.isChecked()

        if working_mode == "direct_online":
            if not name or not url or not api_key:
                QMessageBox.warning(self, "Uyarı", "Doğrudan Online modu için URL ve API Anahtarı zorunludur.")
                return
        else:
            if not name:
                QMessageBox.warning(self, "Uyarı", "Lütfen Firma / Şirket Adı alanını doldurun.")
                return

        if url:
            url = clean_and_build_api_url(url, cms_type)

        try:
            account_name = f"site_{name.lower().replace(' ', '_')}"
            if self.site_id:
                site = self.db.query(Site).filter(Site.id == self.site_id).first()
                if site:
                    site.name = name
                    site.url = url
                    site.cms_type = cms_type
                    site.is_active = is_active
                    site.working_mode = working_mode
                    if api_key:
                        save_api_key(site.api_key_account, api_key)
            else:
                site = Site(
                    name=name,
                    url=url,
                    cms_type=cms_type,
                    api_key_account=account_name,
                    is_active=is_active,
                    working_mode=working_mode,
                )
                self.db.add(site)
                if api_key:
                    save_api_key(account_name, api_key)

            self.db.commit()
            QMessageBox.information(self, "Başarılı", "Firma ayarları başarıyla kaydedildi.")
            self.accept()
        except Exception as e:
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Kaydetme sırasında hata oluştu: {e}")


class SitesWidget(QWidget):
    """DIA stiline, 3-Panelli Düzen mimarisine ve gelişmiş dinamik DBGrid yapısına sahip Firma Tanımları Yönetim Paneli."""

    sites_updated = pyqtSignal()

    def __init__(self, db_session, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.profile_key = "sites"

        self.headers_dict = {
            0: ("Firma Kodu", "id"),
            1: ("Firma Adı", "name"),
            2: ("CMS Platformu", "cms_type"),
            3: ("API Adresi", "url"),
            4: ("Çalışma Modu", "working_mode"),
            5: ("Durum", "is_active"),
            6: ("API Key Hesabı", "api_key_account"),
        }

        self.init_ui()
        self.load_sites()

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
            QPushButton:hover {{
                background-color: #f1f5f9;
                border-color: #94a3b8;
            }}
            QPushButton:disabled {{
                background-color: #e2e8f0;
                color: #94a3b8;
                border-color: #cbd5e1;
            }}
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
            QPushButton:disabled {{ background-color: #cbd5e1; color: #94a3b8; }}
        """

    def init_ui(self):
        # Ana Layout (Sol Panel, Orta Tablo, Sağ Panel)
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(6)

        # ==========================================
        # 1. SOL FİLTRE PANELİ (EdgeTriggeredPanel)
        # ==========================================
        self.left_panel = EdgeTriggeredPanel(side="left", parent=self)

        filter_content = QWidget()
        filter_lyt = QVBoxLayout(filter_content)
        filter_lyt.setContentsMargins(4, 4, 4, 4)
        filter_lyt.setSpacing(10)

        lbl_filter_title = QLabel("🔍 Filtre & Arama")
        lbl_filter_title.setStyleSheet("font-weight: bold; color: #1e3a8a; font-size: 12px;")
        filter_lyt.addWidget(lbl_filter_title)

        # Hızlı Arama
        lbl_search = QLabel("Firma Adı / Kod Arama:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Hızlı arama yap...")
        self.txt_search.setStyleSheet("QLineEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background-color: white; font-size: 12px; }")
        self.txt_search.textChanged.connect(self.on_filter_changed)
        filter_lyt.addWidget(lbl_search)
        filter_lyt.addWidget(self.txt_search)

        combo_style = """
            QComboBox { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px; background-color: white; font-size: 12px; color: #0f172a; }
            QComboBox QAbstractItemView { border: 1px solid #94a3b8; background-color: #ffffff; color: #0f172a; outline: none; padding: 2px 0px; }
            QComboBox QAbstractItemView::item { min-height: 26px; padding: 4px 10px; background-color: #ffffff; color: #0f172a; border-radius: 0px; }
            QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected { background-color: #2563eb; color: #ffffff; }
        """

        # CMS Filtresi
        lbl_cms = QLabel("CMS Platformu:")
        lbl_cms.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_cms = QComboBox()
        self.cmb_filter_cms.addItems(["Tümü", "dolibarr", "woocommerce"])
        self.cmb_filter_cms.setStyleSheet(combo_style)
        self.cmb_filter_cms.currentTextChanged.connect(self.on_filter_changed)
        filter_lyt.addWidget(lbl_cms)
        filter_lyt.addWidget(self.cmb_filter_cms)

        # Çalışma Modu Filtresi
        lbl_mode = QLabel("Çalışma Modu:")
        lbl_mode.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_mode = QComboBox()
        self.cmb_filter_mode.addItems(["Tümü", "local_master", "direct_online"])
        self.cmb_filter_mode.setStyleSheet(combo_style)
        self.cmb_filter_mode.currentTextChanged.connect(self.on_filter_changed)
        filter_lyt.addWidget(lbl_mode)
        filter_lyt.addWidget(self.cmb_filter_mode)

        # Durum Filtresi
        lbl_status = QLabel("Durum:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.cmb_filter_status = QComboBox()
        self.cmb_filter_status.addItem("Tümü", -1)
        self.cmb_filter_status.addItem("Aktif", 1)
        self.cmb_filter_status.addItem("Pasif", 0)
        self.cmb_filter_status.setStyleSheet(combo_style)
        self.cmb_filter_status.currentIndexChanged.connect(self.on_filter_changed)
        filter_lyt.addWidget(lbl_status)
        filter_lyt.addWidget(self.cmb_filter_status)
        filter_lyt.addStretch()

        self.left_panel.set_content(filter_content)
        main_layout.addWidget(self.left_panel)

        # ==========================================
        # 2. ORTA PANEL (Dinamik DBGrid & DIA Aksiyon Çubuğu)
        # ==========================================
        self.center_container = QWidget()
        center_lyt = QVBoxLayout(self.center_container)
        center_lyt.setContentsMargins(4, 0, 4, 0)
        center_lyt.setSpacing(8)

        # Dinamik Filtreli Tablo (FilterableTableView)
        self.filterable_table = FilterableTableView(
            headers_dict=self.headers_dict,
            profile_key="sites",
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
        self.table.doubleClicked.connect(self.open_edit_site_dialog)

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
            QTableView::item { padding: 6px; }
            QTableView::item:selected { background-color: #eff6ff; color: #1d4ed8; font-weight: 600; }
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
        self.filterable_table.filter_changed.connect(self.on_table_filter_changed)
        center_lyt.addWidget(self.filterable_table, 1)

        # DIA Stili Alt İşlem Çubuğu (Bottom Action Bar)
        self.action_bar = QFrame()
        self.action_bar.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px;")
        action_bar_lyt = QHBoxLayout(self.action_bar)
        action_bar_lyt.setContentsMargins(8, 6, 8, 6)
        action_bar_lyt.setSpacing(8)

        self.btn_add = QPushButton("➕ Ekle")
        self.btn_add.setStyleSheet(self.dia_btn_style("#3b82f6", "#2563eb"))
        self.btn_add.clicked.connect(self.open_add_site_dialog)

        self.btn_edit = QPushButton("✏️ Değiştir")
        self.btn_edit.setStyleSheet(self.dia_btn_style("#2563eb", "#1d4ed8"))
        self.btn_edit.clicked.connect(self.open_edit_site_dialog)

        self.btn_inspect = QPushButton("🔍 İncele")
        self.btn_inspect.setStyleSheet(self.dia_btn_style("#475569", "#334155"))
        self.btn_inspect.clicked.connect(self.inspect_site_dialog)

        self.btn_delete = QPushButton("🗑️ Sil")
        self.btn_delete.setStyleSheet(self.dia_btn_style("#ef4444", "#dc2626"))
        self.btn_delete.clicked.connect(self.delete_site)

        self.btn_test = QPushButton("🔌 Test Et")
        self.btn_test.setStyleSheet(self.dia_btn_style("#8b5cf6", "#7c3aed"))
        self.btn_test.clicked.connect(self.test_selected_connection)

        # Diğer Butonu (QMenu)
        self.btn_other = QPushButton("≡ Diğer")
        self.btn_other.setStyleSheet(self.dia_btn_style("#64748b", "#475569"))
        other_menu = QMenu(self)
        other_menu.addAction("🔑 Jeton Otomatik Çek Yardımcısı", self.auto_fetch_token_selected)
        other_menu.addAction("🔄 Firma Listesini Yenile", self.load_sites)
        self.btn_other.setMenu(other_menu)

        action_bar_lyt.addWidget(self.btn_add)
        action_bar_lyt.addWidget(self.btn_edit)
        action_bar_lyt.addWidget(self.btn_inspect)
        action_bar_lyt.addWidget(self.btn_delete)
        action_bar_lyt.addWidget(self.btn_test)
        action_bar_lyt.addWidget(self.btn_other)
        action_bar_lyt.addStretch()

        self.lbl_record_count = QLabel("Toplam Kayıt: 0")
        self.lbl_record_count.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        action_bar_lyt.addWidget(self.lbl_record_count)

        center_lyt.addWidget(self.action_bar)
        main_layout.addWidget(self.center_container, 1)

        # ==========================================
        # 3. SAĞ PANEL (EdgeTriggeredPanel - İşlem Grupları)
        # ==========================================
        self.right_panel = EdgeTriggeredPanel(side="right", parent=self)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        right_content = QWidget()
        right_lyt = QVBoxLayout(right_content)
        right_lyt.setContentsMargins(4, 4, 4, 4)
        right_lyt.setSpacing(8)

        # 1. Grup: Firma İşlemleri
        grp_site = QFrame()
        grp_site.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_site_lyt = QVBoxLayout(grp_site)
        grp_site_lyt.setContentsMargins(6, 8, 6, 8)
        grp_site_lyt.setSpacing(6)

        lbl_grp_site = QLabel("FİRMA İŞLEMLERİ")
        lbl_grp_site.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_site.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_site_lyt.addWidget(lbl_grp_site)

        btn_r_add = QPushButton("➕ Yeni Firma Ekle")
        btn_r_add.setStyleSheet(self.toolbar_btn_style("#10b981", "#ffffff"))
        btn_r_add.clicked.connect(self.open_add_site_dialog)

        btn_r_edit = QPushButton("✏️ Değiştir")
        btn_r_edit.setStyleSheet(self.toolbar_btn_style())
        btn_r_edit.clicked.connect(self.open_edit_site_dialog)

        btn_r_inspect = QPushButton("🔍 İncele")
        btn_r_inspect.setStyleSheet(self.toolbar_btn_style())
        btn_r_inspect.clicked.connect(self.inspect_site_dialog)

        btn_r_delete = QPushButton("🗑️ Sil")
        btn_r_delete.setStyleSheet(self.toolbar_btn_style("#ef4444", "#ffffff"))
        btn_r_delete.clicked.connect(self.delete_site)

        grp_site_lyt.addWidget(btn_r_add)
        grp_site_lyt.addWidget(btn_r_edit)
        grp_site_lyt.addWidget(btn_r_inspect)
        grp_site_lyt.addWidget(btn_r_delete)
        right_lyt.addWidget(grp_site)

        # 2. Grup: Bağlantı & Doküman
        grp_conn = QFrame()
        grp_conn.setStyleSheet("background-color: white; border: 1px solid #cbd5e1; border-radius: 6px;")
        grp_conn_lyt = QVBoxLayout(grp_conn)
        grp_conn_lyt.setContentsMargins(6, 8, 6, 8)
        grp_conn_lyt.setSpacing(6)

        lbl_grp_conn = QLabel("BAĞLANTI & TEST")
        lbl_grp_conn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_grp_conn.setStyleSheet("font-weight: 800; color: #1e3a8a; font-size: 10px; border: none;")
        grp_conn_lyt.addWidget(lbl_grp_conn)

        btn_r_test = QPushButton("🔌 Bağlantıyı Test Et")
        btn_r_test.setStyleSheet(self.toolbar_btn_style())
        btn_r_test.clicked.connect(self.test_selected_connection)

        btn_r_token = QPushButton("🔑 Jeton Çek")
        btn_r_token.setStyleSheet(self.toolbar_btn_style())
        btn_r_token.clicked.connect(self.auto_fetch_token_selected)

        grp_conn_lyt.addWidget(btn_r_test)
        grp_conn_lyt.addWidget(btn_r_token)
        right_lyt.addWidget(grp_conn)

        # 3. Grup: Görünüm & Kolonlar
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

    def load_sites(self):
        self.table_model.removeRows(0, self.table_model.rowCount())
        try:
            query = self.db.query(Site).filter(Site.is_deleted == False)

            # Filtreleme
            search_text = self.txt_search.text().strip().lower()
            if search_text:
                query = query.filter(Site.name.ilike(f"%{search_text}%") | Site.url.ilike(f"%{search_text}%"))

            cms_filter = self.cmb_filter_cms.currentText()
            if cms_filter != "Tümü":
                query = query.filter(Site.cms_type == cms_filter)

            mode_filter = self.cmb_filter_mode.currentText()
            if mode_filter != "Tümü":
                query = query.filter(Site.working_mode == mode_filter)

            status_val = self.cmb_filter_status.currentData()
            if status_val != -1:
                query = query.filter(Site.is_active == bool(status_val))

            sites = query.all()
            for site in sites:
                row_items = [
                    QStandardItem(str(site.id)),
                    QStandardItem(site.name),
                    QStandardItem(site.cms_type),
                    QStandardItem(site.url or "-"),
                    QStandardItem("Yerel Ana Sunucu" if site.working_mode == "local_master" else "Doğrudan Online"),
                    QStandardItem("Aktif" if site.is_active else "Pasif"),
                    QStandardItem(site.api_key_account or "-"),
                ]
                row_items[0].setData(site.id, Qt.ItemDataRole.UserRole)
                self.table_model.appendRow(row_items)

            self.lbl_record_count.setText(f"Toplam Kayıt: {len(sites)}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Siteler yüklenirken hata oluştu: {e}")

    def get_selected_site_id(self) -> int | None:
        indexes = self.table.selectedIndexes()
        if not indexes:
            return None
        row = indexes[0].row()
        item = self.table_model.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def on_filter_changed(self):
        self.load_sites()

    def on_table_filter_changed(self, filter_dict):
        # FilterableTableView içi canlı filtre değişimi
        pass

    def open_add_site_dialog(self):
        dlg = SiteDialog(self.db, site_id=None, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_sites()
            self.sites_updated.emit()

    def open_edit_site_dialog(self):
        site_id = self.get_selected_site_id()
        if not site_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz firmayı seçin.")
            return
        dlg = SiteDialog(self.db, site_id=site_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_sites()
            self.sites_updated.emit()

    def inspect_site_dialog(self):
        site_id = self.get_selected_site_id()
        if not site_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen incelemek istediğiniz firmayı seçin.")
            return
        dlg = SiteDialog(self.db, site_id=site_id, read_only=True, parent=self)
        dlg.exec()

    def delete_site(self):
        site_id = self.get_selected_site_id()
        if not site_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen silmek istediğiniz firmayı seçin.")
            return

        reply = QMessageBox.question(
            self,
            "Onay",
            "Seçili firma/site tanımını veritabanından ve keyring'den silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                site = self.db.query(Site).filter(Site.id == site_id).first()
                if site:
                    delete_api_key(site.api_key_account)
                    self.db.delete(site)
                    self.db.commit()
                    QMessageBox.information(self, "Başarılı", "Firma kaydı silindi.")
                    self.load_sites()
                    self.sites_updated.emit()
            except Exception as e:
                self.db.rollback()
                QMessageBox.critical(self, "Hata", f"Silme sırasında hata oluştu: {e}")

    def test_selected_connection(self):
        site_id = self.get_selected_site_id()
        if not site_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen bağlantısını test etmek istediğiniz firmayı seçin.")
            return
        dlg = SiteDialog(self.db, site_id=site_id, parent=self)
        dlg.test_connection()

    def auto_fetch_token_selected(self):
        site_id = self.get_selected_site_id()
        if not site_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen jeton çekmek istediğiniz firmayı seçin.")
            return
        dlg = SiteDialog(self.db, site_id=site_id, parent=self)
        dlg.auto_fetch_token()

    def show_table_context_menu(self, pos):
        menu = QMenu(self)
        action_add = QAction("➕ Yeni Firma Ekle", self)
        action_add.triggered.connect(self.open_add_site_dialog)

        action_edit = QAction("✏️ Seçili Firmayı Değiştir", self)
        action_edit.triggered.connect(self.open_edit_site_dialog)

        action_inspect = QAction("🔍 Seçili Firmayı İncele", self)
        action_inspect.triggered.connect(self.inspect_site_dialog)

        action_delete = QAction("🗑️ Seçili Firmayı Sil", self)
        action_delete.triggered.connect(self.delete_site)

        action_test = QAction("🔌 Bağlantıyı Test Et", self)
        action_test.triggered.connect(self.test_selected_connection)

        action_cols = QAction("⚙️ Kolonları Yapılandır (DIA)", self)
        action_cols.triggered.connect(self.filterable_table.open_column_manager_dialog)

        menu.addAction(action_add)
        menu.addAction(action_edit)
        menu.addAction(action_inspect)
        menu.addSeparator()
        menu.addAction(action_delete)
        menu.addSeparator()
        menu.addAction(action_test)
        menu.addAction(action_cols)

        menu.exec(self.table.viewport().mapToGlobal(pos))
