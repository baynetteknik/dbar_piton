"""
TOYA ERP - KalemAktarDialog

Belge (teklif/sipariş/fatura) detay ekranındaki "📥 Kalemleri Aktar" akışı.
İki kaynak sunar:
  1. Başka Belgeden — mevcut bir Quotation'ın kalemlerini kopyalar.
  2. Stok Listesinden — çoklu ürün seçip miktarıyla kalem üretir.

Kabul edilirse `self.result_lines` DocumentLinesGrid'in beklediği dict listesini tutar.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import Quotation

logger = logging.getLogger(__name__)

_TYPE_TR = {"Quotation": "Teklif", "Order": "Sipariş", "Invoice": "Fatura", "Waybill": "İrsaliye"}


class KalemAktarDialog(QDialog):
    def __init__(self, db_session=None, products: list[dict] | None = None,
                 exclude_doc_id: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self._products = products or []
        self._exclude_doc_id = exclude_doc_id
        self.result_lines: list[dict] = []

        self.setWindowTitle("Kalemleri Aktar")
        self.setModal(True)
        self.resize(680, 480)

        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_doc_tab(), "📄 Başka Belgeden")
        self.tabs.addTab(self._build_product_tab(), "📦 Stok Listesinden")
        root.addWidget(self.tabs, 1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Aktar")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ------------------------------------------------------------------
    def _build_doc_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.addWidget(QLabel("Kalemleri kopyalanacak belgeyi seçin:"))
        self.tbl_docs = QTableWidget(0, 4)
        self.tbl_docs.setHorizontalHeaderLabels(["Belge No", "Tür", "Cari", "Tutar"])
        self.tbl_docs.verticalHeader().setVisible(False)
        self.tbl_docs.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_docs.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbl_docs.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_docs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        lyt.addWidget(self.tbl_docs, 1)
        self._load_docs()
        return w

    def _load_docs(self) -> None:
        if not self.db:
            return
        try:
            rows = self.db.scalars(
                select(Quotation).where(
                    Quotation.is_deleted == False,  # noqa: E712
                ).order_by(Quotation.id.desc()).limit(200),
            ).all()
        except Exception:  # noqa: BLE001
            logger.exception("Belgeler yüklenemedi")
            rows = []
        self._doc_ids: list[int] = []
        for q in rows:
            if self._exclude_doc_id and q.id == self._exclude_doc_id:
                continue
            r = self.tbl_docs.rowCount()
            self.tbl_docs.insertRow(r)
            self._doc_ids.append(q.id)
            cari = q.customer_name_free or (q.customer.fullname if q.customer else "")
            for c_idx, text in enumerate([
                q.quotation_number or "",
                _TYPE_TR.get(q.quotation_type, q.quotation_type or ""),
                cari,
                f"{float(q.grand_total or 0):,.2f}",
            ]):
                self.tbl_docs.setItem(r, c_idx, QTableWidgetItem(text))

    def _build_product_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Ürün ara (kod / ad / barkod)…")
        self.txt_filter.textChanged.connect(self._filter_products)
        lyt.addWidget(self.txt_filter)

        self.tbl_prod = QTableWidget(0, 4)
        self.tbl_prod.setHorizontalHeaderLabels(["Kod", "Ürün", "Birim", "Fiyat"])
        self.tbl_prod.verticalHeader().setVisible(False)
        self.tbl_prod.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_prod.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_prod.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lyt.addWidget(self.tbl_prod, 1)
        lyt.addWidget(QLabel("Seçili (çoklu) ürünler 1 adet miktarla eklenir."))
        self._fill_products(self._products)
        return w

    def _fill_products(self, items: list[dict]) -> None:
        self.tbl_prod.setRowCount(0)
        self._prod_rows: list[dict] = []
        for p in items:
            r = self.tbl_prod.rowCount()
            self.tbl_prod.insertRow(r)
            self._prod_rows.append(p)
            for c_idx, text in enumerate([
                str(p.get("code", "")), str(p.get("name", "")),
                str(p.get("unit", "Adet")), f"{float(p.get('price', 0) or 0):,.2f}",
            ]):
                self.tbl_prod.setItem(r, c_idx, QTableWidgetItem(text))

    def _filter_products(self, text: str) -> None:
        t = text.strip().lower()
        if not t:
            self._fill_products(self._products)
            return
        self._fill_products([
            p for p in self._products
            if t in str(p.get("code", "")).lower()
            or t in str(p.get("name", "")).lower()
            or t in str(p.get("barcode", "")).lower()
        ])

    # ------------------------------------------------------------------
    def _on_accept(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._collect_from_doc()
        else:
            self._collect_from_products()
        if not self.result_lines:
            self.reject()
            return
        self.accept()

    def _collect_from_doc(self) -> None:
        rows = {i.row() for i in self.tbl_docs.selectedIndexes()}
        if not rows:
            return
        doc_id = self._doc_ids[min(rows)]
        try:
            from src.desktop.services.quotation_save_service import QuotationSaveService
            payload = QuotationSaveService(db_session=self.db).load_payload(doc_id)
            self.result_lines = list(payload.get("lines", [])) if payload else []
        except Exception:  # noqa: BLE001
            logger.exception("Belge kalemleri okunamadı")
            self.result_lines = []

    def _collect_from_products(self) -> None:
        rows = sorted({i.row() for i in self.tbl_prod.selectedIndexes()})
        out = []
        for r in rows:
            p = self._prod_rows[r]
            out.append({
                "kod": p.get("code", ""),
                "barkod": p.get("barcode", ""),
                "aciklama": p.get("name", ""),
                "miktar": "1",
                "birim": p.get("unit", "Adet"),
                "birim_fiyat": str(p.get("price", 0) or 0),
                "iskonto_yuzde": "",
                "kdv_yuzde": str(p.get("vat_rate", "") or ""),
            })
        self.result_lines = out
