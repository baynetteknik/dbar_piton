"""TOYA ERP - Ödeme Planı Otomasyon Servisi.

Fatura kaydedilince, seçilen Ödeme Planı'na göre otomatik kasa/banka fişi oluşturur (bkz.
gelistirme/04_odeme_planlari/tasarim.md). Manuel girişle AYNI `FinansFisService` kod yolunu kullanır —
iki paralel "fiş yaratma" yolu yoktur.

Faz 04.07-04.09: `nakit` → Kasa Tahsilat; `havale_eft`/`kredi_karti`/`pos` → Banka fişi ("Gelen Havale"
türüyle — bu üçü için ayrı fiş türü kodu yok, hesabın kendisi zaten `FinansHesap.tur` ile ayrışıyor).
POS'un BANKAYA otomatik aktarımı ayrı bir servistir (`pos_mahsup_servisi.py`).

Faz 04.11: ÇOK SATIRLI Ödeme Planı — kullanıcı isteği: "yarısı peşin yarısı taksitle ya da bir bölümü
açık hesap bir bölümü banka havalesi ve kalanı kredi kartı gibi". `PaymentPlan.satirlar` doluysa HER
satır kendi `odeme_tipi`'ne göre AYRI bir fiş üretir; tutar `PaymentPlanLine.tutar_formulu` ile hesaplanır
(bkz. `odeme_formul_motoru.py` — TOYA'ya özgü değişken sözlüğü: TUTAR/ARATOPLAM/KDV/KALAN + dört işlem +
round/abs/min/max/sum). `satirlar` BOŞSA (çoğu plan — basit/tek tip, 04.05-04.09'dan beri değişmedi) plan KENDİ eski
alanlarını (`odeme_tipi`/`hedef_finans_hesap_id`) tek bir "TUTAR" formüllü satırmış gibi kullanır — geriye
dönük TAM uyumlu, mevcut davranış hiç değişmez.

Belge her kaydedildiğinde (yeni ya da güncelleme) çağrılır, bir `OtomasyonSonucu` LİSTESİ döner (0, 1 ya
da N — çok satırlı planda N fiş). Otomasyon koşulları sağlanmıyorsa (ödeme planı yok / tanınmayan tip /
hedef hesap seçilmemiş / formül hatası vb.) o satır SESSİZCE atlanır — bu bir hata değildir. Artık
geçerliliği kalmamış (önceki kayıtta vardı, bu kayıtta yok/değişti) eski otomatik fişler GERİ ALINIR
(gizlenir) — otomasyon asla eski, artık geçersiz bir fişi ortada bırakmaz."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from src.core import belge_turleri
from src.core.models import FinansFis, FinansHareket, PaymentPlan, Quotation
from src.desktop.services import odeme_formul_motoru
from src.desktop.services.finans_fis_service import FinansFisError, FinansFisService
from src.desktop.services.odeme_formul_motoru import OdemeFormulHatasi

#: odeme_tipi -> (fiş grubu, fiş/satır türü, kullanıcıya gösterilecek etiket).
_AKIŞLAR: dict[str, tuple[str, str, str]] = {
    "nakit": ("kasa", "kasa_tahsilat", "Kasa Tahsilat"),
    "havale_eft": ("banka", "havale_gelen", "Gelen Havale"),
    "kredi_karti": ("banka", "havale_gelen", "Kredi Kartı Tahsilatı"),
    "pos": ("banka", "havale_gelen", "POS Tahsilatı"),
}


@dataclass
class OtomasyonSonucu:
    fis: FinansFis
    etiket: str   # ör. "Kasa Tahsilat" — kullanıcıya gösterilecek bildirimde kullanılır
    tutar: float = 0.0


@dataclass
class _SatirSpec:
    satir_no: int | None   # None = eski tek-tip (header düzeyi, 04.05-04.09) plan
    odeme_tipi: str | None
    tutar_formulu: str | None
    hedef_finans_hesap_id: int | None


class OdemePlaniOtomasyonServisi:
    def __init__(self, db) -> None:
        self.db = db
        self._fis_svc = FinansFisService(db)

    def belge_kaydedildi(self, q: Quotation) -> list[OtomasyonSonucu]:
        """Belge kaydedildikten SONRA (commit sonrası) çağrılır."""
        plan: PaymentPlan | None = q.payment_plan_ref
        if q.belge_turu not in belge_turleri.CARI_ETKILI or plan is None or not plan.otomatik_fis_olustur:
            self._gecersiz_satirlari_gizle(q.id, gecerli_satir_no=set())
            return []

        specs = (
            [_SatirSpec(s.sira_no, s.odeme_tipi, s.tutar_formulu, s.hedef_finans_hesap_id) for s in plan.satirlar]
            if plan.satirlar
            else [_SatirSpec(None, plan.odeme_tipi, "TUTAR", plan.hedef_finans_hesap_id)]
        )

        sonuclar: list[OtomasyonSonucu] = []
        kalan = q.grand_total or 0.0
        gecerli_satir_no: set[int | None] = set()
        for spec in specs:
            baglam = odeme_formul_motoru.baglam_olustur(
                tutar=q.grand_total or 0.0, aratoplam=q.subtotal or 0.0, kdv=q.total_vat or 0.0, kalan=kalan,
            )
            try:
                tutar = odeme_formul_motoru.degerlendir(spec.tutar_formulu, baglam)
            except OdemeFormulHatasi:
                continue   # bozuk formül — bu satır atlanır, diğer satırlar denenmeye devam eder
            kalan = round(kalan - tutar, 2)

            akis = _AKIŞLAR.get(spec.odeme_tipi) if spec.odeme_tipi else None
            if akis is None or not spec.hedef_finans_hesap_id or tutar <= 0:
                continue
            grup, tur, etiket = akis
            mevcut = self._fis_bul(q.id, spec.satir_no)
            sonuc = self._fis_olustur_veya_guncelle(
                q, mevcut, grup, tur, etiket, spec.hedef_finans_hesap_id, tutar, spec.satir_no,
            )
            if sonuc:
                sonuclar.append(sonuc)
                gecerli_satir_no.add(spec.satir_no)

        self._gecersiz_satirlari_gizle(q.id, gecerli_satir_no)
        return sonuclar

    def _fis_bul(self, belge_id: int, satir_no: int | None) -> FinansFis | None:
        kosul = [FinansFis.kaynak_belge_id == belge_id, FinansFis.is_deleted == False]  # noqa: E712
        kosul.append(FinansFis.kaynak_belge_satir_no.is_(None) if satir_no is None else FinansFis.kaynak_belge_satir_no == satir_no)
        return self.db.scalar(select(FinansFis).where(*kosul))

    def _gecersiz_satirlari_gizle(self, belge_id: int, gecerli_satir_no: set[int | None]) -> None:
        """Bu belgeden daha önce otomatik oluşmuş ama bu kayıtta artık karşılığı olmayan (satır
        silinmiş/tipi değişmiş/formülü artık 0 veya negatif üreten) fişleri geri alır."""
        eski = self.db.scalars(
            select(FinansFis).where(FinansFis.kaynak_belge_id == belge_id, FinansFis.is_deleted == False),  # noqa: E712
        ).all()
        for fis in eski:
            if fis.kaynak_belge_satir_no not in gecerli_satir_no:
                self._fis_svc.fis_gizle(fis.id)

    def _fis_olustur_veya_guncelle(
        self, q: Quotation, mevcut: FinansFis | None, grup: str, tur: str, etiket: str,
        hedef_hesap_id: int, tutar: float, satir_no: int | None,
    ) -> OtomasyonSonucu | None:
        satir = {
            "tur": tur, "hesap_id": hedef_hesap_id,
            "customer_id": q.customer_id, "tutar": tutar,
            "para_birimi": q.currency, "kur": q.exchange_rate,
            "belge_no": q.quotation_number,
            "aciklama": f"{q.quotation_number} nolu faturadan otomatik {etiket.lower()}",
        }
        if mevcut:
            # Aynı satırı GÜNCELLER (yeni satır + eskisini gizleme değil) — her kayıtta fiş geçmişi şişmesin.
            onceki = self.db.scalar(
                select(FinansHareket).where(FinansHareket.fis_id == mevcut.id, FinansHareket.is_deleted == False),  # noqa: E712
            )
            if onceki:
                satir["id"] = onceki.id
        try:
            fis = self._fis_svc.fis_kaydet(
                {
                    "grup": grup, "varsayilan_tur": tur,
                    "tarih": q.issue_date.date() if q.issue_date else None,
                    "belge_no": q.quotation_number,
                    "aciklama1": f"{q.quotation_number} nolu faturadan otomatik",
                },
                [satir],
                fis_id=mevcut.id if mevcut else None,
            )
        except FinansFisError:
            return None   # ör. hesap/para birimi uyuşmazlığı — otomasyon sessizce atlanır, kullanıcı manuel girer
        fis.kaynak_belge_id = q.id
        fis.kaynak_belge_satir_no = satir_no
        self.db.commit()
        return OtomasyonSonucu(fis=fis, etiket=etiket, tutar=tutar)
