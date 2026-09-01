"""
TOYA ERP - Atomik Belge Formu Widget Paketi
Teklif, Fatura, Sipariş ve İrsaliye formlarının modüler parçaları.
"""

from src.desktop.ui.widgets.document_form.cari_kunyesi_widget import CariHesapKunyesiWidget
from src.desktop.ui.widgets.document_form.belge_vade_widget import BelgeVadeDetaylariWidget
from src.desktop.ui.widgets.document_form.hareket_ayarlari_widget import HareketAyarlariWidget
from src.desktop.ui.widgets.document_form.finans_widget import FinansWidget
from src.desktop.ui.widgets.document_form.hareket_kalemleri_widget import HareketKalemleriDbGridWidget
from src.desktop.ui.widgets.document_form.alt_iskonto_masraflar_widget import AltIskontoMasraflarWidget
from src.desktop.ui.widgets.document_form.belge_notlari_widget import BelgeNotlariWidget

__all__ = [
    "CariHesapKunyesiWidget",
    "BelgeVadeDetaylariWidget",
    "HareketAyarlariWidget",
    "FinansWidget",
    "HareketKalemleriDbGridWidget",
    "AltIskontoMasraflarWidget",
    "BelgeNotlariWidget",
]
