"""
TOYA ERP - GitSyncAdvisorWidget

Git durumunu tek bakışta özetleyen kart (aidat'taki "akıllı senkronizasyon tavsiyesi"): ne yapılması gerektiğini
söyler ve tek tıkla ilgili işlemi başlatır. Widget yalnızca gösterir; `action_requested(str)` sinyali ile
"backup" | "push" | "pull" | "remote" | "init" eylemlerini ekrana bildirir.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.desktop.services.git_service import Advice

_COLORS = {
    "success": ("#f0fdf4", "#86efac", "#166534", "✅"),
    "info": ("#eff6ff", "#93c5fd", "#1e40af", "☁️"),
    "warning": ("#fffbeb", "#fcd34d", "#92400e", "🟡"),
    "danger": ("#fef2f2", "#fca5a5", "#991b1b", "⚠️"),
}


class GitSyncAdvisorWidget(QFrame):
    action_requested = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._action = "none"
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-size:12px; font-weight:800;")
        self.lbl_advice = QLabel()
        self.lbl_advice.setWordWrap(True)
        self.lbl_advice.setStyleSheet("font-size:11px;")
        self.lbl_meta = QLabel()
        self.lbl_meta.setStyleSheet("font-size:10px; color:#64748b;")
        col.addWidget(self.lbl_title)
        col.addWidget(self.lbl_advice)
        col.addWidget(self.lbl_meta)
        lay.addLayout(col, 1)
        self.btn_action = QPushButton()
        self.btn_action.setStyleSheet("QPushButton{background:#2563eb; color:white; border:none; border-radius:6px;"
                                      " padding:6px 14px; font-weight:700;}QPushButton:hover{background:#1d4ed8;}")
        self.btn_action.clicked.connect(lambda: self.action_requested.emit(self._action))
        lay.addWidget(self.btn_action)
        self.set_advice(None)

    def set_advice(self, advice: Advice | None) -> None:
        if advice is None:
            self.setStyleSheet("QFrame{background:#f8fafc; border:1px solid #cbd5e1; border-radius:6px;}")
            self.lbl_title.setText("Git durumu okunuyor…")
            self.lbl_advice.setText("")
            self.lbl_meta.setText("")
            self.btn_action.hide()
            self._action = "none"
            return
        bg, border, fg, icon = _COLORS.get(advice.status, _COLORS["info"])
        self.setStyleSheet(f"QFrame{{background:{bg}; border:1px solid {border}; border-radius:6px;}}"
                           "QLabel{border:none; background:transparent;}")
        self.lbl_title.setText(f"{icon} {advice.title}")
        self.lbl_title.setStyleSheet(f"font-size:12px; font-weight:800; color:{fg};")
        self.lbl_advice.setText(advice.advice)
        self.lbl_advice.setStyleSheet(f"font-size:11px; color:{fg};")
        ex = advice.extra
        parts = []
        if ex.get("last_backup_ago"):
            parts.append(f"Son commit: {ex['last_backup_ago']}")
        if ex.get("last_hash"):
            parts.append(f"{ex['last_hash']} — {ex.get('last_message', '')[:60]}")
        self.lbl_meta.setText("  •  ".join(parts))
        self._action = advice.action
        if advice.action != "none" and advice.action_label:
            self.btn_action.setText(advice.action_label)
            self.btn_action.show()
        else:
            self.btn_action.hide()
