"""
TOYA ERP - Zamanlanmış Yedek Ajanı (arayüzsüz)

    python -m src.desktop.backup_agent --due            zamanı gelen işleri çalıştırır
    python -m src.desktop.backup_agent --job <id>       tek bir işi çalıştırır
    python -m src.desktop.backup_agent --register [dk]  Windows Görev Zamanlayıcı'ya ekler (varsayılan 15 dk)
    python -m src.desktop.backup_agent --unregister     görevi kaldırır
    python -m src.desktop.backup_agent --status         görev kayıtlı mı?

TOYA uygulaması kapalıyken de yedeklerin alınmasını sağlar. Aynı iş uygulamada da çalışıyorsa kilit dosyası
çifte çalışmayı engeller. Çıkış kodu: 0 = hata yok, 1 = en az bir iş hata verdi.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TASK_NAME = "TOYA ERP Yedek Ajani"
ROOT = Path(__file__).resolve().parents[2]


def task_command(python: str | None = None, root: Path = ROOT) -> str:
    py = python or sys.executable
    return f'cmd /c cd /d "{root}" && "{py}" -m src.desktop.backup_agent --due'


def register_args(minutes: int = 15, python: str | None = None, root: Path = ROOT) -> list[str]:
    minutes = max(5, min(1439, int(minutes)))
    return ["schtasks", "/Create", "/F", "/SC", "MINUTE", "/MO", str(minutes), "/TN", TASK_NAME, "/TR", task_command(python, root)]


def _schtasks(args: list[str]) -> tuple[bool, str]:
    try:
        # schtasks çıktısı konsolun OEM kod sayfasındadır; varsayılan kodlamayla okumak okuyucu iş parçacığını çökertir.
        p = subprocess.run(args, capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"schtasks çalıştırılamadı: {exc.__class__.__name__}"
    enc = "oem" if sys.platform == "win32" else "utf-8"
    text = (p.stdout or p.stderr or b"").decode(enc, errors="replace").strip()
    return p.returncode == 0, text


def register(minutes: int = 15) -> tuple[bool, str]:
    ok, out = _schtasks(register_args(minutes))
    return ok, ("Görev eklendi." if ok else f"Görev eklenemedi: {out[:200]}")


def unregister() -> tuple[bool, str]:
    ok, out = _schtasks(["schtasks", "/Delete", "/F", "/TN", TASK_NAME])
    return ok, ("Görev kaldırıldı." if ok else f"Görev kaldırılamadı: {out[:200]}")


def status() -> bool:
    return _schtasks(["schtasks", "/Query", "/TN", TASK_NAME])[0]


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--register" in args:
        i = args.index("--register")
        mins = int(args[i + 1]) if len(args) > i + 1 and args[i + 1].isdigit() else 15
        ok, msg = register(mins)
        print(msg)
        return 0 if ok else 1
    if "--unregister" in args:
        ok, msg = unregister()
        print(msg)
        return 0 if ok else 1
    if "--status" in args:
        on = status()
        print("Görev kayıtlı." if on else "Görev kayıtlı değil.")
        return 0 if on else 1

    from src.core.database import DatabaseManager
    from src.desktop.reports.email_engine import EmailEngine, SMTPConfig
    from src.desktop.services.backup import service
    from src.desktop.services.backup.models import JobStore

    db = DatabaseManager().get_db()
    engine = EmailEngine(SMTPConfig.from_db(db))
    if "--job" in args:
        job = JobStore(db).get(args[args.index("--job") + 1])
        if not job:
            print("İş bulunamadı.")
            return 1
        results = [(job, service.execute(db, job, engine, log=print))]
    elif "--due" in args:
        results = service.run_due(db, engine=engine)
    else:
        print(__doc__)
        return 2
    for job, res in results:
        print(f"[{res.status}] {job.name}: {res.message}")
    return 1 if any(r.status == "error" for _j, r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
