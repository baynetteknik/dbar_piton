"""TOYA ERP - CariFisDialog: cari hesap fişi (tahsilat / tediye / cari borç-alacak / virman / açılış) giriş penceresi.

Pencere düzeni, kayıt, çıktı ve hata akışı `FisDialogBase`'den gelir; bu sınıf yalnızca cariye özel parçaları verir:
fiş başlığı, cari kalemleri, seçili carinin durumu ("Bakiyeyi Tutara Aktar") ve döviz bazında toplamlar."""

from __future__ import annotations

from PyQt6.QtCore import Qt

from src.desktop.services import cari_fis_rapor
from src.desktop.services.cari_hareket_service import CariHareketError, CariHareketService
from src.desktop.ui.widgets.cari_durum_widget import CariDurumWidget
from src.desktop.ui.widgets.cari_fis_baslik_widget import CariFisBaslikWidget
from src.desktop.ui.widgets.cari_fis_kalemleri_widget import CariFisKalemleriWidget
from src.desktop.ui.widgets.cari_fis_toplam_widget import CariFisToplamWidget
from src.desktop.ui.widgets.fis_dialog_base import FisDialogBase


class CariFisDialog(FisDialogBase):
    PENCERE_BASLIGI = "Cari Hesap Fişi"
    BASLIK_YENI = "🧾 Yeni Cari Hesap Fişi"
    BASLIK_MEVCUT = "🧾 Cari Hesap Fişi"
    CIKTI_ONEKI = "cari_fis"
    HATA_SINIFI = CariHareketError

    def __init__(self, db, fis_id: int | None = None, tur: str = "tahsilat", parent=None) -> None:
        self.svc = CariHareketService(db)
        self._varsayilan_tur = tur
        super().__init__(db, fis_id, parent)

    # ---- parçalar --------------------------------------------------------------
    def baslik_olustur(self):
        return CariFisBaslikWidget()

    def kalemler_olustur(self):
        return CariFisKalemleriWidget(db_session=self.db)

    def ozet_olustur(self):
        self.durum = CariDurumWidget()
        return self.durum

    def toplam_olustur(self):
        t = CariFisToplamWidget(db_session=self.db)
        t.setMinimumWidth(620)
        t.setMinimumHeight(170)
        t.setMaximumHeight(190)
        return t

    def baglantilar(self) -> None:
        self.baslik.tur_changed.connect(lambda tr: self.kalemler.set_defaults(tur=tr))
        self.baslik.dt_tarih.dateChanged.connect(lambda _d: self.kalemler.set_defaults(tarih=self.baslik.tarih()))
        self.baslik.chk_kilitli.toggled.connect(self.kilit_uygula)
        self.kalemler.cari_selected.connect(self._cari_durumu)
        self.durum.bakiye_aktar_requested.connect(self.kalemler.bakiyeyi_tutara_aktar)
        # Klavye akışı: başlıkta Enter/Tab ile ilerle, son alandan kalemlere geç
        self.baslik.bitti.connect(lambda: self.kalemler.grid.setFocus(Qt.FocusReason.TabFocusReason))
        self.setTabOrder(self.baslik.chk_kilitli, self.kalemler.grid)
        self.baslik.data_changed.connect(self._kirlendi)
        self.baslik.tur_changed.connect(self._kirlendi)

    # ---- kancalar --------------------------------------------------------------
    def baslik_verisi(self) -> dict:
        return self.baslik.get_data()

    def kaydet_servis(self, baslik: dict, satirlar: list[dict], fis_id: int | None):
        return self.svc.fis_kaydet(baslik, satirlar, fis_id=fis_id)

    def yeni_hazirla(self) -> None:
        self.baslik.clear()
        self.baslik.cmb_tur.setCurrentIndex(max(self.baslik.cmb_tur.findData(self._varsayilan_tur), 0))
        self.baslik.txt_fis_no.setText(self.svc.sonraki_fis_no())
        self.kalemler.set_defaults(tur=self.baslik.tur(), tarih=self.baslik.tarih())
        self.durum.clear()

    def yukle(self, fis_id: int) -> None:
        fis, satirlar = self.svc.fis_getir(fis_id)
        self.baslik.set_data({
            "varsayilan_tur": fis.varsayilan_tur, "fis_no": fis.fis_no, "tarih": fis.tarih, "saat": fis.saat,
            "belge_no": fis.belge_no, "sube": fis.sube, "ozel_kod": fis.ozel_kod, "yetki_kodu": fis.yetki_kodu,
            "kilitli": fis.kilitli})
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
        return cari_fis_rapor

    # ---- cariye özel -----------------------------------------------------------
    def _kilit_degisti(self, kilitli: bool) -> None:          # geriye dönük ad
        self.kilit_uygula(kilitli)

    def _cari_durumu(self, cid) -> None:
        if not cid:
            self.durum.clear()
            return
        cari = self.kalemler.cari_bul(cid)
        self.durum.set_customer(cari, self.svc.cari_bakiye(cid, haric_fis_id=self.fis_id))
