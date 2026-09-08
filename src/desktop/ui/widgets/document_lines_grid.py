"""
TOYA ERP - DocumentLinesGrid

Belge (Teklif / Sipariş / İrsaliye / Fatura) detay ekranlarındaki "kalemler"
alanı. Liste ekranlarıyla aynı grid çekirdeğini (FilterableTableView) kullanır,
sadece "entry" modunda: kolon-filtre satırı yok, sıralama kapalı, hücreler
düzenlenebilir. Kolon profilleri, seçim kutusu ve koşullu renklendirme liste
ekranlarındakiyle birebir aynı çalışır.

Canlı hesap: Net Tutar = Miktar × Birim Fiyat × (1 - İsk%/100).
Toplamlar `totals_changed` sinyaliyle dışarı verilir (ToplamWidget'e bağlanır).
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QEvent, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QKeySequence,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.ui.components.current_row_highlighter import CurrentRowHighlighter
from src.desktop.ui.components.filterable_table import FilterableTableView

logger = logging.getLogger(__name__)

# Kolon indeksleri
COL_SELECT = 0
COL_SEQ = 1
COL_TUR = 2
COL_KOD = 3
COL_BARKOD = 4
COL_ACIKLAMA = 5
COL_MIKTAR = 6
COL_BIRIM = 7
COL_BFIYAT = 8
COL_ISK = 9
COL_KDV = 10
COL_NET = 11

HEADERS = {
    COL_SELECT: ("☑", "select"),
    COL_SEQ: ("Sıra", "seq"),
    COL_TUR: ("Türü", "tur"),
    COL_KOD: ("Stok Kodu", "kod"),
    COL_BARKOD: ("Barkod", "barkod"),
    COL_ACIKLAMA: ("Açıklama / Ürün", "aciklama"),
    COL_MIKTAR: ("Miktar", "miktar"),
    COL_BIRIM: ("Birim", "birim"),
    COL_BFIYAT: ("Birim Fiyat", "birim_fiyat"),
    COL_ISK: ("İsk %", "iskonto_yuzde"),
    COL_KDV: ("KDV %", "kdv_yuzde"),
    COL_NET: ("Net Tutar", "net_tutar"),
}

_READONLY_COLS = {COL_SEQ, COL_NET}
_NUMERIC_COLS = {COL_MIKTAR, COL_BFIYAT, COL_ISK, COL_KDV}
_RECALC_COLS = {COL_MIKTAR, COL_BFIYAT, COL_ISK, COL_KDV}
_STOK_ARAMA_COLS = {COL_KOD, COL_ACIKLAMA}

BIRIMLER = ["Adet", "Kg", "Lt", "Mt", "M2", "M3", "Paket", "Kutu", "Koli", "Saat", "Gün"]
KDV_ORANLARI = ["0", "1", "10", "20"]

#: Katalog dışı kalemler için "serbest" tür etiketi. Bu türdeki satırlarda stok
#: kartı açma sorusu hiç sorulmaz.
TUR_SERBEST = "Serbest Ürün"
TUR_SECENEKLERI = ["Malzeme", "Hizmet", TUR_SERBEST]
#: Eski kayıtlarla / şablonlarla geri uyum (önceki etiket "Serbest Giriş"ti).
SERBEST_TUR_ETIKETLERI = {TUR_SERBEST, "Serbest Giriş", "Serbest Kalem"}
_STOGA_EKLE_ROLE = Qt.ItemDataRole.UserRole + 7


def parse_num(text) -> float:
    """Türkçe biçimli ('1.234,56') veya düz sayıyı float'a çevirir."""
    if text is None:
        return 0.0
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text).strip()
    if not s:
        return 0.0
    for ch in ("₺", "$", "€", "£", " "):
        s = s.replace(ch, "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def fmt_num(value: float, decimals: int = 2) -> str:
    """Float'ı Türkçe biçime çevirir ('1.234,56')."""
    try:
        return (
            f"{value:,.{decimals}f}"
            .replace(",", "X").replace(".", ",").replace("X", ".")
        )
    except (ValueError, TypeError):
        return "0,00"


class _LookupDelegate(QStyledItemDelegate):
    """Hücrenin sağ kenarında tıklanabilir 🔍 gösterir; stok rehberini açar."""

    def __init__(self, on_lookup, parent=None):
        super().__init__(parent)
        self.on_lookup = on_lookup

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        r = option.rect
        painter.save()
        painter.drawText(
            QRect(r.right() - 18, r.top(), 16, r.height()),
            Qt.AlignmentFlag.AlignCenter, "🔍",
        )
        painter.restore()

    def editorEvent(self, event, model, option, index):  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonRelease and event.pos().x() >= option.rect.right() - 20:
            self.on_lookup(index.row())
            return True
        return super().editorEvent(event, model, option, index)


class _ComboDelegate(QStyledItemDelegate):
    """Belirli kolonlar için açılır liste hücre editörü (birim, KDV%)."""

    def __init__(self, options: list[str], editable: bool = True, parent=None):
        super().__init__(parent)
        self.options = options
        self.editable = editable

    def createEditor(self, parent, option, index):  # noqa: N802
        cb = QComboBox(parent)
        cb.setEditable(self.editable)
        cb.addItems(self.options)
        return cb

    def setEditorData(self, editor, index):  # noqa: N802
        val = index.data(Qt.ItemDataRole.EditRole) or ""
        i = editor.findText(str(val))
        if i >= 0:
            editor.setCurrentIndex(i)
        else:
            editor.setCurrentText(str(val))

    def setModelData(self, editor, model, index):  # noqa: N802
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)


