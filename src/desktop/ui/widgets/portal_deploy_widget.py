"""
TOYA ERP - PortalDeployWidget

Portalın imzalı güncelleme paketini üretir ve cPanel sunucusuna FTP/FTPS ile gönderir, ardından (Online
Portal API bilgisi tanımlıysa) sunucuda OTOMATİK kurar — yönetici ayrıca portalda `update.php`'ye girip
elle "Kur"a basmak zorunda kalmaz (bkz. `portal_sync_service.trigger_apply`, sunucu tarafı
`bootstrap.php::portal_route` '/update/apply'). API bilgisi tanımlı değilse bu adım sessizce atlanır;
paket yine de sunucuda durur ve `update.php`'den elle kurulabilir — eski akış hep açık kalır.

Birden çok adlandırılmış FTP profili (ör. "Canlı Sunucu", "Test Sunucusu") standart bir dbgrid'de
listelenir; satıra çift tıklayınca (ya da "Yeni Profil Ekle" ile) ayrı bir popup diyalogda düzenlenir —
ana panelde sürekli açık bir form YOKTUR. Ekle/Düzenle/Sil/Test/Gönder/Yardım gibi işlemler panelin kendi
buton satırında DEĞİL, `GeneralSettingsScreen`'in sağdaki İŞLEMLER paneli + sağ tık menüsünden tetiklenir
(bkz. `settings.py::_panel_actions["portal_yayin"]`) — diğer tüm tanım tablolarıyla aynı, tek kaynaklı
desen (bkz. `gelistirme/00_mimari/GRID_STANDARDI.md`). Parolalar işletim sistemi kimlik deposunda tutulur
(bkz. `portal_deploy.PortalFtpProfileStore`).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services import portal_deploy, portal_package, portal_sync_service, sync_log_service
from src.desktop.ui.components.filterable_table import FilterableTableView

logger = logging.getLogger(__name__)

_GRID_COLS = ["PROFİL ADI", "SUNUCU", "KULLANICI", "UZAK DİZİN", "VARSAYILAN"]

HELP_HTML = """
<h3>Portal Yayın / Güncelleme — Nasıl Kullanılır?</h3>
<p>Bu ekran, portalın imzalı güncelleme paketini üretir ve cPanel sunucusuna FTP ile gönderir.
Paket sunucuda <code>update_inbox/</code> klasörüne bırakılır.</p>
<ol>
<li><b>FTP Profili ekleyin</b> — sağdaki İŞLEMLER'den "➕ Yeni Profil Ekle" (ya da listede bir
profile çift tıklayıp "Düzenle"). Sunucu adresi, kullanıcı, parola ve hedef klasörü girin;
klasör alanındaki "📁 Gözat…" düğmesiyle Windows Gezgini gibi sunucuda dolaşıp seçebilirsiniz.</li>
<li><b>Bağlantıyı Test Edin</b> — kaydetmeden önce sunucuya gerçekten ulaşılabildiğini doğrular,
adım adım bir günlük penceresinde gösterir.</li>
<li><b>Paket sürümünü kontrol edin</b> ve <b>"📦 Paketi Üret ve Gönder"</b>e basın. Bir ilerleme/günlük
penceresi açılır: paket üretilir, imzalanır, sunucuya yüklenir.</li>
<li><b>Otomatik kurulum</b> — Genel Ayarlar → Online Portal'da API adresi/anahtarı tanımlıysa,
gönderim bitince sunucu OTOMATİK olarak kurar; siz portala hiç girmezsiniz. Tanımlı değilse paket
yine sunucuda durur, portalda yönetici olarak <code>update.php</code> sayfasını açıp "Kur"a
basmanız yeterlidir.</li>
<li><b>Sürüm Geçmişi</b> — hangi sürümün ne zaman, hangi profile, ne sonuçla gönderildiğini
İŞLEMLER → "🗂️ Sürüm Geçmişi"nden görebilirsiniz.</li>
</ol>
<p><b>Güncelleme Anahtarı</b> — portalın kendisini ilk kurduğunuzda kurulum sihirbazı bir anahtar
üretip bir kez gösterir; o anahtarı panodan "📥 Anahtarı Yapıştır" ile buraya alın (TOYA kendi
anahtarını üretmesin, ikisi eşleşmeli). Zaten TOYA'da bir anahtar varsa "🔑 Anahtarı Kopyala" ile
sunucudaki <code>config.local.php</code>'ye elle ekleyebilirsiniz.</p>
"""


class _SimpleWorker(QThread):
    """Tek seferlik bir işlevi (bağlantı testi, klasör listeleme…) arka planda çalıştırır."""

    done = pyqtSignal(object)

    def __init__(self, fn, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D401 - QThread API
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001
            result = exc
        self.done.emit(result)


class _DeployWorker(QThread):
    progress = pyqtSignal(int, int)
    log = pyqtSignal(str)
    done = pyqtSignal(object)

    def __init__(self, fn, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D401 - QThread API
        try:
            outcome = self._fn(
                lambda s, t: self.progress.emit(s, t),
                lambda msg: self.log.emit(msg),
            )
        except Exception as exc:  # noqa: BLE001 - iş parçacığı hatası arayüze iletilir
            logger.exception("Portal gönderimi beklenmeyen hata verdi")
            outcome = (portal_deploy.DeployResult(False, f"Beklenmeyen hata: {exc}"), None, "")
        self.done.emit(outcome)


class _ProgressLogDialog(QDialog):
    """Bağlantı testi / paket gönderimi gibi aşamalı işlemler için popup: adım adım günlük + ilerleme
    çubuğu. `.show()` ile AÇILIR (`.exec()` DEĞİL) — arka plan işini bekleyen çağıran taraf (widget/test)
    bloklanmasın diye; işlem sürerken kapatılamaz (`reject` engellenir), bitince "Kapat" etkinleşir."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(520, 340)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self._running = True

        lyt = QVBoxLayout(self)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # başlangıçta belirsiz (busy); ilk byte/adımda belirli moda geçer
        lyt.addWidget(self.progress)
        self.log_list = QListWidget()
        lyt.addWidget(self.log_list, 1)
        self.btn_close = QPushButton("Kapat")
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(self.accept)
        lyt.addWidget(self.btn_close)

    def log(self, text: str, ok: bool | None = None) -> None:
        prefix = "✅ " if ok is True else ("❌ " if ok is False else "• ")
        item = QListWidgetItem(prefix + text)
        if ok is True:
            item.setForeground(Qt.GlobalColor.darkGreen)
        elif ok is False:
            item.setForeground(Qt.GlobalColor.darkRed)
        self.log_list.addItem(item)
        self.log_list.scrollToBottom()

    def set_progress(self, sent: int, total: int) -> None:
        if total:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(sent * 100 / total))

    def finish(self) -> None:
        self._running = False
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.btn_close.setEnabled(True)

    def reject(self) -> None:  # noqa: D401 - Esc/kapatma: işlem sürerken engellenir
        if not self._running:
            super().reject()


