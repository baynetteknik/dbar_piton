"""TOYA ERP - StokFisDialog: stok hareket fişi (giriş / çıkış / transfer / sayım / açılış) giriş penceresi.

Pencere düzeni, kayıt, çıktı ve hata akışı `FisDialogBase`'den gelir; bu sınıf stoka özel parçaları verir: fiş başlığı
(depo / hedef depo dahil), stok kalemleri, seçili stoğun durumu (toplam ve depo bakiyesi) ve birim bazında toplamlar."""

from __future__ import annotations

from PyQt6.QtCore import Qt

from src.desktop.services import stok_fis_rapor
from src.desktop.services.stok_fis_service import StokFisError, StokFisService
from src.desktop.ui.widgets.fis_dialog_base import FisDialogBase
from src.desktop.ui.widgets.stok_durum_widget import StokDurumWidget
from src.desktop.ui.widgets.stok_fis_baslik_widget import StokFisBaslikWidget
from src.desktop.ui.widgets.stok_fis_kalemleri_widget import StokFisKalemleriWidget
from src.desktop.ui.widgets.stok_fis_toplam_widget import StokFisToplamWidget


class StokFisDialog(FisDialogBase):
    PENCERE_BASLIGI = "Stok Hareket Fişi"
    BASLIK_YENI = "📦 Yeni Stok Hareket Fişi"
    BASLIK_MEVCUT = "📦 Stok Hareket Fişi"
    CIKTI_ONEKI = "stok_fis"
    HATA_SINIFI = StokFisError

    def __init__(self, db, fis_id: int | None = None, tur: str = "giris", parent=None) -> None:
        self.svc = StokFisService(db)
        self._varsayilan_tur = tur
        self.svc.varsayilan_depo()                                # hiç depo yoksa MERKEZ oluşturulur
        self._depolar = [(d.id, d.code, d.name or "") for d in self.svc.depolar()]
        super().__init__(db, fis_id, parent)

    # ---- parçalar --------------------------------------------------------------
    def baslik_olustur(self):
        return StokFisBaslikWidget(self._depolar)

    def kalemler_olustur(self):
        return StokFisKalemleriWidget(db_session=self.db, depolar=self._depolar)

    def ozet_olustur(self):
        self.durum = StokDurumWidget()
        return self.durum

    def toplam_olustur(self):
        t = StokFisToplamWidget(db_session=self.db)
        t.setMinimumWidth(620)
        t.setMinimumHeight(170)
        t.setMaximumHeight(190)
        return t

    def baglantilar(self) -> None:
        b = self.baslik
        b.tur_changed.connect(lambda tr: self.kalemler.set_defaults(tur=tr))
        b.dt_tarih.dateChanged.connect(lambda _d: self.kalemler.set_defaults(tarih=b.tarih()))
        b.depo_changed.connect(lambda: self.kalemler.set_defaults(depo_id=b.cmb_depo.currentData(),
                                                                  hedef_depo_id=b.cmb_hedef.currentData()))
        b.chk_kilitli.toggled.connect(self.kilit_uygula)
        self.kalemler.urun_secildi.connect(self._urun_durumu)
        self.kalemler.grid.currentCellChanged.connect(lambda *_a: self._urun_durumu(self.kalemler.secili_urun_id()))
        b.bitti.connect(lambda: self.kalemler.grid.setFocus(Qt.FocusReason.TabFocusReason))
        self.setTabOrder(b.chk_kilitli, self.kalemler.grid)
        b.data_changed.connect(self._kirlendi)
        b.tur_changed.connect(self._kirlendi)

    # ---- kancalar --------------------------------------------------------------
    def baslik_verisi(self) -> dict:
        return self.baslik.get_data()

    def kaydet_servis(self, baslik: dict, satirlar: list[dict], fis_id: int | None):
        return self.svc.fis_kaydet(baslik, satirlar, fis_id=fis_id)

    def yeni_hazirla(self) -> None:
        b = self.baslik
        b.clear()
        b.cmb_tur.setCurrentIndex(max(b.cmb_tur.findData(self._varsayilan_tur), 0))
        b.txt_fis_no.setText(self.svc.sonraki_fis_no())
        self.kalemler.set_defaults(tur=b.tur(), tarih=b.tarih(), depo_id=b.cmb_depo.currentData(),
                                   hedef_depo_id=b.cmb_hedef.currentData())
        self.durum.clear()

    def yukle(self, fis_id: int) -> None:
        fis, satirlar = self.svc.fis_getir(fis_id)
        self.baslik.set_data({
            "varsayilan_tur": fis.varsayilan_tur, "fis_no": fis.fis_no, "tarih": fis.tarih, "saat": fis.saat,
            "belge_no": fis.belge_no, "ozel_kod": fis.ozel_kod, "yetki_kodu": fis.yetki_kodu, "kilitli": fis.kilitli,
            "depo_id": fis.depo_id, "hedef_depo_id": fis.hedef_depo_id})
        for e, v in zip(self.txt_acik, (fis.aciklama1, fis.aciklama2, fis.aciklama3)):
            e.setText(v or "")
        self.kalemler.set_defaults(tur=fis.varsayilan_tur, tarih=fis.tarih, depo_id=fis.depo_id, hedef_depo_id=fis.hedef_depo_id)
        self.kalemler.load(satirlar)
        self.lbl_baslik.setText(f"{self.BASLIK_MEVCUT} — {fis.fis_no}")
        self.kilit_uygula(fis.kilitli)
        self._dirty = False

    def toplamlari_tazele(self) -> None:
        self.toplam.update_totals(self.kalemler.totals())

    def kilit_alanlari(self) -> list:
        b = self.baslik
        return [b.cmb_tur, b.dt_tarih, b.txt_fis_no, b.txt_belge_no, b.txt_ozel_kod, b.txt_yetki, b.cmb_depo, b.cmb_hedef]

    def kilitli_mi(self) -> bool:
        return self.baslik.chk_kilitli.isChecked()

    def rapor_modulu(self):
        return stok_fis_rapor

    # ---- stoğa özel ------------------------------------------------------------
    def _urun_durumu(self, pid) -> None:
        if not pid:
            self.durum.clear()
            return
        u = self.kalemler.urun_bul(pid)
        if u is None:
            self.durum.clear()
            return
        from src.core.models import Product
        p = self.db.get(Product, pid)
        depo = self.kalemler.secili_depo_id() or self.baslik.cmb_depo.currentData()
        kod = self.baslik.depo_kodu(depo)
        self.durum.set_urun(dict(u, stock=p.stock), toplam=float(p.stock or 0), depo=kod,
                            depo_bakiye=self.svc.depo_stok(pid, depo, haric_fis_id=self.fis_id) if depo else 0.0)
