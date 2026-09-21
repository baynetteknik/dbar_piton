"""TOYA ERP - Şirket finans hesapları (kasa / banka / kredi kartı / POS) servisi.

Silme = görünümden gizleme. Kasa-banka hareketlerine bağlantı sonraki aşamadır."""

from __future__ import annotations

from sqlalchemy import or_, select

from src.core.models import FinansHesap

HESAP_TURLERI: dict[str, str] = {"kasa": "Kasa", "banka": "Banka", "kredi_karti": "Kredi Kartı", "pos": "POS"}
_KOD_ONEK = {"kasa": "KSA", "banka": "BNK", "kredi_karti": "KK", "pos": "POS"}


class FinansHesapError(ValueError):
    """Doğrulama hatası; mesaj kullanıcıya gösterilebilir."""


class FinansHesapService:
    def __init__(self, db) -> None:
        self.db = db

    def liste(self, tur: str | None = None, arama: str = "", sadece_aktif: bool = False,
              turler: tuple[str, ...] | list[str] | None = None) -> list[FinansHesap]:
        stmt = select(FinansHesap).where(FinansHesap.is_deleted == False)  # noqa: E712
        if tur:
            stmt = stmt.where(FinansHesap.tur == tur)
        if turler:
            stmt = stmt.where(FinansHesap.tur.in_(list(turler)))
        if sadece_aktif:
            stmt = stmt.where(FinansHesap.aktif == True)  # noqa: E712
        if arama.strip():
            q = f"%{arama.strip()}%"
            stmt = stmt.where(or_(FinansHesap.kod.ilike(q), FinansHesap.ad.ilike(q), FinansHesap.banka.ilike(q),
                                  FinansHesap.hesap_no.ilike(q)))
        return list(self.db.scalars(stmt.order_by(FinansHesap.tur, FinansHesap.kod)))

    def sonraki_kod(self, tur: str) -> str:
        onek = _KOD_ONEK.get(tur, "HSP")
        en_buyuk = 0
        for (kod,) in self.db.execute(select(FinansHesap.kod).where(FinansHesap.tur == tur)):
            son = str(kod).removeprefix(onek)
            if son.isdigit():
                en_buyuk = max(en_buyuk, int(son))
        return f"{onek}{en_buyuk + 1:03d}"

    def kaydet(self, v: dict, hesap_id: int | None = None) -> FinansHesap:
        tur = v.get("tur")
        if tur not in HESAP_TURLERI:
            raise FinansHesapError("Hesap türü Kasa, Banka, Kredi Kartı veya POS olmalıdır.")
        ad = (v.get("ad") or "").strip()
        if not ad:
            raise FinansHesapError("Hesap adı boş olamaz.")
        kod = (v.get("kod") or "").strip().upper() or self.sonraki_kod(tur)
        ayni = self.db.scalar(select(FinansHesap).where(
            FinansHesap.kod == kod, FinansHesap.is_deleted == False, FinansHesap.id != (hesap_id or 0)))  # noqa: E712
        if ayni is not None:
            raise FinansHesapError(f"'{kod}' kodu başka bir hesapta kullanılıyor.")
        h = self.db.get(FinansHesap, hesap_id) if hesap_id else FinansHesap()
        if h is None or h.is_deleted:
            raise FinansHesapError("Hesap bulunamadı.")
        h.tur, h.kod, h.ad = tur, kod, ad
        h.para_birimi = (v.get("para_birimi") or "TRY").upper()
        h.banka = (v.get("banka") or "").strip() or None
        h.hesap_no = (v.get("hesap_no") or "").strip() or None
        kom = v.get("komisyon_orani")
        h.komisyon_orani = float(kom) if kom not in (None, "") else None
        h.aktif = bool(v.get("aktif", True))
        for alan in ("sorumlu", "sube_adi", "sube_kodu", "iban", "uye_isyeri_no", "aciklama"):
            if alan in v:
                setattr(h, alan, (v.get(alan) or "").strip() or None)
        if "valor_gun" in v:
            h.valor_gun = int(v["valor_gun"]) if v["valor_gun"] not in (None, "", 0) else None
        if "doviz_kisitli" in v:
            h.doviz_kisitli = bool(v["doviz_kisitli"])
        if hesap_id is None:
            self.db.add(h)
        else:
            h.version_id = (h.version_id or 1) + 1
        self.db.commit()
        return h

    def pasif_yap(self, hesap_id: int, pasif: bool = True) -> None:
        h = self.db.get(FinansHesap, hesap_id)
        if h is not None and not h.is_deleted:
            h.aktif = not pasif
            self.db.commit()

    @staticmethod
    def sozluk(h: FinansHesap) -> dict:
        """Kart editörüne verilen düz sözlük (`id` dahil)."""
        return {"id": h.id, "kod": h.kod, "ad": h.ad, "tur": h.tur, "para_birimi": h.para_birimi, "banka": h.banka or "",
                "hesap_no": h.hesap_no or "", "komisyon_orani": h.komisyon_orani or 0.0, "aktif": bool(h.aktif),
                "sorumlu": h.sorumlu or "", "sube_adi": h.sube_adi or "", "sube_kodu": h.sube_kodu or "", "iban": h.iban or "",
                "uye_isyeri_no": h.uye_isyeri_no or "", "valor_gun": h.valor_gun or 0,
                "doviz_kisitli": bool(h.doviz_kisitli), "aciklama": h.aciklama or ""}

    def gizle(self, hesap_id: int) -> None:
        h = self.db.get(FinansHesap, hesap_id)
        if h is not None and not h.is_deleted:
            h.is_deleted = True
            self.db.commit()


