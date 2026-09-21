"""TOYA ERP - CariCellDelegate: grid hücresinde cari kodu / ünvanı yazdıkça listeleyen, büyüteç düğmeli editör.

`LookupCellDelegate`'in cari için hazır hâlidir; `owner` kalemler widget'ıdır (`katalog()`, `cari_yaz(row, cari)`,
`cari_sec_liste(ilk_arama)` sağlar). Çağrılar her seferinde `owner` üzerinden yapılır."""

from __future__ import annotations

from src.desktop.ui.widgets.lookup_cell_delegate import LookupCellDelegate


class CariCellDelegate(LookupCellDelegate):
    def __init__(self, owner, grid) -> None:
        from src.desktop.ui.widgets.cari_fis_kalemleri_widget import C_KOD
        super().__init__(grid, katalog=lambda: owner.katalog(), sec=lambda r, c: owner.cari_yaz(r, c),
                         liste=lambda t: owner.cari_sec_liste(t), kod_kolonu=C_KOD, ipucu="Cari seçim listesi (F4)")
        self.owner = owner
