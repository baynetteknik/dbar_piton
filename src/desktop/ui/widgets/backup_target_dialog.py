"""
TOYA ERP - BackupTargetDialog

Yedeğin gönderileceği dış hedef: klasör/NAS, FTP/FTPS, Google Drive veya S3. Gizli alanlar (parola, gizli anahtar,
istemci gizli anahtarı) `values()` içinde ayrı sözlükte döner; iş kaydına DEĞİL Windows Kimlik Bilgisi
Yöneticisi'ne yazılır. Düzenlerken boş bırakılan gizli alanlar mevcut değeri korur.
"""

from __future__ import annotations

import uuid
from typing import Any

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.backup import remote_providers as rp
from src.desktop.services.backup.providers import ProviderError
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.widgets.backup_runner import TaskThread

TYPES = [("local", "📁 Klasör / Harici disk / NAS"), ("ftp", "🌐 FTP / FTPS"), ("gdrive", "☁ Google Drive"), ("s3", "🪣 S3 (AWS / uyumlu)")]
_PUBLIC_FIELDS = {"local": ("path",), "ftp": ("host", "port", "user", "remote_dir", "tls", "verify_cert"),
                  "gdrive": ("auth_mode", "client_id", "full_access", "folder", "folder_id", "folder_path"),
                  "s3": ("bucket", "region", "endpoint", "prefix", "access_key")}
_SECRET_FIELDS = {"ftp": ("password",), "gdrive": ("client_secret", "refresh_token", "sa_json"), "s3": ("secret_key",), "local": ()}


