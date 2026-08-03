"""
Git & Task Tracker Utility for Multi-CMS Manager
Manages git_tracker.db SQLite database to track git commits, pushes, done tasks, and pending roadmap items.
"""

import os
import sqlite3
import subprocess
from datetime import datetime
import json

DB_PATH = "git_tracker.db"

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
    
    conn.commit()
    conn.close()

def sync_git_history():
    """Sync commits from git log into SQLite database."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get current branch
    branch_output = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=False
    )
    current_branch = branch_output.stdout.strip() if branch_output.returncode == 0 else "unknown"
    
    # Get recent git commits via git log
    cmd = ["git", "log", "-n", "30", "--pretty=format:%H|%an|%ad|%s", "--date=iso"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    
    if res.returncode == 0 and res.stdout.strip():
        lines = res.stdout.strip().split("\n")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for line in lines:
            if not line:
                continue
            parts = line.split("|")
            if len(parts) >= 4:
                chash, author, cdate, msg = parts[0], parts[1], parts[2], "|".join(parts[3:])
                
                # Check if commit exists
                cursor.execute("SELECT commit_hash FROM git_commits WHERE commit_hash = ?", (chash,))
                row = cursor.fetchone()
                if not row:
                    cursor.execute("""
                        INSERT INTO git_commits (commit_hash, branch, author, commit_date, pushed_status, message, synced_at)
                        VALUES (?, ?, ?, ?, 'Pushed', ?, ?)
                    """, (chash, current_branch, author, cdate, msg, now_str))
                    
                    cursor.execute("""
                        INSERT INTO activity_log (timestamp, event_type, description)
                        VALUES (?, 'Git Commit Recorded', ?)
                    """, (now_str, f"Commit {chash[:7]}: {msg}"))
                    
    conn.commit()
    conn.close()

def seed_initial_tasks():
    """Seed completed and pending tasks into tasks table if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM tasks")
    count = cursor.fetchone()["count"]
    
    if count == 0:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        initial_tasks = [
            ("UI/UX & Stiller", "QComboBox ve Dropdown Stilleri Düzeltmesi", "Tüm uygulama genelinde QComboBox drop-down açılır menü ve stok detay stilleri düzeltildi", "Yapıldı", "feat/combobox-stili-duzeltme", now_str),
            ("ERP Entegrasyonu", "Zirve ERP Adaptörü Entegrasyonu", "Zirve DB bağlantısı, cari/stok çekme ve sipariş aktarımı adaptörü", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("ERP Entegrasyonu", "Logo ERP Adaptörü Entegrasyonu", "Logo REST/DB bağlantısı ve veri senkronizasyonu adaptörü", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("ERP Entegrasyonu", "Akınsoft ERP Adaptörü Entegrasyonu", "Akınsoft Veri çekme ve senkronizasyon adaptörü", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("Teklif Modülü", "Teklif Yönetimi UI ve Servis Altyapısı", "Teklif oluşturma, revizyon, kopyalama, Sipariş/Cari karta dönüştürme", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("Teklif Modülü", "Teklif Excel Exporter Servisi", "Teklifleri xlsx biçiminde dışa aktarma servisi", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("Görünüm Profilleri", "Dinamik Tablo Görünüm Profili Kaydetme/Yükleme", "Tablo sütun genişlikleri, sıralama ve görünürlük ayarlarını profil olarak saklama", "Yapıldı", "feat/teklif-ve-erp-entegrasyonu", now_str),
            ("UI/UX", "Toast Notification Sistemi", "DIAApp3 tarzı animasyonlu notification & network durumu", "Bekliyor", "ROADMAP.md", None),
            ("UI/UX", "Multi-dil Desteği (i18n)", "Türkçe, İngilizce, Almanca dil desteği ve dinamik çeviri", "Bekliyor", "ROADMAP.md", None),
            ("Network & Perf", "Delta Sync (Incremental Pull)", "Son senkronizasyon damgasına göre sadece değişen veriyi çekme", "Bekliyor", "ROADMAP.md", None),
            ("UI/UX", "Frameless Window", "Özel başlık çubuğu ve pencere kontrolleri", "Bekliyor", "ROADMAP.md", None),
        ]
        
        for cat, title, desc, status, branch, completed_at in initial_tasks:
            cursor.execute("""
                INSERT INTO tasks (category, title, description, status, related_branch, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cat, title, desc, status, branch, now_str, completed_at))
            
    conn.commit()
    conn.close()

def generate_report():
    """Generate a Markdown report from git_tracker.db."""
    sync_git_history()
    seed_initial_tasks()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch tasks
    cursor.execute("SELECT * FROM tasks ORDER BY status DESC, category ASC")
    tasks = cursor.fetchall()
    
    # Fetch commits
    cursor.execute("SELECT * FROM git_commits ORDER BY commit_date DESC LIMIT 15")
    commits = cursor.fetchall()
    
    md = []
    md.append("# 📊 Git & Görev Takip Raporu (git_tracker.db)")
    md.append(f"**Son Güncelleme Zamanı:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    md.append("## 🚀 Yapılan ve Yapılacak İşler (Görev Durumları)")
    md.append("| ID | Kategori | Görev / Özellik | Açıklama | Durum | İlgili Branch |")
    md.append("|---|---|---|---|---|---|")
    for t in tasks:
        status_icon = "✅" if t["status"] == "Yapıldı" else ("⏳" if t["status"] == "Devam Ediyor" else "📌")
        md.append(f"| {t['id']} | {t['category']} | **{t['title']}** | {t['description']} | {status_icon} {t['status']} | `{t['related_branch']}` |")
        
    md.append("\n## 📦 Git Commit ve Push Geçmişi (En Son Gönderilenler)")
    md.append("| Commit Hash | Tarih | Dal (Branch) | Commit Mesajı | Gönderim Durumu |")
    md.append("|---|---|---|---|---|")
    for c in commits:
        chash_short = c["commit_hash"][:7]
        md.append(f"| `{chash_short}` | {c['commit_date']} | `{c['branch']}` | {c['message']} | 🟢 {c['pushed_status']} |")
        
    md.append("\n---\n*Bu rapor `git_tracker.db` SQLite veritabanı verilerinden otomatik üretilmiştir.*")
    
    report_content = "\n".join(md)
    with open("GIT_TRACKER_REPORT.md", "w", encoding="utf-8") as f:
        f.write(report_content)
        
    conn.close()
    return report_content

if __name__ == "__main__":
    import sys
    init_db()
    sync_git_history()
    seed_initial_tasks()
    
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        generate_report()
        print("Rapor oluşturuldu: GIT_TRACKER_REPORT.md")
    else:
        generate_report()
        print("git_tracker.db veritabanı ve GIT_TRACKER_REPORT.md güncellendi.")
