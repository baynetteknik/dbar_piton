"""
TOYA ERP - CariEkstreWidget

Bir carinin künyesi + bakiye/risk özeti + o cariye ait belgelerin
(Teklif / Sipariş / Fatura / İrsaliye) salt-okunur listesi.

Not: Gerçek borç/alacak hareket defteri (fatura → bakiye postlama) ayrı bir
tur. Şimdilik belge listesi + `Customer.balance` (saklı değer) gösterilir.

Kullanım:
    w = CariEkstreWidget(db_session=db)
    w.set_customer(customer_id)
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import Customer, Quotation

logger = logging.getLogger(__name__)

_TYPE_TR = {
    "Quotation": "Teklif", "Order": "Sipariş",
    "Invoice": "Fatura", "Waybill": "İrsaliye",
}
_STATUS_TR = {
    "draft": "Taslak", "sent": "Gönderildi", "approved": "Onaylandı",
    "rejected": "Reddedildi", "converted": "Dönüştürüldü", "cancelled": "İptal",
}


def _money(v) -> str:
    try:
        s = f"{float(v or 0):,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "0,00"


class CariEkstreWidget(QWidget):
    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.customer_id: int | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        self.lbl_title = QLabel("Cari Ekstresi")
        self.lbl_title.setStyleSheet("font-size:15px; font-weight:800; color:#1e3a8a;")
        root.addWidget(self.lbl_title)

        stat_row = QHBoxLayout()
        self.lbl_balance = QLabel("Bakiye: —")
        self.lbl_balance.setStyleSheet("font-size:13px; font-weight:700;")
        self.lbl_risk = QLabel("Risk Limiti: —")
        self.lbl_risk.setStyleSheet("font-size:12px; color:#64748b;")
        stat_row.addWidget(self.lbl_balance)
        stat_row.addSpacing(24)
        stat_row.addWidget(self.lbl_risk)
        stat_row.addStretch()
        root.addLayout(stat_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Tarih", "Belge No", "Tür", "Genel Toplam", "Durum"],
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.lbl_empty = QLabel("Bu cariye ait belge bulunmuyor.")
        self.lbl_empty.setStyleSheet("color:#94a3b8; font-size:11px;")
        self.lbl_empty.setVisible(False)
        root.addWidget(self.lbl_empty)

    # ------------------------------------------------------------------
    def set_customer(self, customer_id: int | None) -> None:
        self.customer_id = customer_id
        self.table.setRowCount(0)
        if not (self.db and customer_id):
            self.lbl_title.setText("Cari Ekstresi")
            return

        c = self.db.get(Customer, customer_id)
        if not c:
            return
        self.lbl_title.setText(
            f"Cari Ekstresi — {c.customer_code or ''} {c.fullname or ''}".strip(),
        )
        bal = float(getattr(c, "balance", 0) or 0)
        yon = "Borç" if bal > 0 else ("Alacak" if bal < 0 else "")
        self.lbl_balance.setText(f"Bakiye: {_money(abs(bal))} ₺ {yon}".strip())
        self.lbl_balance.setStyleSheet(
            "font-size:13px; font-weight:700; color:"
            + ("#b91c1c" if bal > 0 else "#15803d" if bal < 0 else "#334155"),
        )
        rl = float(getattr(c, "risk_limit", 0) or 0)
        self.lbl_risk.setText(f"Risk Limiti: {_money(rl)} ₺" if rl else "Risk Limiti: —")

        try:
            rows = self.db.scalars(
                select(Quotation).where(
                    Quotation.customer_id == customer_id,
                    Quotation.is_deleted == False,  # noqa: E712
                ).order_by(Quotation.issue_date.desc().nullslast()),
            ).all()
        except Exception:  # noqa: BLE001
            logger.exception("Cari belgeleri yüklenemedi")
            rows = []

        self.lbl_empty.setVisible(not rows)
        for q in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            dt = q.issue_date or q.date
            cells = [
                dt.strftime("%d.%m.%Y") if dt else "",
                q.quotation_number or "",
                _TYPE_TR.get(q.quotation_type, q.quotation_type or ""),
                _money(q.grand_total),
                _STATUS_TR.get(q.status, q.status or ""),
            ]
            for c_idx, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c_idx == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c_idx, item)