class StokAramaDialog(QDialog):
    """Basit stok seçim listesi (F10)."""

    def __init__(self, products: list[dict], parent=None):
        super().__init__(parent)
        self.products = products or []
        self.selected: dict | None = None
        self.setWindowTitle("📦 Stok / Hizmet Seç")
        self.setMinimumSize(720, 460)
        lyt = QVBoxLayout(self)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Kod, ad veya barkod ile ara…")
        self.txt_search.textChanged.connect(self._filter)
        lyt.addWidget(self.txt_search)
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Kod", "Barkod", "Ad", "Birim", "Fiyat"])
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.doubleClicked.connect(self._accept_row)
        lyt.addWidget(self.tbl, 1)
        row = QHBoxLayout()
        row.addStretch()
        btn_ok = QPushButton("✅ Seç")
        btn_ok.clicked.connect(self._accept_row)
        btn_cancel = QPushButton("Vazgeç")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        row.addWidget(btn_ok)
        lyt.addLayout(row)
        self._fill(self.products)

    def _fill(self, items: list[dict]):
        self.tbl.setRowCount(0)
        for p in items:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            for c, key in enumerate(("code", "barcode", "name", "unit", "price")):
                self.tbl.setItem(r, c, QTableWidgetItem(str(p.get(key, ""))))

    def _filter(self, text: str):
        t = text.strip().lower()
        if not t:
            self._fill(self.products)
            return
        self._fill([
            p for p in self.products
            if t in str(p.get("code", "")).lower()
            or t in str(p.get("name", "")).lower()
            or t in str(p.get("barcode", "")).lower()
        ])

    def _accept_row(self, *_):
        r = self.tbl.currentRow()
        if r < 0:
            return
        code = self.tbl.item(r, 0).text() if self.tbl.item(r, 0) else ""
        self.selected = next(
            (p for p in self.products if str(p.get("code", "")) == code), None,
        )
        self.accept()


