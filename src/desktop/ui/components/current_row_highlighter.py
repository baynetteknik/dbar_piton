"""
TOYA ERP - CurrentRowHighlighter

Bir ``QTableView``'in aktif (imleç bulunan / seçili) satırını yumuşak bir arka
plan tonuyla vurgular. Modele veya item delegate'e dokunmaz; yalnızca görünümün
seçim davranışını "satır" yapar ve seçili satır rengini stil şablonuyla ayarlar.

Bu yüzden koşullu renklendirme delegate'iyle (``ProfileStyleDelegate``) çakışmaz
ve her tablo görünümünde tek satırda yeniden kullanılabilir::

    CurrentRowHighlighter(self.table_view).apply()
    # veya farklı renkle
    CurrentRowHighlighter(self.table_view, bg="#fde68a").apply()
"""

from __future__ import annotations

from PyQt6.QtWidgets import QAbstractItemView, QTableView

__all__ = ["CurrentRowHighlighter"]


class CurrentRowHighlighter:
    """QTableView'de seçili satırı renkle vurgulayan yeniden kullanılabilir yardımcı."""

    #: Varsayılan vurgulu satır arka planı (belirgin açık mavi) ve metin rengi
    DEFAULT_BG = "#bfdbfe"
    DEFAULT_FG = "#0f172a"

    #: Stil kuralını, başka bir <style> ile karışmasın diye işaretleyen yorum
    _MARKER = "/*current-row-highlighter*/"

    def __init__(
        self,
        table_view: QTableView,
        *,
        bg: str = DEFAULT_BG,
        fg: str = DEFAULT_FG,
        whole_row: bool = True,
    ) -> None:
        self.view = table_view
        self.bg = bg
        self.fg = fg
        self.whole_row = whole_row

    # ------------------------------------------------------------------
    def apply(self) -> "CurrentRowHighlighter":
        """Vurguyu görünüme uygular (idempotent — birden çok kez çağrılabilir)."""
        if self.whole_row:
            self.view.setSelectionBehavior(
                QAbstractItemView.SelectionBehavior.SelectRows,
            )
        self._write_rule()
        return self

    def set_color(self, bg: str, fg: str | None = None) -> None:
        """Vurgu rengini değiştirir ve yeniden uygular."""
        self.bg = bg
        if fg:
            self.fg = fg
        self._write_rule()

    def remove(self) -> None:
        """Vurgu kuralını görünümden temizler (diğer stilleri korur)."""
        self.view.setStyleSheet(self._strip_existing(self.view.styleSheet() or ""))

    # ------------------------------------------------------------------
    def _write_rule(self) -> None:
        base = self._strip_existing(self.view.styleSheet() or "")
        rule = (
            f"{self._MARKER}"
            f"QTableView::item:selected{{"
            f"background-color:{self.bg};color:{self.fg};}}"
            f"QTableView::item:selected:!active{{"
            f"background-color:{self.bg};color:{self.fg};}}"
            f"{self._MARKER}"
        )
        self.view.setStyleSheet(f"{base}{rule}" if base else rule)

    def _strip_existing(self, css: str) -> str:
        """Daha önce eklenmiş kuralı (iki marker arası) söker."""
        while self._MARKER in css:
            start = css.index(self._MARKER)
            end = css.index(self._MARKER, start + len(self._MARKER))
            css = css[:start] + css[end + len(self._MARKER):]
        return css.strip()
