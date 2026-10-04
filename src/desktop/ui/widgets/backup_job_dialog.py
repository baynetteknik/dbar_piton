"""
TOYA ERP - BackupJobDialog

Yedek işi ekleme/düzenleme: Genel • Güvenlik (şifreleme) • Dış Hedefler • Zamanlama • Bildirim.
Gizli bilgiler (şifreleme parolası, hedef parolaları) yalnızca Windows Kimlik Bilgisi Yöneticisi'ne yazılır.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.backup import disk_registry, disk_watch, notify, secrets
from src.desktop.services.backup.models import (
    KIND_FILES,
    KIND_TOYA,
    BackupJob,
    validate,
)
from src.desktop.services.backup.remote_providers import secret_name
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.widgets.backup_target_dialog import TYPES, BackupTargetDialog

_DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

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


def _split(text: str) -> list[str]:
    return [p.strip() for p in text.replace("\n", ",").replace(";", ",").split(",") if p.strip()]


class BackupJobDialog(QDialog):
    def __init__(self, job: BackupJob | None = None, parent=None, db=None) -> None:
        super().__init__(parent)
        self.db = db
        self._disks = disk_registry.DiskStore(db).list() if db is not None else []      # kayıtlı yedek diskleri
        self.job = job or BackupJob(name="")
        self.is_new = job is None
        self._targets: list[dict[str, Any]] = [dict(t) for t in self.job.cloud]
        self._pending_secrets: dict[str, dict[str, Any]] = {}
        self._removed_targets: list[str] = []
        self.setWindowTitle("Yedek İşi" + (" — Yeni" if self.is_new else " — Düzenle"))
        self.setMinimumSize(620, 520)
        apply_light_dialog_style(self)
        self._build()
        self._load()

    # ------------------------------------------------------------------ arayüz
    def _build(self) -> None:
        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self.tabs.addTab(self._tab_general(), "Genel")
        self.tabs.addTab(self._tab_security(), "🔐 Güvenlik")
        self.tabs.addTab(self._tab_targets(), "☁ Dış Hedefler")
        self.tabs.addTab(self._tab_schedule(), "🕒 Zamanlama")
        self.tabs.addTab(self._tab_notify(), "✉ Bildirim")
        row = QHBoxLayout()
        row.addStretch()
        b_cancel, b_ok = QPushButton("Vazgeç"), QPushButton("💾 Kaydet")
        b_cancel.clicked.connect(self.reject)
        b_ok.clicked.connect(self._on_save)
        b_ok.setDefault(True)
        row.addWidget(b_cancel)
        row.addWidget(b_ok)
        root.addLayout(row)

    def _tab_general(self) -> QWidget:
        w, f = QWidget(), QFormLayout()
        w.setLayout(f)
        self.txt_name = QLineEdit()
        self.cmb_kind = QComboBox()
        self.cmb_kind.setStyleSheet(_COMBO_STYLE)
        self.cmb_kind.addItem("💾 TOYA veritabanı (+ isteğe bağlı klasörler)", KIND_TOYA)
        self.cmb_kind.addItem("📁 Dosya / klasör yedeği", KIND_FILES)
        self.lst_sources = QListWidget()
        self.lst_sources.setMaximumHeight(90)
        sb = QHBoxLayout()
        b_dir, b_file, b_rm = QPushButton("Klasör ekle"), QPushButton("Dosya ekle"), QPushButton("Kaldır")
        b_dir.clicked.connect(self._add_dir)
        b_file.clicked.connect(self._add_file)
        b_rm.clicked.connect(lambda: [self.lst_sources.takeItem(self.lst_sources.row(i)) for i in self.lst_sources.selectedItems()])
        for b in (b_dir, b_file, b_rm):
            sb.addWidget(b)
        sbw = QWidget()
        sbw.setLayout(sb)
        sb.setContentsMargins(0, 0, 0, 0)
        self.txt_dest = QLineEdit()
        self.txt_dest.setPlaceholderText(r"D:\Yedekler\Belgeler   (harici disk: {disk:KIMLIK}\Yedek — 💽 Diskten… ile seçin)")
        b_dest = QPushButton("Seç…")
        b_dest.setFixedWidth(70)
        b_dest.clicked.connect(self._pick_dest)
        self.btn_disk = QToolButton()
        self.btn_disk.setText("💽 Diskten…")
        self.btn_disk.setToolTip("Kayıtlı harici diskten hedef seç (sürücü harfi değişse de disk seri numarasıyla bulunur)")
        self.btn_disk.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        dm = QMenu(self.btn_disk)
        for d in self._disks:
            dm.addAction(f"💽 {d.name}", lambda _=False, d=d: self.txt_dest.setText(rf"{{disk:{d.id}}}\TOYA_Yedek"))
        if not self._disks:
            dm.addAction("(Kayıtlı disk yok — Yedekleme Merkezi › Yedek Diskleri)").setEnabled(False)
        self.btn_disk.setMenu(dm)
        dl = QHBoxLayout()
        dl.addWidget(self.txt_dest)
        dl.addWidget(self.btn_disk)
        dl.addWidget(b_dest)
        dw = QWidget()
        dw.setLayout(dl)
        dl.setContentsMargins(0, 0, 0, 0)
        self.cmb_fmt = QComboBox()
        self.cmb_fmt.setStyleSheet(_COMBO_STYLE)
        self.cmb_fmt.addItem("ZIP arşivi", "zip")
        self.cmb_fmt.addItem("TAR.GZ arşivi", "tar")
        self.cmb_fmt.addItem("Klasör senkronu (arşivsiz, silmez)", "mirror")
        self.cmb_mode = QComboBox()
        self.cmb_mode.setStyleSheet(_COMBO_STYLE)
        self.cmb_mode.addItem("Tam yedek", "full")
        self.cmb_mode.addItem("Artımlı (son yedekten beri değişenler)", "incremental")
        self.txt_inc = QLineEdit()
        self.txt_inc.setPlaceholderText("*.pdf, *.xlsx   (boş = hepsi)")
        self.txt_exc = QLineEdit()
        self.txt_exc.setPlaceholderText("*.tmp, node_modules, ~*")
        self.spn_keep = QSpinBox()
        self.spn_keep.setRange(1, 999)
        self.spn_keep.setSuffix("  yedek sakla")
        f.addRow("İş adı", self.txt_name)
        f.addRow("Tür", self.cmb_kind)
        f.addRow("Kaynaklar", self.lst_sources)
        f.addRow("", sbw)
        f.addRow("Hedef klasör", dw)
        f.addRow("Biçim", self.cmb_fmt)
        f.addRow("Mod", self.cmb_mode)
        f.addRow("Dahil et", self.txt_inc)
        f.addRow("Hariç tut", self.txt_exc)
        f.addRow("Saklama", self.spn_keep)
        self.cmb_kind.currentIndexChanged.connect(self._sync_general)
        self.cmb_fmt.currentIndexChanged.connect(self._sync_general)
        return w

    def _tab_security(self) -> QWidget:
        w, v = QWidget(), QVBoxLayout()
        w.setLayout(v)
        self.chk_encrypt = QCheckBox("Yedeği parolayla şifrele (AES-256-GCM)")
        self.lbl_pw = QLabel()
        b_pw = QPushButton("🔑 Şifreleme parolasını belirle / değiştir…")
        b_pw.clicked.connect(self._set_password)
        warn = QLabel("⚠ Parolayı kaybederseniz şifreli yedekler HİÇBİR ŞEKİLDE açılamaz. Parola yalnızca bu bilgisayarın "
                      "Windows Kimlik Bilgisi Yöneticisi'nde saklanır; başka bilgisayarda geri yüklemek için parolayı güvenli bir yere yazın. "
                      "Parola tüm şifreli işler için ortaktır.")
        warn.setWordWrap(True)
        warn.setStyleSheet("color:#b45309; font-size:11px;")
        for x in (self.chk_encrypt, self.lbl_pw, b_pw, warn):
            v.addWidget(x)
        v.addStretch()
        return w

    def _tab_targets(self) -> QWidget:
        w, v = QWidget(), QVBoxLayout()
        w.setLayout(v)
        v.addWidget(QLabel("Yedek yerelde alındıktan sonra bu hedeflere de gönderilir (hata olursa 4 kez yeniden denenir):"))
        self.lst_targets = QListWidget()
        v.addWidget(self.lst_targets)
        r = QHBoxLayout()
        b_add, b_edit, b_rm = QPushButton("➕ Ekle"), QPushButton("✏️ Düzenle"), QPushButton("Kaldır")
        b_add.clicked.connect(self._add_target)
        b_edit.clicked.connect(self._edit_target)
        b_rm.clicked.connect(self._remove_target)
        for b in (b_add, b_edit, b_rm):
            r.addWidget(b)
        r.addStretch()
        v.addLayout(r)
        self.lbl_mirror_note = QLabel("Klasör senkronu biçiminde dış hedef ve şifreleme kullanılamaz.")
        self.lbl_mirror_note.setStyleSheet("color:#64748b; font-size:11px;")
        v.addWidget(self.lbl_mirror_note)
        return w

    def _tab_schedule(self) -> QWidget:
        w, f = QWidget(), QFormLayout()
        w.setLayout(f)
        self.cmb_sched = QComboBox()
        self.cmb_sched.setStyleSheet(_COMBO_STYLE)
        for k, label in (("manual", "Elle çalıştır"), ("daily", "Her gün"), ("weekly", "Haftalık"),
                         ("interval", "Belirli aralıkla"), ("disk", "Harici disk takılınca")):
            self.cmb_sched.addItem(label, k)
        self.tm = QTimeEdit(QTime(2, 0))
        self.tm.setDisplayFormat("HH:mm")
        days = QHBoxLayout()
        self.chk_days = [QCheckBox(d) for d in _DAYS]
        for c in self.chk_days:
            days.addWidget(c)
        self.days_w = QWidget()
        self.days_w.setLayout(days)
        days.setContentsMargins(0, 0, 0, 0)
        self.spn_int = QSpinBox()
        self.spn_int.setRange(5, 1440)
        self.spn_int.setValue(60)
        self.spn_int.setSuffix(" dk")
        self.cmb_disk = QComboBox()
        self.cmb_disk.setEditable(True)
        self.cmb_disk.setStyleSheet(_COMBO_STYLE)
        for d in self._disks:                              # kayıtlı diskler (seri numarasıyla tanınır)
            self.cmb_disk.addItem(f"💽 {d.name}", d.id)
        for v in disk_watch.list_volumes():                # kayıtsız: eski usul etiketle eşleşir
            self.cmb_disk.addItem(v.label or v.root, None)
        self.lbl_sched_help = QLabel()
        self.lbl_sched_help.setWordWrap(True)
        self.lbl_sched_help.setStyleSheet("color:#64748b; font-size:11px;")
        self.chk_enabled = QCheckBox("İş etkin")
        f.addRow("Zamanlama", self.cmb_sched)
        f.addRow("Saat", self.tm)
        f.addRow("Günler", self.days_w)
        f.addRow("Aralık", self.spn_int)
        f.addRow("Harici disk", self.cmb_disk)
        f.addRow("", self.lbl_sched_help)
        f.addRow("", self.chk_enabled)
        self._sched_rows = {"daily": [self.tm], "weekly": [self.tm, self.days_w], "interval": [self.spn_int], "disk": [self.cmb_disk]}
        self._sched_labels = {id(x): f.labelForField(x) for x in (self.tm, self.days_w, self.spn_int, self.cmb_disk)}
        self.cmb_sched.currentIndexChanged.connect(self._sync_schedule)
        return w

    def _tab_notify(self) -> QWidget:
        w, v = QWidget(), QVBoxLayout()
        w.setLayout(v)
        v.addWidget(QLabel("<b>Hangi sonuçlarda bildirim gönderilsin?</b> (birden fazla seçebilirsiniz)"))
        self.chk_events = {k: QCheckBox(t) for k, t in notify.EVENTS.items()}
        for c in self.chk_events.values():
            v.addWidget(c)
        v.addSpacing(6)
        v.addWidget(QLabel("<b>Bildirim kanalları</b>"))
        self.chk_channels = {k: QCheckBox(t) for k, t in notify.CHANNELS.items()}
        for c in self.chk_channels.values():
            v.addWidget(c)
        f = QFormLayout()
        self.txt_to = QLineEdit()
        self.txt_to.setPlaceholderText("alici@firma.com   (boş = SMTP gönderen adresi)")
        f.addRow("E-posta alıcısı", self.txt_to)
        v.addLayout(f)
        v.addWidget(QLabel("SMTP ayarları Genel Ayarlar → E-Posta / SMTP'den alınır. Uygulama içi bildirim yedekleme ekranında görünür."))
        v.addStretch()
        return w

    # ------------------------------------------------------------------ yükleme
    def _load(self) -> None:
        j = self.job
        self.txt_name.setText(j.name)
        self.cmb_kind.setCurrentIndex(max(0, self.cmb_kind.findData(j.kind)))
        self.lst_sources.addItems([s for s in j.sources if s.strip()])
        self.txt_dest.setText(j.dest_dir)
        self.cmb_fmt.setCurrentIndex(max(0, self.cmb_fmt.findData(j.fmt)))
        self.cmb_mode.setCurrentIndex(max(0, self.cmb_mode.findData(j.mode)))
        self.txt_inc.setText(", ".join(j.includes))
        self.txt_exc.setText(", ".join(j.excludes))
        self.spn_keep.setValue(j.keep)
        self.chk_encrypt.setChecked(j.encrypt)
        s = j.schedule
        self.cmb_sched.setCurrentIndex(max(0, self.cmb_sched.findData(s.get("type", "manual"))))
        if s.get("time"):
            self.tm.setTime(QTime.fromString(str(s["time"]), "HH:mm"))
        for i, c in enumerate(self.chk_days):
            c.setChecked(i in [int(d) for d in s.get("weekdays", [])])
        self.spn_int.setValue(int(s.get("interval_minutes", 60) or 60))
        if s.get("disk_id") and self.cmb_disk.findData(s["disk_id"]) >= 0:
            self.cmb_disk.setCurrentIndex(self.cmb_disk.findData(s["disk_id"]))
        else:
            self.cmb_disk.setCurrentText(str(s.get("disk_label", "")))
        self.chk_enabled.setChecked(j.enabled)
        evs, chs = notify.events_of(j.notify), notify.channels_of(j.notify)
        for k, c in self.chk_events.items():
            c.setChecked(k in evs)
        for k, c in self.chk_channels.items():
            c.setChecked(k in chs)
        self.txt_to.setText(j.notify.get("to", ""))
        self._refresh_targets()
        self._refresh_pw()
        self._sync_general()
        self._sync_schedule()

    def _sync_general(self) -> None:
        toya = self.cmb_kind.currentData() == KIND_TOYA
        mirror = self.cmb_fmt.currentData() == "mirror"
        if toya and mirror:
            self.cmb_fmt.setCurrentIndex(0)
            mirror = False
        self.cmb_fmt.model().item(2).setEnabled(not toya)
        self.cmb_mode.setEnabled(not toya and not mirror)
        if toya or mirror:
            self.cmb_mode.setCurrentIndex(0)
        self.chk_encrypt.setEnabled(not mirror)
        if mirror:
            self.chk_encrypt.setChecked(False)
        self.lst_targets.setEnabled(not mirror)
        self.lbl_mirror_note.setVisible(mirror)

    def _sync_schedule(self) -> None:
        k = self.cmb_sched.currentData()
        shown = {id(w) for w in self._sched_rows.get(k, [])}
        for w in (self.tm, self.days_w, self.spn_int, self.cmb_disk):
            w.setVisible(id(w) in shown)
            lab = self._sched_labels.get(id(w))
            if lab:
                lab.setVisible(id(w) in shown)
        self.lbl_sched_help.setText({
            "manual": "Yalnızca 'Şimdi Çalıştır' ile.",
            "daily": "Bilgisayar o saatte kapalıysa açıldığında bir kez telafi edilir. Başarısız olursa 30 dk sonra en çok 3 kez denenir.",
            "weekly": "Seçili günlerde, belirtilen saatte.",
            "interval": "Son denemeden bu kadar süre geçince.",
            "disk": "Seçilen disk takılınca çalışır. Kayıtlı disk (💽) seri numarasıyla tanınır; hedef klasörü '💽 Diskten…' ile seçin. "
                    "Kayıtsız etiket yazarsanız yalnız etiketle eşleşir ('{disk}\\Yedek').",
        }[k])

    def _refresh_targets(self) -> None:
        self.lst_targets.clear()
        names = dict(TYPES)
        for t in self._targets:
            ek = f"  →  {t['folder_path']}" if t.get("type") == "gdrive" and t.get("folder_path") else ""
            self.lst_targets.addItem(f"{names.get(t.get('type'), t.get('type'))} — {t.get('label', '')}{ek}")

    def _refresh_pw(self) -> None:
        has = bool(secrets.encryption_password())
        self.lbl_pw.setText("Parola durumu: " + ("✔ tanımlı" if has else "✘ tanımlı değil (şifreli yedek alınamaz)"))

    # ------------------------------------------------------------------ eylemler
    def _add_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Kaynak klasör")
        if d:
            self.lst_sources.addItem(d)

    def _add_file(self) -> None:
        f, _ = QFileDialog.getOpenFileName(self, "Kaynak dosya")
        if f:
            self.lst_sources.addItem(f)

    def _pick_dest(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Hedef klasör")
        if d:
            self.txt_dest.setText(d)

    def _set_password(self) -> None:
        pw, ok = QInputDialog.getText(self, "Şifreleme parolası", "Yeni parola (en az 8 karakter):", QLineEdit.EchoMode.Password)
        if not ok:
            return
        if len(pw) < 8:
            QMessageBox.warning(self, "Parola", "Parola en az 8 karakter olmalı.")
            return
        again, ok2 = QInputDialog.getText(self, "Şifreleme parolası", "Parolayı tekrar girin:", QLineEdit.EchoMode.Password)
        if not ok2 or again != pw:
            QMessageBox.warning(self, "Parola", "Parolalar aynı değil; değiştirilmedi.")
            return
        if secrets.encryption_password() and QMessageBox.question(
                self, "Parola değişiyor", "Mevcut parola değişecek. Eski parolayla şifrelenmiş yedekler yeni parolayla AÇILMAZ; "
                "eski parolayı saklayın. Devam edilsin mi?", defaultButton=QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            secrets.set_secret(secrets.KEY_ENCRYPTION, pw)
        except secrets.SecretStoreError as exc:
            QMessageBox.critical(self, "Parola", f"Parola kaydedilemedi: {exc}")
            return
        self._refresh_pw()

    def _add_target(self) -> None:
        dlg = BackupTargetDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg, sec = dlg.values()
            self._targets.append(cfg)
            self._pending_secrets[cfg["id"]] = sec
            self._refresh_targets()

    def _edit_target(self) -> None:
        i = self.lst_targets.currentRow()
        if i < 0:
            return
        t = self._targets[i]
        existing = self._pending_secrets.get(t["id"]) or secrets.get_json(secret_name(self.job.id, t["id"]))
        dlg = BackupTargetDialog(t, existing, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cfg, sec = dlg.values()
            self._targets[i] = cfg
            self._pending_secrets[cfg["id"]] = sec
            self._refresh_targets()

    def _remove_target(self) -> None:
        i = self.lst_targets.currentRow()
        if i >= 0:
            t = self._targets.pop(i)
            self._removed_targets.append(t["id"])
            self._pending_secrets.pop(t["id"], None)
            self._refresh_targets()

    # ------------------------------------------------------------------ sonuç
    def build_job(self) -> BackupJob:
        j = self.job
        st = self.cmb_sched.currentData()
        sched: dict[str, Any] = {"type": st}
        if st in ("daily", "weekly"):
            sched["time"] = self.tm.time().toString("HH:mm")
        if st == "weekly":
            sched["weekdays"] = [i for i, c in enumerate(self.chk_days) if c.isChecked()]
        if st == "interval":
            sched["interval_minutes"] = self.spn_int.value()
        if st == "disk":
            idx = self.cmb_disk.currentIndex()
            did = self.cmb_disk.itemData(idx) if (idx >= 0 and self.cmb_disk.currentText() == self.cmb_disk.itemText(idx)) else None
            reg = next((d for d in self._disks if d.id == did), None)
            if reg:
                sched.update(disk_id=reg.id, disk_name=reg.name, disk_label=reg.label)
            else:
                sched["disk_label"] = self.cmb_disk.currentText().strip()
        return BackupJob(
            name=self.txt_name.text().strip(), kind=self.cmb_kind.currentData(), dest_dir=self.txt_dest.text().strip(),
            sources=[self.lst_sources.item(i).text() for i in range(self.lst_sources.count())], fmt=self.cmb_fmt.currentData(),
            mode=self.cmb_mode.currentData(), includes=_split(self.txt_inc.text()), excludes=_split(self.txt_exc.text()),
            keep=self.spn_keep.value(), encrypt=self.chk_encrypt.isChecked(), cloud=list(self._targets), schedule=sched,
            notify=self._notify_dict(),
            enabled=self.chk_enabled.isChecked(), hidden=False, id=j.id, state=dict(j.state),
        )

    def _notify_dict(self) -> dict[str, Any]:
        events = [k for k, c in self.chk_events.items() if c.isChecked()]
        channels = [k for k, c in self.chk_channels.items() if c.isChecked()]
        mode = "never" if not events else "always" if len(events) == len(notify.EVENTS) else "failure"    # eski okuyucular için türetilir
        return {"events": events, "channels": channels, "mode": mode, "to": self.txt_to.text().strip()}

    def _on_save(self) -> None:
        job = self.build_job()
        err = validate(job)
        if err:
            QMessageBox.warning(self, "Yedek İşi", err)
            return
        if job.encrypt and not secrets.encryption_password():
            QMessageBox.warning(self, "Yedek İşi", "Şifreleme için önce Güvenlik sekmesinden parola belirleyin.")
            self.tabs.setCurrentIndex(1)
            return
        try:
            for tid, sec in self._pending_secrets.items():
                secrets.set_json(secret_name(job.id, tid), sec)
            for tid in self._removed_targets:
                secrets.delete_secret(secret_name(job.id, tid))
        except secrets.SecretStoreError as exc:
            QMessageBox.critical(self, "Yedek İşi", f"Gizli bilgiler kaydedilemedi: {exc}")
            return
        self.job = job
        self.accept()
