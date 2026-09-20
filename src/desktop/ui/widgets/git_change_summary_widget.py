"""
TOYA ERP - GitChangeSummaryWidget

Değişiklik özeti (aidat'taki "fark inceleme"): türe göre sayılar, klasöre göre dağılım ve uyarılar.
Yalnızca `GitService.comparison()` sözlüğünü gösterir.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

_TYPES = (("modified", "🟡 Değişti"), ("untracked", "🆕 Yeni"), ("added", "➕ Eklendi"),
          ("deleted", "🗑 Silindi"), ("renamed", "↔ Yeniden adlandı"))
_WARN = {"danger": "#b91c1c", "warning": "#b45309", "info": "#1d4ed8", "success": "#15803d"}


class GitChangeSummaryWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        self.lbl_counts = QLabel()
        self.lbl_cats = QLabel()
        self.lbl_warn = QLabel()
        for w in (self.lbl_counts, self.lbl_cats, self.lbl_warn):
            w.setWordWrap(True)
            w.setStyleSheet("font-size:10px; color:#334155;")
            lay.addWidget(w)
        self.set_comparison(None)

    def set_comparison(self, cmp: dict[str, Any] | None) -> None:
        if not cmp or not cmp.get("ok"):
            self.lbl_counts.setText((cmp or {}).get("message", "Git durumu yok."))
            self.lbl_cats.setText("")
            self.lbl_warn.setText("")
            return
        s = cmp["summary"]
        self.lbl_counts.setText(f"<b>Toplam {s['total']} dosya</b>" + "".join(
            f" • {label} {s[k]}" for k, label in _TYPES if s.get(k)))
        cats = cmp["categories"][:6]
        self.lbl_cats.setText("📁 " + " • ".join(f"{name} ({n})" for name, n in cats) if cats else "")
        self.lbl_warn.setText("<br>".join(
            f"<span style='color:{_WARN.get(w['type'], '#334155')}'><b>{w['title']}</b> — {w['message']}</span>"
            for w in cmp["warnings"]))
