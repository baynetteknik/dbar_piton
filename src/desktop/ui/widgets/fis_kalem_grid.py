"""TOYA ERP - FisKalemGrid: fiş (belge) satır girişi için sütun tanımıyla çalışan grid iskeleti.

Cari, stok, kasa ve banka fişleri aynı davranışı paylaşır; her fiş yalnızca sütun listesini (`KOLONLAR`) ve birkaç kancayı
(`hucre_degisti`, `satir_bayraklari`, `bos_mu`, `varsayilan_degerler`) verir. Grid altyapısı (standart `FilterableTableView` entry modu, Enter/Tab
gezinme, editörler, sağ tık menüsü, sütun genişliği, satır silme/taşıma) `EntryGridBase`'ten gelir ve belge kalemleri (`DocumentLinesGrid`) ile
ORTAKTIR. Fişe özgü olan: sıra numarası (`sn`), tablonun sonunda her zaman boş bir satır, boş satır kuralı.

Alt sınıf `lookup_delegate(kolon_key)` ile arama/lookup sütunlarına (cari, ürün, depo) editör verir.
Sinyaller: `totals_changed()`, `satir_secildi(int)` (aktif satır), `message(str)`.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QStandardItem

from src.desktop.ui.widgets.entry_grid_base import HIZA as _HIZA
from src.desktop.ui.widgets.entry_grid_base import EntryGridBase, KolonTanimi
from src.desktop.services import sayi_bicimi
from src.desktop.ui.widgets.money_edit import bicimle, sayiya

__all__ = ["FisKalemGrid", "KolonTanimi", "fmt_num", "parse_date", "parse_num"]


def parse_num(text: str) -> float:
    """'1.234,56' / '1234,56' -> float; çözülemezse 0."""
    d = sayiya((text or "").replace(" ", ""))
    return float(d) if d is not None else 0.0


def fmt_num(v: float, dec: int | str = "tutar") -> str:
    """`dec` sayı ya da hane türü ('kur' | 'fiyat' | 'miktar' | 'tutar'; Genel Ayarlar › Kuruş Hanesi)."""
    return bicimle(v, sayi_bicimi.hane(dec) if isinstance(dec, str) else dec)


def parse_date(text: str) -> date | None:
    from datetime import datetime
    for f in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime((text or "").strip(), f).date()
        except ValueError:
            continue
    return None


class FisKalemGrid(EntryGridBase):
    PRESET_ID: str = "dbgrid_fis_kalem"
    PRESET_AD: str = "Fiş Kalemleri"

    def __init__(self, db_session=None, parent=None) -> None:
        self._tarih = date.today()
        super().__init__(db_session, parent)
        QShortcut(QKeySequence("Ctrl+Del"), self.tv, activated=self.secili_satirlari_sil)
        QShortcut(QKeySequence("Alt+Up"), self.tv, activated=lambda: self.satiri_tasi(-1))
        QShortcut(QKeySequence("Alt+Down"), self.tv, activated=lambda: self.satiri_tasi(1))
        self.add_row()

    # ---- alt sınıf kancaları -------------------------------------------------
    def hucre_degisti(self, r: int, key: str) -> None:
        """Bir hücre değişti (yeniden girişe karşı `_busy` korumalıdır; hücreleri `set_text` ile yazın)."""

    def satir_bayraklari(self, r: int) -> None:
        """Satırın hücre bayraklarını (salt okunur / düzenlenebilir) ayarlar."""

    def bos_mu(self, r: int) -> bool:
        """Satır boş sayılırsa kaydedilmez ve sonda boş satır olarak kalabilir."""
        return all(not self.text(r, k.key) for k in self._kolonlar if k.key != "sn" and k.tip in ("text", "lookup", "para"))

    def varsayilan_degerler(self) -> dict[str, str]:
        """Yeni satırın başlangıç değerleri (key -> metin)."""
        return {}

    def ekstra_baglam_eylemleri(self) -> list[tuple]:
        return []

    # ---- yardımcılar ---------------------------------------------------------
    def sayi(self, r: int, key: str) -> float:
        return parse_num(self.text(r, key))

    # ---- satır yönetimi ------------------------------------------------------
    def set_defaults(self, tarih: date | None = None, **kwargs) -> None:
        """Yeni satırların başlangıç değerleri değişti (fiş başlığından); boş son satır yenilenir."""
        if tarih:
            self._tarih = tarih
        self._bos_satirlari_tazele()

    def _bos_satirlari_tazele(self) -> None:
        last = self.tv.rowCount() - 1
        if last >= 0 and self.bos_mu(last):
            self._busy = True
            self.tv.removeRow(last)
            self._busy = False
            self.add_row()

    def add_row(self, degerler: dict[str, str] | None = None) -> int:
        """Yeni satır ekler. `degerler` (key -> metin) verilirse (yükleme) varsayılanlar yerine kullanılır."""
        g = self.tv
        self._busy = True
        r = g.rowCount()
        g.insertRow(r)
        g.setRowHeight(r, g.effective_row_height)
        v = dict(self.varsayilan_degerler()) if degerler is None else dict(degerler)
        for i, k in enumerate(self._kolonlar):
            it = QStandardItem(str(r + 1) if k.key == "sn" else v.get(k.key, ""))
            it.setTextAlignment(_HIZA.get(k.hiza, Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
            g.setItem(r, i, it)
        self._bayraklari_uygula(r)
        self._busy = False
        return r

    def _bayraklari_uygula(self, r: int) -> None:
        ro = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        for i, k in enumerate(self._kolonlar):
            if k.key == "sn" or k.tip == "readonly":
                self.tv.item(r, i).setFlags(ro)
        self.satir_bayraklari(r)

    def _sira_yenile(self) -> None:
        if "sn" not in self.idx:
            return
        was, self._busy = self._busy, True
        for r in range(self.tv.rowCount()):
            self.tv.item(r, self.idx["sn"]).setText(str(r + 1))
        self._busy = was

    def _sondaki_bos_satir(self) -> None:
        last = self.tv.rowCount() - 1
        if last < 0 or not self.bos_mu(last):
            self.add_row()

    def _on_item_changed(self, it: QStandardItem) -> None:
        if self._busy:
            return
        r, c = it.row(), it.column()
        key = self._kolonlar[c].key
        self._busy = True
        try:
            self.hucre_degisti(r, key)
        finally:
            self._busy = False
        self._sondaki_bos_satir()
        self.totals_changed.emit()
        self.satir_secildi.emit(r)

    def secili_satirlari_sil(self) -> None:
        self.satirlari_sil(self.secili_satirlar())
        if self.tv.rowCount() == 0:
            self.add_row()
        self._sondaki_bos_satir()
        self._sira_yenile()
        self.totals_changed.emit()
        self.satir_secildi.emit(-1)

    def satir_ekle(self) -> None:
        r = self.add_row()
        self.tv.setCurrentCell(r, next((i for i, k in enumerate(self._kolonlar) if not k.nav_atla and k.key != "sn"), 0))

    def _satir_sonrasi(self) -> None:
        self._sira_yenile()
        self.totals_changed.emit()

    def _context_actions(self):
        return [("➕ Satır Ekle", self.satir_ekle), *self.ekstra_baglam_eylemleri(),
                ("⬆️ Satırı Yukarı (Alt+↑)", lambda: self.satiri_tasi(-1)), ("⬇️ Satırı Aşağı (Alt+↓)", lambda: self.satiri_tasi(1)),
                ("🗑️ Seçili Satırları Sil", self.secili_satirlari_sil)]

    def clear(self) -> None:
        self._busy = True
        self.tv.setRowCount(0)
        self._busy = False
        self.add_row()
        self.totals_changed.emit()

    def dolu_satirlar(self) -> list[int]:
        return [r for r in range(self.tv.rowCount()) if not self.bos_mu(r)]
