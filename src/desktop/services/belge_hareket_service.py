"""TOYA ERP - BelgeHareketService: belge zincirinin (teklif → sipariş → irsaliye → fatura) stok/cari hareket üretimi.

Bkz. `gelistirme/06_fatura_irsaliye/belge_zinciri_tasarim.md`. Bir `Quotation` belgesi `belge_turu` + `yon` taşır (bkz.
`src.core.belge_turleri`); yalnızca irsaliye ve fatura hareket üretir (`isle`), teklif/talep/sipariş üretmez. Durum makinesi:

    islenmedi ──isle()──▶ islendi ──geri_al()──▶ geri_alindi
                              │        (yalnız resmi_gonderildi=False iken; sonrası yalnız iade() ile düzeltilir)
                              ▼
                       resmi_isaretle(True)   (e-Devlete gönderildi — elle işaret; sonrası geri_al() kapanır)

Hareketler `StokHareket`/`CariHareket` satırlarına `belge_id`/`belge_satir_id` ile bağlanır; `geri_al` hiçbir satırı
silmez/mutasyona uğratmaz, ters işaretli YENİ satırlar ekler (tam denetim izi). Çift sayım koruması: bir fatura satırı
bir irsaliye satırından geldiyse (`stok_etkisi='kaynaktan'`, `belge_bag` ile bağlı) `isle()` o satır için stok yazmaz —
stok yalnızca irsaliyeden gelir. Çoklu irsaliye → tek fatura ve sipariş → irsaliye (kısmi dahil) `belge_bag` üzerinden
izlenir (`QuotationLine.faturalanan` / `sevk_edilen` önbellekleri). Sipariş rezervi (`StokRezerv`) sevk edilince düşer;
`kullanilabilir_stok` = eldeki − aktif rezervler. Silme yok; her şey ek satırla düzeltilir."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select

from src.core import belge_turleri as bt
from src.core.models import BelgeBag, CariHareket, FinansHesap, Product, Quotation, QuotationLine, StokHareket, StokRezerv
from src.desktop.services import belge_hesap, money_service, numara_servisi
from src.desktop.services.belge_kilit_servisi import BelgeKilitServisi, KilitHatasi
from src.desktop.services import stok_negatif_politika
from src.desktop.services.cari_hareket_service import CariHareketError, CariHareketService
from src.desktop.services.stok_fis_service import StokFisService

#: Faturanın cari etkisi: yön -> hareket türü (bkz. CariHareketService.TURLER). Borç = cari bize borçlu (satış), alacak = biz cariye borçluyuz (alış).
_CARI_TUR = {"satis": "borc_dekontu", "alis": "alacak_dekontu"}
_CARI_TUR_TERS = {"satis": "alacak_dekontu", "alis": "borc_dekontu"}
_CARI_TUR_KARSITI = {"borc_dekontu": "alacak_dekontu", "alacak_dekontu": "borc_dekontu"}


def _norm(x: float) -> float | int:
    x = round(float(x), 4)
    return int(x) if x == int(x) else x


def _belge_tarihi(belge: Quotation) -> date:
    return (belge.date or belge.issue_date or datetime.utcnow()).date()


def kullanilabilir_stok(db, product_id: int, depo_id: int | None = None) -> float:
    """Eldeki (ya da depo bazlı) stoktan aktif sipariş rezervleri düşülmüş miktar."""
    if depo_id:
        eldeki = StokFisService(db).depo_stok(product_id, depo_id)
    else:
        p = db.get(Product, product_id)
        eldeki = float(p.stock or 0) if p is not None else 0.0
    q = select(func.coalesce(func.sum(StokRezerv.miktar), 0.0)).where(
        StokRezerv.product_id == product_id, StokRezerv.durum == "aktif", StokRezerv.is_deleted == False)  # noqa: E712
    if depo_id:
        q = q.where(StokRezerv.depo_id == depo_id)
    return eldeki - float(db.scalar(q) or 0.0)


class BelgeHareketError(ValueError):
    """Doğrulama hatası; mesaj kullanıcıya gösterilebilir."""


class YetersizStokError(BelgeHareketError):
    """Çıkış stoğu negatife düşürüyor ve politika 'işlemi durdur'. Arayüz, kullanıcı onaylarsa `isle(..., politika="uyari_devam")` ile yeniden dener."""


class BelgeHareketService:
    def __init__(self, db) -> None:
        self.db = db
        self._cari = CariHareketService(db)
        self.uyarilar: list[str] = []

    # ---- yardımcılar ---------------------------------------------------------------
    def _belge_getir(self, belge_id: int) -> Quotation:
        b = self.db.get(Quotation, belge_id)
        if b is None or b.is_deleted:
            raise BelgeHareketError("Belge bulunamadı.")
        return b

    def _sonraki_no(self, belge_turu: str, yon: str | None = "satis", tarih=None) -> str:
        return numara_servisi.belge_numarasi(self.db, belge_turu, yon, tarih)

    # ---- işleme: hareket üret / geri al / resmi işaret --------------------------------------
    def isle(self, belge_id: int, politika: str | None = None) -> Quotation:
        """İrsaliye/faturanın stok ve (faturaysa) cari hareketlerini üretir. Yalnızca 'islenmedi' durumundaki belgede çalışır."""
        belge = self._belge_getir(belge_id)
        if belge.belge_turu not in bt.STOK_ETKILI and belge.belge_turu not in bt.CARI_ETKILI:
            raise BelgeHareketError(f"'{bt.BELGE_TURLERI.get(belge.belge_turu, belge.belge_turu)}' hareket üretmez.")
        if belge.hareket_durumu != "islenmedi":
            raise BelgeHareketError("Belge zaten işlenmiş; önce geri alın.")
        self._politika = politika                                             # None = Genel Ayarlar'daki politika
        try:
            self.uyarilar = []
            if belge.belge_turu in bt.STOK_ETKILI:
                taban = 1 if belge.yon == "alis" else -1                          # satış → çıkış(-1), alış → giriş(+1)
                isaret = -taban if belge.belge_turu == "iade_fatura" else taban   # iade bunun tersidir
                for satir in sorted(belge.lines, key=lambda x: x.line_order or 0):
                    if satir.stok_etkisi != "kendi" or not satir.product_id or not satir.quantity:
                        continue
                    urun = self.db.get(Product, satir.product_id)
                    if urun is not None and urun.tracks_stock is False:
                        continue   # Hizmet/Masraf kartı: stok hareketi/depo zorunluluğu YOK (bkz. Product.tracks_stock)
                    self._stok_yaz(belge, satir, isaret)
            if belge.belge_turu in bt.CARI_ETKILI:
                self._cari_yaz(belge)
            belge.hareket_durumu = "islendi"
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return belge

    def _stok_yaz(self, belge: Quotation, satir: QuotationLine, isaret: int) -> StokHareket:
        p = self.db.get(Product, satir.product_id)
        if p is None or p.is_deleted:
            raise BelgeHareketError(f"Satır {satir.line_order}: stok kartı bulunamadı.")
        depo_id = satir.depo_id or belge.depo_id
        if not depo_id:
            raise BelgeHareketError(f"Satır {satir.line_order}: depo seçilmelidir.")
        miktar = float(satir.quantity or 0)
        etki = isaret * miktar
        if etki < 0:
            sonuc, mesaj = stok_negatif_politika.degerlendir(self.db, float(p.stock or 0), -etki, getattr(self, "_politika", None))
            if sonuc == "engel":
                raise YetersizStokError(f"Satır {satir.line_order}: {p.sku} ({p.name}) — Yetersiz stok: {mesaj}")
            if sonuc == "uyari":
                self.uyarilar.append(f"Satır {satir.line_order}: {p.sku} ({p.name}) — {mesaj}")
        p.stock = _norm((p.stock or 0) + etki)
        h = StokHareket(product_id=p.id, tur="giris" if etki > 0 else "cikis", tarih=_belge_tarihi(belge), depo_id=depo_id,
                        miktar=abs(etki), birim=satir.unit or p.unit or "Adet", birim_fiyat=satir.unit_price or 0.0,
                        tutar=round(abs(etki) * (satir.unit_price or 0.0), 2),
                        aciklama=f"{bt.BELGE_TURLERI.get(belge.belge_turu, '')} {belge.quotation_number}",
                        depo_etkisi=etki, toplam_etki=etki, belge_id=belge.id, belge_satir_id=satir.id)
        self.db.add(h)
        return h

    def _cari_yaz(self, belge: Quotation) -> list[CariHareket]:
        """Her satır kendi para birimiyle KENDİ `CariHareket`'ini üretir (`belge_satir_id` ile bağlı) — Kasa/Banka
        fişlerinde (`finans_fis_service.py`) zaten kanıtlanmış desenin fatura/teklif zincirine taşınmış hali. Satır
        döviz belirtmemişse belgenin kendi para birimine, o da yoksa şirketin yerel parasına düşer. Fişin `grand_total`'ı
        (bkz. `_toplamlari_hesapla`) hâlâ TEK bir özet rakamdır ve bilgilendiricidir; asıl borç/alacak kaydı burada
        satır satır, kendi cinsinden işlenir."""
        if not belge.customer_id:
            raise BelgeHareketError("Fatura cariye bağlı değil; cari hareketi üretilemez.")
        tur = (_CARI_TUR_TERS if belge.belge_turu == "iade_fatura" else _CARI_TUR)[belge.yon or "satis"]
        yerel = money_service.yerel_para(self.db)
        kayitlar: list[CariHareket] = []
        for satir in sorted(belge.lines, key=lambda x: x.line_order or 0):
            net = float(satir.total_amount or satir.total_price or 0.0)
            if net == 0:
                continue
            tutar = round(net * (1 + (satir.vat_rate or 0.0) / 100.0), 2)
            if tutar <= 0:
                continue
            para = (satir.doviz or belge.currency or yerel).upper()
            kur = (satir.kur or belge.exchange_rate or 1.0) if para != yerel else 1.0
            c = CariHareket(kaynak="belge", belge_id=belge.id, belge_satir_id=satir.id)
            try:
                self._cari._hazirla(c, {"customer_id": belge.customer_id, "tur": tur, "tutar": tutar, "para_birimi": para,
                                        "kur": kur, "tarih": _belge_tarihi(belge), "belge_no": belge.quotation_number,
                                        "aciklama": f"{bt.BELGE_TURLERI.get(belge.belge_turu, '')} {belge.quotation_number}"
                                                    f" — satır {satir.line_order}: {satir.name or satir.sku or ''}".rstrip(": ")})
            except CariHareketError as e:
                raise BelgeHareketError(str(e)) from e
            self.db.add(c)
            kayitlar.append(c)
        if not kayitlar:
            raise BelgeHareketError("Faturanın genel toplamı sıfırdan büyük olmalıdır.")
        return kayitlar

    def geri_al(self, belge_id: int) -> Quotation:
        """Resmi bildirim öncesi geri alma: belgenin ürettiği tüm hareketleri TERS işaretli yeni satırlarla düzeltir
        (hiçbir kayıt silinmez/mutasyona uğramaz). Bildirildikten sonra kapalıdır; düzeltme `iade()` ile yapılır."""
        belge = self._belge_getir(belge_id)
        if belge.hareket_durumu != "islendi":
            raise BelgeHareketError("Belge işlenmemiş; geri alınacak hareket yok.")
        if belge.resmi_gonderildi:
            raise BelgeHareketError("Belge e-Devlete gönderildi olarak işaretli; geri alınamaz. Düzeltme için iade faturası kesin.")
        if self.tahsilatlar(belge.id):
            raise BelgeHareketError("Faturaya bağlı tahsilat/ödeme var; geri almadan önce onları kaldırın.")
        try:
            self.uyarilar = []
            for h in list(self.db.scalars(select(StokHareket).where(StokHareket.belge_id == belge.id, StokHareket.is_deleted == False))):  # noqa: E712
                p = self.db.get(Product, h.product_id)
                ters = -h.toplam_etki
                if ters < 0 and p is not None:
                    sonuc, mesaj = stok_negatif_politika.degerlendir(self.db, float(p.stock or 0), -ters)
                    if sonuc == "engel":
                        raise BelgeHareketError(f"{p.sku} ({p.name}) — geri alınamaz, yetersiz stok: {mesaj}")
                    if sonuc == "uyari":
                        self.uyarilar.append(f"{p.sku} ({p.name}) — {mesaj}")
                if p is not None:
                    p.stock = _norm((p.stock or 0) + ters)
                self.db.add(StokHareket(product_id=h.product_id, tur="giris" if ters > 0 else "cikis", tarih=date.today(), depo_id=h.depo_id,
                                        miktar=abs(ters), birim=h.birim, birim_fiyat=h.birim_fiyat, tutar=round(abs(ters) * (h.birim_fiyat or 0.0), 2),
                                        aciklama=f"Geri alma — {belge.quotation_number}", depo_etkisi=ters, toplam_etki=ters,
                                        belge_id=belge.id, belge_satir_id=h.belge_satir_id))
            for c in list(self.db.scalars(select(CariHareket).where(CariHareket.belge_id == belge.id, CariHareket.is_deleted == False))):  # noqa: E712
                ters_tur = _CARI_TUR_KARSITI.get(c.tur, c.tur)
                nc = CariHareket(kaynak="belge", belge_id=belge.id, belge_satir_id=c.belge_satir_id)
                self._cari._hazirla(nc, {"customer_id": c.customer_id, "tur": ters_tur, "tutar": c.tutar, "para_birimi": c.para_birimi,
                                         "kur": c.kur, "tarih": date.today(), "aciklama": f"Geri alma — {belge.quotation_number}"})
                self.db.add(nc)
            belge.hareket_durumu = "geri_alindi"
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return belge

    def resmi_isaretle(self, belge_id: int, gonderildi: bool = True, tarih: datetime | None = None) -> Quotation:
        """'e-Devlete gönderildi' elle işareti. Yalnız işlenmiş (hareketleri üretilmiş) belgede işaretlenebilir."""
        belge = self._belge_getir(belge_id)
        if gonderildi and belge.hareket_durumu != "islendi":
            raise BelgeHareketError("Yalnızca işlenmiş belge e-Devlete gönderildi işaretlenebilir.")
        belge.resmi_gonderildi = bool(gonderildi)
        belge.resmi_tarih = (tarih or datetime.utcnow()) if gonderildi else None
        self.db.commit()
        return belge

    # ---- tahsilat / ödeme (fatura ↔ kasa/banka) ------------------------------------------------
    def tahsilatlar(self, belge_id: int) -> list[CariHareket]:
        return list(self.db.scalars(select(CariHareket).where(CariHareket.tahsilat_belge_id == belge_id, CariHareket.is_deleted == False,  # noqa: E712
                                                              CariHareket.tur.in_(("tahsilat", "odeme"))).order_by(CariHareket.tarih, CariHareket.id)))

    def kur_farklari(self, belge_id: int) -> list[CariHareket]:
        return list(self.db.scalars(select(CariHareket).where(CariHareket.tahsilat_belge_id == belge_id, CariHareket.is_deleted == False,  # noqa: E712
                                                              CariHareket.tur == "kur_farki").order_by(CariHareket.id)))

    def _borc_kuru(self, belge: Quotation) -> float:
        """Faturanın cari borç/alacak hareketinin yazıldığı kur (kur farkı karşılaştırması bu kura göredir).
        Not: `_cari_yaz` artık satır başına ayrı `CariHareket` üretir (her satır kendi para biriminde olabilir);
        tahsilat/ödeme hâlâ belge (fatura) düzeyinde TEK bir para biriminde çalıştığından, burada fişin kendi
        `belge.currency`'sine ait satırlardan biri örnek alınır. Tüm satırlar aynı dövizdeyse (yaygın durum) tam
        doğrudur; satırlar KARIŞIK para biriminde ise bu kur yalnız yaklaşık bir referanstır — karma para birimli
        bir faturaya satır bazlı tahsilat/kur farkı, ayrı bir aşamada ele alınacak bilinen bir sınırlamadır."""
        yerel = money_service.yerel_para(self.db)
        hedef_para = (belge.currency or yerel).upper()
        c = self.db.scalar(select(CariHareket).where(CariHareket.belge_id == belge.id, CariHareket.is_deleted == False,  # noqa: E712
                                                     CariHareket.tur.in_(tuple(_CARI_TUR.values())),
                                                     CariHareket.para_birimi == hedef_para).order_by(CariHareket.id))
        if c is None:
            c = self.db.scalar(select(CariHareket).where(CariHareket.belge_id == belge.id, CariHareket.is_deleted == False,  # noqa: E712
                                                         CariHareket.tur.in_(tuple(_CARI_TUR.values()))).order_by(CariHareket.id))
        return float(c.kur) if c is not None else float(belge.exchange_rate or 1.0)

    def kur_farki_onizle(self, belge_id: int, tutar: float, tarih: date | None = None, kur: float | None = None) -> float:
        """Bu tahsilat/ödeme kaydedilirse oluşacak kur farkı (yerel para; işaretli: + ise tahsilat kuru borç kurundan yüksek). Yerel para faturada 0."""
        belge = self._belge_getir(belge_id)
        if (belge.currency or money_service.yerel_para(self.db)).upper() == money_service.yerel_para(self.db):
            return 0.0
        k = kur or money_service.kur_bul(self.db, belge.currency, tarih or date.today())
        return round(float(tutar) * (k - self._borc_kuru(belge)), 2)

    def odenen(self, belge_id: int) -> float:
        return round(sum(c.tutar for c in self.tahsilatlar(belge_id)), 2)

    def kalan_tutar(self, belge_id: int) -> float:
        return round(float(self._belge_getir(belge_id).grand_total or 0.0) - self.odenen(belge_id), 2)

    def acik_faturalar(self, customer_id: int) -> list[Quotation]:
        """Müşterinin kalan tutarı sıfırdan büyük, işlenmiş faturaları — en eski belge tarihinden yeniye (FIFO)
        sıralı. Not: TOYA'da henüz fatura/satır bazlı ayrı bir vade tarihi alanı yok (`payment_plan` yalnız
        metindir); bu yüzden sıralama BELGE TARİHİNE göre yapılır — en eski fatura en önce kapatılır."""
        q = select(Quotation).where(Quotation.customer_id == customer_id, Quotation.belge_turu == "fatura",
                                    Quotation.hareket_durumu == "islendi", Quotation.is_deleted == False)  # noqa: E712
        acik = [f for f in self.db.scalars(q) if self.kalan_tutar(f.id) > 0.005]
        acik.sort(key=lambda f: (_belge_tarihi(f), f.id))
        return acik

    def _tahsilat_plani(self, customer_id: int, odeme_tutari_tl: float, tarih: date) -> list[tuple[Quotation, float, float]]:
        """Salt hesaplama (HİÇBİR KAYIT YAZMAZ): FIFO sırayla hangi faturaya kendi dövizinde ne kadar, hangi
        kurla uygulanacağı. Hem önizleme (`tahsilat_dagit_onizle`) hem gerçek uygulama (`tahsilat_dagit`) bu
        TEK planlama mantığını paylaşır — ikisi asla birbirinden sapmaz."""
        yerel = money_service.yerel_para(self.db)
        plan: list[tuple[Quotation, float, float]] = []
        kalan_tl = odeme_tutari_tl
        for f in self.acik_faturalar(customer_id):
            if kalan_tl <= 0.005:
                break
            para = (f.currency or yerel).upper()
            kur = 1.0 if para == yerel else money_service.kur_bul(self.db, para, tarih)
            kalan_fatura_doviz = self.kalan_tutar(f.id)
            kalan_fatura_tl = round(kalan_fatura_doviz * kur, 2)
            uygulanan_tl = min(kalan_tl, kalan_fatura_tl)
            uygulanan_doviz = kalan_fatura_doviz if uygulanan_tl >= kalan_fatura_tl - 0.005 else round(uygulanan_tl / kur, 2)
            if uygulanan_doviz > 0:
                plan.append((f, uygulanan_doviz, kur))
            kalan_tl = round(kalan_tl - uygulanan_tl, 2)
        return plan

    def tahsilat_dagit_onizle(self, customer_id: int, odeme_tutari_tl: float, *, tarih: date | None = None) -> list[dict]:
        """`tahsilat_dagit` ile AYNI planı, hiçbir kayıt yazmadan döner — ekranda kullanıcıya "şu faturalara şu
        kadar uygulanacak" önizlemesi göstermek için. @return [{"belge", "tutar_doviz", "kur"}, ...]"""
        odeme_tutari_tl = round(float(odeme_tutari_tl or 0.0), 2)
        if odeme_tutari_tl <= 0:
            raise BelgeHareketError("Tutar sıfırdan büyük olmalıdır.")
        try:
            plan = self._tahsilat_plani(customer_id, odeme_tutari_tl, tarih or date.today())
        except money_service.UnknownCurrencyError as e:
            raise BelgeHareketError(str(e)) from e
        return [{"belge": f, "tutar_doviz": t, "kur": k} for f, t, k in plan]

    def tahsilat_dagit(self, customer_id: int, odeme_tutari_tl: float, hesap_id: int, *, tarih: date | None = None,
                       kur_farki_modu: str = "cari") -> list[dict]:
        """Kullanıcı senaryosu: müşteri TEK bir para biriminde (TL) öder, sistem bunu müşterinin AÇIK faturalarına
        (hangi para biriminde olursa olsun) eski→yeni (FIFO, `acik_faturalar`) otomatik dağıtır; her fatura kendi
        para biriminde, ödeme tarihindeki kurla kapanır. `kur_farki_modu`: "cari" (yalnız CariHareket, varsayılan),
        "fatura" (oluşan her kur farkı için `kur_farki_faturasi_olustur` ile taslak fatura kesilir), "yok" (kur
        farkı hiç işlenmez). Ödeme faturaların TOPLAMINI aşarsa fazlası dağıtılmadan kalan bilgisinde görünür
        (ayrıca bir alacak/avans kaydı bu fonksiyonun kapsamında DEĞİLDİR).
        @return [{"belge", "tutar_doviz", "hareket", "kur_farki_taslak"}, ...] — hangi faturaya ne kadar uygulandığı."""
        if kur_farki_modu not in ("cari", "fatura", "yok"):
            raise BelgeHareketError("Geçersiz kur farkı modu.")
        odeme_tutari_tl = round(float(odeme_tutari_tl or 0.0), 2)
        if odeme_tutari_tl <= 0:
            raise BelgeHareketError("Tutar sıfırdan büyük olmalıdır.")
        tarih = tarih or date.today()
        try:
            plan = self._tahsilat_plani(customer_id, odeme_tutari_tl, tarih)
        except money_service.UnknownCurrencyError as e:
            raise BelgeHareketError(str(e)) from e
        dokum: list[dict] = []
        for f, uygulanan_doviz, kur in plan:
            hareket = self.tahsilat_ekle(f.id, uygulanan_doviz, hesap_id, tarih=tarih, kur=kur,
                                         kur_farki_isle=(kur_farki_modu != "yok"))
            taslak = None
            if kur_farki_modu == "fatura":
                kfler = self.kur_farklari(f.id)
                if kfler:
                    taslak = self.kur_farki_faturasi_olustur(kfler[-1].id)
            dokum.append({"belge": f, "tutar_doviz": uygulanan_doviz, "hareket": hareket, "kur_farki_taslak": taslak})
        if not dokum:
            raise BelgeHareketError("Dağıtılacak açık fatura bulunamadı.")
        return dokum

    def tahsilat_ekle(self, belge_id: int, tutar: float, hesap_id: int, *, tarih: date | None = None, aciklama: str | None = None,
                      kur: float | None = None, kur_farki_isle: bool = False) -> CariHareket:
        """İşlenmiş faturaya kasa/banka hesabıyla tahsilat (satış) ya da ödeme (alış) girer. Cari hareket `fin_hesap_id` ile hesabın
        hareketi de olur (ayrı FinansHareket yazılmaz; çift sayım yok) ve fatura ile `tahsilat_belge_id` üzerinden bağlanır."""
        belge = self._belge_getir(belge_id)
        if belge.belge_turu != "fatura":
            raise BelgeHareketError("Tahsilat/ödeme yalnızca fatura için girilebilir.")
        if belge.hareket_durumu != "islendi":
            raise BelgeHareketError("Önce faturanın hareketlerini işleyin.")
        tutar = round(float(tutar or 0.0), 2)
        if tutar <= 0:
            raise BelgeHareketError("Tutar sıfırdan büyük olmalıdır.")
        if tutar > self.kalan_tutar(belge.id) + 0.005:
            raise BelgeHareketError("Tutar, faturanın kalan tutarını aşamaz.")
        hesap = self.db.get(FinansHesap, hesap_id) if hesap_id else None
        if hesap is None or hesap.is_deleted:
            raise BelgeHareketError("Kasa/banka hesabı seçilmelidir.")
        c = CariHareket(kaynak="tahsilat", tahsilat_belge_id=belge.id)
        try:
            self._cari._hazirla(c, {"customer_id": belge.customer_id, "tur": "tahsilat" if belge.yon != "alis" else "odeme", "tutar": tutar,
                                    "para_birimi": belge.currency or money_service.yerel_para(self.db), "kur": kur, "tarih": tarih or date.today(),
                                    "belge_no": belge.quotation_number, "odeme_araci": hesap.tur, "fin_hesap_id": hesap.id,
                                    "aciklama": aciklama or f"{belge.quotation_number} faturası {'tahsilatı' if belge.yon != 'alis' else 'ödemesi'}"})
        except CariHareketError as e:
            raise BelgeHareketError(str(e)) from e
        self.db.add(c)
        self.db.flush()
        fark = round(c.tutar * (c.kur - self._borc_kuru(belge)), 2) if c.para_birimi != money_service.yerel_para(self.db) else 0.0
        if kur_farki_isle and abs(fark) >= 0.005:
            # Tahsilat kuru borç kurundan yüksekse (satış) cari yerel bakiyesi alacaklıya döner; fark tersi yönde bir kur farkı hareketi ile kapanır.
            # Alış faturasında yön tersidir. Yerel para cinsinden yazılır.
            borc_yonlu = (fark > 0) == (belge.yon != "alis")
            kf = CariHareket(kaynak="kur_farki", tahsilat_belge_id=belge.id, iliskili_hareket_id=c.id)
            try:
                self._cari._hazirla(kf, {"customer_id": belge.customer_id, "tur": "kur_farki", "yon": "borc" if borc_yonlu else "alacak", "tutar": abs(fark),
                                         "para_birimi": money_service.yerel_para(self.db), "tarih": c.tarih, "belge_no": belge.quotation_number,
                                         "aciklama": f"{belge.quotation_number} kur farkı (tahsilat kuru {c.kur:g}, borç kuru {self._borc_kuru(belge):g})"})
            except CariHareketError as e:
                raise BelgeHareketError(str(e)) from e
            self.db.add(kf)
        self.db.commit()
        return c

    def tahsilat_kaldir(self, cari_hareket_id: int) -> None:
        """Tahsilatı görünümden kaldırır (silme = gizleme); cari ve hesap bakiyesi eski haline döner."""
        c = self.db.get(CariHareket, cari_hareket_id)
        if c is None or c.is_deleted or not c.tahsilat_belge_id:
            raise BelgeHareketError("Tahsilat kaydı bulunamadı.")
        c.is_deleted = True
        for kf in self.db.scalars(select(CariHareket).where(CariHareket.iliskili_hareket_id == c.id, CariHareket.tur == "kur_farki",
                                                             CariHareket.is_deleted == False)):  # noqa: E712
            kf.is_deleted = True                                              # bağlı kur farkı hareketi birlikte gizlenir
        self.db.commit()

    def kur_farki_faturasi_olustur(self, kur_farki_hareket_id: int) -> Quotation:
        """Cariye işlenmiş bir kur farkı hareketini (bkz. `tahsilat_ekle(..., kur_farki_isle=True)`) GERÇEK,
        numaralı bir fatura TASLAĞINA dönüştürür. Türk vergi mevzuatında ayrı bir "kur farkı faturası" belge
        TÜRÜ yoktur (GİB e-Fatura sisteminde özel bir senaryo taşımaz) — bu, tek satırı kur farkı tutarı olan
        SIRADAN bir satış/alış faturasıdır (KDVK Md. 24 gereği lehte kur farkları KDV matrahına dahildir).
        Taslak döner (`status='draft'`, `hareket_durumu='islenmedi'`); kullanıcı KDV oranını/açıklamayı
        düzenleyip normal fatura akışıyla (`isle()`) resmileştirir. Aynı kur farkı hareketi için ikinci kez
        çağrılırsa (kullanıcı zaten fatura kesmişse) var olan taslağı döner, yinelenen fatura üretmez."""
        kf = self.db.get(CariHareket, kur_farki_hareket_id)
        if kf is None or kf.is_deleted or kf.tur != "kur_farki":
            raise BelgeHareketError("Kur farkı hareketi bulunamadı.")
        if not kf.tahsilat_belge_id:
            raise BelgeHareketError("Kur farkının bağlı olduğu fatura bulunamadı.")
        orijinal = self._belge_getir(kf.tahsilat_belge_id)
        isaret = f"[kur_farki:{kf.id}]"
        mevcut = self.db.scalar(select(Quotation).where(Quotation.kaynak_belge_id == orijinal.id, Quotation.belge_turu == "fatura",
                                                         Quotation.notes.like(f"%{isaret}%"), Quotation.is_deleted == False))  # noqa: E712
        if mevcut is not None:
            return mevcut
        yon = orijinal.yon or "satis"
        yerel = money_service.yerel_para(self.db)
        b = Quotation(company_id=orijinal.company_id, quotation_number=self._sonraki_no("fatura", yon),
                     belge_turu="fatura", yon=yon, quotation_type=bt.quotation_type_of("fatura"),
                     customer_id=orijinal.customer_id, currency=yerel, exchange_rate=1.0,
                     issue_date=datetime.utcnow(), date=datetime.utcnow(), status="draft",
                     kaynak_belge_id=orijinal.id, notes=f"{orijinal.quotation_number} faturası kur farkı {isaret}")
        self.db.add(b)
        self.db.flush()
        kdv_oran = next((l.vat_rate for l in orijinal.lines if l.vat_rate), 0.0)  # varsayım: orijinal faturanın KDV oranı
        tutar_kdv_haric = round(kf.tutar / (1 + kdv_oran / 100.0), 2)
        l = QuotationLine(quotation_id=b.id, line_order=1, name=f"Kur Farkı — {orijinal.quotation_number}",
                          quantity=1, unit="Adet", unit_price=tutar_kdv_haric, vat_rate=kdv_oran,
                          doviz=yerel, kur=1.0, stok_etkisi="kendi", total_amount=tutar_kdv_haric, total_price=tutar_kdv_haric)
        self.db.add(l)
        self.db.flush()
        self._toplamlari_hesapla(b)
        self.db.commit()
        return b

    # ---- çoklu irsaliye → tek fatura, sipariş → irsaliye ------------------------------------
    def faturalanabilir(self, irsaliye_id: int) -> list[dict]:
        irsaliye = self._belge_getir(irsaliye_id)
        return [{"satir": s, "kalan": round((s.quantity or 0) - (s.faturalanan or 0), 6)}
                for s in sorted(irsaliye.lines, key=lambda x: x.line_order or 0) if round((s.quantity or 0) - (s.faturalanan or 0), 6) > 1e-9]

    def sevk_edilebilir(self, siparis_id: int) -> list[dict]:
        siparis = self._belge_getir(siparis_id)
        return [{"satir": s, "kalan": round((s.quantity or 0) - (s.sevk_edilen or 0), 6)}
                for s in sorted(siparis.lines, key=lambda x: x.line_order or 0) if round((s.quantity or 0) - (s.sevk_edilen or 0), 6) > 1e-9]

    def _cikti_belge_olustur(self, kaynaklar: list[Quotation], belge_turu: str, *, fis_no: str | None, tarih: datetime | None,
                             kaynak_belge_id: int | None, depo_id_override: int | None = None) -> Quotation:
        ilk = kaynaklar[0]
        b = Quotation(company_id=ilk.company_id, quotation_number=(fis_no or "").strip() or self._sonraki_no(belge_turu, ilk.yon, tarih),
                     belge_turu=belge_turu, yon=ilk.yon, quotation_type=bt.quotation_type_of(belge_turu), customer_id=ilk.customer_id,
                     customer_name_free=ilk.customer_name_free, currency=ilk.currency or "TRY", exchange_rate=ilk.exchange_rate or 1.0,
                     depo_id=depo_id_override or ilk.depo_id, issue_date=tarih or datetime.utcnow(), date=tarih or datetime.utcnow(),
                     status="draft", kaynak_belge_id=kaynak_belge_id)
        self.db.add(b)
        self.db.flush()
        return b

    @staticmethod
    def _satir_ekle(hedef: Quotation, kaynak_satir: QuotationLine, miktar: float, i: int, stok_etkisi: str) -> QuotationLine:
        tutar = round((kaynak_satir.unit_price or 0.0) * miktar * (1 - (kaynak_satir.discount_rate or 0.0) / 100), 2)
        return QuotationLine(quotation_id=hedef.id, product_id=kaynak_satir.product_id, line_order=i, sku=kaynak_satir.sku,
                             name=kaynak_satir.name, unit=kaynak_satir.unit, quantity=miktar, unit_price=kaynak_satir.unit_price,
                             discount_rate=kaynak_satir.discount_rate, vat_rate=kaynak_satir.vat_rate, currency=kaynak_satir.currency,
                             doviz=kaynak_satir.doviz, kur=kaynak_satir.kur,
                             depo_id=kaynak_satir.depo_id, stok_etkisi=stok_etkisi, total_amount=tutar, total_price=tutar)

    def _toplamlari_hesapla(self, belge: Quotation) -> None:
        yerel = money_service.yerel_para(self.db)
        satirlar = [belge_hesap.satir_netten(l.total_amount or 0.0, l.vat_rate or 0.0,
                                             (l.kur or 1.0) if (l.doviz or yerel).upper() != yerel else 1.0, kdv_yuvarla=2)
                    for l in belge.lines]                    # döviz satırı yerel para karşılığıyla
        t = belge_hesap.belge_toplami(satirlar)
        belge.subtotal = round(t.kdv_matrahi, 2)
        belge.total_vat = belge.vat_total = round(t.kdv_toplam, 2)
        belge.grand_total = round(t.kdv_matrahi + t.kdv_toplam, 2)

    def irsaliyeden_fatura(self, irsaliye_idleri: list[int], *, fis_no: str | None = None, tarih: datetime | None = None,
                           miktarlar: dict[int, float] | None = None) -> Quotation:
        """Bir ya da birden çok irsaliyenin faturalanmamış (ya da `miktarlar`da belirtilen) miktarını tek faturada birleştirir.
        Oluşan fatura satırları `stok_etkisi='kaynaktan'` olduğundan `isle()` çağrılınca stok tekrar düşmez."""
        if not irsaliye_idleri:
            raise BelgeHareketError("En az bir irsaliye seçilmelidir.")
        irsaliyeler = [self._belge_getir(i) for i in irsaliye_idleri]
        ilk = irsaliyeler[0]
        for irs in irsaliyeler:
            if irs.belge_turu != "irsaliye":
                raise BelgeHareketError(f"{irs.quotation_number}: irsaliye değil.")
            if irs.customer_id != ilk.customer_id or irs.yon != ilk.yon:
                raise BelgeHareketError("Seçilen irsaliyeler aynı cariye ve aynı yöne (satış/alış) ait olmalıdır.")
        try:
            self.uyarilar = list(BelgeKilitServisi(self.db).irsaliye_fatura_kontrol(irsaliyeler, tarih))          # kilit + ay aşımı kuralları
        except KilitHatasi as e:
            raise BelgeHareketError(str(e)) from e
        kalemler = []
        for irs in irsaliyeler:
            for satir in sorted(irs.lines, key=lambda x: x.line_order or 0):
                kalan = round((satir.quantity or 0) - (satir.faturalanan or 0), 6)
                istenen = (miktarlar or {}).get(satir.id, kalan) if miktarlar is not None else kalan
                if istenen <= 1e-9:
                    continue
                if istenen - kalan > 1e-6:
                    raise BelgeHareketError(f"{irs.quotation_number} satır {satir.line_order}: kalan {kalan:g}, istenen {istenen:g}.")
                kalemler.append((satir, istenen))
        if not kalemler:
            raise BelgeHareketError("Faturalanacak miktar yok.")
        try:
            fatura = self._cikti_belge_olustur(irsaliyeler, "fatura", fis_no=fis_no, tarih=tarih,
                                              kaynak_belge_id=ilk.id if len(irsaliyeler) == 1 else None)
            for i, (satir, miktar) in enumerate(kalemler, start=1):
                fl = self._satir_ekle(fatura, satir, miktar, i, "kaynaktan")
                self.db.add(fl)
                self.db.flush()
                self.db.add(BelgeBag(kaynak_satir_id=satir.id, hedef_satir_id=fl.id, miktar=miktar, tur="fatura"))
                satir.faturalanan = round((satir.faturalanan or 0) + miktar, 6)
            self._toplamlari_hesapla(fatura)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return fatura

    def siparisden_irsaliye(self, siparis_id: int, *, fis_no: str | None = None, tarih: datetime | None = None,
                            miktarlar: dict[int, float] | None = None, depo_id: int | None = None) -> Quotation:
        """Siparişin sevk edilmemiş (ya da `miktarlar`da belirtilen) miktarı için irsaliye oluşturur; sipariş satırının
        aktif rezervlerini (varsa) sevk edilen miktar kadar düşer/kapatır."""
        siparis = self._belge_getir(siparis_id)
        if siparis.belge_turu != "siparis":
            raise BelgeHareketError("Yalnızca siparişten irsaliye oluşturulabilir.")
        kalemler = []
        for satir in sorted(siparis.lines, key=lambda x: x.line_order or 0):
            kalan = round((satir.quantity or 0) - (satir.sevk_edilen or 0), 6)
            istenen = (miktarlar or {}).get(satir.id, kalan) if miktarlar is not None else kalan
            if istenen <= 1e-9:
                continue
            if istenen - kalan > 1e-6:
                raise BelgeHareketError(f"Satır {satir.line_order}: kalan {kalan:g}, istenen {istenen:g}.")
            kalemler.append((satir, istenen))
        if not kalemler:
            raise BelgeHareketError("Sevk edilecek miktar yok.")
        try:
            irsaliye = self._cikti_belge_olustur([siparis], "irsaliye", fis_no=fis_no, tarih=tarih, kaynak_belge_id=siparis.id,
                                                depo_id_override=depo_id)
            for i, (satir, miktar) in enumerate(kalemler, start=1):
                il = self._satir_ekle(irsaliye, satir, miktar, i, "kendi")
                il.depo_id = satir.depo_id or irsaliye.depo_id
                self.db.add(il)
                self.db.flush()
                self.db.add(BelgeBag(kaynak_satir_id=satir.id, hedef_satir_id=il.id, miktar=miktar, tur="sevk"))
                satir.sevk_edilen = round((satir.sevk_edilen or 0) + miktar, 6)
                self._rezerv_dus(satir.id, miktar)
            self._toplamlari_hesapla(irsaliye)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return irsaliye

    def _rezerv_dus(self, siparis_satir_id: int, miktar: float) -> None:
        kalan = miktar
        for r in self.db.scalars(select(StokRezerv).where(StokRezerv.siparis_satir_id == siparis_satir_id, StokRezerv.durum == "aktif",
                                                          StokRezerv.is_deleted == False).order_by(StokRezerv.id)):  # noqa: E712
            if kalan <= 1e-9:
                break
            if r.miktar <= kalan + 1e-9:
                kalan = round(kalan - r.miktar, 6)
                r.miktar, r.durum = 0.0, "kullanildi"
            else:
                r.miktar = round(r.miktar - kalan, 6)
                kalan = 0.0

    # ---- iade -------------------------------------------------------------------------------
    def iade(self, belge_id: int, *, satirlar: dict[int, float] | None = None, fis_no: str | None = None,
            tarih: datetime | None = None) -> Quotation:
        """Fatura ya da irsaliyeye bağlı iade belgesi (taslak) oluşturur; `isle()` çağrılınca ters yönde stok/cari hareketi üretir.
        `satirlar` verilmezse kaynağın tüm miktarları iade edilir; kısmi iade `satirlar={satir_id: miktar}` ile yapılır."""
        kaynak = self._belge_getir(belge_id)
        if kaynak.belge_turu not in ("fatura", "irsaliye"):
            raise BelgeHareketError("Yalnızca fatura veya irsaliye iade edilebilir.")
        kalemler = []
        for satir in sorted(kaynak.lines, key=lambda x: x.line_order or 0):
            miktar = satir.quantity if satirlar is None else satirlar.get(satir.id, 0)   # verilirse yalnız listelenen satırlar
            if not miktar or miktar <= 1e-9:
                continue
            if miktar - (satir.quantity or 0) > 1e-6:
                raise BelgeHareketError(f"Satır {satir.line_order}: iade miktarı {miktar:g}, orijinal {satir.quantity:g}'den fazla olamaz.")
            kalemler.append((satir, miktar))
        if not kalemler:
            raise BelgeHareketError("İade edilecek satır yok.")
        try:
            iade_belge = self._cikti_belge_olustur([kaynak], "iade_fatura", fis_no=fis_no, tarih=tarih, kaynak_belge_id=kaynak.id)
            for i, (satir, miktar) in enumerate(kalemler, start=1):
                il = self._satir_ekle(iade_belge, satir, miktar, i, "kendi")
                self.db.add(il)
                self.db.flush()
                self.db.add(BelgeBag(kaynak_satir_id=satir.id, hedef_satir_id=il.id, miktar=miktar, tur="iade"))
            self._toplamlari_hesapla(iade_belge)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return iade_belge

    # ---- sipariş rezervi ----------------------------------------------------------------------
    def rezerv_olustur(self, siparis_id: int, siparis_satir_id: int | None, product_id: int, miktar: float, *,
                       depo_id: int | None = None, bitis: date | None = None, musteri_donus_bekle: bool = False,
                       aciklama: str | None = None) -> StokRezerv:
        if miktar <= 0:
            raise BelgeHareketError("Rezerv miktarı sıfırdan büyük olmalıdır.")
        siparis = self._belge_getir(siparis_id)
        if siparis.belge_turu != "siparis":
            raise BelgeHareketError("Rezerv yalnızca sipariş için oluşturulabilir.")
        r = StokRezerv(siparis_id=siparis_id, siparis_satir_id=siparis_satir_id, product_id=product_id, depo_id=depo_id,
                       miktar=float(miktar), bitis=bitis, musteri_donus_bekle=bool(musteri_donus_bekle), durum="aktif", aciklama=aciklama)
        self.db.add(r)
        self.db.commit()
        return r

    def rezerv_serbest_birak(self, rezerv_id: int) -> None:
        r = self.db.get(StokRezerv, rezerv_id)
        if r is None or r.is_deleted:
            raise BelgeHareketError("Rezerv bulunamadı.")
        if r.durum != "aktif":
            raise BelgeHareketError("Yalnızca aktif rezerv serbest bırakılabilir.")
        r.durum = "serbest"
        self.db.commit()

    def rezerv_suresi_dolanlari_kapat(self, simdi: date | None = None) -> int:
        """Süresi geçmiş, müşteri dönüşü beklenmeyen aktif rezervleri kapatır. @return kapatılan sayı"""
        simdi = simdi or date.today()
        n = 0
        for r in self.db.scalars(select(StokRezerv).where(StokRezerv.durum == "aktif", StokRezerv.is_deleted == False,  # noqa: E712
                                                          StokRezerv.bitis.is_not(None), StokRezerv.bitis < simdi,
                                                          StokRezerv.musteri_donus_bekle == False)):  # noqa: E712
            r.durum = "suresi_doldu"
            n += 1
        if n:
            self.db.commit()
        return n
