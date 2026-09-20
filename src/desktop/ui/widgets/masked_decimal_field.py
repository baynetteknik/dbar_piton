"""
TOYA ERP - MaskedDecimalField

Hesap makinesi tarzı, maskeli ondalık sayı/tutar giriş alanı. Ekran her zaman
"0,00" (veya ondalık hane sayısına göre "0,0000") biçimini korur:

- Virgüle basılana kadar girilen rakamlar tam sayı kısmına yazılır (binlik
  ayraç "." canlı olarak uygulanır).
- Virgüle basıldıktan sonra girilen rakamlar sırayla ondalık hanelere yazılır;
  girilmeyen ondalık haneler "0" olarak görünmeye devam eder.
- Ondalık hane sayısı parametriktir (`decimals` / `set_decimals`) — Genel
  Ayarlar'daki "Sayı Biçimi" tercihinden okunup tüm sayısal/fiyat alanlarına
  aynı şekilde uygulanabilir.

Kullanım:
    f = MaskedDecimalField(decimals=2)
    f.setValue(1585686.5)   # "1.585.686,50"
    f.value()                # 1585686.5
    f.valueChanged.connect(...)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLineEdit

_MAX_INT_DIGITS = 12


class MaskedDecimalField(QLineEdit):
    """Sağa yaslı, binlik ayraçlı, parametrik ondalık haneli maskeli sayı alanı."""

    valueChanged = pyqtSignal(float)  # noqa: N815 (Qt sinyal adlandırma kuralı)

    def __init__(self, *, decimals: int = 2, parent=None):
        super().__init__(parent)
        self._decimals = max(0, decimals)
        self._int_part = "0"
        self._dec_part = ""
        self._in_decimal = False
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._render()

    # ------------------------------------------------------------------
    def set_decimals(self, decimals: int) -> None:
        """Ondalık hane sayısını değiştirir (Genel Ayarlar'dan parametrik olarak)."""
        self._decimals = max(0, decimals)
        self._dec_part = self._dec_part[: self._decimals]
        self._render()

    def decimals(self) -> int:
        return self._decimals

    @staticmethod
    def _group(digits: str) -> str:
        digits = digits.lstrip("0") or "0"
        out: list[str] = []
        for i, ch in enumerate(reversed(digits)):
            if i and i % 3 == 0:
                out.append(".")
            out.append(ch)
        return "".join(reversed(out))

    def _render(self) -> None:
        int_display = self._group(self._int_part)
        text = int_display
        # İmleç, o an aktif olan kısmın (tam sayı ya da ondalık) son yazılan
        # hanesinin hemen sağında durur — maskenin dolgu sıfırlarının
        # (ör. henüz yazılmamış ondalık haneler) üzerine değil.
        cursor_pos = len(int_display)
        if self._decimals:
            dec_display = (self._dec_part + "0" * self._decimals)[: self._decimals]
            text = f"{int_display},{dec_display}"
            if self._in_decimal:
                cursor_pos = len(int_display) + 1 + len(self._dec_part)
        self.blockSignals(True)
        self.setText(text)
        self.blockSignals(False)
        self.setCursorPosition(cursor_pos)

    # ------------------------------------------------------------------
    def value(self) -> float:
        dec = self._dec_part.ljust(self._decimals, "0") if self._decimals else ""
        raw = f"{self._int_part}.{dec}" if dec else self._int_part
        try:
            return float(raw)
        except ValueError:
            return 0.0

    def setValue(self, v) -> None:  # noqa: N802
        try:
            v = float(v or 0)
        except (TypeError, ValueError):
            v = 0.0
        s = f"{v:.{self._decimals}f}" if self._decimals else f"{v:.0f}"
        if self._decimals:
            int_s, dec_s = s.split(".")
        else:
            int_s, dec_s = s, ""
        self._int_part = int_s.lstrip("0") or "0"
        self._dec_part = dec_s
        self._in_decimal = False
        self._render()

    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Fare ile virgülden önceye (tam sayı) veya sonrasına (ondalık)
        tıklamak, o kısma yazmaya başlamayı sağlar — yalnızca virgül tuşuna
        basmaya bağlı kalınmaz. Böylece "kuruş hanesine tıklayınca imleç
        sağa yapışıp yazdırmıyor" sorunu ortadan kalkar."""
        super().mousePressEvent(event)
        if not self._decimals:
            return
        comma_pos = len(self._group(self._int_part))
        click_pos = self.cursorPositionAt(event.pos())
        was_in_decimal = self._in_decimal
        self._in_decimal = click_pos > comma_pos
        if self._in_decimal and not was_in_decimal:
            self._dec_part = ""
        self._render()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        text = event.text()
        mods = event.modifiers()

        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier):
            if key == Qt.Key.Key_C:
                super().keyPressEvent(event)
            else:
                event.ignore()
            return

        if key in (
            Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End,
            Qt.Key.Key_Tab, Qt.Key.Key_Backtab, Qt.Key.Key_Return, Qt.Key.Key_Enter,
            Qt.Key.Key_Escape,
        ):
            super().keyPressEvent(event)
            return

        if text.isdigit():
            if self._in_decimal:
                if len(self._dec_part) < self._decimals:
                    self._dec_part += text
            elif len(self._int_part.lstrip("0")) < _MAX_INT_DIGITS:
                self._int_part = (self._int_part.lstrip("0") + text) or text
            self._render()
            self.valueChanged.emit(self.value())
            event.accept()
            return

        # Bazı klavye düzenlerinde (ör. numpad ondalık tuşu) sanal tuş kodu
        # Key_Comma/Key_Period olsa da event.text() boş ya da beklenmedik
        # gelebilir; bu yüzden tuş koduna da bakılır, yalnızca metne değil.
        if (text in (",", ".") or key in (Qt.Key.Key_Comma, Qt.Key.Key_Period)) and self._decimals:
            if not self._in_decimal:
                # setValue()'dan gelen "00" gibi görüntü amaçlı ondalık haneler
                # burada temizlenir — virgüle her basış, ondalık haneleri
                # sıfırdan yazmaya başlar (aksi halde önceden dolu "00"
                # arabelleği yeni rakamlara yer bırakmaz).
                self._dec_part = ""
            self._in_decimal = True
            event.accept()
            return

        if key == Qt.Key.Key_Backspace:
            if self._in_decimal:
                if self._dec_part:
                    self._dec_part = self._dec_part[:-1]
                else:
                    self._in_decimal = False
            else:
                self._int_part = self._int_part[:-1] or "0"
            self._render()
            self.valueChanged.emit(self.value())
            event.accept()
            return

        event.ignore()
