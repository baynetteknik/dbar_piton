"""TOYA ERP - FinansFisDialog: kasa / banka hareket fişi (tahsilat, tediye, açılış, havale, EFT, virman) giriş penceresi.

Pencere düzeni, kayıt, çıktı ve hata akışı `FisDialogBase`'den gelir; bu sınıf kasa/bankaya özel parçaları verir: fiş başlığı
(türler gruba göre), hesap/cari kalemleri, seçili carinin durumu ("Bakiyeyi Tutara Aktar") ve döviz bazında giriş/çıkış toplamları.
`hesap_id` verilirse (kart ekranından açılınca) yeni satırların hesabı o hesaptır."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from sqlalchemy import select

from src.core.models import CariHareket, FinansHareket
from src.desktop.services import money_service
from src.desktop.services import finans_fis_rapor
from src.desktop.services.cari_hareket_service import CariHareketService
from src.desktop.services.finans_fis_service import (
    FIS_TIPLERI,
    GRUPLAR,
    FinansFisError,
    FinansFisService,
)
from src.desktop.ui.widgets.cari_durum_widget import CariDurumWidget
from src.desktop.ui.widgets.cari_fis_baslik_widget import CariFisBaslikWidget
from src.desktop.ui.widgets.finans_fis_kalemleri_widget import FinansFisKalemleriWidget
from src.desktop.ui.widgets.finans_fis_toplam_widget import FinansFisToplamWidget
from src.desktop.ui.widgets.fis_dialog_base import FisDialogBase


class FinansFisDialog(FisDialogBase):
    HATA_SINIFI = FinansFisError

    def __init__(self, db, fis_id: int | None = None, grup: str = "kasa", tur: str | None = None, hesap_id: int | None = None,
                 parent=None) -> None:
        if fis_id:                                            # mevcut fişin grubu fişten gelir
            from src.core.models import FinansFis
            f = db.get(FinansFis, fis_id)
            grup = f.grup if f is not None else grup
        self.grup = grup
        self.PENCERE_BASLIGI = f"{GRUPLAR[grup]} Hareket Fişi"
        self.BASLIK_YENI = f"{'💰' if grup == 'kasa' else '🏦'} Yeni {GRUPLAR[grup]} Hareket Fişi"
        self.BASLIK_MEVCUT = f"{'💰' if grup == 'kasa' else '🏦'} {GRUPLAR[grup]} Hareket Fişi"
        self.CIKTI_ONEKI = f"{grup}_fis"
        self.svc = FinansFisService(db)
        self._cari_svc = CariHareketService(db)
        self._varsayilan_tur = tur if tur in FIS_TIPLERI[grup] else next(iter(FIS_TIPLERI[grup]))
        self._hesap_id = hesap_id
        super().__init__(db, fis_id, parent)

    # ---- parçalar --------------------------------------------------------------
    def baslik_olustur(self):
        return CariFisBaslikWidget(tipler=FIS_TIPLERI[self.grup])

    def kalemler_olustur(self):
        k = FinansFisKalemleriWidget(db_session=self.db, grup=self.grup)
        k.set_varsayilan_hesap(self._hesap_id)
        return k

    def ozet_olustur(self):
        self.durum = CariDurumWidget()
        return self.durum

    def toplam_olustur(self):
        t = FinansFisToplamWidget(db_session=self.db)
        t.setMinimumWidth(620)
        t.setMinimumHeight(170)
        t.setMaximumHeight(190)
        return t

    def baglantilar(self) -> None:
        b = self.baslik
        b.tur_changed.connect(lambda tr: self.kalemler.set_defaults(tur=tr))
        b.dt_tarih.dateChanged.connect(lambda _d: self.kalemler.set_defaults(tarih=b.tarih()))
        b.chk_kilitli.toggled.connect(self.kilit_uygula)
        self.kalemler.cari_selected.connect(self._cari_durumu)
        self.durum.bakiye_aktar_requested.connect(self.kalemler.bakiyeyi_tutara_aktar)
        b.bitti.connect(lambda: self.kalemler.grid.setFocus(Qt.FocusReason.TabFocusReason))
        self.setTabOrder(b.chk_kilitli, self.kalemler.grid)
        b.data_changed.connect(self._kirlendi)
        b.tur_changed.connect(self._kirlendi)

    # ---- kancalar --------------------------------------------------------------
    def baslik_verisi(self) -> dict:
        return dict(self.baslik.get_data(), grup=self.grup)

    def kaydet_servis(self, baslik: dict, satirlar: list[dict], fis_id: int | None):
        return self.svc.fis_kaydet(baslik, satirlar, fis_id=fis_id)

    def yeni_hazirla(self) -> None:
        b = self.baslik
        b.clear()
        b.cmb_tur.setCurrentIndex(max(b.cmb_tur.findData(self._varsayilan_tur), 0))
        b.txt_fis_no.setText(self.svc.sonraki_fis_no(self.grup))
        self.kalemler.set_defaults(tur=b.tur(), tarih=b.tarih())
        self.durum.clear()

    def yukle(self, fis_id: int) -> None:
        fis, satirlar = self.svc.fis_getir(fis_id)
        self.baslik.set_data({
            "varsayilan_tur": fis.varsayilan_tur, "fis_no": fis.fis_no, "tarih": fis.tarih, "saat": fis.saat, "belge_no": fis.belge_no,
            "sube": fis.sube, "ozel_kod": fis.ozel_kod, "yetki_kodu": fis.yetki_kodu, "kilitli": fis.kilitli})
        for e, v in zip(self.txt_acik, (fis.aciklama1, fis.aciklama2, fis.aciklama3)):
            e.setText(v or "")
        self.kalemler.set_defaults(tur=fis.varsayilan_tur, tarih=fis.tarih)
        self.kalemler.load(satirlar)
        self.lbl_baslik.setText(f"{self.BASLIK_MEVCUT} — {fis.fis_no}")
        self.kilit_uygula(fis.kilitli)
        self._dirty = False

    def toplamlari_tazele(self) -> None:
        self.toplam.update_totals(self.kalemler.totals())

    def kilit_alanlari(self) -> list:
        b = self.baslik
        return [b.cmb_tur, b.dt_tarih, b.txt_fis_no, b.txt_belge_no, b.txt_sube, b.txt_ozel_kod, b.txt_yetki]

    def kilitli_mi(self) -> bool:
        return self.baslik.chk_kilitli.isChecked()

    def rapor_modulu(self):
        return finans_fis_rapor

    # ---- cariye özel -----------------------------------------------------------
    def _cari_durumu(self, cid) -> None:
        if not cid:
            self.durum.clear()
            return
        cari = self.kalemler.cari_bul(cid)
        bakiye = self._cari_svc.cari_bakiye(cid)
        if self.fis_id:                                       # bu fişin kendi cari karşılıkları bakiyeden düşülür
            for h in self.db.scalars(select(FinansHareket).where(FinansHareket.fis_id == self.fis_id, FinansHareket.customer_id == cid,
                                                                 FinansHareket.is_deleted == False)):  # noqa: E712
                c = self.db.get(CariHareket, h.cari_hareket_id) if h.cari_hareket_id else None
                if c is not None and not c.is_deleted:
                    bakiye -= c.tutar_tl if c.yon == "borc" else -c.tutar_tl
        self.durum.set_customer(cari, bakiye, self._cari_svc.dovizli_bakiye(cid), money_service.yerel_para(self.db))
