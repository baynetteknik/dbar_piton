"""TOYA ERP - BackupRestoreHistoryDialog: geri yükleme tarihçesi (ne zaman/hangi yedekten). Kayıtlar silinmez, yalnızca listelenir."""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QTableWidgetItem, QVBoxLayout

from src.desktop.core.grid_presets import GRID_PRESETS, register_preset
from src.desktop.services import sync_log_service
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.components.dialog_style import apply_light_dialog_style

PRESET_ID = "dbgrid_backup_geri_yukleme"
_EYLEM = {"stage": "Geri yükleme hazırlandı", "cancel": "Geri yükleme iptal edildi", "extract": "Dosyalar klasöre çıkarıldı"}


class BackupRestoreHistoryDialog(QDialog):
    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📜 Geri Yükleme Geçmişi")
        self.setMinimumSize(820, 420)
        apply_light_dialog_style(self)
        if PRESET_ID not in GRID_PRESETS:
            register_preset(PRESET_ID, ["TARİH", "İŞ", "İŞLEM", "YEDEK DOSYASI", "DURUM", "AÇIKLAMA"], [0.14, 0.14, 0.17, 0.2, 0.08, 0.27],
                            ["C", "L", "L", "L", "L", "L"], name="Geri Yükleme Geçmişi")
        lyt = QVBoxLayout(self)
        self.lbl = QLabel()
        lyt.addWidget(self.lbl)
        self.grid = AppGrid(PRESET_ID)
        self.grid.enable_layout_persistence(db)
        lyt.addWidget(self.grid, 1)
        b = QPushButton("Kapat")
        b.clicked.connect(self.accept)
        lyt.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
        rows = [r for r in sync_log_service.recent(db, 500, source="backup") if r.direction == sync_log_service.DIR_BACKUP_RESTORE]
        self.lbl.setText(f"{len(rows)} kayıt (silinmez; en yeni üstte).")
        for log in rows:
            try:
                c = json.loads(log.counts_json or "{}")
            except ValueError:
                c = {}
            r = self.grid.rowCount()
            self.grid.insertRow(r)
            self.grid.setRowHeight(r, self.grid.effective_row_height)
            vals = [log.created_at.strftime("%d.%m.%Y %H:%M") if log.created_at else "", c.get("job", ""), _EYLEM.get(c.get("action"), c.get("action", "")),
                    c.get("file", ""), "✔ Başarılı" if log.status == "ok" else "✘ Hata", log.message or ""]
            for i, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setToolTip(str(v))
                self.grid.setItem(r, i, it)
