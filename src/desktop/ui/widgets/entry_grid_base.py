"""TOYA ERP - EntryGridBase: belge kalemleri ve fiş kalemleri için ORTAK satır giriş gridi tabanı.

`DocumentLinesGrid` (teklif…fatura) ve `FisKalemGrid` (cari/kasa/banka/stok fişi) bu sınıftan türer. Ortak olan her şey burada, farklar alt sınıfta:

- standart grid: `FilterableTableView` (entry modu) + `EntryTableView` (hücre erişimi, Enter/Tab gezinme, yeni satır isteme); liste ekranlarıyla aynı
  başlık, sütun menüsü ve görünüm profilleri; isteğe bağlı seçim (onay kutusu) sütunu,
- sütun tanımı (`KolonTanimi`) ile hücre editörleri (para = `MoneyEdit`, tarih, açılır liste, arama/lookup),
- sağ tık menüsü (alt sınıf eylemleri + standart sütun/profil eylemi), sütun genişliğinin oranla dağıtılması,
- satır işlemleri: seçili (işaretli) satırları bulma/silme, satırı yukarı/aşağı taşıma, satır ekleme kancası.

Adlandırma: `self.entry` = `FilterableTableView` (kapsayıcı), `self.tv` = `EntryTableView` (tablo), `self.model` = `QStandardItemModel`.
`grid` özelliği tabloyu (`tv`) verir; `DocumentLinesGrid` geriye uyum için kendi `grid`'inde `entry`'yi verir (bkz. orası)."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import QMenu, QVBoxLayout, QWidget

from src.desktop.services import sayi_bicimi
from src.desktop.ui.components.entry_table_view import EntryTableView
from src.desktop.ui.components.filterable_table import FilterableTableView
from src.desktop.ui.components.grid_delegates import ComboDelegate, DateDelegate, MoneyDelegate


@dataclass(frozen=True)
class KolonTanimi:
    """Bir satır sütununun tanımı.

    tip: text | para | tarih | combo | lookup | readonly | secim (onay kutusu sütunu; en fazla bir tane). `ondalik` yalnız para içindir;
    `bos_olabilir` para hücresinde boş değere izin verir. Combo seçenekleri alt sınıfın `combo_secenekleri(key)` kancasından gelir.
    `oran` sütunun göreli genişliğidir; `min_px` altına inmez (dar pencerede yatay kaydırma). `nav_atla` klavye akışında atlanır."""
    key: str
    baslik: str
    oran: float
    hiza: str = "L"
    tip: str = "text"
    tam_ad: str | None = None
    ondalik: int | str = 2          # sayı ya da hane türü ('kur' | 'fiyat' | 'miktar' | 'tutar': Genel Ayarlar › Kuruş Hanesi)
    nav_atla: bool = False
    bos_olabilir: bool = True
    min_px: int = 40


HIZA = {"L": Qt.AlignmentFlag.AlignLeft, "R": Qt.AlignmentFlag.AlignRight, "C": Qt.AlignmentFlag.AlignCenter}


class EntryGridBase(QWidget):
    PRESET_ID: str = "dbgrid_entry"
    KOLONLAR: list[KolonTanimi] = []

    totals_changed = pyqtSignal()
    satir_secildi = pyqtSignal(int)
    message = pyqtSignal(str)

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        if db_session is not None:
            sayi_bicimi.yukle(db_session)
        self._busy = False
        self._kolonlar = list(self.kolonlar())
        self.idx = {k.key: i for i, k in enumerate(self._kolonlar)}
        self._secim_sutunu = next((i for i, k in enumerate(self._kolonlar) if k.tip == "secim"), None)
        self._lyt = QVBoxLayout(self)
        self._lyt.setContentsMargins(0, 0, 0, 0)
        self._lyt.setSpacing(4)
        headers = {i: (k.tam_ad or k.baslik, k.key) for i, k in enumerate(self._kolonlar)}      # sütun menüsünde tam ad, başlıkta kısaltma
        self.entry = FilterableTableView(headers_dict=headers, profile_key=self.PRESET_ID, select_column=self._secim_sutunu,
                                         mode="entry", table_view_class=EntryTableView)
        self.tv: EntryTableView = self.entry.table_view
        self.model = self.tv._model
        self.tv.set_columns([k.baslik for k in self._kolonlar], [k.tam_ad for k in self._kolonlar])
        self.tv.context_actions_provider = self._context_actions
        self.tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tv.customContextMenuRequested.connect(self._baglam_menusu)
        self.tv.enable_enter_navigation(skip_columns={i for i, k in enumerate(self._kolonlar) if k.nav_atla})
        self.tv.row_append_requested.connect(self.satir_istendi)
        self._lyt.addWidget(self.entry, 1)
        for i, k in enumerate(self._kolonlar):
            d = self._delegate(k)
            if d is not None:
                self.tv.setItemDelegateForColumn(i, d)
        self._oranli = True                            # kullanıcı sütun genişliğine dokunana (ya da kayıtlı profil uygulanana) kadar oranla dağıtılır
        self._genislik_uygulaniyor = False
        self.tv.horizontalHeader().sectionResized.connect(self._sutun_boyutlandi)
        self.model.itemChanged.connect(self._hucre_degisti_sinyali)
        self.tv.currentCellChanged.connect(lambda r, _c, _pr, _pc: self.satir_secildi.emit(r))

    # ---- alt sınıf kancaları -----------------------------------------------------------
    def kolonlar(self) -> list[KolonTanimi]:
        """Sütun tanımları (çalışma anı ayarlarına — ör. hane sayıları — bağlıysa alt sınıf bunu geçersiz kılar)."""
        return self.KOLONLAR

    def lookup_delegate(self, key: str):
        """`lookup` tipli sütun için editör (delegate). Varsayılan: düz metin."""
        return None

    def combo_secenekleri(self, key: str) -> list[str]:
        """`combo` tipli sütunun açılır liste seçenekleri."""
        return []

    def satir_istendi(self) -> None:
        """Klavye gezinmesi son satırı aştı: yeni satır ekle (alt sınıf `add_row`'u uygular)."""
        self.add_row()

    def add_row(self, *_a, **_k):
        raise NotImplementedError

    def _on_item_changed(self, it: QStandardItem) -> None:
        """Bir hücre değişti (alt sınıf uygular)."""

    def _satir_sonrasi(self) -> None:
        """Satır silindi / taşındı: sıra no ve toplamları tazele (alt sınıf uygular)."""

    def _context_actions(self) -> list[tuple]:
        """Sağ tık menüsünün üst eylemleri: [(metin, çağrılabilir)]."""
        return []

    # ---- editörler / sinyal ------------------------------------------------------------
    def _delegate(self, k: KolonTanimi):
        if k.tip == "para":
            return MoneyDelegate(sayi_bicimi.hane(k.ondalik) if isinstance(k.ondalik, str) else k.ondalik, k.bos_olabilir, self.tv)
        if k.tip == "tarih":
            return DateDelegate(self.tv)
        if k.tip == "combo":
            return ComboDelegate(lambda key=k.key: self.combo_secenekleri(key), self.tv)
        if k.tip == "lookup":
            return self.lookup_delegate(k.key)
        return None

    def _hucre_degisti_sinyali(self, it: QStandardItem) -> None:
        if not self._busy:
            self._on_item_changed(it)

    @property
    def grid(self) -> EntryTableView:
        return self.tv

    # ---- hücre erişimi -----------------------------------------------------------------
    def text(self, r: int, key: str) -> str:
        it = self.tv.item(r, self.idx[key])
        return it.text().strip() if it else ""

    def set_text(self, r: int, key: str, value: str) -> None:
        was, self._busy = self._busy, True
        self.tv.item(r, self.idx[key]).setText(value)
        self._busy = was

    def item(self, r: int, key: str) -> QStandardItem:
        return self.tv.item(r, self.idx[key])

    def kimlik(self, r: int, key: str):
        it = self.item(r, key)
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def set_kimlik(self, r: int, key: str, value) -> None:
        was, self._busy = self._busy, True             # setData de itemChanged tetikler
        self.item(r, key).setData(value, Qt.ItemDataRole.UserRole)
        self._busy = was

    # ---- satır işlemleri ----------------------------------------------------------------
    def secili_satirlar(self) -> list[int]:
        """İşaretli (onay kutulu) satırlar; yoksa seçili satırlar (artan sırada)."""
        if self._secim_sutunu is not None:
            isaretli = self.entry.get_checked_rows()
            if isaretli:
                return sorted(isaretli)
        return sorted({i.row() for i in self.tv.selectedIndexes()})

    def satirlari_sil(self, rows: list[int]) -> None:
        was, self._busy = self._busy, True
        for r in sorted(rows, reverse=True):
            self.model.removeRow(r)
        self._busy = was

    def aktif_satir(self) -> int:
        """Geçerli satır; yoksa seçili ilk satır; o da yoksa -1."""
        r = self.tv.currentRow()
        if r >= 0:
            return r
        sel = self.tv.selectionModel().selectedRows()
        return sel[0].row() if sel else -1

    def satiri_tasi(self, yon: int) -> None:
        """Geçerli satırı yukarı (-1) / aşağı (+1) taşır."""
        r = self.aktif_satir()
        h = r + yon
        if r < 0 or not 0 <= h < self.model.rowCount():
            return
        was, self._busy = self._busy, True
        try:
            self.model.insertRow(h, self.model.takeRow(r))
        finally:
            self._busy = was
        self._satir_sonrasi()
        self.tv.selectRow(h)

    # ---- sağ tık menüsü -----------------------------------------------------------------
    def _baglam_menusu(self, pos) -> None:
        """Sağ tık: alt sınıf eylemleri + standart sütun/profil eylemi (liste ve belge gridleriyle aynı)."""
        menu = QMenu(self)
        for ad, fn in self._context_actions():
            menu.addAction(ad).triggered.connect(lambda _c=False, f=fn: f())
        menu.addSeparator()
        self.entry.add_column_actions_to_menu(menu)
        menu.exec(self.tv.viewport().mapToGlobal(pos))

    # ---- sütun genişlikleri (KolonTanimi.oran / min_px) ---------------------------------
    def _sutun_boyutlandi(self, *_a) -> None:
        if not self._genislik_uygulaniyor:
            self._oranli = False                       # kullanıcı ya da kayıtlı profil genişliği belirledi

    def _oranli_genislik(self) -> None:
        if not self._oranli:
            return
        toplam = sum(k.oran for k in self._kolonlar) or 1.0
        w = max(self.tv.viewport().width(), 300)
        self._genislik_uygulaniyor = True
        for i, k in enumerate(self._kolonlar):
            self.tv.setColumnWidth(i, max(k.min_px, int(w * k.oran / toplam)))
        self._genislik_uygulaniyor = False

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self._oranli_genislik)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._oranli_genislik()
