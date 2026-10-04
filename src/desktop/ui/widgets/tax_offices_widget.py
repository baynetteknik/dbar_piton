"""TOYA ERP - Vergi Daireleri Tanım Bileşeni (TaxOfficesWidget).

Vergi Dairesi kodları, adları, bağlı oldukları il/ilçe ve saymanlık kodlarını yönetir.
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
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.master_definitions_store import (
    MasterDefinitionsStore,
)
from src.desktop.ui.components.button_style import btn_style
from src.desktop.ui.components.dialog_style import apply_light_dialog_style, onay, uyari
from src.desktop.ui.components.entry_table_view import standart_grid


class TaxOfficesWidget(QWidget):
    """Genel Ayarlar içi Vergi Daireleri Paneli."""

    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, store: MasterDefinitionsStore | None = None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.store = store or MasterDefinitionsStore()
        self._init_ui()
        self.load_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Bilgi Başlığı
        header = QFrame()
        header.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;")
        h_lyt = QHBoxLayout(header)
        h_lyt.setContentsMargins(0, 0, 0, 0)
        lbl_info = QLabel("🏛️ <b>Vergi Dairesi Tanımları</b> — Cari ve Fatura işlemlerinde vergi dairesi seçimi ve e-Devlet kodlaması için kullanılır.")
        lbl_info.setStyleSheet("color: #0f172a; font-size: 11px;")
        h_lyt.addWidget(lbl_info)
        layout.addWidget(header)

        # Filtre ve Aksiyon Barı
        bar = QHBoxLayout()
        lbl_f = QLabel("İl Filtresi:")
        lbl_f.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.cmb_city = QComboBox()
        self.cmb_city.addItem("Tüm İller", None)
        for c in self.store.get_cities(country_code="TR", active_only=True):
            self.cmb_city.addItem(f"{c['plate_code']} - {c['name']}", c["plate_code"])
        self.cmb_city.currentIndexChanged.connect(self.load_data)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Vergi dairesi ara (kod / ad)...")
        self.txt_search.setFixedWidth(220)
        self.txt_search.textChanged.connect(self.load_data)

        btn_add = QPushButton("➕ Yeni Vergi Dairesi")
        btn_add.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        btn_add.clicked.connect(self._on_add)

        btn_del = QPushButton("🗑️ Pasife Al")
        btn_del.setStyleSheet(btn_style("#ffffff", "#dc2626"))
        btn_del.clicked.connect(self._on_delete)

        bar.addWidget(lbl_f)
        bar.addWidget(self.cmb_city)
        bar.addWidget(self.txt_search)
        bar.addStretch()
        bar.addWidget(btn_add)
        bar.addWidget(btn_del)
        layout.addLayout(bar)

        # Standart Grid
        self.grid = standart_grid("def_tax_offices", [
            ("code", "V.D. KODU"), ("name", "VERGİ DAİRESİ ADI"), ("city_plate", "İL"),
            ("district_name", "İLÇE"), ("treasury_code", "SAYMANLIK KODU"),
        ])
        layout.addWidget(self.grid, 1)

    def add_new(self) -> None:
        self._on_add()

    def edit_selected(self) -> None:
        pass

    def delete_selected(self) -> None:
        self._on_delete()

    def load_data(self) -> None:
        plate = self.cmb_city.currentData()
        q = self.txt_search.text().strip().lower()
        tv = self.grid.table_view
        tv.setRowCount(0)
        rows = self.store.get_tax_offices(city_plate=plate, active_only=True)
        for d in rows:
            if q:
                if q not in (d.get("name") or "").lower() and q not in (d.get("code") or "").lower():
                    continue
            r = tv.rowCount()
            tv.insertRow(r)
            tv.setRowHeight(r, tv.effective_row_height)
            for col_idx, key in enumerate(["code", "name", "city_plate", "district_name", "treasury_code"]):
                val = str(d.get(key) or "")
                it = QStandardItem(val)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col_idx == 0:
                    it.setData(d["id"], Qt.ItemDataRole.UserRole)
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tv.setItem(r, col_idx, it)

    def _on_add(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Vergi Dairesi Tanımla")
        dlg.setMinimumWidth(380)
        apply_light_dialog_style(dlg)
        f = QFormLayout(dlg)

        t_code = QLineEdit()
        t_code.setPlaceholderText("Örn: 034251")
        t_name = QLineEdit()
        t_name.setPlaceholderText("Örn: Kadıköy Vergi Dairesi")
        cmb_pl = QComboBox()
        for c in self.store.get_cities(country_code="TR", active_only=True):
            cmb_pl.addItem(f"{c['plate_code']} - {c['name']}", c["plate_code"])
        cur_pl = self.cmb_city.currentData()
        if cur_pl:
            idx = cmb_pl.findData(cur_pl)
            if idx >= 0:
                cmb_pl.setCurrentIndex(idx)
        t_dist = QLineEdit()
        t_dist.setPlaceholderText("Örn: Kadıköy")
        t_saym = QLineEdit()
        t_saym.setPlaceholderText("Örn: 34251")

        f.addRow("V.D. Kodu", t_code)
        f.addRow("Vergi Dairesi Adı *", t_name)
        f.addRow("İl", cmb_pl)
        f.addRow("İlçe", t_dist)
        f.addRow("Saymanlık Kodu", t_saym)

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
                self.store.add_tax_office(t_code.text(), t_name.text(), cmb_pl.currentData(), t_dist.text(), t_saym.text())
                self.load_data()
            except Exception as e:
                uyari(self, "Hata", str(e))

    def _on_delete(self) -> None:
        tv = self.grid.table_view
        r = tv.currentRow()
        if r < 0:
            uyari(self, "Seçim Yapılmadı", "Lütfen pasife almak istediğiniz vergi dairesini seçin.")
            return
        tid = tv.item(r, 0).data(Qt.ItemDataRole.UserRole)
        tname = tv.item(r, 1).text()
        if onay(self, "Onay", f"'{tname}' vergi dairesini pasife almak istediğinize emin misiniz?"):
            self.store.delete_tax_office(tid)
            self.load_data()
