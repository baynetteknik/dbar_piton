"""
TOYA ERP - Yedek İşi Çalıştırıcı

Bir işi uçtan uca yürütür: arşivle → doğrula → (isteğe bağlı) şifrele ve şifreli dosyayı da doğrula → saklama →
hedeflere yükle (yeniden denemeli, boyut doğrulamalı). Bu modül VERİTABANINA DOKUNMAZ (arka plan iş parçacığında
güvenle çalışsın diye); durum/günlük kaydı `finish_run` ile çağıranın (ana) iş parçacığında yazılır.

Başarı ölçütü: yerel yedek oluştu VE doğrulandı. Bulut yüklemesi başarısızsa sonuç "warning" olur
(yedek elde ama dış kopya yok) — sessizce başarılı sayılmaz.
"""

from __future__ import annotations

import logging
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.desktop.services import sync_log_service
from src.desktop.services.backup import archive, crypto, disk_watch, file_job, toya_backup
from src.desktop.services.backup.models import KIND_TOYA, BackupJob, JobStore
from src.desktop.services.backup.providers import Provider, with_retry

logger = logging.getLogger(__name__)
Progress = Callable[[int, int], None]
Log = Callable[[str], None]


@dataclass
class RunContext:
    db_path: Path | None = None            # TOYA işleri için
    db_key: str | None = None
    password: str | None = None            # şifreleme parolası (kimlik deposundan)
    providers: list[Provider] = field(default_factory=list)
    retry_delays: tuple[int, ...] = (5, 15, 30, 60)
    sleep: Callable[[float], None] = time.sleep
    now: datetime | None = None
    disk_root: str | None = None           # '{disk}' yer tutucusu için takılı sürücü kökü
    disks: dict[str, str] = field(default_factory=dict)   # '{disk:KIMLIK}' için {kayıtlı disk kimliği: takılı sürücü kökü}


@dataclass
class RunResult:
    status: str                            # ok | warning | error | nochange
    message: str
    path: Path | None = None
    files: int = 0
    size: int = 0
    seconds: float = 0.0
    started: float = 0.0
    warnings: list[str] = field(default_factory=list)
    uploads: list[tuple[str, bool, str]] = field(default_factory=list)
    removed: int = 0
    targets: list[tuple[str, bool, str]] = field(default_factory=list)   # yazıldığı tüm hedefler: klasör + dış hedefler

    @property
    def ok(self) -> bool:
        return self.status in ("ok", "warning", "nochange")


def _decrypt_verify(enc: Path, password: str) -> archive.VerifyResult:
    with tempfile.TemporaryDirectory(prefix="toya_dogrula_") as tmp:
        name = enc.name[: -len(crypto.SUFFIX)]
        out = Path(tmp) / name
        try:
            crypto.decrypt_file(enc, out, password)
        except crypto.DecryptError as exc:
            return archive.VerifyResult(False, str(exc))
        return archive.verify_archive(out)


def run_job(job: BackupJob, ctx: RunContext, progress: Progress | None = None, log: Log | None = None) -> RunResult:
    say = log or (lambda _m: None)
    started = time.time()
    res = _run(job, ctx, progress, say, started)
    res.seconds = time.time() - started
    res.started = started
    yerel = [(f"Klasör/disk: {res.path.parent}", True, "Yazıldı")] if res.path is not None and res.status in ("ok", "warning") else []
    res.targets = yerel + list(res.uploads)
    return res


