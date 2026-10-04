"""TOYA ERP - LookupCellDelegate: grid hücresinde kayıt (cari, stok kartı, ...) yazdıkça listeleyen, büyüteç düğmeli editör.

Cari widget'ındaki gibi çalışır: yazdıkça (kod ya da adın herhangi bir yerinde) öneri listesi açılır, listeden seçilir;
hücrenin sağındaki büyüteç tam seçim listesini açar. Seçim yapılınca kayıt satıra yazılır ve klavye akışı devam eder.
Doğrudan kart / seçim penceresi açılmaz.

Katalog kayıtları `{"id", "code", "name", ...}` sözlükleridir. `kod_kolonu`, kodun yazıldığı sütundur; diğer sütuna ad yazılır."""

from __future__ import annotations

from PyQt6 import sip
from PyQt6.QtCore import QRect, Qt, QTimer
from PyQt6.QtWidgets import QAbstractItemDelegate, QCompleter, QLineEdit

from src.desktop.ui.components.grid_delegates import NavDelegate

_POPUP_QSS = ("QListView { background-color: #ffffff; color: #1e293b; border: 1px solid #cbd5e1; outline: 0; }"
              " QListView::item { padding: 3px 6px; }"
              " QListView::item:selected { background-color: #dbeafe; color: #1e3a8a; }")
_EDITOR_QSS = ("QLineEdit { background: #ffffff; color: #0f172a; border: 1px solid #2563eb; padding: 0px 4px;"
               " selection-background-color: #bfdbfe; selection-color: #0f172a; }")
_AYRAC = "  —  "


class LookupCellDelegate(NavDelegate):
    """`katalog()` kayıt listesini, `sec(row, kayit)` seçimi satıra yazmayı, `liste(ilk_arama)` tam seçim listesini
    (seçilen kaydı ya da None döner) sağlayan çağrılabilirlerle çalışır."""

    def __init__(self, grid, katalog, sec, liste, kod_kolonu: int, ipucu: str = "Seçim listesi (F4)") -> None:
        super().__init__(grid)
        self._katalog, self._sec, self._liste, self.kod_kolonu, self._ipucu = katalog, sec, liste, kod_kolonu, ipucu

    def createEditor(self, parent, _option, index):  # noqa: N802
        from src.desktop.ui.widgets.catalog_picker import _magnifier_icon

        le = QLineEdit(parent)
        le.setStyleSheet(_EDITOR_QSS)
        gosterim = {f"{c['code']}{_AYRAC}{c['name']}": c for c in self._katalog()}
        comp = QCompleter(list(gosterim), le)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        comp.setMaxVisibleItems(10)
        comp.popup().setStyleSheet(_POPUP_QSS)
        le.setCompleter(comp)
        # Öneri listesi hücre genişliğine sıkışmasın: yazdıkça daha geniş açılır
        le.textEdited.connect(lambda _t, le=le, comp=comp: QTimer.singleShot(
            0, lambda: comp.complete(QRect(0, 0, max(le.width(), 420), le.height())) if comp.completionCount() else None))
        row, col = index.row(), index.column()
        comp.activated[str].connect(lambda text, le=le, row=row, g=gosterim, col=col:
                                    QTimer.singleShot(0, lambda: self._secildi(le, row, col, g.get(text))))
        act = le.addAction(_magnifier_icon(14, "#2563eb"), QLineEdit.ActionPosition.TrailingPosition)
        act.setToolTip(self._ipucu)
        act.triggered.connect(lambda _=False, le=le, row=row, col=col: self._liste_ac(le, row, col))
        return le

    def setEditorData(self, editor, index):  # noqa: N802
        editor.setText(index.data() or "")
        editor.selectAll()

    def _secildi(self, le, row: int, col: int, kayit: dict | None) -> None:
        """Öneri listesinden / seçim listesinden kayıt seçildi: satıra yaz, düzenlemeyi kapat, klavye akışını sürdür."""
        if kayit is None:
            return
        self._sec(row, kayit)
        # Seçim penceresi açıkken editör odak kaybıyla ya da satır güncellemesiyle yok edilmiş olabilir
        if not sip.isdeleted(le):
            le.setText(kayit["code"] if col == self.kod_kolonu else kayit["name"])
            self.commitData.emit(le)
            self.closeEditor.emit(le, QAbstractItemDelegate.EndEditHint.NoHint)
        grid = self.parent()
        if getattr(grid, "_enter_nav", False):
            grid.setCurrentCell(row, col)
            QTimer.singleShot(0, lambda: grid.navigate(1))

    def _liste_ac(self, le, row: int, col: int) -> None:
        """Büyüteç: tam seçim listesi (yazılan metinle aranmış olarak); seçilirse satıra yazılır."""
        ilk = le.text().strip()
        kayit = self._liste(ilk)
        if kayit is not None:
            self._secildi(le, row, col, kayit)
