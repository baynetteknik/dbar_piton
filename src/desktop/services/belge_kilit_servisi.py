"""TOYA ERP - Belge zinciri kilit / bağ yönetimi (esnek, kuralcı olmayan).

İlke (kullanıcı kararı): bağlantı kuralları varsayılan olarak UYARIR ve devam ettirir; bloklama yalnız gerekli yerlerde. Her kuralın sertliği
ayarlanabilir (`engelle` | `uyar` | `serbest`, `system_settings` → `belge.kilit.<kural>`). Silme, bağ koparma ve kural kararları
`BelgeIslemLogu`'na yazılır; müşteri itiraz ederse gösterilir. Kullanıcı bir yola zorlanmaz: bağ koparma, bağlı belgeyi de silme ya da
bağlı belgeyi bırakma seçenekleri vardır. Hiçbir belge fiziksel silinmez (gizlenir).

Kavramlar: `altlar` = bu belgeden türeyen belgeler (irsaliyenin faturası, teklifin siparişi); `ustler` = bu belgenin kaynağı (faturanın irsaliyeleri).
Fatura silinince irsaliyeler serbest kalır (yeniden faturalanabilir) ya da isteğe bağlı birlikte silinir. Faturaya bağlı irsaliye başka faturaya
bağlanamaz (kural `irsaliye_tek_fatura`); çözüm faturayı silmek ya da bağı koparmaktır. Logo gibi otomatik irsaliye üretilmez."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select

from src.core.models import BelgeBag, BelgeIslemLogu, Quotation, QuotationLine
from src.desktop.services import numara_servisi, settings_store

SEVIYELER = {"engelle": "Engelle", "uyar": "Uyar ve devam et", "serbest": "Serbest"}
#: kural -> (açıklama, varsayılan seviye)
KURALLAR: dict[str, tuple[str, str]] = {
    "irsaliye_tek_fatura": ("Zaten faturalanmış irsaliyeyi başka bir faturaya bağlama", "engelle"),
    "teklif_tek_siparis": ("Siparişe dönüşmüş teklifi ikinci bir siparişe dönüştürme", "engelle"),
    "bagli_belge_silme": ("Bağlı (alt) belgesi olan belgeyi silme", "uyar"),
    "resmi_belge_silme": ("e-Devlete gönderilmiş belgeyi silme", "engelle"),
    "donusmus_teklif_duzenleme": ("Siparişe dönüşmüş teklifi düzenleme", "uyar"),
    "irsaliye_ay_asimi": ("İrsaliyeyi düzenlendiği ay dışında faturalama", "uyar"),
}
_ANAHTAR = "belge.kilit."


class KilitHatasi(ValueError):
    """Kural işlemi engelledi; mesaj kullanıcıya gösterilebilir (çözüm önerisini içerir)."""


def seviye(db, kural: str) -> str:
    v = (settings_store.get_setting(db, _ANAHTAR + kural, "") or "").strip()
    return v if v in SEVIYELER else KURALLAR[kural][1]


def seviye_kaydet(db, kural: str, deger: str) -> None:
    if kural not in KURALLAR or deger not in SEVIYELER:
        raise ValueError("Geçersiz kilit kuralı ya da seviyesi.")
    settings_store.set_setting(db, _ANAHTAR + kural, deger, commit=True)


def _kullanici() -> str:
    try:
        from src.desktop.managers.permission_manager import PermissionManager
        u = PermissionManager().current_user
        return str(getattr(u, "username", None) or getattr(u, "name", None) or "") if u is not None else ""
    except Exception:  # noqa: BLE001 - günlük kullanıcı adı yüzünden işlem düşmesin
        return ""


@dataclass
class SilmePlani:
    belge: Quotation
    altlar: list[Quotation] = field(default_factory=list)
    ustler: list[Quotation] = field(default_factory=list)
    engel: str | None = None                       # varsa silinemez (mesaj)
    uyarilar: list[str] = field(default_factory=list)


class BelgeKilitServisi:
    def __init__(self, db) -> None:
        self.db = db

    # ---- günlük -------------------------------------------------------------------------------------
    def logla(self, belge: Quotation | None, islem: str, karar: str = "yapildi", kural: str | None = None, ayrinti: str = "") -> None:
        self.db.add(BelgeIslemLogu(belge_id=belge.id if belge is not None else None, belge_no=belge.quotation_number if belge is not None else None,
                                   islem=islem, kural=kural, karar=karar, kullanici=_kullanici(), ayrinti=ayrinti or None))

    def gunluk(self, belge_id: int) -> list[BelgeIslemLogu]:
        return list(self.db.scalars(select(BelgeIslemLogu).where(BelgeIslemLogu.belge_id == belge_id).order_by(BelgeIslemLogu.id)))

    def _uygula(self, belge: Quotation | None, kural: str, mesaj: str, islem: str) -> str | None:
        """Kuralın seviyesine göre: engelle → KilitHatasi; uyar → mesajı döner; serbest → None. Karar günlüğe yazılır."""
        sev = seviye(self.db, kural)
        if sev == "engelle":
            self.logla(belge, islem, "engellendi", kural, mesaj)
            self.db.commit()
            raise KilitHatasi(mesaj)
        self.logla(belge, islem, "uyarildi_devam" if sev == "uyar" else "serbest", kural, mesaj)
        return mesaj if sev == "uyar" else None

    # ---- ilişkiler ------------------------------------------------------------------------------------
    def _canli(self, ids) -> list[Quotation]:
        ids = [i for i in dict.fromkeys(ids) if i]
        if not ids:
            return []
        return list(self.db.scalars(select(Quotation).where(Quotation.id.in_(ids), Quotation.is_deleted == False)))  # noqa: E712

    def _bag_satirlari(self, belge: Quotation, hedef: bool) -> list[BelgeBag]:
        ids = [l.id for l in belge.lines]
        if not ids:
            return []
        alan = BelgeBag.hedef_satir_id if hedef else BelgeBag.kaynak_satir_id
        return list(self.db.scalars(select(BelgeBag).where(alan.in_(ids), BelgeBag.is_deleted == False)))  # noqa: E712

    def _belge_of_satir(self, satir_idleri) -> list[int]:
        if not satir_idleri:
            return []
        return list(self.db.scalars(select(QuotationLine.quotation_id).where(QuotationLine.id.in_(list(satir_idleri))).distinct()))

    def altlar(self, belge: Quotation) -> list[Quotation]:
        kaynakli = list(self.db.scalars(select(Quotation.id).where(Quotation.kaynak_belge_id == belge.id, Quotation.is_deleted == False)))  # noqa: E712
        bagli = self._belge_of_satir([b.hedef_satir_id for b in self._bag_satirlari(belge, hedef=False)])
        return [q for q in self._canli(kaynakli + bagli) if q.id != belge.id]

    def ustler(self, belge: Quotation) -> list[Quotation]:
        kaynakli = [belge.kaynak_belge_id] if belge.kaynak_belge_id else []
        bagli = self._belge_of_satir([b.kaynak_satir_id for b in self._bag_satirlari(belge, hedef=True)])
        return [q for q in self._canli(kaynakli + bagli) if q.id != belge.id]

    # ---- dönüşüm / bağlama kontrolleri (BelgeHareketService ve QuotationSaveService çağırır) ------------------------------
    def teklif_donusum_kontrol(self, teklif: Quotation) -> list[str]:
        """Teklif zaten bir siparişe dönüştüyse `teklif_tek_siparis` kuralı. Uyarı metinleri döner (engelde KilitHatasi)."""
        varolan = [q for q in self.altlar(teklif) if q.belge_turu == "siparis"]
        if not varolan:
            return []
        m = self._uygula(teklif, "teklif_tek_siparis", f"{teklif.quotation_number} teklifi zaten {varolan[0].quotation_number} siparişine dönüşmüş. "
                         "Çözüm: o siparişi silin, bağı koparın ya da teklifin satırlarını kopyalayıp yeni sipariş girin.", "teklif_siparise_donustur")
        return [m] if m else []

    def irsaliye_fatura_kontrol(self, irsaliyeler: list[Quotation], fatura_tarihi: date | datetime | None = None) -> list[str]:
        """İrsaliye(ler) faturalanmadan önce: `irsaliye_tek_fatura` (zaten faturalanmışsa) ve `irsaliye_ay_asimi` (ay dışı) kuralları."""
        uyarilar: list[str] = []
        ft = fatura_tarihi.date() if isinstance(fatura_tarihi, datetime) else (fatura_tarihi or date.today())
        for irs in irsaliyeler:
            if any((s.faturalanan or 0) > 1e-9 for s in irs.lines):
                m = self._uygula(irs, "irsaliye_tek_fatura", f"{irs.quotation_number} irsaliyesi zaten bir faturaya bağlı. Çözüm: o faturayı silin "
                                 "(irsaliye serbest kalır) ya da bağı koparın; sonra yeni faturada birden çok irsaliyeyi seçin.", "irsaliyeden_fatura")
                if m:
                    uyarilar.append(m)
            it = irs.date or irs.issue_date
            if it is not None and (it.year, it.month) != (ft.year, ft.month):
                m = self._uygula(irs, "irsaliye_ay_asimi", f"{irs.quotation_number} irsaliyesi {it.strftime('%m.%Y')} tarihli; faturası {ft.strftime('%m.%Y')} "
                                 "döneminde kesiliyor. İrsaliye düzenlendiği ay içinde faturalanmalıdır (süreleri mali müşavirinizle doğrulayın).", "irsaliyeden_fatura")
                if m:
                    uyarilar.append(m)
        return uyarilar

    def duzenleme_uyarisi(self, belge: Quotation) -> str | None:
        """Siparişe dönüşmüş teklif düzenlenirken kural mesajı (engelde KilitHatasi); yoksa None."""
        if belge.belge_turu != "teklif" or not any(q.belge_turu == "siparis" for q in self.altlar(belge)):
            return None
        return self._uygula(belge, "donusmus_teklif_duzenleme", f"{belge.quotation_number} teklifi siparişe dönüşmüş; değişiklik siparişe yansımaz.", "teklif_duzenle")

    # ---- silme --------------------------------------------------------------------------------------------
    def silme_plani(self, belge_id: int) -> SilmePlani:
        belge = self.db.get(Quotation, belge_id)
        if belge is None or belge.is_deleted:
            raise KilitHatasi("Belge bulunamadı.")
        p = SilmePlani(belge, self.altlar(belge), self.ustler(belge))
        if belge.resmi_gonderildi and seviye(self.db, "resmi_belge_silme") == "engelle":
            p.engel = f"{belge.quotation_number} e-Devlete gönderildi olarak işaretli; silinemez. Düzeltme için iade faturası kesin."
        elif belge.resmi_gonderildi:
            p.uyarilar.append(f"{belge.quotation_number} e-Devlete gönderilmiş; silmek karşı tarafla uyuşmazlığa yol açabilir.")
        if p.altlar and seviye(self.db, "bagli_belge_silme") != "serbest":
            p.uyarilar.append("Bağlı belgeler var: " + ", ".join(q.quotation_number for q in p.altlar) + ".")
        return p

    def sil(self, belge_id: int, *, alt_belgeleri_de_sil: bool = False, ust_belgeleri_de_sil: bool = False) -> list[int]:
        """Belgeyi gizler. Bağlı alt belgeler `alt_belgeleri_de_sil`e göre birlikte silinir ya da bağları koparılır (işlenmiş alt belgenin bağı
        stok kaybı olmasın diye koparılamaz). Üst belgeler (fatura silinince irsaliyeler) `ust_belgeleri_de_sil`e göre silinir, aksi halde
        serbest kalır. Silinen belge id'leri döner. Hata olursa hiçbir şey yazılmaz."""
        silinen: list[int] = []
        try:
            plan = self.silme_plani(belge_id)
            if plan.engel:
                self.logla(plan.belge, "sil", "engellendi", "resmi_belge_silme", plan.engel)
                self.db.commit()
                raise KilitHatasi(plan.engel)
            if plan.altlar and not alt_belgeleri_de_sil and seviye(self.db, "bagli_belge_silme") == "engelle":
                m = f"{plan.belge.quotation_number} silinemez: bağlı belgeler var ({', '.join(q.quotation_number for q in plan.altlar)}). Önce onları silin."
                self.logla(plan.belge, "sil", "engellendi", "bagli_belge_silme", m)
                self.db.commit()
                raise KilitHatasi(m)
            self._sil_tek(plan.belge, alt_belgeleri_de_sil, ust_belgeleri_de_sil, silinen)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return silinen

    def _sil_tek(self, belge: Quotation, alt_de: bool, ust_de: bool, silinen: list[int]) -> None:
        from src.desktop.services.belge_hareket_service import BelgeHareketError, BelgeHareketService
        if belge.id in silinen:
            return
        ustler = self.ustler(belge)
        for alt in self.altlar(belge):
            if alt_de:
                self._sil_tek(alt, True, False, silinen)
            else:
                self._alt_bagini_kopar(alt, belge)
        try:
            if belge.hareket_durumu == "islendi":
                BelgeHareketService(self.db).geri_al(belge.id)                  # stok/cari hareketlerini ters kayıtla düzeltir
        except BelgeHareketError as e:
            raise KilitHatasi(f"{belge.quotation_number}: hareketleri geri alınamadığı için silinemez — {e}") from e
        for bag in self._bag_satirlari(belge, hedef=True):                       # üst belge satırlarının faturalanan/sevk önbelleğini geri ver
            kaynak = self.db.get(QuotationLine, bag.kaynak_satir_id)
            if kaynak is not None:
                if bag.tur == "fatura":
                    kaynak.faturalanan = max(0.0, round((kaynak.faturalanan or 0) - bag.miktar, 6))
                elif bag.tur == "sevk":
                    kaynak.sevk_edilen = max(0.0, round((kaynak.sevk_edilen or 0) - bag.miktar, 6))
            bag.is_deleted = True
        belge.is_deleted = True
        silinen.append(belge.id)
        self.db.flush()
        numara_servisi.belge_silindi(self.db, belge)
        self.logla(belge, "sil", "yapildi", None, f"alt_belgeler_de={alt_de}; ust_belgeler_de={ust_de}; ustler={[q.quotation_number for q in ustler]}")
        for ust in ustler:
            if ust_de:
                self._sil_tek(ust, False, False, silinen)
        kaynak_belge = self.db.get(Quotation, belge.kaynak_belge_id) if belge.kaynak_belge_id else None
        if kaynak_belge is not None and kaynak_belge.status == "converted" and not self.altlar(kaynak_belge):
            kaynak_belge.status = "accepted"                                     # teklif yeniden serbest

    def _alt_bagini_kopar(self, alt: Quotation, ust: Quotation) -> None:
        """Alt belge (ör. faturanın) `ust`'e (ör. irsaliyeye) bağını koparır. Alt belge işlenmişse ve satırları stoğu kaynaktan alıyorsa,
        stok etkisi kaybolacağından koparılamaz."""
        ust_satirlar = {l.id for l in ust.lines}
        bagla = [b for b in self._bag_satirlari(alt, hedef=True) if b.kaynak_satir_id in ust_satirlar]
        if alt.hareket_durumu == "islendi" and any(l.stok_etkisi == "kaynaktan" for l in alt.lines):
            raise KilitHatasi(f"{alt.quotation_number} işlenmiş ve stok etkisini {ust.quotation_number} üzerinden alıyor. Önce {alt.quotation_number} belgesini "
                              "silin ya da birlikte silmeyi seçin.")
        for b in bagla:
            hedef = self.db.get(QuotationLine, b.hedef_satir_id)
            if hedef is not None and hedef.stok_etkisi == "kaynaktan":
                hedef.stok_etkisi = "kendi"                                      # kaynak gidince satır stoğu kendisi etkiler
            b.is_deleted = True
        if alt.kaynak_belge_id == ust.id:
            alt.kaynak_belge_id = None
        self.logla(alt, "bag_kopar", "yapildi", None, f"kaynak: {ust.quotation_number}")

    def bag_kopar(self, belge_id: int) -> list[str]:
        """Belgenin üst belgelerle (kaynaklarıyla) bağını koparır; belge kalır. Koparılan kaynak numaralarını döner."""
        belge = self.db.get(Quotation, belge_id)
        if belge is None or belge.is_deleted:
            raise KilitHatasi("Belge bulunamadı.")
        try:
            ustler = self.ustler(belge)
            if not ustler:
                raise KilitHatasi("Bu belgenin koparılacak bir bağı yok.")
            for u in ustler:
                self._alt_bagini_kopar(belge, u)
                if u.status == "converted" and not self.altlar(u):
                    u.status = "accepted"
                for satir in u.lines:                                            # üst satırların faturalanan önbelleği yeniden hesaplanır
                    if belge.belge_turu in ("fatura", "iade_fatura"):
                        kalan = sum(b.miktar for b in self.db.scalars(select(BelgeBag).where(
                            BelgeBag.kaynak_satir_id == satir.id, BelgeBag.tur == "fatura", BelgeBag.is_deleted == False)))  # noqa: E712
                        satir.faturalanan = round(kalan, 6)
            self.db.commit()
            return [u.quotation_number for u in ustler]
        except Exception:
            self.db.rollback()
            raise
