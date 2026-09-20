"""
TOYA ERP - CodedButton

Metin + altında küçük KOD rozeti olan düğme (kodu satır sonuna eklemek dar panellerde yer harcıyordu).
`text()` yalnızca adı döndürür; kod `code()` ile alınır, rozet `set_code_visible()` ile açılıp kapanır.
Renk/yazı boyutu, düğmeye verilen stil sayfasından (`color:`, `font-size:`, `font-weight:`) okunur, böylece
mevcut menü/işlem stilleri (aktif/pasif) aynen çalışır.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

_BADGE_QSS = ("background:#eef2ff; color:#4f46e5; border:1px solid #c7d2fe; border-radius:6px; padding:0px 6px;"
              " font-size:8px; font-weight:700; font-family:'Consolas','Segoe UI';")


class CodedButton(QPushButton):
    def __init__(self, text: str = "", code: str = "", parent: QWidget | None = None, show_code: bool = True,
                 left_padding: int = 8) -> None:
        super().__init__(parent)
        self._name = text
        self._code = code
        self._show_code = show_code
        self._left = left_padding
        lay = QVBoxLayout(self)
        lay.setContentsMargins(left_padding, 3, 6, 3)
        lay.setSpacing(1)
        self._lbl = QLabel(text)
        self._lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._lbl.setWordWrap(False)
        self._badge = QLabel(code)
        self._badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._badge.setStyleSheet(_BADGE_QSS)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self._lbl)
        lay.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignLeft)
        self._refresh()

    # -------------------------------------------------------------- API
    def text(self) -> str:  # noqa: D401
        return self._name

    def setText(self, text: str) -> None:  # noqa: N802
        self._name = text
        self._lbl.setText(text)

    def code(self) -> str:
        return self._code

    def set_code(self, code: str) -> None:
        self._code = code
        self._badge.setText(code)
        self._refresh()

    def set_code_visible(self, on: bool) -> None:
        self._show_code = on
        self._refresh()

    def code_visible(self) -> bool:
        return bool(self._code) and self._show_code

    def _refresh(self) -> None:
        self._badge.setVisible(self.code_visible())
        self.setMinimumHeight(34 if self.code_visible() else 24)
        self.updateGeometry()

    def setStyleSheet(self, css: str) -> None:  # noqa: N802
        super().setStyleSheet(css)
        color = re.search(r"(?<![-\w])color:\s*(#[0-9a-fA-F]{3,8})", css)
        size = re.search(r"font-size:\s*(\d+px)", css)
        weight = re.search(r"font-weight:\s*(\w+)", css)
        self._lbl.setStyleSheet(
            "background:transparent; border:none; padding:0px;"
            + (f"color:{color.group(1)};" if color else "")
            + (f"font-size:{size.group(1)};" if size else "")
            + (f"font-weight:{weight.group(1)};" if weight else ""),
        )
