"""
TOYA ERP - PortalSettingsWidget

Online teklif portalının (cPanel) adresi ve API anahtarı. `portal.*` anahtarlarını
okur/yazar; `portal_sync_service` bu anahtarları kullanır.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.connectors import wolvox_connector as wolvox
from src.desktop.services import portal_secret_store
from src.desktop.services import portal_sync_service, settings_store


class PortalSettingsWidget(QWidget):
    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self._build_ui()
        self.load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("🌐 Online Teklif Portalı")
        title.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        root.addWidget(title)

        info = QLabel(
            "Tekliflerin müşteriye online link ile gönderilip kabul / ret / karşı teklif "
            "takibinin yapılacağı portal. Adres, portalın kurulu olduğu cPanel klasörüdür "
            "(örn. https://firmaniz.com/portal).",
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748b; font-size:11px;")
        root.addWidget(info)

        form = QFormLayout()
        form.setSpacing(6)
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("https://firmaniz.com/portal")
        self.txt_key = QLineEdit()
        self.txt_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_key.setPlaceholderText("Portaldaki config.local.php içindeki agent_api_key")
        form.addRow("Portal adresi", self.txt_url)
        form.addRow("API anahtarı", self.txt_key)
        root.addLayout(form)

        row = QHBoxLayout()
        self.btn_test = QPushButton("🔌 Bağlantıyı Test Et")
        self.btn_test.clicked.connect(self._on_test)
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setStyleSheet(
            "QPushButton{background:#2563eb; color:white; border:none; border-radius:6px;"
            " padding:6px 16px; font-weight:700;}"
            "QPushButton:hover{background:#1d4ed8;}",
        )
        self.btn_save.clicked.connect(self.save)
        row.addWidget(self.btn_test)
        row.addStretch()
        row.addWidget(self.btn_save)
        root.addLayout(row)

        # ---- Wolvox (salt okunur kaynak) ----
        wt = QLabel("📚 Wolvox 9 Bağlantısı (salt okunur)")
        wt.setStyleSheet("font-size:13px; font-weight:800; color:#1e3a8a; margin-top:10px;")
        root.addWidget(wt)
        winfo = QLabel(
            "Wolvox'un Firebird veritabanından cari bakiyeleri ve teklifleri okuyup portala aktarır. "
            "Wolvox veritabanına hiçbir zaman yazılmaz.",
        )
        winfo.setWordWrap(True)
        winfo.setStyleSheet("color:#64748b; font-size:11px;")
        root.addWidget(winfo)
        wform = QFormLayout()
        wform.setSpacing(6)
        self.txt_wdb = QLineEdit()
        self.txt_wdb.setPlaceholderText(r"C:\AKINSOFT\Wolvox9\Database_FB\WOLVOX.FDB")
        self.txt_whost = QLineEdit()
        self.txt_wport = QLineEdit()
        self.txt_wuser = QLineEdit()
        self.txt_wpass = QLineEdit()
        self.txt_wpass.setEchoMode(QLineEdit.EchoMode.Password)
        wform.addRow("Veritabanı yolu", self.txt_wdb)
        wform.addRow("Sunucu", self.txt_whost)
        wform.addRow("Port", self.txt_wport)
        wform.addRow("Kullanıcı", self.txt_wuser)
        wform.addRow("Parola", self.txt_wpass)
        root.addLayout(wform)
        wrow = QHBoxLayout()
        self.btn_wtest = QPushButton("🔌 Wolvox'u Test Et")
        self.btn_wtest.clicked.connect(self._on_wolvox_test)
        self.btn_wsync = QPushButton("⬆️ Wolvox → Portala Aktar")
        self.btn_wsync.setStyleSheet(
            "QPushButton{background:#0f766e; color:white; border:none; border-radius:6px;"
            " padding:6px 16px; font-weight:700;}"
            "QPushButton:hover{background:#115e59;}",
        )
        self.btn_wsync.clicked.connect(self._on_wolvox_sync)
        wrow.addWidget(self.btn_wtest)
        wrow.addStretch()
        wrow.addWidget(self.btn_wsync)
        root.addLayout(wrow)
        root.addStretch()

    def load(self) -> None:
        g = settings_store.get_setting
        self.txt_wdb.setText(g(self.db, wolvox.KEY_DATABASE, "") or "")
        self.txt_whost.setText(g(self.db, wolvox.KEY_HOST, "127.0.0.1") or "127.0.0.1")
        self.txt_wport.setText(g(self.db, wolvox.KEY_PORT, "3050") or "3050")
        self.txt_wuser.setText(g(self.db, wolvox.KEY_USER, "SYSDBA") or "SYSDBA")
        self.txt_wpass.setText(g(self.db, wolvox.KEY_PASSWORD, "") or "")
        self._load_portal()

    def _save_wolvox(self) -> bool:
        port = self.txt_wport.text().strip() or "3050"
        if not port.isdigit():
            QMessageBox.warning(self, "Wolvox", "Port sayı olmalıdır.")
            return False
        for key, w in ((wolvox.KEY_DATABASE, self.txt_wdb), (wolvox.KEY_HOST, self.txt_whost),
                       (wolvox.KEY_USER, self.txt_wuser), (wolvox.KEY_PASSWORD, self.txt_wpass)):
            settings_store.set_setting(self.db, key, w.text().strip(), commit=False)
        settings_store.set_setting(self.db, wolvox.KEY_PORT, port, commit=True)
        return True

    def _connector(self):
        if not self.db or not self._save_wolvox():
            return None
        try:
            return wolvox.WolvoxConnector.from_settings(self.db)
        except wolvox.WolvoxError as exc:
            QMessageBox.warning(self, "Wolvox", str(exc))
            return None

    def _on_wolvox_test(self) -> None:
        c = self._connector()
        if c is None:
            return
        try:
            QMessageBox.information(self, "Wolvox", c.test_connection())
        except wolvox.WolvoxError as exc:
            QMessageBox.warning(self, "Wolvox", str(exc))

    def _on_wolvox_sync(self) -> None:
        c = self._connector()
        if c is None:
            return
        try:
            r = portal_sync_service.sync_connector(self.db, c)
        except wolvox.WolvoxError as exc:
            QMessageBox.warning(self, "Wolvox", str(exc))
            return
        (QMessageBox.information if r.success else QMessageBox.warning)(self, "Wolvox → Portal", r.message)
        self.toast_requested.emit(r.message, "success" if r.success else "error")

    def _load_portal(self) -> None:
        self.txt_url.setText(settings_store.get_setting(self.db, portal_sync_service.KEY_BASE_URL, "") or "")
        self.txt_key.setText(portal_secret_store.al(self.db, portal_sync_service.KEY_API_KEY))

    def save(self) -> bool:
        if not self.db:
            QMessageBox.warning(self, "Portal", "Veritabanı bağlantısı yok.")
            return False
        url = self.txt_url.text().strip().rstrip("/")
        if url and not url.lower().startswith(("http://", "https://")):
            QMessageBox.warning(self, "Portal", "Adres http:// veya https:// ile başlamalıdır.")
            return False
        try:
            portal_secret_store.yaz(self.db, portal_sync_service.KEY_API_KEY, self.txt_key.text())
        except portal_secret_store.SecretStoreError as e:
            QMessageBox.warning(self, "Portal", f"API anahtarı güvenli kimlik deposuna yazılamadı; kaydedilmedi. {e}")
            return False
        settings_store.set_setting(self.db, portal_sync_service.KEY_BASE_URL, url, commit=True)
        self.toast_requested.emit("Portal ayarları kaydedildi", "success")
        return True

    def _on_test(self) -> None:
        if not self.save():
            return
        r = portal_sync_service.test_connection(self.db)
        (QMessageBox.information if r.success else QMessageBox.warning)(self, "Portal Bağlantısı", r.message)
