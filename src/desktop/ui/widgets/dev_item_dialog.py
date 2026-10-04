"""TOYA ERP - DevItemDialog: geliştirme kaydı (öneri / yapılacak / hata) penceresi + değişiklik geçmişi. Yalnız geliştirme yapılarında kullanılır."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.services.dev_tracker_store import (
    DURUMLAR,
    ONCELIKLER,
    TURLER,
    DevTracker,
    DevTrackerError,
)
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.components.entry_table_view import standart_grid

PRESET_ID = "dbgrid_dev_gecmis"


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

class DevItemDialog(QDialog):
    def __init__(self, tracker: DevTracker, item_id: int | None = None, kim: str = "", varsayilan: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.tracker, self.item_id, self.kim = tracker, item_id, kim
        self.setWindowTitle("Geliştirme Kaydı")
        self.setMinimumWidth(620)
        apply_light_dialog_style(self)
        f = QFormLayout()
        self.cmb_tur, self.cmb_durum, self.cmb_oncelik = QComboBox(), QComboBox(), QComboBox()
        for c, d in ((self.cmb_tur, TURLER), (self.cmb_durum, DURUMLAR), (self.cmb_oncelik, ONCELIKLER)):
            c.setStyleSheet(_COMBO_STYLE)
            for k, e in d.items():
                c.addItem(e, k)
        self.cmb_oncelik.setCurrentIndex(self.cmb_oncelik.findData(2))
        self.txt_baslik, self.txt_modul, self.txt_commit, self.txt_ekleyen = (QLineEdit() for _ in range(4))
        self.txt_modul.setPlaceholderText("ör. Kasa, Yedekleme, Görevler")
        self.cmb_surum = QComboBox()
        self.cmb_surum.setEditable(True)
        self.cmb_surum.setStyleSheet(_COMBO_STYLE)
        self.cmb_surum.addItem("", None)
        for s in self.tracker.surumler():
            self.cmb_surum.addItem(s, s)
        self.txt_aciklama = QPlainTextEdit()
        self.txt_aciklama.setFixedHeight(110)
        f.addRow("Tür", self.cmb_tur)
        f.addRow("Başlık *", self.txt_baslik)
        f.addRow("Modül", self.txt_modul)
        f.addRow("Öncelik / Durum", self._yan(self.cmb_oncelik, self.cmb_durum))
        f.addRow("Ekleyen", self.txt_ekleyen)
        f.addRow("Sürüm / Commit", self._yan(self.cmb_surum, self.txt_commit))
        f.addRow("Açıklama", self.txt_aciklama)
        lyt = QVBoxLayout(self)
        lyt.addLayout(f)
        self.lbl_hata = QLabel("")
        self.lbl_hata.setStyleSheet("color:#dc2626; font-weight:600;")
        lyt.addWidget(self.lbl_hata)
        self.grid = None
        if item_id:
            lyt.addWidget(QLabel("<b>Değişiklik geçmişi</b>"))
            self.entry = standart_grid(PRESET_ID, [
                ("zaman", "ZAMAN"), ("kim", "KİM"), ("alan", "ALAN"), ("eski", "ESKİ"), ("yeni", "YENİ"),
            ])
            self.grid = self.entry.table_view
            self.entry.setMaximumHeight(170)
            lyt.addWidget(self.entry)
            self._yukle(tracker.getir(item_id))
            self._gecmis()
        else:
            v = varsayilan or {}
            self.cmb_tur.setCurrentIndex(max(self.cmb_tur.findData(v.get("tur", "oneri")), 0))
            self.txt_ekleyen.setText(v.get("ekleyen", kim))
            self.txt_modul.setText(v.get("modul", ""))
        bar = QHBoxLayout()
        bar.addStretch()
        b_kaydet, b_iptal = QPushButton("💾 Kaydet"), QPushButton("✖ Vazgeç")
        b_kaydet.setDefault(True)
        bar.addWidget(b_kaydet)
        bar.addWidget(b_iptal)
        lyt.addLayout(bar)
        b_kaydet.clicked.connect(self.kaydet)
        b_iptal.clicked.connect(self.reject)

    @staticmethod
    def _yan(*widgets) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            h.addWidget(w, 1)
        return h

    def _yukle(self, r: dict) -> None:
        self.cmb_tur.setCurrentIndex(max(self.cmb_tur.findData(r["tur"]), 0))
        self.cmb_durum.setCurrentIndex(max(self.cmb_durum.findData(r["durum"]), 0))
        self.cmb_oncelik.setCurrentIndex(max(self.cmb_oncelik.findData(r["oncelik"]), 0))
        self.txt_baslik.setText(r["baslik"])
        self.txt_modul.setText(r["modul"] or "")
        self.txt_commit.setText(r["commit_hash"] or "")
        s_val = r.get("surum") or ""
        s_idx = self.cmb_surum.findData(s_val)
        if s_idx >= 0:
            self.cmb_surum.setCurrentIndex(s_idx)
        else:
            self.cmb_surum.setCurrentText(s_val)
        self.txt_ekleyen.setText(r["ekleyen"] or "")
        self.txt_aciklama.setPlainText(r["aciklama"] or "")

    def _gecmis(self) -> None:
        g = self.grid
        g.setRowCount(0)
        for h in self.tracker.gecmis(self.item_id):
            r = g.rowCount()
            g.insertRow(r)
            g.setRowHeight(r, g.effective_row_height)
            for c, t in enumerate([h["zaman"], h["kim"] or "", h["alan"], h["eski"] or "", h["yeni"] or ""]):
                item = QStandardItem(str(t))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setTextAlignment((Qt.AlignmentFlag.AlignCenter if c == 0 else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
                g.setItem(r, c, item)

    def degerler(self) -> dict:
        surum_txt = self.cmb_surum.currentData() if self.cmb_surum.currentData() is not None else self.cmb_surum.currentText()
        surum_val = str(surum_txt).strip() if surum_txt else None
        return {"tur": self.cmb_tur.currentData(), "baslik": self.txt_baslik.text(), "modul": self.txt_modul.text().strip() or None,
                "oncelik": self.cmb_oncelik.currentData(), "durum": self.cmb_durum.currentData(), "ekleyen": self.txt_ekleyen.text().strip() or None,
                "surum": surum_val, "commit_hash": self.txt_commit.text().strip() or None,
                "aciklama": self.txt_aciklama.toPlainText().strip() or None}

    def kaydet(self) -> None:
        v = self.degerler()
        try:
            if self.item_id:
                self.tracker.guncelle(self.item_id, kim=self.kim, **v)
            else:
                self.item_id = self.tracker.ekle(v.pop("baslik"), kim=self.kim, **v)
        except DevTrackerError as e:
            self.lbl_hata.setText(str(e))
            QMessageBox.warning(self, "Geliştirme Kaydı", str(e))
            return
        self.accept()
