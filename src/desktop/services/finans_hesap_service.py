"""TOYA ERP - Şirket finans hesapları (kasa / banka / kredi kartı / POS) servisi.

Silme = görünümden gizleme. Kasa-banka hareketlerine bağlantı sonraki aşamadır."""

from __future__ import annotations

from sqlalchemy import or_, select

from src.core.models import FinansHesap
from src.desktop.services import money_service

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
        if tur == "pos" and bool(v.get("aktif", True)) and not self._banka_hesabi_var_mi():
            raise FinansHesapError(
                "POS hesabı aktif edilemez: önce en az bir Banka Hesabı tanımlanmalı "
                "(POS bakiyesi otomatik/manuel olarak bir banka hesabına aktarılır).",
            )
        kod = (v.get("kod") or "").strip().upper() or self.sonraki_kod(tur)
        ayni = self.db.scalar(select(FinansHesap).where(
            FinansHesap.kod == kod, FinansHesap.is_deleted == False, FinansHesap.id != (hesap_id or 0)))  # noqa: E712
        if ayni is not None:
            raise FinansHesapError(f"'{kod}' kodu başka bir hesapta kullanılıyor.")
        h = self.db.get(FinansHesap, hesap_id) if hesap_id else FinansHesap()
        if h is None or h.is_deleted:
            raise FinansHesapError("Hesap bulunamadı.")
        h.tur, h.kod, h.ad = tur, kod, ad
        h.para_birimi = (v.get("para_birimi") or money_service.yerel_para(self.db)).upper()
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
        if "pos_otomatik_mahsup" in v:
            h.pos_otomatik_mahsup = bool(v["pos_otomatik_mahsup"])
        if "pos_hedef_hesap_id" in v:
            h.pos_hedef_hesap_id = v["pos_hedef_hesap_id"] or None
        if "kk_kart_no" in v:
            h.kk_kart_no = (v.get("kk_kart_no") or "").strip() or None
        if "kk_hesap_kesim_gunu" in v:
            h.kk_hesap_kesim_gunu = int(v["kk_hesap_kesim_gunu"]) if v["kk_hesap_kesim_gunu"] not in (None, "", 0) else None
        if "kk_son_odeme_gunu" in v:
            h.kk_son_odeme_gunu = int(v["kk_son_odeme_gunu"]) if v["kk_son_odeme_gunu"] not in (None, "", 0) else None
        if "kk_faiz_orani" in v:
            faiz = v.get("kk_faiz_orani")
            h.kk_faiz_orani = float(faiz) if faiz not in (None, "") else None
        if "varsayilan_banka_odeme_plani_id" in v:
            h.varsayilan_banka_odeme_plani_id = v["varsayilan_banka_odeme_plani_id"] or None
        if hesap_id is None:
            self.db.add(h)
        else:
            h.version_id = (h.version_id or 1) + 1
        self.db.commit()
        return h

    def pasif_yap(self, hesap_id: int, pasif: bool = True) -> None:
        h = self.db.get(FinansHesap, hesap_id)
        if h is None or h.is_deleted:
            return
        if h.tur == "pos" and not pasif and not self._banka_hesabi_var_mi():
            raise FinansHesapError(
                "POS hesabı aktif edilemez: önce en az bir Banka Hesabı tanımlanmalı.",
            )
        h.aktif = not pasif
        self.db.commit()

    def _banka_hesabi_var_mi(self) -> bool:
        return self.db.scalar(
            select(FinansHesap.id).where(
                FinansHesap.tur == "banka", FinansHesap.is_deleted == False, FinansHesap.aktif == True,  # noqa: E712
            ).limit(1),
        ) is not None

    @staticmethod
    def sozluk(h: FinansHesap) -> dict:
        """Kart editörüne verilen düz sözlük (`id` dahil)."""
        return {"id": h.id, "kod": h.kod, "ad": h.ad, "tur": h.tur, "para_birimi": h.para_birimi, "banka": h.banka or "",
                "hesap_no": h.hesap_no or "", "komisyon_orani": h.komisyon_orani or 0.0, "aktif": bool(h.aktif),
                "sorumlu": h.sorumlu or "", "sube_adi": h.sube_adi or "", "sube_kodu": h.sube_kodu or "", "iban": h.iban or "",
                "uye_isyeri_no": h.uye_isyeri_no or "", "valor_gun": h.valor_gun or 0,
                "doviz_kisitli": bool(h.doviz_kisitli), "aciklama": h.aciklama or "",
                "pos_otomatik_mahsup": bool(h.pos_otomatik_mahsup), "pos_hedef_hesap_id": h.pos_hedef_hesap_id,
                "pos_hedef_hesap_etiket": f"{h.pos_hedef_hesap.kod} — {h.pos_hedef_hesap.ad}" if h.pos_hedef_hesap else "",
                "kk_kart_no": h.kk_kart_no or "", "kk_hesap_kesim_gunu": h.kk_hesap_kesim_gunu or 0,
                "kk_son_odeme_gunu": h.kk_son_odeme_gunu or 0, "kk_faiz_orani": h.kk_faiz_orani or 0.0,
                "varsayilan_banka_odeme_plani_id": h.varsayilan_banka_odeme_plani_id,
                "varsayilan_banka_odeme_plani_etiket": (
                    f"{h.varsayilan_banka_odeme_plani.kod} — {h.varsayilan_banka_odeme_plani.aciklama or ''}".rstrip(" —")
                    if h.varsayilan_banka_odeme_plani else ""
                )}

    def gizle(self, hesap_id: int) -> None:
        h = self.db.get(FinansHesap, hesap_id)
        if h is not None and not h.is_deleted:
            h.is_deleted = True
            self.db.commit()


