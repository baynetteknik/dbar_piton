"""TOYA ERP - Geliştirme takibi (dev_tracker.db): geliştirici ile yapay zekânın birlikte tuttuğu öneri / hata / yapılacak listesi.

Müşteri veritabanından AYRI bir SQLite dosyasıdır; kullanıcı verisine karışmaz ve paketlenen (exe) sürümde ekranı görünmez
(`gelistirme_acik()`: kaynak koddan çalışırken ya da `TOYA_DEV_BUILD=1` iken açık). Silme = gizleme; her alan değişikliği
`dev_gecmis` tablosuna yazılır (kim, ne zaman, eski → yeni). Tamamlanan işler `SURUM_NOTLARI.md`'nin otomatik bölümüne yazılabilir.
Sürümler (Milestones/Releases) `dev_versions` tablosunda takip edilir ve sürüm kapatıldığında changelog ve Git Tag üretilir."""

from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

TURLER = {"oneri": "Öneri", "gorev": "Yapılacak", "hata": "Hata", "gelistirme": "Geliştirme"}
DURUMLAR = {
    "oneri": "Öneri",
    "planli": "Planlandı",
    "devam": "Devam Ediyor",
    "test": "Testte",
    "tamam": "Tamamlandı",
    "reddedildi": "Reddedildi",
}
ACIK = ("oneri", "planli", "devam", "test")
ONCELIKLER = {1: "Düşük", 2: "Normal", 3: "Yüksek", 4: "Acil"}
SURUM_DURUMLARI = {
    "planli": "Planlandı",
    "gelistirmede": "Geliştirmede",
    "testte": "Testte",
    "yayinlandi": "Yayınlandı",
    "iptal": "İptal Edildi",
}
_ALANLAR = ("tur", "baslik", "aciklama", "modul", "oncelik", "durum", "ekleyen", "surum", "commit_hash")
_SURUM_ALANLAR = ("version_code", "title", "description", "target_date", "release_date", "status")
BEGIN, END = "<!-- DEV-TRACKER:BEGIN -->", "<!-- DEV-TRACKER:END -->"
_KOK = Path(__file__).resolve().parents[3]


def gelistirme_acik() -> bool:
    """Geliştirme ekranı/menüsü gösterilsin mi: kaynak koddan çalışırken evet, paketlenmiş exe'de hayır (TOYA_DEV_BUILD=1 ile zorlanır)."""
    env = os.environ.get("TOYA_DEV_BUILD")
    if env is not None:
        return env == "1"
    return not getattr(sys, "frozen", False)


def varsayilan_yol() -> Path:
    return Path(os.environ.get("TOYA_DEV_TRACKER_DB") or _KOK / "dev_tracker.db")


def _simdi() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DevTrackerError(ValueError):
    """Doğrulama hatası."""


