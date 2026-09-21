"""TOYA ERP - FisKalemGrid: fiş (belge) satır girişi için ortak, sütun tanımıyla çalışan grid iskeleti.

Cari, stok, kasa ve banka fişleri aynı davranışı paylaşır; her fiş yalnızca sütun listesini (`KOLONLAR`) ve birkaç kancayı
(`hucre_degisti`, `satir_bayraklari`, `bos_mu`, `rows`, `totals`) verir. Ortak davranış:

- standart AppGrid, hücre içi düzenleme; sütunlar sürükle-bırak ile taşınır, görünürlük/genişlik kaydedilir,
- Enter / Tab ile sağa, satır sonunda alt satıra, son satırın sonunda yeni satır,
- sütun tipine göre editör: para (`MoneyEdit`: binlik nokta, kuruş, + - * / hesap makinesi), tarih (takvimli), açılır liste,
- ilk sütun `sn` ise sıra numarası otomatik; tablonun sonunda her zaman boş bir satır,
- satır ekle / sil (sağ tık, Ctrl+Del).

Alt sınıf `lookup_delegate(kolon_key)` ile arama/lookup sütunlarına (cari, ürün, depo) editör verir.
Sinyaller: `totals_changed()`, `satir_secildi(int)` (aktif satır), `message(str)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QTableWidgetItem, QVBoxLayout, QWidget

from src.desktop.core.grid_presets import GRID_PRESETS, register_preset
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.components.grid_delegates import ComboDelegate, DateDelegate, MoneyDelegate
from src.desktop.ui.widgets.money_edit import bicimle, sayiya


@dataclass(frozen=True)
class KolonTanimi:
    """Bir fiş satırı sütununun tanımı.

    tip: text | para | tarih | combo | lookup | readonly. `ondalik` yalnız para içindir. Combo seçenekleri alt sınıfın
    `combo_secenekleri(key)` kancasından gelir. `nav_atla` klavye akışında atlanır (yine de tıklayarak düzenlenir)."""
    key: str
    baslik: str
    oran: float
    hiza: str = "L"
    tip: str = "text"
    tam_ad: str | None = None
    ondalik: int = 2
    nav_atla: bool = False


_HIZA = {"L": Qt.AlignmentFlag.AlignLeft, "R": Qt.AlignmentFlag.AlignRight, "C": Qt.AlignmentFlag.AlignCenter}


def parse_num(text: str) -> float:
    """'1.234,56' / '1234,56' -> float; çözülemezse 0."""
    d = sayiya((text or "").replace(" ", ""))
    return float(d) if d is not None else 0.0


def fmt_num(v: float, dec: int = 2) -> str:
    return bicimle(v, dec)


def parse_date(text: str) -> date | None:
    from datetime import datetime
    for f in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime((text or "").strip(), f).date()
        except ValueError:
            continue
    return None


class FisKalemGrid(QWidget):
    PRESET_ID: str = "dbgrid_fis_kalem"
    PRESET_AD: str = "Fiş Kalemleri"
    KOLONLAR: list[KolonTanimi] = []

    totals_changed = pyqtSignal()
    satir_secildi = pyqtSignal(int)
    message = pyqtSignal(str)

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self._busy = False
        self._tarih = date.today()
        self.idx = {k.key: i for i, k in enumerate(self.KOLONLAR)}
        if self.PRESET_ID not in GRID_PRESETS:
            register_preset(self.PRESET_ID, [k.baslik for k in self.KOLONLAR], [k.oran for k in self.KOLONLAR],
                            [k.hiza for k in self.KOLONLAR], name=self.PRESET_AD)
        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(0, 0, 0, 0)
        self.grid = AppGrid(self.PRESET_ID, editable=True)
        self.grid.setSelectionMode(AppGrid.SelectionMode.ExtendedSelection)
        self.grid.context_actions_provider = self._context_actions
        for i, k in enumerate(self.KOLONLAR):
            if k.tam_ad:
                self.grid.horizontalHeaderItem(i).setToolTip(k.tam_ad)
        if db_session is not None:
            self.grid.enable_layout_persistence(db_session)
        atla = {i for i, k in enumerate(self.KOLONLAR) if k.nav_atla}
        self.grid.enable_enter_navigation(skip_columns=atla)
        self.grid.row_append_requested.connect(self.add_row)
        lyt.addWidget(self.grid, 1)
        for i, k in enumerate(self.KOLONLAR):
            d = self._delegate(k)
            if d is not None:
                self.grid.setItemDelegateForColumn(i, d)
        self.grid.itemChanged.connect(self._on_item_changed)
        self.grid.currentCellChanged.connect(lambda r, _c, _pr, _pc: self.satir_secildi.emit(r))
        QShortcut(QKeySequence("Ctrl+Del"), self.grid, activated=self.secili_satirlari_sil)
        self.add_row()

    # ---- alt sınıf kancaları -------------------------------------------------
    def lookup_delegate(self, key: str):
        """`lookup` tipli sütun için editör (delegate). Varsayılan: düz metin."""
        return None

    def combo_secenekleri(self, key: str) -> list[str]:
        """`combo` tipli sütunun açılır liste seçenekleri."""
        return []

    def hucre_degisti(self, r: int, key: str) -> None:
        """Bir hücre değişti (yeniden girişe karşı `_busy` korumalıdır; hücreleri `set_text` ile yazın)."""

    def satir_bayraklari(self, r: int) -> None:
        """Satırın hücre bayraklarını (salt okunur / düzenlenebilir) ayarlar."""

    def bos_mu(self, r: int) -> bool:
        """Satır boş sayılırsa kaydedilmez ve sonda boş satır olarak kalabilir."""
        return all(not self.text(r, k.key) for k in self.KOLONLAR if k.key != "sn" and k.tip in ("text", "lookup", "para"))

    def varsayilan_degerler(self) -> dict[str, str]:
        """Yeni satırın başlangıç değerleri (key -> metin)."""
        return {}

    def ekstra_baglam_eylemleri(self) -> list[tuple]:
        return []

    # ---- yardımcılar ---------------------------------------------------------
    def _delegate(self, k: KolonTanimi):
        if k.tip == "para":
            return MoneyDelegate(k.ondalik, True, self.grid)
        if k.tip == "tarih":
            return DateDelegate(self.grid)
        if k.tip == "combo":
            return ComboDelegate(lambda key=k.key: self.combo_secenekleri(key), self.grid)
        if k.tip == "lookup":
            return self.lookup_delegate(k.key)
        return None

    def text(self, r: int, key: str) -> str:
        it = self.grid.item(r, self.idx[key])
        return it.text().strip() if it else ""

    def set_text(self, r: int, key: str, value: str) -> None:
        was, self._busy = self._busy, True
        self.grid.item(r, self.idx[key]).setText(value)
        self._busy = was

    def item(self, r: int, key: str) -> QTableWidgetItem:
        return self.grid.item(r, self.idx[key])

    def sayi(self, r: int, key: str) -> float:
        return parse_num(self.text(r, key))

    def kimlik(self, r: int, key: str):
        it = self.item(r, key)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def set_kimlik(self, r: int, key: str, value) -> None:
        was, self._busy = self._busy, True             # setData de itemChanged tetikler
        self.item(r, key).setData(Qt.ItemDataRole.UserRole, value)
        self._busy = was

    # ---- satır yönetimi ------------------------------------------------------
    def set_defaults(self, tarih: date | None = None, **kwargs) -> None:
        """Yeni satırların başlangıç değerleri değişti (fiş başlığından); boş son satır yenilenir."""
        if tarih:
            self._tarih = tarih
        self._bos_satirlari_tazele()

    def _bos_satirlari_tazele(self) -> None:
        last = self.grid.rowCount() - 1
        if last >= 0 and self.bos_mu(last):
            self._busy = True
            self.grid.removeRow(last)
            self._busy = False
            self.add_row()

    def add_row(self, degerler: dict[str, str] | None = None) -> int:
        """Yeni satır ekler. `degerler` (key -> metin) verilirse (yükleme) varsayılanlar yerine kullanılır."""
        g = self.grid
        self._busy = True
        r = g.rowCount()
        g.insertRow(r)
        g.setRowHeight(r, g.effective_row_height)
        v = dict(self.varsayilan_degerler()) if degerler is None else dict(degerler)
        for i, k in enumerate(self.KOLONLAR):
            it = QTableWidgetItem(str(r + 1) if k.key == "sn" else v.get(k.key, ""))
            it.setTextAlignment(_HIZA.get(k.hiza, Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
            g.setItem(r, i, it)
        self._bayraklari_uygula(r)
        self._busy = False
        return r

    def _bayraklari_uygula(self, r: int) -> None:
        ro = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        for i, k in enumerate(self.KOLONLAR):
            if k.key == "sn" or k.tip == "readonly":
                self.grid.item(r, i).setFlags(ro)
        self.satir_bayraklari(r)

    def _sira_yenile(self) -> None:
        if "sn" not in self.idx:
            return
        was, self._busy = self._busy, True
        for r in range(self.grid.rowCount()):
            self.grid.item(r, self.idx["sn"]).setText(str(r + 1))
        self._busy = was

    def _sondaki_bos_satir(self) -> None:
        last = self.grid.rowCount() - 1
        if last < 0 or not self.bos_mu(last):
            self.add_row()

    def _on_item_changed(self, it: QTableWidgetItem) -> None:
        if self._busy:
            return
        r, c = it.row(), it.column()
        key = self.KOLONLAR[c].key
        self._busy = True
        try:
            self.hucre_degisti(r, key)
        finally:
            self._busy = False
        self._sondaki_bos_satir()
        self.totals_changed.emit()
        self.satir_secildi.emit(r)

    def secili_satirlari_sil(self) -> None:
        rows = sorted({i.row() for i in self.grid.selectedIndexes()}, reverse=True)
        self._busy = True
        for r in rows:
            self.grid.removeRow(r)
        self._busy = False
        if self.grid.rowCount() == 0:
            self.add_row()
        self._sondaki_bos_satir()
        self._sira_yenile()
        self.totals_changed.emit()
        self.satir_secildi.emit(-1)

    def satir_ekle(self) -> None:
        r = self.add_row()
        self.grid.setCurrentCell(r, next((i for i, k in enumerate(self.KOLONLAR) if not k.nav_atla and k.key != "sn"), 0))

    def _context_actions(self):
        return [("➕ Satır Ekle", self.satir_ekle), *self.ekstra_baglam_eylemleri(),
                ("🗑️ Seçili Satırları Sil", self.secili_satirlari_sil)]

    def clear(self) -> None:
        self._busy = True
        self.grid.setRowCount(0)
        self._busy = False
        self.add_row()
        self.totals_changed.emit()

    def dolu_satirlar(self) -> list[int]:
        return [r for r in range(self.grid.rowCount()) if not self.bos_mu(r)]