class DocumentLinesGrid(QWidget):
    """Belge kalemleri giriş grid'i (entry modunda FilterableTableView tabanlı)."""

    totals_changed = pyqtSignal(dict)

    def __init__(self, profile_key: str = "belge_kalemleri", parent=None):
        super().__init__(parent)
        self.profile_key = profile_key
        self._recalc_guard = False
        self._doviz_sembol = "₺"
        self._doviz_kur = 1.0
        self._products: list[dict] = []
        #: Opsiyonel: sağ-tık menüsüne belge düzeyi eylem ekleyen callable(menu)
        self.document_actions_provider = None
        self._init_ui()

    # ------------------------------------------------------------------
    def _init_ui(self):
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(4)

        # İnce üst şerit: sadece "Kartlara da kaydet" + kalem sayacı
        bar = QHBoxLayout()
        bar.setContentsMargins(2, 0, 2, 0)
        bar.setSpacing(6)
        _info_full = (
            "Türü 'Malzeme'/'Hizmet' iken katalogda olmayan kod/ad yazıp çıkınca "
            "stok kartı açmak istediğiniz sorulur. 'Hayır' derseniz satır otomatik "
            f"'{TUR_SERBEST}' türüne geçer ve bir daha sorulmaz."
        )
        info = QLabel(
            "ℹ️ Katalogda olmayan Malzeme/Hizmet kodu girince stok kartı açma sorulur.",
        )
        info.setStyleSheet("font-size:10px;color:#94a3b8;")
        # DİKKAT: setWordWrap(True) QLabel'a heightForWidth kazandırır; bu da üst
        # QVBoxLayout'u (kalem gridi + alt panel) hatalı hfw dağıtım moduna sokup
        # pencere kısaldığında Toplam widget'ının alt satırlarını kırpıyordu.
        # Tek satır + tooltip ile aynı bilgi, layout bozulmadan verilir.
        info.setWordWrap(False)
        info.setToolTip(_info_full)
        bar.addWidget(info, 1)
        bar.addStretch()
        self.lbl_count = QLabel("0 kalem")
        self.lbl_count.setStyleSheet("font-size:10px;font-weight:600;color:#64748b;")
        bar.addWidget(self.lbl_count)
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
        self.model.itemChanged.connect(self._on_item_changed)

        self.grid.table_view.setItemDelegateForColumn(
            COL_TUR, _ComboDelegate(TUR_SECENEKLERI, editable=False, parent=self),
        )
        self.grid.table_view.setItemDelegateForColumn(
            COL_BIRIM, _ComboDelegate(BIRIMLER, editable=True, parent=self),
        )
        self.grid.table_view.setItemDelegateForColumn(
            COL_KDV, _ComboDelegate(KDV_ORANLARI, editable=True, parent=self),
        )
        # Stok Kodu ve Açıklama hücrelerinde tıklanabilir 🔍 (cari gibi)
        lookup_del = _LookupDelegate(self._lookup_for_row, parent=self)
        self.grid.table_view.setItemDelegateForColumn(COL_KOD, lookup_del)
        self.grid.table_view.setItemDelegateForColumn(COL_ACIKLAMA, lookup_del)

        # Üzerinde çalışılan satır tüm genişliğince renklenir (yeniden kullanılabilir
        # bileşen; koşullu renklendirme delegate'iyle çakışmaz).
        self.row_highlighter = CurrentRowHighlighter(
            self.grid.table_view, bg="#bfdbfe", fg="#0f172a",
        ).apply()

        lyt.addWidget(self.grid, 1)

        # Satır işlemleri: sağ-tık menüsü (butonlar yer kaplamasın)
        self.grid.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.table_view.customContextMenuRequested.connect(self._show_context_menu)

        QShortcut(QKeySequence("Ins"), self.grid.table_view,
                  activated=lambda: self.add_row(focus=True))
        QShortcut(QKeySequence("Del"), self.grid.table_view,
                  activated=self.remove_checked_rows)
        QShortcut(QKeySequence("F10"), self.grid.table_view,
                  activated=self.open_stock_lookup)

    def _lookup_for_row(self, row: int):
        self.grid.table_view.setCurrentIndex(self.model.index(row, COL_KOD))
        prefill = self._cell(row, COL_KOD) or self._cell(row, COL_ACIKLAMA)
        self.open_stock_lookup(prefill=prefill)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        a_add = QAction("➕ Satır Ekle (Ins)", self)
        a_add.triggered.connect(lambda: self.add_row(focus=True))
        a_lookup = QAction("🔍 Stok Seç (F10)", self)
        a_lookup.triggered.connect(self.open_stock_lookup)
        a_del = QAction("🗑️ Seçili Satırları Sil (Del)", self)
        a_del.triggered.connect(self.remove_checked_rows)
        a_up = QAction("⬆️ Satırı Yukarı (Alt+↑)", self)
        a_up.triggered.connect(self.move_selected_up)
        a_down = QAction("⬇️ Satırı Aşağı (Alt+↓)", self)
        a_down.triggered.connect(self.move_selected_down)
        a_card = QAction("📥 Bu satırı stok kartına ekle", self)
        a_card.triggered.connect(lambda: self.mark_row_for_stock_card())
        for a in (a_add, a_lookup, a_del):
            menu.addAction(a)
        menu.addSeparator()
        menu.addAction(a_up)
        menu.addAction(a_down)
        menu.addSeparator()
        menu.addAction(a_card)
        if callable(self.document_actions_provider):
            menu.addSeparator()
            self.document_actions_provider(menu)
        menu.addSeparator()
        self.grid.add_column_actions_to_menu(menu)
        menu.exec(self.grid.table_view.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------
    def set_products(self, products: list[dict]):
        self._products = products or []

    # ------------------------------------------------------------------
    def add_row(self, data: dict | None = None, focus: bool = False):
        data = data or {}
        self._recalc_guard = True
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
                    COL_TUR: "Malzeme",
                    COL_MIKTAR: "1", COL_ISK: "0", COL_KDV: "20",
                    COL_BFIYAT: "0", COL_BIRIM: "Adet",
                }.get(col, "")
                it = QStandardItem(str(data.get(field, default)))
                it.setEditable(col not in _READONLY_COLS)
                if col in _NUMERIC_COLS or col == COL_NET:
                    it.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    )
            row.append(it)
        self.model.appendRow(row)
        self._recalc_guard = False
        self._renumber()
        self._recalc_row(self.model.rowCount() - 1)
        self._emit_totals()
        if focus:
            idx = self.model.index(self.model.rowCount() - 1, COL_KOD)
            self.grid.table_view.setCurrentIndex(idx)
            self.grid.table_view.edit(idx)

    def remove_checked_rows(self):
        rows = sorted(self.grid.get_checked_rows(), reverse=True)
        if not rows:
            sel = self.grid.table_view.selectionModel().selectedRows()
            rows = sorted((i.row() for i in sel), reverse=True)
        for r in rows:
            self.model.removeRow(r)
        self._renumber()
        self._emit_totals()

    def clear_rows(self):
        self.model.removeRows(0, self.model.rowCount())
        self._emit_totals()

    def _current_row(self) -> int:
        idx = self.grid.table_view.currentIndex()
        if idx.isValid():
            return idx.row()
        sel = self.grid.table_view.selectionModel().selectedRows()
        return sel[0].row() if sel else -1

    def move_selected_up(self):
        r = self._current_row()
        if r > 0:
            self._recalc_guard = True
            try:
                row_items = self.model.takeRow(r)
                self.model.insertRow(r - 1, row_items)
            finally:
                self._recalc_guard = False
            self._renumber()
            self.grid.table_view.selectRow(r - 1)
            self._emit_totals()

    def move_selected_down(self):
        r = self._current_row()
        if 0 <= r < self.model.rowCount() - 1:
            self._recalc_guard = True
            try:
                row_items = self.model.takeRow(r)
                self.model.insertRow(r + 1, row_items)
            finally:
                self._recalc_guard = False
            self._renumber()
            self.grid.table_view.selectRow(r + 1)
            self._emit_totals()

    def load_lines(self, lines: list[dict]):
        self.clear_rows()
        for ln in lines:
            self.add_row(ln)

    def get_lines(self) -> list[dict]:
        out = []
        for r in range(self.model.rowCount()):
            rec = {}
            for col in sorted(HEADERS):
                if col == COL_SELECT:
                    continue
                field = HEADERS[col][1]
                it = self.model.item(r, col)
                rec[field] = it.text() if it else ""
            rec["_num"] = {
                "miktar": parse_num(rec.get("miktar")),
                "birim_fiyat": parse_num(rec.get("birim_fiyat")),
                "iskonto_yuzde": parse_num(rec.get("iskonto_yuzde")),
                "kdv_yuzde": parse_num(rec.get("kdv_yuzde")),
                "net_tutar": parse_num(rec.get("net_tutar")),
            }
            rec["stoga_ekle"] = self._get_stoga_ekle(r)
            out.append(rec)
        return out

    # ------------------------------------------------------------------
    def open_stock_lookup(self, prefill: str = ""):
        dlg = StokAramaDialog(self._products, parent=self)
        if prefill:
            dlg.txt_search.setText(prefill)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
            self._apply_product_to_current_row(dlg.selected)

    def _apply_product_to_current_row(self, p: dict):
        row = self.grid.table_view.currentIndex().row()
        if row < 0:
            self.add_row(focus=False)
            row = self.model.rowCount() - 1
        self._recalc_guard = True
        try:
            self._set_cell(row, COL_KOD, p.get("code", ""))
            self._set_cell(row, COL_BARKOD, p.get("barcode", ""))
            self._set_cell(row, COL_ACIKLAMA, p.get("name", ""))
            self._set_cell(row, COL_BIRIM, p.get("unit", "Adet"))
            if p.get("price"):
                self._set_cell(row, COL_BFIYAT, fmt_num(parse_num(p.get("price"))))
            if p.get("vat_rate"):
                self._set_cell(row, COL_KDV, str(p.get("vat_rate")))
        finally:
            self._recalc_guard = False
        self._recalc_row(row)
        self._emit_totals()

    # ------------------------------------------------------------------
    def set_row_highlight_color(self, bg: str, fg: str | None = None):
        """Seçili kalem satırının vurgu rengini değiştirir."""
        self.row_highlighter.set_color(bg, fg)

    # ------------------------------------------------------------------
    def set_currency(self, sembol: str, kur: float):
        self._doviz_sembol = sembol or "₺"
        self._doviz_kur = kur or 1.0
        self._emit_totals()

    # ------------------------------------------------------------------
    def _on_item_changed(self, item: QStandardItem):
        if self._recalc_guard:
            return
        if item.column() in _RECALC_COLS:
            self._recalc_guard = True
            try:
                self._recalc_row(item.row())
            finally:
                self._recalc_guard = False
            self._emit_totals()
        elif item.column() in _STOK_ARAMA_COLS:
            self._maybe_offer_new_card(item.row())

    def _find_product(self, text: str) -> dict | None:
        t = (text or "").strip().lower()
        if not t:
            return None
        for p in self._products:
            if t in (
                str(p.get("code", "")).lower(),
                str(p.get("barcode", "")).lower(),
                str(p.get("name", "")).lower(),
            ):
                return p
        return None

    def _maybe_offer_new_card(self, row: int):
        """Kod/ad yazıldı, katalogda yok ve tür serbest değilse kart açmayı sor."""
        if row < 0 or row >= self.model.rowCount():
            return
        tur = self._cell(row, COL_TUR)
        if tur in SERBEST_TUR_ETIKETLERI:
            self._set_stoga_ekle(row, False)
            return
        kod = self._cell(row, COL_KOD).strip()
        ad = self._cell(row, COL_ACIKLAMA).strip()
        if not (kod or ad):
            return
        if self._find_product(kod) or self._find_product(ad):
            self._set_stoga_ekle(row, False)
            return
        if self._get_stoga_ekle(row):
            return  # zaten sorulmuş ve onaylanmış
        etiket = kod or ad
        cevap = QMessageBox.question(
            self, "Stok Kartı Bulunamadı",
            f"'{etiket}' stok kartlarında bulunamadı.\n\n"
            "Bu kalem için yeni bir stok kartı oluşturulsun mu?\n"
            f"(Hayır → satırın türü '{TUR_SERBEST}' olur, belge yine kaydedilir.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if cevap == QMessageBox.StandardButton.Yes:
            self._set_stoga_ekle(row, True)
        else:
            # Kullanıcı kart istemedi: satırı otomatik serbest ürüne çevir,
            # böylece aynı satır için soru tekrar sorulmaz.
            self._set_stoga_ekle(row, False)
            self._set_tur_silently(row, TUR_SERBEST)

    def _set_tur_silently(self, row: int, tur: str):
        """COL_TUR'u itemChanged kaskadı tetiklemeden değiştirir."""
        prev = self._recalc_guard
        self._recalc_guard = True
        try:
            self._set_cell(row, COL_TUR, tur)
        finally:
            self._recalc_guard = prev

    # ---- Boş satır yönetimi (kayıt öncesi temizlik) -------------------
    def is_row_empty(self, row: int) -> bool:
        """Satırda stok kodu ve açıklama yoksa 'boş' sayılır."""
        return not self._cell(row, COL_KOD).strip() and not self._cell(row, COL_ACIKLAMA).strip()

    def empty_row_count(self) -> int:
        return sum(1 for r in range(self.model.rowCount()) if self.is_row_empty(r))

    def remove_empty_rows(self) -> int:
        """Boş kalem satırlarını siler; silinen satır sayısını döndürür."""
        rows = [r for r in range(self.model.rowCount()) if self.is_row_empty(r)]
        for r in reversed(rows):
            self.model.removeRow(r)
        if rows:
            self._renumber()
            self._emit_totals()
        return len(rows)

    def _set_stoga_ekle(self, row: int, value: bool):
        it = self.model.item(row, COL_KOD)
        if it is None:
            it = QStandardItem()
            self.model.setItem(row, COL_KOD, it)
        prev = self._recalc_guard
        self._recalc_guard = True  # itemChanged kaskadını engelle
        try:
            it.setData(bool(value), _STOGA_EKLE_ROLE)
        finally:
            self._recalc_guard = prev

    def _get_stoga_ekle(self, row: int) -> bool:
        it = self.model.item(row, COL_KOD)
        return bool(it and it.data(_STOGA_EKLE_ROLE))

    def mark_row_for_stock_card(self, row: int | None = None):
        """Sağ-tık: seçili satırı stok kartına eklenecek olarak işaretle."""
        if row is None:
            row = self._current_row()
        if row >= 0:
            self._set_stoga_ekle(row, True)
            self.lbl_count.setText(f"{self.model.rowCount()} kalem  ·  satır {row + 1} → stok kartı")

    def _recalc_row(self, row: int):
        if row < 0 or row >= self.model.rowCount():
            return
        miktar = parse_num(self._cell(row, COL_MIKTAR))
        fiyat = parse_num(self._cell(row, COL_BFIYAT))
        isk = parse_num(self._cell(row, COL_ISK))
        net = miktar * fiyat * (1 - isk / 100.0)
        net_item = self.model.item(row, COL_NET)
        if net_item is None:
            net_item = QStandardItem()
            net_item.setEditable(False)
            self.model.setItem(row, COL_NET, net_item)
        net_item.setText(fmt_num(net))

    def _row_values(self, row: int) -> tuple[float, float, float, float, float]:
        miktar = parse_num(self._cell(row, COL_MIKTAR))
        fiyat = parse_num(self._cell(row, COL_BFIYAT))
        isk = parse_num(self._cell(row, COL_ISK))
        kdv_yuzde = parse_num(self._cell(row, COL_KDV))
        brut = miktar * fiyat
        satir_iskonto = brut * (isk / 100.0)
        net = brut - satir_iskonto
        kdv = net * (kdv_yuzde / 100.0)
        return brut, satir_iskonto, net, kdv, kdv_yuzde

    def _emit_totals(self):
        ara_toplam = iskonto = matrah = kdv_toplam = 0.0
        kdv_dagilim: dict[float, dict[str, float]] = {}
        for r in range(self.model.rowCount()):
            brut, s_isk, net, kdv, oran = self._row_values(r)
            ara_toplam += brut
            iskonto += s_isk
            matrah += net
            kdv_toplam += kdv
            d = kdv_dagilim.setdefault(oran, {"matrah": 0.0, "kdv": 0.0})
            d["matrah"] += net
            d["kdv"] += kdv
        genel = matrah + kdv_toplam
        self.lbl_count.setText(f"{self.model.rowCount()} kalem")
        self.totals_changed.emit({
            "ara_toplam": ara_toplam,
            "iskonto": iskonto,
            "kdv_matrahi": matrah,
            "kdv_toplam": kdv_toplam,
            "genel_toplam": genel,
            "satir_sayisi": self.model.rowCount(),
            "kdv_dagilim": kdv_dagilim,
            "doviz_sembol": self._doviz_sembol,
            "doviz_kur": self._doviz_kur,
        })

    def _renumber(self):
        self._recalc_guard = True
        try:
            for r in range(self.model.rowCount()):
                it = self.model.item(r, COL_SEQ)
                if it is None:
                    it = QStandardItem()
                    it.setEditable(False)
                    self.model.setItem(r, COL_SEQ, it)
                it.setText(str(r + 1))
        finally:
            self._recalc_guard = False

    def _cell(self, row: int, col: int) -> str:
        it = self.model.item(row, col)
        return it.text() if it else ""

    def _set_cell(self, row: int, col: int, value):
        it = self.model.item(row, col)
        if it is None:
            it = QStandardItem()
            self.model.setItem(row, col, it)
        it.setText(str(value))


if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = DocumentLinesGrid()
    w.set_products([
        {"code": "STK-001", "barcode": "8690001", "name": "4K Güvenlik Kamerası", "unit": "Adet", "price": 150, "vat_rate": 20},
        {"code": "STK-002", "barcode": "8690002", "name": "16 Kanal NVR", "unit": "Adet", "price": 650, "vat_rate": 20},
    ])
    w.resize(1000, 400)
    w.add_row({"kod": "STK-001", "aciklama": "4K Güvenlik Kamerası", "miktar": "8", "birim_fiyat": "150", "iskonto_yuzde": "10", "kdv_yuzde": "20"})
    w.totals_changed.connect(lambda d: print("TOTALS:", {k: v for k, v in d.items() if k != "kdv_dagilim"}))
    w._emit_totals()
    w.show()
    sys.exit(app.exec())
