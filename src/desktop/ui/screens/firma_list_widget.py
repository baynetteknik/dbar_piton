"""
TOYA ERP - FirmaListWidget

Firma (Şirket) tanımları liste ekranı. Teklif listesiyle aynı 3-panel
mimariyi (`ThreePanelBaseWidget`) kullanır; Genel Ayarlar kabuğu içinde
`embedded=True` ile açıldığında kendi sol/sağ panellerini kurmaz.

Yeni / Düzenle akışı `FirmaEditorDialog` (tam ekran) ile yürür.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QStandardItem
from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
)

from src.desktop.services.company_service import CompanyService
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.screens.firma_editor import FirmaEditorDialog

logger = logging.getLogger(__name__)


class FirmaListWidget(ThreePanelBaseWidget):
    """Firma tanımları yönetim listesi."""

    def __init__(self, db_session=None, parent=None, embedded: bool = False):
        self.service = CompanyService(db_session=db_session)
        self._search_text = ""
        super().__init__(
            db_session=db_session,
            profile_key="companies",
            module_name="Firma Tanımları",
            parent=parent,
            embedded=embedded,
        )
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._context_menu)
        self.table_view.doubleClicked.connect(lambda *_: self.edit_selected())
        self.load_data()

    # ------------------------------------------------------------------
    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return {
            0: ("ID", "id"),
            1: ("Kod", "code"),
            2: ("Kısa Ad", "short_name"),
            3: ("Ünvan", "title"),
            4: ("Vergi No", "tax_number"),
            5: ("İl", "city"),
            6: ("e-Fatura", "e_invoice"),
            7: ("Durum", "status"),
        }

    def setup_left_panel_content(self, container, layout) -> None:
        sec = CollapsibleSection("FİLTRE & ARAMA", is_expanded=True)
        sec.add_widget(QLabel("Ara (kod / ad / ünvan):"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Hızlı arama…")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._on_search)
        sec.add_widget(self.txt_search)
        layout.addWidget(sec)
        layout.addStretch()

    def setup_right_panel_content(self, container, layout) -> None:
        sec = CollapsibleSection("FİRMA İŞLEMLERİ", is_expanded=True)
        for text, slot, style in (
            ("➕ Yeni Firma", self.add_new, "#16a34a"),
            ("✏️ Düzenle", self.edit_selected, "#2563eb"),
            ("🗑️ Sil", self.delete_selected, "#ef4444"),
            ("🔄 Yenile", self.load_data, "#64748b"),
        ):
            b = QPushButton(text)
            b.setStyleSheet(
                f"QPushButton{{background:{style};color:#fff;border:none;border-radius:4px;"
                f"padding:6px 8px;font-size:11px;font-weight:600;text-align:left;}}",
            )
            b.clicked.connect(lambda _c=False, s=slot: s())
            sec.add_widget(b)
        layout.addWidget(sec)
        layout.addStretch()

    # ------------------------------------------------------------------
    def _on_search(self, text: str):
        self._search_text = (text or "").strip().lower()
        self.load_data()

    def apply_quick_search(self, text: str):
        """Kabuk (Genel Ayarlar) sağ sidebar araması buraya yönlendirir."""
        if hasattr(self, "txt_search"):
            self.txt_search.setText(text)

    def apply_status_filter(self, status: str):
        pass

    def record_count(self) -> int:
        return self.table_model.rowCount()

    # ------------------------------------------------------------------
    def load_data(self) -> None:
        self.table_model.removeRows(0, self.table_model.rowCount())
        companies = self.service.list_companies()
        q = self._search_text
        for c in companies:
            hay = " ".join(str(x or "").lower() for x in (c.code, c.short_name, c.title))
            if q and q not in hay:
                continue
            row = [
                QStandardItem(str(c.id)),
                QStandardItem(c.code or ""),
                QStandardItem(c.short_name or ""),
                QStandardItem(c.title or ""),
                QStandardItem(c.tax_number or ""),
                QStandardItem(c.city or ""),
                QStandardItem("✔" if c.e_invoice_enabled else "—"),
                QStandardItem("Aktif" if c.is_active else "Pasif"),
            ]
            for it in row:
                it.setEditable(False)
            self.table_model.appendRow(row)
        self.total_records = self.table_model.rowCount()

    def _selected_id(self) -> int | None:
        sel = self.table_view.selectionModel().selectedRows()
        if not sel:
            return None
        it = self.table_model.item(sel[0].row(), 0)
        return int(it.text()) if it and it.text().isdigit() else None

    # ------------------------------------------------------------------
    def add_new(self):
        dlg = FirmaEditorDialog(db_session=self.db, company_id=None, parent=self)
        if dlg.exec():
            self.load_data()

    def edit_selected(self):
        cid = self._selected_id()
        if not cid:
            QMessageBox.information(self, "Uyarı", "Düzenlenecek firmayı seçin.")
            return
        dlg = FirmaEditorDialog(db_session=self.db, company_id=cid, parent=self)
        if dlg.exec():
            self.load_data()

    def delete_selected(self):
        cid = self._selected_id()
        if not cid:
            QMessageBox.information(self, "Uyarı", "Silinecek firmayı seçin.")
            return
        if QMessageBox.question(
            self, "Firma Sil", "Seçili firma silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        if self.service.delete(cid):
            self.load_data()
        else:
            QMessageBox.critical(self, "Hata", "Firma silinemedi.")

    def _context_menu(self, pos):
        menu = QMenu(self)
        a_new = QAction("➕ Yeni Firma", self)
        a_new.triggered.connect(self.add_new)
        a_edit = QAction("✏️ Düzenle", self)
        a_edit.triggered.connect(self.edit_selected)
        a_del = QAction("🗑️ Sil", self)
        a_del.triggered.connect(self.delete_selected)
        menu.addAction(a_new)
        if self.table_view.indexAt(pos).isValid():
            menu.addAction(a_edit)
            menu.addAction(a_del)
        menu.exec(self.table_view.viewport().mapToGlobal(pos))
