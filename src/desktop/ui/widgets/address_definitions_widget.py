"""TOYA ERP - Adres Tanımları Yönetim Bileşeni (AddressDefinitionsWidget).

Ülkeler, İller/Şehirler, İlçeler ve Semt/Mahalle hiyerarşik tanım tablolarını
ve CRUD işlemlerini yönetir.
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


class AddressDefinitionsWidget(QWidget):
    """Genel Ayarlar içi Adres Tanımları Paneli (Ülke / İl / İlçe / Semt)."""

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

        # Başlık Bilgisi
        header = QFrame()
        header.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;")
        h_lyt = QHBoxLayout(header)
        h_lyt.setContentsMargins(0, 0, 0, 0)
        lbl_info = QLabel("🌍 <b>Adres Tanımları</b> — Ülke, İl, İlçe ve Mahalle/Semt hiyerarşisi cari ve sipariş formlarında otomatik kullanılır.")
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

        self.tab_countries = self._build_countries_tab()
        self.tab_cities = self._build_cities_tab()
        self.tab_districts = self._build_districts_tab()
        self.tab_sub_districts = self._build_sub_districts_tab()

        self.tabs.addTab(self.tab_countries, "1. Ülkeler")
        self.tabs.addTab(self.tab_cities, "2. Şehirler / İller")
        self.tabs.addTab(self.tab_districts, "3. İlçeler")
        self.tabs.addTab(self.tab_sub_districts, "4. Semt & Mahalleler")

        layout.addWidget(self.tabs, 1)

        # İlk verileri yükle
        self.load_countries()
        self.load_cities()
        self.load_districts()

    def add_new(self) -> None:
        idx = self.tabs.currentIndex()
        if idx == 0:
            self._on_add_country()
        elif idx == 1:
            self._on_add_city()
        elif idx == 2:
            self._on_add_district()
        else:
            self._on_add_sub_district()

    def edit_selected(self) -> None:
        pass

    def delete_selected(self) -> None:
        idx = self.tabs.currentIndex()
        if idx == 0:
            self._on_delete_country()
        elif idx == 1:
            self._on_delete_city()
        elif idx == 2:
            self._on_delete_district()
        else:
            self._on_delete_sub_district()

    def refresh_all(self) -> None:
        self.load_countries()
        self.load_cities()
        self.load_districts()
        self.load_sub_districts()

    # ---- 1. ÜLKELER --------------------------------------------------------
    def _build_countries_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(6)

        # Toolbar
        bar = QHBoxLayout()
        btn_add = QPushButton("➕ Yeni Ülke Ekle")
        btn_add.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        btn_add.clicked.connect(self._on_add_country)
        btn_del = QPushButton("🗑️ Seçiliyi Pasife Al")
        btn_del.setStyleSheet(btn_style("#ffffff", "#dc2626"))
        btn_del.clicked.connect(self._on_delete_country)

        bar.addWidget(btn_add)
        bar.addWidget(btn_del)
        bar.addStretch()
        lyt.addLayout(bar)

        self.grid_countries = standart_grid("def_countries", [
            ("code", "ÜLKE KODU"), ("name", "ÜLKE ADI"), ("phone_code", "TEL KODU"), ("currency", "PARA BİRİMİ"),
        ])
        lyt.addWidget(self.grid_countries, 1)
        return w

    def load_countries(self) -> None:
        tv = self.grid_countries.table_view
        tv.setRowCount(0)
        countries = self.store.get_countries(active_only=True)
        for c in countries:
            r = tv.rowCount()
            tv.insertRow(r)
            tv.setRowHeight(r, tv.effective_row_height)
            for col_idx, key in enumerate(["code", "name", "phone_code", "currency"]):
                val = str(c.get(key) or "")
                it = QStandardItem(val)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col_idx == 0:
                    it.setData(c["id"], Qt.ItemDataRole.UserRole)
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tv.setItem(r, col_idx, it)

    def _on_add_country(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Ülke Tanımla")
        dlg.setMinimumWidth(340)
        apply_light_dialog_style(dlg)
        f = QFormLayout(dlg)
        t_code = QLineEdit()
        t_code.setPlaceholderText("Örn: TR")
        t_name = QLineEdit()
        t_name.setPlaceholderText("Örn: Türkiye")
        t_phone = QLineEdit()
        t_phone.setPlaceholderText("Örn: +90")
        t_curr = QLineEdit()
        t_curr.setText("TRY")
        f.addRow("Ülke Kodu *", t_code)
        f.addRow("Ülke Adı *", t_name)
        f.addRow("Telefon Kodu", t_phone)
        f.addRow("Para Birimi", t_curr)
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
                self.store.add_country(t_code.text(), t_name.text(), t_phone.text(), t_curr.text())
                self.load_countries()
            except Exception as e:
                uyari(self, "Hata", str(e))

    def _on_delete_country(self) -> None:
        tv = self.grid_countries.table_view
        r = tv.currentRow()
        if r < 0:
            uyari(self, "Seçim Yapılmadı", "Lütfen pasife almak istediğiniz ülkeyi seçin.")
            return
        cid = tv.item(r, 0).data(Qt.ItemDataRole.UserRole)
        cname = tv.item(r, 1).text()
        if onay(self, "Onay", f"'{cname}' ülkesini pasife almak istediğinize emin misiniz?"):
            self.store.delete_country(cid)
            self.load_countries()

    # ---- 2. İLLER / ŞEHİRLER ------------------------------------------------
    def _build_cities_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(6)

        bar = QHBoxLayout()
        lbl_u = QLabel("Ülke:")
        lbl_u.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.cmb_city_country = QComboBox()
        self.cmb_city_country.addItem("🇹🇷 Türkiye (TR)", "TR")
        self.cmb_city_country.currentIndexChanged.connect(self.load_cities)
        bar.addWidget(lbl_u)
        bar.addWidget(self.cmb_city_country)

        btn_add = QPushButton("➕ Yeni İl Ekle")
        btn_add.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        btn_add.clicked.connect(self._on_add_city)
        btn_del = QPushButton("🗑️ Pasife Al")
        btn_del.setStyleSheet(btn_style("#ffffff", "#dc2626"))
        btn_del.clicked.connect(self._on_delete_city)

        bar.addWidget(btn_add)
        bar.addWidget(btn_del)
        bar.addStretch()
        lyt.addLayout(bar)

        self.grid_cities = standart_grid("def_cities", [
            ("plate_code", "PLAKA"), ("name", "ŞEHİR / İL ADI"), ("phone_code", "ALAN KODU"),
        ])
        lyt.addWidget(self.grid_cities, 1)
        return w

    def load_cities(self) -> None:
        country_code = self.cmb_city_country.currentData() or "TR"
        tv = self.grid_cities.table_view
        tv.setRowCount(0)
        cities = self.store.get_cities(country_code=country_code, active_only=True)
        for c in cities:
            r = tv.rowCount()
            tv.insertRow(r)
            tv.setRowHeight(r, tv.effective_row_height)
            for col_idx, key in enumerate(["plate_code", "name", "phone_code"]):
                val = str(c.get(key) or "")
                it = QStandardItem(val)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col_idx == 0:
                    it.setData(c["id"], Qt.ItemDataRole.UserRole)
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tv.setItem(r, col_idx, it)

    def _on_add_city(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni İl / Şehir Ekle")
        dlg.setMinimumWidth(320)
        apply_light_dialog_style(dlg)
        f = QFormLayout(dlg)
        t_plate = QLineEdit()
        t_plate.setPlaceholderText("Örn: 34")
        t_name = QLineEdit()
        t_name.setPlaceholderText("Örn: İstanbul")
        t_phone = QLineEdit()
        t_phone.setPlaceholderText("Örn: 212")
        f.addRow("Plaka Kodu *", t_plate)
        f.addRow("İl Adı *", t_name)
        f.addRow("Alan Kodu", t_phone)
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
                self.store.add_city(t_plate.text(), t_name.text(), phone_code=t_phone.text())
                self.load_cities()
                self._update_district_combos()
            except Exception as e:
                uyari(self, "Hata", str(e))

    def _on_delete_city(self) -> None:
        tv = self.grid_cities.table_view
        r = tv.currentRow()
        if r < 0:
            uyari(self, "Seçim Yapılmadı", "Lütfen pasife almak istediğiniz ili seçin.")
            return
        cid = tv.item(r, 0).data(Qt.ItemDataRole.UserRole)
        cname = tv.item(r, 1).text()
        if onay(self, "Onay", f"'{cname}' ilini pasife almak istediğinize emin misiniz?"):
            self.store.delete_city(cid)
            self.load_cities()

    # ---- 3. İLÇELER --------------------------------------------------------
    def _build_districts_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(6)

        bar = QHBoxLayout()
        lbl_i = QLabel("İl:")
        lbl_i.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.cmb_district_city = QComboBox()
        self.cmb_district_city.currentIndexChanged.connect(self.load_districts)
        bar.addWidget(lbl_i)
        bar.addWidget(self.cmb_district_city)

        btn_add = QPushButton("➕ Yeni İlçe Ekle")
        btn_add.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        btn_add.clicked.connect(self._on_add_district)
        btn_del = QPushButton("🗑️ Pasife Al")
        btn_del.setStyleSheet(btn_style("#ffffff", "#dc2626"))
        btn_del.clicked.connect(self._on_delete_district)

        bar.addWidget(btn_add)
        bar.addWidget(btn_del)
        bar.addStretch()
        lyt.addLayout(bar)

        self.grid_districts = standart_grid("def_districts", [
            ("city_plate", "İL PLAKA"), ("name", "İLÇE ADI"),
        ])
        lyt.addWidget(self.grid_districts, 1)
        return w

    def _update_district_combos(self) -> None:
        cities = self.store.get_cities(country_code="TR", active_only=True)
        self.cmb_district_city.blockSignals(True)
        self.cmb_district_city.clear()
        self.cmb_district_city.addItem("Tüm İller", None)
        for c in cities:
            self.cmb_district_city.addItem(f"{c['plate_code']} - {c['name']}", c["plate_code"])
        self.cmb_district_city.blockSignals(False)

    def load_districts(self) -> None:
        if self.cmb_district_city.count() == 0:
            self._update_district_combos()
        plate = self.cmb_district_city.currentData()
        tv = self.grid_districts.table_view
        tv.setRowCount(0)
        districts = self.store.get_districts(city_plate=plate, active_only=True)
        for d in districts:
            r = tv.rowCount()
            tv.insertRow(r)
            tv.setRowHeight(r, tv.effective_row_height)
            for col_idx, key in enumerate(["city_plate", "name"]):
                val = str(d.get(key) or "")
                it = QStandardItem(val)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col_idx == 0:
                    it.setData(d["id"], Qt.ItemDataRole.UserRole)
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tv.setItem(r, col_idx, it)

    def _on_add_district(self) -> None:
        plate = self.cmb_district_city.currentData() or "34"
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni İlçe Ekle")
        dlg.setMinimumWidth(320)
        apply_light_dialog_style(dlg)
        f = QFormLayout(dlg)
        cmb_pl = QComboBox()
        for c in self.store.get_cities(country_code="TR", active_only=True):
            cmb_pl.addItem(f"{c['plate_code']} - {c['name']}", c["plate_code"])
        idx = cmb_pl.findData(plate)
        if idx >= 0:
            cmb_pl.setCurrentIndex(idx)
        t_name = QLineEdit()
        t_name.setPlaceholderText("Örn: Kadıköy")
        f.addRow("İl *", cmb_pl)
        f.addRow("İlçe Adı *", t_name)
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
                self.store.add_district(cmb_pl.currentData(), t_name.text())
                self.load_districts()
            except Exception as e:
                uyari(self, "Hata", str(e))

    def _on_delete_district(self) -> None:
        tv = self.grid_districts.table_view
        r = tv.currentRow()
        if r < 0:
            uyari(self, "Seçim Yapılmadı", "Lütfen pasife almak istediğiniz ilçeyi seçin.")
            return
        did = tv.item(r, 0).data(Qt.ItemDataRole.UserRole)
        dname = tv.item(r, 1).text()
        if onay(self, "Onay", f"'{dname}' ilçesini pasife almak istediğinize emin misiniz?"):
            self.store.delete_district(did)
            self.load_districts()

    # ---- 4. SEMT / MAHALLE -------------------------------------------------
    def _build_sub_districts_tab(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(8, 8, 8, 8)
        lyt.setSpacing(6)

        bar = QHBoxLayout()
        btn_add = QPushButton("➕ Yeni Semt / Mahalle Ekle")
        btn_add.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        btn_add.clicked.connect(self._on_add_sub_district)
        btn_del = QPushButton("🗑️ Pasife Al")
        btn_del.setStyleSheet(btn_style("#ffffff", "#dc2626"))
        btn_del.clicked.connect(self._on_delete_sub_district)
        bar.addWidget(btn_add)
        bar.addWidget(btn_del)
        bar.addStretch()
        lyt.addLayout(bar)

        self.grid_sub_districts = standart_grid("def_sub_districts", [
            ("city_plate", "İL"), ("district_name", "İLÇE"), ("name", "SEMT / MAHALLE"), ("postcode", "POSTA KODU"),
        ])
        lyt.addWidget(self.grid_sub_districts, 1)
        return w

    def load_sub_districts(self) -> None:
        tv = self.grid_sub_districts.table_view
        tv.setRowCount(0)
        subs = self.store.get_sub_districts(active_only=True)
        for s in subs:
            r = tv.rowCount()
            tv.insertRow(r)
            tv.setRowHeight(r, tv.effective_row_height)
            for col_idx, key in enumerate(["city_plate", "district_name", "name", "postcode"]):
                val = str(s.get(key) or "")
                it = QStandardItem(val)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col_idx == 0:
                    it.setData(s["id"], Qt.ItemDataRole.UserRole)
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tv.setItem(r, col_idx, it)

    def _on_add_sub_district(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Yeni Semt / Mahalle Ekle")
        dlg.setMinimumWidth(340)
        apply_light_dialog_style(dlg)
        f = QFormLayout(dlg)
        cmb_pl = QComboBox()
        for c in self.store.get_cities(country_code="TR", active_only=True):
            cmb_pl.addItem(f"{c['plate_code']} - {c['name']}", c["plate_code"])
        t_dist = QLineEdit()
        t_dist.setPlaceholderText("Örn: Kadıköy")
        t_name = QLineEdit()
        t_name.setPlaceholderText("Örn: Moda / Caferağa Mah.")
        t_post = QLineEdit()
        t_post.setPlaceholderText("Örn: 34710")
        f.addRow("İl *", cmb_pl)
        f.addRow("İlçe *", t_dist)
        f.addRow("Semt / Mahalle *", t_name)
        f.addRow("Posta Kodu", t_post)
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
                self.store.add_sub_district(cmb_pl.currentData(), t_dist.text(), t_name.text(), t_post.text())
                self.load_sub_districts()
            except Exception as e:
                uyari(self, "Hata", str(e))

    def _on_delete_sub_district(self) -> None:
        tv = self.grid_sub_districts.table_view
        r = tv.currentRow()
        if r < 0:
            uyari(self, "Seçim Yapılmadı", "Lütfen pasife almak istediğiniz semt/mahalleyi seçin.")
            return
        sid = tv.item(r, 0).data(Qt.ItemDataRole.UserRole)
        sname = tv.item(r, 2).text()
        if onay(self, "Onay", f"'{sname}' kaydını pasife almak istediğinize emin misiniz?"):
            self.store.delete_sub_district(sid)
            self.load_sub_districts()