class DevTracker:
    def __init__(self, yol: str | Path | None = None) -> None:
        self.yol = Path(yol) if yol else varsayilan_yol()
        self._ac().close()  # tabloları oluşturur

    @contextmanager
    def _baglan(self):
        """Bağlantıyı işlem sonunda onaylayıp KAPATIR (Windows'ta dosya kilidi kalmasın)."""
        c = self._ac()
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def _ac(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.yol)
        c.row_factory = sqlite3.Row
        c.executescript("""
            CREATE TABLE IF NOT EXISTS dev_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tur TEXT NOT NULL DEFAULT 'gorev', baslik TEXT NOT NULL, aciklama TEXT,
                modul TEXT, oncelik INTEGER DEFAULT 2, durum TEXT NOT NULL DEFAULT 'oneri', ekleyen TEXT, surum TEXT, commit_hash TEXT,
                olusturma TEXT, guncelleme TEXT, tamamlanma TEXT, gizli INTEGER DEFAULT 0, kaynak_id TEXT);
            CREATE TABLE IF NOT EXISTS dev_gecmis (
                id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL, zaman TEXT, kim TEXT, alan TEXT, eski TEXT, yeni TEXT);
            CREATE TABLE IF NOT EXISTS dev_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, version_code TEXT UNIQUE NOT NULL, title TEXT NOT NULL, description TEXT,
                target_date TEXT, release_date TEXT, status TEXT NOT NULL DEFAULT 'planli', created_at TEXT, updated_at TEXT, gizli INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS ix_dev_items_durum ON dev_items(durum);
            CREATE INDEX IF NOT EXISTS ix_dev_items_surum ON dev_items(surum);
            CREATE INDEX IF NOT EXISTS ix_dev_gecmis_item ON dev_gecmis(item_id);
            CREATE INDEX IF NOT EXISTS ix_dev_versions_code ON dev_versions(version_code);
            CREATE INDEX IF NOT EXISTS ix_dev_versions_status ON dev_versions(status);
        """)
        return c

    # ---- yazma (dev_items) -------------------------------------------------
    @staticmethod
    def _dogrula(v: dict) -> None:
        if not (v.get("baslik") or "").strip():
            raise DevTrackerError("Başlık boş olamaz.")
        if v.get("tur", "gorev") not in TURLER or v.get("durum", "oneri") not in DURUMLAR or int(v.get("oncelik", 2) or 2) not in ONCELIKLER:
            raise DevTrackerError("Geçersiz tür, durum ya da öncelik.")

    def ekle(self, baslik: str, *, kim: str = "", **v: Any) -> int:
        v = dict(v, baslik=baslik)
        v.setdefault("tur", "gorev")
        v.setdefault("durum", "oneri")
        v.setdefault("oncelik", 2)
        self._dogrula(v)
        simdi = _simdi()
        tamam = simdi if v["durum"] == "tamam" else None
        with self._baglan() as c:
            cur = c.execute(
                "INSERT INTO dev_items (tur,baslik,aciklama,modul,oncelik,durum,ekleyen,surum,commit_hash,olusturma,guncelleme,tamamlanma,kaynak_id)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (v["tur"], v["baslik"].strip(), v.get("aciklama"), v.get("modul"), int(v["oncelik"]), v["durum"], v.get("ekleyen") or kim,
                 v.get("surum"), v.get("commit_hash"), simdi, simdi, tamam, v.get("kaynak_id")),
            )
            c.execute("INSERT INTO dev_gecmis (item_id,zaman,kim,alan,eski,yeni) VALUES (?,?,?,?,?,?)", (cur.lastrowid, simdi, kim, "olusturuldu", None, v["baslik"]))
            return int(cur.lastrowid)

    def guncelle(self, item_id: int, *, kim: str = "", **v: Any) -> None:
        eski = self.getir(item_id)
        yeni = {k: v[k] for k in _ALANLAR if k in v}
        merged = dict(eski, **yeni)
        self._dogrula(merged)
        degisen = {k: x for k, x in yeni.items() if str(eski.get(k) if eski.get(k) is not None else "") != str(x if x is not None else "")}
        if not degisen:
            return
        simdi = _simdi()
        sets = dict(degisen, guncelleme=simdi)
        if "durum" in degisen:
            sets["tamamlanma"] = simdi if degisen["durum"] == "tamam" else None
        with self._baglan() as c:
            c.execute(f"UPDATE dev_items SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), item_id))
            for k, x in degisen.items():
                c.execute("INSERT INTO dev_gecmis (item_id,zaman,kim,alan,eski,yeni) VALUES (?,?,?,?,?,?)",
                          (item_id, simdi, kim, k, None if eski.get(k) is None else str(eski.get(k)), None if x is None else str(x)))

    def durum_degistir(self, item_id: int, durum: str, *, kim: str = "", commit_hash: str | None = None) -> None:
        v: dict[str, Any] = {"durum": durum}
        if commit_hash:
            v["commit_hash"] = commit_hash
        self.guncelle(item_id, kim=kim, **v)

    def gizle(self, item_id: int, *, kim: str = "") -> None:
        """Silme = gizleme; geçmişe yazılır."""
        with self._baglan() as c:
            c.execute("UPDATE dev_items SET gizli=1, guncelleme=? WHERE id=?", (_simdi(), item_id))
            c.execute("INSERT INTO dev_gecmis (item_id,zaman,kim,alan,eski,yeni) VALUES (?,?,?,?,?,?)", (item_id, _simdi(), kim, "gizli", "0", "1"))

    # ---- okuma (dev_items) -------------------------------------------------
    def getir(self, item_id: int) -> dict[str, Any]:
        with self._baglan() as c:
            r = c.execute("SELECT * FROM dev_items WHERE id=? AND gizli=0", (item_id,)).fetchone()
        if r is None:
            raise DevTrackerError("Kayıt bulunamadı.")
        return dict(r)

    def liste(self, *, arama: str = "", durumlar: tuple[str, ...] | None = None, tur: str | None = None, modul: str | None = None,
              oncelik: int | None = None, surum: str | None = None) -> list[dict[str, Any]]:
        w, p = ["gizli=0"], []
        if durumlar:
            w.append(f"durum IN ({','.join('?' * len(durumlar))})")
            p += list(durumlar)
        for alan, x in (("tur", tur), ("modul", modul), ("oncelik", oncelik)):
            if x:
                w.append(f"{alan}=?")
                p.append(x)
        if surum:
            if surum == "atanmamis":
                w.append("(surum IS NULL OR surum = '')")
            elif surum != "tumu":
                w.append("surum = ?")
                p.append(surum)
        if arama.strip():
            w.append("(baslik LIKE ? OR aciklama LIKE ? OR modul LIKE ? OR commit_hash LIKE ? OR surum LIKE ?)")
            p += [f"%{arama.strip()}%"] * 5
        with self._baglan() as c:
            rows = c.execute(f"SELECT * FROM dev_items WHERE {' AND '.join(w)} "
                             "ORDER BY CASE durum WHEN 'devam' THEN 0 WHEN 'test' THEN 1 WHEN 'planli' THEN 2 WHEN 'oneri' THEN 3 ELSE 4 END, oncelik DESC, id DESC", p).fetchall()
        return [dict(r) for r in rows]

    def gecmis(self, item_id: int) -> list[dict[str, Any]]:
        with self._baglan() as c:
            return [dict(r) for r in c.execute("SELECT * FROM dev_gecmis WHERE item_id=? ORDER BY id DESC", (item_id,)).fetchall()]

    def moduller(self) -> list[str]:
        with self._baglan() as c:
            return [r[0] for r in c.execute("SELECT DISTINCT modul FROM dev_items WHERE gizli=0 AND modul IS NOT NULL AND modul<>'' ORDER BY modul")]

    def ozet(self) -> dict[str, int]:
        with self._baglan() as c:
            return {r[0]: r[1] for r in c.execute("SELECT durum, COUNT(*) FROM dev_items WHERE gizli=0 GROUP BY durum")}

    # ---- SÜRÜM & MİLESTONE YÖNETİMİ (dev_versions) -------------------------
    def surum_ekle(self, version_code: str, title: str, description: str = "", target_date: str = "",
                   status: str = "planli", release_date: str = "") -> int:
        """Yeni bir sürüm / milestone tanımı ekler."""
        vcode = (version_code or "").strip()
        t = (title or "").strip()
        if not vcode:
            raise DevTrackerError("Sürüm kodu boş olamaz (Örn: v1.2.0).")
        if not t:
            raise DevTrackerError("Sürüm başlığı boş olamaz.")
        if status not in SURUM_DURUMLARI:
            raise DevTrackerError(f"Geçersiz sürüm durumu: {status}")

        simdi = _simdi()
        with self._baglan() as c:
            # Check existing version_code
            row = c.execute("SELECT id, gizli FROM dev_versions WHERE version_code=?", (vcode,)).fetchone()
            if row:
                if row["gizli"] == 1:
                    # Restore and update
                    c.execute("UPDATE dev_versions SET title=?, description=?, target_date=?, release_date=?, status=?, gizli=0, updated_at=? WHERE id=?",
                              (t, description, target_date, release_date, status, simdi, row["id"]))
                    return int(row["id"])
                raise DevTrackerError(f"'{vcode}' kodlu sürüm zaten mevcut.")

            cur = c.execute(
                "INSERT INTO dev_versions (version_code, title, description, target_date, release_date, status, created_at, updated_at, gizli)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (vcode, t, description, target_date, release_date, status, simdi, simdi),
            )
            return int(cur.lastrowid)

    def surum_guncelle(self, version_id: int, **v: Any) -> None:
        """Sürüm kaydını günceller. Sürüm kodu değişirse dev_items tablosunu da otomatik günceller."""
        eski = self.surum_getir(version_id)
        simdi = _simdi()
        sets = {}
        for k in _SURUM_ALANLAR:
            if k in v:
                sets[k] = v[k]
        if not sets:
            return

        if "version_code" in sets:
            vcode = (sets["version_code"] or "").strip()
            if not vcode:
                raise DevTrackerError("Sürüm kodu boş olamaz.")
            sets["version_code"] = vcode
            if vcode != eski["version_code"]:
                with self._baglan() as c:
                    var_mi = c.execute("SELECT id FROM dev_versions WHERE version_code=? AND id<>? AND gizli=0", (vcode, version_id)).fetchone()
                    if var_mi:
                        raise DevTrackerError(f"'{vcode}' kodlu başka bir sürüm zaten var.")
                    # Update dev_items with old version code
                    c.execute("UPDATE dev_items SET surum=? WHERE surum=?", (vcode, eski["version_code"]))

        if "status" in sets and sets["status"] not in SURUM_DURUMLARI:
            raise DevTrackerError(f"Geçersiz sürüm durumu: {sets['status']}")

        sets["updated_at"] = simdi
        with self._baglan() as c:
            c.execute(f"UPDATE dev_versions SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?", (*sets.values(), version_id))

    def surum_getir(self, version_id: int) -> dict[str, Any]:
        with self._baglan() as c:
            r = c.execute("SELECT * FROM dev_versions WHERE id=? AND gizli=0", (version_id,)).fetchone()
        if r is None:
            raise DevTrackerError("Sürüm kaydı bulunamadı.")
        return dict(r)

    def surum_getir_kod(self, version_code: str) -> dict[str, Any] | None:
        with self._baglan() as c:
            r = c.execute("SELECT * FROM dev_versions WHERE version_code=? AND gizli=0", (version_code,)).fetchone()
        return dict(r) if r else None

    def surum_sil(self, version_id: int) -> None:
        """Sürümü gizler."""
        with self._baglan() as c:
            c.execute("UPDATE dev_versions SET gizli=1, updated_at=? WHERE id=?", (_simdi(), version_id))

    def surum_liste(self, durum: str | None = None, sadece_aktif: bool = False) -> list[dict[str, Any]]:
        """Tüm sürümleri hesaplanmış istatistikleriyle (toplam, tamamlanan, % ilerleme) listeler."""
        w, p = ["v.gizli=0"], []
        if durum:
            w.append("v.status = ?")
            p.append(durum)
        elif sadece_aktif:
            w.append("v.status IN ('planli', 'gelistirmede', 'testte')")

        with self._baglan() as c:
            rows = c.execute(f"""
                SELECT v.*,
                    COUNT(i.id) AS total_items,
                    SUM(CASE WHEN i.durum = 'tamam' THEN 1 ELSE 0 END) AS completed_items,
                    SUM(CASE WHEN i.durum = 'devam' THEN 1 ELSE 0 END) AS in_progress_items,
                    SUM(CASE WHEN i.durum = 'test' THEN 1 ELSE 0 END) AS test_items,
                    SUM(CASE WHEN i.durum IN ('planli', 'oneri') THEN 1 ELSE 0 END) AS planli_items
                FROM dev_versions v
                LEFT JOIN dev_items i ON i.surum = v.version_code AND i.gizli = 0
                WHERE {' AND '.join(w)}
                GROUP BY v.id
                ORDER BY
                    CASE v.status
                        WHEN 'gelistirmede' THEN 0
                        WHEN 'testte' THEN 1
                        WHEN 'planli' THEN 2
                        WHEN 'yayinlandi' THEN 3
                        ELSE 4
                    END,
                    COALESCE(v.target_date, '9999-99-99') ASC,
                    v.id DESC
            """, p).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            tot = d.get("total_items") or 0
            comp = d.get("completed_items") or 0
            d["total_items"] = tot
            d["completed_items"] = comp
            d["in_progress_items"] = d.get("in_progress_items") or 0
            d["test_items"] = d.get("test_items") or 0
            d["planli_items"] = d.get("planli_items") or 0
            d["progress_percent"] = int((comp / tot) * 100) if tot > 0 else 0
            result.append(d)
        return result

    def surumler(self) -> list[str]:
        """Sistemde kayıtlı ve kullanılan benzersiz sürüm kodlarını listeler."""
        with self._baglan() as c:
            # 1. dev_versions'tan
            v_codes = [r[0] for r in c.execute("SELECT version_code FROM dev_versions WHERE gizli=0 ORDER BY id DESC")]
            # 2. dev_items'ta olup dev_versions'ta henüz olmayanlar
            item_codes = [r[0] for r in c.execute("SELECT DISTINCT surum FROM dev_items WHERE gizli=0 AND surum IS NOT NULL AND surum<>''")]
            all_codes = list(dict.fromkeys(v_codes + item_codes))
            return all_codes

    def surume_gorevleri_ata(self, item_ids: list[int], version_code: str | None, kim: str = "") -> None:
        """Seçilen geliştirme kayıtlarını belirtilen sürüme topluca atar."""
        if not item_ids:
            return
        vcode = version_code.strip() if version_code else None
        for item_id in item_ids:
            self.guncelle(item_id, surum=vcode, kim=kim)

    def surum_kapat_ve_yayinla(self, version_code: str, release_date: str | None = None,
                               git_tag: bool = False, tag_message: str = "", kim: str = "") -> dict[str, Any]:
        """Sürümü 'yayinlandi' durumuna alır, sürüm notlarını basar ve isteğe bağlı git tag oluşturur."""
        vcode = version_code.strip()
        ver = self.surum_getir_kod(vcode)
        simdi_tarih = release_date or datetime.now().strftime("%Y-%m-%d")

        if ver:
            self.surum_guncelle(ver["id"], status="yayinlandi", release_date=simdi_tarih)
        else:
            # Sürüm tablosunda yoksa otomatik ekle
            self.surum_ekle(vcode, title=f"Sürüm {vcode}", status="yayinlandi", release_date=simdi_tarih)

        # SURUM_NOTLARI.md güncelle
        self.surum_notlarina_yaz()

        # Git Tag işlemi
        tag_ok, tag_info = False, "Git etiketi oluşturulmadı."
        if git_tag:
            try:
                import git_tracker
                tag_ok, tag_info = git_tracker.create_git_tag(vcode, tag_message or f"Sürüm {vcode} yayını")
            except Exception as e:
                tag_ok, tag_info = False, f"Git tag hatası: {e}"

        return {
            "version_code": vcode,
            "release_date": simdi_tarih,
            "tag_created": tag_ok,
            "tag_message": tag_info,
        }

    # ---- içe / dışa aktarım --------------------------------------------------
    def git_gorevlerini_al(self, git_db: str | Path | None = None) -> int:
        """`git_tracker.db` içindeki eski görev listesini bir kez içe alır (aynı başlık tekrar eklenmez). @return eklenen sayı"""
        git_db = Path(git_db) if git_db else _KOK / "git_tracker.db"
        if not git_db.exists():
            return 0
        harita = {"Yapıldı": "tamam", "Devam Ediyor": "devam", "Bekliyor": "planli", "Planlandı": "planli"}
        n = 0
        g = sqlite3.connect(git_db)
        try:
            rows = g.execute("SELECT id, category, title, description, status, related_commit, completed_at FROM tasks").fetchall()
        except sqlite3.OperationalError:
            return 0
        finally:
            g.close()
        mevcut = {r["kaynak_id"] for r in self._tum_kaynaklar()}
        for tid, kat, baslik, acik, durum, commit, bitti in rows:
            kaynak = f"git_tracker:{tid}"
            if kaynak in mevcut:
                continue
            i = self.ekle(baslik, tur="gelistirme", modul=kat, aciklama=acik, durum=harita.get(durum, "planli"), commit_hash=commit,
                          ekleyen="git_tracker", kaynak_id=kaynak, kim="içe aktarma")
            if bitti:
                with self._baglan() as c:
                    c.execute("UPDATE dev_items SET tamamlanma=? WHERE id=?", (bitti, i))
            n += 1
        return n

    def _tum_kaynaklar(self):
        with self._baglan() as c:
            return c.execute("SELECT kaynak_id FROM dev_items WHERE kaynak_id IS NOT NULL").fetchall()

    def surum_notlari_metni(self) -> str:
        """Tamamlanan işlerin sürüm ve ay bazlı Markdown özeti."""
        with self._baglan() as c:
            items = c.execute("SELECT * FROM dev_items WHERE gizli=0 AND durum='tamam' ORDER BY COALESCE(tamamlanma, guncelleme) DESC, id DESC").fetchall()
            versions = c.execute("SELECT * FROM dev_versions WHERE gizli=0 ORDER BY COALESCE(release_date, target_date, created_at) DESC, id DESC").fetchall()

        if not items:
            return "_Henüz tamamlanmış kayıt yok._"

        v_dict = {v["version_code"]: dict(v) for v in versions}
        items_by_version: dict[str, list[dict]] = {}
        unversioned_items: list[dict] = []

        for item in items:
            s = item["surum"]
            if s and s.strip():
                items_by_version.setdefault(s.strip(), []).append(dict(item))
            else:
                unversioned_items.append(dict(item))

        satirlar: list[str] = []

        # 1. Sürümlü tamamlanan maddeler
        for vcode, v_items in items_by_version.items():
            ver_info = v_dict.get(vcode)
            rel_date = ver_info.get("release_date") if ver_info else None
            t_date = ver_info.get("target_date") if ver_info else None
            tarih_str = rel_date or t_date or "Yayınlandı"
            baslik_str = f" — {ver_info['title']}" if ver_info and ver_info.get("title") and ver_info["title"] != vcode else ""

            satirlar.append(f"\n## [{vcode}] — {tarih_str}{baslik_str}")
            if ver_info and ver_info.get("description"):
                satirlar.append(f"_{ver_info['description'].strip()}_\n")

            # Türlerine göre grupla
            features = [x for x in v_items if x.get("tur") in ("gelistirme", "gorev")]
            fixes = [x for x in v_items if x.get("tur") == "hata"]
            ideas = [x for x in v_items if x.get("tur") == "oneri"]

            if features:
                satirlar.append("### 🛠️ Geliştirmeler & Yeni Özellikler")
                for itm in features:
                    gun = (itm["tamamlanma"] or itm["guncelleme"] or "")[:10]
                    ek = f" — `{itm['commit_hash'][:7]}`" if itm.get("commit_hash") else ""
                    modul = f"**{itm['modul']}:** " if itm.get("modul") else ""
                    satirlar.append(f"- {gun} · {modul}{itm['baslik']}{ek}")

            if fixes:
                satirlar.append("### 🐞 Düzeltilen Hatalar")
                for itm in fixes:
                    gun = (itm["tamamlanma"] or itm["guncelleme"] or "")[:10]
                    ek = f" — `{itm['commit_hash'][:7]}`" if itm.get("commit_hash") else ""
                    modul = f"**{itm['modul']}:** " if itm.get("modul") else ""
                    satirlar.append(f"- {gun} · {modul}{itm['baslik']}{ek}")

            if ideas:
                satirlar.append("### 💡 Tamamlanan İyileştirmeler & Öneriler")
                for itm in ideas:
                    gun = (itm["tamamlanma"] or itm["guncelleme"] or "")[:10]
                    ek = f" — `{itm['commit_hash'][:7]}`" if itm.get("commit_hash") else ""
                    modul = f"**{itm['modul']}:** " if itm.get("modul") else ""
                    satirlar.append(f"- {gun} · {modul}{itm['baslik']}{ek}")

        # 2. Sürümsüz tamamlanan maddeler (Ay ay listele)
        if unversioned_items:
            satirlar.append("\n## Genel Geliştirmeler (Sürümsüz)")
            ay = None
            for itm in unversioned_items:
                gun = (itm["tamamlanma"] or itm["guncelleme"] or "")[:10]
                if gun[:7] != ay:
                    ay = gun[:7]
                    satirlar += ["", f"### {ay}"]
                ek = f" — `{itm['commit_hash'][:7]}`" if itm.get("commit_hash") else ""
                modul = f"**{itm['modul']}:** " if itm.get("modul") else ""
                satirlar.append(f"- {gun} · {modul}{itm['baslik']}{ek}")

        return "\n".join(satirlar).strip()

    def surum_notlarina_yaz(self, yol: str | Path | None = None) -> Path:
        """`SURUM_NOTLARI.md` içindeki otomatik bölümü (işaretçiler arası) yeniler; el yazısı bölümlere dokunmaz."""
        yol = Path(yol) if yol else _KOK / "SURUM_NOTLARI.md"
        metin = yol.read_text(encoding="utf-8") if yol.exists() else "# TOYA ERP — Sürüm Notları\n"
        blok = f"{BEGIN}\n## Geliştirme Takibi (otomatik)\n_Kaynak: dev_tracker.db — tamamlanan kayıtlar._\n\n{self.surum_notlari_metni()}\n{END}"
        if BEGIN in metin and END in metin:
            a, b = metin.index(BEGIN), metin.index(END) + len(END)
            yeni = metin[:a] + blok + metin[b:]
        else:
            yeni = metin.rstrip() + "\n\n---\n\n" + blok + "\n"
        yol.write_text(yeni, encoding="utf-8")
        return yol
