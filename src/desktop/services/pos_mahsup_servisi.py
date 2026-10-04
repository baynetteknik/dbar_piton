"""TOYA ERP - POS → Banka Parametrik Otomatik Mahsup Servisi.

04.09 (bkz. gelistirme/04_odeme_planlari/tasarim.md): her POS hesabı için `pos_otomatik_mahsup` açıksa ve
bir `pos_hedef_hesap_id` seçiliyse, valörü (hareket tarihi + `FinansHesap.valor_gun`) geçmiş ama henüz
bankaya aktarılmamış POS tahsilat satırlarını (para birimi bazında) toplayıp TEK bir virman fişiyle hedef
banka hesabına aktarır. Gerçek bir arka plan zamanlayıcısı YOK — bu fonksiyon "vadesi gelenleri tara"
tetikleyicisidir: Banka Hareketleri ekranı her açıldığında (bkz. `finans_hareket_screen.py`) çağrılır.
Manuel virman girişiyle AYNI `FinansFisService` kod yolunu kullanır."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select

from src.core.models import FinansFis, FinansHareket, FinansHesap
from src.desktop.services.finans_fis_service import FinansFisError, FinansFisService


@dataclass
class MahsupSonucu:
    pos_hesap: FinansHesap
    fis: FinansFis
    tutar: float
    para_birimi: str


@dataclass
class BekleyenBakiye:
    pos_hesap: FinansHesap
    vadesi_gelmis: dict[str, float]     # {para_birimi: tutar} — mahsup edilebilir
    vadesi_gelmemis: dict[str, float]   # {para_birimi: tutar} — valör günü henüz dolmamış
    en_eski_tarih: date | None


def _bekleyen_hareketler(db, pos: FinansHesap) -> list[FinansHareket]:
    return list(db.scalars(
        select(FinansHareket).where(
            FinansHareket.hesap_id == pos.id, FinansHareket.yon == "giris",
            FinansHareket.is_deleted == False, FinansHareket.mahsup_virman_id.is_(None),  # noqa: E712
        ),
    ))


def bekleyen_bakiyeler(db, bugun: date | None = None) -> list[BekleyenBakiye]:
    """POS Mahsup Takip ekranı için: her aktif POS hesabının henüz bankaya aktarılmamış bakiyesini,
    vadesi gelmiş / gelmemiş olarak ayırıp döner. Bekleyen hiçbir hareketi olmayan POS hesapları listeye
    hiç girmez (ekranı boş hesaplarla doldurmamak için)."""
    bugun = bugun or date.today()
    sonuc: list[BekleyenBakiye] = []
    pos_hesaplari = db.scalars(
        select(FinansHesap).where(
            FinansHesap.tur == "pos", FinansHesap.is_deleted == False, FinansHesap.aktif == True,  # noqa: E712
        ).order_by(FinansHesap.kod),
    ).all()
    for pos in pos_hesaplari:
        bekleyenler = _bekleyen_hareketler(db, pos)
        if not bekleyenler:
            continue
        valor = timedelta(days=pos.valor_gun or 0)
        gelmis: dict[str, float] = defaultdict(float)
        gelmemis: dict[str, float] = defaultdict(float)
        en_eski = None
        for h in bekleyenler:
            hedef = gelmis if h.tarih + valor <= bugun else gelmemis
            hedef[h.para_birimi] += h.tutar
            en_eski = h.tarih if en_eski is None else min(en_eski, h.tarih)
        sonuc.append(BekleyenBakiye(
            pos_hesap=pos, vadesi_gelmis=dict(gelmis), vadesi_gelmemis=dict(gelmemis), en_eski_tarih=en_eski,
        ))
    return sonuc


def _hesabi_mahsup_et(db, fis_svc: FinansFisService, pos: FinansHesap, bugun: date) -> list[MahsupSonucu]:
    """Tek bir POS hesabının vadesi gelmiş bakiyesini (para birimi bazında) hedef hesaba aktarır.
    `vadesi_gelenleri_tara` (otomatik) ve `tek_hesabi_mahsup_et` (manuel, "Tahsil Et" butonu) ortak çekirdeği —
    aralarındaki tek fark hangi POS hesaplarının bu fonksiyona verildiğidir."""
    if not pos.pos_hedef_hesap_id:
        return []
    valor = timedelta(days=pos.valor_gun or 0)
    bekleyenler = [h for h in _bekleyen_hareketler(db, pos) if h.tarih + valor <= bugun]
    if not bekleyenler:
        return []

    gruplar: dict[str, list[FinansHareket]] = defaultdict(list)
    for h in bekleyenler:
        gruplar[h.para_birimi].append(h)

    sonuclar: list[MahsupSonucu] = []
    for para_birimi, hareketler in gruplar.items():
        toplam = sum(h.tutar for h in hareketler)
        if toplam <= 0:
            continue
        try:
            fis = fis_svc.fis_kaydet(
                {
                    "grup": "banka", "varsayilan_tur": "banka_virman", "tarih": bugun,
                    "aciklama1": f"{pos.kod} POS mahsup ({len(hareketler)} işlem)",
                },
                [{
                    "tur": "banka_virman", "hesap_id": pos.id, "karsi_hesap_id": pos.pos_hedef_hesap_id,
                    "tutar": toplam, "para_birimi": para_birimi,
                    "aciklama": f"{pos.kod} → POS mahsubu ({len(hareketler)} işlem)",
                }],
            )
        except FinansFisError:
            continue   # ör. hedef hesap döviz kısıtı uyuşmazlığı — bu hesap atlanır, diğerleri denenir
        virman_satiri = db.scalar(
            select(FinansHareket).where(FinansHareket.fis_id == fis.id, FinansHareket.is_deleted == False),  # noqa: E712
        )
        for h in hareketler:
            h.mahsup_virman_id = virman_satiri.id
        db.commit()
        sonuclar.append(MahsupSonucu(pos_hesap=pos, fis=fis, tutar=toplam, para_birimi=para_birimi))
    return sonuclar


def vadesi_gelenleri_tara(db, bugun: date | None = None) -> list[MahsupSonucu]:
    """Otomatik mahsup açık, vadesi gelmiş bakiyesi olan her POS hesabı için bir virman fişi oluşturur.
    Hiçbir POS hesabının vadesi gelmemişse boş liste döner — bu normal bir durumdur, hata değildir."""
    bugun = bugun or date.today()
    fis_svc = FinansFisService(db)
    pos_hesaplari = db.scalars(
        select(FinansHesap).where(
            FinansHesap.tur == "pos", FinansHesap.is_deleted == False, FinansHesap.aktif == True,  # noqa: E712
            FinansHesap.pos_otomatik_mahsup == True, FinansHesap.pos_hedef_hesap_id.is_not(None),  # noqa: E712
        ),
    ).all()
    sonuclar: list[MahsupSonucu] = []
    for pos in pos_hesaplari:
        sonuclar.extend(_hesabi_mahsup_et(db, fis_svc, pos, bugun))
    return sonuclar


def tek_hesabi_mahsup_et(db, pos_hesap_id: int, bugun: date | None = None) -> list[MahsupSonucu]:
    """"POS Mahsup Takip" ekranındaki "Tahsil Et" butonu: `pos_otomatik_mahsup` kapalı olan (ya da açık
    olsa bile kullanıcının beklemeden erkenden tetiklemek istediği) bir POS hesabını, otomatik-mahsup
    bayrağına BAKMAKSIZIN manuel olarak mahsup eder — yine de yalnız vadesi (valör) gelmiş tutarı aktarır."""
    bugun = bugun or date.today()
    pos = db.get(FinansHesap, pos_hesap_id)
    if pos is None or pos.is_deleted or pos.tur != "pos":
        return []
    return _hesabi_mahsup_et(db, FinansFisService(db), pos, bugun)
