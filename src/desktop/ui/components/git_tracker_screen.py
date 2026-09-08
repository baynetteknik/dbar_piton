"""
TOYA ERP - Sürüm & Git Takip Merkezi Ekranı (GitTrackerScreen)
3-Panelli (Sol/Sağ Açılır/Kapanır EdgeTriggeredPanel, FilterableTableView, Sayfalama) Mimarisi.
Açık Teklifler ve Bekleyen Siparişler ekran şablonuyla birebir uyumludur.
"""

import logging
from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

import git_tracker
from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.layout_hint_helper import register_layout_hint
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget

logger = logging.getLogger(__name__)


class GitRepositoryDialog(QDialog):
    """Git Uzak Depo (Remote Repository) Ekleme ve Düzenleme Diyalogu."""

    def __init__(self, repo_data: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.repo_data = repo_data
        self.setWindowTitle("🌐 Git Deposu Ekle / Düzenle" if not repo_data else "🌐 Git Deposunu Düzenle")
        self.setMinimumWidth(480)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        combo_style = """
            QLineEdit, QComboBox {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px 10px;
                background-color: white;
                font-size: 12px;
            }
        """

        layout.addWidget(QLabel("🏷️ Depo / Tanım Adı:"))
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Örn: GitHub Ana Depo (origin)")
        self.txt_name.setStyleSheet(combo_style)
        layout.addWidget(self.txt_name)

        layout.addWidget(QLabel("🌐 Uzak Depo URL (Remote Git URL):"))
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("https://github.com/kullanici/proje.git veya git@github.com:...")
        self.txt_url.setStyleSheet(combo_style)
        layout.addWidget(self.txt_url)

        layout.addWidget(QLabel("🌿 Varsayılan Dal (Branch):"))
        self.txt_branch = QLineEdit("main")
        self.txt_branch.setStyleSheet(combo_style)
        layout.addWidget(self.txt_branch)

        self.chk_default = QCheckBox("🌟 Varsayılan Depo Olarak Ayarla")
        self.chk_default.setStyleSheet("font-weight: 600; color: #1e3a8a;")
        layout.addWidget(self.chk_default)

        if self.repo_data:
            self.txt_name.setText(self.repo_data.get("name", ""))
            self.txt_url.setText(self.repo_data.get("remote_url", ""))
            self.txt_branch.setText(self.repo_data.get("default_branch", "main"))
            self.chk_default.setChecked(bool(self.repo_data.get("is_default", 0)))

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Vazgeç")
        btn_cancel.setStyleSheet("padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Depoyu Kaydet")
        btn_save.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; border: none;")
        btn_save.clicked.connect(self._save_repo)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def _save_repo(self):
        name = self.txt_name.text().strip()
        url = self.txt_url.text().strip()
        branch = self.txt_branch.text().strip() or "main"
        is_def = 1 if self.chk_default.isChecked() else 0

        if not name or not url:
            QMessageBox.warning(self, "Uyarı", "Lütfen Depo Adı ve URL alanlarını doldurunuz.")
            return

        try:
            git_tracker.add_repository(name=name, remote_url=url, default_branch=branch, is_default=is_def)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Depo kaydedilirken hata: {e}")


class GitAccountDialog(QDialog):
    """Git Kullanıcı ve Kimlik (Credentials / Token) Ekleme Diyalogu."""

    def __init__(self, account_data: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.account_data = account_data
        self.setWindowTitle("👤 Git Kullanıcısı / Token Ekle" if not account_data else "👤 Git Kullanıcısını Düzenle")
        self.setMinimumWidth(460)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        combo_style = """
            QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px 10px;
                background-color: white;
                font-size: 12px;
            }
        """

        layout.addWidget(QLabel("👤 Kullanıcı Adı (Git Username):"))
        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("Örn: ahmet_toya")
        self.txt_user.setStyleSheet(combo_style)
        layout.addWidget(self.txt_user)

        layout.addWidget(QLabel("📧 E-Posta (Git Email):"))
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("Örn: ahmet@toya.com.tr")
        self.txt_email.setStyleSheet(combo_style)
        layout.addWidget(self.txt_email)

        layout.addWidget(QLabel("🔑 Kişisel Erişim Tokeni (PAT) / Şifre:"))
        self.txt_token = QLineEdit()
        self.txt_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_token.setPlaceholderText("ghp_... veya erişim tokeni")
        self.txt_token.setStyleSheet(combo_style)
        layout.addWidget(self.txt_token)

        self.chk_default = QCheckBox("🌟 Varsayılan Kullanıcı Olarak Ayarla")
        self.chk_default.setStyleSheet("font-weight: 600; color: #1e3a8a;")
        layout.addWidget(self.chk_default)

        if self.account_data:
            self.txt_user.setText(self.account_data.get("username", ""))
            self.txt_email.setText(self.account_data.get("email", ""))
            self.txt_token.setText(self.account_data.get("token", ""))
            self.chk_default.setChecked(bool(self.account_data.get("is_default", 0)))

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Vazgeç")
        btn_cancel.setStyleSheet("padding: 6px 12px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Kullanıcıyı Kaydet")
        btn_save.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; border: none;")
        btn_save.clicked.connect(self._save_account)
        btn_box.addWidget(btn_save)
        layout.addLayout(btn_box)

    def _save_account(self):
        user = self.txt_user.text().strip()
        email = self.txt_email.text().strip()
        token = self.txt_token.text().strip()
        is_def = 1 if self.chk_default.isChecked() else 0

        if not user:
            QMessageBox.warning(self, "Uyarı", "Lütfen Kullanıcı Adı alanını doldurunuz.")
            return

        try:
            git_tracker.add_account(username=user, email=email, token=token, is_default=is_def)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kullanıcı kaydedilirken hata: {e}")


class GitCommitDialog(QDialog):
    """Git Commit & Push öncesi commit mesajı ve dal teyit diyalogu."""

    def __init__(self, current_branch: str, changed_files_count: int, parent=None):
        super().__init__(parent)
        self.current_branch = current_branch
        self.changed_files_count = changed_files_count
        self.setWindowTitle("🚀 Git'e Gönder (Commit & Push)")
        self.setMinimumWidth(540)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info_card = QFrame()
        info_card.setStyleSheet("background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px;")
        info_lyt = QVBoxLayout(info_card)
        info_lyt.setSpacing(4)

        lbl_branch = QLabel(f"🌿 <b>Hedef Dal (Branch):</b> origin/{self.current_branch}")
        lbl_branch.setStyleSheet("color: #1e40af; font-size: 12px;")
        info_lyt.addWidget(lbl_branch)

        lbl_files = QLabel(f"📁 <b>Değişen/Yeni Dosya Sayısı:</b> {self.changed_files_count} dosya")
        lbl_files.setStyleSheet("color: #1e40af; font-size: 11px;")
        info_lyt.addWidget(lbl_files)
        layout.addWidget(info_card)

        lbl_msg = QLabel("✍️ Commit Mesajı:")
        lbl_msg.setStyleSheet("font-weight: bold; font-size: 11px; color: #0f172a;")
        layout.addWidget(lbl_msg)

        self.txt_message = QTextEdit()
        self.txt_message.setPlaceholderText("Bu gönderimde yapılan değişiklikleri açıklayınız (Örn: feat: 3-bölmeli git takip ekranı tamamlandı)...")
        self.txt_message.setFixedHeight(90)
        self.txt_message.setStyleSheet("""
            QTextEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px;
                background-color: #ffffff;
                font-size: 12px;
            }
            QTextEdit:focus {
                border-color: #2563eb;
            }
        """)
        layout.addWidget(self.txt_message)

        tpl_layout = QHBoxLayout()
        tpl_layout.setSpacing(6)
        lbl_quick = QLabel("Hızlı Ön Ek:")
        lbl_quick.setStyleSheet("font-size: 10px; color: #64748b;")
        tpl_layout.addWidget(lbl_quick)

        for prefix in ["feat:", "fix:", "refactor:", "docs:", "style:", "test:"]:
            btn_p = QPushButton(prefix)
            btn_p.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_p.setStyleSheet("padding: 2px 6px; font-size: 10px; border: 1px solid #cbd5e1; border-radius: 3px; background: white;")
            btn_p.clicked.connect(lambda checked, p=prefix: self._add_prefix(p))
            tpl_layout.addWidget(btn_p)
        tpl_layout.addStretch()
        layout.addLayout(tpl_layout)

        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Vazgeç")
        self.btn_cancel.setStyleSheet("padding: 6px 14px; border: 1px solid #cbd5e1; border-radius: 4px; background: white;")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_submit = QPushButton("🚀 Şimdi Gönder (Commit & Push)")
        self.btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover { background-color: #1d4ed8; }
        """)
        self.btn_submit.clicked.connect(self._on_submit)
        btn_box.addWidget(self.btn_submit)
        layout.addLayout(btn_box)

    def _add_prefix(self, prefix: str):
        cur = self.txt_message.toPlainText().strip()
        if cur:
            self.txt_message.setText(f"{prefix} {cur}")
        else:
            self.txt_message.setText(f"{prefix} ")
        self.txt_message.setFocus()

    def _on_submit(self):
        msg = self.txt_message.toPlainText().strip()
        if not msg:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir commit mesajı yazınız.")
            return
        self.accept()

    def get_commit_message(self) -> str:
        return self.txt_message.toPlainText().strip()


class GitTrackerScreen(ThreePanelBaseWidget):
    """
    TOYA ERP Sürüm & Git Takip Merkezi Ekranı.
    Açık Teklifler ve Bekleyen Siparişler ile birebir aynı mimariye (EdgeTriggeredPanel,
    FilterableTableView, CollapsibleSection, Sayfalama) sahiptir.
    """

    def __init__(self, db_session=None, parent=None, embedded: bool = False):
        self.active_view_mode = "commits"  # 'commits', 'tasks', 'changes'
        self.worker: git_tracker.GitWorker | None = None
        self._raw_records: list[dict[str, Any]] = []

        super().__init__(
            db_session=db_session,
            profile_key="git_tracker",
            module_name="Sürüm & Git Takip Merkezi",
            parent=parent,
            embedded=embedded,
        )
        self.setObjectName("GitTrackerCanvas")
        register_layout_hint(self, "Git Yönetimi", "Sürüm ve Git Takip Ekranı")

        self.profile_manager = ProfileManager(profile_key=self.profile_key)
        self._inject_stage_progress_and_console()
        self.load_repositories_and_accounts()
        self.load_sidebar_profiles()
        self.load_data()

    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        """Açık Tekliflerdeki gibi Kolon 0'da ☑ ve Tooltip 'Seçim Yapın' bulunur."""
        if getattr(self, "active_view_mode", "commits") == "tasks":
            return {
                0: ("☑", "select"),
                1: ("ID", "id"),
                2: ("Kategori", "category"),
                3: ("Görev / Özellik", "title"),
                4: ("Detay Açıklama", "description"),
                5: ("Durum", "status"),
                6: ("İlgili Dal", "related_branch"),
                7: ("Oluşturulma", "created_at"),
            }
        elif getattr(self, "active_view_mode", "commits") == "changes":
            return {
                0: ("☑", "select"),
                1: ("Durum", "status"),
                2: ("Kod", "code"),
                3: ("Dosya Yolu", "file"),
            }
        else:
            # Commits mode (Default)
            return {
                0: ("☑", "select"),
                1: ("ID", "id"),
                2: ("Durum", "pushed_status"),
                3: ("Commit Hash", "commit_hash"),
                4: ("Tarih", "commit_date"),
                5: ("Dal (Branch)", "branch"),
                6: ("Yazar", "author"),
                7: ("Commit Mesajı / Başlık", "message"),
                8: ("Değişen Dosya", "files_changed"),
            }

    def toolbar_btn_style(self, bg_color="#ffffff", text_color="#1e293b"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
                text-align: left;
                font-family: 'Segoe UI';
            }}
            QPushButton:hover {{ background-color: #f1f5f9; }}
            QPushButton:disabled {{ color: #94a3b8; background-color: #f8fafc; border-color: #e2e8f0; }}
        """

    def setup_left_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        """Sol Panel: Bekleyen Siparişler / Teklifler tarzı Akordiyon Grupları."""
        combo_style = """
            QComboBox, QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
                background-color: white;
                color: #0f172a;
                font-size: 11px;
            }
        """

        # 1. GRUP: GİT İŞLEMLERİ (Bekleyen Siparişlerdeki gibi butonlar)
        self.sec_git_actions = CollapsibleSection("GİT İŞLEMLERİ", is_expanded=True)
        self.sec_git_actions.setObjectName("cmp.act.git")

        self.btn_commit_push = QPushButton("🚀 Git'e Gönder (F3)")
        self.btn_commit_push.setToolTip("[F3] Değişiklikleri stage'e al, commit oluştur ve push et")
        self.btn_commit_push.setShortcut("F3")
        self.btn_commit_push.setStyleSheet(self.toolbar_btn_style("#2563eb", "#ffffff"))
        self.btn_commit_push.clicked.connect(self.on_commit_push_clicked)
        self.sec_git_actions.add_widget(self.btn_commit_push)

        self.btn_fetch = QPushButton("🔄 Fetch (Durum Tara) (F4)")
        self.btn_fetch.setToolTip("[F4] Uzak sunucu durumunu kontrol et")
        self.btn_fetch.setShortcut("F4")
        self.btn_fetch.setStyleSheet(self.toolbar_btn_style())
        self.btn_fetch.clicked.connect(lambda: self._start_worker("fetch"))
        self.sec_git_actions.add_widget(self.btn_fetch)

        self.btn_pull = QPushButton("📥 Değişiklikleri Çek (Pull)")
        self.btn_pull.setStyleSheet(self.toolbar_btn_style())
        self.btn_pull.clicked.connect(lambda: self._start_worker("pull"))
        self.sec_git_actions.add_widget(self.btn_pull)

        # Stash & Pop
        stash_box = QHBoxLayout()
        stash_box.setSpacing(4)
        btn_stash = QPushButton("📦 Stash")
        btn_stash.setStyleSheet(self.toolbar_btn_style())
        btn_stash.clicked.connect(lambda: self._start_worker("stash"))
        btn_pop = QPushButton("Pop")
        btn_pop.setFixedWidth(45)
        btn_pop.setStyleSheet(self.toolbar_btn_style())
        btn_pop.clicked.connect(lambda: self._start_worker("stash_pop"))
        stash_box.addWidget(btn_stash)
        stash_box.addWidget(btn_pop)
        self.sec_git_actions.add_layout(stash_box)

        self.btn_report = QPushButton("📄 Rapor Üret (.md) (F9)")
        self.btn_report.setShortcut("F9")
        self.btn_report.setStyleSheet(self.toolbar_btn_style())
        self.btn_report.clicked.connect(self.on_report_clicked)
        self.sec_git_actions.add_widget(self.btn_report)

        btn_close = QPushButton("🚪 Kapat")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #fee2e2;
                border: 1px solid #fca5a5;
                border-radius: 6px;
                padding: 4px 8px;
                font-family: 'Segoe UI';
                font-size: 11px;
                color: #991b1b;
                font-weight: bold;
                text-align: center;
                min-height: 26px;
            }
            QPushButton:hover { background-color: #fca5a5; }
        """)
        btn_close.clicked.connect(self.close_tab)
        self.sec_git_actions.add_widget(btn_close)

        layout.addWidget(self.sec_git_actions)

        # 2. GRUP: DEPO & KULLANICI YÖNETİMİ
        self.sec_repos_users = CollapsibleSection("DEPO & KULLANICI YÖNETİMİ", is_expanded=True)

        # Depo Seçimi & Ekleme
        lbl_repo = QLabel("🌐 Aktif Git Deposu:")
        lbl_repo.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.combo_repos = QComboBox()
        self.combo_repos.setStyleSheet(combo_style)
        self.sec_repos_users.add_widget(lbl_repo)
        self.sec_repos_users.add_widget(self.combo_repos)

        repo_btn_box = QHBoxLayout()
        repo_btn_box.setSpacing(4)
        btn_add_repo = QPushButton("➕ Depo Ekle")
        btn_add_repo.setStyleSheet(self.toolbar_btn_style())
        btn_add_repo.clicked.connect(self.open_add_repo_dialog)
        btn_del_repo = QPushButton("🗑️ Sil")
        btn_del_repo.setFixedWidth(50)
        btn_del_repo.setStyleSheet(self.toolbar_btn_style())
        btn_del_repo.clicked.connect(self.delete_selected_repo)
        repo_btn_box.addWidget(btn_add_repo)
        repo_btn_box.addWidget(btn_del_repo)
        self.sec_repos_users.add_layout(repo_btn_box)

        # Kullanıcı Seçimi & Ekleme
        lbl_user = QLabel("👤 Aktif Git Kullanıcısı:")
        lbl_user.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px; margin-top: 6px;")
        self.combo_users = QComboBox()
        self.combo_users.setStyleSheet(combo_style)
        self.sec_repos_users.add_widget(lbl_user)
        self.sec_repos_users.add_widget(self.combo_users)

        user_btn_box = QHBoxLayout()
        user_btn_box.setSpacing(4)
        btn_add_user = QPushButton("➕ Kullanıcı Ekle")
        btn_add_user.setStyleSheet(self.toolbar_btn_style())
        btn_add_user.clicked.connect(self.open_add_user_dialog)
        btn_del_user = QPushButton("🗑️ Sil")
        btn_del_user.setFixedWidth(50)
        btn_del_user.setStyleSheet(self.toolbar_btn_style())
        btn_del_user.clicked.connect(self.delete_selected_user)
        user_btn_box.addWidget(btn_add_user)
        user_btn_box.addWidget(btn_del_user)
        self.sec_repos_users.add_layout(user_btn_box)

        layout.addWidget(self.sec_repos_users)

        # 3. GRUP: GÖRÜNÜM PROFİLLERİ (Açık Tekliflerdeki gibi)
        self.sec_profiles = CollapsibleSection("GÖRÜNÜM PROFİLLERİ", is_expanded=True)
        lbl_prof = QLabel("Aktif Profil:")
        lbl_prof.setStyleSheet("font-weight: bold; color: #475569; font-size: 11px;")
        self.combo_sidebar_profiles = QComboBox()
        self.combo_sidebar_profiles.setStyleSheet(combo_style)
        self.combo_sidebar_profiles.currentTextChanged.connect(self._on_sidebar_profile_changed)

        prof_btn_lyt = QHBoxLayout()
        prof_btn_lyt.setSpacing(4)
        btn_save_prof = QPushButton("💾 Kaydet")
        btn_save_prof.setStyleSheet(self.toolbar_btn_style())
        btn_save_prof.clicked.connect(self.save_current_profile)
        btn_manage_prof = QPushButton("⚙️ Sütunlar")
        btn_manage_prof.setStyleSheet(self.toolbar_btn_style())
        btn_manage_prof.clicked.connect(self.open_column_manager)
        prof_btn_lyt.addWidget(btn_save_prof)
        prof_btn_lyt.addWidget(btn_manage_prof)

        self.sec_profiles.add_widget(lbl_prof)
        self.sec_profiles.add_widget(self.combo_sidebar_profiles)
        self.sec_profiles.add_layout(prof_btn_lyt)
        layout.addWidget(self.sec_profiles)

        layout.addStretch()

    def setup_right_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        """Sağ Panel: Filtreler, Durum Göstergeleri, Seçili Detayı ve Canlı Konsol."""
        combo_style = """
            QComboBox, QLineEdit {
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 8px;
                background-color: white;
                color: #0f172a;
                font-size: 11px;
            }
        """

        # 1. GRUP: FİLTRELER & GÖRÜNÜM
        self.sec_filters = CollapsibleSection("FİLTRELER & DAL", is_expanded=True)

        lbl_search = QLabel("Mesaj / Hash / Yazar:")
        lbl_search.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px;")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Hızlı ara...")
        self.search_box.textChanged.connect(self.on_filter_changed)
        self.search_box.setStyleSheet(combo_style)
        self.sec_filters.add_widget(lbl_search)
        self.sec_filters.add_widget(self.search_box)

        lbl_view = QLabel("📑 Tablo Görünümü:")
        lbl_view.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px; margin-top: 4px;")
        self.cmb_view_mode = QComboBox()
        self.cmb_view_mode.addItems(["📦 Commit Geçmişi", "🚀 Yol Haritası & Görevler", "🟡 Değişen Dosyalar"])
        self.cmb_view_mode.currentIndexChanged.connect(self._on_view_mode_changed)
        self.cmb_view_mode.setStyleSheet(combo_style)
        self.sec_filters.add_widget(lbl_view)
        self.sec_filters.add_widget(self.cmb_view_mode)

        lbl_branch = QLabel("🌿 Dal (Branch):")
        lbl_branch.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px; margin-top: 4px;")
        self.cmb_branch = QComboBox()
        self.cmb_branch.currentTextChanged.connect(self.on_filter_changed)
        self.cmb_branch.setStyleSheet(combo_style)
        self.sec_filters.add_widget(lbl_branch)
        self.sec_filters.add_widget(self.cmb_branch)

        lbl_status = QLabel("Gönderim Durumu:")
        lbl_status.setStyleSheet("font-weight: bold; color: #0f172a; font-size: 11px; margin-top: 4px;")
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["Tümü", "Gönderildi (Pushed)", "Yerel (Gönderilmedi)"])
        self.cmb_status.currentTextChanged.connect(self.on_filter_changed)
        self.cmb_status.setStyleSheet(combo_style)
        self.sec_filters.add_widget(lbl_status)
        self.sec_filters.add_widget(self.cmb_status)

        btn_clear = QPushButton("🗑️ Filtreleri Temizle")
        btn_clear.setStyleSheet("border: 1px solid #cbd5e1; background: white; padding: 6px; border-radius: 4px; font-weight: 600; font-size: 11px;")
        btn_clear.clicked.connect(self.clear_filters)
        self.sec_filters.add_widget(btn_clear)

        layout.addWidget(self.sec_filters)

        # 2. GRUP: DEPO VE BAĞLANTI DURUMU
        self.sec_repo_status = CollapsibleSection("DEPO & BAĞLANTI DURUMU", is_expanded=True)
        self.lbl_branch_name = QLabel("🌿 Dal: -")
        self.lbl_branch_name.setStyleSheet("font-weight: bold; font-size: 11px; color: #0f172a;")
        self.lbl_remote = QLabel("🌐 Remote: -")
        self.lbl_remote.setWordWrap(True)
        self.lbl_remote.setStyleSheet("font-size: 10px; color: #64748b;")
        self.lbl_unpushed = QLabel("🔴 Gönderilmedi: 0 commit")
        self.lbl_unpushed.setStyleSheet("font-weight: bold; color: #dc2626; font-size: 11px;")
        self.lbl_changed = QLabel("🟡 Değişen: 0 dosya")
        self.lbl_changed.setStyleSheet("font-weight: bold; color: #d97706; font-size: 11px;")

        self.sec_repo_status.add_widget(self.lbl_branch_name)
        self.sec_repo_status.add_widget(self.lbl_remote)
        self.sec_repo_status.add_widget(self.lbl_unpushed)
        self.sec_repo_status.add_widget(self.lbl_changed)
        layout.addWidget(self.sec_repo_status)

        # 3. GRUP: SEÇİLİ KAYIT DETAY KARTI
        self.sec_selected_detail = CollapsibleSection("SEÇİLİ KAYIT DETAYI", is_expanded=True)
        
        detail_card = QFrame()
        detail_card.setStyleSheet("background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px;")
        d_lyt = QVBoxLayout(detail_card)
        d_lyt.setContentsMargins(4, 4, 4, 4)
        d_lyt.setSpacing(4)

        hash_box = QHBoxLayout()
        self.lbl_hash = QLabel("Hash: -")
        self.lbl_hash.setStyleSheet("font-family: monospace; font-weight: bold; color: #2563eb;")
        self.btn_copy_hash = QPushButton("📋")
        self.btn_copy_hash.setToolTip("Hash Kopyala")
        self.btn_copy_hash.setFixedSize(22, 22)
        self.btn_copy_hash.clicked.connect(self._copy_hash)
        self.btn_copy_hash.setStyleSheet("border: 1px solid #cbd5e1; background: white; border-radius: 3px;")
        hash_box.addWidget(self.lbl_hash)
        hash_box.addWidget(self.btn_copy_hash)
        d_lyt.addLayout(hash_box)

        self.lbl_author_date = QLabel("Yazar / Tarih: -")
        self.lbl_author_date.setWordWrap(True)
        self.lbl_author_date.setStyleSheet("font-size: 10px; color: #475569;")
        d_lyt.addWidget(self.lbl_author_date)

        self.lbl_status_badge = QLabel("Durum: -")
        self.lbl_status_badge.setStyleSheet("font-weight: bold; font-size: 10px; color: #047857;")
        d_lyt.addWidget(self.lbl_status_badge)

        self.lbl_detail_message = QLabel("Tablodan bir kayıt seçiniz.")
        self.lbl_detail_message.setWordWrap(True)
        self.lbl_detail_message.setStyleSheet("font-size: 11px; color: #1e293b; background: #f8fafc; padding: 4px; border: 1px solid #e2e8f0; border-radius: 4px;")
        d_lyt.addWidget(self.lbl_detail_message)

        self.sec_selected_detail.add_widget(detail_card)
        layout.addWidget(self.sec_selected_detail)

        # 4. GRUP: KONSOL & ÇIKTI
        self.sec_console_toggle = CollapsibleSection("CANLI KONSOL & LOG", is_expanded=True)
        self.btn_toggle_console = QPushButton("🖥️ Konsol Çıktısı (Aç/Kapat)")
        self.btn_toggle_console.setStyleSheet(self.toolbar_btn_style())
        self.btn_toggle_console.clicked.connect(self._toggle_console)
        self.sec_console_toggle.add_widget(self.btn_toggle_console)
        layout.addWidget(self.sec_console_toggle)

        layout.addStretch()

    def _inject_stage_progress_and_console(self):
        """Orta panelin üstüne 5 aşamalı ilerleme çubuğu ve altına konsol çekmecesi ekler."""
        # 1. Aşama İlerleme Kartı (Top Bar)
        self.progress_frame = QFrame()
        self.progress_frame.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px;")
        p_lyt = QVBoxLayout(self.progress_frame)
        p_lyt.setContentsMargins(6, 4, 6, 4)
        p_lyt.setSpacing(4)

        top_row = QHBoxLayout()
        self.lbl_stage = QLabel("🟢 Sistem Hazır (Beklemede)")
        self.lbl_stage.setStyleSheet("font-size: 11px; font-weight: bold; color: #1e3a8a;")
        top_row.addWidget(self.lbl_stage)
        top_row.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setValue(100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background-color: #e2e8f0; border-radius: 5px; border: none; }
            QProgressBar::chunk { background-color: #2563eb; border-radius: 5px; }
        """)
        top_row.addWidget(self.progress_bar)
        p_lyt.addLayout(top_row)

        # Insert to top of center_layout
        self.center_layout.insertWidget(0, self.progress_frame)

        # 2. Konsol Çekmecesi (Bottom)
        self.console_drawer = QPlainTextEdit()
        self.console_drawer.setReadOnly(True)
        self.console_drawer.setFixedHeight(100)
        self.console_drawer.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0f172a;
                color: #38bdf8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border-radius: 4px;
                padding: 6px;
                border: 1px solid #1e293b;
            }
        """)
        self.console_drawer.hide()
        self.center_layout.addWidget(self.console_drawer)

        # Sayfalama Barı
        self.pagination_layout = QHBoxLayout()
        self.pagination_layout.setContentsMargins(0, 4, 0, 0)
        self.pagination_layout.setSpacing(6)

        self.btn_first_page = QPushButton("⏮️")
        self.btn_first_page.clicked.connect(self.go_to_first_page)
        self.btn_prev_page = QPushButton("⬅️")
        self.btn_prev_page.clicked.connect(self.go_to_prev_page)

        self.lbl_page_info = QLabel("Sayfa 1 / 1")
        self.lbl_page_info.setStyleSheet("font-weight: bold; color: #475569;")

        self.btn_next_page = QPushButton("➡️")
        self.btn_next_page.clicked.connect(self.go_to_next_page)
        self.btn_last_page = QPushButton("⏭️")
        self.btn_last_page.clicked.connect(self.go_to_last_page)

        self.combo_page_size = QComboBox()
        self.combo_page_size.addItems(["25 kayıt", "50 kayıt", "100 kayıt"])
        self.combo_page_size.currentTextChanged.connect(self.on_page_size_changed)

        for btn in [self.btn_first_page, self.btn_prev_page, self.btn_next_page, self.btn_last_page]:
            btn.setStyleSheet("QPushButton { border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; background: white; }")

        self.pagination_layout.addWidget(self.btn_first_page)
        self.pagination_layout.addWidget(self.btn_prev_page)
        self.pagination_layout.addWidget(self.lbl_page_info)
        self.pagination_layout.addWidget(self.btn_next_page)
        self.pagination_layout.addWidget(self.btn_last_page)
        self.pagination_layout.addStretch()
        self.pagination_layout.addWidget(QLabel("Adet:"))
        self.pagination_layout.addWidget(self.combo_page_size)

        self.center_layout.addLayout(self.pagination_layout)

        # Tablo seçimi ve çift tıklama
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_view.doubleClicked.connect(self.on_row_double_clicked)

        # Header Kolon 0 için Tooltip Ayarı ("Seçim Yapın")
        self.table_model.setHeaderData(0, Qt.Orientation.Horizontal, "Seçim Yapın", Qt.ItemDataRole.ToolTipRole)

    def load_repositories_and_accounts(self):
        """Depo ve Kullanıcı listesini yükler."""
        repos = git_tracker.get_repositories()
        self.combo_repos.blockSignals(True)
        self.combo_repos.clear()
        for r in repos:
            is_def = " (Varsayılan)" if r.get("is_default") else ""
            self.combo_repos.addItem(f"{r['name']}{is_def}", r)
        self.combo_repos.blockSignals(False)

        accounts = git_tracker.get_accounts()
        self.combo_users.blockSignals(True)
        self.combo_users.clear()
        for a in accounts:
            is_def = " (Varsayılan)" if a.get("is_default") else ""
            self.combo_users.addItem(f"{a['username']}{is_def}", a)
        self.combo_users.blockSignals(False)

    def load_sidebar_profiles(self):
        if not hasattr(self, "combo_sidebar_profiles") or not hasattr(self, "profile_manager"):
            return
        self.combo_sidebar_profiles.blockSignals(True)
        self.combo_sidebar_profiles.clear()
        profiles = self.profile_manager.load_profiles()
        for name in profiles.keys():
            self.combo_sidebar_profiles.addItem(name)
        active = self.profile_manager.get_active_profile_name()
        idx = self.combo_sidebar_profiles.findText(active)
        if idx >= 0:
            self.combo_sidebar_profiles.setCurrentIndex(idx)
        self.combo_sidebar_profiles.blockSignals(False)

    def _on_sidebar_profile_changed(self, profile_name):
        if not profile_name:
            return
        p = self.profile_manager.get_profile(profile_name)
        if p and hasattr(self, "filterable_table"):
            self.filterable_table.apply_view_profile(p)

    def save_current_profile(self):
        active_name = self.combo_sidebar_profiles.currentText() or "Varsayılan"
        current_p = self.filterable_table.get_current_view_as_profile(active_name)
        self.profile_manager.save_profile(active_name, current_p)
        QMessageBox.information(self, "Profil Kaydedildi", f"'{active_name}' görünüm profili kaydedildi.")

    def open_column_manager(self):
        self.filterable_table.open_column_manager_dialog()

    def open_add_repo_dialog(self):
        dlg = GitRepositoryDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_repositories_and_accounts()
            QMessageBox.information(self, "Başarılı", "Git deposu başarıyla eklendi.")

    def delete_selected_repo(self):
        repo_data = self.combo_repos.currentData()
        if not repo_data:
            return
        res = QMessageBox.question(self, "Depo Sil", f"'{repo_data['name']}' deposunu silmek istiyor musunuz?")
        if res == QMessageBox.StandardButton.Yes:
            git_tracker.delete_repository(repo_data["id"])
            self.load_repositories_and_accounts()

    def open_add_user_dialog(self):
        dlg = GitAccountDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_repositories_and_accounts()
            QMessageBox.information(self, "Başarılı", "Git kullanıcısı başarıyla eklendi.")

    def delete_selected_user(self):
        user_data = self.combo_users.currentData()
        if not user_data:
            return
        res = QMessageBox.question(self, "Kullanıcı Sil", f"'{user_data['username']}' kullanıcısını silmek istiyor musunuz?")
        if res == QMessageBox.StandardButton.Yes:
            git_tracker.delete_account(user_data["id"])
            self.load_repositories_and_accounts()

    def _on_view_mode_changed(self, idx: int):
        modes = ["commits", "tasks", "changes"]
        if 0 <= idx < len(modes):
            self.active_view_mode = modes[idx]
            self.headers_dict = self.setup_headers_dict()
            self.filterable_table.headers_dict = self.headers_dict
            
            headers = [self.headers_dict[i][0] for i in sorted(self.headers_dict.keys())]
            self.table_model.setHorizontalHeaderLabels(headers)
            self.table_model.setHeaderData(0, Qt.Orientation.Horizontal, "Seçim Yapın", Qt.ItemDataRole.ToolTipRole)
            self.load_data()

    def load_data(self):
        """Verileri SQLite ve Git üzerinden yükler ve sayfalamaya uygun biçimde tabloya basar."""
        try:
            git_tracker.init_db()
            git_tracker.sync_git_history()
            git_tracker.seed_initial_tasks()

            status_info = git_tracker.get_git_status()
            branches = git_tracker.get_git_branches()

            # Sağ panel güncellemeleri
            if not git_tracker.is_git_available():
                self.lbl_branch_name.setText("🌿 Dal: (Git Bulunamadı)")
                self.lbl_remote.setText("🌐 Remote: (Git Bulunamadı)")
                self.lbl_unpushed.setText("⚪ Git Yüklü Değil / PATH Yok")
                self.lbl_unpushed.setStyleSheet("font-weight: bold; color: #64748b;")
                self.lbl_changed.setText("⚪ Git Yüklü Değil")
                self.lbl_changed.setStyleSheet("font-weight: bold; color: #64748b;")
            else:
                self.lbl_branch_name.setText(f"🌿 Dal: {status_info['branch']}")
                remote_str = status_info.get("remote_url", "")
                if remote_str:
                    short_r = remote_str.replace("https://github.com/", "gh:").replace(".git", "")
                    self.lbl_remote.setText(f"🌐 Remote: {short_r}")
                else:
                    self.lbl_remote.setText("🌐 Remote: (Bağlantı Yok)")

                ahead = status_info.get("ahead_count", 0)
                self.lbl_unpushed.setText(f"🔴 Gönderilmedi: {ahead} commit")
                self.lbl_unpushed.setStyleSheet("font-weight: bold; color: #dc2626;" if ahead > 0 else "color: #16a34a;")

                mod_count = status_info.get("modified_count", 0)
                self.lbl_changed.setText(f"🟡 Değişen: {mod_count} dosya")
                self.lbl_changed.setStyleSheet("font-weight: bold; color: #d97706;" if mod_count > 0 else "color: #16a34a;")

            # Branch listesini doldur
            self.cmb_branch.blockSignals(True)
            self.cmb_branch.clear()
            self.cmb_branch.addItem("Tümü")
            for b in branches:
                self.cmb_branch.addItem(b)
            idx = self.cmb_branch.findText(status_info["branch"])
            if idx > 0:
                self.cmb_branch.setCurrentIndex(idx)
            self.cmb_branch.blockSignals(False)

            # Tablo verilerini hazırla
            conn = git_tracker.get_db_connection()
            cursor = conn.cursor()

            search_txt = self.search_box.text().strip().lower()
            selected_branch = self.cmb_branch.currentText()
            selected_status = self.cmb_status.currentText()

            self.table_model.removeRows(0, self.table_model.rowCount())

            if self.active_view_mode == "commits":
                cursor.execute("SELECT * FROM git_commits ORDER BY commit_date DESC")
                rows = cursor.fetchall()
                filtered = []
                for r in rows:
                    if selected_branch != "Tümü" and r["branch"] != selected_branch:
                        continue
                    if selected_status == "Gönderildi (Pushed)" and r["pushed_status"] != "Gönderildi":
                        continue
                    if selected_status == "Yerel (Gönderilmedi)" and r["pushed_status"] == "Gönderildi":
                        continue
                    if search_txt and search_txt not in (r["message"] or "").lower() and search_txt not in (r["commit_hash"] or "").lower() and search_txt not in (r["author"] or "").lower():
                        continue
                    filtered.append(r)

                self.total_records = len(filtered)
                start_idx = (self.current_page - 1) * self.per_page
                page_rows = filtered[start_idx : start_idx + self.per_page]

                for row_idx, r in enumerate(page_rows):
                    pstatus = r["pushed_status"] or "Gönderildi"
                    status_badge = "🟢 Gönderildi" if pstatus == "Gönderildi" else "🔴 Yerel"
                    chash = r["commit_hash"][:7] if r["commit_hash"] else ""

                    items = [
                        QStandardItem("☐"),
                        QStandardItem(str(row_idx + 1)),
                        QStandardItem(status_badge),
                        QStandardItem(chash),
                        QStandardItem(r["commit_date"] or ""),
                        QStandardItem(r["branch"] or ""),
                        QStandardItem(r["author"] or ""),
                        QStandardItem(r["message"] or ""),
                        QStandardItem(str(r["files_changed"] or 0)),
                    ]
                    items[0].setCheckable(True)
                    items[0].setCheckState(Qt.CheckState.Unchecked)
                    items[0].setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_model.appendRow(items)

            elif self.active_view_mode == "tasks":
                cursor.execute("SELECT * FROM tasks ORDER BY status DESC, category ASC")
                rows = cursor.fetchall()
                filtered = []
                for r in rows:
                    if search_txt and search_txt not in (r["title"] or "").lower() and search_txt not in (r["description"] or "").lower():
                        continue
                    filtered.append(r)

                self.total_records = len(filtered)
                start_idx = (self.current_page - 1) * self.per_page
                page_rows = filtered[start_idx : start_idx + self.per_page]

                for r in page_rows:
                    st = r["status"]
                    st_icon = "✅ Yapıldı" if st == "Yapıldı" else ("⏳ Devam Ediyor" if st == "Devam Ediyor" else "📌 Bekliyor")
                    items = [
                        QStandardItem("☐"),
                        QStandardItem(str(r["id"])),
                        QStandardItem(r["category"] or ""),
                        QStandardItem(r["title"] or ""),
                        QStandardItem(r["description"] or ""),
                        QStandardItem(st_icon),
                        QStandardItem(r["related_branch"] or ""),
                        QStandardItem(r["created_at"] or ""),
                    ]
                    items[0].setCheckable(True)
                    items[0].setCheckState(Qt.CheckState.Unchecked)
                    self.table_model.appendRow(items)

            elif self.active_view_mode == "changes":
                changes = status_info.get("changed_files", [])
                filtered = [c for c in changes if not search_txt or search_txt in c["file"].lower()]
                self.total_records = len(filtered)
                start_idx = (self.current_page - 1) * self.per_page
                page_rows = filtered[start_idx : start_idx + self.per_page]

                for c in page_rows:
                    badge = "🟡 Değişti" if not c["staged"] else "🟢 Sahnelendi"
                    items = [
                        QStandardItem("☐"),
                        QStandardItem(badge),
                        QStandardItem(c["code"]),
                        QStandardItem(c["file"]),
                    ]
                    items[0].setCheckable(True)
                    items[0].setCheckState(Qt.CheckState.Unchecked)
                    self.table_model.appendRow(items)

            conn.close()
            self._update_pagination_ui()

        except Exception as e:
            logger.error(f"GitTrackerScreen load_data error: {e}", exc_info=True)

    def _update_pagination_ui(self):
        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        self.lbl_page_info.setText(f"Sayfa {self.current_page} / {total_pages} (Toplam {self.total_records} kayıt)")
        self.btn_first_page.setEnabled(self.current_page > 1)
        self.btn_prev_page.setEnabled(self.current_page > 1)
        self.btn_next_page.setEnabled(self.current_page < total_pages)
        self.btn_last_page.setEnabled(self.current_page < total_pages)

    def go_to_first_page(self):
        self.current_page = 1
        self.load_data()

    def go_to_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def go_to_next_page(self):
        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_data()

    def go_to_last_page(self):
        total_pages = max(1, (self.total_records + self.per_page - 1) // self.per_page)
        self.current_page = total_pages
        self.load_data()

    def on_page_size_changed(self, text: str):
        try:
            size = int(text.split()[0])
            self.per_page = size
            self.current_page = 1
            self.load_data()
        except Exception:
            pass

    def on_selection_changed(self, selected, deselected):
        indexes = self.table_view.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()

        if self.active_view_mode == "commits":
            chash = self.table_model.item(row, 3).text() if self.table_model.item(row, 3) else ""
            date_s = self.table_model.item(row, 4).text() if self.table_model.item(row, 4) else ""
            branch = self.table_model.item(row, 5).text() if self.table_model.item(row, 5) else ""
            author = self.table_model.item(row, 6).text() if self.table_model.item(row, 6) else ""
            msg = self.table_model.item(row, 7).text() if self.table_model.item(row, 7) else ""
            status = self.table_model.item(row, 2).text() if self.table_model.item(row, 2) else ""

            self.lbl_hash.setText(f"Hash: {chash}")
            self.btn_copy_hash.setProperty("full_hash", chash)
            self.lbl_author_date.setText(f"👤 {author}\n📅 {date_s} (🌿 {branch})")
            self.lbl_status_badge.setText(f"Durum: {status}")
            self.lbl_detail_message.setText(msg)

        elif self.active_view_mode == "tasks":
            tid = self.table_model.item(row, 1).text() if self.table_model.item(row, 1) else ""
            cat = self.table_model.item(row, 2).text() if self.table_model.item(row, 2) else ""
            title = self.table_model.item(row, 3).text() if self.table_model.item(row, 3) else ""
            desc = self.table_model.item(row, 4).text() if self.table_model.item(row, 4) else ""
            status = self.table_model.item(row, 5).text() if self.table_model.item(row, 5) else ""

            self.lbl_hash.setText(f"Görev #{tid}")
            self.btn_copy_hash.setProperty("full_hash", tid)
            self.lbl_author_date.setText(f"📂 Kategori: {cat}")
            self.lbl_status_badge.setText(f"Durum: {status}")
            self.lbl_detail_message.setText(f"{title}\n\n{desc}")

        elif self.active_view_mode == "changes":
            fpath = self.table_model.item(row, 3).text() if self.table_model.item(row, 3) else ""
            code_c = self.table_model.item(row, 2).text() if self.table_model.item(row, 2) else ""
            badge = self.table_model.item(row, 1).text() if self.table_model.item(row, 1) else ""

            self.lbl_hash.setText("Dosya Değişikliği")
            self.btn_copy_hash.setProperty("full_hash", fpath)
            self.lbl_author_date.setText(f"Kod: {code_c}")
            self.lbl_status_badge.setText(f"Durum: {badge}")
            self.lbl_detail_message.setText(fpath)

    def on_row_double_clicked(self, index):
        self.on_selection_changed(None, None)

    def _copy_hash(self):
        val = self.btn_copy_hash.property("full_hash") or self.lbl_hash.text()
        cb = QApplication.clipboard()
        if cb and val:
            cb.setText(val)
            self.btn_copy_hash.setText("✓")
            QTimer.singleShot(1500, lambda: self.btn_copy_hash.setText("📋"))

    def _toggle_console(self):
        if self.console_drawer.isVisible():
            self.console_drawer.hide()
        else:
            self.console_drawer.show()

    def on_commit_push_clicked(self):
        """Açık Teklifler / Bekleyen Siparişler gibi F3 veya butonla tetiklenen Git Gönderimi."""
        if not git_tracker.is_git_available():
            QMessageBox.warning(
                self,
                "Git Bulunamadı",
                "Sisteminizde Git komut satırı aracı (git.exe) bulunamadı.\n"
                "Lütfen Git'in kurulu ve sistem PATH ortam değişkeninde olduğundan emin olun.",
            )
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Meşgul", "Devam eden bir Git işlemi var. Lütfen bekleyiniz.")
            return

        status_info = git_tracker.get_git_status()
        dlg = GitCommitDialog(status_info["branch"], status_info["modified_count"], self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            msg = dlg.get_commit_message()
            self._start_worker("commit_and_push", {"message": msg, "branch": status_info["branch"]})

    def on_report_clicked(self):
        try:
            git_tracker.generate_report()
            QMessageBox.information(self, "Rapor Üretildi", "GIT_TRACKER_REPORT.md başarıyla güncellendi.")
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Rapor üretilirken hata: {e}")

    def _start_worker(self, action_name: str, params: dict[str, Any] | None = None):
        """Asenkron GitWorker'ı başlatır ve konsolu açar."""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Meşgul", "Devam eden bir Git işlemi var.")
            return

        self.console_drawer.show()
        now_t = datetime.now().strftime('%H:%M:%S')
        self.console_drawer.appendPlainText(f"\n--- [BAŞLATILDI: {action_name.upper()}] {now_t} ---")

        self.progress_bar.setValue(10)
        self.lbl_stage.setText(f"⏳ İşlem Başlatılıyor: {action_name}...")
        self.lbl_stage.setStyleSheet("font-size: 11px; font-weight: bold; color: #d97706;")

        self.worker = git_tracker.GitWorker(action=action_name, params=params, parent=self)
        self.worker.stage_progress.connect(self._on_stage_progress)
        self.worker.log_line.connect(self._on_log_line)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_stage_progress(self, stage_title: str, percent: int):
        self.lbl_stage.setText(stage_title)
        self.progress_bar.setValue(percent)

    def _on_log_line(self, line: str):
        self.console_drawer.appendPlainText(line)
        sb = self.console_drawer.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _on_worker_finished(self, success: bool, message: str):
        self.progress_bar.setValue(100)
        if success:
            self.lbl_stage.setText("✅ " + message)
            self.lbl_stage.setStyleSheet("font-size: 11px; font-weight: bold; color: #16a34a;")
            QMessageBox.information(self, "Başarılı", message)
        else:
            self.lbl_stage.setText("❌ Hata: " + message)
            self.lbl_stage.setStyleSheet("font-size: 11px; font-weight: bold; color: #dc2626;")
            QMessageBox.critical(self, "Git İşlem Hatası", f"İşlem tamamlanamadı:\n{message}")

        self.load_data()

    def close_tab(self):
        parent_tab = self.parentWidget()
        while parent_tab and not hasattr(parent_tab, "removeTab"):
            parent_tab = parent_tab.parentWidget()
        if parent_tab and hasattr(parent_tab, "removeTab"):
            cur_idx = parent_tab.indexOf(self) if hasattr(parent_tab, "indexOf") else parent_tab.currentIndex()
            if cur_idx >= 0:
                parent_tab.removeTab(cur_idx)
