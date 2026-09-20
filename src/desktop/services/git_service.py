"""
TOYA ERP - Git Servisi (Qt'siz, test edilebilir)

Sürüm & Git Takip ekranının arka ucu. Aidat projesindeki (GitService.php) işlevlerin TOYA karşılığıdır:
durum/karşılaştırma, eşitleme tavsiyesi, uzak depo testi, güvenli geri alma, kimlik yapılandırması.

Kimlik bilgisi ilkeleri:
  - Token/parola ASLA uzak depo adresine (remote URL) yazılmaz ve TOYA veritabanına konmaz.
  - "gcm" (Google ile / tarayıcıdan giriş): Git Credential Manager tarayıcıyı açar; kullanıcı GitHub'da Google ile
    oturum açar, oluşan belirteci Windows Kimlik Bilgisi Yöneticisi saklar. TOYA'da hiçbir gizli bilgi kalmaz.
  - "token": erişim belirteci `git credential approve` ile Git'in kimlik bilgisi deposuna verilir.
  - "ssh": adres olduğu gibi kullanılır; ortak anahtar ekranda gösterilir.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

AUTH_GCM = "gcm"
AUTH_TOKEN = "token"
AUTH_SSH = "ssh"
AUTH_TYPES = (AUTH_GCM, AUTH_TOKEN, AUTH_SSH)

#: Depoya yanlışlıkla girmemesi gereken dosya adları (commit öncesi uyarı için).
_SENSITIVE = re.compile(
    r"(^|/)(\.env(\..*)?|config\.local\.php|id_(rsa|ed25519|ecdsa)(\.pub)?|.*\.(pem|key|pfx|p12|kdbx|sqlite|sqlite3|fdb)|"
    r"credentials?\.json|secrets?\.(json|ya?ml))$",
    re.IGNORECASE,
)
_HASH_RE = re.compile(r"^[0-9a-fA-F]{4,40}$")
_URL_CREDS = re.compile(r"^(https?://)([^/@\s]+)@")


@dataclass
class GitResult:
    ok: bool
    out: str = ""
    code: int = 0

    @property
    def text(self) -> str:
        return self.out.strip()


@dataclass
class Advice:
    status: str  # danger | warning | info | success
    title: str
    advice: str
    action: str = "none"  # init | remote | backup | push | pull | none
    action_label: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def find_git() -> str | None:
    p = shutil.which("git")
    if p:
        return p
    for cand in (
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
    ):
        if os.path.exists(cand):
            return cand
    return None


def mask_url(url: str) -> str:
    """Adresteki kullanıcı/parola/token kısmını gizler."""
    return _URL_CREDS.sub(r"\1***@", url or "")


def strip_url_credentials(url: str) -> str:
    return _URL_CREDS.sub(r"\1", url or "")


def validate_repo_url(url: str) -> str | None:
    """Geçerliyse None, değilse Türkçe hata metni. Adrese gömülü parola/token reddedilir."""
    u = (url or "").strip()
    if not u:
        return "Depo adresi boş olamaz."
    if re.search(r"\s", u):
        return "Depo adresi boşluk içeremez."
    m = _URL_CREDS.match(u)
    if m and ":" in m.group(2):
        return ("Adrese parola/token yazmayın; erişim belirtecini ayrı alana girin "
                "(güvenli şekilde Windows Kimlik Bilgisi Yöneticisi'nde saklanır).")
    if re.match(r"^(https?|ssh|git)://\S+$", u) or re.match(r"^[\w.-]+@[\w.-]+:\S+$", u) or os.path.isdir(u):
        return None
    return "Depo adresi https://…, git@sunucu:yol veya var olan bir yerel klasör olmalı."


def is_sensitive(path: str) -> bool:
    return bool(_SENSITIVE.search(path.replace("\\", "/")))


class GitService:
    def __init__(self, repo_path: Path | str | None = None, git_exe: str | None = None) -> None:
        self.repo = Path(repo_path) if repo_path else REPO_ROOT
        self.git = git_exe or find_git()

    # ------------------------------------------------------------------ çalıştırma
    def available(self) -> bool:
        return self.git is not None

    def run(self, args: list[str], timeout: int = 60, env: dict[str, str] | None = None,
            input_text: str | None = None, config: list[str] | None = None) -> GitResult:
        if not self.git:
            return GitResult(False, "Git bulunamadı (git.exe kurulu ve PATH'te olmalı).", 127)
        cmd = [self.git, "-c", "core.quotepath=false"]
        for c in config or []:
            cmd += ["-c", c]
        cmd += args
        e = dict(os.environ)
        e.setdefault("GIT_TERMINAL_PROMPT", "0")  # takılıp beklemesin
        e["LC_ALL"] = "C"
        e.update(env or {})
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            p = subprocess.run(cmd, cwd=str(self.repo), capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout, env=e, input=input_text, creationflags=flags)
        except subprocess.TimeoutExpired:
            return GitResult(False, f"Git işlemi {timeout} sn içinde tamamlanmadı.", 124)
        except OSError as exc:
            return GitResult(False, f"Git çalıştırılamadı: {exc}", 126)
        return GitResult(p.returncode == 0, (p.stdout or "") + (p.stderr or "" if p.returncode else ""), p.returncode)

    # ------------------------------------------------------------------ temel bilgiler
    def is_repo(self) -> bool:
        return self.run(["rev-parse", "--is-inside-work-tree"]).text == "true"

    def branch(self) -> str:
        r = self.run(["rev-parse", "--abbrev-ref", "HEAD"])
        return r.text if r.ok and r.text else "main"

    def remote_url(self) -> str:
        r = self.run(["remote", "get-url", "origin"])
        return r.text if r.ok else ""

    def masked_remote(self) -> str:
        return mask_url(self.remote_url())

    def user(self) -> tuple[str, str]:
        return self.run(["config", "user.name"]).text, self.run(["config", "user.email"]).text

    def ssh_public_key(self) -> str:
        home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or "~").expanduser()
        for name in ("id_ed25519.pub", "id_rsa.pub"):
            f = home / ".ssh" / name
            if f.is_file():
                return f.read_text(encoding="utf-8", errors="replace").strip()
        return ""

    def commit_history(self, limit: int = 20) -> list[dict[str, str]]:
        r = self.run(["log", f"-n{max(1, min(500, limit))}", "--pretty=format:%H%x1f%an%x1f%cI%x1f%s"])
        rows = []
        for line in (r.out.splitlines() if r.ok else []):
            parts = line.split("\x1f")
            if len(parts) == 4:
                rows.append({"hash": parts[0], "author": parts[1], "date": parts[2], "message": parts[3]})
        return rows

    # ------------------------------------------------------------------ değişiklikler
    def changes(self) -> list[dict[str, Any]]:
        r = self.run(["status", "--porcelain", "-uall"])
        out = []
        for line in (r.out.splitlines() if r.ok else []):
            if len(line) < 4:
                continue
            code, path = line[:2], line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            path = path.strip().strip('"')
            if "?" in code:
                kind = "untracked"
            elif "D" in code:
                kind = "deleted"
            elif "R" in code:
                kind = "renamed"
            elif "A" in code:
                kind = "added"
            else:
                kind = "modified"
            top = path.split("/", 1)[0] if "/" in path else "(kök)"
            out.append({"code": code, "file": path, "type": kind, "category": top,
                        "staged": code[0] not in (" ", "?"), "sensitive": is_sensitive(path)})
        return out

    def ahead_behind(self, branch: str | None = None) -> dict[str, Any]:
        """origin/<dal> ile karşılaştırma. Uzak izleme dalı yoksa tracking=False (önce fetch gerekir)."""
        branch = branch or self.branch()
        ref = f"origin/{branch}"
        if not self.run(["rev-parse", "--verify", "--quiet", ref]).ok:
            return {"tracking": False, "ahead": 0, "behind": 0}
        r = self.run(["rev-list", "--left-right", "--count", f"{ref}...HEAD"])
        if not r.ok or len(r.text.split()) != 2:
            return {"tracking": False, "ahead": 0, "behind": 0}
        behind, ahead = (int(x) for x in r.text.split())
        return {"tracking": True, "ahead": ahead, "behind": behind}

    def comparison(self) -> dict[str, Any]:
        """Aidat'taki getDetailedComparison karşılığı: sayımlar, klasör kategorileri, uyarılar."""
        if not self.available():
            return {"ok": False, "message": "Git bulunamadı.", "warnings": [], "summary": {"total": 0}}
        if not self.is_repo():
            return {"ok": False, "message": "Git deposu bulunamadı.", "warnings": [], "summary": {"total": 0}}
        changes = self.changes()
        summary = {"total": len(changes), "modified": 0, "added": 0, "deleted": 0, "renamed": 0, "untracked": 0}
        cats: dict[str, int] = {}
        for c in changes:
            summary[c["type"]] += 1
            cats[c["category"]] = cats.get(c["category"], 0) + 1
        ab = self.ahead_behind()
        sensitive = [c["file"] for c in changes if c["sensitive"]]
        warnings: list[dict[str, str]] = []
        if ab["behind"]:
            warnings.append({"type": "danger", "title": f"Uzak depoda {ab['behind']} yeni commit var",
                             "message": "Çakışmayı önlemek için göndermeden önce Pull yapın.", "action": "pull"})
        if ab["ahead"]:
            warnings.append({"type": "info", "title": f"{ab['ahead']} commit gönderilmeyi bekliyor",
                             "message": "Yerelde kayıtlı, uzak depoya henüz basılmamış.", "action": "push"})
        if changes:
            warnings.append({"type": "warning", "title": f"{len(changes)} dosyada değişiklik var",
                             "message": "Kaydedilmemiş değişiklikler tek commit olarak gönderilebilir.", "action": "backup"})
        if sensitive:
            warnings.append({"type": "danger", "title": f"{len(sensitive)} hassas görünen dosya değişiklikler arasında",
                             "message": ", ".join(sensitive[:5]) + (" …" if len(sensitive) > 5 else "")
                             + " — gizli bilgi içeriyorsa .gitignore'a ekleyin.", "action": "none"})
        if not changes and not ab["ahead"] and not ab["behind"]:
            warnings.append({"type": "success", "title": "Çalışma dizini temiz", "message": "Bekleyen değişiklik yok.", "action": "none"})
        return {
            "ok": True, "branch": self.branch(), "summary": summary,
            "categories": sorted(cats.items(), key=lambda kv: (-kv[1], kv[0])),
            "files": changes, "remote": ab, "sensitive": sensitive, "warnings": warnings,
        }

    # ------------------------------------------------------------------ tavsiye
    def sync_advice(self, cmp: dict[str, Any] | None = None) -> Advice:
        """Aidat'taki getSyncAdvice: tek bakışta ne yapılması gerektiği. Önceden hesaplanmış `comparison()` verilirse
        git yeniden çalıştırılmaz (her çağrı birkaç git süreci demektir)."""
        if not self.available():
            return Advice("danger", "Git bulunamadı", "git.exe kurulu ve PATH'te olmalı.")
        if not self.is_repo():
            return Advice("danger", "Git deposu bulunamadı", "Proje klasöründe Git deposu yok.", "init", "Git Başlat")
        if not self.remote_url():
            return Advice("warning", "Uzak depo tanımlı değil",
                          "Yedek almak için bir bağlantı profili ekleyip etkinleştirin.", "remote", "Profil Ekle")
        info = cmp if cmp is not None else self.comparison()
        ab, n = info["remote"], info["summary"]["total"]
        last = self.commit_history(1)
        ago = time_ago(last[0]["date"]) if last else "Henüz commit yok"
        extra = {"last_backup_ago": ago, "changed": n, "ahead": ab["ahead"], "behind": ab["behind"],
                 "last_hash": last[0]["hash"][:7] if last else "", "last_message": last[0]["message"] if last else ""}
        if ab["behind"]:
            return Advice("danger", f"Uzak depoda {ab['behind']} yeni commit var",
                          "Göndermeden önce Pull yapın; aksi halde çakışma çıkabilir.", "pull", "Değişiklikleri Çek (Pull)", extra)
        if n:
            return Advice("warning", f"{n} dosyada değişiklik var (yedek alınmalı)",
                          "Olası veri kaybına karşı Git'e gönderin (Commit & Push).", "backup", "Git'e Gönder", extra)
        if ab["ahead"]:
            return Advice("info", f"{ab['ahead']} commit uzak depoya gönderilmedi",
                          "Yerelde kayıtlı; push bekliyor.", "push", "Uzak Depoya Gönder (Push)", extra)
        if not ab["tracking"]:
            return Advice("info", "Uzak depo henüz karşılaştırılamadı",
                          "Fetch yaparak uzak depo durumunu öğrenin.", "none", "", extra)
        return Advice("success", "Her şey güvende (tam senkron)", "Yerel ve uzak depo aynı durumda.", "none", "", extra)

    # ------------------------------------------------------------------ uzak depo / kimlik
    def test_remote(self, timeout: int = 40) -> tuple[bool, str]:
        if not self.available():
            return False, "Git bulunamadı."
        if not self.is_repo():
            return False, "Git deposu bulunamadı."
        if not self.remote_url():
            return False, "Uzak depo (origin) tanımlı değil."
        r = self.run(["ls-remote", "--heads", "origin"], timeout=timeout)
        if r.ok:
            return True, "Uzak depoya bağlanıldı ve kimlik doğrulandı."
        err = r.text
        low = err.lower()
        if any(k in low for k in ("authentication", "403", "401", "denied", "invalid username", "could not read username", "terminal prompts disabled")):
            return False, ("Kimlik doğrulanamadı. 'Google ile giriş yap' düğmesiyle tarayıcıdan oturum açın "
                           "veya profilde erişim belirteci (repo yetkili) tanımlayın. Ayrıntı: " + _clip(mask_url(err)))
        if "not found" in low or "does not appear to be a git repository" in low:
            return False, "Depo bulunamadı: adresi ve depo adını kontrol edin. Ayrıntı: " + _clip(mask_url(err))
        if "could not resolve host" in low or "unable to access" in low:
            return False, "Sunucuya erişilemedi (internet/adres). Ayrıntı: " + _clip(mask_url(err))
        return False, "Bağlantı doğrulanamadı: " + _clip(mask_url(err))

    def fetch(self, timeout: int = 90) -> GitResult:
        return self.run(["fetch", "--all", "--prune"], timeout=timeout)

    def set_remote(self, url: str) -> GitResult:
        url = strip_url_credentials(url.strip())
        if self.remote_url():
            return self.run(["remote", "set-url", "origin", url])
        return self.run(["remote", "add", "origin", url])

    def set_user(self, name: str, email: str) -> None:
        if name.strip():
            self.run(["config", "user.name", name.strip()])
        if email.strip():
            self.run(["config", "user.email", email.strip()])

    def apply_profile(self, profile: dict[str, Any]) -> tuple[bool, str]:
        """Profili git yapılandırmasına uygular (uzak adres + yazar kimliği). Gizli bilgi yazmaz."""
        err = validate_repo_url(str(profile.get("repo_url", "")))
        if err:
            return False, err
        if not self.is_repo():
            return False, "Git deposu bulunamadı."
        r = self.set_remote(str(profile["repo_url"]))
        if not r.ok:
            return False, "Uzak adres ayarlanamadı: " + _clip(r.text)
        self.set_user(str(profile.get("username") or ""), str(profile.get("email") or ""))
        if profile.get("auth_type") == AUTH_GCM:
            self.run(["config", "credential.helper", "manager"])  # Git Credential Manager
        return True, "Profil uygulandı."

    def forget_credentials(self, helper: str | None = None) -> None:
        """Bu uzak sunucu için kayıtlı (eski/geçersiz) kimlik bilgilerini kimlik deposundan siler."""
        m = re.match(r"^https?://([^/@]+@)?([^/]+)", strip_url_credentials(self.remote_url()))
        if m:
            cfg = [f"credential.helper={helper}"] if helper else None
            self.run(["credential", "reject"], input_text=f"protocol=https\nhost={m.group(2)}\n\n", config=cfg)

    def login_with_browser(self, timeout: int = 300) -> tuple[bool, str]:
        """Git Credential Manager'ı tetikler: tarayıcı açılır, kullanıcı GitHub'da (Google ile) oturum açar.
        Önce eski/geçersiz kayıtlı kimlik silinir (aksi halde Git eski parolayı yollayıp 'Password authentication
        is not supported' hatası alır)."""
        if not self.remote_url():
            return False, "Önce bir profil etkinleştirin (uzak depo tanımlı değil)."
        self.forget_credentials("manager")
        r = self.run(["ls-remote", "--heads", "origin"], timeout=timeout, env={"GCM_INTERACTIVE": "always"},
                     config=["credential.helper=manager"])
        if r.ok:
            return True, "Giriş başarılı; kimlik Windows Kimlik Bilgisi Yöneticisi'nde saklandı."
        return False, "Giriş tamamlanamadı: " + _clip(mask_url(r.text))

    def store_token(self, url: str, username: str, token: str, helper: str | None = None) -> tuple[bool, str]:
        """Belirteci Git'in kimlik bilgisi deposuna verir (URL'ye/veritabanına yazılmaz)."""
        m = re.match(r"^https?://([^/@]+@)?([^/]+)", strip_url_credentials(url.strip()))
        if not m:
            return False, "Belirteç yalnızca https adresleri için kaydedilebilir."
        if not token.strip():
            return False, "Belirteç boş."
        if "\n" in token or "\r" in token or "\n" in username:
            return False, "Geçersiz karakter."
        payload = f"protocol=https\nhost={m.group(2)}\nusername={username.strip() or 'x-access-token'}\npassword={token.strip()}\n\n"
        cfg = [f"credential.helper={helper}"] if helper else None
        r = self.run(["credential", "approve"], input_text=payload, config=cfg)
        return (True, "Belirteç güvenli kimlik deposuna kaydedildi.") if r.ok else (False, "Belirteç kaydedilemedi: " + _clip(r.text))

    # ------------------------------------------------------------------ geri alma
    def rollback(self, ref: str) -> dict[str, Any]:
        """Dosyaları `ref` commit'indeki hale getirir. Önce geri dönüş noktası oluşturur:
        bekleyen değişiklikler stash'e alınır ve mevcut HEAD'e etiket konur. Geçmiş silinmez.
        Not: `ref`'ten sonra EKLENEN dosyalar silinmez (yalnızca izlenen dosyaların içeriği geri gelir)."""
        ref = (ref or "").strip()
        if not _HASH_RE.match(ref):
            return {"ok": False, "message": "Geçersiz commit kodu."}
        if not self.is_repo():
            return {"ok": False, "message": "Git deposu bulunamadı."}
        full = self.run(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
        if not full.ok or not full.text:
            return {"ok": False, "message": "Bu commit depoda bulunamadı."}
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        tag = f"toya-geri-alma-oncesi-{stamp}"
        n = 1
        while self.run(["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"]).ok:  # aynı saniyede tekrar: benzersiz ad
            n += 1
            tag = f"toya-geri-alma-oncesi-{stamp}-{n}"
        stashed = False
        if self.changes():
            st = self.run(["stash", "push", "-u", "-m", f"TOYA geri alma öncesi {stamp} → {ref}"])
            if not st.ok:
                return {"ok": False, "message": "Bekleyen değişiklikler güvene alınamadı: " + _clip(st.text)}
            stashed = True
        tg = self.run(["tag", tag, "HEAD"])
        if not tg.ok:
            if stashed:
                self.run(["stash", "pop"])
            return {"ok": False, "message": "Geri dönüş noktası oluşturulamadı: " + _clip(tg.text)}
        co = self.run(["checkout", full.text, "--", "."])
        if not co.ok:
            if stashed:
                self.run(["stash", "pop"])
            return {"ok": False, "message": "Geri yükleme başarısız: " + _clip(co.text)}
        msg = f"{full.text[:7]} sürümündeki dosya durumuna dönüldü. Geri dönüş noktası: {tag}"
        if stashed:
            msg += " (bekleyen değişiklikleriniz 'git stash' içinde saklandı)"
        return {"ok": True, "message": msg, "tag": tag, "stashed": stashed, "hash": full.text}


def _clip(text: str, n: int = 240) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def time_ago(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    s = max(0, int((now - dt).total_seconds()))
    if s < 90:
        return "az önce"
    if s < 3600:
        return f"{s // 60} dk önce"
    if s < 86400:
        return f"{s // 3600} saat önce"
    return f"{s // 86400} gün önce"
