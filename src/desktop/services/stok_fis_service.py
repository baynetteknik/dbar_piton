"""TOYA ERP - Stok hareket fişi servisi.

Fiş türleri: giriş, çıkış, depo transferi, sayım, açılış. Hareketler depo bazlı bir defterde tutulur (`StokHareket`);
her hareketin `Product.stock` (toplam stok) üzerindeki net etkisi saklanır, böylece fiş değiştirilince ya da gizlenince
etki tam olarak geri alınır. Silme yalnızca görünümden gizler (`is_deleted`)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, or_, select

from src.core.models import Product, StockMovement, StokFis, StokHareket, WarehouseDefinition

# tür kodu -> (etiket, işaret). Sayımın etkisi sayılan − mevcut farkıdır; transferin toplam etkisi sıfırdır.
TURLER: dict[str, tuple[str, int | None]] = {
    "giris": ("Stok Giriş", +1),
    "cikis": ("Stok Çıkış", -1),
    "transfer": ("Depo Transfer", 0),
    "sayim": ("Sayım", None),
    "acilis": ("Açılış Girişi", +1),
}
#: Fiş başlığındaki fiş türü -> yeni satırın başlangıç türü.
FIS_TIPLERI: dict[str, str] = {
    "giris": "Stok Giriş Fişi", "cikis": "Stok Çıkış Fişi", "transfer": "Depo Transfer Fişi",
    "sayim": "Sayım Fişi", "acilis": "Açılış Fişi",
}


class StokFisError(ValueError):
    """Doğrulama hatası; mesaj kullanıcıya gösterilebilir."""


@dataclass
class StokFiltre:
    arama: str = ""
    tur: str | None = None
    depo_id: int | None = None
    product_id: int | None = None
    tarih_bas: date | None = None
    tarih_bit: date | None = None


@dataclass
class StokOzet:
    adet: int = 0
    giris: float = 0.0
    cikis: float = 0.0
    tutar: float = 0.0


def _norm(x: float) -> float | int:
    """Tam sayı ise int (mevcut tamsayılı stok alanıyla uyumlu), değilse 4 haneye yuvarlanmış float."""
    x = round(float(x), 4)
    return int(x) if x == int(x) else x


class StokFisService:
    def __init__(self, db, negatif_stok_izni: bool = False) -> None:
        self.db = db
        self.negatif_stok_izni = negatif_stok_izni

    # ---- depo ------------------------------------------------------------------
    def depolar(self) -> list[WarehouseDefinition]:
        return list(self.db.scalars(select(WarehouseDefinition).where(
            WarehouseDefinition.is_deleted == False, WarehouseDefinition.is_active != False)  # noqa: E712
            .order_by(WarehouseDefinition.code)))

    def varsayilan_depo(self) -> int:
        """İlk aktif depo; hiç depo tanımlı değilse 'MERKEZ' deposu oluşturulur."""
        d = self.depolar()
        if d:
            return d[0].id
        w = WarehouseDefinition(code="MERKEZ", name="Merkez Depo", is_active=True)
        self.db.add(w)
        self.db.commit()
        return w.id

    def depo_stok(self, product_id: int, depo_id: int, haric_fis_id: int | None = None) -> float:
        """Ürünün depodaki (defterden hesaplanan) bakiyesi. Transferde hedef depo giriş, kaynak depo çıkış sayılır."""
        def ek(q):
            return q.where(StokHareket.is_deleted == False, StokHareket.product_id == product_id,  # noqa: E712
                           *([or_(StokHareket.fis_id.is_(None), StokHareket.fis_id != haric_fis_id)] if haric_fis_id else []))

        kaynak = self.db.scalar(ek(select(func.coalesce(func.sum(StokHareket.depo_etkisi), 0.0))).where(StokHareket.depo_id == depo_id))
        hedef = self.db.scalar(ek(select(func.coalesce(func.sum(StokHareket.miktar), 0.0)))
                               .where(StokHareket.tur == "transfer", StokHareket.hedef_depo_id == depo_id))
        return float(kaynak or 0.0) + float(hedef or 0.0)

    # ---- yazma -----------------------------------------------------------------
    def sonraki_fis_no(self) -> str:
        en_buyuk = 0
        for (no,) in self.db.execute(select(StokFis.fis_no)):
            if str(no).isdigit():
                en_buyuk = max(en_buyuk, int(no))
        return f"{en_buyuk + 1:06d}"

    def _etkiyi_geri_al(self, h: StokHareket) -> None:
        p = self.db.get(Product, h.product_id)
        if p is not None and h.toplam_etki:
            p.stock = _norm((p.stock or 0) - h.toplam_etki)
        h.toplam_etki = 0.0
        h.depo_etkisi = 0.0

    def _hazirla(self, h: StokHareket, v: dict, fis: StokFis) -> None:
        tur = v.get("tur", h.tur)
        if tur not in TURLER:
            raise StokFisError("Geçersiz hareket türü.")
        pid = v.get("product_id", h.product_id)
        p = self.db.get(Product, pid) if pid else None
        if p is None or p.is_deleted:
            raise StokFisError("Stok kartı seçilmelidir.")
        miktar = float(v.get("miktar", h.miktar) or 0)
        if miktar < 0 or (miktar == 0 and tur != "sayim"):
            raise StokFisError("Miktar sıfırdan büyük olmalıdır." if tur != "sayim" else "Sayılan miktar negatif olamaz.")
        depo = v.get("depo_id") or fis.depo_id
        if not depo or self.db.get(WarehouseDefinition, depo) is None:
            raise StokFisError("Depo seçilmelidir.")
        hedef = v.get("hedef_depo_id") if tur == "transfer" else None
        if tur == "transfer":
            if not hedef or self.db.get(WarehouseDefinition, hedef) is None:
                raise StokFisError("Transferde hedef depo seçilmelidir.")
            if hedef == depo:
                raise StokFisError("Kaynak ve hedef depo aynı olamaz.")
        h.product_id, h.tur, h.depo_id, h.hedef_depo_id = p.id, tur, depo, hedef
        h.tarih = v.get("tarih") or fis.tarih
        h.miktar = miktar
        h.birim = (v.get("birim") or p.unit or "Adet")
        h.birim_fiyat = float(v.get("birim_fiyat") or 0)
        h.tutar = round(miktar * h.birim_fiyat, 2)
        h.aciklama = (v.get("aciklama") or "").strip() or None
        # etkiler
        isaret = TURLER[tur][1]
        if tur == "sayim":
            fark = miktar - self.depo_stok(p.id, depo, haric_fis_id=fis.id)
            h.depo_etkisi = h.toplam_etki = round(fark, 4)
        elif tur == "transfer":
            h.depo_etkisi, h.toplam_etki = -miktar, 0.0
        else:
            h.depo_etkisi = h.toplam_etki = round(isaret * miktar, 4)
        yeni = (p.stock or 0) + h.toplam_etki
        if yeni < 0 and not self.negatif_stok_izni and h.toplam_etki < 0:
            raise StokFisError(f"Yetersiz stok: {p.sku} ({p.name}) mevcut {_norm(p.stock or 0)}, istenen {_norm(-h.toplam_etki)}.")
        p.stock = _norm(yeni)

    def fis_kaydet(self, baslik: dict, satirlar: list[dict], fis_id: int | None = None) -> StokFis:
        """Fişi ve satırlarını tek işlemde kaydeder; stok etkileri uygulanır. Satır sözlüğünde `id` varsa güncellenir
        (eski etkisi önce geri alınır), yoksa eklenir; fişte artık bulunmayan satırlar gizlenir ve etkileri geri alınır.
        Hata olursa hiçbir şey yazılmaz."""
        if not satirlar:
            raise StokFisError("Fişte en az bir satır olmalıdır.")
        if baslik.get("varsayilan_tur", "giris") not in TURLER:
            raise StokFisError("Geçersiz fiş türü.")
        try:
            if fis_id:
                fis = self.db.get(StokFis, fis_id)
                if fis is None or fis.is_deleted:
                    raise StokFisError("Fiş bulunamadı.")
                if fis.kilitli and baslik.get("kilitli", True):
                    raise StokFisError("Fiş kilitli; değiştirmek için önce kilidi kaldırın.")
            else:
                fis = StokFis()
            fis.fis_no = (baslik.get("fis_no") or "").strip() or self.sonraki_fis_no()
            fis.tarih = baslik.get("tarih") or date.today()
            fis.saat = baslik.get("saat") or datetime.now().strftime("%H:%M:%S")
            for alan in ("belge_no", "ozel_kod", "yetki_kodu", "aciklama1", "aciklama2", "aciklama3"):
                setattr(fis, alan, (baslik.get(alan) or "").strip() or None)
            fis.depo_id = baslik.get("depo_id") or self.varsayilan_depo()
            fis.hedef_depo_id = baslik.get("hedef_depo_id")
            fis.varsayilan_tur = baslik.get("varsayilan_tur", "giris")
            fis.kilitli = bool(baslik.get("kilitli"))
            if fis_id is None:
                self.db.add(fis)
            self.db.flush()

            mevcut = {h.id: h for h in self.db.scalars(
                select(StokHareket).where(StokHareket.fis_id == fis.id, StokHareket.is_deleted == False))}  # noqa: E712
            for h in mevcut.values():
                self._etkiyi_geri_al(h)              # eski etkiler kalkar; yeniler aşağıda uygulanır
            kalan = set()
            for sira, v in enumerate(satirlar, start=1):
                v = dict(v)
                sid = v.pop("id", None)
                no = v.pop("_satir", None) or sira
                try:
                    if sid and sid in mevcut:
                        h = mevcut[sid]
                        h.version_id = (h.version_id or 1) + 1
                        kalan.add(sid)
                    else:
                        h = StokHareket(fis_id=fis.id)      # alanlar dolmadan oturuma eklenmez (otomatik flush)
                    h.satir_no = no
                    self._hazirla(h, v, fis)
                    if h.id is None:
                        self.db.add(h)
                    self.db.flush()
                except StokFisError as e:
                    raise StokFisError(f"Satır {no}: {e}") from e
            for sid, h in mevcut.items():
                if sid not in kalan:
                    h.is_deleted = True
            self.db.commit()
            return fis
        except Exception:
            self.db.rollback()
            raise

    def fis_getir(self, fis_id: int) -> tuple[StokFis, list[StokHareket]]:
        fis = self.db.get(StokFis, fis_id)
        if fis is None or fis.is_deleted:
            raise StokFisError("Fiş bulunamadı.")
        satirlar = list(self.db.scalars(
            select(StokHareket).where(StokHareket.fis_id == fis_id, StokHareket.is_deleted == False)  # noqa: E712
            .order_by(StokHareket.satir_no, StokHareket.id)))
        return fis, satirlar

    def fis_gizle(self, fis_id: int) -> None:
        """Fişi ve satırlarını görünümden kaldırır; stok etkileri geri alınır (fiziksel silme yok)."""
        fis, satirlar = self.fis_getir(fis_id)
        if fis.kilitli:
            raise StokFisError("Fiş kilitli; önce kilidi kaldırın.")
        for h in satirlar:
            self._etkiyi_geri_al(h)
            h.is_deleted = True
        fis.is_deleted = True
        self.db.commit()

    # ---- okuma -------------------------------------------------------------------
    def _where(self, f: StokFiltre):
        c = [StokHareket.is_deleted == False]  # noqa: E712
        if f.tur:
            c.append(StokHareket.tur == f.tur)
        if f.depo_id:
            c.append(or_(StokHareket.depo_id == f.depo_id, StokHareket.hedef_depo_id == f.depo_id))
        if f.product_id:
            c.append(StokHareket.product_id == f.product_id)
        if f.tarih_bas:
            c.append(StokHareket.tarih >= f.tarih_bas)
        if f.tarih_bit:
            c.append(StokHareket.tarih <= f.tarih_bit)
        if f.arama.strip():
            q = f"%{f.arama.strip()}%"
            c.append(or_(StokHareket.aciklama.ilike(q), StokHareket.product_id.in_(
                select(Product.id).where(or_(Product.sku.ilike(q), Product.name.ilike(q), Product.barcode.ilike(q)))),
                StokHareket.fis_id.in_(select(StokFis.id).where(or_(StokFis.fis_no.ilike(q), StokFis.belge_no.ilike(q))))))
        return c

    def liste(self, f: StokFiltre, page: int = 1, per_page: int = 25) -> tuple[list[StokHareket], int]:
        where = self._where(f)
        total = self.db.scalar(select(func.count()).select_from(StokHareket).where(*where)) or 0
        stmt = (select(StokHareket).where(*where).order_by(StokHareket.tarih.desc(), StokHareket.id.desc())
                .offset((max(page, 1) - 1) * per_page).limit(per_page))
        return list(self.db.scalars(stmt)), total

    def ozet(self, f: StokFiltre) -> StokOzet:
        o = StokOzet()
        for h in self.db.scalars(select(StokHareket).where(*self._where(f))):
            o.adet += 1
            o.tutar += h.tutar
            if h.toplam_etki > 0 or h.tur in ("giris", "acilis"):
                o.giris += h.miktar if h.tur != "sayim" else h.toplam_etki
            elif h.tur == "cikis" or h.toplam_etki < 0:
                o.cikis += h.miktar if h.tur != "sayim" else -h.toplam_etki
        return o


# ---------------------------------------------------------------------------------------------------
# Stok kartı tarafı: kart düzeltmesi, depo dağılımı, birleşik hareket listesi
# ---------------------------------------------------------------------------------------------------
_ESKI_TUR = {
    "sale": "Satış (Çıkış)", "purchase": "Alış (Giriş)", "adjustment": "Düzeltme", "sync": "Senkron",
    "transfer": "Transfer", "count": "Sayım", "return": "İade",
}
_ESKI_GIRIS = {"purchase", "return"}


def kart_duzeltme(db, product: Product, eski: float, yeni: float, aciklama: str = "Stok kartından düzeltme") -> StokHareket | None:
    """Stok kartında toplam stok elle değiştirildiğinde farkı deftere yazar (depo atanmamış hareket, `fis_id` yok), böylece
    toplam stok ile hareket geçmişi tutarlı kalır. Değişiklik yoksa None döner. Kayıt oturuma eklenir, commit çağırana aittir."""
    fark = round(float(yeni or 0) - float(eski or 0), 4)
    if abs(fark) < 1e-9:
        return None
    h = StokHareket(fis_id=None, product_id=product.id, tur="acilis" if not eski else "sayim", tarih=date.today(),
                    depo_id=None, miktar=abs(float(yeni or 0)) if eski else float(yeni or 0), birim=product.unit or "Adet",
                    aciklama=aciklama, depo_etkisi=0.0, toplam_etki=fark)
    db.add(h)
    return h


def depo_dagilimi(db, product_id: int) -> dict:
    """Ürünün depo bazlı dağılımı: {"depolar": [(kod, ad, bakiye)], "atanmamis": float, "toplam": float}.
    `atanmamis`, toplam stok ile depolardaki (defter) bakiyelerin farkıdır: içe aktarma, kart düzeltmesi ya da fiş
    öncesi mevcut stok gibi depoya atanmamış miktar."""
    svc = StokFisService(db)
    p = db.get(Product, product_id)
    depolar, atanan = [], 0.0
    for w in svc.depolar():
        b = svc.depo_stok(product_id, w.id)
        if abs(b) > 1e-9:
            depolar.append((w.code, w.name or "", _norm(b)))
            atanan += b
    toplam = float(p.stock or 0) if p else 0.0
    return {"depolar": depolar, "atanmamis": _norm(round(toplam - atanan, 4)), "toplam": _norm(toplam)}


def urun_hareketleri(db, product_id: int, limit: int | None = None) -> list[dict]:
    """Ürünün tüm hareketleri (yeni fiş defteri + eski `stock_movements`), yeniden eskiye.
    Her kayıt: tarih (datetime), fis_no, fis_id, tur, depo, hedef, miktar, birim, fiyat, tutar, etki, kaynak."""
    kod = {w.id: w.code for w in db.scalars(select(WarehouseDefinition))}
    out: list[dict] = []
    for h in db.scalars(select(StokHareket).where(StokHareket.product_id == product_id, StokHareket.is_deleted == False)  # noqa: E712
                        .order_by(StokHareket.created_at.desc(), StokHareket.id.desc())):
        out.append({"tarih": h.created_at or datetime.combine(h.tarih, datetime.min.time()), "fis_no": h.fis.fis_no if h.fis else "",
                    "fis_id": h.fis_id, "tur": TURLER.get(h.tur, (h.tur,))[0] if h.fis_id else "Kart Düzeltmesi",
                    "depo": kod.get(h.depo_id, ""), "hedef": kod.get(h.hedef_depo_id, "") if h.hedef_depo_id else "",
                    "miktar": h.miktar, "birim": h.birim or "", "fiyat": h.birim_fiyat, "tutar": h.tutar, "etki": h.toplam_etki,
                    "kaynak": "Fiş" if h.fis_id else "Kart"})
    for m in db.scalars(select(StockMovement).where(StockMovement.product_id == product_id)
                        .order_by(StockMovement.created_at.desc())):
        q = float(m.quantity or 0)
        etki = abs(q) if m.movement_type in _ESKI_GIRIS else -abs(q) if m.movement_type == "sale" else q
        out.append({"tarih": m.created_at, "fis_no": "", "fis_id": None, "tur": _ESKI_TUR.get(m.movement_type, m.movement_type or ""),
                    "depo": "", "hedef": "", "miktar": abs(q), "birim": "", "fiyat": 0.0, "tutar": 0.0, "etki": etki, "kaynak": "Eski"})
    out.sort(key=lambda x: x["tarih"] or datetime.min, reverse=True)
    return out[:limit] if limit else out
