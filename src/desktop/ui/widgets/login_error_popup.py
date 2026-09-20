"""
TOYA ERP - LoginErrorPopup

Hatalı giriş / giriş kilidi bilgilendirme penceresi.

- Otomatik kapanma geri sayımı ("Tamam (8)"). Kullanıcı "Otomatik kapanmayı
  durdur" kutucuğuyla sayacı durdurabilir; tercih SystemSetting'e yazılır.
- Giriş kilitliyse ayrı bir canlı geri sayım gösterir; kilit bitince
  `retry_ready` sinyali yayılır ve otomatik kapanma devre dışıdır.
- "🔑 Şifremi Unuttum" butonu `forgot_requested` sinyalini yayar.

Kullanım:
    dlg = LoginErrorPopup(db_session=db, message="Şifre hatalı", error_kind="bad_password",
                          locked_remaining=0)
    dlg.forgot_requested.connect(open_recovery)
    dlg.exec()
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.services import settings_store
from src.desktop.services.auth_service import (
    DEFAULT_AUTOCLOSE_SECONDS,
    KEY_AUTOCLOSE_DISABLED,
    KEY_AUTOCLOSE_SECONDS,
)


def _fmt_mmss(secs: int) -> str:
    m, s = divmod(max(0, secs), 60)
    return f"{m:02d}:{s:02d}"


class LoginErrorPopup(QDialog):
    forgot_requested = pyqtSignal()
    retry_ready = pyqtSignal()

    def __init__(
        self,
        *,
        db_session=None,
        message: str,
        error_kind: str = "bad_password",
        locked_remaining: int = 0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.db = db_session
        self.error_kind = error_kind
        self._locked_remaining = int(locked_remaining or 0)

        self.setWindowTitle("Giriş Uyarısı")
        self.setModal(True)
        self.setMinimumWidth(380)

        self._autoclose_seconds = settings_store.get_int(
            self.db, KEY_AUTOCLOSE_SECONDS, DEFAULT_AUTOCLOSE_SECONDS,
        )
        self._autoclose_disabled = settings_store.get_bool(
            self.db, KEY_AUTOCLOSE_DISABLED, False,
        )
        self._remaining = self._autoclose_seconds

        self._build_ui(message)
        self._wire_timers()

    # ------------------------------------------------------------------
    def _build_ui(self, message: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        icon = "🔒" if self.error_kind == "locked" else "⚠️"
        title = QLabel(f"{icon}  {message}")
        title.setWordWrap(True)
        title.setStyleSheet("font-size:13px; font-weight:600; color:#b91c1c;")
        root.addWidget(title)

        self.lbl_lock = QLabel("")
        self.lbl_lock.setStyleSheet("font-size:12px; color:#334155;")
        self.lbl_lock.setVisible(self._locked_remaining > 0)
        root.addWidget(self.lbl_lock)

        self.cb_stop_autoclose = QCheckBox("Otomatik kapanmayı durdur")
        self.cb_stop_autoclose.setChecked(self._autoclose_disabled)
        self.cb_stop_autoclose.setStyleSheet("font-size:11px; color:#64748b;")
        self.cb_stop_autoclose.toggled.connect(self._on_toggle_autoclose)
        root.addWidget(self.cb_stop_autoclose)

        btn_row = QHBoxLayout()
        self.btn_forgot = QPushButton("🔑 Şifremi Unuttum")
        self.btn_forgot.setStyleSheet(
            "QPushButton{background:transparent; color:#2563eb; border:none;"
            " text-decoration:underline; font-size:12px;}"
            "QPushButton:hover{color:#1d4ed8;}",
        )
        self.btn_forgot.clicked.connect(self._on_forgot)
        btn_row.addWidget(self.btn_forgot)
        btn_row.addStretch()

        self.btn_ok = QPushButton("Tamam")
        self.btn_ok.setDefault(True)
        self.btn_ok.setMinimumWidth(110)
        self.btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_ok)
        root.addLayout(btn_row)

        self._refresh_lock_label()
        self._refresh_ok_label()

    def _wire_timers(self) -> None:
        self._lock_timer = QTimer(self)
        self._lock_timer.setInterval(1000)
        self._lock_timer.timeout.connect(self._tick_lock)
        if self._locked_remaining > 0:
            self._lock_timer.start()

        self._autoclose_timer = QTimer(self)
        self._autoclose_timer.setInterval(1000)
        self._autoclose_timer.timeout.connect(self._tick_autoclose)
        if self._autoclose_active():
            self._autoclose_timer.start()

    # ------------------------------------------------------------------
    def _autoclose_active(self) -> bool:
        return (
            self._autoclose_seconds > 0
            and not self.cb_stop_autoclose.isChecked()
            and self._locked_remaining <= 0
        )

    def _refresh_ok_label(self) -> None:
        if self._autoclose_active():
            self.btn_ok.setText(f"Tamam ({self._remaining})")
        else:
            self.btn_ok.setText("Tamam")

    def _refresh_lock_label(self) -> None:
        if self._locked_remaining > 0:
            self.lbl_lock.setText(
                f"Giriş {_fmt_mmss(self._locked_remaining)} süreyle kilitli.",
            )
        else:
            self.lbl_lock.setText("Giriş kilidi kalktı, tekrar deneyebilirsiniz.")

    # ------------------------------------------------------------------
    def _tick_lock(self) -> None:
        self._locked_remaining -= 1
        if self._locked_remaining <= 0:
            self._locked_remaining = 0
            self._lock_timer.stop()
            self._refresh_lock_label()
            self.retry_ready.emit()
            # kilit bitti — otomatik kapanma başlasın
            if self._autoclose_active() and not self._autoclose_timer.isActive():
                self._remaining = self._autoclose_seconds
                self._autoclose_timer.start()
            self._refresh_ok_label()
        else:
            self._refresh_lock_label()

    def _tick_autoclose(self) -> None:
        if not self._autoclose_active():
            self._autoclose_timer.stop()
            self._refresh_ok_label()
            return
        self._remaining -= 1
        self._refresh_ok_label()
        if self._remaining <= 0:
            self._autoclose_timer.stop()
            self.accept()

    # ------------------------------------------------------------------
    def _on_toggle_autoclose(self, checked: bool) -> None:
        try:
            settings_store.set_setting(
                self.db, KEY_AUTOCLOSE_DISABLED, "1" if checked else "0",
            )
        except Exception:  # noqa: BLE001
            pass
        if checked:
            self._autoclose_timer.stop()
        elif self._autoclose_active():
            self._remaining = self._autoclose_seconds
            self._autoclose_timer.start()
        self._refresh_ok_label()

    def _on_forgot(self) -> None:
        self.forgot_requested.emit()
        self.accept()
