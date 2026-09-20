"""
TOYA ERP - GitProfilePanelWidget

Sol panelde "BAĞLANTI PROFİLLERİ": profil seçimi, ekleme/düzenleme, etkinleştirme, gizleme, bağlantı testi ve
"Google ile Giriş Yap". Ağ gerektiren işler (`test_remote`, `login`) ekrana `worker_requested(eylem, parametre)`
sinyaliyle bildirilir; ekran bunları arka plan iş parçacığında çalıştırır. Yerel işler (etkinleştirme, kayıt)
burada eşzamanlı yapılır.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from src.desktop.services import git_profile_store as store
from src.desktop.services.git_service import AUTH_GCM, AUTH_TOKEN, GitService
from src.desktop.ui.widgets.git_profile_dialog import GitProfileDialog

_BTN = ("QPushButton{background:#fff; color:#1e293b; border:1px solid #cbd5e1; border-radius:6px; padding:5px 8px;"
        " font-size:11px; font-weight:600; text-align:left;}QPushButton:hover{background:#f1f5f9;}"
        "QPushButton:disabled{color:#94a3b8; background:#f8fafc;}")
_AUTH_NAMES = {"gcm": "Google girişi", "token": "Erişim belirteci", "ssh": "SSH"}


class GitProfilePanelWidget(QWidget):
    worker_requested = pyqtSignal(str, dict)
    changed = pyqtSignal()
    message = pyqtSignal(str, bool)  # metin, başarılı mı

    def __init__(self, service: GitService | None = None, parent=None) -> None:
        super().__init__(parent)
        self.service = service or GitService()
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.cmb = QComboBox()
        self.cmb.setStyleSheet("QComboBox{border:1px solid #cbd5e1; border-radius:6px; padding:5px 8px; background:#fff;"
                               " font-size:11px;}")
        self.lbl_info = QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet("font-size:10px; color:#64748b;")
        lay.addWidget(QLabel("🌐 Aktif bağlantı profili:"))
        lay.addWidget(self.cmb)
        lay.addWidget(self.lbl_info)

        r1 = QHBoxLayout()
        self.btn_add = QPushButton("➕ Ekle")
        self.btn_edit = QPushButton("✏️ Düzenle")
        r1.addWidget(self.btn_add)
        r1.addWidget(self.btn_edit)
        lay.addLayout(r1)
        r2 = QHBoxLayout()
        self.btn_activate = QPushButton("✔ Etkin Yap")
        self.btn_hide = QPushButton("🙈 Gizle")
        r2.addWidget(self.btn_activate)
        r2.addWidget(self.btn_hide)
        lay.addLayout(r2)
        self.btn_test = QPushButton("🔌 Bağlantıyı Test Et")
        self.btn_login = QPushButton("🔵 Google ile Giriş Yap")
        self.btn_login.setToolTip("Tarayıcıyı açar; GitHub'da Google hesabınızla oturum açarsınız (Git Credential Manager).")
        lay.addWidget(self.btn_test)
        lay.addWidget(self.btn_login)
        self.lbl_ssh = QLabel()
        self.lbl_ssh.setWordWrap(True)
        self.lbl_ssh.setTextInteractionFlags(self.lbl_ssh.textInteractionFlags().TextSelectableByMouse)
        self.lbl_ssh.setStyleSheet("font-size:9px; color:#475569;")
        self.lbl_ssh.hide()
        lay.addWidget(self.lbl_ssh)
        for b in (self.btn_add, self.btn_edit, self.btn_activate, self.btn_hide, self.btn_test, self.btn_login):
            b.setStyleSheet(_BTN)

        self.btn_add.clicked.connect(self.add_profile)
        self.btn_edit.clicked.connect(self.edit_profile)
        self.btn_activate.clicked.connect(self.activate_selected)
        self.btn_hide.clicked.connect(self.hide_selected)
        self.btn_test.clicked.connect(lambda: self.worker_requested.emit("test_remote", {"profile_id": self.current_id()}))
        self.btn_login.clicked.connect(lambda: self.worker_requested.emit("login", {"profile_id": self.current_id()}))
        self.cmb.currentIndexChanged.connect(self._refresh_buttons)

    # ------------------------------------------------------------------
    def current(self) -> dict | None:
        return self.cmb.currentData()

    def current_id(self) -> int | None:
        p = self.current()
        return p["id"] if p else None

    def reload(self, select_id: int | None = None) -> None:
        store.seed_from_repo(self.service) if self.service.available() and self.service.is_repo() else None
        keep = select_id or self.current_id()
        self.cmb.blockSignals(True)
        self.cmb.clear()
        for p in store.list_profiles():
            self.cmb.addItem(("● " if p["is_active"] else "○ ") + p["title"], p)
        active = store.active_profile()
        want = keep or (active["id"] if active else None)
        for i in range(self.cmb.count()):
            if self.cmb.itemData(i)["id"] == want:
                self.cmb.setCurrentIndex(i)
                break
        self.cmb.blockSignals(False)
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        p = self.current()
        has = p is not None
        for b in (self.btn_edit, self.btn_activate, self.btn_hide, self.btn_test):
            b.setEnabled(has)
        self.btn_activate.setEnabled(has and not p["is_active"])
        self.btn_login.setEnabled(has and p["auth_type"] == AUTH_GCM)
        self.lbl_ssh.hide()
        if not has:
            self.lbl_info.setText("Henüz profil yok. '➕ Ekle' ile GitHub deponuzu tanımlayın.")
            return
        last = f" • Son işlem: {p['last_message']}" if p.get("last_message") else ""
        self.lbl_info.setText(f"{_AUTH_NAMES.get(p['auth_type'], p['auth_type'])} • {p['repo_url']} • {p['branch']}{last}")
        if p["auth_type"] == "ssh":
            key = self.service.ssh_public_key()
            self.lbl_ssh.setText("🗝 Ortak anahtar: " + (key or "bulunamadı (ssh-keygen -t ed25519 ile oluşturun)"))
            self.lbl_ssh.show()

    # ------------------------------------------------------------------ eylemler
    def _report(self, ok: bool, text: str) -> None:
        self.message.emit(text, ok)

    def _edit(self, profile: dict | None) -> None:
        dlg = GitProfileDialog(profile, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        ok, msg, pid = store.save_profile(dlg.values(), make_active=False)
        if not ok or pid is None:
            self._report(False, msg)
            return
        if dlg.token:
            stored, smsg = self.service.store_token(dlg.values()["repo_url"], dlg.values()["username"], dlg.token)
            msg += " " + smsg
            if not stored:
                self._report(False, msg)
        if dlg.make_active():
            ok2, msg2 = store.activate(pid, self.service)
            msg += " " + msg2
            ok = ok and ok2
        self.reload(pid)
        self._report(ok, msg)
        self.changed.emit()

    def add_profile(self) -> None:
        self._edit(None)

    def edit_profile(self) -> None:
        if self.current():
            self._edit(self.current())

    def activate_selected(self) -> None:
        pid = self.current_id()
        if pid is None:
            return
        ok, msg = store.activate(pid, self.service)
        self.reload(pid)
        self._report(ok, msg)
        self.changed.emit()

    def hide_selected(self) -> None:
        p = self.current()
        if not p:
            return
        if QMessageBox.question(self, "Profili Gizle", f"'{p['title']}' profili listeden gizlensin mi?\n"
                                "(Kayıt silinmez; git yapılandırması olduğu gibi kalır.)") != QMessageBox.StandardButton.Yes:
            return
        store.hide_profile(p["id"])
        self.reload()
        self._report(True, f"'{p['title']}' gizlendi.")
        self.changed.emit()

    def record_result(self, profile_id: int | None, ok: bool, message: str) -> None:
        if profile_id:
            store.record_result(profile_id, ok, message)
            self.reload(profile_id)