def _run(job: BackupJob, ctx: RunContext, progress: Progress | None, say: Log, started: float) -> RunResult:
    resolved = disk_watch.resolve_dest(job.dest_dir, ctx.disk_root, ctx.disks)
    if resolved is None:
        return RunResult("error", "Yedek diski takılı değil (hedef klasör bir harici diske bağlı).")
    dest = Path(resolved)
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return RunResult("error", f"Hedef klasör oluşturulamadı: {exc}")

    # --- mirror: arşivsiz, değişenleri kopyala
    if job.fmt == "mirror":
        say("Klasör senkronu başlıyor…")
        copied, skipped, warns = file_job.mirror(job.sources, dest / job.slug, job.includes, job.excludes)
        msg = f"Senkron tamamlandı: {copied} dosya kopyalandı, {skipped} değişmemiş."
        return RunResult("warning" if warns else "ok", msg + (f" {len(warns)} dosya okunamadı." if warns else ""),
                         dest / job.slug, copied, 0, warnings=warns)

    since = None
    full = True
    if job.kind != KIND_TOYA and job.mode == "incremental" and job.state.get("last_success_ts"):
        since, full = float(job.state["last_success_ts"]), False
    ext = archive.archive_ext(job.fmt)
    final = dest / file_job.backup_name(job.slug, full, ext, ctx.now)

    # --- 1) arşivle
    say("Arşiv oluşturuluyor…")
    try:
        if job.kind == KIND_TOYA:
            if ctx.db_path is None:
                return RunResult("error", "Veritabanı yolu bilinmiyor.")
            manifest = toya_backup.build(final, ctx.db_path, job.sources, job.includes, job.excludes, job.fmt,
                                         ctx.db_key, job.name, progress)
        else:
            entries = file_job.plan(job.sources, job.includes, job.excludes, since)
            if not entries:
                if not full:
                    return RunResult("nochange", "Son yedekten beri değişen dosya yok.")
                return RunResult("error", "Kaynakta yedeklenecek dosya bulunamadı.")
            manifest = archive.build_archive(final, entries, job.fmt, {"kind": "files", "job": job.name, "mode": "full" if full else "incremental"},
                                             progress=progress)
    except (OSError, RuntimeError) as exc:
        final.unlink(missing_ok=True)
        return RunResult("error", f"Arşiv oluşturulamadı: {exc}")
    warns = [f"Atlandı: {s}" for s in manifest.get("skipped", [])]

    # --- 2) doğrula
    say("Yedek doğrulanıyor…")
    v = archive.verify_archive(final)
    if not v.ok:
        final.unlink(missing_ok=True)
        return RunResult("error", "Yedek doğrulanamadı, silindi: " + v.message)
    files, size = v.files, v.size

    # --- 3) şifrele
    if job.encrypt:
        if not ctx.password:
            final.unlink(missing_ok=True)
            return RunResult("error", "Şifreleme parolası tanımlı değil (Yedekleme → Şifreleme).")
        say("Şifreleniyor…")
        enc = final.with_name(final.name + crypto.SUFFIX)
        try:
            crypto.encrypt_file(final, enc, ctx.password)
        except (OSError, ValueError) as exc:
            final.unlink(missing_ok=True)
            enc.unlink(missing_ok=True)
            return RunResult("error", f"Şifrelenemedi: {exc}")
        cv = _decrypt_verify(enc, ctx.password)
        if not cv.ok:
            final.unlink(missing_ok=True)
            enc.unlink(missing_ok=True)
            return RunResult("error", "Şifreli yedek doğrulanamadı, silindi: " + cv.message)
        final.unlink(missing_ok=True)
        final = enc

    # --- 4) saklama
    removed = len(file_job.apply_retention(dest, job.slug, job.keep))

    # --- 5) dış hedefler
    uploads: list[tuple[str, bool, str]] = []
    for prov in ctx.providers:
        say(f"Yükleniyor: {prov.label}…")
        try:
            with_retry(lambda p=prov: p.upload(final, final.name, progress), delays=ctx.retry_delays, sleep=ctx.sleep)
            remote = prov.size(final.name)
            if remote is not None and remote != final.stat().st_size:
                raise OSError(f"Boyut uyuşmuyor (uzak {remote}, yerel {final.stat().st_size})")
            temizlenen = _remote_retention(prov, job.slug, job.keep)
            uploads.append((prov.label, True, "Yüklendi" + (f" · {temizlenen} eski yedek temizlendi" if temizlenen else "")))
        except Exception as exc:  # noqa: BLE001 - bir hedefin hatası diğerlerini durdurmamalı
            uploads.append((prov.label, False, str(exc)[:200]))
            logger.warning("Yedek yüklenemedi (%s): %s", prov.label, exc)
    failed = [u for u in uploads if not u[1]]
    msg = f"{final.name}: {files} dosya, {size:,} bayt" + (", şifreli" if job.encrypt else "") + "."
    if removed:
        msg += f" {removed} eski yedek saklama kuralıyla temizlendi."
    if failed:
        msg += " Yüklenemeyen hedef: " + ", ".join(f"{u[0]} ({u[2]})" for u in failed)
    if warns:
        msg += f" {len(warns)} dosya atlandı."
    return RunResult("warning" if (failed or warns) else "ok", msg, final, files, size, warnings=warns, uploads=uploads, removed=removed)


def _remote_retention(prov, slug: str, keep: int) -> int:
    """Yükleme başarılıysa uzak hedefteki (Drive / FTP / S3 / klasör) eski yedek kümelerini de saklama kuralına göre siler.
    Yalnızca bu işin adıyla eşleşen dosyalara dokunulur; hata olursa yükleme sonucunu bozmaz."""
    try:
        silinecek = file_job.retention_victims([f["name"] for f in prov.list()], slug, keep)
        for name in silinecek:
            prov.delete(name)
        return len(silinecek)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Uzak saklama temizliği yapılamadı (%s): %s", getattr(prov, "label", "?"), exc)
        return 0


def finish_run(db, store: JobStore, job: BackupJob, res: RunResult) -> None:
    """Ana iş parçacığında: iş durumunu ve aktarım günlüğünü yazar."""
    now = datetime.now().isoformat(timespec="seconds")
    state = {"last_run": now, "last_status": res.status, "last_message": res.message[:500],
             "fail_streak": int(job.state.get("fail_streak", 0)) + 1 if res.status == "error" else 0}
    atlanan = [(w.split(":", 1)[0], False, w.split(":", 1)[-1].strip()) for w in res.warnings if w.startswith("Hedef atlandı")]
    targets = list(res.targets or res.uploads) + atlanan
    state["last_targets"] = [[n, ok, str(m)[:120]] for n, ok, m in targets][:10]
    if res.status in ("ok", "warning"):
        state.update(last_success=now, last_success_ts=res.started, last_file=res.path.name if res.path else "")
    elif res.status == "nochange":
        state.update(last_success=now)                              # güncel: değişiklik yok da başarılı bir denetimdir
    store.update_state(job.id, **state)
    sync_log_service.record(
        db, "backup", sync_log_service.DIR_BACKUP_JOB, res.ok, f"[{job.name}] {res.message}",
        {"job": job.name, "job_id": job.id, "files": res.files, "bytes": res.size, "status": res.status,
         "mode": "mirror" if job.fmt == "mirror" else ("inc" if res.path and "-inc-" in res.path.name else "full"),
         "seconds": round(res.seconds, 1), "file": res.path.name if res.path else "",
         "uploads": [[n, ok, str(m)[:120]] for n, ok, m in targets][:10], "warnings": len(res.warnings), "dest": job.dest_dir},
        datetime.utcfromtimestamp(res.started) if res.started else None,
    )
