import logging
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.security.keyring_store import get_api_key, save_api_key

logger = logging.getLogger(__name__)


class LoginWindow(QMainWindow):
    """modern login ekranı.

    Uygulama başlatıldığında sunucu, kullanıcı adı ve şifre bilgilerini
    alarak CMS bağlantısını kurar.

    Özellikler:
    - Sunucu URL girişi
    - Kullanıcı adı / Şifre
    - CMS tipi seçimi (Dolibarr / WooCommerce)
    - Bağlantı testi
    - Son giriş bilgilerini hatırlama
    - Demo modu

    Sinyaller:
        login_success: Başarılı giriş sonrası (site_config dict)
        login_cancelled: Kullanıcı iptal etti
    """

    login_success = pyqtSignal(dict)
    login_cancelled = pyqtSignal()

    def __init__(self, db_session=None, parent=None):
        super().__init__(parent)
        self.db = db_session
        self.setWindowTitle("Toya ERP - Giriş")
        self.setFixedSize(500, 800)
        self.setStyleSheet("background-color: #0f172a;")
        self._result: dict[str, Any] | None = None
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(0)

        # Logo / Baslik
        # Logo görseli hazır olunca buraya QPixmap gelecek; şimdilik metin.
        logo_lbl = QLabel("Toya ERP")
        logo_lbl.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        logo_lbl.setStyleSheet("color: #ffffff;")
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_lbl)

        subtitle = QLabel("Entegre Yönetim Platformu")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setStyleSheet("color: #64748b; margin-bottom: 30px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Form alani
        form_widget = QWidget()
        form_widget.setStyleSheet("""
            QWidget {
                background-color: #1e293b;
                border-radius: 16px;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        form_widget.setGraphicsEffect(shadow)

        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(30, 30, 30, 30)
        form_layout.setSpacing(16)

        # Bağlantı Türü
        cms_label = QLabel("Bağlantı Türü")
        cms_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        form_layout.addWidget(cms_label)
        self.cms_combo = QComboBox()
        self.cms_combo.addItems(["Toya ERP (Yerel)", "Dolibarr ERP", "WooCommerce"])
        self.cms_combo.setFixedHeight(42)
        self.cms_combo.setStyleSheet(self._input_style())
        self.cms_combo.currentIndexChanged.connect(self._on_conn_type_changed)
        form_layout.addWidget(self.cms_combo)

        # --- Yerel (Toya ERP) alanı: Veri Türü + Veritabanı ---
        self.local_box = QWidget()
        local_lyt = QVBoxLayout(self.local_box)
        local_lyt.setContentsMargins(0, 4, 0, 0)
        local_lyt.setSpacing(6)

        dt_label = QLabel("Veri Türü")
        dt_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        local_lyt.addWidget(dt_label)
        self.datatype_combo = QComboBox()
        self.datatype_combo.addItems(["SQLite (Yerel Dosya)"])
        self.datatype_combo.setFixedHeight(42)
        self.datatype_combo.setStyleSheet(self._input_style())
        local_lyt.addWidget(self.datatype_combo)

        db_label = QLabel("Veritabanı")
        db_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        local_lyt.addWidget(db_label)
        self.database_combo = QComboBox()
        self.database_combo.setEditable(True)
        self.database_combo.setFixedHeight(42)
        self.database_combo.setStyleSheet(self._input_style())
        self._populate_databases()
        local_lyt.addWidget(self.database_combo)
        form_layout.addWidget(self.local_box)

        # --- Uzak (CMS) alanı: Sunucu Adresi ---
        self.remote_box = QWidget()
        remote_lyt = QVBoxLayout(self.remote_box)
        remote_lyt.setContentsMargins(0, 4, 0, 0)
        remote_lyt.setSpacing(6)
        url_label = QLabel("Sunucu Adresi")
        url_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        remote_lyt.addWidget(url_label)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://orneginiz.com")
        self.url_input.setFixedHeight(42)
        self.url_input.setStyleSheet(self._input_style())
        remote_lyt.addWidget(self.url_input)
        form_layout.addWidget(self.remote_box)

        # Kullanıcı Adı (mevcut kullanıcılar açılır listede)
        user_label = QLabel("Kullanıcı Adı")
        user_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        form_layout.addWidget(user_label)
        self.username_input = QComboBox()
        self.username_input.setEditable(True)
        self.username_input.setFixedHeight(42)
        self.username_input.setStyleSheet(self._input_style())
        self.username_input.lineEdit().setPlaceholderText("Kullanıcı adınızı girin veya seçin")
        self._populate_users()
        form_layout.addWidget(self.username_input)

        self._on_conn_type_changed(0)  # başlangıçta yerel görünümü

        # Sifre
        pass_label = QLabel("Sifre")
        pass_label.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        form_layout.addWidget(pass_label)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Sifrenizi girin")
        self.password_input.setFixedHeight(42)
        self.password_input.setStyleSheet(self._input_style())
        self.password_input.returnPressed.connect(self._on_connect)
        form_layout.addWidget(self.password_input)

        # Hatirla
        remember_layout = QHBoxLayout()
        self.remember_cb = QCheckBox("Giris bilgilerini hatirla")
        self.remember_cb.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.remember_cb.setChecked(True)
        remember_layout.addWidget(self.remember_cb)
        remember_layout.addStretch()
        form_layout.addLayout(remember_layout)

        layout.addWidget(form_widget)
        layout.addSpacing(20)

        # Butonlar
        self.connect_btn = QPushButton("Baglan")
        self.connect_btn.setFixedHeight(48)
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #f97316;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ea580c;
            }
            QPushButton:pressed {
                background-color: #c2410c;
            }
            QPushButton:disabled {
                background-color: #475569;
                color: #94a3b8;
            }
        """)
        self.connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(self.connect_btn)

        layout.addSpacing(8)

        self.demo_btn = QPushButton("Demo Baglan")
        self.demo_btn.setFixedHeight(40)
        self.demo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.demo_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #f97316;
                border: 2px solid #f97316;
                border-radius: 12px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(249, 115, 22, 0.1);
            }
        """)
        self.demo_btn.clicked.connect(self._on_demo)
        layout.addWidget(self.demo_btn)

        layout.addSpacing(16)

        # Durum
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #64748b; font-size: 11px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # Alt bilgi
        layout.addStretch()
        footer = QLabel("Toya ERP · v0.1.0")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #475569; font-size: 10px;")
        layout.addWidget(footer)

        # Onceki giris bilgilerini yukle
        self._load_saved_credentials()

    def _input_style(self) -> str:
        return """
            QLineEdit, QComboBox {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 10px;
                padding: 0 14px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #f97316;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #94a3b8;
                margin-right: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                selection-background-color: #f97316;
                outline: none;
                padding: 2px 0px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 26px;
                padding: 4px 10px;
                background-color: #1e293b;
                color: #e2e8f0;
                border-radius: 0px;
            }
            QComboBox QAbstractItemView::item:hover,
            QComboBox QAbstractItemView::item:selected {
                background-color: #f97316;
                color: #ffffff;
            }
        """

    # ------------------------------------------------------------------
    def _is_local(self) -> bool:
        return self.cms_combo.currentIndex() == 0

    def _on_conn_type_changed(self, _idx: int):
        local = self._is_local()
        self.local_box.setVisible(local)
        self.remote_box.setVisible(not local)

    def _populate_users(self):
        """Kullanıcı kutusunu DB'deki aktif kullanıcılarla doldurur."""
        self.username_input.clear()
        try:
            from src.core.models import User
            names = [u.username for u in self.db.query(User).filter(
                User.is_active == True, User.is_deleted == False,
            ).order_by(User.username).all()]
            self.username_input.addItems(names)
        except Exception:  # noqa: BLE001
            pass
        self.username_input.setCurrentText("")

    def _populate_databases(self):
        """data/ ve proje kökündeki .db / .sqlite dosyalarını listeler."""
        import glob
        import os

        from src.core.config import settings
        self.database_combo.clear()
        found: list[str] = []
        try:
            cur = getattr(settings.db, "db_path", "")
            if cur and cur != ":memory:":
                found.append(os.path.abspath(cur))
        except Exception:  # noqa: BLE001
            pass
        for pat in ("*.db", "*.sqlite", "*.sqlite3", "data/*.db", "data/*.sqlite"):
            for p in glob.glob(pat):
                ap = os.path.abspath(p)
                if ap not in found:
                    found.append(ap)
        self.database_combo.addItems(found or ["toya_erp.db"])

    def _on_connect(self):
        url = self.url_input.text().strip()
        username = self.username_input.currentText().strip()
        password = self.password_input.text()

        # Uzak modda URL'ye otomatik https:// ekle
        if not self._is_local() and url and not url.startswith(("http://", "https://")):
            url = f"https://{url}"
            self.url_input.setText(url)

        if not username:
            self._show_status("Kullanıcı adı boş olamaz", "error")
            return
        if not password:
            self._show_status("Sifre bos olamaz", "error")
            return

        self._show_status("Giris yapiliyor...", "info")
        self.connect_btn.setEnabled(False)

        if self.db:
            import hashlib

            from src.core.models import User
            
            try:
                salt = "multi_cms_salt_key"
                password_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
                
                user = self.db.query(User).filter(
                    User.username == username,
                    User.password_hash == password_hash,
                    User.is_active == True,
                ).first()
                
                if not user:
                    self._show_status("Kullanici adi veya sifre hatali!", "error")
                    self.connect_btn.setEnabled(True)
                    return
                
                self._show_status("Giris basarili!", "success")

                # Rol tabanlı yetkileri DB'den yükle ve giriş yapan kullanıcıyı ata
                try:
                    from src.desktop.managers.permission_manager import PermissionManager
                    pm = PermissionManager()
                    pm.load_from_db(self.db)
                    pm.set_current_user(user)
                except Exception:  # noqa: BLE001
                    logger.exception("Yetki yöneticisi başlatılamadı")

                if self._is_local():
                    cms_type = "local"
                    db_path = self.database_combo.currentText().strip()
                    site_name = f"Toya ERP (Yerel) · {db_path}"
                else:
                    cms_type = "dolibarr" if self.cms_combo.currentIndex() == 1 else "woocommerce"
                    db_path = None
                    site_name = f"{self.cms_combo.currentText()} - {url}"
                self._result = {
                    "site_name": site_name,
                    "url": url,
                    "username": username,
                    "password": password,
                    "cms_type": cms_type,
                    "data_type": "sqlite" if self._is_local() else "api",
                    "db_path": db_path,
                    "user_role": user.role,
                    "full_name": user.full_name,
                }

                if self.remember_cb.isChecked():
                    self._save_credentials(url, username, cms_type, password)
                else:
                    self._clear_saved_credentials()
                
                self.login_success.emit(self._result)
                self.close()
                
            except Exception as e:
                logger.error("login_failed error=%s", str(e))
                self._show_status(f"Giris hatasi: {e}", "error")
                self.connect_btn.setEnabled(True)
        else:
            self._show_status("Veritabani baglantisi yok!", "error")
            self.connect_btn.setEnabled(True)

    def _fetch_dolibarr_token(self, url: str, username: str, password: str) -> str | None:
        """Dolibarr API'sine istek atarak token degerini otomatik çeker."""
        import requests

        api_root = url.rstrip("/")
        if not api_root.endswith("/api/index.php"):
            api_root = f"{api_root}/api/index.php"

        login_url = f"{api_root}/login"
        params = {"login": username, "password": password}
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            response = requests.get(
                login_url, params=params, headers=headers, timeout=10,
            )
            if response.status_code == 200:
                data = response.json()
                if "success" in data and "token" in data["success"]:
                    return data["success"]["token"]
        except Exception as e:
            logger.error("dolibarr_token_fetch_failed error=%s", str(e))

        return None

    def _on_demo(self):
        self._result = {
            "site_name": "Demo Modu",
            "url": "",
            "username": "demo",
            "password": "",
            "cms_type": "dolibarr",
            "demo": True,
        }
        self.login_success.emit(self._result)
        self.close()

    def _show_status(self, msg: str, level: str = "info"):
        colors = {"info": "#64748b", "success": "#10b981", "error": "#ef4444"}
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {colors.get(level, '#64748b')}; font-size: 11px;")
        self.connect_btn.setEnabled(True)

    def _save_credentials(self, url: str, username: str, cms_type: str, password: str):
        save_api_key("login_last_url", url)
        save_api_key("login_last_username", username)
        save_api_key("login_last_cms_type", cms_type)
        save_api_key("login_last_password", password)

    def _clear_saved_credentials(self):
        from src.core.security.keyring_store import delete_api_key
        delete_api_key("login_last_url")
        delete_api_key("login_last_username")
        delete_api_key("login_last_cms_type")
        delete_api_key("login_last_password")

    def _load_saved_credentials(self):
        url = get_api_key("login_last_url")
        username = get_api_key("login_last_username")
        cms_type = get_api_key("login_last_cms_type")
        password = get_api_key("login_last_password")

        if url:
            self.url_input.setText(url)
        if username:
            self.username_input.setCurrentText(username)
        if password:
            self.password_input.setText(password)
        if cms_type == "woocommerce":
            self.cms_combo.setCurrentIndex(2)
        elif cms_type == "dolibarr":
            self.cms_combo.setCurrentIndex(1)
        else:
            self.cms_combo.setCurrentIndex(0)  # Toya ERP (Yerel)

    def get_result(self) -> dict[str, Any] | None:
        return self._result
