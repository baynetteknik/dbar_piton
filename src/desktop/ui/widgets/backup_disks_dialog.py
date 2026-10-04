"""TOYA ERP - BackupDisksDialog: yedek disklerinin tanımı (seri numarasıyla).

Harici disk bir kez tanıtılır; Windows'un verdiği birim seri numarasıyla kaydedilir. Sürücü harfi (E:, F:) ya da etiket değişse bile
disk tanınır. Yedek işlerinde hedef `{disk:KIMLIK}\\TOYA_Yedek` olarak seçilir ve "disk takılınca çalış" zamanlaması bu kayıtla eşleşir.
Silme yalnızca listeden gizler. Takılı disklerin durumu ve doluluğu gösterilir."""

from __future__ import annotations

import shutil

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.services.backup import disk_registry, disk_watch, history
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.components.entry_table_view import standart_grid

PRESET_ID = "dbgrid_backup_diskler"


class BackupDisksDialog(QDialog):
    def __init__(self, db, parent=None, volumes_provider=None) -> None:
        super().__init__(parent)
        self.db = db
        self.store = disk_registry.DiskStore(db)
        self._volumes = volumes_provider or disk_watch.list_volumes
        self._disks: list[disk_registry.RegisteredDisk] = []
        self.setWindowTitle("💽 Yedek Diskleri")
        self.setMinimumSize(760, 420)
        apply_light_dialog_style(self)
        lyt = QVBoxLayout(self)
        info = QLabel("Harici diskinizi bir kez tanıtın: disk <b>birim seri numarasıyla</b> tanınır, sürücü harfi (E:, F: …) veya "
                      "etiket değişse de yedek işleri o diski bulur. Yedek işinde hedefi <b>💽 Diskten…</b> ile seçin.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#475569;")
        lyt.addWidget(info)
        self.entry = standart_grid(PRESET_ID, [
            ("name", "DİSK ADI"), ("serial", "SERİ NO"), ("label", "ETİKET"),
            ("status", "DURUM"), ("capacity", "KAPASİTE / DOLU"), ("last_seen", "SON GÖRÜLEN"),
        ])
        self.grid = self.entry.table_view
        lyt.addWidget(self.entry, 1)
        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        lyt.addWidget(self.lbl)
        row = QHBoxLayout()
        self.btn_ekle = QPushButton("➕ Takılı Diskten Ekle…")
        self.btn_ad = QPushButton("✏️ Yeniden Adlandır")
        self.btn_sil = QPushButton("🗑️ Listeden Kaldır")
        self.btn_yenile = QPushButton("🔄 Yenile")
        b_kapat = QPushButton("Kapat")
        for b in (self.btn_ekle, self.btn_ad, self.btn_sil, self.btn_yenile):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(b_kapat)
        lyt.addLayout(row)
        self.btn_ekle.clicked.connect(self.ekle)
        self.btn_ad.clicked.connect(self.adlandir)
        self.btn_sil.clicked.connect(self.kaldir)
        self.btn_yenile.clicked.connect(self.yenile)
        b_kapat.clicked.connect(self.accept)
        self.yenile()

    def yenile(self) -> None:
        vols = self._volumes()
        self.store.touch(vols)
        self._disks = self.store.list()
        roots = disk_registry.roots(self._disks, vols)
        g = self.grid
        g.setRowCount(0)
        for d in self._disks:
            r = g.rowCount()
            g.insertRow(r)
            g.setRowHeight(r, g.effective_row_height)
            kok = roots.get(d.id)
            kap = ""
            if kok:
                try:
                    du = shutil.disk_usage(kok)
                    kap = f"{history.format_size(du.used)} / {history.format_size(du.total)}"
                except OSError:
                    pass
            durum = f"✔ Takılı ({kok})" if kok else "✘ Takılı değil"
            for c, t in enumerate((d.name, d.serial or "—", d.label, durum, kap, d.last_seen.replace("T", " ")[:16])):
                it = QStandardItem(t)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                it.setTextAlignment({4: Qt.AlignmentFlag.AlignRight, 1: Qt.AlignmentFlag.AlignCenter, 5: Qt.AlignmentFlag.AlignCenter}.get(
                    c, Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
                g.setItem(r, c, it)
        self.lbl.setText(f"{len(self._disks)} kayıtlı disk." if self._disks else "Henüz kayıtlı disk yok. Diski takıp ➕ Takılı Diskten Ekle'ye basın.")

    def _secili(self) -> disk_registry.RegisteredDisk | None:
        r = self.grid.currentRow() if self.grid.selectedIndexes() else -1
        return self._disks[r] if 0 <= r < len(self._disks) else None

    def ekle(self) -> None:
        kayitli = {d.serial for d in self._disks if d.serial}
        adaylar = [v for v in self._volumes() if v.kind == disk_watch.DRIVE_REMOVABLE or v.serial not in kayitli]
        adaylar = [v for v in adaylar if not (v.serial and v.serial in kayitli)]
        if not adaylar:
            QMessageBox.information(self, "Yedek Diskleri", "Kayıtlı olmayan takılı disk bulunamadı.")
            return
        secenekler = [f"{v.root}  {v.label or '(etiketsiz)'}  — seri {v.serial or '?'}" for v in adaylar]
        secim, ok = QInputDialog.getItem(self, "Takılı Disk", "Hangi disk tanıtılsın?", secenekler, 0, False)
        if not ok:
            return
        v = adaylar[secenekler.index(secim)]
        ad, ok = QInputDialog.getText(self, "Disk Adı", "Bu diske verilecek ad (ör. Yedek Disk 1):", text=v.label or "Yedek Disk")
        if not ok or not ad.strip():
            return
        self.disk_ekle(v, ad)

    def disk_ekle(self, v: disk_watch.Volume, ad: str) -> bool:
        ok, msg = self.store.save(disk_registry.from_volume(ad, v))
        self.yenile()
        self.lbl.setText(msg)
        return ok

    def adlandir(self) -> None:
        d = self._secili()
        if d is None:
            return
        ad, ok = QInputDialog.getText(self, "Yeniden Adlandır", "Yeni ad:", text=d.name)
        if ok and ad.strip():
            d.name = ad.strip()
            ok2, msg = self.store.save(d)
            self.yenile()
            self.lbl.setText(msg)

    def kaldir(self) -> None:
        d = self._secili()
        if d and QMessageBox.question(self, "Yedek Diski", f"'{d.name}' listeden kaldırılsın mı?\n(Diskteki yedekler silinmez; bu diske bağlı işler "
                                                          "'disk takılı değil' uyarısı verir.)") == QMessageBox.StandardButton.Yes:
            self.store.hide(d.id)
            self.yenile()
