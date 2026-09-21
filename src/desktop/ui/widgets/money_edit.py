"""TOYA ERP - MoneyEdit: tüm parasal alanlar için ortak tutar girişi (maske + hesap makinesi).

Yazım:  3550 yazarken `3.550` (binlik ayraç nokta) görünür; virgüle basınca kuruş hanesi girilir: `3.550,25`.
        Alan bırakılınca / Enter'da sabit ondalıkla biçimlenir (`3.550,25`, `3.550` → `3.550,00`).
Hesap makinesi: rakamdan sonra + - * / (ya da x, :) yazılırsa alan toplama makinesi gibi çalışır; `100+250*2` yazarken
        sonuç ipucu olarak görünür, Enter (veya =) sonucu alana aktarır. İşlem önceliği matematikteki gibidir (* ve / önce).
API (MaskedDecimalField ile uyumlu): `value()`, `setValue(v)`, `valueChanged(float)`, `set_decimals()`.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QLineEdit, QToolTip

_OPS = "+-*/"
_TUS_ESLEME = {"x": "*", "X": "*", ":": "/", "÷": "/", "×": "*"}
_IZINLI = set("0123456789,") | set(_OPS)


def _grupla(tam: str) -> str:
    out = []
    for i, ch in enumerate(reversed(tam)):
        if i and i % 3 == 0:
            out.append(".")
        out.append(ch)
    return "".join(reversed(out))


def bicimle(v: Decimal | float | int, ondalik: int = 2) -> str:
    """Sabit ondalıklı, binlik ayraçlı Türkçe tutar metni: 3550.25 -> '3.550,25'."""
    d = Decimal(str(v)) if not isinstance(v, Decimal) else v
    q = d.quantize(Decimal(1).scaleb(-ondalik), rounding=ROUND_HALF_UP) if ondalik else d.quantize(Decimal(1), rounding=ROUND_HALF_UP)
    neg = q < 0
    s = f"{abs(q):f}"
    tam, _, kes = s.partition(".")
    metin = _grupla(tam) + (f",{kes}" if ondalik else "")
    return f"-{metin}" if neg else metin


def sayiya(metin: str) -> Decimal | None:
    """'3.550,25' / '3550,25' -> Decimal; boş ya da çözülemezse None."""
    t = (metin or "").replace(".", "").replace(" ", "").replace(",", ".")
    if t in ("", "-", "."):
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def hesapla(ifade: str) -> Decimal | None:
    """`100+250*2` gibi ifadeyi hesaplar (önce * /, sonra + -). Geçersizse ya da sıfıra bölünürse None."""
    ham = ifade.replace(".", "").replace(" ", "").replace(",", ".")
    ham = ham.rstrip(_OPS)                                    # yarım kalan işlemi yok say
    parcalar = re.split(r"([+\-*/])", ham)
    sayilar: list[Decimal] = []
    ops: list[str] = []
    beklenen_sayi = True
    i = 0
    negatif = False
    while i < len(parcalar):
        p = parcalar[i]
        if beklenen_sayi:
            if p == "":
                if i + 1 < len(parcalar) and parcalar[i + 1] == "-" and not negatif and not sayilar:
                    negatif = True                          # baştaki eksi işareti
                    i += 2
                    continue
                return None
            try:
                v = Decimal(p)
            except InvalidOperation:
                return None
            sayilar.append(-v if negatif else v)
            negatif = False
            beklenen_sayi = False
        else:
            if p not in _OPS:
                return None
            ops.append(p)
            beklenen_sayi = True
        i += 1
    if not sayilar or len(sayilar) != len(ops) + 1:
        return None
    # önce çarpma / bölme
    s2, o2 = [sayilar[0]], []
    for op, v in zip(ops, sayilar[1:]):
        if op in "*/":
            if op == "/" and v == 0:
                return None
            s2[-1] = s2[-1] * v if op == "*" else s2[-1] / v
        else:
            o2.append(op)
            s2.append(v)
    sonuc = s2[0]
    for op, v in zip(o2, s2[1:]):
        sonuc = sonuc + v if op == "+" else sonuc - v
    return sonuc


class MoneyEdit(QLineEdit):
    """Parasal tutar alanı; bkz. modül açıklaması."""

    valueChanged = pyqtSignal(float)  # noqa: N815 (Qt sinyal adlandırma kuralı)

    def __init__(self, *, decimals: int = 2, allow_negative: bool = False, allow_empty: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._decimals = max(0, decimals)
        self.allow_negative = allow_negative
        self.allow_empty = allow_empty
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setPlaceholderText("0" if not allow_empty else "")
        self.textEdited.connect(self._yazildi)
        if not allow_empty:
            self.setText(bicimle(0, self._decimals))

    # ---- API ---------------------------------------------------------------
    def decimals(self) -> int:
        return self._decimals

    def set_decimals(self, decimals: int) -> None:
        self._decimals = max(0, decimals)
        self.setValue(self.value())

    def value(self) -> float:
        """Alandaki tutar (ifade yazılıysa hesaplanmış sonucu; geçersizse 0)."""
        t = self.text()
        d = hesapla(t) if any(o in t[1:] for o in _OPS) else sayiya(t)
        return float(d) if d is not None else 0.0

    def setValue(self, v) -> None:  # noqa: N802
        try:
            self.setText(bicimle(Decimal(str(float(v or 0))), self._decimals))
        except (InvalidOperation, ValueError, TypeError):
            self.setText(bicimle(0, self._decimals))

    def has_expression(self) -> bool:
        return any(o in self.text()[1:] for o in _OPS)

    def commit_expression(self) -> bool:
        """İfade varsa sonucu alana yazar; yoksa sabit ondalıklı biçime getirir. Geçersiz ifadede False döner
        (metin korunur, hata ipucu gösterilir)."""
        t = self.text().strip()
        if not t:
            if not self.allow_empty:
                self.setText(bicimle(0, self._decimals))
            return True
        d = hesapla(t) if self.has_expression() else sayiya(t)
        if d is None:
            self._ipucu("Geçersiz işlem (sıfıra bölme ya da eksik sayı)")
            return False
        if d < 0 and not self.allow_negative:
            self._ipucu("Tutar negatif olamaz")
            return False
        self.setText(bicimle(d, self._decimals))
        QToolTip.hideText()
        self.valueChanged.emit(float(d))
        return True

    # ---- klavye ------------------------------------------------------------
    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            hesapliydi = self.has_expression()
            if not self.commit_expression():
                return                                   # geçersiz ifade: alanda kal
            if hesapliydi:
                return                                   # ilk Enter yalnızca sonucu aktarır; formu (Kaydet) tetiklemez
            super().keyPressEvent(event)
            return
        ch = event.text()
        if ch == "=":
            self.commit_expression()
            return
        if ch and ch.isprintable() and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            ch = _TUS_ESLEME.get(ch, ch)
            if ch == ".":
                ch = ","                                 # tuş takımındaki nokta ondalık ayraç sayılır (binlik noktayı maske koyar)
            if ch not in _IZINLI:
                return                                   # harf vb. yazılamaz
            self.insert(ch)
            self._yazildi(self.text())
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.commit_expression()
        super().focusOutEvent(event)

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        """Yapıştırma: '1.234,56' ve '1234.56' biçimleri doğru anlaşılır."""
        t = source.text().strip()
        if "," in t:
            t = t.replace(".", "")
        elif t.count(".") == 1 and len(t.split(".")[1]) <= self._decimals:
            t = t.replace(".", ",")
        else:
            t = t.replace(".", "")
        self.insert("".join(c for c in t if c in _IZINLI))
        self._yazildi(self.text())

    # ---- biçimleme ---------------------------------------------------------
    def _yazildi(self, metin: str) -> None:
        """Her yazımdan sonra: binlik noktaları yeniden koy, ondalığı sınırla, işleçleri düzenle, imleci koru."""
        pos = self.cursorPosition()
        anahtar = sum(1 for c in metin[:pos] if c in _IZINLI)          # imlecin solundaki anlamlı karakter sayısı
        ham = metin.replace(".", "").replace(" ", "")
        cikti: list[list[str]] = []                                     # [tür, metin]; tür: "sayi" | "op"
        eksi_bekliyor = False
        for t in re.findall(r"[0-9,]+|[+\-*/]", ham):
            if t in _OPS:
                if cikti and cikti[-1][0] == "op":
                    cikti[-1][1] = t                                    # üst üste işleç: sonuncusu geçerli
                elif cikti:
                    cikti.append(["op", t])
                elif t == "-" and self.allow_negative:
                    eksi_bekliyor = True                                # baştaki eksi (yalnız izin varsa)
                continue
            tam, virgul, kes = t.partition(",")
            kes = kes.replace(",", "")[: self._decimals]
            tam = tam.lstrip("0") or ("0" if (virgul or tam) else "")
            sayi = _grupla(tam) + ("," + kes if virgul and self._decimals else "")
            if eksi_bekliyor:
                sayi, eksi_bekliyor = "-" + sayi, False
            cikti.append(["sayi", sayi])
        if eksi_bekliyor and not cikti:
            cikti.append(["sayi", "-"])
        yeni = "".join(f" {m} " if k == "op" else m for k, m in cikti)
        self.blockSignals(True)
        self.setText(yeni)
        self.blockSignals(False)
        toplam = sum(1 for c in yeni if c in _IZINLI)
        if anahtar >= toplam:
            self.setCursorPosition(len(yeni))
        else:                                                           # imleci aynı anlamlı karakterin sağına koy
            sayac = 0
            for i, c in enumerate(yeni):
                if c in _IZINLI:
                    sayac += 1
                if sayac == anahtar:
                    self.setCursorPosition(i + 1)
                    break
            else:
                self.setCursorPosition(0)
        if self.has_expression():
            d = hesapla(yeni)
            self._ipucu("= " + bicimle(d, self._decimals) if d is not None else "…")
        else:
            QToolTip.hideText()
            d = sayiya(yeni)
            self.valueChanged.emit(float(d) if d is not None else 0.0)

    def _ipucu(self, metin: str) -> None:
        QToolTip.showText(self.mapToGlobal(QPoint(0, self.height() + 2)), metin, self)