class _FtpBrowserDialog(QDialog):
    """Uzak (FTP) klasör seçici — Windows Gezgini gibi alt klasörlerde dolaşarak hedef klasör seçilir."""

    def __init__(self, profile: portal_deploy.FtpProfile, start_path: str, parent=None) -> None:
        super().__init__(parent)
        self.profile = profile
        self.path = "/" + start_path.strip("/") if start_path.strip("/") else "/"
        self._worker: _SimpleWorker | None = None
        self.setWindowTitle("Uzak Klasör Seç")
        self.setMinimumSize(420, 480)

        lyt = QVBoxLayout(self)
        path_row = QHBoxLayout()
        self.btn_up = QPushButton("⬆️ Yukarı")
        self.btn_up.clicked.connect(self._go_up)
        self.lbl_path = QLabel(self.path)
        self.lbl_path.setStyleSheet("font-weight:600;")
        path_row.addWidget(self.btn_up)
        path_row.addWidget(self.lbl_path, 1)
        lyt.addLayout(path_row)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._descend)
        lyt.addWidget(self.list, 1)

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(self.lbl_info)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(self.reject)
        self.btn_select = QPushButton("✅ Bu Klasörü Seç")
        self.btn_select.clicked.connect(self.accept)
        btns.addStretch(1)
        btns.addWidget(btn_cancel)
        btns.addWidget(self.btn_select)
        lyt.addLayout(btns)

        self._reload()

    def selected_path(self) -> str:
        return self.path

    def _go_up(self) -> None:
        if self.path == "/":
            return
        self.path = self.path.rstrip("/").rsplit("/", 1)[0] or "/"
        self._reload()

    def _descend(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        self.path = name if self.path == "/" else f"{self.path.rstrip('/')}/{name}"
        self.path = "/" + self.path.lstrip("/")
        self._reload()

    def _reload(self) -> None:
        self.lbl_path.setText(self.path)
        self.list.clear()
        self.lbl_info.setText("Yükleniyor…")
        self.btn_select.setEnabled(False)
        self._worker = _SimpleWorker(lambda p=self.profile, path=self.path: portal_deploy.list_remote_dirs(p, path), self)
        self._worker.done.connect(self._on_loaded)
        self._worker.start()

    def _on_loaded(self, result) -> None:
        self.btn_select.setEnabled(True)
        if isinstance(result, Exception):
            self.lbl_info.setText(f"⚠️ {result}")
            return
        ok, err, dirs = result
        if not ok:
            self.lbl_info.setText(f"⚠️ {err}")
            return
        self.lbl_info.setText(f"{len(dirs)} klasör" if dirs else "Alt klasör yok.")
        for name in dirs:
            item = QListWidgetItem(f"📁 {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list.addItem(item)


class _HistoryDialog(QDialog):
    """İŞLEMLER → '🗂️ Sürüm Geçmişi': hangi sürüm ne zaman, ne sonuçla gönderildi/kuruldu."""

    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Portal Sürüm / Gönderim Geçmişi")
        self.setMinimumSize(560, 420)
        lyt = QVBoxLayout(self)
        self.list = QListWidget()
        lyt.addWidget(self.list, 1)
        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.accept)
        lyt.addWidget(btn_close)

        logs = sync_log_service.recent(db, limit=100, source="portal") if db is not None else []
        logs = [log for log in logs if log.direction == sync_log_service.DIR_DEPLOY]
        if not logs:
            self.list.addItem("Henüz bir gönderim yapılmadı.")
            return
        for log in logs:
            when = log.created_at.strftime("%d.%m.%Y %H:%M") if log.created_at else ""
            item = QListWidgetItem(f"{'✅' if log.status == 'ok' else '❌'} {when} — {log.message}")
            if log.status != "ok":
                item.setForeground(Qt.GlobalColor.darkRed)
            self.list.addItem(item)


class PortalDeployWidget(QWidget):
    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, portal_dir: Path | None = None, output_dir: Path | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.store = portal_deploy.PortalFtpProfileStore(db_session) if db_session is not None else None
        self.portal_dir = Path(portal_dir) if portal_dir else portal_package.DEFAULT_PORTAL_DIR
        self.output_dir = Path(output_dir) if output_dir else portal_package.DEFAULT_OUTPUT_DIR
        self._worker: _DeployWorker | None = None
        self._test_worker: _SimpleWorker | None = None
        self._current_profile_id: str | None = None
        self._build_ui()
        self._build_detail_dialog()
        self.load()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # ── Profil listesi (standart dbgrid) — tek içerik, form/açıklama artık ayrı popuplarda ──
        self.tbl_profil = FilterableTableView(
            headers_dict={i: (h, h) for i, h in enumerate(_GRID_COLS)},
            profile_key="genel_ayarlar_portal_ftp",
            enable_profile_bar=False,
            parent=self,
        )
        self.profil_model = QStandardItemModel(self)
        self.profil_model.setHorizontalHeaderLabels(_GRID_COLS)
        self.tbl_profil.table_view.setModel(self.profil_model)
        self.tbl_profil.table_view.verticalHeader().setVisible(False)
        self.tbl_profil.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_profil.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl_profil.table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_profil.table_view.selectionModel().selectionChanged.connect(self._on_profile_row_changed)
        self.tbl_profil.table_view.doubleClicked.connect(lambda _i: self._open_edit_dialog())
        root.addWidget(self.tbl_profil, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("Paket sürümü:"))
        self.txt_version = QLineEdit()
        self.txt_version.setMaximumWidth(120)
        bottom_row.addWidget(self.txt_version)
        bottom_row.addStretch(1)
        root.addLayout(bottom_row)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size:11px; color:#334155;")
        root.addWidget(self.lbl_status)

    def _build_detail_dialog(self) -> None:
        """FTP profili ekle/düzenle popup'ı — listede çift tıklayınca ya da 'Yeni Profil Ekle' ile açılır;
        ana panelde artık sürekli açık bir form yok (kullanıcı geri bildirimi: "detaylar listedeki bilgiye
        çift tıklayınca açılsın, ekranda açık gelmesin")."""
        dlg = QDialog(self)
        dlg.setMinimumWidth(440)
        lyt = QVBoxLayout(dlg)

        form = QFormLayout()
        form.setSpacing(6)
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("ör. Canlı Sunucu, Test Sunucusu")
        form.addRow("Profil adı", self.txt_title)
        self.txt_host = QLineEdit()
        self.txt_host.setPlaceholderText("ftp.firmaniz.com")
        self.spn_port = QSpinBox()
        self.spn_port.setRange(1, 65535)
        self.spn_port.setValue(21)
        self.txt_user = QLineEdit()
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("FTP sunucu", self.txt_host)
        form.addRow("Port", self.spn_port)
        form.addRow("Kullanıcı", self.txt_user)
        form.addRow("Parola", self.txt_pass)

        remote_row = QHBoxLayout()
        self.txt_remote = QLineEdit()
        self.txt_remote.setPlaceholderText("public_html/portal  (FTP oturum köküne göre)")
        btn_browse = QPushButton("📁 Gözat…")
        btn_browse.setToolTip("Sunucuda Windows Gezgini gibi dolaşarak hedef klasörü seçin.")
        btn_browse.clicked.connect(self._on_browse_remote_dir)
        remote_row.addWidget(self.txt_remote, 1)
        remote_row.addWidget(btn_browse)
        form.addRow("Portal klasörü", remote_row)

        self.chk_tls = QCheckBox("Şifreli bağlantı (FTPS / TLS) kullan")
        self.chk_verify = QCheckBox("Sunucu sertifikasını doğrula")
        self.chk_passive = QCheckBox("Pasif mod")
        form.addRow("", self.chk_tls)
        form.addRow("", self.chk_verify)
        form.addRow("", self.chk_passive)
        lyt.addLayout(form)

        btns = QHBoxLayout()
        btn_cancel = QPushButton("İptal")
        btn_cancel.clicked.connect(dlg.reject)
        btn_save = QPushButton("💾 Kaydet")
        btn_save.setStyleSheet(
            "QPushButton{background:#2563eb; color:white; border:none; border-radius:6px;"
            " padding:6px 16px; font-weight:700;}",
        )
        btn_save.clicked.connect(lambda: self._on_save_in_dialog())
        btns.addStretch(1)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        lyt.addLayout(btns)

        self._detail_dialog = dlg

    def _on_save_in_dialog(self) -> None:
        self.save()
        self._detail_dialog.accept()

    def _open_edit_dialog(self) -> None:
        if self._selected_profile_id() is None:
            QMessageBox.information(self, "Portal Yayın", "Önce listeden bir profil seçin ya da "
                                    "İŞLEMLER'den 'Yeni Profil Ekle' kullanın.")
            return
        self._detail_dialog.setWindowTitle(f"FTP Profili — {self.txt_title.text()}")
        self._detail_dialog.exec()

    def _on_browse_remote_dir(self) -> None:
        profile = self.profile()
        if not (profile.host and profile.user):
            QMessageBox.information(self, "Klasör Seç", "Önce FTP sunucu ve kullanıcı bilgilerini girin.")
            return
        dlg = _FtpBrowserDialog(profile, self.txt_remote.text().strip() or "/", self)
        if dlg.exec():
            self.txt_remote.setText(dlg.selected_path())

    def show_help(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Yardım — Portal Yayın / Güncelleme")
        dlg.setMinimumSize(560, 480)
        lyt = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setHtml(HELP_HTML)
        browser.setOpenExternalLinks(True)
        lyt.addWidget(browser, 1)
        btn = QPushButton("Kapat")
        btn.clicked.connect(dlg.accept)
        lyt.addWidget(btn)
        dlg.exec()

    def show_history(self) -> None:
        _HistoryDialog(self.db, self).exec()

    # ------------------------------------------------------------------
    def load(self) -> None:
        self._reload_profile_grid(select=self.store.active_id() if self.store else None)
        self.txt_version.setText(portal_package.suggest_next_version(self.db, self.portal_dir) if self.db else "")

    def record_count(self) -> int:
        """Alt bardaki kayıt sayacı (bkz. `settings.py::_update_bottom_count`)."""
        return self.profil_model.rowCount()

    def _reload_profile_grid(self, select: str | None = None) -> None:
        self.profil_model.setRowCount(0)
        row_of_id: dict[str, int] = {}
        if self.store is not None:
            for p in self.store.list():
                r = self.profil_model.rowCount()
                self.profil_model.insertRow(r)
                for c, text in enumerate((p.title, p.host, p.user, p.remote_dir, "⭐" if select == p.id else "")):
                    self.profil_model.setItem(r, c, QStandardItem(text))
                self.profil_model.item(r, 0).setData(p.id, Qt.ItemDataRole.UserRole)
                row_of_id[p.id] = r
        sel = self.tbl_profil.table_view.selectionModel()
        sel.blockSignals(True)
        sel.clearSelection()
        sel.blockSignals(False)
        if select and select in row_of_id:
            self.tbl_profil.table_view.selectRow(row_of_id[select])
        self._on_profile_row_changed()

    def _selected_profile_id(self) -> str | None:
        rows = self.tbl_profil.table_view.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.profil_model.item(rows[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_profile_row_changed(self, *_args) -> None:
        pid = self._selected_profile_id()
        if not pid or self.store is None:
            self._current_profile_id = None
            for w in (self.txt_title, self.txt_host, self.txt_user, self.txt_remote):
                w.clear()
            self.txt_pass.clear()
            self.spn_port.setValue(21)
            self.chk_tls.setChecked(True)
            self.chk_verify.setChecked(True)
            self.chk_passive.setChecked(True)
            return
        meta = self.store.get(pid)
        if meta is None:
            return
        self._current_profile_id = meta.id
        self.txt_title.setText(meta.title)
        self.txt_host.setText(meta.host)
        self.spn_port.setValue(meta.port)
        self.txt_user.setText(meta.user)
        self.txt_pass.setText(self.store.password(meta.id))
        self.txt_remote.setText(meta.remote_dir)
        self.chk_tls.setChecked(meta.use_tls)
        self.chk_verify.setChecked(meta.verify_cert)
        self.chk_passive.setChecked(meta.passive)

    def new_profile(self) -> None:
        """İŞLEMLER → '➕ Yeni Profil Ekle': seçimi kaldırır, boş bir profil formu popup'ta açar."""
        self.tbl_profil.table_view.clearSelection()
        self._detail_dialog.setWindowTitle("Yeni FTP Profili")
        self._detail_dialog.exec()

    def _on_delete_profile(self) -> None:
        pid = self._current_profile_id
        if not pid or self.store is None:
            QMessageBox.information(self, "Portal Yayın", "Önce listeden bir profil seçin.")
            return
        title = self.store.get(pid).title if self.store.get(pid) else ""
        if QMessageBox.question(self, "Profili Kaldır", f"'{title}' profili listeden kaldırılsın mı?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        self.store.hide(pid)
        if self.store.active_id() == pid:
            self.store.set_active(None)
        self._reload_profile_grid()

    def profile(self) -> portal_deploy.FtpProfile:
        return portal_deploy.FtpProfile(
            host=self.txt_host.text().strip(), port=self.spn_port.value(), user=self.txt_user.text().strip(),
            password=self.txt_pass.text(), remote_dir=self.txt_remote.text().strip(),
            use_tls=self.chk_tls.isChecked(), verify_cert=self.chk_verify.isChecked(),
            passive=self.chk_passive.isChecked(),
        )

    def save(self) -> None:
        """Geçerli form alanlarını seçili profile (ya da yeniyse yeni bir profile) kaydeder ve etkin profil yapar."""
        if self.db is None or self.store is None:
            return
        title = self.txt_title.text().strip() or self.txt_host.text().strip() or "Profil"
        existing = self.store.get(self._current_profile_id) if self._current_profile_id else None
        meta = portal_deploy.PortalFtpProfile(
            title=title, host=self.txt_host.text().strip(), port=self.spn_port.value(), user=self.txt_user.text().strip(),
            remote_dir=self.txt_remote.text().strip(), use_tls=self.chk_tls.isChecked(), verify_cert=self.chk_verify.isChecked(),
            passive=self.chk_passive.isChecked(), **({"id": existing.id} if existing else {}),
        )
        ok, msg = self.store.save(meta, password=self.txt_pass.text())
        if ok:
            self._current_profile_id = meta.id
            self.store.set_active(meta.id)
            self._reload_profile_grid(select=meta.id)
        self._set_status(msg, ok)

    def _set_status(self, text: str, ok: bool | None = None) -> None:
        color = "#334155" if ok is None else ("#15803d" if ok else "#b91c1c")
        self.lbl_status.setStyleSheet(f"font-size:11px; color:{color};")
        self.lbl_status.setText(text)

    # ------------------------------------------------------------------
    def _on_test(self) -> None:
        """Bağlantıyı popup bir ilerleme/günlük penceresinde, arka planda test eder (UI donmaz)."""
        self.save()
        profile = self.profile()
        dlg = _ProgressLogDialog("Bağlantı Testi", self)
        dlg.log(f"{profile.host or '(sunucu tanımsız)'} adresine bağlanılıyor…")
        dlg.show()

        self._test_worker = _SimpleWorker(lambda: portal_deploy.test_connection(profile), self)

        def _done(result) -> None:
            if isinstance(result, Exception):
                dlg.log(f"Beklenmeyen hata: {result}", ok=False)
                self._set_status(str(result), False)
            else:
                dlg.log(result.message, ok=result.success)
                self._set_status(result.message, result.success)
            dlg.finish()
            self._test_worker = None

        self._test_worker.done.connect(_done)
        self._test_worker.start()

    def _on_copy_secret(self) -> None:
        if not self.db:
            return
        QApplication.clipboard().setText(portal_package.get_or_create_secret(self.db))
        self._set_status("Güncelleme anahtarı panoya kopyalandı. Sunucudaki config.local.php içine "
                         "'update_secret' olarak yapıştırın (paylaşmayın).", True)

    def _on_paste_secret(self) -> None:
        """Sunucunun kurulum sihirbazında ürettiği anahtarı (panodan) TOYA'ya alır; ilk kurulumda ikisi
        EŞLEŞMELİDİR — burada üretmek yerine sunucununkini almak doğru olan budur."""
        if not self.db:
            return
        text = QApplication.clipboard().text().strip()
        try:
            portal_package.set_secret(self.db, text)
        except ValueError as exc:
            self._set_status(f"Anahtar alınamadı: {exc}", False)
            return
        self._set_status("Panodaki anahtar 'Güncelleme anahtarı' olarak kaydedildi.", True)

    def _on_softaculous(self) -> portal_package.Path | None:
        """Softaculous paketini üretir (yalnızca yerel dosya işi; sunucuya göndermez)."""
        try:
            path = portal_package.build_softaculous_package(
                self.portal_dir, self.output_dir, portal_package.read_version(self.portal_dir))
        except (ValueError, OSError) as exc:
            self._set_status(f"Softaculous paketi üretilemedi: {exc}", False)
            return None
        self._set_status(
            f"Softaculous paketi hazır: {path}. Softaculous kurulumunda bu paket kullanılır; hostingde Softaculous yoksa "
            "FTP + kurulum sihirbazı yolunu kullanın.", True)
        return path

    def _prepare_job(self):
        """Ana iş parçacığında: veritabanından gerekenleri okur ve yalnızca dosya/ağ işi yapan bir iş döner.

        SQLAlchemy oturumu iş parçacığı güvenli olmadığından arka plandaki iş veritabanına DOKUNMAZ;
        sürüm kaydı, otomatik kurulum tetikleme ve günlük yazımı sonuç geldiğinde ana iş parçacığında
        yapılır (`_finalize`)."""
        version = self.txt_version.text().strip()
        secret = portal_package.get_or_create_secret(self.db)
        profile = self.profile()
        portal_dir, output_dir = self.portal_dir, self.output_dir

        def job(progress=None, log=None):
            def _log(msg: str) -> None:
                if log:
                    log(msg)

            _log(f"Paket üretiliyor (sürüm {version})…")
            try:
                zip_path = portal_package.build_package(portal_dir, output_dir, version, secret)
            except (ValueError, OSError) as exc:
                _log(f"Paket üretilemedi: {exc}")
                return portal_deploy.DeployResult(False, f"Paket üretilemedi: {exc}"), None, version
            _log(f"Paket üretildi: {zip_path.name}")
            _log("Sunucuya bağlanılıp gönderiliyor…")
            result = portal_deploy.upload_package(zip_path, profile, progress)
            return result, zip_path, version

        return job

    def _finalize(self, outcome) -> portal_deploy.DeployResult:
        """Ana iş parçacığında: sürümü kaydeder, başarılıysa otomatik kurulumu tetikler (Online Portal
        tanımlıysa) ve sonucu aktarım günlüğüne yazar (bkz. `_HistoryDialog`)."""
        result, zip_path, version = outcome
        if zip_path is None:
            return result
        portal_package.record_built_version(self.db, version)
        sync_log_service.record(
            self.db, "portal", sync_log_service.DIR_DEPLOY, result.success, result.message,
            {"package": Path(zip_path).name},
        )
        if not result.success:
            return result
        apply_result = portal_sync_service.trigger_apply(self.db, Path(zip_path).name)
        sync_log_service.record(
            self.db, "portal", sync_log_service.DIR_DEPLOY, apply_result.success, apply_result.message,
            {"package": Path(zip_path).name, "adim": "otomatik_kurulum"},
        )
        return portal_deploy.DeployResult(result.success, f"{result.message}\n{apply_result.message}", result.remote_path)

    def _do_deploy(self, progress=None) -> portal_deploy.DeployResult:
        """Eşzamanlı çalıştırır (testler ve komut satırı kullanımı için)."""
        return self._finalize(self._prepare_job()(progress))

    def _on_send(self) -> None:
        if self._worker is not None or not self.db:
            return
        if not self.profile().is_complete():
            QMessageBox.warning(self, "Portal", "FTP sunucu, kullanıcı ve parola girilmelidir.")
            return
        self.save()
        job = self._prepare_job()
        dlg = _ProgressLogDialog("Paket Üret ve Gönder", self)
        dlg.log("Başlatılıyor…")
        dlg.show()

        self._worker = _DeployWorker(job, self)
        self._worker.progress.connect(lambda s, t: dlg.set_progress(s, t))
        self._worker.log.connect(lambda m: dlg.log(m))
        self._worker.done.connect(lambda outcome: self._on_done(outcome, dlg))
        self._worker.start()

    def _on_done(self, outcome, dlg: _ProgressLogDialog | None = None) -> None:
        self._worker = None
        result = self._finalize(outcome)
        lines = result.message.split("\n")
        if dlg is not None:
            for i, line in enumerate(lines):
                dlg.log(line, ok=(result.success if i == len(lines) - 1 else None))
            dlg.finish()
        self._set_status(lines[0], result.success)
        self.toast_requested.emit(lines[0], "success" if result.success else "error")
        if result.success:
            self.txt_version.setText(portal_package.suggest_next_version(self.db, self.portal_dir))
