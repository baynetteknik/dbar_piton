"""
TOYA ERP - PortalPublishWidget

Bir teklifin online portalda yayınlanması, linkinin kopyalanması, müşteri
kararlarının (kabul / ret / karşı teklif) alınması ve yayının iptali için
gömülebilir bölüm. Belge detay ekranının sağ panelinde kullanılır.

`ensure_saved`: belge kaydedilmemişse kaydetmeyi deneyip belge id'sini döndüren
(başarısızsa `None`) çağrılabilir — yayın her zaman kayıtlı veriyle yapılır.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.models import Quotation
from src.desktop.services import portal_sync_service

_STATUS_TR = {
    "draft": "Taslak", "sent": "Müşteriye gönderildi", "accepted": "Müşteri kabul etti",
    "rejected": "Müşteri reddetti", "converted": "Dönüştürüldü", "cancelled": "İptal",
}
_BTN = (
    "QPushButton{{background:{bg}; color:{fg}; border:1px solid {bd}; border-radius:5px;"
    " padding:5px 8px; font-weight:600; font-size:11px; text-align:left;}}"
    "QPushButton:hover{{background:{hv};}} QPushButton:disabled{{color:#94a3b8;}}"
)


def _style(bg: str, fg: str, bd: str, hv: str) -> str:
    return _BTN.format(bg=bg, fg=fg, bd=bd, hv=hv)


class PortalPublishWidget(QWidget):
    toast_requested = pyqtSignal(str, str)
    #: Yayın/karar sonrası teklif durumu değişmiş olabilir (ekran özetini yenilemek için).
    state_changed = pyqtSignal()

    def __init__(self, db_session=None, ensure_saved: Callable[[], int | None] | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self._ensure_saved = ensure_saved
        self._doc_id: int | None = None
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(4)

        self.lbl_state = QLabel("")
        self.lbl_state.setWordWrap(True)
        self.lbl_state.setStyleSheet("font-size:11px; color:#334155; padding:2px 0;")
        lyt.addWidget(self.lbl_state)

        self.btn_publish = QPushButton("🌐 Portala Gönder")
        self.btn_publish.setStyleSheet(_style("#0f766e", "#ffffff", "#0d9488", "#115e59"))
        self.btn_copy = QPushButton("🔗 Portal Linkini Kopyala")
        self.btn_pull = QPushButton("🔄 Müşteri Kararlarını Al")
        self.btn_revoke = QPushButton("⛔ Yayını İptal Et")
        for b in (self.btn_copy, self.btn_pull, self.btn_revoke):
            b.setStyleSheet(_style("#ffffff", "#1e293b", "#cbd5e1", "#f1f5f9"))
        for b in (self.btn_publish, self.btn_copy, self.btn_pull, self.btn_revoke):
            lyt.addWidget(b)

        self.btn_publish.clicked.connect(self._on_publish)
        self.btn_copy.clicked.connect(self._on_copy)
        self.btn_pull.clicked.connect(self._on_pull)
        self.btn_revoke.clicked.connect(self._on_revoke)

    # ------------------------------------------------------------------
    def set_document(self, doc_id: int | None) -> None:
        self._doc_id = doc_id
        self.refresh()

    def _quotation(self) -> Quotation | None:
        if self.db and self._doc_id:
            return self.db.get(Quotation, self._doc_id)
        return None

    def refresh(self) -> None:
        q = self._quotation()
        pub = portal_sync_service.get_publication(self.db, q.quotation_number) if q and self.db else None
        configured = bool(self.db) and portal_sync_service.is_configured(self.db)

        if not configured:
            self.lbl_state.setText("Portal tanımlı değil (Genel Ayarlar → Online Portal).")
        elif q is None:
            self.lbl_state.setText("Belge kaydedilince portala gönderilebilir.")
        elif pub:
            self.lbl_state.setText(f"Yayında · Durum: {_STATUS_TR.get(q.status, q.status)}")
        else:
            self.lbl_state.setText("Henüz portala gönderilmedi.")

        decided = q is not None and q.status in ("accepted", "rejected")
        self.btn_publish.setEnabled(configured and not decided)
        self.btn_publish.setText("🌐 Yeniden Yayınla" if pub else "🌐 Portala Gönder")
        self.btn_copy.setEnabled(bool(pub))
        self.btn_pull.setEnabled(configured)
        self.btn_revoke.setEnabled(bool(pub) and not decided)

    # ------------------------------------------------------------------
    def _resolve_doc_id(self) -> int | None:
        if self._ensure_saved is not None:
            doc_id = self._ensure_saved()
            if doc_id:
                self._doc_id = doc_id
            return doc_id
        return self._doc_id

    def _on_publish(self) -> None:
        doc_id = self._resolve_doc_id()
        if not doc_id:
            QMessageBox.warning(self, "Portal", "Teklif önce kaydedilmelidir.")
            return
        r = portal_sync_service.publish_quotation(self.db, doc_id)
        self.refresh()
        if r.success:
            self.state_changed.emit()
            self.toast_requested.emit("Teklif portalda yayınlandı", "success")
            QMessageBox.information(self, "Portal", f"{r.message}\n\n{r.url}")
        else:
            QMessageBox.warning(self, "Portal", r.message)

    def _on_copy(self) -> None:
        q = self._quotation()
        pub = portal_sync_service.get_publication(self.db, q.quotation_number) if q else None
        if not pub:
            return
        QApplication.clipboard().setText(pub["url"])
        self.toast_requested.emit("Portal linki kopyalandı", "success")

    def _on_pull(self) -> None:
        r = portal_sync_service.pull_decisions(self.db)
        self.refresh()
        if not r.success:
            QMessageBox.warning(self, "Portal", r.message)
            return
        if r.applied:
            self.state_changed.emit()
        self.toast_requested.emit(r.message, "success" if r.applied else "info")

    def _on_revoke(self) -> None:
        if not self._doc_id:
            return
        if QMessageBox.question(
            self, "Yayını İptal Et",
            "Portal linki geçersiz hale gelecek; müşteri artık teklife erişemeyecek. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        r = portal_sync_service.revoke_quotation(self.db, self._doc_id)
        self.refresh()
        self.toast_requested.emit(r.message, "success" if r.success else "error")
