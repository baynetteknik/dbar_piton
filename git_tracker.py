"""
Git & Task Tracker Utility for TOYA ERP / Multi-CMS Manager
Manages git_tracker.db SQLite database to track git commits, push statuses, working tree changes,
repositories, accounts, and executes asynchronous Git operations (Commit, Push, Fetch, Pull, Stash)
with real-time stage progress.
"""

import logging
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

logger = logging.getLogger(__name__)

DB_PATH = "git_tracker.db"


def get_git_executable() -> str | None:
    """Finds git executable in system PATH or common installation paths on Windows."""
    # 1. Check PATH
    git_path = shutil.which("git")
    if git_path and os.path.exists(git_path):
        return git_path

    # 2. Check common Windows installation paths
    candidates = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\bin\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\git.exe"),
        r"C:\ProgramData\chocolatey\bin\git.exe",
        os.path.expanduser(r"~\scoop\apps\git\current\bin\git.exe"),
        os.path.expanduser(r"~\scoop\shims\git.exe"),
    ]
    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    return None


def is_git_available() -> bool:
    """Returns True if git executable is found on the system."""
    return get_git_executable() is not None


def run_git_cmd(args: list[str], **kwargs) -> subprocess.CompletedProcess | None:
    """Safely runs a git command using the detected git executable."""
    git_exe = get_git_executable()
    if not git_exe:
        return None

    cmd = [git_exe] + args
    try:
        kwargs.setdefault("capture_output", True)
        kwargs.setdefault("text", True)
        kwargs.setdefault("check", False)
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs.setdefault("startupinfo", startupinfo)
        return subprocess.run(cmd, **kwargs)
    except FileNotFoundError:
        logger.warning(f"Git executable not found: {git_exe}")
        return None
    except Exception as e:
        logger.warning(f"Error running git command {args}: {e}")
        return None


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table for Git Commits & Push history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS git_commits (
            commit_hash TEXT PRIMARY KEY,
            branch TEXT,
            author TEXT,
            commit_date TEXT,
            pushed_status TEXT DEFAULT 'Pushed',
            message TEXT,
            files_changed INTEGER DEFAULT 0,
            synced_at TEXT
        )
    """)

    # Table for Tasks (Completed & Pending)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL CHECK(status IN ('Yapıldı', 'Devam Ediyor', 'Bekliyor', 'Planlandı')),
            related_branch TEXT,
            related_commit TEXT,
            created_at TEXT,
            completed_at TEXT
        )
    """)

    # Table for Tracking Log Events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            description TEXT
        )
    """)

    # Table for Git Repositories (Depo Yönetimi)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS git_repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            remote_url TEXT NOT NULL,
            default_branch TEXT DEFAULT 'main',
            auth_type TEXT DEFAULT 'HTTPS',
            is_default INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    # Table for Git Accounts / Credentials (Kullanıcı Yönetimi)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS git_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT,
            token TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_repositories() -> list[dict[str, Any]]:
    """Returns list of configured git repositories."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM git_repositories ORDER BY is_default DESC, name ASC")
    rows = cursor.fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


def add_repository(name: str, remote_url: str, default_branch: str = "main", auth_type: str = "HTTPS", is_default: int = 0) -> int:
    """Adds a new git repository definition."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if is_default:
        cursor.execute("UPDATE git_repositories SET is_default = 0")

    cursor.execute("""
        INSERT INTO git_repositories (name, remote_url, default_branch, auth_type, is_default, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, remote_url, default_branch, auth_type, is_default, now_str))
    repo_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return repo_id


def delete_repository(repo_id: int):
    """Deletes a git repository definition."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM git_repositories WHERE id = ?", (repo_id,))
    conn.commit()
    conn.close()


def get_accounts() -> list[dict[str, Any]]:
    """Returns list of configured git user accounts."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM git_accounts ORDER BY is_default DESC, username ASC")
    rows = cursor.fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


