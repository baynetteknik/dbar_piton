"""
TOYA ERP - StokHareketDialog

Bir stok kartının `stock_movements` kayıtlarını salt-okunur listeler.
Stok kartındaki "📊 Stok Hareketleri" aksiyonundan açılır.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from sqlalchemy import select

from src.core.models import Product, StockMovement

logger = logging.getLogger(__name__)

_TYPE_TR = {
    "sale": "Satış (Çıkış)", "purchase": "Alış (Giriş)",
    "adjustment": "Düzeltme", "sync": "Senkron", "transfer": "Transfer",
    "count": "Sayım", "return": "İade",
}


class StokHareketDialog(QDialog):
    def __init__(self, db_session=None, product_id: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.setWindowTitle("Stok Hareketleri")
        self.setModal(True)
        self.resize(620, 460)

        lyt = QVBoxLayout(self)
        lyt.setContentsMargins(14, 12, 14, 12)
        lyt.setSpacing(10)

        title = QLabel("Stok Hareketleri")
        if self.db and product_id:
            p = self.db.get(Product, product_id)
            if p:
                title.setText(
                    f"Stok Hareketleri — {p.sku or ''} {p.name or ''}  "
                    f"(Mevcut: {p.stock or 0} {p.unit or ''})",
                )
        title.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(title)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Tarih", "Tür", "Miktar"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lyt.addWidget(self.table, 1)

        self.lbl_empty = QLabel("Bu ürün için stok hareketi bulunmuyor.")
        self.lbl_empty.setStyleSheet("color:#94a3b8; font-size:11px;")
        lyt.addWidget(self.lbl_empty)

        self._load(product_id)

    def _load(self, product_id: int | None) -> None:
        if not (self.db and product_id):
            return
        try:
            rows = self.db.scalars(
                select(StockMovement).where(
                    StockMovement.product_id == product_id,
                ).order_by(StockMovement.created_at.desc()),
            ).all()
        except Exception:  # noqa: BLE001
            logger.exception("Stok hareketleri yüklenemedi")
            rows = []

        self.lbl_empty.setVisible(not rows)
        for m in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(
                r, 0,
                QTableWidgetItem(m.created_at.strftime("%d.%m.%Y %H:%M") if m.created_at else ""),
            )
            self.table.setItem(r, 1, QTableWidgetItem(_TYPE_TR.get(m.movement_type, m.movement_type or "")))
            qty_item = QTableWidgetItem(str(m.quantity))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(r, 2, qty_item)
