"""
TOYA ERP - Git Takibi Modüler Sol Sidebar Bileşeni (leftsidebar_git)
Git operasyonları (Commit & Push, Fetch, Pull, Stash), dal seçimi, görünüm modu ve görev ekleme butonlarını barındırır.
"""

from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QRadioButton, QButtonGroup
)

from src.desktop.managers.theme_manager import ThemeManager


class GitLeftSidebar(QFrame):
    """TOYA ERP Git Takip Ekranı Sol Aksiyon ve Filtre Paneli"""

    action_requested = pyqtSignal(str)  # 'commit_push', 'fetch', 'pull', 'stash', 'stash_pop', 'report', 'new_task', 'refresh'
    branch_selected = pyqtSignal(str)   # branch_name
    view_mode_changed = pyqtSignal(str) # 'commits', 'tasks', 'changes'
    filter_changed = pyqtSignal(dict)   # {'status': 'all'|'pushed'|'unpushed', 'branch': str}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar_frame")
        self.theme = ThemeManager()
        self.setFixedWidth(230)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 1. BAŞLIK
        title_lbl = QLabel("🚀 GİT İŞLEMLERİ")
        title_lbl.setStyleSheet("font-size: 11pt; font-weight: bold; color: #1e3a8a; border-bottom: 2px solid #3b82f6; padding-bottom: 4px;")
        layout.addWidget(title_lbl)

        # 2. ANA AKSİYON: GİT'E GÖNDER
        self.btn_commit_push = QPushButton("🚀 Git'e Gönder (Push)")
        self.btn_commit_push.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_commit_push.setToolTip("Değişiklikleri stage'e al, commit oluştur ve uzak sunucuya aktar")
        self.btn_commit_push.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                font-size: 11px;
                border-radius: 6px;
                padding: 10px 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)
        self.btn_commit_push.clicked.connect(lambda: self.action_requested.emit("commit_push"))
        layout.addWidget(self.btn_commit_push)

        # 3. YARDIMCI GİT AKSİYONLARI (FETCH, PULL, STASH)
        sub_actions_frame = QFrame()
        sub_actions_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px;")
        sub_layout = QVBoxLayout(sub_actions_frame)
        sub_layout.setContentsMargins(4, 4, 4, 4)
        sub_layout.setSpacing(5)

        self.btn_fetch = self._create_sub_btn("🔄 Fetch (Durum Tara)", "#0284c7")
        self.btn_fetch.clicked.connect(lambda: self.action_requested.emit("fetch"))
        sub_layout.addWidget(self.btn_fetch)

        self.btn_pull = self._create_sub_btn("📥 Değişiklikleri Çek (Pull)", "#059669")
        self.btn_pull.clicked.connect(lambda: self.action_requested.emit("pull"))
        sub_layout.addWidget(self.btn_pull)

        # Stash HBox
        stash_box = QHBoxLayout()
        stash_box.setSpacing(4)
        self.btn_stash = self._create_sub_btn("📦 Stash", "#d97706")
        self.btn_stash.clicked.connect(lambda: self.action_requested.emit("stash"))
        self.btn_stash_pop = self._create_sub_btn("Pop", "#b45309")
        self.btn_stash_pop.setFixedWidth(50)
        self.btn_stash_pop.clicked.connect(lambda: self.action_requested.emit("stash_pop"))
        stash_box.addWidget(self.btn_stash)
        stash_box.addWidget(self.btn_stash_pop)
        sub_layout.addLayout(stash_box)

        layout.addWidget(sub_actions_frame)

        # 4. AKTİF DAL (BRANCH) SEÇİCİ
        branch_box = QFrame()
        branch_box.setStyleSheet("background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px;")
        branch_layout = QVBoxLayout(branch_box)
        branch_layout.setContentsMargins(4, 4, 4, 4)
        branch_layout.setSpacing(4)

        lbl_branch = QLabel("🌿 Aktif / Hedef Dal (Branch):")
        lbl_branch.setStyleSheet("font-size: 10px; font-weight: bold; color: #475569;")
        branch_layout.addWidget(lbl_branch)

        self.cmb_branch = QComboBox()
        self.cmb_branch.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 4px 6px;
                background-color: #f8fafc;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        self.cmb_branch.currentTextChanged.connect(self._on_branch_changed)
        branch_layout.addWidget(self.cmb_branch)

        layout.addWidget(branch_box)

        # 5. GÖRÜNÜM MODLARI SEÇİCİ (SEKMELER/RADYO BUTONLAR)
        view_box = QFrame()
        view_box.setStyleSheet("background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px;")
        view_layout = QVBoxLayout(view_box)
        view_layout.setContentsMargins(6, 6, 6, 6)
        view_layout.setSpacing(4)

        lbl_view = QLabel("📑 Görünüm Tablosu:")
        lbl_view.setStyleSheet("font-size: 10px; font-weight: bold; color: #334155;")
        view_layout.addWidget(lbl_view)

        self.bg_views = QButtonGroup(self)
        
        self.rb_commits = QRadioButton("📦 Commit Geçmişi")
        self.rb_commits.setChecked(True)
        self.bg_views.addButton(self.rb_commits, 1)
        view_layout.addWidget(self.rb_commits)

        self.rb_tasks = QRadioButton("🚀 Görevler & Yol Haritası")
        self.bg_views.addButton(self.rb_tasks, 2)
        view_layout.addWidget(self.rb_tasks)

        self.rb_changes = QRadioButton("🟡 Değişen Dosyalar")
        self.bg_views.addButton(self.rb_changes, 3)
        view_layout.addWidget(self.rb_changes)

        self.bg_views.idClicked.connect(self._on_view_mode_clicked)
        layout.addWidget(view_box)

        # 6. DİĞER ARAÇLAR (RAPOR & GÖREV EKLE)
        tools_box = QVBoxLayout()
        tools_box.setSpacing(6)

        self.btn_new_task = self._create_action_btn("➕ Yeni Görev Ekle", "#475569")
        self.btn_new_task.clicked.connect(lambda: self.action_requested.emit("new_task"))
        tools_box.addWidget(self.btn_new_task)

        self.btn_report = self._create_action_btn("📄 Rapor Üret (.md)", "#059669")
        self.btn_report.clicked.connect(lambda: self.action_requested.emit("report"))
        tools_box.addWidget(self.btn_report)

        layout.addLayout(tools_box)

        layout.addStretch()

        # 7. EN ALT YENİLE BUTONU
        self.btn_refresh = QPushButton("🔄 Tümünü Yenile")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #e2e8f0;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #cbd5e1; }
        """)
        self.btn_refresh.clicked.connect(lambda: self.action_requested.emit("refresh"))
        layout.addWidget(self.btn_refresh)

    def _create_sub_btn(self, text: str, color: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-weight: 600;
                font-size: 10px;
                border-radius: 4px;
                padding: 6px 4px;
                border: none;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        return btn

    def _create_action_btn(self, text: str, color: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: white;
                color: {color};
                border: 1px solid {color};
                font-weight: 600;
                font-size: 11px;
                border-radius: 4px;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: #f1f5f9;
            }}
        """)
        return btn

    def set_branches(self, branches: List[str], current_branch: str):
        self.cmb_branch.blockSignals(True)
        self.cmb_branch.clear()
        for b in branches:
            self.cmb_branch.addItem(b)
        idx = self.cmb_branch.findText(current_branch)
        if idx >= 0:
            self.cmb_branch.setCurrentIndex(idx)
        self.cmb_branch.blockSignals(False)

    def _on_branch_changed(self, branch: str):
        if branch:
            self.branch_selected.emit(branch)
            self.filter_changed.emit({"branch": branch})

    def _on_view_mode_clicked(self, btn_id: int):
        if btn_id == 1:
            self.view_mode_changed.emit("commits")
        elif btn_id == 2:
            self.view_mode_changed.emit("tasks")
        elif btn_id == 3:
            self.view_mode_changed.emit("changes")
