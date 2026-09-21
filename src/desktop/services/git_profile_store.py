"""
TOYA ERP - Git Bağlantı Profilleri (git_tracker.db)

Aidat'taki `git_connections` tablosunun karşılığı. Bir profil = depo adresi + dal + kimlik türü + yazar kimliği.
Profilde TOKEN/PAROLA SAKLANMAZ (bkz. git_service: belirteç Git'in kimlik bilgisi deposuna gider).
Silme yalnızca gizler (`hidden=1`); programın "silme = gizleme" ilkesi.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import git_tracker
from src.desktop.services.git_service import AUTH_GCM, AUTH_TYPES, GitService, strip_url_credentials, validate_repo_url

_COLS = ("title", "provider", "auth_type", "email", "username", "repo_url", "branch")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_table(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS git_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            provider TEXT DEFAULT 'github',
            auth_type TEXT DEFAULT 'gcm',
            email TEXT,
            username TEXT,
            repo_url TEXT NOT NULL,
            branch TEXT DEFAULT 'main',
            is_active INTEGER DEFAULT 0,
            hidden INTEGER DEFAULT 0,
            last_sync_at TEXT,
            last_status TEXT,
            last_message TEXT,
            created_at TEXT
        )"""
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(git_profiles)")}
    if "login_at" not in cols:              # eski veritabanları için: son başarılı giriş/doğrulama zamanı
        conn.execute("ALTER TABLE git_profiles ADD COLUMN login_at TEXT")
    conn.commit()


def _conn():
    conn = git_tracker.get_db_connection()
    ensure_table(conn)
    return conn


def list_profiles() -> list[dict[str, Any]]:
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM git_profiles WHERE hidden = 0 ORDER BY is_active DESC, title COLLATE NOCASE").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_profile(profile_id: int) -> dict[str, Any] | None:
    conn = _conn()
    try:
        r = conn.execute("SELECT * FROM git_profiles WHERE id = ? AND hidden = 0", (profile_id,)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def active_profile() -> dict[str, Any] | None:
    return next((p for p in list_profiles() if p["is_active"]), None)


def clean_profile(data: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Girdiyi temizler ve doğrular. @return (temiz veri, hata metni | None). Belirteç alanı bilerek yok sayılır."""
    p = {k: str(data.get(k) or "").strip() for k in _COLS}
    p["provider"] = p["provider"] or "github"
    p["branch"] = p["branch"] or "main"
    p["auth_type"] = p["auth_type"] if p["auth_type"] in AUTH_TYPES else AUTH_GCM
    if not p["title"]:
        return p, "Profil başlığı zorunludur."
    err = validate_repo_url(p["repo_url"])
    if err:
        return p, err
    p["repo_url"] = strip_url_credentials(p["repo_url"])
    if p["email"] and not ("@" in p["email"] and "." in p["email"].split("@")[-1]):
        return p, "E-posta adresi geçersiz."
    if any(ch in p["branch"] for ch in " ~^:?*[\\") or p["branch"].startswith("-"):
        return p, "Dal adı geçersiz."
    return p, None


def save_profile(data: dict[str, Any], make_active: bool = False) -> tuple[bool, str, int | None]:
    p, err = clean_profile(data)
    if err:
        return False, err, None
    conn = _conn()
    try:
        pid = int(data.get("id") or 0)
        if pid:
            if not conn.execute("SELECT 1 FROM git_profiles WHERE id = ? AND hidden = 0", (pid,)).fetchone():
                return False, "Profil bulunamadı.", None
            conn.execute(
                "UPDATE git_profiles SET title=?, provider=?, auth_type=?, email=?, username=?, repo_url=?, branch=? WHERE id=?",
                (*(p[k] for k in _COLS), pid),
            )
        else:
            cur = conn.execute(
                "INSERT INTO git_profiles (title, provider, auth_type, email, username, repo_url, branch, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (*(p[k] for k in _COLS), _now()),
            )
            pid = int(cur.lastrowid)
        conn.commit()
    finally:
        conn.close()
    if make_active:
        return activate_profile_flag(pid) + (pid,)
    return True, f"Profil kaydedildi: {p['title']}", pid


def activate_profile_flag(profile_id: int) -> tuple[bool, str]:
    """Yalnızca veritabanındaki 'etkin' bayrağını değiştirir (tek etkin profil)."""
    conn = _conn()
    try:
        r = conn.execute("SELECT title FROM git_profiles WHERE id = ? AND hidden = 0", (profile_id,)).fetchone()
        if not r:
            return False, "Profil bulunamadı."
        conn.execute("UPDATE git_profiles SET is_active = 0")
        conn.execute("UPDATE git_profiles SET is_active = 1 WHERE id = ?", (profile_id,))
        conn.commit()
        return True, f"'{r['title']}' etkin profil yapıldı."
    finally:
        conn.close()


def activate(profile_id: int, service: GitService) -> tuple[bool, str]:
    """Profili etkinleştirir ve git'e uygular. Uygulama başarısızsa önceki etkin profil değişmez."""
    prof = get_profile(profile_id)
    if not prof:
        return False, "Profil bulunamadı."
    ok, msg = service.apply_profile(prof)
    if not ok:
        record_result(profile_id, False, msg)
        return False, msg
    activate_profile_flag(profile_id)
    return True, f"'{prof['title']}' etkin: uzak adres ve yazar kimliği ayarlandı."


def hide_profile(profile_id: int) -> bool:
    """Profili kullanıcı görünümünden kaldırır (veri silinmez)."""
    conn = _conn()
    try:
        cur = conn.execute("UPDATE git_profiles SET hidden = 1, is_active = 0 WHERE id = ? AND hidden = 0", (profile_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def record_result(profile_id: int, ok: bool, message: str) -> None:
    conn = _conn()
    try:
        conn.execute("UPDATE git_profiles SET last_sync_at=?, last_status=?, last_message=? WHERE id=?",
                     (_now(), "ok" if ok else "error", (message or "")[:500], profile_id))
        conn.commit()
    finally:
        conn.close()


def set_login(profile_id: int, ok: bool) -> None:
    """Giriş durumunu kaydeder: başarılı giriş/bağlantı doğrulaması → zaman damgası, kimlik hatası → temizlenir."""
    conn = _conn()
    try:
        conn.execute("UPDATE git_profiles SET login_at = ? WHERE id = ?", (_now() if ok else None, profile_id))
        conn.commit()
    finally:
        conn.close()


def seed_from_repo(service: GitService) -> dict[str, Any] | None:
    """Profil yoksa ve depoda origin tanımlıysa mevcut yapılandırmadan bir profil oluşturur (aidat'taki gibi)."""
    if list_profiles():
        return None
    url = service.remote_url()
    if not url:
        return None
    name, email = service.user()
    ok, _msg, pid = save_profile({
        "title": "Ana Depo (origin)", "auth_type": AUTH_GCM, "repo_url": strip_url_credentials(url),
        "branch": service.branch(), "username": name, "email": email,
    }, make_active=True)
    return get_profile(pid) if ok and pid else None