def add_account(username: str, email: str = "", token: str = "", is_default: int = 0) -> int:
    """Adds a new git account / token."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if is_default:
        cursor.execute("UPDATE git_accounts SET is_default = 0")

    cursor.execute("""
        INSERT INTO git_accounts (username, email, token, is_default, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (username, email, token, is_default, now_str))
    acc_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return acc_id


def delete_account(account_id: int):
    """Deletes a git account."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM git_accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()


def get_git_status() -> dict[str, Any]:
    """Inspects real Git working tree, remote repository, and branch status."""
    info: dict[str, Any] = {
        "branch": "main" if not is_git_available() else "unknown",
        "remote_url": "",
        "upstream": "",
        "ahead_count": 0,
        "behind_count": 0,
        "unpushed_hashes": [],
        "changed_files": [],
        "modified_count": 0,
        "is_clean": True,
        "git_available": is_git_available(),
    }

    if not is_git_available():
        info["branch"] = "Git Bulunamadı"
        return info

    try:
        # 1. Current Branch
        res = run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"])
        if res and res.returncode == 0 and res.stdout.strip():
            info["branch"] = res.stdout.strip()

        # 2. Remote URL
        res = run_git_cmd(["config", "--get", "remote.origin.url"])
        if res and res.returncode == 0:
            info["remote_url"] = res.stdout.strip()

        # 3. Upstream Branch
        res = run_git_cmd(["rev-parse", "--abbrev-ref", "@{u}"])
        if res and res.returncode == 0 and res.stdout.strip():
            info["upstream"] = res.stdout.strip()
            # Ahead / Behind Counts
            res_ahead = run_git_cmd(["rev-list", "@{u}..HEAD", "--count"])
            if res_ahead and res_ahead.returncode == 0 and res_ahead.stdout.strip():
                try:
                    info["ahead_count"] = int(res_ahead.stdout.strip())
                except ValueError:
                    info["ahead_count"] = 0

            res_unpushed = run_git_cmd(["rev-list", "@{u}..HEAD"])
            if res_unpushed and res_unpushed.returncode == 0 and res_unpushed.stdout.strip():
                info["unpushed_hashes"] = [h.strip() for h in res_unpushed.stdout.strip().split("\n") if h.strip()]
        else:
            # No upstream tracking branch set yet: all commits in current branch are local
            res_local_all = run_git_cmd(["rev-list", "HEAD", "-n", "20"])
            if res_local_all and res_local_all.returncode == 0 and res_local_all.stdout.strip():
                info["unpushed_hashes"] = [h.strip() for h in res_local_all.stdout.strip().split("\n") if h.strip()]
                info["ahead_count"] = len(info["unpushed_hashes"])

        # 4. Changed / Untracked Files (git status --porcelain)
        res_status = run_git_cmd(["status", "--porcelain"])
        if res_status and res_status.returncode == 0 and res_status.stdout.strip():
            lines = res_status.stdout.strip().split("\n")
            changed = []
            for line in lines:
                if len(line) < 3:
                    continue
                code = line[:2]
                file_path = line[3:].strip()
                staged = code[0] not in (" ", "?")
                status_desc = "Değiştirildi"
                if "A" in code or "?" in code:
                    status_desc = "Yeni / İzlenmeyen"
                elif "D" in code:
                    status_desc = "Silindi"
                elif "R" in code:
                    status_desc = "Yeniden Adlandırıldı"

                changed.append({
                    "code": code,
                    "file": file_path,
                    "status": status_desc,
                    "staged": staged,
                })
            info["changed_files"] = changed
            info["modified_count"] = len(changed)
            info["is_clean"] = len(changed) == 0

    except Exception as e:
        logger.error(f"Error inspecting git status: {e}", exc_info=True)

    return info


def get_git_branches() -> list[str]:
    """Returns list of local git branches."""
    branches = []
    if not is_git_available():
        return branches
    try:
        res = run_git_cmd(["branch", "--format=%(refname:short)"])
        if res and res.returncode == 0 and res.stdout.strip():
            branches = [b.strip() for b in res.stdout.strip().split("\n") if b.strip()]
    except Exception as e:
        logger.error(f"Error getting branches: {e}")
    return branches


def sync_git_history():
    """Sync commits from git log into SQLite database with accurate pushed status."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        git_info = get_git_status()
        current_branch = git_info["branch"]
        unpushed_set = set(git_info.get("unpushed_hashes", []))

        if is_git_available():
            # Get recent git commits via git log
            res = run_git_cmd(["log", "-n", "50", "--pretty=format:%H|%an|%ad|%s", "--date=iso"])
            if res and res.returncode == 0 and res.stdout.strip():
                lines = res.stdout.strip().split("\n")
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                for line in lines:
                    if not line:
                        continue
                    parts = line.split("|")
                    if len(parts) >= 4:
                        chash, author, cdate, msg = parts[0], parts[1], parts[2], "|".join(parts[3:])
                        pushed_status = "Yerel (Gönderilmedi)" if chash in unpushed_set else "Gönderildi"

                        # Check if commit exists
                        cursor.execute("SELECT commit_hash FROM git_commits WHERE commit_hash = ?", (chash,))
                        row = cursor.fetchone()
                        if not row:
                            cursor.execute("""
                                INSERT INTO git_commits (commit_hash, branch, author, commit_date, pushed_status, message, synced_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (chash, current_branch, author, cdate, pushed_status, msg, now_str))

                            cursor.execute("""
                                INSERT INTO activity_log (timestamp, event_type, description)
                                VALUES (?, 'Git Commit Recorded', ?)
                            """, (now_str, f"Commit {chash[:7]}: {msg}"))
                        else:
                            # Update status
                            cursor.execute("""
                                UPDATE git_commits SET pushed_status = ?, synced_at = ? WHERE commit_hash = ?
                            """, (pushed_status, now_str, chash))

                conn.commit()
    except Exception as e:
        logger.error(f"Error syncing git history: {e}", exc_info=True)
    finally:
        conn.close()


def seed_initial_tasks():
    """Seed initial tasks, repositories, and accounts if empty."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM tasks")
    count = cursor.fetchone()["count"]

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if count == 0:
        initial_tasks = [
            ("UI/UX & Stiller", "QComboBox ve Dropdown Stilleri Düzeltmesi", "Tüm uygulama genelinde QComboBox drop-down açılır menü ve stok detay stilleri düzeltildi", "Yapıldı", "feat/combobox-stili-duzeltme", now_str),
            ("ERP Entegrasyonu", "Zirve ERP Adaptörü Entegrasyonu", "Zirve DB bağlantısı, cari/stok çekme ve sipariş aktarımı adaptörü", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("ERP Entegrasyonu", "Logo ERP Adaptörü Entegrasyonu", "Logo REST/DB bağlantısı ve veri senkronizasyonu adaptörü", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("ERP Entegrasyonu", "Akınsoft ERP Adaptörü Entegrasyonu", "Akınsoft Veri çekme ve senkronizasyon adaptörü", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("Teklif Modülü", "Teklif Yönetimi UI ve Servis Altyapısı", "Teklif oluşturma, revizyon, kopyalama, Sipariş/Cari karta dönüştürme", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("Teklif Modülü", "Teklif Excel Exporter Servisi", "Teklifleri xlsx biçiminde dışa aktarma servisi", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("Görünüm Profilleri", "Dinamik Tablo Görünüm Profili Kaydetme/Yükleme", "Tablo sütun genişlikleri, sıralama ve görünürlük ayarlarını profil olarak saklama", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("UI/UX & Mimari", "3-Bölmeli AppGrid ve Standart Layout", "Dia ERP tarzı sol sidebar, AppGrid ve sağ özet panel mimarisi", "Yapıldı", "feat/dia-3panel-and-layout-hints", now_str),
            ("Git Yönetimi", "Canlı Aşama ve İlerlemeli Git Takip Ekranı", "3-Bölmeli arayüz, aşama çubuğu ve canlı konsol logu ile Git gönderimi", "Devam Ediyor", "feat/dia-3panel-and-layout-hints", None),
            ("UI/UX", "Toast Notification Sistemi", "DIAApp3 tarzı animasyonlu notification & network durumu", "Bekliyor", "ROADMAP.md", None),
            ("UI/UX", "Multi-dil Desteği (i18n)", "Türkçe, İngilizce, Almanca dil desteği ve dinamik çeviri", "Bekliyor", "ROADMAP.md", None),
            ("Network & Perf", "Delta Sync (Incremental Pull)", "Son senkronizasyon damgasına göre sadece değişen veriyi çekme", "Bekliyor", "ROADMAP.md", None),
        ]

        for cat, title, desc, status, branch, completed_at in initial_tasks:
            cursor.execute("""
                INSERT INTO tasks (category, title, description, status, related_branch, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cat, title, desc, status, branch, now_str, completed_at))

    # Seed Default Repository if empty
    cursor.execute("SELECT COUNT(*) as count FROM git_repositories")
    repo_count = cursor.fetchone()["count"]
    if repo_count == 0:
        git_info = get_git_status()
        remote_url = git_info["remote_url"] or "https://github.com/baynetteknik/dbar_piton.git"
        branch = git_info["branch"] or "main"
        cursor.execute("""
            INSERT INTO git_repositories (name, remote_url, default_branch, auth_type, is_default, created_at)
            VALUES (?, ?, ?, 'HTTPS', 1, ?)
        """, ("Ana Depo (origin)", remote_url, branch, now_str))

    # Seed Default Account if empty
    cursor.execute("SELECT COUNT(*) as count FROM git_accounts")
    acc_count = cursor.fetchone()["count"]
    if acc_count == 0:
        # Check git config user
        u_name = "baynetteknik"
        u_email = "info@baynet.com.tr"
        if is_git_available():
            r_name = run_git_cmd(["config", "user.name"])
            if r_name and r_name.stdout.strip():
                u_name = r_name.stdout.strip()
            r_email = run_git_cmd(["config", "user.email"])
            if r_email and r_email.stdout.strip():
                u_email = r_email.stdout.strip()

        cursor.execute("""
            INSERT INTO git_accounts (username, email, token, is_default, created_at)
            VALUES (?, ?, '', 1, ?)
        """, (u_name, u_email, now_str))

    conn.commit()
    conn.close()


def generate_report():
    """Generate a Markdown report from git_tracker.db."""
    sync_git_history()
    seed_initial_tasks()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks ORDER BY status DESC, category ASC")
    tasks = cursor.fetchall()

    cursor.execute("SELECT * FROM git_commits ORDER BY commit_date DESC LIMIT 20")
    commits = cursor.fetchall()

    md = []
    md.append("# 📊 TOYA ERP - Git & Görev Takip Raporu (git_tracker.db)")
    md.append(f"**Son Güncelleme Zamanı:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    md.append("## 🚀 Yapılan ve Yapılacak İşler (Görev Durumları)")
    md.append("| ID | Kategori | Görev / Özellik | Açıklama | Durum | İlgili Branch |")
    md.append("|---|---|---|---|---|---|")
    for t in tasks:
        status_icon = "✅" if t["status"] == "Yapıldı" else ("⏳" if t["status"] == "Devam Ediyor" else "📌")
        md.append(f"| {t['id']} | {t['category']} | **{t['title']}** | {t['description']} | {status_icon} {t['status']} | `{t['related_branch']}` |")

    md.append("\n## 📦 Git Commit ve Push Geçmişi")
    md.append("| Commit Hash | Tarih | Dal (Branch) | Commit Mesajı | Gönderim Durumu |")
    md.append("|---|---|---|---|---|")
    for c in commits:
        chash_short = c["commit_hash"][:7]
        status_icon = "🟢" if c["pushed_status"] == "Gönderildi" else "🔴"
        md.append(f"| `{chash_short}` | {c['commit_date']} | `{c['branch']}` | {c['message']} | {status_icon} {c['pushed_status']} |")

    md.append("\n---\n*Bu rapor `git_tracker.db` SQLite veritabanı verilerinden otomatik üretilmiştir.*")

    report_content = "\n".join(md)
    with open("GIT_TRACKER_REPORT.md", "w", encoding="utf-8") as f:
        f.write(report_content)

    conn.close()
    return report_content


class GitWorker(QThread):
    """Asynchronous background worker for Git commands with real-time stage progress and log streaming."""

    # Sinyaller:
    stage_progress = pyqtSignal(str, int)
    log_line = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, action: str, params: dict[str, Any] | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.action = action
        self.params = params or {}

    def run(self):
        try:
            if not is_git_available():
                err_msg = "Git komut satırı aracı (git.exe) sistemde bulunamadı. Lütfen Git'in kurulu ve sistem PATH'inde olduğundan emin olun."
                self.log_line.emit(f"❌ HATA: {err_msg}")
                self.finished.emit(False, err_msg)
                return

            if self.action == "commit_and_push":
                self._run_commit_and_push()
            elif self.action == "fetch":
                self._run_fetch()
            elif self.action == "pull":
                self._run_pull()
            elif self.action == "stash":
                self._run_stash()
            elif self.action == "stash_pop":
                self._run_stash_pop()
            else:
                self.finished.emit(False, f"Bilinmeyen eylem: {self.action}")
        except Exception as e:
            logger.error(f"GitWorker exception: {e}", exc_info=True)
            self.log_line.emit(f"❌ HATA: {str(e)}")
            self.finished.emit(False, str(e))

    def _exec_cmd(self, cmd_list: list[str], desc: str) -> tuple[bool, str]:
        git_exe = get_git_executable()
        if not git_exe:
            err_msg = "Git komut satırı aracı (git.exe) sistemde bulunamadı."
            self.log_line.emit(f"❌ HATA: {err_msg}")
            return False, err_msg

        real_cmd = [git_exe if c == "git" else c for c in cmd_list]
        cmd_str = " ".join(cmd_list)
        self.log_line.emit(f"▶ {desc} [{cmd_str}]")

        try:
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                real_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                startupinfo=startupinfo,
            )
            full_out = []
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    clean_l = line.rstrip()
                    if clean_l:
                        self.log_line.emit(f"  {clean_l}")
                        full_out.append(clean_l)
                process.stdout.close()
            process.wait()
            success = (process.returncode == 0)
            return success, "\n".join(full_out)
        except FileNotFoundError:
            err_msg = "Git yürütülebilir dosyası bulunamadı."
            self.log_line.emit(f"❌ {err_msg}")
            return False, err_msg
        except Exception as e:
            err_msg = f"Komut yürütülürken hata: {str(e)}"
            self.log_line.emit(f"❌ {err_msg}")
            return False, err_msg

    def _run_commit_and_push(self):
        commit_msg = self.params.get("message", "").strip()
        if not commit_msg:
            commit_msg = f"Güncelleme - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        branch = self.params.get("branch")
        if not branch:
            git_info = get_git_status()
            branch = git_info["branch"]

        # AŞAMA 1: Tarama ve Durum Kontrolü (%20)
        self.stage_progress.emit("🔍 Aşama 1/5: Çalışma dizini taranıyor...", 20)
        status_info = get_git_status()
        self.log_line.emit(f"Aktif Dal: {status_info['branch']}, Değişen Dosya Sayısı: {status_info['modified_count']}")

        # AŞAMA 2: Değişiklikler Sahneleniyor (Stage / git add) (%40)
        self.stage_progress.emit("📦 Aşama 2/5: Değişiklikler stage alanına alınıyor (git add)...", 40)
        ok, out = self._exec_cmd(["git", "add", "."], "Dosyalar Ekleniyor")
        if not ok:
            self.finished.emit(False, f"Stage hatası: {out}")
            return

        # AŞAMA 3: Commit Oluşturuluyor (%60)
        self.stage_progress.emit(f"✍️ Aşama 3/5: Commit oluşturuluyor: '{commit_msg[:30]}...'...", 60)
        ok, out = self._exec_cmd(["git", "commit", "-m", commit_msg], "Commit Oluşturuluyor")
        if not ok and "nothing to commit" not in out.lower() and "working tree clean" not in out.lower():
            self.finished.emit(False, f"Commit hatası: {out}")
            return

        # AŞAMA 4: Uzak Depoya Aktarılıyor (git push) (%80)
        self.stage_progress.emit(f"🚀 Aşama 4/5: Uzak sunucuya (origin/{branch}) gönderiliyor...", 80)
        ok, out = self._exec_cmd(["git", "push", "-u", "origin", branch], "Git Push Yapılıyor")
        if not ok:
            self.finished.emit(False, f"Push hatası (Uzak depoya aktarılamadı): {out}")
            return

        # AŞAMA 5: Senkronizasyon & Veritabanı Kaydı (%100)
        self.stage_progress.emit("✅ Aşama 5/5: Yerel kayıtlar ve rapor güncelleniyor...", 100)
        sync_git_history()
        generate_report()

        self.log_line.emit("🎉 Git'e gönderme işlemi başarıyla tamamlandı!")
        self.finished.emit(True, f"Değişiklikler başarıyla 'origin/{branch}' dalına gönderildi.")

    def _run_fetch(self):
        self.stage_progress.emit("🔄 Uzak sunucu kontrol ediliyor (git fetch)...", 50)
        ok, out = self._exec_cmd(["git", "fetch", "--all"], "Git Fetch")
        sync_git_history()
        self.stage_progress.emit("Tamamlandı", 100)
        if ok:
            self.finished.emit(True, "Uzak depo güncellemeleri başarıyla çekildi.")
        else:
            self.finished.emit(False, f"Fetch hatası: {out}")

    def _run_pull(self):
        branch = self.params.get("branch") or get_git_status()["branch"]
        self.stage_progress.emit(f"📥 Değişiklikler birleştiriliyor (git pull origin {branch})...", 50)
        ok, out = self._exec_cmd(["git", "pull", "origin", branch], "Git Pull")
        sync_git_history()
        self.stage_progress.emit("Tamamlandı", 100)
        if ok:
            self.finished.emit(True, f"'{branch}' dalındaki son değişiklikler başarıyla çekildi.")
        else:
            self.finished.emit(False, f"Pull hatası: {out}")

    def _run_stash(self):
        self.stage_progress.emit("📦 Değişiklikler geçici hafızaya alınıyor (git stash)...", 50)
        ok, out = self._exec_cmd(["git", "stash"], "Git Stash")
        sync_git_history()
        self.stage_progress.emit("Tamamlandı", 100)
        if ok:
            self.finished.emit(True, "Değişiklikler başarıyla stash'e alındı.")
        else:
            self.finished.emit(False, f"Stash hatası: {out}")

    def _run_stash_pop(self):
        self.stage_progress.emit("📦 Geçici değişiklikler geri yükleniyor (git stash pop)...", 50)
        ok, out = self._exec_cmd(["git", "stash", "pop"], "Git Stash Pop")
        sync_git_history()
        self.stage_progress.emit("Tamamlandı", 100)
        if ok:
            self.finished.emit(True, "Stash'teki değişiklikler geri yüklendi.")
        else:
            self.finished.emit(False, f"Stash pop hatası: {out}")