# ---------------------------------------------------------------------------------------------------
# Hesap hareketleri (kasa / banka / kredi kartı / POS): şimdilik cari fişlerindeki "Araç / Hesap" satırları
# ---------------------------------------------------------------------------------------------------
def hesap_hareketleri(db, hesap_id: int) -> list[dict]:
    """Hesaba bağlı hareketler, eskiden yeniye. Tahsilat satırı hesaba **giriş**, ödeme (tediye) satırı **çıkış** sayılır.
    Her kayıt: tarih, fis_no, tur, cari, giris, cikis, doviz, aciklama, vade, kaynak, bakiye (aynı dövizdeki yürüyen bakiye).
    Kasa / banka kendi hareket fişleri geldiğinde bu liste onlarla birleştirilecektir."""
    from src.core.models import CariHareket
    satirlar = list(db.scalars(
        select(CariHareket).where(CariHareket.fin_hesap_id == hesap_id, CariHareket.is_deleted == False)  # noqa: E712
        .order_by(CariHareket.tarih, CariHareket.id)))
    yuruyen: dict[str, float] = {}
    out = []
    for h in satirlar:
        giris = h.tutar if h.tur == "tahsilat" else 0.0
        cikis = h.tutar if h.tur == "odeme" else 0.0
        yuruyen[h.para_birimi] = round(yuruyen.get(h.para_birimi, 0.0) + giris - cikis, 4)
        out.append({"tarih": h.tarih, "fis_no": h.fis.fis_no if h.fis else "", "tur": "Tahsilat" if giris else "Ödeme",
                    "cari": h.customer.fullname, "giris": giris, "cikis": cikis, "doviz": h.para_birimi,
                    "aciklama": h.aciklama or "", "vade": h.vade, "kaynak": "Cari Fişi", "bakiye": yuruyen[h.para_birimi]})
    return out


def hesap_bakiyeleri(db, hesap_id: int) -> dict[str, float]:
    """{döviz: bakiye} — hesabın güncel bakiyesi (giriş − çıkış), döviz bazında. Hareketi olmayan hesap boş sözlük döner."""
    bak: dict[str, float] = {}
    for h in hesap_hareketleri(db, hesap_id):
        bak[h["doviz"]] = h["bakiye"]
    return {k: v for k, v in bak.items()}
