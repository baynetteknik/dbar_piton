"""TOYA ERP - EntryTableView: veri girişi (fiş kalemleri) için `FilterableTableView`'in tablo motoru.

Liste ekranlarının ve belge kalemlerinin kullandığı standart grid (`FilterableTableView`, model/görünüm tabanlı) üzerinde, fiş satır
girişinin ihtiyaç duyduğu davranışları verir: hücre-tabanlı erişim (`item`, `setItem`, `insertRow`, `setCurrentCell`… — QTableWidget'a
benzer kısa bir yüzey, alt sınıfların kodu bozulmasın diye), Enter/Tab ile hücreden hücreye gezinme, son satırı aşınca yeni satır isteme ve
açık editörü kaydetme. Görünüm (başlık, satır rengi, sütun menüsü, kayıtlı profiller) `FilterableTableView`'dan gelir; böylece kasa/cari/stok fişi
ile teklif kalem gridi aynı bileşeni paylaşır."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import QAbstractItemDelegate, QAbstractItemView

from src.desktop.ui.components.filterable_table import _ModelAwareTableView


class EntryTableView(_ModelAwareTableView):
    row_append_requested = pyqtSignal()            # klavye gezinmesi son satırı aştığında (yeni satır iste)
    cellDoubleClicked = pyqtSignal(int, int)
    currentCellChanged = pyqtSignal(int, int, int, int)
    itemChanged = pyqtSignal(object)               # QStandardItem

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        self._model.itemChanged.connect(lambda it: self.itemChanged.emit(it))
        self.doubleClicked.connect(lambda i: self.cellDoubleClicked.emit(i.row(), i.column()))
        self.selectionModel().currentChanged.connect(
            lambda cur, prev: self.currentCellChanged.emit(cur.row(), cur.column(), prev.row(), prev.column()))
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.context_actions_provider = None
        self._enter_nav = False
        self.nav_skip_columns: set[int] = set()
        self._nav_suspended = False
        self._nav_deferred: int | None = None

    # ---- QTableWidget benzeri yüzey -------------------------------------------------
    @property
    def effective_row_height(self) -> int:
        try:
            from src.desktop.managers.theme_manager import ThemeManager
            return ThemeManager().row_height
        except Exception:  # noqa: BLE001
            return 26

    def set_columns(self, titles: list[str], tooltips: list[str | None] | None = None) -> None:
        self._model.setColumnCount(len(titles))
        self._model.setHorizontalHeaderLabels(titles)
        for i, tip in enumerate(tooltips or []):
            if tip:
                self._model.setHeaderData(i, Qt.Orientation.Horizontal, tip, Qt.ItemDataRole.ToolTipRole)

    def rowCount(self) -> int:  # noqa: N802
        return self._model.rowCount()

    def columnCount(self) -> int:  # noqa: N802
        return self._model.columnCount()

    def insertRow(self, row: int) -> None:  # noqa: N802
        self._model.insertRow(row)

    def removeRow(self, row: int) -> None:  # noqa: N802
        self._model.removeRow(row)

    def setRowCount(self, n: int) -> None:  # noqa: N802
        self._model.setRowCount(n)

    def item(self, row: int, col: int) -> QStandardItem | None:
        return self._model.item(row, col)

    def setItem(self, row: int, col: int, item: QStandardItem) -> None:  # noqa: N802
        self._model.setItem(row, col, item)

    def currentRow(self) -> int:  # noqa: N802
        i = self.currentIndex()
        return i.row() if i.isValid() else -1

    def currentColumn(self) -> int:  # noqa: N802
        i = self.currentIndex()
        return i.column() if i.isValid() else -1

    def currentItem(self) -> QStandardItem | None:  # noqa: N802
        i = self.currentIndex()
        return self._model.itemFromIndex(i) if i.isValid() else None

    def setCurrentCell(self, row: int, col: int) -> None:  # noqa: N802
        if 0 <= row < self.rowCount() and 0 <= col < self.columnCount():
            self.setCurrentIndex(self._model.index(row, col))

    def editItem(self, item: QStandardItem | None) -> None:  # noqa: N802
        if item is not None:
            self.edit(item.index())

    # ---- klavye gezinmesi -------------------------------------------------------------
    def enable_enter_navigation(self, skip_columns=()) -> None:
        """Enter/Tab: düzenlemeyi kaydedip sağdaki sonraki düzenlenebilir hücreye geçer, satır sonunda alt satırın başına iner; son
        satırın sonunda `row_append_requested` ile yeni satır ister. Shift+Tab geri gider. `skip_columns` klavye akışında atlanan
        (yine de tıklayarak düzenlenebilen) sütunlardır. Ctrl+Tab grid'den çıkar. (Editör tarafı `NavDelegate`'tedir.)"""
        self._enter_nav = True
        self.nav_skip_columns = set(skip_columns)

    def _nav_editable(self, r: int, c: int) -> bool:
        it = self.item(r, c)
        return bool(it and it.flags() & Qt.ItemFlag.ItemIsEditable and not self.isColumnHidden(c) and c not in self.nav_skip_columns)

    def commit_editor(self) -> None:
        """Açık hücre editörü varsa değeri hücreye yazıp kapatır (Kaydet gibi düğmelerden önce çağrılır)."""
        ed = self.indexWidget(self.currentIndex())
        if ed is not None and self.state() == QAbstractItemView.State.EditingState:
            onayla = getattr(ed, "commit_expression", None)
            if onayla is not None:
                onayla()
            self.commitData(ed)
            self.closeEditor(ed, QAbstractItemDelegate.EndEditHint.NoHint)

    def suspend_navigation(self) -> None:
        """Bir açılır pencere açılacakken klavye akışını bekletir; `resume_navigation` sürdürür."""
        self._nav_suspended = True
        self._nav_deferred = None

    def resume_navigation(self) -> None:
        self._nav_suspended = False
        step, self._nav_deferred = self._nav_deferred, None
        if step:
            self.navigate(step)

    def focusInEvent(self, event) -> None:  # noqa: N802
        """Tab ile grid'e girildiğinde ilk düzenlenebilir hücre düzenlemeye açılır (başlıktan kalemlere geçiş)."""
        super().focusInEvent(event)
        if self._enter_nav and event.reason() == Qt.FocusReason.TabFocusReason and self.state() != QAbstractItemView.State.EditingState:
            QTimer.singleShot(0, self.focus_first_cell)

    def focus_first_cell(self) -> None:
        header = self.horizontalHeader()
        for r in range(self.rowCount()):
            for v in range(self.columnCount()):
                c = header.logicalIndex(v)
                if self._nav_editable(r, c):
                    self.setCurrentCell(r, c)
                    self.editItem(self.item(r, c))
                    return

    def navigate(self, step: int = 1) -> None:
        """Bir sonraki (step=1) ya da önceki (step=-1) düzenlenebilir hücreye geçip düzenlemeyi başlatır (görsel sütun sırasına göre)."""
        if self._nav_suspended:
            self._nav_deferred = step
            return
        header = self.horizontalHeader()
        order = [c for c in (header.logicalIndex(v) for v in range(self.columnCount())) if not self.isColumnHidden(c)]
        r, c = self.currentRow(), self.currentColumn()
        if not order or r < 0 or c not in order:
            return
        pos = order.index(c)
        for _guard in range(self.rowCount() * len(order) + len(order) + 2):
            pos += step
            if pos >= len(order):
                pos, r = 0, r + 1
                if r >= self.rowCount():
                    self.row_append_requested.emit()
                    if r >= self.rowCount():
                        return
            elif pos < 0:
                pos, r = len(order) - 1, r - 1
                if r < 0:
                    return
            if self._nav_editable(r, order[pos]):
                self.setCurrentCell(r, order[pos])
                self.editItem(self.item(r, order[pos]))
                return

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._enter_nav and self.state() != QAbstractItemView.State.EditingState:
            key, mods = event.key(), event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                it = self.currentItem()
                if it is not None and self._nav_editable(self.currentRow(), self.currentColumn()):
                    self.editItem(it)
                else:
                    self.navigate(1)
                return
            if key == Qt.Key.Key_Tab and not mods & Qt.KeyboardModifier.ControlModifier:
                self.navigate(1)
                return
            if key == Qt.Key.Key_Backtab and not mods & Qt.KeyboardModifier.ControlModifier:
                self.navigate(-1)
                return
        super().keyPressEvent(event)


