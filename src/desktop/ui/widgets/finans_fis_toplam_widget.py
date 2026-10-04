"""TOYA ERP - FinansFisToplamWidget: kasa / banka fişinin döviz bazında giriş / çıkış / net toplamları.

    w.update_totals({"TRY": (giris, cikis, yerel_giris, yerel_cikis)})   # net > 0: hesaba net giriş (G), < 0: çıkış (Ç)"""

from __future__ import annotations

from src.desktop.ui.widgets.cari_fis_toplam_widget import CariFisToplamWidget


class FinansFisToplamWidget(CariFisToplamWidget):
    PRESET_ID = "dbgrid_finans_fis_toplam"
    PRESET_AD = "Kasa / Banka Fiş Toplamları"
    ETIKETLER = ["DÖVİZ", "GİRİŞ", "ÇIKIŞ", "NET", "Y. GİRİŞ", "Y. ÇIKIŞ", "Y. NET", "G/Ç"]
    YONLER = ("(G)", "(Ç)")
    RENKLER = ("#16a34a", "#dc2626")
