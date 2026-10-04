"""TOYA ERP - BackupStatusPopup: yedek sürerken ana pencerenin köşesinde küçük durum penceresi.

Hangi aşamada olduğunu (arşivleme, doğrulama, yükleme…) ve ilerlemeyi gösterir. Yedek sürerken kullanıcı klavye/fare ile işlem yaparsa
'yedekleme sürüyor, işlem yapmamanız önerilir' uyarısı çıkar. Başka kullanıcı bağlı olduğundan bekleyen yedek de burada duyurulur.
Pencere odağı çalmaz; sonuç birkaç saniye sonra kendiliğinden kapanır."""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer
from PyQt6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout

_RESULT = {"ok": ("✅ Yedek tamamlandı", "#15803d"), "warning": ("⚠️ Yedek uyarıyla tamamlandı", "#b45309"),
           "error": ("❌ Yedek başarısız", "#b91c1c"), "nochange": ("➖ Değişiklik yok", "#475569")}
_INPUT_EVENTS = (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress)


class BackupStatusPopup(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BackupStatusPopup")
        self.setFixedWidth(330)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet("#BackupStatusPopup { background:#ffffff; border:1px solid #94a3b8; border-radius:8px; }"
                           "QLabel { background:transparent; } QProgressBar { border:1px solid #cbd5e1; border-radius:4px; height:10px;"
                           " background:#f1f5f9; } QProgressBar::chunk { background:#2563eb; border-radius:3px; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(4)
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-weight:800; color:#1e3a8a; font-size:12px;")
        self.lbl_stage = QLabel()
        self.lbl_stage.setWordWrap(True)
        self.lbl_stage.setStyleSheet("color:#334155; font-size:11px;")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.lbl_warn = QLabel("⚠ Yedekleme sürüyor. Veri tutarlılığı için şu an kayıt/işlem yapmamanız önerilir.")
        self.lbl_warn.setWordWrap(True)
        self.lbl_warn.setStyleSheet("background:#fffbeb; border:1px solid #fcd34d; border-radius:5px; padding:4px; color:#92400e; font-size:11px;")
        for w in (self.lbl_title, self.lbl_stage, self.bar, self.lbl_warn):
            v.addWidget(w)
        self.lbl_warn.hide()
        self.running = False
        self._last_warn = 0.0
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self.hide)
        self._warn_hide = QTimer(self)
        self._warn_hide.setSingleShot(True)
        self._warn_hide.timeout.connect(self.lbl_warn.hide)
        self.hide()

    # ---- konum -----------------------------------------------------------------------
    def reposition(self) -> None:
        p = self.parentWidget()
        if p is None:
            return
        self.adjustSize()
        self.move(max(0, p.width() - self.width() - 16), max(0, p.height() - self.height() - 36))

    def _goster(self, sure_ms: int = 0) -> None:
        self._hide.stop()
        self.show()
        self.raise_()
        self.reposition()
        if sure_ms:
            self._hide.start(sure_ms)

    # ---- yedekleyici olayları --------------------------------------------------------------
    def on_started(self, name: str) -> None:
        self.running = True
        self.lbl_title.setText(f"🛡 Yedek çalışıyor: {name}")
        self.lbl_title.setStyleSheet("font-weight:800; color:#1e3a8a; font-size:12px;")
        self.lbl_stage.setText("Başlatılıyor…")
        self.bar.setRange(0, 0)                      # aşama belirsizken hareketli
        self.bar.show()
        self.lbl_warn.hide()
        self._goster()

    def on_line(self, text: str) -> None:
        if self.running:
            self.lbl_stage.setText(text)
            self.reposition()

    def on_progress(self, done: int, total: int) -> None:
        if self.running and total:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(done * 100 / total))

    def on_finished(self, name: str, status: str, message: str) -> None:
        self.running = False
        baslik, renk = _RESULT.get(status, ("Yedek bitti", "#334155"))
        self.lbl_title.setText(f"{baslik}: {name}")
        self.lbl_title.setStyleSheet(f"font-weight:800; color:{renk}; font-size:12px;")
        self.lbl_stage.setText(message[:220])
        self.bar.hide()
        self.lbl_warn.hide()
        self._goster(9000 if status in ("ok", "nochange") else 20000)

    def on_waiting(self, name: str, users: str) -> None:
        """Başka kullanıcı bağlı olduğundan yedek başlatılmadı; kullanıcılar çıkınca otomatik başlar."""
        self.running = False
        self.lbl_title.setText(f"⏳ Yedek bekliyor: {name}")
        self.lbl_title.setStyleSheet("font-weight:800; color:#b45309; font-size:12px;")
        self.lbl_stage.setText(f"Bağlı kullanıcı var ({users}). Herkes çıkınca yedek kendiliğinden başlar.")
        self.bar.hide()
        self.lbl_warn.hide()
        self._goster(15000)

    # ---- kullanıcı etkinliği ---------------------------------------------------------------
    def note_activity(self, now: float | None = None) -> bool:
        """Yedek sürerken kullanıcı işlem yaptı: uyarıyı gösterir. @return uyarı gösterildi mi"""
        if not self.running:
            return False
        self.lbl_warn.show()
        self._warn_hide.start(8000)
        self.reposition()
        return True


class ActivityFilter(QObject):
    """Uygulama genelinde klavye/fare girdisini popup'a bildirir (yalnızca yedek sürerken iş yapar)."""

    def __init__(self, popup: BackupStatusPopup) -> None:
        super().__init__(popup)
        self.popup = popup

    def eventFilter(self, obj, ev) -> bool:  # noqa: N802
        if self.popup.running and ev.type() in _INPUT_EVENTS:
            self.popup.note_activity()
        return False
