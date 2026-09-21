"""TOYA ERP - StokHareketDialog: bir stok kartının tüm hareketleri (fiş defteri + eski kayıtlar) ve depo dağılımı.

Stok kartındaki "📊 Stok Hareketleri" aksiyonundan açılır. Yeni stok fişleri, kart düzeltmeleri ve eski `stock_movements`
kayıtları tek listede, yeniden eskiye görünür. Bir fiş satırına çift tıklayınca fiş açılır (değiştirilebilir). Depo
dağılımı ve depoya atanmamış miktar üstte özetlenir. Sütunlar sürükle-bırak ile taşınır ve kaydedilir."""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem, QVBoxLayout

from src.core.models import Product
from src.desktop.core.grid_presets import GRID_PRESETS, register_preset
from src.desktop.services.stok_fis_service import depo_dagilimi, urun_hareketleri
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.widgets.money_edit import bicimle

logger = logging.getLogger(__name__)

PRESET_ID = "dbgrid_stok_kart_hareket"
_LABELS = ["TARİH", "FİŞ NO", "TÜR", "DEPO", "HEDEF", "MİKTAR", "BİRİM", "B.FİYAT", "TUTAR", "ETKİ", "KAYNAK"]
_W = [0.12, 0.08, 0.15, 0.06, 0.06, 0.09, 0.06, 0.09, 0.10, 0.09, 0.10]
_HIZA = ["C", "C", "L", "C", "C", "R", "C", "R", "R", "R", "C"]
C_FISNO = 1


class StokHareketDialog(QDialog):
    def __init__(self, db_session=None, product_id: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.product_id = product_id
        self._hareketler: list[dict] = []
        self.setWindowTitle("Stok Hareketleri")
        self.setWindowState(Qt.WindowState.WindowMaximized)          # ekran standardı: ekranı kaplayarak açılır
        apply_light_dialog_style(self)
        if PRESET_ID not in GRID_PRESETS:
            register_preset(PRESET_ID, _LABELS, _W, _HIZA, name="Stok Kartı Hareketleri")

        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(14, 12, 14, 12)
        lyt.setSpacing(8)
        self.lbl_baslik = QLabel("Stok Hareketleri")
        self.lbl_baslik.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(self.lbl_baslik)
        self.lbl_dagilim = QLabel("")
        self.lbl_dagilim.setStyleSheet("font-size:11px; color:#334155;")
        self.lbl_dagilim.setWordWrap(True)
        lyt.addWidget(self.lbl_dagilim)

        self.grid = AppGrid(PRESET_ID)
        if db_session is not None:
            self.grid.enable_layout_persistence(db_session)
        self.grid.cellDoubleClicked.connect(self._satir_ac)
        lyt.addWidget(self.grid, 1)

        self.lbl_bos = QLabel("Bu ürün için stok hareketi bulunmuyor.")
        self.lbl_bos.setStyleSheet("color:#94a3b8; font-size:11px;")
        lyt.addWidget(self.lbl_bos)
        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton("Kapat")
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lyt.addLayout(row)
        self._load(product_id)

    def _load(self, product_id: int | None) -> None:
        if not (self.db and product_id):
            self.lbl_bos.setVisible(True)
            return
        p = self.db.get(Product, product_id)
        try:
            self._hareketler = urun_hareketleri(self.db, product_id)
            dag = depo_dagilimi(self.db, product_id)
        except Exception:  # noqa: BLE001
            logger.exception("Stok hareketleri yüklenemedi")
            self._hareketler, dag = [], {"depolar": [], "atanmamis": 0, "toplam": 0}
        if p:
            self.lbl_baslik.setText(f"Stok Hareketleri — {p.sku or ''} {p.name or ''}  (Mevcut: {dag['toplam']} {p.unit or ''})")
        parcalar = [f"<b>{kod}</b>: {bicimle(b, 3).rstrip('0').rstrip(',') or '0'}" for kod, _ad, b in dag["depolar"]]
        if abs(float(dag["atanmamis"])) > 1e-9:
            parcalar.append(f"<span style='color:#ea580c'>depoya atanmamış: <b>{dag['atanmamis']}</b></span>")
        self.lbl_dagilim.setText("Depo dağılımı: " + " · ".join(parcalar) if parcalar else "Depo dağılımı: —")

        self.lbl_bos.setVisible(not self._hareketler)
        g = self.grid
        g.setRowCount(0)
        for h in self._hareketler:
            r = g.rowCount()
            g.insertRow(r)
            g.setRowHeight(r, g.effective_row_height)
            etki = h["etki"]
            hucreler = [h["tarih"].strftime("%d.%m.%Y %H:%M") if h["tarih"] else "", h["fis_no"], h["tur"], h["depo"], h["hedef"],
                        bicimle(h["miktar"], 3), h["birim"], bicimle(h["fiyat"], 2) if h["fiyat"] else "",
                        bicimle(h["tutar"], 2) if h["tutar"] else "", ("+" if etki > 0 else "") + bicimle(etki, 3) if etki else "0",
                        h["kaynak"]]
            for c, t in enumerate(hucreler):
                it = QTableWidgetItem(t)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                it.setTextAlignment({"L": Qt.AlignmentFlag.AlignLeft, "R": Qt.AlignmentFlag.AlignRight,
                                     "C": Qt.AlignmentFlag.AlignCenter}[_HIZA[c]] | Qt.AlignmentFlag.AlignVCenter)
                if c == 9:
                    it.setForeground(QBrush(QColor("#16a34a" if etki > 0 else "#dc2626" if etki < 0 else "#64748b")))
                g.setItem(r, c, it)

    def _satir_ac(self, r: int, _c: int) -> None:
        """Fiş satırına çift tıklayınca fişi açar; kayıt değiştiyse liste yenilenir."""
        if r < 0 or r >= len(self._hareketler) or not self._hareketler[r]["fis_id"]:
            return
        from src.desktop.ui.widgets.stok_fis_dialog import StokFisDialog
        if StokFisDialog(self.db, fis_id=self._hareketler[r]["fis_id"], parent=self).exec():
            self._load(self.product_id)