# ---------------------------------------------------------------------------------------------------
# Hesap hareketleri (kasa / banka / kredi kartı / POS): şimdilik cari fişlerindeki "Araç / Hesap" satırları
# ---------------------------------------------------------------------------------------------------
def hesap_hareketleri(db, hesap_id: int) -> list[dict]:
    """Hesaba bağlı hareketler, eskiden yeniye: cari fişlerindeki "Araç / Hesap" satırları + kasa/banka hareket fişleri.
    Tahsilat/giriş **giriş**, ödeme/çıkış **çıkış** sayılır; virman çıkış hesabından çıkar, karşı hesaba girer.
    Her kayıt: tarih, fis_no, tur, cari, giris, cikis, doviz, aciklama, vade, kaynak, bakiye (aynı dövizdeki yürüyen bakiye)."""
    from src.core.models import CariHareket, FinansHareket
    from src.desktop.services.finans_fis_service import TURLER as FIN_TURLER
    ham = []
    for h in db.scalars(select(CariHareket).where(CariHareket.fin_hesap_id == hesap_id, CariHareket.is_deleted == False)  # noqa: E712
                        .order_by(CariHareket.tarih, CariHareket.id)):
        giris = h.tutar if h.tur == "tahsilat" else 0.0
        cikis = h.tutar if h.tur == "odeme" else 0.0
        ham.append((h.tarih, 0, h.id, {"fis_no": h.fis.fis_no if h.fis else "", "tur": "Tahsilat" if giris else "Ödeme",
                                       "cari": h.customer.fullname, "giris": giris, "cikis": cikis, "doviz": h.para_birimi,
                                       "aciklama": h.aciklama or "", "vade": h.vade, "kaynak": "Cari Fişi"}))
    for f in db.scalars(select(FinansHareket).where(FinansHareket.is_deleted == False,  # noqa: E712
                                                    or_(FinansHareket.hesap_id == hesap_id, FinansHareket.karsi_hesap_id == hesap_id))
                        .order_by(FinansHareket.tarih, FinansHareket.id)):
        etiket = FIN_TURLER[f.tur][0] if f.tur in FIN_TURLER else f.tur
        if f.karsi_hesap_id:                                                    # virman
            giren = f.karsi_hesap_id == hesap_id
            karsi = f.hesap if giren else f.karsi_hesap
            cari = ("← " if giren else "→ ") + (karsi.ad if karsi else "")
            giris, cikis = (f.tutar, 0.0) if giren else (0.0, f.tutar)
        else:
            giris, cikis = (f.tutar, 0.0) if f.yon == "giris" else (0.0, f.tutar)
            cari = f.customer.fullname if f.customer else ""
        ham.append((f.tarih, 1, f.id, {"fis_no": f.fis.fis_no if f.fis else "", "tur": etiket, "cari": cari, "giris": giris,
                                       "cikis": cikis, "doviz": f.para_birimi, "aciklama": f.aciklama or "", "vade": None,
                                       "kaynak": "Kasa Fişi" if f.tur.startswith("kasa") else "Banka Fişi"}))
    ham.sort(key=lambda x: (x[0], x[1], x[2]))
    yuruyen: dict[str, float] = {}
    out = []
    for tarih, _k, _i, d in ham:
        yuruyen[d["doviz"]] = round(yuruyen.get(d["doviz"], 0.0) + d["giris"] - d["cikis"], 4)
        out.append({"tarih": tarih, **d, "bakiye": yuruyen[d["doviz"]]})
    return out


def hesap_bakiyeleri(db, hesap_id: int) -> dict[str, float]:
    """{döviz: bakiye} — hesabın güncel bakiyesi (giriş − çıkış), döviz bazında. Hareketi olmayan hesap boş sözlük döner."""
    bak: dict[str, float] = {}
    for h in hesap_hareketleri(db, hesap_id):
        bak[h["doviz"]] = h["bakiye"]
    return {k: v for k, v in bak.items()}
