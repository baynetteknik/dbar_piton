"""
Git & Task Tracker Widget for Settings Dialog.
Displays commits, pushes, done tasks, and pending roadmap features stored in git_tracker.db.
"""

import logging
import os
import sqlite3
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import git_tracker

logger = logging.getLogger(__name__)


class GitTrackerWidget(QWidget):
    """Widget to display Git commits, push statuses, and project tasks inside settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.load_data()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # 1. Top Header Card
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(10, 8, 10, 8)

        # Left Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        self.lbl_title = QLabel("📊 Sürüm, Git Commit & Görev Takibi (git_tracker.db)")
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0f172a;")
        
        self.lbl_sub = QLabel("Projede gerçekleştirilen geliştirmeler, Git push geçmişi ve yol haritası durumu.")
        self.lbl_sub.setStyleSheet("font-size: 12px; color: #64748b;")
        
        info_layout.addWidget(self.lbl_title)
        info_layout.addWidget(self.lbl_sub)
        header_layout.addLayout(info_layout)

        header_layout.addStretch()

        # Action Buttons
        self.btn_refresh = QPushButton("🔄 Senkronize Et & Yenile")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_refresh.clicked.connect(self.refresh_data)
        header_layout.addWidget(self.btn_refresh)

        self.btn_report = QPushButton("📄 GIT_TRACKER_REPORT.md Oluştur")
        self.btn_report.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_report.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.btn_report.clicked.connect(self.export_report)
        header_layout.addWidget(self.btn_report)

        main_layout.addWidget(header_card)

        # 2. Main Content - Splitter (Tasks Table & Git Commits Table)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top Panel: Tasks
        tasks_panel = QWidget()
        tasks_layout = QVBoxLayout(tasks_panel)
        tasks_layout.setContentsMargins(0, 0, 0, 0)
        tasks_layout.setSpacing(6)

        tasks_header = QLabel("🚀 Yapılan ve Yapılacak İşler (Yol Haritası)")
        tasks_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b;")
        tasks_layout.addWidget(tasks_header)

        self.tbl_tasks = QTableWidget()
        self.tbl_tasks.setColumnCount(6)
        self.tbl_tasks.setHorizontalHeaderLabels([
            "ID", "Kategori", "Görev / Özellik", "Açıklama", "Durum", "İlgili Branch"
        ])
        self.tbl_tasks.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tbl_tasks.horizontalHeader().setStretchLastSection(True)
        self.tbl_tasks.setAlternatingRowColors(True)
        self.tbl_tasks.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                padding: 6px;
                font-weight: bold;
                border: 1px solid #cbd5e1;
            }
        """)
        tasks_layout.addWidget(self.tbl_tasks)
        splitter.addWidget(tasks_panel)

        # Bottom Panel: Git Commits
        commits_panel = QWidget()
        commits_layout = QVBoxLayout(commits_panel)
        commits_layout.setContentsMargins(0, 0, 0, 0)
        commits_layout.setSpacing(6)

        commits_header = QLabel("📦 Git Commit ve Push Geçmişi (En Son Gönderilenler)")
        commits_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b;")
        commits_layout.addWidget(commits_header)

        self.tbl_commits = QTableWidget()
        self.tbl_commits.setColumnCount(5)
        self.tbl_commits.setHorizontalHeaderLabels([
            "Commit Hash", "Tarih", "Dal (Branch)", "Commit Mesajı", "Gönderim Durumu"
        ])
        self.tbl_commits.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tbl_commits.horizontalHeader().setStretchLastSection(True)
        self.tbl_commits.setAlternatingRowColors(True)
        self.tbl_commits.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                padding: 6px;
                font-weight: bold;
                border: 1px solid #cbd5e1;
            }
        """)
        commits_layout.addWidget(self.tbl_commits)
        splitter.addWidget(commits_panel)

        splitter.setSizes([300, 300])
        main_layout.addWidget(splitter)

    def load_data(self):
        """Load tasks and git commits from git_tracker.db into tables."""
        try:
            git_tracker.init_db()
            git_tracker.sync_git_history()
            git_tracker.seed_initial_tasks()

            conn = git_tracker.get_db_connection()
            cursor = conn.cursor()

            # 1. Load Tasks
            cursor.execute("SELECT * FROM tasks ORDER BY status DESC, category ASC")
            tasks = cursor.fetchall()

            self.tbl_tasks.setRowCount(len(tasks))
            for row_idx, t in enumerate(tasks):
                self.tbl_tasks.setItem(row_idx, 0, QTableWidgetItem(str(t["id"])))
                self.tbl_tasks.setItem(row_idx, 1, QTableWidgetItem(t["category"] or ""))
                
                title_item = QTableWidgetItem(t["title"] or "")
                font = title_item.font()
                font.setBold(True)
                title_item.setFont(font)
                self.tbl_tasks.setItem(row_idx, 2, title_item)

                self.tbl_tasks.setItem(row_idx, 3, QTableWidgetItem(t["description"] or ""))

                # Status item with color coding
                status = t["status"]
                if status == "Yapıldı":
                    status_text = "✅ Yapıldı"
                    status_item = QTableWidgetItem(status_text)
                    status_item.setForeground(QColor("#047857")) # Green
                elif status == "Devam Ediyor":
                    status_text = "⏳ Devam Ediyor"
                    status_item = QTableWidgetItem(status_text)
                    status_item.setForeground(QColor("#d97706")) # Amber
                else:
                    status_text = "📌 Bekliyor"
                    status_item = QTableWidgetItem(status_text)
                    status_item.setForeground(QColor("#64748b")) # Slate

                self.tbl_tasks.setItem(row_idx, 4, status_item)
                self.tbl_tasks.setItem(row_idx, 5, QTableWidgetItem(t["related_branch"] or ""))

            self.tbl_tasks.resizeColumnsToContents()
            self.tbl_tasks.setColumnWidth(3, 300)

            # 2. Load Commits
            cursor.execute("SELECT * FROM git_commits ORDER BY commit_date DESC LIMIT 30")
            commits = cursor.fetchall()

            self.tbl_commits.setRowCount(len(commits))
            for row_idx, c in enumerate(commits):
                hash_item = QTableWidgetItem(c["commit_hash"][:7])
                hash_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.tbl_commits.setItem(row_idx, 0, hash_item)

                self.tbl_commits.setItem(row_idx, 1, QTableWidgetItem(c["commit_date"] or ""))
                self.tbl_commits.setItem(row_idx, 2, QTableWidgetItem(c["branch"] or ""))
                self.tbl_commits.setItem(row_idx, 3, QTableWidgetItem(c["message"] or ""))

                push_item = QTableWidgetItem("🟢 " + (c["pushed_status"] or "Pushed"))
                push_item.setForeground(QColor("#047857"))
                self.tbl_commits.setItem(row_idx, 4, push_item)

            self.tbl_commits.resizeColumnsToContents()
            self.tbl_commits.setColumnWidth(3, 350)

            conn.close()

            now_str = datetime.now().strftime("%H:%M:%S")
            self.lbl_sub.setText(f"Projede gerçekleştirilen geliştirmeler, Git push geçmişi. (Son Senkronizasyon: {now_str})")

        except Exception as e:
            logger.error(f"GitTrackerWidget load error: {e}", exc_info=True)

    def refresh_data(self):
        """Re-sync git history and reload tables."""
        self.load_data()
        QMessageBox.information(self, "Bilgi", "Git ve Görev verileri başarıyla senkronize edildi.")

    def export_report(self):
        """Export GIT_TRACKER_REPORT.md file."""
        try:
            git_tracker.generate_report()
            QMessageBox.information(
                self, "Rapor Oluşturuldu",
                "GIT_TRACKER_REPORT.md dosyası proje ana dizininde başarıyla güncellendi."
            )
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Rapor oluşturulurken hata: {e}")
