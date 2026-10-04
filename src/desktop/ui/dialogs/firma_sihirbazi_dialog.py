"""TOYA ERP - Firma Kurulum Sihirbazı (Wizard).

Adım adım şirket kurulumu:
1. Şirket Kimlik, Vergi ve Dinamik Adres Bilgileri
2. Yetkili & Ortak Tanımları (Popup destekli)
3. Çalışma Dönemi (Otomatik cari yıl 01.01.YYYY - 31.12.YYYY, Zorunlu)
4. Şube & Depo Tanımları (Varsayılan Merkez Şube/Depo, Zorunlu)
5. Banka Hesapları (İsteğe bağlı)
6. Özet & Kurulum Onayı
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QDate
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.core.models import WarehouseDefinition
from src.desktop.services.company_service import CompanyService
from src.desktop.services.currency_catalog import CURRENCY_CODES
from src.desktop.services.master_definitions_store import MasterDefinitionsStore
from src.desktop.services.numara_servisi import ensure_default_series
from src.desktop.services.sube_service import SubeService
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.widgets.donem_ekle_dialog import DonemEkleDialog
from src.desktop.ui.widgets.firma_tanim_dialoglari import (
    BankaHesabiEkleDialog,
    BirimEkleDialog,
    DepoEkleDialog,
    OrtakEkleDialog,
    SubeEkleDialog,
    YetkiliEkleDialog,
)

logger = logging.getLogger(__name__)


class FirmaSihirbaziDialog(QDialog):
    """Modern, adım adım Şirket Kurulum Sihirbazı."""

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.service = CompanyService(db_session=db_session)
        self.created_company_id: int | None = None
        self.master_store = MasterDefinitionsStore()

        self.setWindowTitle("🏢 Yeni Şirket Kurulum Sihirbazı")
        self.resize(920, 640)
        apply_light_dialog_style(self)

        # Veri depoları (Adımlardan toplanacak)
        self.yetkililer: list[dict] = []
        self.ortaklar: list[dict] = []
        self.donemler: list[dict] = []
        self.subeler: list[dict] = []
        self.depolar: list[dict] = []
        self.bankalar: list[dict] = []
        self.birimler: list[dict] = []

        # Varsayılan ilk dönem (Geçerli yıl)
        curr_year = QDate.currentDate().year()
        self.donemler.append({
            "ad": str(curr_year),
            "baslangic": f"01.01.{curr_year}",
            "bitis": f"31.12.{curr_year}",
            "aktif": "Evet",
        })

        # Varsayılan ilk şube & depo
        self.subeler.append({
            "code": "01",
            "name": "MERKEZ ŞUBE",
            "yetkili": "",
            "durum": "Aktif",
        })
        self.depolar.append({
            "code": "D01",
            "name": "MERKEZ DEPO",
            "address": "Merkez Adres",
            "durum": "Aktif",
        })

        # Varsayılan standart ölçü birimleri
        try:
            self.birimler = self.master_store.get_units(active_only=True)
        except Exception:  # noqa: BLE001
            self.birimler = []
        if not self.birimler:
            self.birimler = [
                {"code": "C62", "name": "Adet", "symbol": "Adet", "unit_type": "adet", "durum": "Aktif"},
                {"code": "KGM", "name": "Kilogram", "symbol": "Kg", "unit_type": "agirlik", "durum": "Aktif"},
                {"code": "MTR", "name": "Metre", "symbol": "m", "unit_type": "uzunluk", "durum": "Aktif"},
                {"code": "LTR", "name": "Litre", "symbol": "Lt", "unit_type": "hacim", "durum": "Aktif"},
                {"code": "PA", "name": "Paket", "symbol": "Paket", "unit_type": "paket", "durum": "Aktif"},
                {"code": "BX", "name": "Koli", "symbol": "Koli", "unit_type": "paket", "durum": "Aktif"},
                {"code": "PX", "name": "Palet", "symbol": "Palet", "unit_type": "paket", "durum": "Aktif"},
                {"code": "TNE", "name": "Ton", "symbol": "Ton", "unit_type": "agirlik", "durum": "Aktif"},
                {"code": "HUR", "name": "Saat", "symbol": "Sa", "unit_type": "zaman", "durum": "Aktif"},
                {"code": "DAY", "name": "Gün", "symbol": "Gün", "unit_type": "zaman", "durum": "Aktif"},
            ]

        self._build_ui()
        self._init_defaults()
        self._goto_step(0)

    # ------------------------------------------------------------------ UI Kurulumu
    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sol Adım Menüsü (Sidebar)
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(240)
        self.sidebar.setStyleSheet("background-color: #0f172a; color: #f8fafc;")
        side_lyt = QVBoxLayout(self.sidebar)
        side_lyt.setContentsMargins(16, 20, 16, 20)
        side_lyt.setSpacing(10)

        brand_lbl = QLabel("🏢 TOYA ERP\nŞirket Sihirbazı")
        brand_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #38bdf8; margin-bottom: 12px;")
        side_lyt.addWidget(brand_lbl)

        self.step_buttons: list[QPushButton] = []
        steps = [
            ("1. Şirket Bilgileri", "🏢"),
            ("2. Yetkili & Ortaklar", "👥"),
            ("3. Çalışma Dönemi *", "📅"),
            ("4. Şube & Depo *", "🏭"),
            ("5. Banka Hesapları", "🏦"),
            ("6. Birimler & Şablonlar", "📦"),
            ("7. Onay & Tamamla", "🚀"),
        ]

        for _idx, (title, icon) in enumerate(steps):
            btn = QPushButton(f"{icon}  {title}")
            btn.setStyleSheet(
                "QPushButton { text-align: left; padding: 10px 12px; border-radius: 6px; "
                "font-size: 12px; font-weight: 600; color: #94a3b8; background: transparent; border: none; } "
                "QPushButton:hover { background: #1e293b; color: #f8fafc; }",
            )
            btn.setEnabled(False)  # Sadece sırayla ilerleme
            side_lyt.addWidget(btn)
            self.step_buttons.append(btn)

        side_lyt.addStretch()

        help_box = QLabel("💡 <b>İpucu:</b>\nZorunlu alanları (Para Birimi, Dönem, Şube/Depo) tamamlayarak şirketinizi hemen çalışmaya hazır hale getirebilirsiniz.")
        help_box.setWordWrap(True)
        help_box.setStyleSheet("background: #1e293b; color: #cbd5e1; padding: 10px; border-radius: 6px; font-size: 11px;")
        side_lyt.addWidget(help_box)

        main_layout.addWidget(self.sidebar)

        # 2. Sağ Gövde (QStackedWidget + Navigasyon Barı)
        right_container = QWidget()
        right_lyt = QVBoxLayout(right_container)
        right_lyt.setContentsMargins(24, 20, 24, 20)
        right_lyt.setSpacing(16)

        self.stack = QStackedWidget()
        self.page_company = self._build_page_company()
        self.page_people = self._build_page_people()
        self.page_donem = self._build_page_donem()
        self.page_sube_depo = self._build_page_sube_depo()
        self.page_bank = self._build_page_bank()
        self.page_starter_pack = self._build_page_starter_pack()
        self.page_summary = self._build_page_summary()

        self.stack.addWidget(self.page_company)
        self.stack.addWidget(self.page_people)
        self.stack.addWidget(self.page_donem)
        self.stack.addWidget(self.page_sube_depo)
        self.stack.addWidget(self.page_bank)
        self.stack.addWidget(self.page_starter_pack)
        self.stack.addWidget(self.page_summary)

        right_lyt.addWidget(self.stack, 1)

        # 3. Alt Navigasyon Barı
        nav_bar = QHBoxLayout()
        self.btn_cancel = QPushButton("✖ Vazgeç")
        self.btn_cancel.setStyleSheet("background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; font-weight: 600; padding: 8px 16px; border-radius: 6px;")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_prev = QPushButton("◀ Geri")
        self.btn_prev.setStyleSheet("background: #e2e8f0; color: #1e293b; font-weight: 600; padding: 8px 20px; border-radius: 6px; border: 1px solid #cbd5e1;")
        self.btn_prev.clicked.connect(self._on_prev)

        self.btn_next = QPushButton("İleri ▶")
        self.btn_next.setStyleSheet("background: #2563eb; color: #ffffff; font-weight: 700; padding: 8px 24px; border-radius: 6px; border: none;")
        self.btn_next.clicked.connect(self._on_next)

        nav_bar.addWidget(self.btn_cancel)
        nav_bar.addStretch()
        nav_bar.addWidget(self.btn_prev)
        nav_bar.addWidget(self.btn_next)

        right_lyt.addLayout(nav_bar)
        main_layout.addWidget(right_container, 1)

    # ------------------------------------------------------------------ Sayfa 1: Şirket Kimlik & Adres
    def _build_page_company(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(12)

        header = QLabel("<h3>Adım 1: Şirket Kimlik, Vergi ve Adres Bilgileri</h3>")
        lyt.addWidget(header)

        form_box = QGroupBox("Temel Bilgiler")
        f = QFormLayout(form_box)

        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("örn. 001")
        self.txt_short_name = QLineEdit()
        self.txt_short_name.setPlaceholderText("Kısa / Ticari Ad (Zorunlu)")
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("Resmi / Fatura Ünvanı")

        self.cmb_company_type = QComboBox()
        self.cmb_company_type.addItems(["Limited Şirket", "Anonim Şirket", "Tüzel", "Şahıs", "Kooperatif", "Diğer"])

        self.cmb_currency = QComboBox()
        self.cmb_currency.addItems(CURRENCY_CODES[:15] or ["TRY", "USD", "EUR", "GBP"])

        self.txt_tax_office = QLineEdit()
        self.txt_tax_office.setPlaceholderText("Vergi Dairesi Adı")
        self.txt_tax_number = QLineEdit()
        self.txt_tax_number.setPlaceholderText("VKN (10 hane) veya TCKN (11 hane)")

        f.addRow("Firma Kodu *", self.txt_code)
        f.addRow("Firma Kısa Adı *", self.txt_short_name)
        f.addRow("Resmi Ünvan", self.txt_title)
        f.addRow("Şirket Tipi", self.cmb_company_type)
        f.addRow("Çalışma Para Birimi *", self.cmb_currency)
        f.addRow("Vergi Dairesi", self.txt_tax_office)
        f.addRow("Vergi No / TCKN", self.txt_tax_number)
        lyt.addWidget(form_box)

        # Adres Grubu (Dinamik Master Tanımlardan beslenir)
        addr_box = QGroupBox("Adres & İletişim Bilgileri (Dinamik Adres Tanımları)")
        af = QFormLayout(addr_box)

        self.cmb_country = QComboBox()
        self.cmb_city = QComboBox()
        self.cmb_district = QComboBox()
        self.txt_address = QPlainTextEdit()
        self.txt_address.setMaximumHeight(50)
        self.txt_address.setPlaceholderText("Mahalle, Cadde, Sokak, Kapı No...")

        self.txt_phone = QLineEdit()
        self.txt_email = QLineEdit()

        af.addRow("Ülke", self.cmb_country)
        af.addRow("İl (Şehir) *", self.cmb_city)
        af.addRow("İlçe", self.cmb_district)
        af.addRow("Açık Adres", self.txt_address)
        af.addRow("Telefon / E-Posta", self._make_h_pair(self.txt_phone, self.txt_email, "Telefon", "E-Posta"))
        lyt.addWidget(addr_box)

        self._load_countries()
        self.cmb_country.currentIndexChanged.connect(self._load_cities)
        self.cmb_city.currentIndexChanged.connect(self._load_districts)

        lyt.addStretch()
        return w

    def _make_h_pair(self, w1, w2, p1="", p2=""):
        c = QWidget()
        pair_lyt = QHBoxLayout(c)
        pair_lyt.setContentsMargins(0, 0, 0, 0)
        if p1:
            w1.setPlaceholderText(p1)
        if p2:
            w2.setPlaceholderText(p2)
        pair_lyt.addWidget(w1)
        pair_lyt.addWidget(w2)
        return c

    def _load_countries(self):
        self.cmb_country.blockSignals(True)
        self.cmb_country.clear()
        try:
            countries = self.master_store.get_countries(active_only=True)
            for c in countries:
                self.cmb_country.addItem(c["name"], c["code"])
            tr_idx = self.cmb_country.findData("TR")
            if tr_idx >= 0:
                self.cmb_country.setCurrentIndex(tr_idx)
        except Exception:  # noqa: BLE001
            self.cmb_country.addItem("TÜRKİYE", "TR")
        self.cmb_country.blockSignals(False)
        self._load_cities()

    def _load_cities(self):
        self.cmb_city.blockSignals(True)
        self.cmb_city.clear()
        self.cmb_city.addItem("— İl Seçin —", "")
        c_code = self.cmb_country.currentData() or "TR"
        try:
            cities = self.master_store.get_cities(country_code=c_code, active_only=True)
            for city in cities:
                self.cmb_city.addItem(f"{city['plate_code']} - {city['name']}", city["plate_code"])
        except Exception:  # noqa: BLE001
            pass
        self.cmb_city.blockSignals(False)
        self._load_districts()

    def _load_districts(self):
        self.cmb_district.blockSignals(True)
        self.cmb_district.clear()
        self.cmb_district.addItem("— İlçe Seçin —", "")
        plate = self.cmb_city.currentData()
        if plate:
            try:
                districts = self.master_store.get_districts(city_plate=plate, active_only=True)
                for d in districts:
                    self.cmb_district.addItem(d["name"], d["name"])
            except Exception:  # noqa: BLE001
                pass
        self.cmb_district.blockSignals(False)

    # ------------------------------------------------------------------ Sayfa 2: Yetkili & Ortaklar
    def _build_page_people(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(12)

        lyt.addWidget(QLabel("<h3>Adım 2: Yetkili ve Ortak Tanımları</h3>"))

        # Yetkililer
        box_y = QGroupBox("Yetkili Kişiler")
        lyt_y = QVBoxLayout(box_y)
        bar_y = QHBoxLayout()
        btn_add_y = QPushButton("➕ Yetkili Ekle")
        btn_add_y.clicked.connect(self._on_add_yetkili)
        btn_edit_y = QPushButton("✏️ Düzenle")
        btn_edit_y.clicked.connect(self._on_edit_yetkili)
        btn_del_y = QPushButton("🗑️ Sil")
        btn_del_y.clicked.connect(self._on_del_yetkili)
        bar_y.addWidget(QLabel("Şirket yetkilileri / irtibat kişileri:"))
        bar_y.addStretch()
        bar_y.addWidget(btn_add_y)
        bar_y.addWidget(btn_edit_y)
        bar_y.addWidget(btn_del_y)
        lyt_y.addLayout(bar_y)

        self.tbl_yetkili = QTableView()
        self.model_yetkili = QStandardItemModel(0, 4)
        self.model_yetkili.setHorizontalHeaderLabels(["Ad Soyad", "Ünvan", "Telefon", "E-Posta"])
        self.tbl_yetkili.setModel(self.model_yetkili)
        self.tbl_yetkili.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_yetkili.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tbl_yetkili.doubleClicked.connect(self._on_edit_yetkili)
        lyt_y.addWidget(self.tbl_yetkili)
        lyt.addWidget(box_y)

        # Ortaklar
        box_o = QGroupBox("Şirket Ortakları")
        lyt_o = QVBoxLayout(box_o)
        bar_o = QHBoxLayout()
        btn_add_o = QPushButton("➕ Ortak Ekle")
        btn_add_o.clicked.connect(self._on_add_ortak)
        btn_edit_o = QPushButton("✏️ Düzenle")
        btn_edit_o.clicked.connect(self._on_edit_ortak)
        btn_del_o = QPushButton("🗑️ Sil")
        btn_del_o.clicked.connect(self._on_del_ortak)
        bar_o.addWidget(QLabel("Hissedar ve ortaklar:"))
        bar_o.addStretch()
        bar_o.addWidget(btn_add_o)
        bar_o.addWidget(btn_edit_o)
        bar_o.addWidget(btn_del_o)
        lyt_o.addLayout(bar_o)

        self.tbl_ortak = QTableView()
        self.model_ortak = QStandardItemModel(0, 4)
        self.model_ortak.setHorizontalHeaderLabels(["Ad Soyad / Ünvan", "TC / Vergi No", "Pay Oranı (%)", "Görevi"])
        self.tbl_ortak.setModel(self.model_ortak)
        self.tbl_ortak.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_ortak.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tbl_ortak.doubleClicked.connect(self._on_edit_ortak)
        lyt_o.addWidget(self.tbl_ortak)
        lyt.addWidget(box_o)

        return w

    def _on_add_yetkili(self):
        dlg = YetkiliEkleDialog(parent=self)
        if dlg.exec():
            self.yetkililer.append(dlg.deger())
            self._refresh_yetkili_table()

    def _on_edit_yetkili(self):
        idx = self.tbl_yetkili.currentIndex().row()
        if idx < 0 or idx >= len(self.yetkililer):
            QMessageBox.information(self, "Seçim Yapın", "Lütfen düzenlenecek yetkiliyi seçin.")
            return
        dlg = YetkiliEkleDialog(deger=self.yetkililer[idx], parent=self)
        if dlg.exec():
            self.yetkililer[idx] = dlg.deger()
            self._refresh_yetkili_table()

    def _on_del_yetkili(self):
        idx = self.tbl_yetkili.currentIndex().row()
        if idx >= 0 and idx < len(self.yetkililer):
            del self.yetkililer[idx]
            self._refresh_yetkili_table()

    def _refresh_yetkili_table(self):
        self.model_yetkili.removeRows(0, self.model_yetkili.rowCount())
        for y in self.yetkililer:
            row = [
                QStandardItem(y.get("ad_soyad", "")),
                QStandardItem(y.get("unvan", "")),
                QStandardItem(y.get("telefon", "")),
                QStandardItem(y.get("e_posta", "")),
            ]
            for it in row:
                it.setEditable(False)
            self.model_yetkili.appendRow(row)

    def _on_add_ortak(self):
        dlg = OrtakEkleDialog(parent=self)
        if dlg.exec():
            self.ortaklar.append(dlg.deger())
            self._refresh_ortak_table()

    def _on_edit_ortak(self):
        idx = self.tbl_ortak.currentIndex().row()
        if idx < 0 or idx >= len(self.ortaklar):
            QMessageBox.information(self, "Seçim Yapın", "Lütfen düzenlenecek ortağı seçin.")
            return
        dlg = OrtakEkleDialog(deger=self.ortaklar[idx], parent=self)
        if dlg.exec():
            self.ortaklar[idx] = dlg.deger()
            self._refresh_ortak_table()

    def _on_del_ortak(self):
        idx = self.tbl_ortak.currentIndex().row()
        if idx >= 0 and idx < len(self.ortaklar):
            del self.ortaklar[idx]
            self._refresh_ortak_table()

    def _refresh_ortak_table(self):
        self.model_ortak.removeRows(0, self.model_ortak.rowCount())
        for o in self.ortaklar:
            row = [
                QStandardItem(o.get("ad_soyad", "")),
                QStandardItem(o.get("tc_vergi_no", "")),
                QStandardItem(o.get("pay_orani", "")),
                QStandardItem(o.get("gorev", "")),
            ]
            for it in row:
                it.setEditable(False)
            self.model_ortak.appendRow(row)

    # ------------------------------------------------------------------ Sayfa 3: Çalışma Dönemi (Zorunlu)
    def _build_page_donem(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(12)

        lyt.addWidget(QLabel("<h3>Adım 3: Çalışma Dönemi Tanımları (Zorunlu)</h3>"))
        desc = QLabel(
            "Muhasebe ve ticari hareketlerin kaydedilebilmesi için şirketin en az bir çalışma dönemine ihtiyacı vardır.\n"
            "Sistem, bilgisayarınızın tarihine göre geçerli mali yılı otomatik olarak aşağıya eklemiştir.",
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #475569; font-size: 11px;")
        lyt.addWidget(desc)

        box = QGroupBox("Mali Çalışma Dönemleri")
        b_lyt = QVBoxLayout(box)

        bar = QHBoxLayout()
        btn_add = QPushButton("➕ Dönem Ekle")
        btn_add.clicked.connect(self._on_add_donem)
        btn_edit = QPushButton("✏️ Düzenle")
        btn_edit.clicked.connect(self._on_edit_donem)
        btn_del = QPushButton("🗑️ Sil")
        btn_del.clicked.connect(self._on_del_donem)

        bar.addWidget(QLabel("<b>Tanımlı Dönemler (En az 1 dönem zorunludur):</b>"))
        bar.addStretch()
        bar.addWidget(btn_add)
        bar.addWidget(btn_edit)
        bar.addWidget(btn_del)
        b_lyt.addLayout(bar)

        self.tbl_donem = QTableView()
        self.model_donem = QStandardItemModel(0, 4)
        self.model_donem.setHorizontalHeaderLabels(["Dönem Adı / Kodu", "Başlangıç Tarihi", "Bitiş Tarihi", "Durum"])
        self.tbl_donem.setModel(self.model_donem)
        self.tbl_donem.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_donem.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tbl_donem.doubleClicked.connect(self._on_edit_donem)
        b_lyt.addWidget(self.tbl_donem)

        lyt.addWidget(box)
        self._refresh_donem_table()
        return w

    def _on_add_donem(self):
        dlg = DonemEkleDialog(parent=self)
        if dlg.exec():
            self.donemler.append(dlg.deger())
            self._refresh_donem_table()

    def _on_edit_donem(self):
        idx = self.tbl_donem.currentIndex().row()
        if idx < 0 or idx >= len(self.donemler):
            QMessageBox.information(self, "Seçim Yapın", "Lütfen düzenlenecek dönemi seçin.")
            return
        dlg = DonemEkleDialog(deger=self.donemler[idx], parent=self)
        if dlg.exec():
            self.donemler[idx] = dlg.deger()
            self._refresh_donem_table()

    def _on_del_donem(self):
        idx = self.tbl_donem.currentIndex().row()
        if idx >= 0 and idx < len(self.donemler):
            if len(self.donemler) <= 1:
                QMessageBox.warning(self, "Uyarı", "Şirket kurulumu için en az bir çalışma dönemi bulunmalıdır.")
                return
            del self.donemler[idx]
            self._refresh_donem_table()

    def _refresh_donem_table(self):
        self.model_donem.removeRows(0, self.model_donem.rowCount())
        for d in self.donemler:
            row = [
                QStandardItem(d.get("ad", "")),
                QStandardItem(d.get("baslangic", "")),
                QStandardItem(d.get("bitis", "")),
                QStandardItem(d.get("aktif", "Evet")),
            ]
            for it in row:
                it.setEditable(False)
            self.model_donem.appendRow(row)

    # ------------------------------------------------------------------ Sayfa 4: Şube & Depo (Zorunlu)
    def _build_page_sube_depo(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(12)

        lyt.addWidget(QLabel("<h3>Adım 4: Şube ve Depo Tanımları (Zorunlu)</h3>"))
        desc = QLabel(
            "Faturalandırma, stok hareketleri ve işlemler için firmanın en az 1 şube ve 1 deposu bulunmalıdır.\n"
            "Varsayılan 'Merkez Şube' ve 'Merkez Depo' otomatik hazırlanmıştır; dilediğiniz gibi düzenleyebilir veya yeni ekleyebilirsiniz.",
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #475569; font-size: 11px;")
        lyt.addWidget(desc)

        # Şubeler
        box_s = QGroupBox("Şubeler (En az 1 şube zorunludur)")
        lyt_s = QVBoxLayout(box_s)
        bar_s = QHBoxLayout()
        btn_add_s = QPushButton("➕ Şube Ekle")
        btn_add_s.clicked.connect(self._on_add_sube)
        btn_edit_s = QPushButton("✏️ Düzenle")
        btn_edit_s.clicked.connect(self._on_edit_sube)
        btn_del_s = QPushButton("🗑️ Sil")
        btn_del_s.clicked.connect(self._on_del_sube)
        bar_s.addWidget(QLabel("Firma Şubeleri:"))
        bar_s.addStretch()
        bar_s.addWidget(btn_add_s)
        bar_s.addWidget(btn_edit_s)
        bar_s.addWidget(btn_del_s)
        lyt_s.addLayout(bar_s)

        self.tbl_sube = QTableView()
        self.model_sube = QStandardItemModel(0, 4)
        self.model_sube.setHorizontalHeaderLabels(["Şube Kodu", "Şube Adı", "Yetkili", "Durum"])
        self.tbl_sube.setModel(self.model_sube)
        self.tbl_sube.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_sube.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tbl_sube.doubleClicked.connect(self._on_edit_sube)
        lyt_s.addWidget(self.tbl_sube)
        lyt.addWidget(box_s)

        # Depolar
        box_d = QGroupBox("Depolar (En az 1 depo zorunludur)")
        lyt_d = QVBoxLayout(box_d)
        bar_d = QHBoxLayout()
        btn_add_d = QPushButton("➕ Depo Ekle")
        btn_add_d.clicked.connect(self._on_add_depo)
        btn_edit_d = QPushButton("✏️ Düzenle")
        btn_edit_d.clicked.connect(self._on_edit_depo)
        btn_del_d = QPushButton("🗑️ Sil")
        btn_del_d.clicked.connect(self._on_del_depo)
        bar_d.addWidget(QLabel("Firma Depoları:"))
        bar_d.addStretch()
        bar_d.addWidget(btn_add_d)
        bar_d.addWidget(btn_edit_d)
        bar_d.addWidget(btn_del_d)
        lyt_d.addLayout(bar_d)

        self.tbl_depo = QTableView()
        self.model_depo = QStandardItemModel(0, 4)
        self.model_depo.setHorizontalHeaderLabels(["Depo Kodu", "Depo Adı", "Adres / Konum", "Durum"])
        self.tbl_depo.setModel(self.model_depo)
        self.tbl_depo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_depo.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tbl_depo.doubleClicked.connect(self._on_edit_depo)
        lyt_d.addWidget(self.tbl_depo)
        lyt.addWidget(box_d)

        self._refresh_sube_table()
        self._refresh_depo_table()
        return w

    def _on_add_sube(self):
        dlg = SubeEkleDialog(parent=self)
        if dlg.exec():
            self.subeler.append(dlg.deger())
            self._refresh_sube_table()

    def _on_edit_sube(self):
        idx = self.tbl_sube.currentIndex().row()
        if idx < 0 or idx >= len(self.subeler):
            QMessageBox.information(self, "Seçim Yapın", "Lütfen düzenlenecek şubeyi seçin.")
            return
        dlg = SubeEkleDialog(deger=self.subeler[idx], parent=self)
        if dlg.exec():
            self.subeler[idx] = dlg.deger()
            self._refresh_sube_table()

    def _on_del_sube(self):
        idx = self.tbl_sube.currentIndex().row()
        if idx >= 0 and idx < len(self.subeler):
            if len(self.subeler) <= 1:
                QMessageBox.warning(self, "Uyarı", "Şirket kurulumu için en az 1 şube zorunludur.")
                return
            del self.subeler[idx]
            self._refresh_sube_table()

    def _refresh_sube_table(self):
        self.model_sube.removeRows(0, self.model_sube.rowCount())
        for s in self.subeler:
            row = [
                QStandardItem(s.get("code", "")),
                QStandardItem(s.get("name", "")),
                QStandardItem(s.get("yetkili", "")),
                QStandardItem(s.get("durum", "Aktif")),
            ]
            for it in row:
                it.setEditable(False)
            self.model_sube.appendRow(row)

    def _on_add_depo(self):
        dlg = DepoEkleDialog(parent=self)
        if dlg.exec():
            self.depolar.append(dlg.deger())
            self._refresh_depo_table()

    def _on_edit_depo(self):
        idx = self.tbl_depo.currentIndex().row()
        if idx < 0 or idx >= len(self.depolar):
            QMessageBox.information(self, "Seçim Yapın", "Lütfen düzenlenecek depoyu seçin.")
            return
        dlg = DepoEkleDialog(deger=self.depolar[idx], parent=self)
        if dlg.exec():
            self.depolar[idx] = dlg.deger()
            self._refresh_depo_table()

    def _on_del_depo(self):
        idx = self.tbl_depo.currentIndex().row()
        if idx >= 0 and idx < len(self.depolar):
            if len(self.depolar) <= 1:
                QMessageBox.warning(self, "Uyarı", "Şirket kurulumu için en az 1 depo zorunludur.")
                return
            del self.depolar[idx]
            self._refresh_depo_table()

    def _refresh_depo_table(self):
        self.model_depo.removeRows(0, self.model_depo.rowCount())
        for d in self.depolar:
            row = [
                QStandardItem(d.get("code", "")),
                QStandardItem(d.get("name", "")),
                QStandardItem(d.get("address", "")),
                QStandardItem(d.get("durum", "Aktif")),
            ]
            for it in row:
                it.setEditable(False)
            self.model_depo.appendRow(row)

    # ------------------------------------------------------------------ Sayfa 5: Banka Hesapları
    def _build_page_bank(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(12)

        lyt.addWidget(QLabel("<h3>Adım 5: Banka Hesap Tanımları (İsteğe Bağlı)</h3>"))
        lyt.addWidget(QLabel("Faturalar ve ödeme planlarında görünecek banka hesaplarını buradan ekleyebilirsiniz."))

        box = QGroupBox("Banka Hesapları")
        b_lyt = QVBoxLayout(box)

        bar = QHBoxLayout()
        btn_add = QPushButton("➕ Banka Hesabı Ekle")
        btn_add.clicked.connect(self._on_add_bank)
        btn_edit = QPushButton("✏️ Düzenle")
        btn_edit.clicked.connect(self._on_edit_bank)
        btn_del = QPushButton("🗑️ Sil")
        btn_del.clicked.connect(self._on_del_bank)

        bar.addWidget(QLabel("Tanımlı Banka Hesapları:"))
        bar.addStretch()
        bar.addWidget(btn_add)
        bar.addWidget(btn_edit)
        bar.addWidget(btn_del)
        b_lyt.addLayout(bar)

        self.tbl_bank = QTableView()
        self.model_bank = QStandardItemModel(0, 5)
        self.model_bank.setHorizontalHeaderLabels(["Banka", "Şube", "Hesap No", "IBAN", "Para Birimi"])
        self.tbl_bank.setModel(self.model_bank)
        self.tbl_bank.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_bank.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tbl_bank.doubleClicked.connect(self._on_edit_bank)
        b_lyt.addWidget(self.tbl_bank)

        lyt.addWidget(box)
        return w

    def _on_add_bank(self):
        dlg = BankaHesabiEkleDialog(parent=self)
        if dlg.exec():
            self.bankalar.append(dlg.deger())
            self._refresh_bank_table()

    def _on_edit_bank(self):
        idx = self.tbl_bank.currentIndex().row()
        if idx < 0 or idx >= len(self.bankalar):
            QMessageBox.information(self, "Seçim Yapın", "Lütfen düzenlenecek banka hesabını seçin.")
            return
        dlg = BankaHesabiEkleDialog(deger=self.bankalar[idx], parent=self)
        if dlg.exec():
            self.bankalar[idx] = dlg.deger()
            self._refresh_bank_table()

    def _on_del_bank(self):
        idx = self.tbl_bank.currentIndex().row()
        if idx >= 0 and idx < len(self.bankalar):
            del self.bankalar[idx]
            self._refresh_bank_table()

    def _refresh_bank_table(self):
        self.model_bank.removeRows(0, self.model_bank.rowCount())
        for b in self.bankalar:
            row = [
                QStandardItem(b.get("banka", "")),
                QStandardItem(b.get("sube", "")),
                QStandardItem(b.get("hesap_no", "")),
                QStandardItem(b.get("iban", "")),
                QStandardItem(b.get("para_birimi", "TRY")),
            ]
            for it in row:
                it.setEditable(False)
            self.model_bank.appendRow(row)

    # ------------------------------------------------------------------ Sayfa 6: Ölçü Birimleri & Şablonlar
    def _build_page_starter_pack(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(12)

        header = QLabel("<h3>Adım 6: Ölçü Birimleri, Belge Numaralama ve Şablonlar</h3>")
        lyt.addWidget(header)

        # 1. Ölçü Birimleri Kutusu
        unit_box = QGroupBox("📦 Standart Ölçü Birimleri Havuzu")
        u_lyt = QVBoxLayout(unit_box)

        self.chk_enable_units = QCheckBox("Standart Ölçü Birimlerini Şirkete Dahil Et (Adet, Kg, Metre, Litre, Paket, Koli...)")
        self.chk_enable_units.setChecked(True)
        self.chk_enable_units.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 12px;")
        u_lyt.addWidget(self.chk_enable_units)

        bar = QHBoxLayout()
        btn_add = QPushButton("➕ Birim Ekle")
        btn_add.clicked.connect(self._on_add_unit)
        btn_edit = QPushButton("✏️ Düzenle")
        btn_edit.clicked.connect(self._on_edit_unit)
        btn_del = QPushButton("🗑️ Sil")
        btn_del.clicked.connect(self._on_del_unit)

        bar.addWidget(QLabel("Aktif Ölçü Birimleri Listesi:"))
        bar.addStretch()
        bar.addWidget(btn_add)
        bar.addWidget(btn_edit)
        bar.addWidget(btn_del)
        u_lyt.addLayout(bar)

        self.tbl_unit = QTableView()
        self.model_unit = QStandardItemModel(0, 5)
        self.model_unit.setHorizontalHeaderLabels(["Birim Kodu", "Birim Adı", "Sembol", "Birim Türü", "Durum"])
        self.tbl_unit.setModel(self.model_unit)
        self.tbl_unit.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_unit.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.tbl_unit.doubleClicked.connect(self._on_edit_unit)
        u_lyt.addWidget(self.tbl_unit)

        self._refresh_unit_table()
        lyt.addWidget(unit_box, 1)

        # 2. Form Tasarımları & Belge Numaralandırma Kutusu
        series_box = QGroupBox("📄 Belge Numaralandırma & Görsel Form Şablonları")
        s_lyt = QVBoxLayout(series_box)

        self.chk_enable_series = QCheckBox("Standart Belge Numaralandırma Serilerini Otomatik Oluştur (TEK-, SIP-, IRS-, FAT-, Fişler)")
        self.chk_enable_series.setChecked(True)
        self.chk_enable_series.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 12px;")
        s_lyt.addWidget(self.chk_enable_series)

        self.chk_enable_templates = QCheckBox("Standart Görsel Form Tasarımlarını (Teklif, Fatura, İrsaliye, Kasa Fişi) Hazırla")
        self.chk_enable_templates.setChecked(True)
        self.chk_enable_templates.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 12px;")
        s_lyt.addWidget(self.chk_enable_templates)

        info_lbl = QLabel(
            "💡 <b>Otomatik Hazırlık:</b> Şirketiniz kurulduğunda Satış Teklifi, Sipariş, İrsaliye, e-Fatura/e-Arşiv "
            "ve Kasa/Banka/Stok fişi için resmi mevzuata uygun standart numaralandırma şablonları ve hazır form baskı "
            "tasarımları anında kullanıma hazır hale getirilir.",
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet("background: #f1f5f9; padding: 10px; border-radius: 6px; color: #334155; font-size: 11px;")
        s_lyt.addWidget(info_lbl)

        lyt.addWidget(series_box)
        return w

    def _on_add_unit(self):
        dlg = BirimEkleDialog(parent=self)
        if dlg.exec():
            self.birimler.append(dlg.deger())
            self._refresh_unit_table()

    def _on_edit_unit(self):
        idx = self.tbl_unit.currentIndex().row()
        if idx < 0 or idx >= len(self.birimler):
            QMessageBox.information(self, "Seçim Yapın", "Lütfen düzenlenecek ölçü birimini seçin.")
            return
        dlg = BirimEkleDialog(deger=self.birimler[idx], parent=self)
        if dlg.exec():
            self.birimler[idx] = dlg.deger()
            self._refresh_unit_table()

    def _on_del_unit(self):
        idx = self.tbl_unit.currentIndex().row()
        if idx >= 0 and idx < len(self.birimler):
            del self.birimler[idx]
            self._refresh_unit_table()

    def _refresh_unit_table(self):
        self.model_unit.removeRows(0, self.model_unit.rowCount())
        for u in self.birimler:
            row = [
                QStandardItem(u.get("code", "")),
                QStandardItem(u.get("name", "")),
                QStandardItem(u.get("symbol", "")),
                QStandardItem(u.get("unit_type", "")),
                QStandardItem(u.get("durum", "Aktif")),
            ]
            for it in row:
                it.setEditable(False)
            self.model_unit.appendRow(row)

    # ------------------------------------------------------------------ Sayfa 7: Özet & Tamamlama
    def _build_page_summary(self) -> QWidget:
        w = QWidget()
        lyt = QVBoxLayout(w)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(12)

        lyt.addWidget(QLabel("<h3>Adım 7: Şirket Kurulum Özeti & Onay</h3>"))

        self.summary_box = QLabel()
        self.summary_box.setStyleSheet(
            "background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; "
            "padding: 16px; font-size: 12px; line-height: 1.5;",
        )
        self.summary_box.setWordWrap(True)
        lyt.addWidget(self.summary_box)

        ready_lbl = QLabel("✅ Tüm zorunlu ve başlangıç alanları hazırlandı. 'Şirketi Kur ve Aktifleştir' butonuna basarak sistemi kullanmaya başlayabilirsiniz.")
        ready_lbl.setStyleSheet("color: #16a34a; font-weight: 700; font-size: 12px;")
        lyt.addWidget(ready_lbl)

        lyt.addStretch()
        return w

    def _update_summary_page(self):
        il_adi = self.cmb_city.currentText() if self.cmb_city.currentData() else "—"
        ilce_adi = self.cmb_district.currentText() if self.cmb_district.currentData() else "—"

        units_status = f"{len(self.birimler)} Tanımlı Birim (Aktif edilecek)" if self.chk_enable_units.isChecked() else "Dahil edilmedi"
        series_status = "Standart 10 Belge Serisi + Görsel Formlar Hazır" if self.chk_enable_series.isChecked() else "Manuel oluşturulacak"

        html = f"""
        <table style="width:100%; border-collapse: collapse;">
            <tr><td style="width:30%; font-weight:bold; color:#475569;">Firma Kodu:</td><td style="color:#0f172a; font-weight:bold;">{self.txt_code.text()}</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Firma Kısa Adı:</td><td style="color:#0f172a; font-weight:bold;">{self.txt_short_name.text()}</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Resmi Ünvan:</td><td>{self.txt_title.text() or '—'}</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Çalışma Para Birimi:</td><td style="color:#2563eb; font-weight:bold;">{self.cmb_currency.currentText()}</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Şirket Tipi:</td><td>{self.cmb_company_type.currentText()}</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Vergi Dairesi / No:</td><td>{self.txt_tax_office.text() or '—'} / {self.txt_tax_number.text() or '—'}</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Lokasyon:</td><td>{il_adi} / {ilce_adi}</td></tr>
            <tr style="border-top:1px solid #e2e8f0;"><td style="font-weight:bold; color:#475569; padding-top:8px;">Tanımlı Dönemler:</td><td style="padding-top:8px;">{len(self.donemler)} Dönem ({", ".join(d['ad'] for d in self.donemler)})</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Tanımlı Şubeler:</td><td>{len(self.subeler)} Şube ({", ".join(s['name'] for s in self.subeler)})</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Tanımlı Depolar:</td><td>{len(self.depolar)} Depo ({", ".join(d['name'] for d in self.depolar)})</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Yetkili & Ortaklar:</td><td>{len(self.yetkililer)} Yetkili, {len(self.ortaklar)} Ortak</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Banka Hesapları:</td><td>{len(self.bankalar)} Hesap</td></tr>
            <tr style="border-top:1px solid #e2e8f0;"><td style="font-weight:bold; color:#475569; padding-top:8px;">Ölçü Birimleri:</td><td style="padding-top:8px; color:#0369a1; font-weight:600;">{units_status}</td></tr>
            <tr><td style="font-weight:bold; color:#475569;">Belge & Form Serileri:</td><td style="color:#0369a1; font-weight:600;">{series_status}</td></tr>
        </table>
        """
        self.summary_box.setText(html)

    # ------------------------------------------------------------------ Navigasyon & Doğrulama
    def _init_defaults(self):
        # Otomatik bir sonraki firma kodunu öner
        try:
            firmalar = self.service.list_companies()
            max_code = 0
            for f in firmalar:
                if f.code and f.code.isdigit():
                    max_code = max(max_code, int(f.code))
            next_code = f"{max_code + 1:03d}"
            self.txt_code.setText(next_code)
        except Exception:  # noqa: BLE001
            self.txt_code.setText("001")

    def _goto_step(self, step_idx: int):
        self.stack.setCurrentIndex(step_idx)
        for i, btn in enumerate(self.step_buttons):
            if i == step_idx:
                btn.setStyleSheet(
                    "QPushButton { text-align: left; padding: 10px 12px; border-radius: 6px; "
                    "font-size: 12px; font-weight: 700; color: #ffffff; background: #2563eb; border: none; }",
                )
            elif i < step_idx:
                btn.setStyleSheet(
                    "QPushButton { text-align: left; padding: 10px 12px; border-radius: 6px; "
                    "font-size: 12px; font-weight: 600; color: #38bdf8; background: #1e293b; border: none; }",
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { text-align: left; padding: 10px 12px; border-radius: 6px; "
                    "font-size: 12px; font-weight: 600; color: #64748b; background: transparent; border: none; }",
                )

        self.btn_prev.setEnabled(step_idx > 0)
        if step_idx == self.stack.count() - 1:
            self._update_summary_page()
            self.btn_next.setText("🚀 Şirketi Kur ve Aktifleştir")
            self.btn_next.setStyleSheet("background: #16a34a; color: #ffffff; font-weight: 800; padding: 8px 24px; border-radius: 6px; border: none;")
        else:
            self.btn_next.setText("İleri ▶")
            self.btn_next.setStyleSheet("background: #2563eb; color: #ffffff; font-weight: 700; padding: 8px 24px; border-radius: 6px; border: none;")

    def _validate_current_step(self) -> bool:
        cur = self.stack.currentIndex()
        if cur == 0:
            if not self.txt_code.text().strip():
                QMessageBox.warning(self, "Zorunlu Alan", "Lütfen Firma Kodu alanını doldurun.")
                self.txt_code.setFocus()
                return False
            if not self.txt_short_name.text().strip():
                QMessageBox.warning(self, "Zorunlu Alan", "Lütfen Firma Kısa Adı alanını doldurun.")
                self.txt_short_name.setFocus()
                return False
            if not self.cmb_currency.currentText().strip():
                QMessageBox.warning(self, "Zorunlu Alan", "Lütfen Çalışma Para Birimini seçin.")
                return False
            # Kod çakışma kontrolü
            kod = self.txt_code.text().strip()
            if self.service.get_by_code(kod):
                QMessageBox.warning(self, "Kod Çakışması", f"'{kod}' kodlu firma sistemde zaten kayıtlı.")
                self.txt_code.setFocus()
                return False
        elif cur == 2:
            if not self.donemler:
                QMessageBox.warning(self, "Zorunlu Alan", "Şirket kurulumu için en az bir çalışma dönemi eklemelisiniz.")
                return False
        elif cur == 3:
            if not self.subeler:
                QMessageBox.warning(self, "Zorunlu Alan", "En az bir şube tanımlanmalıdır.")
                return False
            if not self.depolar:
                QMessageBox.warning(self, "Zorunlu Alan", "En az bir depo tanımlanmalıdır.")
                return False
        return True

    def _on_next(self):
        if not self._validate_current_step():
            return
        cur = self.stack.currentIndex()
        if cur < self.stack.count() - 1:
            self._goto_step(cur + 1)
        else:
            self._save_and_finish()

    def _on_prev(self):
        cur = self.stack.currentIndex()
        if cur > 0:
            self._goto_step(cur - 1)

    # ------------------------------------------------------------------ Kurulumu Tamamla
    def _save_and_finish(self):
        """Toplanan tüm verileri atomic olarak kaydeder ve şirketi aktif yapar."""
        payload = {
            "code": self.txt_code.text().strip(),
            "short_name": self.txt_short_name.text().strip(),
            "title": self.txt_title.text().strip() or None,
            "company_type": self.cmb_company_type.currentText(),
            "default_currency": self.cmb_currency.currentText(),
            "tax_office": self.txt_tax_office.text().strip() or None,
            "tax_number": self.txt_tax_number.text().strip() or None,
            "country": self.cmb_country.currentText(),
            "city": self.cmb_city.currentText().split(" - ", 1)[-1] if self.cmb_city.currentData() else None,
            "district": self.cmb_district.currentText() if self.cmb_district.currentData() else None,
            "address": self.txt_address.toPlainText().strip() or None,
            "phone1": self.txt_phone.text().strip() or None,
            "email": self.txt_email.text().strip() or None,
            "authorized_persons": self.yetkililer,
            "partners": self.ortaklar,
            "bank_accounts": self.bankalar,
            "periods": self.donemler,
            "is_active": True,
        }

        res = self.service.save(payload)
        if not res.success:
            QMessageBox.critical(self, "Kurulum Hatası", res.error or "Şirket kaydedilemedi.")
            return

        cid = res.company_id
        self.created_company_id = cid

        try:
            # 1. Şubeleri kaydet
            sube_svc = SubeService(self.db)
            for s in self.subeler:
                sube_svc.kaydet(cid, {
                    "code": s["code"],
                    "name": s["name"],
                    "yetkili": s.get("yetkili") or None,
                    "is_active": s.get("is_active", True),
                })

            # 2. Depoları kaydet
            for d in self.depolar:
                self.db.add(WarehouseDefinition(
                    company_id=cid,
                    code=d["code"],
                    name=d["name"],
                    address=d.get("address") or None,
                    is_active=d.get("is_active", True),
                ))
            self.db.commit()

            # 3. Belge Numaralandırma Serilerini Otomatik Oluştur
            created_series_count = 0
            if hasattr(self, "chk_enable_series") and self.chk_enable_series.isChecked():
                series = ensure_default_series(self.db, company_id=cid)
                created_series_count = len(series)

            # 4. Ölçü Birimlerini Kaydet/Garantiye Al
            if hasattr(self, "chk_enable_units") and self.chk_enable_units.isChecked():
                try:
                    for u in self.birimler:
                        try:
                            self.master_store.add_unit(
                                code=u["code"],
                                name=u["name"],
                                symbol=u.get("symbol", u["name"]),
                                unit_type=u.get("unit_type", "adet"),
                            )
                        except Exception:  # noqa: BLE001
                            pass  # Zaten kayıtlıysa devam et
                except Exception:  # noqa: BLE001
                    pass

            # 5. Otomatik Aktif Şirket Seçimi
            self.service.aktif_firma_sec(cid)

            QMessageBox.information(
                self,
                "Kurulum Başarılı! 🎉",
                f"<b>{payload['short_name']}</b> şirketi başarıyla kuruldu ve aktif şirket olarak seçildi.\n\n"
                f"• {len(self.donemler)} Çalışma Dönemi\n"
                f"• {len(self.subeler)} Şube\n"
                f"• {len(self.depolar)} Depo\n"
                f"• {len(self.birimler)} Ölçü Birimi\n"
                f"• {created_series_count} Belge Numaralandırma Serisi\n\n"
                "Artık tüm ERP modüllerini kullanmaya başlayabilirsiniz.",
            )
            self.accept()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Şube/Depo/Seri kurulumu sırasında hata")
            self.db.rollback()
            QMessageBox.critical(self, "Hata", f"Alt tanımlar kaydedilirken hata oluştu: {exc}")

