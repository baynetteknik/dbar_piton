"""
TOYA ERP - DocumentExpensesGrid

Belge detayında "Alt İskontolar & Masraflar" alanı. Kalemler grid'iyle aynı
çekirdeği (FilterableTableView, entry modu) kullanır. Belge ara toplamı üzerine
uygulanan genel indirimler ve masraflar (navlun, montaj, vb.) burada girilir.

`expenses_changed` sinyali net indirim, net masraf, bu satırların doğurduğu net
KDV farkını ve oran bazlı KDV dağılımını yayar; DocumentDetailScreen bunları
ToplamWidget'e ve KDV dağılımı tablosuna aktarır.

Her satırın bir "KDV %" sütunu vardır: boş / 0 = "yapılan iş" (KDV'siz), 20 = "+ KDV".
"Eşitle" hesap şekillerinde bu sütun yok sayılır; satır, toplamı girilen değere
tam olarak eşitler (KDV etkisi 0) ve "Tür" otomatik belirlenir.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from src.desktop.ui.components.current_row_highlighter import CurrentRowHighlighter
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.widgets.document_lines_grid import fmt_num, parse_num

logger = logging.getLogger(__name__)

COL_SELECT = 0
COL_SEQ = 1
COL_TUR = 2
COL_ACIKLAMA = 3
COL_SEKIL = 4
COL_DEGER = 5
COL_KDV = 6
COL_NET = 7

HEADERS = {
    COL_SELECT: ("☑", "select"),
    COL_SEQ: ("Sıra", "seq"),
    COL_TUR: ("Tür", "tur"),
    COL_ACIKLAMA: ("Açıklama", "aciklama"),
    COL_SEKIL: ("Hesap Şekli", "sekil"),
    COL_DEGER: ("Değer", "deger"),
    COL_KDV: ("KDV %", "kdv"),
    COL_NET: ("Net Etki", "net"),
}

TURLER = ["İndirim", "Masraf"]
SEKILLER = [
    "Toplamdan % Düş",
    "Toplamdan Düş",
    "Toplamı Eşitle",
    "G.Toplamdan % Düş",
    "G.Toplamdan Düş",
    "G.Toplamı Eşitle",
]
# KDV oranı: boş/0 = "yapılan iş" (KDV'siz), 20 = "+ KDV"
KDV_ORANLARI = ["", "0", "1", "10", "20"]
DEFAULT_KDV = "20"
_READONLY = {COL_SEQ, COL_NET}


class _ComboDelegate(QStyledItemDelegate):
    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.options = options

    def createEditor(self, parent, option, index):  # noqa: N802
        cb = QComboBox(parent)
        cb.addItems(self.options)
        return cb

    def setEditorData(self, editor, index):  # noqa: N802
        i = editor.findText(str(index.data(Qt.ItemDataRole.EditRole) or ""))
        if i >= 0:
            editor.setCurrentIndex(i)

    def setModelData(self, editor, model, index):  # noqa: N802
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class DocumentExpensesGrid(QWidget):
    """Alt iskonto & masraf giriş grid'i."""

    expenses_changed = pyqtSignal(dict)  # {indirim, masraf, kdv, kdv_dagilim}

    def __init__(self, profile_key: str = "belge_masraflar", parent=None):
        super().__init__(parent)
        self.profile_key = profile_key
        self._base_amount = 0.0
        self._grand_amount = 0.0
        # Bu grid'in en son yaydığı genel toplam katkısı (masraf - indirim + net KDV).
        # 'G.Toplam' satırlarını, grid'in kendi etkisi çıkarılmış "temel genel
        # toplam" üzerinden hesaplamak için kullanılır; böylece geri besleme
        # döngüsü tek adımda yakınsar.
        self._last_contribution = 0.0
        self._guard = False
        self._recalc_depth = 0
        self._init_ui()

    def _init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(4)

        bar = QHBoxLayout()
        bar.setContentsMargins(2, 0, 2, 0)
        info = QLabel("Sağ tık → Satır Ekle / Sil. Yüzde satırları ara toplam üzerinden hesaplanır.")
        info.setStyleSheet("font-size:10px;color:#94a3b8;")
        bar.addWidget(info)
        bar.addStretch()
        self.lbl = QLabel("İndirim: 0,00  ·  Masraf: 0,00")
        self.lbl.setStyleSheet("font-size:10px;font-weight:600;color:#64748b;")
        bar.addWidget(self.lbl)
        lyt.addLayout(bar)

        self.grid = FilterableTableView(
            headers_dict=HEADERS,
            profile_key=self.profile_key,
            select_column=COL_SELECT,
            mode="entry",
        )
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels([HEADERS[c][0] for c in sorted(HEADERS)])
        self.grid.table_view.setModel(self.model)
        self.model.itemChanged.connect(self._on_changed)
        self.grid.table_view.setItemDelegateForColumn(COL_TUR, _ComboDelegate(TURLER, self))
        self.grid.table_view.setItemDelegateForColumn(COL_SEKIL, _ComboDelegate(SEKILLER, self))
        self.grid.table_view.setItemDelegateForColumn(COL_KDV, _ComboDelegate(KDV_ORANLARI, self))
        self.grid.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.table_view.customContextMenuRequested.connect(self._show_context_menu)

        # Seçili satır kalemler gridiyle aynı şekilde tüm genişliğince renklenir.
        self.row_highlighter = CurrentRowHighlighter(
            self.grid.table_view, bg="#bfdbfe", fg="#0f172a",
        ).apply()

        lyt.addWidget(self.grid, 1)

    def set_row_highlight_color(self, bg: str, fg: str | None = None):
        """Seçili masraf satırının vurgu rengini değiştirir."""
        self.row_highlighter.set_color(bg, fg)

    def _show_context_menu(self, pos):
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        a_add = QAction("➕ Satır Ekle", self)
        a_add.triggered.connect(lambda: self.add_row())
        a_del = QAction("🗑️ Seçili Satırları Sil", self)
        a_del.triggered.connect(self.remove_checked_rows)
        menu.addAction(a_add)
        menu.addAction(a_del)
        menu.addSeparator()
        self.grid.add_column_actions_to_menu(menu)
        menu.exec(self.grid.table_view.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    def set_base_amount(self, amount: float):
        """Yüzdesel ('Toplamdan...') hesaplar için belge ara toplamı."""
        self._base_amount = amount or 0.0
        self._recalc_all()

    def set_grand_amount(self, amount: float):
        """'G.Toplamdan...' hesap şekilleri için belge genel toplamı.

        Genel toplam, bu grid'in kendi net etkisinden de etkilendiği için
        (indirim/masraf -> genel toplam -> "G.Toplamdan" satırları -> ...)
        değişmeyen değerde yeniden hesaplamayı atlayarak sonsuz döngüyü önler.
        """
        amount = amount or 0.0
        if abs(amount - self._grand_amount) < 0.005:
            return
        self._grand_amount = amount
        self._recalc_all()

    def add_row(self, data: dict | None = None):
        data = data or {}
        row = []
        for col in sorted(HEADERS):
            if col == COL_SELECT:
                it = QStandardItem("")
                it.setCheckable(True)
                it.setCheckState(Qt.CheckState.Unchecked)
                it.setEditable(False)
            else:
                field = HEADERS[col][1]
                default = {
                    COL_TUR: "İndirim",
                    COL_SEKIL: SEKILLER[0],
                    COL_DEGER: "0",
                    COL_KDV: DEFAULT_KDV,
                }.get(col, "")
                it = QStandardItem(str(data.get(field, default)))
                it.setEditable(col not in _READONLY)
            row.append(it)
        self.model.appendRow(row)
        self._renumber()
        self._recalc_all()

    def remove_checked_rows(self):
        rows = sorted(self.grid.get_checked_rows(), reverse=True)
        if not rows:
            sel = self.grid.table_view.selectionModel().selectedRows()
            rows = sorted((i.row() for i in sel), reverse=True)
        for r in rows:
            self.model.removeRow(r)
        self._renumber()
        self._recalc_all()

    def clear_rows(self):
        self.model.removeRows(0, self.model.rowCount())
        self._recalc_all()

    def _renumber(self):
        prev = self._guard
        self._guard = True
        try:
            for r in range(self.model.rowCount()):
                it = self.model.item(r, COL_SEQ)
                if it is None:
                    it = QStandardItem()
                    it.setEditable(False)
                    self.model.setItem(r, COL_SEQ, it)
                it.setText(str(r + 1))
        finally:
            self._guard = prev

    def load_rows(self, rows: list[dict]):
        self.clear_rows()
        for r in rows:
            self.add_row(r)

    def get_rows(self) -> list[dict]:
        out = []
        for r in range(self.model.rowCount()):
            rec = {}
            for col in sorted(HEADERS):
                if col == COL_SELECT:
                    continue
                it = self.model.item(r, col)
                val = it.text() if it else ""
                if col == COL_KDV and val == "—":
                    val = ""  # Eşitle satırının devre dışı göstergesi kaydedilmez
                rec[HEADERS[col][1]] = val
            out.append(rec)
        return out

    # ------------------------------------------------------------------
    def _on_changed(self, item: QStandardItem):
        if self._guard or item.column() not in (COL_TUR, COL_SEKIL, COL_DEGER, COL_KDV):
            return
        self._recalc_all()

    def _row_calc(
        self, row: int, running_subtotal: float, running_grand: float,
    ) -> tuple[str, float, float, float, bool, bool]:
        """Bir satırın net etkisini, KDV oranını ve KDV tutarını hesaplar.

        `running_subtotal` / `running_grand`: bu satırdan ÖNCEKİ satırların etkisi
        uygulanmış ara toplam / genel toplam (sıralı/kümülatif hesap — "Toplamdan"
        satırın kendi sırasındaki ara toplamı, "G.Toplamdan" ise o sıradaki genel
        toplamı baz alır).

        Dönüş: (tur, net, kdv_orani, kdv_tutari, esitle_mi, kdv_kapali_mi)
        "Eşitle" satırlarında `net`, toplamı girilen değere tam eşitleyecek farktır;
        yön ("Tür") otomatik belirlenir. "Eşitle" ve tüm "G.Toplam" şekilleri
        KDV-dahil bir figürü hedef aldığından satır KDV oranı yok sayılır.
        """
        tur = self._cell(row, COL_TUR) or "İndirim"
        sekil = self._cell(row, COL_SEKIL) or SEKILLER[0]
        deger = parse_num(self._cell(row, COL_DEGER))
        esitle = "Eşitle" in sekil
        genel = "G.Toplam" in sekil
        kdv_off = esitle or genel
        base = running_grand if genel else running_subtotal
        if esitle:
            diff = deger - base
            tur = "Masraf" if diff >= 0 else "İndirim"
            return tur, abs(diff), 0.0, 0.0, True, True
        net = base * (deger / 100.0) if "%" in sekil else deger
        if kdv_off:
            return tur, net, 0.0, 0.0, False, True
        oran = parse_num(self._cell(row, COL_KDV))
        return tur, net, oran, net * (oran / 100.0), False, False

    def _recalc_all(self):
        # 'G.Toplamdan...' satırları genel toplama, genel toplam da bu grid'in
        # net etkisine bağlı olduğundan emit -> set_grand_amount -> _recalc_all
        # geri besleme döngüsü oluşur. G.Toplam satırları grid'in kendi katkısı
        # çıkarılmış "temel genel toplam" üzerinden hesaplandığından döngü birkaç
        # adımda yakınsar; yine de patolojik yapılandırmalara karşı derinlik
        # sınırı sonsuz özyinelemeyi önler.
        if self._recalc_depth >= 12:
            logger.warning("Masraf grid yeniden hesap derinliği sınırına ulaştı; döngü kesildi.")
            return
        self._recalc_depth += 1
        try:
            self._guard = True
            try:
                indirim = masraf = 0.0
                kdv_indirim = kdv_masraf = 0.0
                kdv_dagilim: dict[float, dict[str, float]] = {}
                running = self._base_amount
                # Grid'in kendi etkisi dışlanmış temel genel toplam.
                running_grand = self._grand_amount - self._last_contribution
                for r in range(self.model.rowCount()):
                    tur, net, oran, kdv, esitle, kdv_off = self._row_calc(
                        r, running, running_grand,
                    )
                    delta = -net if tur == "İndirim" else net
                    running += delta
                    running_grand += delta + (kdv if tur == "Masraf" else -kdv)

                    it = self.model.item(r, COL_NET)
                    if it is None:
                        it = QStandardItem()
                        it.setEditable(False)
                        self.model.setItem(r, COL_NET, it)
                    sign = "-" if tur == "İndirim" else "+"
                    it.setText(f"{sign}{fmt_num(net)}")

                    if esitle:
                        # "Eşitle" satırında yön hesaplanır; kullanıcı görsün diye
                        # Tür hücresine yazılır.
                        self._set_cell_text(r, COL_TUR, tur)
                    if kdv_off:
                        self._set_cell_text(r, COL_KDV, "—", editable=False)
                    elif not self._cell_editable(r, COL_KDV):
                        # KDV uygulanan bir şekle geçildiyse sütunu geri aç.
                        self._set_cell_text(r, COL_KDV, DEFAULT_KDV, editable=True)

                    if tur == "İndirim":
                        indirim += net
                        kdv_indirim += kdv
                    else:
                        masraf += net
                        kdv_masraf += kdv
                    if oran:
                        d = kdv_dagilim.setdefault(oran, {"matrah": 0.0, "kdv": 0.0})
                        s = -1.0 if tur == "İndirim" else 1.0
                        d["matrah"] += s * net
                        d["kdv"] += s * kdv
            finally:
                self._guard = False
            net_kdv = kdv_masraf - kdv_indirim
            self._last_contribution = (masraf - indirim) + net_kdv
            self.lbl.setText(
                f"İndirim: {fmt_num(indirim)}  ·  Masraf: {fmt_num(masraf)}"
                f"  ·  KDV: {fmt_num(net_kdv)}",
            )
            self.expenses_changed.emit({
                "indirim": indirim,
                "masraf": masraf,
                "kdv": net_kdv,
                "kdv_dagilim": kdv_dagilim,
            })
        finally:
            self._recalc_depth -= 1

    def _cell(self, row: int, col: int) -> str:
        it = self.model.item(row, col)
        return it.text() if it else ""

    def _cell_editable(self, row: int, col: int) -> bool:
        it = self.model.item(row, col)
        return bool(it.isEditable()) if it else True

    def _set_cell_text(self, row: int, col: int, text: str, editable: bool | None = None):
        """Hücre metnini (ve istenirse düzenlenebilirliğini) `_guard` altında ayarlar."""
        it = self.model.item(row, col)
        if it is None:
            it = QStandardItem()
            self.model.setItem(row, col, it)
        if it.text() != str(text):
            it.setText(str(text))
        if editable is not None and it.isEditable() != editable:
            it.setEditable(editable)


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = DocumentExpensesGrid()
    w.set_base_amount(10000)
    w.set_grand_amount(12000)
    w.add_row({"tur": "İndirim", "aciklama": "Sezon indirimi", "sekil": "Toplamdan % Düş", "deger": "5"})
    w.add_row({"tur": "Masraf", "aciklama": "Navlun (+ KDV)", "sekil": "Toplamdan Düş", "deger": "250", "kdv": "20"})
    w.add_row({"tur": "Masraf", "aciklama": "İşçilik (yapılan iş)", "sekil": "Toplamdan Düş", "deger": "400", "kdv": "0"})
    w.add_row({"aciklama": "Yuvarlama", "sekil": "Toplamı Eşitle", "deger": "10000"})
    w.expenses_changed.connect(lambda d: print("EXPENSES:", d))
    w._recalc_all()
    w.resize(700, 300)
    w.show()
    sys.exit(app.exec())
