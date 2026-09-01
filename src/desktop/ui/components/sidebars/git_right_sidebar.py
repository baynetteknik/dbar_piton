"""
TOYA ERP - Git Takibi Modüler Sağ Sidebar Bileşeni (rightsidebar_git)
Repository durumu, uzak sunucu (origin) bağlantısı, bekleyen commit/değişiklik sayaçları
ve seçili commit/görev detay kartını sunar.
"""

from typing import Any, Dict, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QClipboard, QFont, QColor
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget, QHBoxLayout
)

from src.desktop.managers.theme_manager import ThemeManager


class GitRightSidebar(QFrame):
    """TOYA ERP Git Takip Ekranı Sağ Özet ve Detay Paneli"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar_frame")
        self.theme = ThemeManager()
        self.setFixedWidth(260)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 1. BAŞLIK
        title_lbl = QLabel("📊 DEPO & DURUM ÖZETİ")
        title_lbl.setStyleSheet("font-size: 11pt; font-weight: bold; color: #1e3a8a; border-bottom: 2px solid #3b82f6; padding-bottom: 4px;")
        main_layout.addWidget(title_lbl)

        # 2. CANLI DEPO KARTLARI (STATUS STATS)
        stats_frame = QFrame()
        stats_frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(6, 6, 6, 6)
        stats_layout.setSpacing(6)

        # Dal & Remote
        self.lbl_branch_name = QLabel("Dal: -")
        self.lbl_branch_name.setStyleSheet("font-weight: bold; font-size: 11px; color: #0f172a;")
        stats_layout.addWidget(self.lbl_branch_name)

        self.lbl_remote = QLabel("Remote: -")
        self.lbl_remote.setWordWrap(True)
        self.lbl_remote.setStyleSheet("font-size: 10px; color: #64748b;")
        stats_layout.addWidget(self.lbl_remote)

        # Sayaçlar
        counters_grid = QGridLayout()
        counters_grid.setVerticalSpacing(4)

        # Bekleyen Commitler
        counters_grid.addWidget(QLabel("🔴 Gönderilmedi:"), 0, 0)
        self.lbl_unpushed_count = QLabel("0 commit")
        self.lbl_unpushed_count.setStyleSheet("font-weight: bold; color: #dc2626; font-size: 11px;")
        self.lbl_unpushed_count.setAlignment(Qt.AlignmentFlag.AlignRight)
        counters_grid.addWidget(self.lbl_unpushed_count, 0, 1)

        # Değişen Dosyalar
        counters_grid.addWidget(QLabel("🟡 Değişen Dosya:"), 1, 0)
        self.lbl_changed_count = QLabel("0 dosya")
        self.lbl_changed_count.setStyleSheet("font-weight: bold; color: #d97706; font-size: 11px;")
        self.lbl_changed_count.setAlignment(Qt.AlignmentFlag.AlignRight)
        counters_grid.addWidget(self.lbl_changed_count, 1, 1)

        stats_layout.addLayout(counters_grid)
        main_layout.addWidget(stats_frame)

        # 3. SEÇİLİ KAYIT DETAY KARTI
        detail_header = QLabel("🔍 SEÇİLİ DETAYI")
        detail_header.setStyleSheet("font-size: 10pt; font-weight: bold; color: #334155;")
        main_layout.addWidget(detail_header)

        self.detail_card = QFrame()
        self.detail_card.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
            }
        """)
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(8, 8, 8, 8)
        detail_layout.setSpacing(6)

        # Hash & Copy Button
        hash_box = QHBoxLayout()
        self.lbl_hash = QLabel("Hash: -")
        self.lbl_hash.setStyleSheet("font-family: monospace; font-weight: bold; color: #2563eb;")
        self.btn_copy_hash = QPushButton("📋")
        self.btn_copy_hash.setToolTip("Hash Kopyala")
        self.btn_copy_hash.setFixedSize(24, 24)
        self.btn_copy_hash.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_hash.setStyleSheet("border: 1px solid #cbd5e1; background: white; border-radius: 3px;")
        self.btn_copy_hash.clicked.connect(self._copy_hash)
        hash_box.addWidget(self.lbl_hash)
        hash_box.addWidget(self.btn_copy_hash)
        detail_layout.addLayout(hash_box)

        # Tarih & Yazar
        self.lbl_author_date = QLabel("Yazar / Tarih: -")
        self.lbl_author_date.setWordWrap(True)
        self.lbl_author_date.setStyleSheet("font-size: 10px; color: #475569;")
        detail_layout.addWidget(self.lbl_author_date)

        # Durum Badge
        self.lbl_status_badge = QLabel("Durum: -")
        self.lbl_status_badge.setStyleSheet("font-weight: bold; font-size: 10px; color: #047857;")
        detail_layout.addWidget(self.lbl_status_badge)

        # Mesaj Scroll Area
        self.lbl_message = QLabel("Henüz kayıt seçilmedi.\nTablodan bir commit veya görev seçiniz.")
        self.lbl_message.setWordWrap(True)
        self.lbl_message.setStyleSheet("font-size: 11px; color: #1e293b; background: white; padding: 6px; border: 1px solid #e2e8f0; border-radius: 4px;")
        detail_layout.addWidget(self.lbl_message)

        main_layout.addWidget(self.detail_card, 1)

        # 4. EN ALT BİLGİ VE SON SENKRONİZASYON
        self.lbl_last_sync = QLabel("Son Tarama: -")
        self.lbl_last_sync.setStyleSheet("font-size: 9px; color: #94a3b8; font-style: italic;")
        self.lbl_last_sync.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_last_sync)

    def update_git_status(self, git_info: Dict[str, Any]):
        """Updates repository statistics from get_git_status() dict."""
        branch = git_info.get("branch", "unknown")
        self.lbl_branch_name.setText(f"🌿 Dal: {branch}")

        remote = git_info.get("remote_url", "")
        if remote:
            # Shorten remote display
            short_remote = remote.replace("https://github.com/", "gh:").replace(".git", "")
            self.lbl_remote.setText(f"🌐 Remote: {short_remote}")
        else:
            self.lbl_remote.setText("🌐 Remote: (Bağlantı Yok)")

        ahead = git_info.get("ahead_count", 0)
        self.lbl_unpushed_count.setText(f"{ahead} commit")
        if ahead > 0:
            self.lbl_unpushed_count.setStyleSheet("font-weight: bold; color: #dc2626; font-size: 11px;")
        else:
            self.lbl_unpushed_count.setStyleSheet("font-weight: bold; color: #16a34a; font-size: 11px;")

        modified = git_info.get("modified_count", 0)
        self.lbl_changed_count.setText(f"{modified} dosya")
        if modified > 0:
            self.lbl_changed_count.setStyleSheet("font-weight: bold; color: #d97706; font-size: 11px;")
        else:
            self.lbl_changed_count.setStyleSheet("font-weight: bold; color: #16a34a; font-size: 11px;")

        from datetime import datetime
        self.lbl_last_sync.setText(f"Son Tarama: {datetime.now().strftime('%H:%M:%S')}")

    def update_summary(self, row_dict: Dict[str, Any]):
        """Called automatically when an AppGrid row is selected."""
        # Check if Commit row
        if "HASH" in row_dict:
            chash = str(row_dict.get("HASH", ""))
            self.lbl_hash.setText(f"Hash: {chash}")
            self.btn_copy_hash.setProperty("full_hash", chash)
            
            author = row_dict.get("YAZAR", "")
            date_str = row_dict.get("TARİH", "")
            self.lbl_author_date.setText(f"👤 {author}\n📅 {date_str}")
            
            status = row_dict.get("DURUM", "")
            self.lbl_status_badge.setText(f"Durum: {status}")
            
            msg = row_dict.get("MESAJ", "")
            self.lbl_message.setText(msg or "Mesaj yok")

        # Check if Task row
        elif "GÖREV" in row_dict:
            tid = str(row_dict.get("ID", ""))
            self.lbl_hash.setText(f"Görev ID: #{tid}")
            self.btn_copy_hash.setProperty("full_hash", tid)
            
            cat = row_dict.get("KATEGORİ", "")
            branch = row_dict.get("İLGİLİ DAL", "")
            self.lbl_author_date.setText(f"📂 Kategori: {cat}\n🌿 Dal: {branch}")
            
            status = row_dict.get("DURUM", "")
            self.lbl_status_badge.setText(f"Durum: {status}")
            
            task_title = row_dict.get("GÖREV", "")
            task_desc = row_dict.get("AÇIKLAMA", "")
            self.lbl_message.setText(f"**{task_title}**\n\n{task_desc}")

        # Check if Change row
        elif "DOSYA YOLU" in row_dict:
            fpath = str(row_dict.get("DOSYA YOLU", ""))
            self.lbl_hash.setText("Dosya Değişikliği")
            self.btn_copy_hash.setProperty("full_hash", fpath)
            self.lbl_author_date.setText(f"Tip: {row_dict.get('DURUM', '')}")
            self.lbl_status_badge.setText(f"Kod: {row_dict.get('KOD', '')}")
            self.lbl_message.setText(fpath)

    def _copy_hash(self):
        target = self.btn_copy_hash.property("full_hash") or self.lbl_hash.text()
        cb = QApplication.clipboard()
        if cb and target:
            cb.setText(target)
            self.btn_copy_hash.setText("✓")
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.btn_copy_hash.setText("📋"))