class BackupTargetDialog(QDialog):
    def __init__(self, target: dict[str, Any] | None = None, existing_secret: dict[str, Any] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.target = dict(target or {})
        self.target.setdefault("id", uuid.uuid4().hex[:8])
        self._old_secret = dict(existing_secret or {})
        self._new_secret: dict[str, Any] = {}
        self._thread: TaskThread | None = None
        self.setWindowTitle("Yedek Hedefi")
        self.setMinimumWidth(500)
        apply_light_dialog_style(self)
        self._build()
        self._load()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        top = QFormLayout()
        combo_style = """
            QComboBox {
                combobox-popup: 0;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 6px;
                background-color: white;
                color: #0f172a;
                font-size: 11px;
            }
            QComboBox QAbstractItemView {
                outline: 0;
                padding: 0px;
                border: 1px solid #cbd5e1;
                background-color: #ffffff;
                color: #0f172a;
            }
            QComboBox QAbstractItemView::item {
                padding: 3px 6px;
                min-height: 20px;
            }
        """
        self.cmb = QComboBox()
        self.cmb.setStyleSheet(combo_style)
        for k, label in TYPES:
            self.cmb.addItem(label, k)
        self.txt_label = QLineEdit()
        self.txt_label.setPlaceholderText("Görünen ad (örn. Ofis NAS)")
        top.addRow("Tür", self.cmb)
        top.addRow("Ad", self.txt_label)
        root.addLayout(top)
        self.fields: dict[str, QLineEdit | QSpinBox | QCheckBox] = {}
        self._rows: dict[str, list[QWidget]] = {}
        form = QFormLayout()
        root.addLayout(form)

        def add(key: str, label: str, kinds: tuple[str, ...], widget=None, secret=False, ph=""):
            w = widget or QLineEdit()
            if isinstance(w, QLineEdit):
                if secret:
                    w.setEchoMode(QLineEdit.EchoMode.Password)
                w.setPlaceholderText(ph)
            lab = QLabel(label)
            form.addRow(lab, w)
            self.fields[key] = w
            for k in kinds:
                self._rows.setdefault(k, []).extend([lab, w])

        add("path", "Klasör", ("local",), ph=r"D:\Yedek  veya  \\NAS\yedek")
        add("host", "Sunucu", ("ftp",), ph="ftp.firma.com")
        port = QSpinBox()
        port.setRange(1, 65535)
        port.setValue(21)
        add("port", "Port", ("ftp",), port)
        add("user", "Kullanıcı", ("ftp",))
        add("password", "Parola", ("ftp",), secret=True, ph="(değiştirmek için yazın)")
        add("remote_dir", "Uzak klasör", ("ftp",), ph="yedekler/toya")
        tls = QCheckBox("Şifreli bağlantı (FTPS)")
        add("tls", "", ("ftp",), tls)
        vc = QCheckBox("Sunucu sertifikasını doğrula")
        vc.setChecked(True)
        add("verify_cert", "", ("ftp",), vc)
        am = QComboBox()
        am.setStyleSheet(combo_style)
        am.addItem("Google hesabımla (OAuth)", "oauth")
        am.addItem("Servis hesabı (JSON anahtarı)", "service_account")
        add("auth_mode", "Kimlik doğrulama", ("gdrive",), am)
        add("client_id", "İstemci kimliği", ("gdrive",), ph="…apps.googleusercontent.com")
        add("client_secret", "İstemci gizli anahtarı", ("gdrive",), secret=True, ph="(değiştirmek için yazın)")
        fa = QCheckBox("Mevcut Drive klasörlerine göz at (tam Drive erişimi)")
        add("full_access", "", ("gdrive",), fa)
        add("folder_path", "Hedef klasör", ("gdrive",), ph="Henüz seçilmedi — klasör seçilmezse 'TOYA Yedek' açılır")
        self.fields["folder_path"].setReadOnly(True)
        add("folder", "Klasör adı (yedek)", ("gdrive",), ph="TOYA Yedek")
        self.fields["folder_id"] = QLineEdit()             # seçilen klasör kimliği (görünmez)
        add("bucket", "Bucket", ("s3",), ph="firma-yedek")
        add("region", "Bölge", ("s3",), ph="eu-central-1")
        add("endpoint", "Uç nokta (isteğe bağlı)", ("s3",), ph="https://minio.firma.com:9000  (AWS için boş)")
        add("prefix", "Klasör öneki", ("s3",), ph="toya")
        add("access_key", "Erişim anahtarı", ("s3",))
        add("secret_key", "Gizli anahtar", ("s3",), secret=True, ph="(değiştirmek için yazın)")

        self.btn_google = QPushButton("🔵 Google ile Bağlan")
        self.btn_google.clicked.connect(self._connect_google)
        self.btn_json = QPushButton("📥 Google JSON İçe Aktar…")
        self.btn_json.setToolTip("Google Cloud Console'dan indirdiğiniz OAuth istemci JSON'u ya da servis hesabı JSON'u (otomatik tanınır)")
        self.btn_json.clicked.connect(self._import_json)
        self.btn_sa = QPushButton("🔑 Servis Hesabı JSON Seç…")
        self.btn_sa.clicked.connect(self._pick_sa_json)
        self.btn_folder = QPushButton("📂 Drive Klasörü Seç…")
        self.btn_folder.clicked.connect(self._pick_folder)
        self.btn_folder_clear = QPushButton("✖")
        self.btn_folder_clear.setToolTip("Klasör seçimini temizle")
        self.btn_folder_clear.setMaximumWidth(34)
        self.btn_folder_clear.clicked.connect(self._clear_folder)
        self.lbl_google = QLabel()
        gl = QHBoxLayout()
        gl.addWidget(self.btn_json)
        gl.addWidget(self.btn_google)
        gl.addWidget(self.btn_sa)
        gl.addWidget(self.btn_folder)
        gl.addWidget(self.btn_folder_clear)
        gl.addWidget(self.lbl_google, 1)
        self.google_box = QWidget()
        self.google_box.setLayout(gl)
        gl.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self.google_box)
        self.lbl_help = QLabel()
        self.lbl_help.setWordWrap(True)
        self.lbl_help.setStyleSheet("color:#64748b; font-size:11px;")
        root.addWidget(self.lbl_help)
        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)
        root.addWidget(self.lbl_status)
        row = QHBoxLayout()
        b_test = QPushButton("🔌 Bağlantıyı Test Et")
        b_test.clicked.connect(self._test)
        b_ok, b_cancel = QPushButton("💾 Kaydet"), QPushButton("Vazgeç")
        b_ok.clicked.connect(self._accept)
        b_cancel.clicked.connect(self.reject)
        row.addWidget(b_test)
        row.addStretch()
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        root.addLayout(row)
        self.cmb.currentIndexChanged.connect(self._sync)
        self.fields["auth_mode"].currentIndexChanged.connect(self._sync_gdrive)

    def kind(self) -> str:
        return self.cmb.currentData()

    def _sync(self) -> None:
        k = self.kind()
        for kind, widgets in self._rows.items():
            for w in widgets:
                w.setVisible(kind == k)
        self.google_box.setVisible(k == "gdrive")
        self._sync_gdrive()
        self.lbl_help.setText({
            "local": "Harici disk veya ağ paylaşımı (UNC). Disk takılı değilse yükleme başarısız sayılır ve yeniden denenir.",
            "ftp": "FTP/FTPS sunucusuna yüklenir. Parola yalnızca Windows Kimlik Bilgisi Yöneticisi'nde saklanır.",
            "gdrive": "OAuth: Google Cloud Console'da 'Masaüstü uygulaması' istemcisi oluşturup kimlik/gizli anahtarı girin, 'Google ile "
                      "Bağlan'a basın. Varsayılan izin yalnızca TOYA'nın oluşturduğu dosyalarla sınırlıdır; Drive'daki mevcut "
                      "klasörleri seçmek için 'tam Drive erişimi'ni işaretleyip bağlanın. Servis hesabı paylaşılan sürücülerde "
                      "(Workspace) kullanılır; hedef klasörü servis hesabıyla paylaşın.",
            "s3": "AWS S3 veya S3 uyumlu servis (MinIO, Wasabi, Backblaze B2…). Uyumlu servis için uç noktayı yazın.",
        }[k])

    def _sync_gdrive(self) -> None:
        """OAuth / servis hesabı seçimine göre ilgili alanları gösterir."""
        oauth = self.fields["auth_mode"].currentData() != "service_account"
        gd = self.kind() == "gdrive"
        for key in ("client_id", "client_secret", "full_access"):
            idx = self._rows["gdrive"].index(self.fields[key])
            for w in (self._rows["gdrive"][idx - 1], self._rows["gdrive"][idx]):
                w.setVisible(gd and oauth)
        self.btn_google.setVisible(gd and oauth)
        self.btn_sa.setVisible(gd and not oauth)
        has_sa = bool(self._new_secret.get("sa_json") or self._old_secret.get("sa_json"))
        has_rt = bool(self._new_secret.get("refresh_token") or self._old_secret.get("refresh_token"))
        self.lbl_google.setText(("✔ Servis hesabı anahtarı yüklü" if has_sa else "Servis hesabı anahtarı yüklenmedi") if not oauth
                                else ("✔ Google hesabı bağlı" if has_rt else "Henüz bağlı değil"))

    def _load(self) -> None:
        t = self.target
        idx = self.cmb.findData(t.get("type", "local"))
        self.cmb.setCurrentIndex(max(0, idx))
        self.txt_label.setText(t.get("label", ""))
        for k, w in self.fields.items():
            v = t.get(k)
            if v is None or k in _SECRET_FIELDS.get(t.get("type", ""), ()):
                continue
            if isinstance(w, QLineEdit):
                w.setText(str(v))
            elif isinstance(w, QSpinBox):
                w.setValue(int(v))
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(v))
            elif isinstance(w, QComboBox):
                w.setCurrentIndex(max(0, w.findData(v)))
        self._sync()

    def values(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """(gizli olmayan ayarlar, gizli bilgiler). Boş gizli alan mevcut değeri korur."""
        k = self.kind()
        cfg: dict[str, Any] = {"id": self.target["id"], "type": k, "label": self.txt_label.text().strip()}
        for key in _PUBLIC_FIELDS[k]:
            w = self.fields[key]
            cfg[key] = (w.text().strip() if isinstance(w, QLineEdit) else w.currentData() if isinstance(w, QComboBox)
                        else w.value() if isinstance(w, QSpinBox) else w.isChecked())
        secret = {**self._old_secret, **self._new_secret}
        for key in _SECRET_FIELDS[k]:
            w = self.fields.get(key)
            if isinstance(w, QLineEdit) and w.text().strip():
                secret[key] = w.text().strip()
        secret = {s: v for s, v in secret.items() if s in _SECRET_FIELDS[k]}
        if not cfg["label"]:
            cfg["label"] = dict(TYPES)[k].split(" ", 1)[1]
        return cfg, secret

    # ------------------------------------------------------------------ eylemler
    def _status(self, text: str, ok: bool | None = None) -> None:
        self.lbl_status.setStyleSheet(f"color:{'#334155' if ok is None else ('#15803d' if ok else '#b91c1c')};")
        self.lbl_status.setText(text)

    def build_provider(self):
        cfg, secret = self.values()
        return rp.build_provider(cfg, secret)

    def _test(self) -> None:
        try:
            prov = self.build_provider()
        except ProviderError as exc:
            self._status(str(exc), False)
            return
        self._status("Bağlantı deneniyor…")
        self._thread = TaskThread(prov.test, self)
        self._thread.done.connect(lambda r: self._status(r[1], r[0]) if isinstance(r, tuple) else self._status(f"Hata: {r.__class__.__name__}", False))
        self._thread.start()

    def _connect_google(self) -> None:
        cid = self.fields["client_id"].text().strip()
        cs = self.fields["client_secret"].text().strip() or self._old_secret.get("client_secret", "")
        if not cid or not cs:
            self._status("Önce istemci kimliği ve gizli anahtarı girin.", False)
            return
        self._status("Tarayıcı açılıyor; Google hesabınızla izin verin…")
        self.btn_google.setEnabled(False)
        full = self.fields["full_access"].isChecked()
        self._thread = TaskThread(lambda: rp.authorize_google_interactive(cid, cs, full_access=full), self)

        def done(r):
            self.btn_google.setEnabled(True)
            if isinstance(r, dict):
                self._new_secret.update({"refresh_token": r["refresh_token"], "client_secret": cs})
                self._status("Google hesabı bağlandı." + (" (tam Drive erişimi)" if full else ""), True)
                self._sync()
            else:
                self._status(str(r) if isinstance(r, ProviderError) else "Google bağlantısı kurulamadı.", False)

        self._thread.done.connect(done)
        self._thread.start()

    # ---- Google Drive: servis hesabı ve klasör gezgini ---------------------------------------------
    def _pick_sa_json(self) -> None:
        import json
        path, _ = QFileDialog.getOpenFileName(self, "Servis Hesabı JSON Anahtarı", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
            data = json.loads(raw)
            if not data.get("client_email") or not data.get("private_key"):
                raise ValueError
        except (OSError, ValueError):
            self._status("Geçerli bir servis hesabı JSON anahtarı değil (client_email / private_key yok).", False)
            return
        self._new_secret["sa_json"] = raw
        self._status(f"Servis hesabı anahtarı yüklendi: {data['client_email']}", True)
        self._sync_gdrive()

    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Google JSON Dosyası", "", "JSON (*.json)")
        if path:
            self.import_google_json(path)

    def import_google_json(self, path: str) -> bool:
        """İndirilen Google JSON'unu tanır: OAuth istemci dosyası (`installed` / `web`) → istemci kimliği + gizli anahtar alanları;
        servis hesabı anahtarı (`type: service_account`) → servis hesabı kipi. Başarılıysa True."""
        import json
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError
        except (OSError, ValueError):
            self._status("Dosya geçerli bir JSON değil.", False)
            return False
        if data.get("type") == "service_account" or (data.get("client_email") and data.get("private_key")):
            if not data.get("client_email") or not data.get("private_key"):
                self._status("Servis hesabı JSON'unda client_email / private_key yok.", False)
                return False
            self.fields["auth_mode"].setCurrentIndex(self.fields["auth_mode"].findData("service_account"))
            self._new_secret["sa_json"] = raw
            self._status(f"Servis hesabı anahtarı içe aktarıldı: {data['client_email']}", True)
            self._sync_gdrive()
            return True
        blok = data.get("installed") or data.get("web")
        if isinstance(blok, dict) and blok.get("client_id") and blok.get("client_secret"):
            self.fields["auth_mode"].setCurrentIndex(self.fields["auth_mode"].findData("oauth"))
            self.fields["client_id"].setText(blok["client_id"])
            self.fields["client_secret"].setText(blok["client_secret"])
            self._status("OAuth istemci bilgileri içe aktarıldı; şimdi 'Google ile Bağlan'a basın."
                         + (" (Uyarı: 'web' türü istemci; 'Masaüstü uygulaması' türü önerilir.)" if "web" in data else ""), True)
            self._sync_gdrive()
            return True
        self._status("Tanınmayan JSON: OAuth istemci dosyası (installed/web) ya da servis hesabı anahtarı bekleniyor.", False)
        return False

    def _pick_folder(self) -> None:
        """Drive klasörlerini Gezgin gibi gezip hedef klasörü seçtirir (kimlik + görünen yol kaydedilir)."""
        from src.desktop.ui.widgets.gdrive_folder_dialog import GoogleDriveFolderDialog
        try:
            prov = self.build_provider()
        except ProviderError as exc:
            self._status(str(exc), False)
            return
        sa = self.fields["auth_mode"].currentData() == "service_account"
        if not sa and not (self._new_secret.get("refresh_token") or self._old_secret.get("refresh_token")):
            self._status("Klasör seçmek için önce 'Google ile Bağlan'a basın.", False)
            return
        if sa and not (self._new_secret.get("sa_json") or self._old_secret.get("sa_json")):
            self._status("Klasör seçmek için önce servis hesabı JSON anahtarını yükleyin.", False)
            return
        dlg = GoogleDriveFolderDialog(prov, parent=self)
        if dlg.exec() and dlg.secilen:
            self.fields["folder_id"].setText(dlg.secilen["id"])
            self.fields["folder_path"].setText(dlg.secilen["path"])
            self.fields["folder"].setText(dlg.secilen["name"])
            self._status(f"Hedef klasör: {dlg.secilen['path']}", True)

    def _clear_folder(self) -> None:
        self.fields["folder_id"].clear()
        self.fields["folder_path"].clear()
        self._status("Klasör seçimi temizlendi; yedekler 'TOYA Yedek' klasörüne yazılır.")

    def _accept(self) -> None:
        cfg, secret = self.values()
        k = cfg["type"]
        sa = k == "gdrive" and cfg.get("auth_mode") == "service_account"
        need = {"local": ["path"], "ftp": ["host", "user"], "gdrive": [] if sa else ["client_id"], "s3": ["bucket", "access_key"]}[k]
        miss = [n for n in need if not str(cfg.get(n, "")).strip()]
        if miss:
            QMessageBox.warning(self, "Yedek Hedefi", f"Zorunlu alan boş: {', '.join(miss)}")
            return
        if k == "gdrive" and not sa and not secret.get("refresh_token"):
            QMessageBox.warning(self, "Yedek Hedefi", "Google hesabı bağlı değil. 'Google ile Bağlan'a basın.")
            return
        if sa and not secret.get("sa_json"):
            QMessageBox.warning(self, "Yedek Hedefi", "Servis hesabı JSON anahtarı yüklenmedi.")
            return
        if k == "ftp" and not secret.get("password"):
            QMessageBox.warning(self, "Yedek Hedefi", "FTP parolası girilmeli.")
            return
        if k == "s3" and not secret.get("secret_key"):
            QMessageBox.warning(self, "Yedek Hedefi", "S3 gizli anahtarı girilmeli.")
            return
        self.accept()
