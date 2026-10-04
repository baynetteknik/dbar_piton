"""TOYA ERP - Sürüm / Milestone Yönetimi Diyalogları (DevVersionDialog, DevReleaseDialog, DevVersionManageDialog).

Geliştirme maddelerini sürümlere bağlama, sürüm planlama, sürüm kapatma/yayınlama,
SURUM_NOTLARI.md güncelleme ve Git Tag oluşturma işlemlerini yönetir.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from src.desktop.services.dev_tracker_store import (
    SURUM_DURUMLARI,
    DevTracker,
    DevTrackerError,
)
from src.desktop.ui.components.dialog_style import (
    apply_light_dialog_style,
    bilgi,
    onay,
    uyari,
)

_COMBO_STYLE = """
    QComboBox {
        combobox-popup: 0;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 4px 6px;
        background-color: white;
        color: #0f172a;
        font-size: 11px;
    }
    QComboBox QAbstractItemView {
        outline: 0;
        padding: 0px;
        border: 1px solid #cbd5e1;
        background-color: #ffffff;
        color: #0f172a;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 6px;
        min-height: 20px;
    }
"""


def _parse_semver(vcode: str) -> tuple[int, int, int]:
    """Extracts (major, minor, patch) integers from a version code string."""
    clean = re.sub(r"^[^\d]*", "", vcode.strip())
    parts = clean.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 1
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return major, minor, patch
    except ValueError:
        return 1, 0, 0


class DevVersionDialog(QDialog):
    """Yeni sürüm oluşturma veya mevcut sürümü düzenleme penceresi."""

    def __init__(self, tracker: DevTracker, version_id: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self.tracker = tracker
        self.version_id = version_id
        self.setWindowTitle("Sürüm Planlama & Düzenleme" if version_id else "🎯 Yeni Sürüm Planla")
        self.setMinimumWidth(560)
        apply_light_dialog_style(self)
        self._init_ui()
        if version_id:
            self._yukle()
        else:
            self._varsayilan_doldur()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        # Sürüm Kodu & Semver Öneri Butonları
        vbox_code = QVBoxLayout()
        self.txt_version_code = QLineEdit()
        self.txt_version_code.setPlaceholderText("Örn: v1.2.0")
        vbox_code.addWidget(self.txt_version_code)

        row_semver = QHBoxLayout()
        row_semver.setSpacing(4)
        lbl_sem = QLabel("Hızlı Artır:")
        lbl_sem.setStyleSheet("font-size: 10px; color: #64748b;")
        row_semver.addWidget(lbl_sem)

        self.btn_patch = QPushButton("+0.0.1 Patch")
        self.btn_minor = QPushButton("+0.1.0 Minor")
        self.btn_major = QPushButton("+1.0.0 Major")
        for b, delta in ((self.btn_patch, (0, 0, 1)), (self.btn_minor, (0, 1, 0)), (self.btn_major, (1, 0, 0))):
            b.setStyleSheet("font-size: 10px; padding: 2px 6px; background: white; border: 1px solid #cbd5e1; border-radius: 3px;")
            b.clicked.connect(lambda _=False, d=delta: self._increment_semver(d))
            row_semver.addWidget(b)
        row_semver.addStretch()
        vbox_code.addLayout(row_semver)
        form.addRow("Sürüm Kodu *", vbox_code)

        # Sürüm Başlığı
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Örn: Kasa & Banka Entegrasyonu ve Belge Zinciri")
        form.addRow("Sürüm Başlığı *", self.txt_title)

        # Hedef Tarih
        self.dt_target = QDateEdit()
        self.dt_target.setCalendarPopup(True)
        self.dt_target.setDate(QDate.currentDate().addDays(14))
        self.dt_target.setDisplayFormat("yyyy-MM-dd")

        # Durum
        self.cmb_status = QComboBox()
        self.cmb_status.setStyleSheet(_COMBO_STYLE)
        for k, name in SURUM_DURUMLARI.items():
            self.cmb_status.addItem(name, k)

        h_status = QHBoxLayout()
        h_status.addWidget(self.dt_target, 1)
        lbl_st = QLabel("Durum:")
        lbl_st.setStyleSheet("font-weight: 600; font-size: 11px; margin-left: 8px;")
        h_status.addWidget(lbl_st)
        h_status.addWidget(self.cmb_status, 1)
        form.addRow("Hedef Tarih", h_status)

        # Açıklama
        self.txt_desc = QPlainTextEdit()
        self.txt_desc.setPlaceholderText("Bu sürümde tamamlanması hedeflenen ana özellikler ve geliştirme notları...")
        self.txt_desc.setFixedHeight(90)
        form.addRow("Sürüm Notu / Hedefler", self.txt_desc)

        layout.addLayout(form)

        self.lbl_hata = QLabel("")
        self.lbl_hata.setStyleSheet("color: #dc2626; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl_hata)

        # Butonlar
        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_save = QPushButton("💾 Sürümü Kaydet")
        self.btn_save.setDefault(True)
        self.btn_cancel = QPushButton("✖ Vazgeç")
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel.clicked.connect(self.reject)
        bar.addWidget(self.btn_save)
        bar.addWidget(self.btn_cancel)
        layout.addLayout(bar)

    def _varsayilan_doldur(self):
        # Find latest version to suggest next patch/minor
        s_list = self.tracker.surum_liste()
        if s_list:
            last_code = s_list[0]["version_code"]
            maj, mino, pat = _parse_semver(last_code)
            has_v = last_code.startswith("v")
            prefix = "v" if has_v else ""
            self.txt_version_code.setText(f"{prefix}{maj}.{mino}.{pat + 1}")
        else:
            self.txt_version_code.setText("v1.0.0")

    def _increment_semver(self, delta: tuple[int, int, int]):
        cur = self.txt_version_code.text().strip() or "v1.0.0"
        has_v = cur.startswith("v")
        prefix = "v" if has_v else ""
        maj, mino, pat = _parse_semver(cur)
        if delta[0] > 0:
            maj += delta[0]
            mino = 0
            pat = 0
        elif delta[1] > 0:
            mino += delta[1]
            pat = 0
        elif delta[2] > 0:
            pat += delta[2]
        self.txt_version_code.setText(f"{prefix}{maj}.{mino}.{pat}")

    def _yukle(self):
        r = self.tracker.surum_getir(self.version_id)
        self.txt_version_code.setText(r["version_code"])
        self.txt_title.setText(r["title"])
        if r.get("target_date"):
            try:
                self.dt_target.setDate(QDate.fromString(r["target_date"], "yyyy-MM-dd"))
            except Exception:
                pass
        self.cmb_status.setCurrentIndex(max(self.cmb_status.findData(r["status"]), 0))
        self.txt_desc.setPlainText(r.get("description") or "")

    def _save(self):
        vcode = self.txt_version_code.text().strip()
        title = self.txt_title.text().strip()
        tdate = self.dt_target.date().toString("yyyy-MM-dd")
        status = self.cmb_status.currentData()
        desc = self.txt_desc.toPlainText().strip()

        if not vcode:
            self.lbl_hata.setText("Lütfen bir sürüm kodu giriniz (Örn: v1.2.0).")
            return
        if not title:
            self.lbl_hata.setText("Lütfen sürüm için bir başlık belirleyiniz.")
            return

        try:
            if self.version_id:
                self.tracker.surum_guncelle(self.version_id, version_code=vcode, title=title,
                                            target_date=tdate, status=status, description=desc)
            else:
                self.tracker.surum_ekle(version_code=vcode, title=title, target_date=tdate,
                                        status=status, description=desc)
            self.accept()
        except DevTrackerError as e:
            self.lbl_hata.setText(str(e))
        except Exception as e:
            self.lbl_hata.setText(f"Kayıt hatası: {e}")


class DevReleaseDialog(QDialog):
    """Sürümü Kapatma ve Yayınlama Sihirbazı."""

    def __init__(self, tracker: DevTracker, version_code: str, parent=None) -> None:
        super().__init__(parent)
        self.tracker = tracker
        self.version_code = version_code
        self.setWindowTitle(f"🚀 Sürümü Yayınla & Kapat — [{version_code}]")
        self.setMinimumWidth(540)
        apply_light_dialog_style(self)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Bilgi Kartı
        card = QFrame()
        card.setStyleSheet("background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px;")
        card_lyt = QVBoxLayout(card)
        card_lyt.setSpacing(6)

        ver_info = self.tracker.surum_getir_kod(self.version_code) or {}
        items = self.tracker.liste(surum=self.version_code)
        completed = [i for i in items if i.get("durum") == "tamam"]
        open_items = [i for i in items if i.get("durum") != "tamam"]
        total = len(items)

        lbl_title = QLabel(f"📦 <b>Sürüm:</b> <span style='font-size:13px; color:#1e40af;'>{self.version_code}</span> — {ver_info.get('title', '')}")
        card_lyt.addWidget(lbl_title)

        pct = int((len(completed) / total) * 100) if total > 0 else 100
        lbl_stats = QLabel(f"📊 <b>İş Durumu:</b> {len(completed)} / {total} Tamamlandı (%{pct})")
        card_lyt.addWidget(lbl_stats)

        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(pct)
        pbar.setStyleSheet("QProgressBar { border: 1px solid #93c5fd; border-radius: 4px; text-align: center; height: 14px; background: white; }"
                           "QProgressBar::chunk { background-color: #2563eb; }")
        card_lyt.addWidget(pbar)
        layout.addWidget(card)

        if open_items:
            warn_card = QFrame()
            warn_card.setStyleSheet("background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 8px;")
            warn_lyt = QVBoxLayout(warn_card)
            warn_lbl = QLabel(f"⚠️ <b>Dikkat:</b> Bu sürümde henüz tamamlanmamış <b>{len(open_items)}</b> adet açık kayıt bulunmaktadır.\n"
                              "Sürüm yayınlandığında bu açık kayıtlar sürümde kalmaya devam eder (isterseniz daha sonra bir sonraki sürüme aktarabilirsiniz).")
            warn_lbl.setStyleSheet("color: #92400e; font-size: 11px;")
            warn_lbl.setWordWrap(True)
            warn_lyt.addWidget(warn_lbl)
            layout.addWidget(warn_card)

        # Yayınlama Seçenekleri Formu
        form = QFormLayout()
        form.setSpacing(8)

        self.dt_release = QDateEdit()
        self.dt_release.setCalendarPopup(True)
        self.dt_release.setDate(QDate.currentDate())
        self.dt_release.setDisplayFormat("yyyy-MM-dd")
        form.addRow("Yayınlanma Tarihi", self.dt_release)

        self.chk_surum_notu = QCheckBox("SURUM_NOTLARI.md dosyasını otomatik güncelle")
        self.chk_surum_notu.setChecked(True)
        form.addRow("", self.chk_surum_notu)

        self.chk_git_tag = QCheckBox(f"Git Sürüm Etiketi (Tag) oluştur: 'git tag -a {self.version_code}'")
        self.chk_git_tag.setChecked(True)
        form.addRow("", self.chk_git_tag)

        self.txt_tag_msg = QLineEdit()
        self.txt_tag_msg.setText(f"TOYA ERP Sürüm {self.version_code} Yayını")
        form.addRow("Git Tag Mesajı", self.txt_tag_msg)

        layout.addLayout(form)

        # Butonlar
        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_release = QPushButton("🚀 Şimdi Sürümü Yayınla ve Kapat")
        self.btn_release.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 7px 16px;")
        self.btn_release.setDefault(True)
        self.btn_cancel = QPushButton("✖ Vazgeç")
        self.btn_release.clicked.connect(self._do_release)
        self.btn_cancel.clicked.connect(self.reject)
        bar.addWidget(self.btn_release)
        bar.addWidget(self.btn_cancel)
        layout.addLayout(bar)

    def _do_release(self):
        rel_date = self.dt_release.date().toString("yyyy-MM-dd")
        do_tag = self.chk_git_tag.isChecked()
        tag_msg = self.txt_tag_msg.text().strip()

        try:
            res = self.tracker.surum_kapat_ve_yayinla(
                version_code=self.version_code,
                release_date=rel_date,
                git_tag=do_tag,
                tag_message=tag_msg,
            )
            msg = f"'{self.version_code}' sürümü başarıyla yayınlandı ve kapatıldı!\n\n"
            if self.chk_surum_notu.isChecked():
                msg += "• SURUM_NOTLARI.md güncellendi.\n"
            if do_tag:
                msg += f"• {res.get('tag_message', 'Git etiketi oluşturuldu.')}\n"
            bilgi(self, "Sürüm Yayınlandı", msg)
            self.accept()
        except Exception as e:
            uyari(self, "Yayınlama Hatası", str(e))


class DevVersionManageDialog(QDialog):
    """Sürüm & Milestone Yönetim Paneli (Tüm sürümler, durumları, ilerleme çubuğu)."""

    def __init__(self, tracker: DevTracker, parent=None) -> None:
        super().__init__(parent)
        self.tracker = tracker
        self.setWindowTitle("🎯 Sürüm & Milestone Yönetim Merkezi")
        self.setMinimumWidth(820)
        self.setMinimumHeight(460)
        apply_light_dialog_style(self)
        self._init_ui()
        self.load_versions()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Üst Başlık & Açıklama
        top_box = QHBoxLayout()
        lbl_info = QLabel("<b>Proje Sürümleri (Milestones)</b> — Geliştirme işlerini planlayın, takip edin ve tamamlandığında yayınlayın.")
        lbl_info.setStyleSheet("color: #1e3a8a; font-size: 12px;")
        top_box.addWidget(lbl_info)
        top_box.addStretch()

        self.btn_yeni = QPushButton("➕ Yeni Sürüm Planla")
        self.btn_yeni.setStyleSheet("background-color: #2563eb; color: white; font-weight: bold; padding: 5px 12px;")
        self.btn_yeni.clicked.connect(self._on_new_version)
        top_box.addWidget(self.btn_yeni)
        layout.addLayout(top_box)

        # Tablo
        self.table = QTableView()
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels([
            "Sürüm", "Başlık", "Hedef Tarih", "Yayın Tarihi", "Durum", "İşler (Biten/Top)", "İlerleme %",
        ])
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_edit_version)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("""
            QTableView {
                background-color: white;
                gridline-color: #e2e8f0;
                selection-background-color: #dbeafe;
                selection-color: #1e3a8a;
            }
            QHeaderView::section {
                background-color: #f1f5f9;
                color: #334155;
                font-weight: 600;
                padding: 4px 8px;
                border: 1px solid #e2e8f0;
            }
        """)
        layout.addWidget(self.table)

        # Alt Aksiyon Butonları
        bar = QHBoxLayout()
        self.btn_edit = QPushButton("✏️ Sürümü Düzenle")
        self.btn_release = QPushButton("🚀 Sürümü Yayınla / Kapat")
        self.btn_delete = QPushButton("🗑️ Sürümü Sil")
        self.btn_close = QPushButton("Kapat")

        self.btn_edit.clicked.connect(self._on_edit_version)
        self.btn_release.clicked.connect(self._on_release_version)
        self.btn_delete.clicked.connect(self._on_delete_version)
        self.btn_close.clicked.connect(self.accept)

        bar.addWidget(self.btn_edit)
        bar.addWidget(self.btn_release)
        bar.addWidget(self.btn_delete)
        bar.addStretch()
        bar.addWidget(self.btn_close)
        layout.addLayout(bar)

    def load_versions(self):
        self.model.setRowCount(0)
        self._versions_data = self.tracker.surum_liste()

        for r in self._versions_data:
            vid = r["id"]
            vcode = r["version_code"]
            title = r["title"]
            t_date = r.get("target_date") or "-"
            r_date = r.get("release_date") or "-"
            st_text = SURUM_DURUMLARI.get(r["status"], r["status"])
            items_str = f"{r['completed_items']} / {r['total_items']}"
            pct_str = f"%{r['progress_percent']}"

            it_vcode = QStandardItem(vcode)
            it_vcode.setData(vid, Qt.ItemDataRole.UserRole)
            it_vcode.setData(vcode, Qt.ItemDataRole.UserRole + 1)
            it_vcode.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            it_title = QStandardItem(title)
            it_tdate = QStandardItem(t_date)
            it_tdate.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_rdate = QStandardItem(r_date)
            it_rdate.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            it_status = QStandardItem(st_text)
            it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if r["status"] == "yayinlandi":
                it_status.setForeground(QColor("#15803d"))
            elif r["status"] == "gelistirmede":
                it_status.setForeground(QColor("#2563eb"))

            it_items = QStandardItem(items_str)
            it_items.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            it_pct = QStandardItem(pct_str)
            it_pct.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if r["progress_percent"] == 100:
                it_pct.setForeground(QColor("#15803d"))

            self.model.appendRow([it_vcode, it_title, it_tdate, it_rdate, it_status, it_items, it_pct])

    def _get_selected_version(self) -> tuple[int, str] | None:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            uyari(self, "Seçim Yapılmadı", "Lütfen işlem yapmak için listeden bir sürüm seçiniz.")
            return None
        idx = sel[0]
        it = self.model.item(idx.row(), 0)
        vid = it.data(Qt.ItemDataRole.UserRole)
        vcode = it.data(Qt.ItemDataRole.UserRole + 1)
        return vid, vcode

    def _on_new_version(self):
        dlg = DevVersionDialog(self.tracker, parent=self)
        if dlg.exec():
            self.load_versions()

    def _on_edit_version(self):
        sel = self._get_selected_version()
        if not sel:
            return
        vid, _ = sel
        dlg = DevVersionDialog(self.tracker, version_id=vid, parent=self)
        if dlg.exec():
            self.load_versions()

    def _on_release_version(self):
        sel = self._get_selected_version()
        if not sel:
            return
        _, vcode = sel
        dlg = DevReleaseDialog(self.tracker, version_code=vcode, parent=self)
        if dlg.exec():
            self.load_versions()

    def _on_delete_version(self):
        sel = self._get_selected_version()
        if not sel:
            return
        vid, vcode = sel
        if onay(self, "Sürüm Silme Onayı", f"'{vcode}' sürümünü silmek istediğinize emin misiniz?"):
            self.tracker.surum_sil(vid)
            self.load_versions()


class DevAssignVersionDialog(QDialog):
    """Seçili geliştirme kayıtlarını bir sürüme atama penceresi."""

    def __init__(self, tracker: DevTracker, selected_count: int, parent=None) -> None:
        super().__init__(parent)
        self.tracker = tracker
        self.selected_count = selected_count
        self.setWindowTitle("📦 Sürüme Ata")
        self.setMinimumWidth(380)
        apply_light_dialog_style(self)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        lbl = QLabel(f"Seçili <b>{self.selected_count}</b> adet geliştirme kaydı hangi sürüme dahil edilsin?")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        self.cmb_surum = QComboBox()
        self.cmb_surum.setEditable(True)
        self.cmb_surum.setStyleSheet(_COMBO_STYLE)
        self.cmb_surum.addItem("-- Sürümden Çıkar (Atanmamış) --", "")

        for v in self.tracker.surum_liste():
            self.cmb_surum.addItem(f"{v['version_code']} — {v['title']}", v["version_code"])

        layout.addWidget(self.cmb_surum)

        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_save = QPushButton("💾 Sürüme Ata")
        self.btn_save.setDefault(True)
        self.btn_cancel = QPushButton("✖ Vazgeç")
        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        bar.addWidget(self.btn_save)
        bar.addWidget(self.btn_cancel)
        layout.addLayout(bar)

    def get_version_code(self) -> str | None:
        data = self.cmb_surum.currentData()
        if data is not None:
            return data if data != "" else None
        txt = self.cmb_surum.currentText().strip()
        return txt if txt else None
