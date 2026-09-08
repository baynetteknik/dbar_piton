"""TOYA ERP - Rol (Yetki Rolü) tanımları liste ekranı (embedded 3-panel)."""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QStandardItem
from PyQt6.QtWidgets import QLabel, QLineEdit, QMenu, QMessageBox, QPushButton

from src.desktop.security.permissions import ALL_PERMISSIONS
from src.desktop.services.role_service import RoleService
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.screens.rol_editor import RolEditorDialog

logger = logging.getLogger(__name__)


class RolListWidget(ThreePanelBaseWidget):
    def __init__(self, db_session=None, parent=None, embedded: bool = False):
        self.service = RoleService(db_session)
        self.service.seed_defaults()
        self._search = ""
        super().__init__(db_session=db_session, profile_key="roles",
                         module_name="Rol Tanımları", parent=parent, embedded=embedded)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._menu)
        self.table_view.doubleClicked.connect(lambda *_: self.edit_selected())
        self.load_data()

    def setup_headers_dict(self):
        return {
            0: ("ID", "id"), 1: ("Rol Adı", "name"), 2: ("Açıklama", "description"),
            3: ("Yetki Sayısı", "perm_count"), 4: ("Tür", "kind"), 5: ("Durum", "status"),
        }

    def setup_left_panel_content(self, container, layout):
        sec = CollapsibleSection("FİLTRE & ARAMA", is_expanded=True)
        sec.add_widget(QLabel("Ara (rol adı):"))
        self.txt_search = QLineEdit()
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._on_search)
        sec.add_widget(self.txt_search)
        layout.addWidget(sec)
        layout.addStretch()

    def setup_right_panel_content(self, container, layout):
        sec = CollapsibleSection("ROL İŞLEMLERİ", is_expanded=True)
        for text, slot, color in (
            ("➕ Yeni Rol", self.add_new, "#16a34a"),
            ("✏️ Düzenle", self.edit_selected, "#2563eb"),
            ("🗑️ Sil", self.delete_selected, "#ef4444"),
            ("🔄 Yenile", self.load_data, "#64748b"),
        ):
            b = QPushButton(text)
            b.setStyleSheet(f"QPushButton{{background:{color};color:#fff;border:none;"
                            f"border-radius:4px;padding:6px 8px;font-size:11px;"
                            f"font-weight:600;text-align:left;}}")
            b.clicked.connect(lambda _c=False, s=slot: s())
            sec.add_widget(b)
        layout.addWidget(sec)
        layout.addStretch()

    def apply_quick_search(self, text):
        if hasattr(self, "txt_search"):
            self.txt_search.setText(text)

    def apply_status_filter(self, status):
        pass

    def record_count(self):
        return self.table_model.rowCount()

    def _on_search(self, text):
        self._search = (text or "").strip().lower()
        self.load_data()

    # ------------------------------------------------------------------
    def load_data(self):
        self.table_model.removeRows(0, self.table_model.rowCount())
        for r in self.service.list_roles():
            if self._search and self._search not in (r.name or "").lower():
                continue
            perms = self.service.permissions_of(r)
            n = len(ALL_PERMISSIONS) if "*" in perms else len(perms)
            row = [
                QStandardItem(str(r.id)),
                QStandardItem(r.name),
                QStandardItem(r.description or ""),
                QStandardItem(f"{n} / {len(ALL_PERMISSIONS)}"),
                QStandardItem("Sistem" if r.is_system else "Özel"),
                QStandardItem("Aktif" if r.is_active else "Pasif"),
            ]
            for it in row:
                it.setEditable(False)
            self.table_model.appendRow(row)
        self.total_records = self.table_model.rowCount()

    def _selected_id(self):
        sel = self.table_view.selectionModel().selectedRows()
        if not sel:
            return None
        it = self.table_model.item(sel[0].row(), 0)
        return int(it.text()) if it and it.text().isdigit() else None

    def add_new(self):
        if RolEditorDialog(db_session=self.db, role_id=None, parent=self).exec():
            self.load_data()

    def edit_selected(self):
        rid = self._selected_id()
        if not rid:
            QMessageBox.information(self, "Uyarı", "Düzenlenecek rolü seçin.")
            return
        if RolEditorDialog(db_session=self.db, role_id=rid, parent=self).exec():
            self.load_data()

    def delete_selected(self):
        rid = self._selected_id()
        if not rid:
            QMessageBox.information(self, "Uyarı", "Silinecek rolü seçin.")
            return
        if QMessageBox.question(
            self, "Rol Sil", "Seçili rol silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        ok, msg = self.service.delete(rid)
        if ok:
            self.load_data()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def _menu(self, pos):
        m = QMenu(self)
        a_new = QAction("➕ Yeni Rol", self)
        a_new.triggered.connect(self.add_new)
        m.addAction(a_new)
        if self.table_view.indexAt(pos).isValid():
            a_edit = QAction("✏️ Düzenle", self)
            a_edit.triggered.connect(self.edit_selected)
            a_del = QAction("🗑️ Sil", self)
            a_del.triggered.connect(self.delete_selected)
            m.addAction(a_edit)
            m.addAction(a_del)
        m.exec(self.table_view.viewport().mapToGlobal(pos))
