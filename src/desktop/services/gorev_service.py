"""TOYA ERP - Görevler servisi (görev / randevu / hatırlatma).

Genel amaçlıdır: her modül `ilgili_tur` + `ilgili_id` ile bir kayda (cari, stok, fatura, teklif, servis…) bağlı görev açabilir
(`iliskili_olustur`, `ilgili_gorevler`). Takvim `baslangic`/`bitis` tarihlerinden beslenir; yinelenen görevler (günlük/haftalık/
aylık) aralık içinde açılarak gösterilir, yinelenen görev tamamlanınca bir sonraki tekrarı otomatik oluşur.
Silme = gizleme (fiziksel silme yok)."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_, select

from src.core.models import Gorev

TURLER = {"gorev": "Görev", "randevu": "Randevu", "hatirlatma": "Hatırlatma"}
DURUMLAR = {"yapilacak": "Yapılacak", "devam": "Devam Ediyor", "inceleme": "İncelemede", "tamam": "Tamamlandı", "iptal": "İptal"}
ACIK_DURUMLAR = ("yapilacak", "devam", "inceleme")
ONCELIKLER = {1: "Düşük", 2: "Normal", 3: "Yüksek", 4: "Acil"}
KATEGORILER = {"genel": "Genel", "tahsilat": "Tahsilat Takibi", "satis": "Satış / Ziyaret", "sevkiyat": "Sevkiyat", "servis": "Servis", "finans": "Finans / Masraf", "diger": "Diğer"}
TEKRARLAR = {"yok": "Tekrarlanmaz", "gunluk": "Her gün", "haftalik": "Her hafta", "aylik": "Her ay"}
ILGILI_TURLERI = {"cari": "Cari", "stok": "Stok", "fatura": "Fatura", "teklif": "Teklif", "siparis": "Sipariş", "servis": "Servis", "masraf": "Masraf"}


class GorevError(ValueError):
    """Doğrulama hatası; mesaj kullanıcıya gösterilebilir."""


@dataclass
class GorevFiltre:
    arama: str = ""
    durumlar: tuple[str, ...] | None = None
    oncelik: int | None = None
    kategori: str | None = None
    tur: str | None = None
    atanan: str | None = None
    ilgili_tur: str | None = None
    ilgili_id: int | None = None
    tarih_bas: date | None = None            # başlangıç/bitiş bu aralığa denk gelenler
    tarih_bit: date | None = None
    sadece_gecikmis: bool = False


@dataclass
class Olay:
    """Takvimde görünen bir tekrar (yinelenmeyen görevde tek)."""
    gorev: Gorev
    gun: date
    baslangic: datetime | None
    bitis: datetime | None
    tekrar_no: int = 0


@dataclass
class GorevOzeti:
    toplam: int = 0
    acik: int = 0
    gecikmis: int = 0
    bugun: int = 0
    tamam: int = 0
    durum: dict[str, int] = field(default_factory=dict)


def ay_ekle(d: datetime | date, n: int):
    """Ay sonu taşmasını düzelterek n ay ileri (31 Ocak + 1 ay = 28/29 Şubat)."""
    ay = d.month - 1 + n
    yil, ay = d.year + ay // 12, ay % 12 + 1
    return d.replace(year=yil, month=ay, day=min(d.day, calendar.monthrange(yil, ay)[1]))


def _adim(d, tekrar: str, n: int):
    if tekrar == "gunluk":
        return d + timedelta(days=n)
    if tekrar == "haftalik":
        return d + timedelta(weeks=n)
    if tekrar == "aylik":
        return ay_ekle(d, n)
    return d


class GorevService:
    def __init__(self, db) -> None:
        self.db = db

    # ---- yazma -------------------------------------------------------------
    def _hazirla(self, g: Gorev, v: dict) -> None:
        baslik = (v.get("baslik", g.baslik) or "").strip()
        if not baslik:
            raise GorevError("Başlık boş olamaz.")
        tur = v.get("tur", g.tur) or "gorev"
        durum = v.get("durum", g.durum) or "yapilacak"
        oncelik = int(v.get("oncelik", g.oncelik) or 2)
        kategori = v.get("kategori", g.kategori) or "genel"
        tekrar = v.get("tekrar", g.tekrar) or "yok"
        if tur not in TURLER or durum not in DURUMLAR or oncelik not in ONCELIKLER or kategori not in KATEGORILER or tekrar not in TEKRARLAR:
            raise GorevError("Geçersiz tür, durum, öncelik, kategori ya da tekrar değeri.")
        bas, bit = v.get("baslangic", g.baslangic), v.get("bitis", g.bitis)
        if bas and bit and bit < bas:
            raise GorevError("Bitiş, başlangıçtan önce olamaz.")
        if tur == "randevu" and not bas:
            raise GorevError("Randevu için başlangıç zamanı girilmelidir.")
        if tekrar != "yok" and not (bas or bit):
            raise GorevError("Tekrarlanan görevde başlangıç ya da bitiş tarihi olmalıdır.")
        ilgili_tur = v.get("ilgili_tur", g.ilgili_tur) or None
        if ilgili_tur and ilgili_tur not in ILGILI_TURLERI:
            raise GorevError("Geçersiz ilişkili kayıt türü.")
        g.tur, g.baslik, g.durum, g.oncelik, g.kategori, g.tekrar = tur, baslik, durum, oncelik, kategori, tekrar
        g.aciklama = (v.get("aciklama", g.aciklama) or "").strip() or None
        g.atanan = (v.get("atanan", g.atanan) or "").strip() or None
        g.olusturan = g.olusturan or (v.get("olusturan") or "").strip() or None
        g.baslangic, g.bitis = bas, bit
        g.tum_gun = bool(v.get("tum_gun", g.tum_gun))
        hat = v.get("hatirlat_dk", g.hatirlat_dk)
        g.hatirlat_dk = int(hat) if hat not in (None, "") else None
        if any(k in v for k in ("baslangic", "bitis", "hatirlat_dk")):
            g.hatirlatildi = False                                   # zaman değişti: hatırlatma yeniden kurulur
        g.tekrar_bitis = v.get("tekrar_bitis", g.tekrar_bitis)
        g.ilgili_tur, g.ilgili_id = ilgili_tur, (v.get("ilgili_id", g.ilgili_id) if ilgili_tur else None)
        g.ilgili_ad = (v.get("ilgili_ad", g.ilgili_ad) or "").strip() or None if ilgili_tur else None
        g.tamamlandi = (g.tamamlandi or datetime.now()) if durum == "tamam" else None

    def kaydet(self, v: dict, gorev_id: int | None = None) -> Gorev:
        if gorev_id:
            g = self.db.get(Gorev, gorev_id)
            if g is None or g.is_deleted:
                raise GorevError("Görev bulunamadı.")
            g.version_id = (g.version_id or 1) + 1
        else:
            g = Gorev()
        try:
            self._hazirla(g, v)
            if gorev_id is None:
                self.db.add(g)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return g

    def iliskili_olustur(self, ilgili_tur: str, ilgili_id: int, ilgili_ad: str, baslik: str, **v) -> Gorev:
        """Başka bir modülden (ör. Servis) ilgili kayda bağlı görev açar."""
        return self.kaydet(dict(v, baslik=baslik, ilgili_tur=ilgili_tur, ilgili_id=ilgili_id, ilgili_ad=ilgili_ad))

    def durum_degistir(self, gorev_id: int, durum: str) -> Gorev:
        """Durumu değiştirir. Yinelenen görev tamamlanınca bir sonraki tekrar yeni görev olarak açılır."""
        g = self.db.get(Gorev, gorev_id)
        if g is None or g.is_deleted:
            raise GorevError("Görev bulunamadı.")
        if durum not in DURUMLAR:
            raise GorevError("Geçersiz durum.")
        onceki = g.durum
        g.durum = durum
        g.tamamlandi = (g.tamamlandi or datetime.now()) if durum == "tamam" else None
        g.version_id = (g.version_id or 1) + 1
        if durum == "tamam" and onceki != "tamam" and g.tekrar != "yok":
            self._sonraki_tekrar(g)
        self.db.commit()
        return g

    def _sonraki_tekrar(self, g: Gorev) -> None:
        bas = _adim(g.baslangic, g.tekrar, 1) if g.baslangic else None
        bit = _adim(g.bitis, g.tekrar, 1) if g.bitis else None
        ref = (bas or bit).date()
        if g.tekrar_bitis and ref > g.tekrar_bitis:
            return
        yeni = Gorev(tur=g.tur, baslik=g.baslik, aciklama=g.aciklama, kategori=g.kategori, oncelik=g.oncelik, durum="yapilacak",
                     atanan=g.atanan, olusturan=g.olusturan, baslangic=bas, bitis=bit, tum_gun=g.tum_gun, hatirlat_dk=g.hatirlat_dk,
                     tekrar=g.tekrar, tekrar_bitis=g.tekrar_bitis, ilgili_tur=g.ilgili_tur, ilgili_id=g.ilgili_id, ilgili_ad=g.ilgili_ad)
        self.db.add(yeni)

    def gizle(self, ids: list[int]) -> int:
        """Silme = gizleme."""
        n = 0
        for i in ids:
            g = self.db.get(Gorev, i)
            if g is not None and not g.is_deleted:
                g.is_deleted = True
                n += 1
        self.db.commit()
        return n

    def getir(self, gorev_id: int) -> Gorev:
        g = self.db.get(Gorev, gorev_id)
        if g is None or g.is_deleted:
            raise GorevError("Görev bulunamadı.")
        return g

    # ---- okuma -------------------------------------------------------------
    def _where(self, f: GorevFiltre, simdi: datetime | None = None):
        simdi = simdi or datetime.now()
        c = [Gorev.is_deleted == False]  # noqa: E712
        if f.durumlar:
            c.append(Gorev.durum.in_(list(f.durumlar)))
        if f.oncelik:
            c.append(Gorev.oncelik == f.oncelik)
        for alan, deger in (("kategori", f.kategori), ("tur", f.tur), ("atanan", f.atanan), ("ilgili_tur", f.ilgili_tur), ("ilgili_id", f.ilgili_id)):
            if deger:
                c.append(getattr(Gorev, alan) == deger)
        if f.sadece_gecikmis:
            c += [Gorev.durum.in_(list(ACIK_DURUMLAR)), Gorev.bitis.is_not(None), Gorev.bitis < simdi]
        if f.tarih_bas:
            c.append(or_(Gorev.bitis >= datetime.combine(f.tarih_bas, time.min), Gorev.baslangic >= datetime.combine(f.tarih_bas, time.min)))
        if f.tarih_bit:
            c.append(or_(Gorev.baslangic <= datetime.combine(f.tarih_bit, time.max), Gorev.bitis <= datetime.combine(f.tarih_bit, time.max)))
        if f.arama.strip():
            q = f"%{f.arama.strip()}%"
            c.append(or_(Gorev.baslik.ilike(q), Gorev.aciklama.ilike(q), Gorev.atanan.ilike(q), Gorev.ilgili_ad.ilike(q)))
        return c

    def liste(self, f: GorevFiltre, sayfa: int = 1, sayfa_boyu: int = 25) -> tuple[list[Gorev], int]:
        where = self._where(f)
        toplam = self.db.scalar(select(func.count()).select_from(Gorev).where(*where)) or 0
        stmt = (select(Gorev).where(*where)
                .order_by(Gorev.durum.in_(["tamam", "iptal"]), Gorev.bitis.is_(None), Gorev.bitis, Gorev.oncelik.desc(), Gorev.id.desc())
                .offset((max(sayfa, 1) - 1) * sayfa_boyu).limit(sayfa_boyu))
        return list(self.db.scalars(stmt)), toplam

    def hepsi(self, f: GorevFiltre) -> list[Gorev]:
        return self.liste(f, 1, 1_000_000)[0]

    def ozet(self, f: GorevFiltre | None = None, simdi: datetime | None = None) -> GorevOzeti:
        simdi = simdi or datetime.now()
        o = GorevOzeti()
        bugun = simdi.date()
        for g in self.db.scalars(select(Gorev).where(*self._where(f or GorevFiltre(), simdi))):
            o.toplam += 1
            o.durum[g.durum] = o.durum.get(g.durum, 0) + 1
            if g.durum == "tamam":
                o.tamam += 1
            if g.durum in ACIK_DURUMLAR:
                o.acik += 1
                if g.bitis and g.bitis < simdi:
                    o.gecikmis += 1
                if (g.bitis or g.baslangic) and (g.bitis or g.baslangic).date() == bugun:
                    o.bugun += 1
        return o

    def gecikmis_mi(self, g: Gorev, simdi: datetime | None = None) -> bool:
        return g.durum in ACIK_DURUMLAR and g.bitis is not None and g.bitis < (simdi or datetime.now())

    def ilgili_gorevler(self, ilgili_tur: str, ilgili_id: int, sadece_acik: bool = True) -> list[Gorev]:
        """Bir kayda (cari kartı, servis kaydı…) bağlı görevler; ilgili modül ekranı bunu listeleyebilir."""
        return self.hepsi(GorevFiltre(ilgili_tur=ilgili_tur, ilgili_id=ilgili_id, durumlar=ACIK_DURUMLAR if sadece_acik else None))

    # ---- takvim ------------------------------------------------------------
    def takvim(self, bas: date, bit: date, f: GorevFiltre | None = None) -> list[Olay]:
        """[bas, bit] aralığındaki olaylar (yinelenenler açılmış), gün ve saat sırasıyla. Görev başlangıcı yoksa bitiş günü esas alınır."""
        f = f or GorevFiltre()
        olaylar: list[Olay] = []
        for g in self.db.scalars(select(Gorev).where(*self._where(f))):
            ref_bas = g.baslangic or g.bitis
            if ref_bas is None:
                continue
            sure = (g.bitis - g.baslangic) if (g.baslangic and g.bitis) else timedelta(0)
            if g.tekrar == "yok":
                gunler = [(0, ref_bas)]
            else:
                gunler, n = [], 0
                while True:
                    d = _adim(ref_bas, g.tekrar, n)
                    if d.date() > bit or (g.tekrar_bitis and d.date() > g.tekrar_bitis):
                        break
                    gunler.append((n, d))
                    n += 1
                    if n > 3660:
                        break
            for n, d in gunler:
                son = d + sure
                if son.date() < bas or d.date() > bit:
                    continue
                gun = d.date()
                while gun <= son.date():                            # çok günlü görev her güne düşer
                    if bas <= gun <= bit:
                        olaylar.append(Olay(g, gun, d if g.baslangic else None, son if g.bitis else None, n))
                    gun += timedelta(days=1)
        olaylar.sort(key=lambda o: (o.gun, o.baslangic or datetime.combine(o.gun, time.max), o.gorev.id))
        return olaylar

    # ---- ana panel özeti -----------------------------------------------------
    def bugun_ozeti(self, kullanici: str | None = None, simdi: datetime | None = None, tumu: bool = False) -> dict[str, list]:
        """Ana paneldeki "bugünün görevleri": {"gecikmis": [Gorev], "bugun": [Olay]} — yalnız açık olanlar.
        Kullanıcı verilirse ona atanmış ve kimseye atanmamış olanlar gelir (`tumu=True` herkesinkini getirir). Yinelenenler bugüne açılır."""
        simdi = simdi or datetime.now()
        bugun = simdi.date()

        def uygun(g: Gorev) -> bool:
            return tumu or not kullanici or not g.atanan or g.atanan == kullanici

        gecikmis = [g for g in self.hepsi(GorevFiltre(sadece_gecikmis=True)) if uygun(g) and g.bitis.date() < bugun]
        bugun_gec = [g for g in self.hepsi(GorevFiltre(sadece_gecikmis=True)) if uygun(g) and g.bitis.date() == bugun]
        gec_idler = {g.id for g in gecikmis}
        olaylar = [o for o in self.takvim(bugun, bugun, GorevFiltre(durumlar=ACIK_DURUMLAR))
                   if uygun(o.gorev) and o.gorev.id not in gec_idler]
        gorulen = {o.gorev.id for o in olaylar}
        for g in bugun_gec:                                   # bugün bitmiş saati geçmiş olanlar da "bugün" listesinde kalır
            if g.id not in gorulen:
                olaylar.append(Olay(g, bugun, g.baslangic, g.bitis))
        olaylar.sort(key=lambda o: (o.baslangic or o.bitis or datetime.combine(bugun, time.max), o.gorev.id))
        return {"gecikmis": gecikmis, "bugun": olaylar}

    # ---- hatırlatma --------------------------------------------------------
    def hatirlatmalar(self, simdi: datetime | None = None, kullanici: str | None = None, isaretle: bool = True) -> list[Gorev]:
        """Zamanı gelen (başlangıç/bitiş − hatırlat_dk ≤ şimdi) ve henüz hatırlatılmamış açık görevler."""
        simdi = simdi or datetime.now()
        out = []
        for g in self.db.scalars(select(Gorev).where(Gorev.is_deleted == False, Gorev.hatirlat_dk.is_not(None),  # noqa: E712
                                                     Gorev.hatirlatildi == False, Gorev.durum.in_(list(ACIK_DURUMLAR)))):  # noqa: E712
            ref = g.baslangic or g.bitis
            if ref is None or (kullanici and g.atanan and g.atanan != kullanici):
                continue
            if ref - timedelta(minutes=g.hatirlat_dk) <= simdi:
                out.append(g)
                if isaretle:
                    g.hatirlatildi = True
        if out and isaretle:
            self.db.commit()
        return out
