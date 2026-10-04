"""TOYA ERP - DonemService: firmaya bağlı çalışma dönemi (mali yıl / esnek dönem) CRUD'u.

`Donem` modeli (2026-09-30), `Company.periods_json` JSON alanının ve eski, firmadan bağımsız sahte
"Çalışma Dönemi Tanımları" ayarlar panelinin yerini alan TEK gerçek kaynaktır. Bir firmanın AYNI ANDA
birden fazla dönemi "aktif" (açık) olabilir (kullanıcı isteği, 2026-09-30) — ör. yıl sonu kapanışında
hem geçmiş dönem düzeltmeleri hem yeni dönem kayıtları aynı anda girilebilmeli; dönemler arası tekillik
ZORLANMAZ, her dönem bağımsız aktif/kapalı işaretlenir. Silme = gizleme.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from src.core.models import Donem

DURUMLAR = {"aktif": "Aktif", "kapali": "Kapalı"}


class DonemError(ValueError):
    pass


@dataclass
class DonemSaveResult:
    success: bool
    donem_id: int | None = None
    error: str | None = None


class DonemService:
    def __init__(self, db_session=None) -> None:
        self.db = db_session

    # ------------------------------------------------------------------
    def liste(self, company_id: int) -> list[Donem]:
        if not self.db or not company_id:
            return []
        return list(self.db.scalars(
            select(Donem).where(Donem.company_id == company_id, Donem.is_deleted == False)  # noqa: E712
            .order_by(Donem.baslangic.desc()),
        ))

    def acik_donemler(self, company_id: int) -> list[Donem]:
        """Firmanın şu an aktif (açık) TÜM dönemleri — birden fazla olabilir (ör. yıl sonu kapanışında
        hem eski hem yeni dönem birlikte açık kalabilir)."""
        if not self.db or not company_id:
            return []
        return list(self.db.scalars(
            select(Donem).where(Donem.company_id == company_id, Donem.is_deleted == False,  # noqa: E712
                                 Donem.durum == "aktif").order_by(Donem.baslangic.desc()),
        ))

    def guncel_donem(self, company_id: int) -> Donem | None:
        """Yeni bir belge/fiş için varsayılan önerilecek TEK dönem: açık dönemler arasından bugünün
        tarihini kapsayan; yoksa en son başlayan açık dönem; hiç açık dönem yoksa None."""
        acikler = self.acik_donemler(company_id)
        if not acikler:
            return None
        bugun = date.today()
        for d in acikler:
            if d.baslangic <= bugun <= d.bitis:
                return d
        return acikler[0]

    def get(self, donem_id: int) -> Donem | None:
        return self.db.get(Donem, donem_id) if self.db else None

    # ------------------------------------------------------------------
    def kaydet(self, company_id: int, v: dict, donem_id: int | None = None) -> DonemSaveResult:
        if not self.db:
            return DonemSaveResult(success=True, donem_id=donem_id)
        code = (v.get("code") or "").strip()
        if not code:
            return DonemSaveResult(success=False, error="Dönem adı/kodu boş olamaz.")
        bas, bit = v.get("baslangic"), v.get("bitis")
        if not bas or not bit:
            return DonemSaveResult(success=False, error="Başlangıç ve bitiş tarihi zorunludur.")
        if bit < bas:
            return DonemSaveResult(success=False, error="Bitiş, başlangıçtan önce olamaz.")
        try:
            d = self.db.get(Donem, donem_id) if donem_id else None
            if d is None:
                mevcut = self.db.scalar(select(Donem).where(
                    Donem.company_id == company_id, Donem.code == code, Donem.is_deleted == False,  # noqa: E712
                ))
                if mevcut:
                    return DonemSaveResult(success=False, error=f"'{code}' kodlu dönem bu firmada zaten var.")
                d = Donem(company_id=company_id)
                self.db.add(d)
            d.code, d.baslangic, d.bitis = code, bas, bit
            d.durum = v.get("durum", d.durum or "aktif")
            self.db.commit()
            return DonemSaveResult(success=True, donem_id=d.id)
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            return DonemSaveResult(success=False, error=str(exc))

    def aktif_yap(self, donem_id: int) -> DonemSaveResult:
        """Dönemi aktif (açık) işaretler — firmanın BAŞKA dönemleri de aktif kalmaya devam eder,
        tekillik zorlanmaz (bir firmanın aynı anda birden fazla açık dönemi olabilir)."""
        d = self.get(donem_id)
        if d is None or d.is_deleted:
            return DonemSaveResult(success=False, error="Dönem bulunamadı.")
        d.durum = "aktif"
        self.db.commit()
        return DonemSaveResult(success=True, donem_id=d.id)

    def kapat(self, donem_id: int) -> DonemSaveResult:
        d = self.get(donem_id)
        if d is None or d.is_deleted:
            return DonemSaveResult(success=False, error="Dönem bulunamadı.")
        d.durum = "kapali"
        self.db.commit()
        return DonemSaveResult(success=True, donem_id=d.id)

    def donemde_hareket_var_mi(self, donem_id: int) -> tuple[bool, str]:
        """Bu döneme ait herhangi bir ticari/mali hareket (Cari, Kasa, Banka, Fiş, Belge) var mı kontrol eder."""
        if not self.db or not donem_id:
            return False, ""
        d = self.get(donem_id)
        if d is None:
            return False, ""

        from src.core.models import CariHareket, FinansHareket, Quotation

        # 1. Cari Hareket kontrolü
        c_count = self.db.scalar(
            select(CariHareket.id).where(
                CariHareket.is_deleted == False,  # noqa: E712
                CariHareket.tarih >= d.baslangic,
                CariHareket.tarih <= d.bitis,
            ).limit(1),
        )
        if c_count is not None:
            return True, "Cari hareket kayıtları mevcut"

        # 2. Finans / Kasa / Banka Hareket kontrolü
        f_count = self.db.scalar(
            select(FinansHareket.id).where(
                FinansHareket.is_deleted == False,  # noqa: E712
                FinansHareket.tarih >= d.baslangic,
                FinansHareket.tarih <= d.bitis,
            ).limit(1),
        )
        if f_count is not None:
            return True, "Kasa/Banka hareket kayıtları mevcut"

        # 3. Belge / Teklif / Sipariş / Fatura kontrolü
        q_count = self.db.scalar(
            select(Quotation.id).where(
                Quotation.is_deleted == False,  # noqa: E712
                Quotation.company_id == d.company_id,
                Quotation.date >= d.baslangic,
                Quotation.date <= d.bitis,
            ).limit(1),
        )
        if q_count is not None:
            return True, "İşlenmiş ticari belge kayıtları mevcut"

        return False, ""

    def anlik_yedek_al(self, aciklama: str = "Dönem silme öncesi otomatik snapshot") -> str | None:
        """Dönem silinmesi gibi kritik işlemlerden önce anlık güvenli veritabanı kopyası oluşturur."""
        try:
            import shutil
            from datetime import datetime
            from pathlib import Path
            
            db_bind = self.db.get_bind() if self.db else None
            if not db_bind:
                return None
            db_file = getattr(db_bind.url, "database", None)
            if not db_file or db_file == ":memory:":
                return "in_memory_backup"

            src_path = Path(db_file).resolve()
            if not src_path.exists():
                return None

            backup_dir = src_path.parent / "backups" / "snapshots"
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_path = backup_dir / f"toya_erp_snapshot_{ts}.db"
            shutil.copy2(src_path, target_path)
            return str(target_path)
        except Exception:  # noqa: BLE001
            return None

    def donem_guvenli_sil(self, donem_id: int, zorla: bool = False) -> tuple[bool, str, str | None]:
        """Dönemi güvenli siler. Hareket varsa zorla silme onayı ve otomatik yedek gerektirir."""
        d = self.get(donem_id)
        if d is None or d.is_deleted:
            return False, "Dönem bulunamadı.", None

        has_mov, reason = self.donemde_hareket_var_mi(donem_id)
        if has_mov and not zorla:
            return False, f"Bu dönemde işlem kayıtları mevcuttur ({reason}).", None

        backup_file = None
        if has_mov and zorla:
            backup_file = self.anlik_yedek_al(f"Dönem {d.code} silme öncesi")

        d.is_deleted = True
        self.db.commit()
        return True, "Dönem başarıyla arşivlendi/silindi.", backup_file

    def gizle(self, donem_id: int) -> bool:
        ok, _, _ = self.donem_guvenli_sil(donem_id, zorla=True)
        return ok

    # ------------------------------------------------------------------ Firma kartı alt-tablosu köprüsü
    def to_subtable(self, company_id: int) -> list[dict]:
        """Firma kartındaki 'Dönemler' alt-tablosunun beklediği list[dict] biçimi."""
        return [
            {"ad": d.code, "baslangic": d.baslangic.strftime("%d.%m.%Y") if d.baslangic else "",
             "bitis": d.bitis.strftime("%d.%m.%Y") if d.bitis else "",
             "aktif": "Evet" if d.durum == "aktif" else "Hayır"}
            for d in self.liste(company_id)
        ]

    def senkron_subtable(self, company_id: int, satirlar: list[dict]) -> None:
        """Firma kartı alt-tablosundan (Company kaydıyla birlikte) gelen dönem satırlarını gerçek `Donem`
        tablosuyla eşitler: kod eşleşiyorsa günceller, yeni kodlar eklenir, listede artık olmayanlar gizlenir."""
        if not self.db or not company_id:
            return
        mevcutlar = {d.code: d for d in self.liste(company_id)}
        gelen_kodlar: set[str] = set()
        for satir in satirlar:
            kod = (satir.get("ad") or "").strip()
            if not kod:
                continue
            gelen_kodlar.add(kod)
            bas = _parse_tarih(satir.get("baslangic"))
            bit = _parse_tarih(satir.get("bitis"))
            if not bas or not bit:
                continue
            d = mevcutlar.get(kod)
            if d is None:
                d = Donem(company_id=company_id, code=kod, durum="kapali")
                self.db.add(d)
                mevcutlar[kod] = d
            d.baslangic, d.bitis, d.is_deleted = bas, bit, False
            aktif_mi = str(satir.get("aktif", "")).strip().lower() in ("evet", "true", "1", "aktif")
            d.durum = "aktif" if aktif_mi else "kapali"
        for kod, d in mevcutlar.items():
            if kod not in gelen_kodlar:
                d.is_deleted = True
        self.db.commit()


def _parse_tarih(metin: str | None) -> date | None:
    if not metin:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            from datetime import datetime
            return datetime.strptime(metin.strip(), fmt).date()
        except ValueError:
            continue
    return None