def standart_grid(profile_key: str, kolonlar: list[tuple[str, str]], *, tam_adlar: dict[str, str] | None = None):
    """Standart gridi (`FilterableTableView`, entry modu + `EntryTableView`) hazır kurar; küçük tablolar (özet, diyalog listesi) için.

    `kolonlar`: [(anahtar, başlık), ...] — anahtar profilde sütunu tanımlar, KOD İÇİNDE DEĞİŞTİRME (kayıtlı profiller ona bağlıdır).
    Döner: `FilterableTableView` (`.table_view` = `EntryTableView`: `insertRow/item/setItem/rowCount/setRowCount/currentRow/
    cellDoubleClicked…`; hücreler `QStandardItem`). Salt okunur tablo için hücrelere `Qt.ItemFlag.ItemIsEnabled | ItemIsSelectable` verin."""
    from src.desktop.ui.components.filterable_table import FilterableTableView

    tam_adlar = tam_adlar or {}
    headers = {i: (tam_adlar.get(k, b), k) for i, (k, b) in enumerate(kolonlar)}
    g = FilterableTableView(headers_dict=headers, profile_key=profile_key, mode="entry", table_view_class=EntryTableView)
    g.table_view.set_columns([b for _k, b in kolonlar], [tam_adlar.get(k) for k, _b in kolonlar])
    return g
