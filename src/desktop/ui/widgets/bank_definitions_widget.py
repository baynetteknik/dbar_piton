"""TOYA ERP - Banka ve Şube Tanımları Yönetim Bileşeni (BankDefinitionsWidget).

Banka kodları, Swift/BIC, EFT kodları ve şube tanımlarını yönetir.
Banka & POS kartlarında bu katalogdan seçim yapılır.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.master_definitions_store import (
    MasterDefinitionsStore,
)
from src.desktop.ui.components.button_style import btn_style
from src.desktop.ui.components.dialog_style import apply_light_dialog_style, onay, uyari
from src.desktop.ui.components.entry_table_view import standart_grid


class BankDefinitionsWidget(QWidget):
    """Genel Ayarlar içi Banka ve Şube Tanımları Paneli."""

    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, store: MasterDefinitionsStore | None = None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.store = store or MasterDefinitionsStore()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Bilgi Başlığı
        header = QFrame()
        header.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;")
        h_lyt = QHBoxLayout(header)
        h_lyt.setContentsMargins(0, 0, 0, 0)
        lbl_info = QLabel("🏦 <b>Banka & Şube Tanımları</b> — Banka Hesapları, POS ve Kredi Kartı tanımlarında standart banka/şube kataloğu olarak kullanılır.")
        lbl_info.setStyleSheet("color: #0f172a; font-size: 11px;")
        h_lyt.addWidget(lbl_info)
        layout.addWidget(header)

        # Sekmeler
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #cbd5e1; background: #ffffff; border-radius: 4px; }
            QTabBar::tab { background: #e2e8f0; color: #334155; padding: 6px 14px; border: 1px solid #cbd5e1; border-bottom: none;
                           border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px; font-weight: 600; font-size: 11px; }
            QTabBar::tab:selected { background: #2563eb; color: #ffffff; border-color: #1d4ed8; }
            QTabBar::tab:hover:!selected { background: #dbeafe; color: #1d4ed8; }
        """)

        self.tab_banks = self._build_banks_tab()
        self.tab_branches = self._build_branches_tab()

        self.tabs.addTab(self.tab_banks, "1. Bankalar")
        self.tabs.addTab(self.tab_branches, "2. Banka Şubeleri")
        layout.addWidget(self.tabs, 1)

        self.load_banks()
        self.load_branches()

    # ---- 1. BANKALAR -------------------------------------------------------
    def _build_banks_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(6)

        bar = QHBoxLayout()
        btn_add = QPushButton("➕ Yeni Banka Ekle")
        btn_add.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        btn_add.clicked.connect(self._on_add_bank)

        btn_del = QPushButton("🗑️ Pasife Al")
        btn_del.setStyleSheet(btn_style("#ffffff", "#dc2626"))
        btn_del.clicked.connect(self._on_delete_bank)

        bar.addWidget(btn_add)
        bar.addWidget(btn_del)
        bar.addStretch()
        lyt.addLayout(bar)

        self.grid_banks = standart_grid("def_banks", [
            ("code", "BANKA KODU"), ("name", "BANKA ADI"), ("swift_code", "SWIFT / BIC"), ("eft_code", "EFT KODU"),
        ])
        lyt.addWidget(self.grid_banks, 1)
        return w

    def add_new(self) -> None:
        idx = self.tabs.currentIndex()
        if idx == 0:
            self._on_add_bank()
        else:
            self._on_add_branch()

    def edit_selected(self) -> None:
        pass

    def delete_selected(self) -> None:
        idx = self.tabs.currentIndex()
        if idx == 0:
            self._on_delete_bank()
        else:
            self._on_delete_branch()

    def refresh_all(self) -> None:
        self.load_banks()
        self.load_branches()

    def load_banks(self) -> None:
        tv = self.grid_banks.table_view
        tv.setRowCount(0)
        banks = self.store.get_banks(active_only=True)
        for b in banks:
            r = tv.rowCount()
            tv.insertRow(r)
            tv.setRowHeight(r, tv.effective_row_height)
            for col_idx, key in enumerate(["code", "name", "swift_code", "eft_code"]):
                val = str(b.get(key) or "")
                it = QStandardItem(val)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col_idx == 0:
                    it.setData(b["id"], Qt.ItemDataRole.UserRole)
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tv.setItem(r, col_idx, it)

    def _on_add_bank(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Banka Tanımla")
        dlg.setMinimumWidth(380)
        apply_light_dialog_style(dlg)
        f = QFormLayout(dlg)

        t_code = QLineEdit()
        t_code.setPlaceholderText("Örn: 0010")
        t_name = QLineEdit()
        t_name.setPlaceholderText("Örn: T.C. Ziraat Bankası")
        t_swift = QLineEdit()
        t_swift.setPlaceholderText("Örn: TCZBTR2A")
        t_eft = QLineEdit()
        t_eft.setPlaceholderText("Örn: 0010")

        f.addRow("Banka Kodu *", t_code)
        f.addRow("Banka Adı *", t_name)
        f.addRow("SWIFT / BIC Kodu", t_swift)
        f.addRow("EFT / Merkez Kodu", t_eft)

        bar = QHBoxLayout()
        b_save = QPushButton("💾 Kaydet")
        b_save.setDefault(True)
        b_cancel = QPushButton("✖ Vazgeç")
        b_save.clicked.connect(dlg.accept)
        b_cancel.clicked.connect(dlg.reject)
        bar.addWidget(b_save)
        bar.addWidget(b_cancel)
        f.addRow(bar)

        if dlg.exec():
            try:
                self.store.add_bank(t_code.text(), t_name.text(), t_swift.text(), t_eft.text())
                self.load_banks()
                self._update_branch_bank_combo()
            except Exception as e:
                uyari(self, "Hata", str(e))

    def _on_delete_bank(self) -> None:
        tv = self.grid_banks.table_view
        r = tv.currentRow()
        if r < 0:
            uyari(self, "Seçim Yapılmadı", "Lütfen pasife almak istediğiniz bankayı seçin.")
            return
        bid = tv.item(r, 0).data(Qt.ItemDataRole.UserRole)
        bname = tv.item(r, 1).text()
        if onay(self, "Onay", f"'{bname}' bankasını pasife almak istediğinize emin misiniz?"):
            self.store.delete_bank(bid)
            self.load_banks()

    # ---- 2. BANKA ŞUBELERİ -------------------------------------------------
    def _build_branches_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(6)

        bar = QHBoxLayout()
        lbl_b = QLabel("Banka:")
        lbl_b.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.cmb_branch_bank = QComboBox()
        self.cmb_branch_bank.currentIndexChanged.connect(self.load_branches)

        btn_add = QPushButton("➕ Yeni Şube Ekle")
        btn_add.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        btn_add.clicked.connect(self._on_add_branch)

        btn_del = QPushButton("🗑️ Pasife Al")
        btn_del.setStyleSheet(btn_style("#ffffff", "#dc2626"))
        btn_del.clicked.connect(self._on_delete_branch)

        bar.addWidget(lbl_b)
        bar.addWidget(self.cmb_branch_bank)
        bar.addStretch()
        bar.addWidget(btn_add)
        bar.addWidget(btn_del)
        lyt.addLayout(bar)

        self.grid_branches = standart_grid("def_bank_branches", [
            ("bank_code", "BANKA KODU"), ("branch_code", "ŞUBE KODU"), ("branch_name", "ŞUBE ADI"),
            ("city_plate", "İL"), ("district_name", "İLÇE"),
        ])
        lyt.addWidget(self.grid_branches, 1)
        return w

    def _update_branch_bank_combo(self) -> None:
        self.cmb_branch_bank.blockSignals(True)
        self.cmb_branch_bank.clear()
        self.cmb_branch_bank.addItem("Tüm Bankalar", None)
        for b in self.store.get_banks(active_only=True):
            self.cmb_branch_bank.addItem(f"{b['code']} - {b['name']}", b["code"])
        self.cmb_branch_bank.blockSignals(False)

    def load_branches(self) -> None:
        if self.cmb_branch_bank.count() == 0:
            self._update_branch_bank_combo()
        bcode = self.cmb_branch_bank.currentData()
        tv = self.grid_branches.table_view
        tv.setRowCount(0)
        branches = self.store.get_bank_branches(bank_code=bcode, active_only=True)
        for br in branches:
            r = tv.rowCount()
            tv.insertRow(r)
            tv.setRowHeight(r, tv.effective_row_height)
            for col_idx, key in enumerate(["bank_code", "branch_code", "branch_name", "city_plate", "district_name"]):
                val = str(br.get(key) or "")
                it = QStandardItem(val)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col_idx == 0:
                    it.setData(br["id"], Qt.ItemDataRole.UserRole)
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tv.setItem(r, col_idx, it)

    def _on_add_branch(self) -> None:
        bcode = self.cmb_branch_bank.currentData()
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Banka Şubesi Ekle")
        dlg.setMinimumWidth(380)
        apply_light_dialog_style(dlg)
        f = QFormLayout(dlg)

        cmb_b = QComboBox()
        for b in self.store.get_banks(active_only=True):
            cmb_b.addItem(f"{b['code']} - {b['name']}", b["code"])
        if bcode:
            idx = cmb_b.findData(bcode)
            if idx >= 0:
                cmb_b.setCurrentIndex(idx)

        t_scode = QLineEdit()
        t_scode.setPlaceholderText("Örn: 0101")
        t_sname = QLineEdit()
        t_sname.setPlaceholderText("Örn: Kadıköy Rıhtım Şubesi")
        cmb_pl = QComboBox()
        for c in self.store.get_cities(country_code="TR", active_only=True):
            cmb_pl.addItem(f"{c['plate_code']} - {c['name']}", c["plate_code"])
        t_dist = QLineEdit()
        t_dist.setPlaceholderText("Örn: Kadıköy")

        f.addRow("Banka *", cmb_b)
        f.addRow("Şube Kodu *", t_scode)
        f.addRow("Şube Adı *", t_sname)
        f.addRow("İl", cmb_pl)
        f.addRow("İlçe", t_dist)

        bar = QHBoxLayout()
        b_save = QPushButton("💾 Kaydet")
        b_save.setDefault(True)
        b_cancel = QPushButton("✖ Vazgeç")
        b_save.clicked.connect(dlg.accept)
        b_cancel.clicked.connect(dlg.reject)
        bar.addWidget(b_save)
        bar.addWidget(b_cancel)
        f.addRow(bar)

        if dlg.exec():
            try:
                self.store.add_bank_branch(cmb_b.currentData(), t_scode.text(), t_sname.text(), cmb_pl.currentData(), t_dist.text())
                self.load_branches()
            except Exception as e:
                uyari(self, "Hata", str(e))

    def _on_delete_branch(self) -> None:
        tv = self.grid_branches.table_view
        r = tv.currentRow()
        if r < 0:
            uyari(self, "Seçim Yapılmadı", "Lütfen pasife almak istediğiniz şubeyi seçin.")
            return
        brid = tv.item(r, 0).data(Qt.ItemDataRole.UserRole)
        brname = tv.item(r, 2).text()
        if onay(self, "Onay", f"'{brname}' şubesini pasife almak istediğinize emin misiniz?"):
            self.store.delete_bank_branch(brid)
            self.load_branches()
