"""TOYA ERP - Belge ve Seri Numaralandırma Yönetim Bileşeni (DocumentNumberingWidget).

Her firma için belge (Teklif, Sipariş, İrsaliye, Fatura) ve fiş (Cari, Kasa, Banka, Stok) serilerini,
şablonlarını, sayaçlarını ve e-Fatura / GİB standartlarını yönetir.
"""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QStandardItem
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import Company, DocumentSeries
from src.desktop.services import numara_servisi as ns
from src.desktop.ui.components.button_style import btn_style
from src.desktop.ui.components.dialog_style import (
    apply_light_dialog_style,
    onay,
    uyari,
)
from src.desktop.ui.components.entry_table_view import standart_grid


class DocumentNumberingWidget(QWidget):
    """Genel Ayarlar içi Belge ve Seri Numaralandırma Paneli."""

    toast_requested = pyqtSignal(str, str)

    def __init__(self, db_session=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self._series_list: list[DocumentSeries] = []
        self._init_ui()
        self._ensure_seed()
        self.load_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Bilgi Başlığı
        header = QFrame()
        header.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #cbd5e1; "
            "border-radius: 6px; padding: 6px 10px;",
        )
        h_lyt = QHBoxLayout(header)
        h_lyt.setContentsMargins(0, 0, 0, 0)
        lbl_info = QLabel(
            "🔢 <b>Belge & Seri Numaralandırma</b> — Tüm evrak ve fişler için "
            "firma bazlı serileri, şablonları, sayaçları ve e-Fatura / GİB "
            "uyumluluklarını yönetebilirsiniz.",
        )
        lbl_info.setStyleSheet("color: #0f172a; font-size: 11px;")
        h_lyt.addWidget(lbl_info)
        layout.addWidget(header)

        # Filtre ve Aksiyon Barı (Kompakt 2-satırlı düzen - 1366x768 uyumlu)
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(6)

        lbl_c = QLabel("Firma:")
        lbl_c.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.cmb_company = QComboBox()
        self.cmb_company.addItem("Tüm Firmalar / Genel", None)
        self._load_companies()
        self.cmb_company.currentIndexChanged.connect(self.load_data)

        lbl_t = QLabel("Belge Türü:")
        lbl_t.setStyleSheet("font-weight: bold; font-size: 11px;")
        self.cmb_type = QComboBox()
        self.cmb_type.addItem("Tüm Belge & Fişler", None)
        for code, name in ns.ADLAR.items():
            self.cmb_type.addItem(name, code)
        self.cmb_type.currentIndexChanged.connect(self.load_data)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Seri ara (kod / şablon / ad)...")
        self.txt_search.textChanged.connect(self.load_data)

        filter_bar.addWidget(lbl_c)
        filter_bar.addWidget(self.cmb_company)
        filter_bar.addWidget(lbl_t)
        filter_bar.addWidget(self.cmb_type)
        filter_bar.addWidget(self.txt_search, 1)
        layout.addLayout(filter_bar)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(6)

        btn_add = QPushButton("➕ Yeni Seri")
        btn_add.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        btn_add.clicked.connect(self._on_add)

        btn_edit = QPushButton("✏️ Düzenle")
        btn_edit.setStyleSheet(btn_style("#ffffff", "#2563eb"))
        btn_edit.clicked.connect(self._on_edit)

        btn_default = QPushButton("⭐ Varsayılan Yap")
        btn_default.setStyleSheet(btn_style("#ffffff", "#0284c7"))
        btn_default.clicked.connect(self._on_set_default)

        btn_gaps = QPushButton("🔍 Boşluk Analizi")
        btn_gaps.setStyleSheet(btn_style("#f8fafc", "#475569"))
        btn_gaps.clicked.connect(self._on_gaps_dialog)

        btn_del = QPushButton("🗑️ Sil")
        btn_del.setStyleSheet(btn_style("#ffffff", "#dc2626"))
        btn_del.clicked.connect(self._on_delete)

        action_bar.addWidget(btn_add)
        action_bar.addWidget(btn_edit)
        action_bar.addWidget(btn_default)
        action_bar.addWidget(btn_gaps)
        action_bar.addStretch()
        action_bar.addWidget(btn_del)
        layout.addLayout(action_bar)

        # Standart Grid Tablosu
        self.grid = standart_grid(
            "def_doc_series",
            [
                ("belge_turu", "BELGE TÜRÜ"),
                ("seri_kodu", "SERİ"),
                ("seri_adi", "SERİ AÇIKLAMASI"),
                ("sablon", "NUMARA ŞABLONU"),
                ("ornek_no", "SIRADAKİ NUMARA"),
                ("efatura", "E-BELGE (GİB)"),
                ("is_default", "VARSAYILAN"),
                ("is_active", "DURUM"),
            ],
        )
        self.grid.table_view.doubleClicked.connect(self._on_edit)
        layout.addWidget(self.grid, 1)

    def _load_companies(self) -> None:
        if not self.db:
            return
        try:
            comps = self.db.scalars(select(Company).order_by(Company.short_name)).all()
            for c in comps:
                self.cmb_company.addItem(f"{c.short_name} ({c.code})", c.id)
        except Exception:
            pass

    def _ensure_seed(self) -> None:
        if not self.db:
            return
        try:
            ns.ensure_default_series(self.db, company_id=None)
        except Exception:
            pass

    def load_data(self) -> None:
        if not self.db:
            return
        company_id = self.cmb_company.currentData()
        belge_turu = self.cmb_type.currentData()
        search = self.txt_search.text().strip().lower()

        self._series_list = ns.list_series(
            self.db, company_id=company_id, belge_turu=belge_turu,
        )

        tv = self.grid.table_view
        tv.setRowCount(0)

        today = date.today()
        for ds in self._series_list:
            b_label = ns.ADLAR.get(ds.belge_turu, ds.belge_turu)
            if search and not (
                search in ds.seri_kodu.lower()
                or search in (ds.seri_adi or "").lower()
                or search in ds.sablon.lower()
                or search in b_label.lower()
            ):
                continue

            try:
                next_no = ns.uret(
                    ds.sablon, today, ds.son_numara + 1, seri=ds.seri_kodu,
                )
            except Exception:
                next_no = "-"

            efatura_str = "-"
            if ds.is_efatura:
                e_type = (ds.efatura_turu or "e-Fatura").upper()
                efatura_str = f"🟢 {e_type} ({ds.gib_prefix or ds.seri_kodu})"

            default_str = "✔ Varsayılan" if ds.is_default else "-"
            active_str = "Aktif" if ds.is_active else "Pasif"

            r = tv.rowCount()
            tv.insertRow(r)
            tv.setRowHeight(r, getattr(tv, "effective_row_height", 28))

            row_items = [
                QStandardItem(b_label),
                QStandardItem(ds.seri_kodu),
                QStandardItem(ds.seri_adi or "-"),
                QStandardItem(ds.sablon),
                QStandardItem(next_no),
                QStandardItem(efatura_str),
                QStandardItem(default_str),
                QStandardItem(active_str),
            ]
            for col_idx, item in enumerate(row_items):
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if col_idx == 0:
                    item.setData(ds.id, Qt.ItemDataRole.UserRole)
                tv.setItem(r, col_idx, item)

    def _selected_series_id(self) -> int | None:
        tv = self.grid.table_view
        idx = tv.currentIndex()
        if not idx.isValid():
            return None
        item = tv.item(idx.row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_add(self) -> None:
        dlg = SeriesEditDialog(
            self.db,
            company_id=self.cmb_company.currentData(),
            belge_turu=self.cmb_type.currentData(),
            parent=self,
        )
        if dlg.exec():
            self.load_data()
            self.toast_requested.emit("Seri başarıyla eklendi.", "success")

    def _on_edit(self) -> None:
        s_id = self._selected_series_id()
        if not s_id:
            uyari(self, "Seçim Yapılmadı", "Lütfen düzenlemek istediğiniz seriyi seçin.")
            return
        dlg = SeriesEditDialog(self.db, series_id=s_id, parent=self)
        if dlg.exec():
            self.load_data()
            self.toast_requested.emit("Seri güncellendi.", "success")

    def _on_set_default(self) -> None:
        s_id = self._selected_series_id()
        if not s_id:
            uyari(self, "Seçim Yapılmadı", "Lütfen varsayılan yapmak istediğiniz seriyi seçin.")
            return
        ds = ns.get_series(self.db, s_id)
        if not ds:
            return
        ds.is_default = True
        ns.save_series(
            self.db,
            {
                "company_id": ds.company_id,
                "belge_turu": ds.belge_turu,
                "seri_kodu": ds.seri_kodu,
                "seri_adi": ds.seri_adi,
                "sablon": ds.sablon,
                "baslangic_no": ds.baslangic_no,
                "is_default": True,
                "is_active": ds.is_active,
                "is_efatura": ds.is_efatura,
                "efatura_turu": ds.efatura_turu,
                "gib_prefix": ds.gib_prefix,
            },
            series_id=ds.id,
        )
        self.load_data()
        self.toast_requested.emit(f"'{ds.seri_kodu}' varsayılan seri yapıldı.", "success")

    def _on_delete(self) -> None:
        s_id = self._selected_series_id()
        if not s_id:
            uyari(self, "Seçim Yapılmadı", "Lütfen silmek istediğiniz seriyi seçin.")
            return
        ds = ns.get_series(self.db, s_id)
        if not ds:
            return
        if not onay(self, "Seri Sil", f"'{ds.seri_kodu}' serisini silmek istediğinize emin misiniz?"):
            return
        ns.delete_series(self.db, s_id)
        self.load_data()
        self.toast_requested.emit("Seri silindi.", "success")

    def _on_gaps_dialog(self) -> None:
        dlg = NumberGapsDialog(
            self.db,
            company_id=self.cmb_company.currentData(),
            belge_turu=self.cmb_type.currentData(),
            parent=self,
        )
        dlg.exec()

    def record_count(self) -> int:
        """Tablodaki satır / kayıt sayısını döndürür."""
        if hasattr(self, "grid") and hasattr(self.grid, "table_view"):
            return self.grid.table_view.rowCount()
        return 0

    def apply_quick_search(self, query: str) -> None:
        """Genel ayarlar arama çubuğundan gelen metni arama alanına aktarır."""
        if hasattr(self, "txt_search"):
            self.txt_search.setText(query)


class SeriesEditDialog(QDialog):
    """Seri Ekleme / Düzenleme Dialogu (e-Fatura ve GİB Canlı Doğrulama Destekli)."""

    def __init__(
        self,
        db_session,
        series_id: int | None = None,
        company_id: int | None = None,
        belge_turu: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.db = db_session
        self.series_id = series_id
        self.preset_company_id = company_id
        self.preset_belge_turu = belge_turu
        self._init_ui()
        apply_light_dialog_style(self)
        if series_id:
            self._load_series()

    def _init_ui(self) -> None:
        self.setWindowTitle("Numara Serisi Tanımı" if not self.series_id else "Seri Düzenle")
        self.setFixedWidth(520)
        lyt = QVBoxLayout(self)
        lyt.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        # 1. Firma
        self.cmb_comp = QComboBox()
        self.cmb_comp.addItem("Tüm Firmalar (Genel)", None)
        if self.db:
            comps = self.db.scalars(select(Company).order_by(Company.short_name)).all()
            for c in comps:
                self.cmb_comp.addItem(f"{c.short_name} ({c.code})", c.id)
        if self.preset_company_id:
            idx = self.cmb_comp.findData(self.preset_company_id)
            if idx >= 0:
                self.cmb_comp.setCurrentIndex(idx)
        form.addRow("Firma:", self.cmb_comp)

        # 2. Belge Türü
        self.cmb_type = QComboBox()
        for code, name in ns.ADLAR.items():
            self.cmb_type.addItem(name, code)
        if self.preset_belge_turu:
            idx = self.cmb_type.findData(self.preset_belge_turu)
            if idx >= 0:
                self.cmb_type.setCurrentIndex(idx)
        self.cmb_type.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Belge / Fiş Türü:", self.cmb_type)

        # 3. Seri Kodu & Açıklama
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("Örn: FAT, EAR, A, B, TEK")
        self.txt_code.setMaxLength(10)
        self.txt_code.textChanged.connect(self._on_code_changed)
        form.addRow("Seri Kodu (*):", self.txt_code)

        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Örn: Merkez e-Fatura Serisi")
        form.addRow("Seri Adı:", self.txt_name)

        # 4. E-Fatura / e-Belge Grubu
        self.grp_efatura = QGroupBox("GİB e-Belge / e-Fatura Entegrasyonu")
        self.grp_efatura.setCheckable(True)
        self.grp_efatura.setChecked(False)
        self.grp_efatura.toggled.connect(self._on_efatura_toggled)
        ef_lyt = QFormLayout(self.grp_efatura)

        self.cmb_efatura_type = QComboBox()
        self.cmb_efatura_type.addItems(["e-Fatura", "e-Arşiv", "e-İrsaliye", "e-Müstahsil", "e-SMM"])
        ef_lyt.addRow("e-Belge Türü:", self.cmb_efatura_type)

        self.txt_gib_prefix = QLineEdit()
        self.txt_gib_prefix.setMaxLength(3)
        self.txt_gib_prefix.setPlaceholderText("3 harf (örn. EFA, EAR)")
        self.txt_gib_prefix.textChanged.connect(self._update_preview)
        ef_lyt.addRow("GİB 3 Harfli Birim Kodu:", self.txt_gib_prefix)

        form.addRow(self.grp_efatura)

        # 5. Şablon & Canlı Etiket Butonları
        sablon_box = QVBoxLayout()
        self.txt_sablon = QLineEdit()
        self.txt_sablon.setPlaceholderText("{SERI}{YYYY}{#########}")
        self.txt_sablon.textChanged.connect(self._update_preview)
        sablon_box.addWidget(self.txt_sablon)

        btn_row = QHBoxLayout()
        for tag in ["{SERI}", "{YYYY}", "{YY}", "{MM}", "{DD}", "{#####}", "{#########}"]:
            b = QPushButton(tag)
            b.setStyleSheet("font-size: 10px; padding: 2px 4px;")
            b.clicked.connect(lambda _c, t=tag: self._insert_tag(t))
            btn_row.addWidget(b)
        btn_row.addStretch()
        sablon_box.addLayout(btn_row)
        form.addRow("Numara Şablonu (*):", sablon_box)

        # 6. Başlangıç / Sayaç & Seçenekler
        self.spn_start = QSpinBox()
        self.spn_start.setRange(1, 999999999)
        self.spn_start.setValue(1)
        form.addRow("Başlangıç Sayısı:", self.spn_start)

        opt_row = QHBoxLayout()
        self.chk_default = QCheckBox("Varsayılan Seri")
        self.chk_active = QCheckBox("Aktif")
        self.chk_active.setChecked(True)
        opt_row.addWidget(self.chk_default)
        opt_row.addWidget(self.chk_active)
        opt_row.addStretch()
        form.addRow("Ayarlar:", opt_row)

        lyt.addLayout(form)

        # Önizleme ve Doğrulama Kutusu
        self.pnl_preview = QFrame()
        self.pnl_preview.setStyleSheet(
            "background-color: #f0fdf4; border: 1px solid #bbf7d0; "
            "border-radius: 6px; padding: 8px;",
        )
        prv_lyt = QVBoxLayout(self.pnl_preview)
        self.lbl_preview_title = QLabel("Canlı Numara Önizlemesi:")
        self.lbl_preview_title.setStyleSheet("font-weight: 700; color: #166534; font-size: 11px;")
        self.lbl_preview = QLabel("FAT2026000000001")
        self.lbl_preview.setStyleSheet("font-size: 14px; font-weight: 800; color: #15803d;")
        self.lbl_gib_badge = QLabel("🟢 GİB Standartlarına Uygun (16 Karakter)")
        self.lbl_gib_badge.setStyleSheet("font-size: 10px; color: #166534; font-weight: 600;")
        prv_lyt.addWidget(self.lbl_preview_title)
        prv_lyt.addWidget(self.lbl_preview)
        prv_lyt.addWidget(self.lbl_gib_badge)
        lyt.addWidget(self.pnl_preview)

        # Alt Butonlar
        btn_bar = QHBoxLayout()
        self.btn_cancel = QPushButton("Vazgeç")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("💾 Kaydet")
        self.btn_save.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        self.btn_save.clicked.connect(self._on_save)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_cancel)
        btn_bar.addWidget(self.btn_save)
        lyt.addLayout(btn_bar)

        self._on_type_changed()

    def _insert_tag(self, tag: str) -> None:
        self.txt_sablon.insert(tag)

    def _on_code_changed(self, text: str) -> None:
        upper = text.upper()
        if upper != text:
            self.txt_code.setText(upper)
        if self.grp_efatura.isChecked() and not self.txt_gib_prefix.text():
            self.txt_gib_prefix.setText(upper[:3])
        self._update_preview()

    def _on_type_changed(self) -> None:
        t = self.cmb_type.currentData()
        if t == "fatura":
            self.grp_efatura.setChecked(True)
            if not self.txt_sablon.text():
                self.txt_sablon.setText("{SERI}{YYYY}{#########}")
        else:
            if not self.txt_sablon.text():
                self.txt_sablon.setText(ns.VARSAYILANLAR.get(t, "{SERI}-{YYYY}-{#####}"))
        self._update_preview()

    def _on_efatura_toggled(self, checked: bool) -> None:
        if checked:
            if not self.txt_sablon.text() or self.txt_sablon.text() == ns.VARSAYILANLAR.get(self.cmb_type.currentData()):
                self.txt_sablon.setText("{SERI}{YYYY}{#########}")
        self._update_preview()

    def _update_preview(self) -> None:
        sab = self.txt_sablon.text().strip() or "{SERI}{YYYY}{#########}"
        seri = self.txt_gib_prefix.text().strip().upper() if self.grp_efatura.isChecked() else self.txt_code.text().strip().upper()
        if not seri:
            seri = "SERI"

        try:
            sample = ns.uret(sab, date.today(), 1, seri=seri)
            self.lbl_preview.setText(sample)
            if self.grp_efatura.isChecked():
                ok, err = ns.validate_gib_format(seri, sab)
                if ok:
                    self.lbl_gib_badge.setText("🟢 GİB e-Belge Formatına Uygun (16 Karakter)")
                    self.lbl_gib_badge.setStyleSheet("color: #15803d; font-weight: 600;")
                else:
                    self.lbl_gib_badge.setText(f"⚠ {err}")
                    self.lbl_gib_badge.setStyleSheet("color: #dc2626; font-weight: 600;")
            else:
                self.lbl_gib_badge.setText(f"Standart Format ({len(sample)} karakter)")
                self.lbl_gib_badge.setStyleSheet("color: #475569;")
        except Exception as e:
            self.lbl_preview.setText(f"Geçersiz Şablon: {e}")
            self.lbl_gib_badge.setText("⚠ Şablon Hatası")
            self.lbl_gib_badge.setStyleSheet("color: #dc2626;")

    def _load_series(self) -> None:
        ds = ns.get_series(self.db, self.series_id)
        if not ds:
            return
        idx = self.cmb_comp.findData(ds.company_id)
        if idx >= 0:
            self.cmb_comp.setCurrentIndex(idx)
        idx_t = self.cmb_type.findData(ds.belge_turu)
        if idx_t >= 0:
            self.cmb_type.setCurrentIndex(idx_t)
        self.txt_code.setText(ds.seri_kodu)
        self.txt_name.setText(ds.seri_adi or "")
        self.txt_sablon.setText(ds.sablon)
        self.spn_start.setValue(ds.baslangic_no)
        self.chk_default.setChecked(ds.is_default)
        self.chk_active.setChecked(ds.is_active)
        if ds.is_efatura:
            self.grp_efatura.setChecked(True)
            self.txt_gib_prefix.setText(ds.gib_prefix or ds.seri_kodu)
            idx_e = self.cmb_efatura_type.findText(ds.efatura_turu or "e-Fatura", Qt.MatchFlag.MatchContains)
            if idx_e >= 0:
                self.cmb_efatura_type.setCurrentIndex(idx_e)
        else:
            self.grp_efatura.setChecked(False)
        self._update_preview()

    def _on_save(self) -> None:
        data = {
            "company_id": self.cmb_comp.currentData(),
            "belge_turu": self.cmb_type.currentData(),
            "seri_kodu": self.txt_code.text().strip().upper(),
            "seri_adi": self.txt_name.text().strip(),
            "sablon": self.txt_sablon.text().strip(),
            "baslangic_no": self.spn_start.value(),
            "is_default": self.chk_default.isChecked(),
            "is_active": self.chk_active.isChecked(),
            "is_efatura": self.grp_efatura.isChecked(),
            "efatura_turu": self.cmb_efatura_type.currentText().lower() if self.grp_efatura.isChecked() else None,
            "gib_prefix": self.txt_gib_prefix.text().strip().upper() if self.grp_efatura.isChecked() else None,
        }
        try:
            ns.save_series(self.db, data, series_id=self.series_id)
            self.accept()
        except ns.SablonHatasi as e:
            QMessageBox.critical(self, "Kayıt Hatası", str(e))


class NumberGapsDialog(QDialog):
    """Müteselsil Sıra Denetimi ve Boşluk / Atlama Raporu Dialogu."""

    def __init__(self, db_session, company_id=None, belge_turu=None, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.company_id = company_id
        self.belge_turu = belge_turu
        self._init_ui()
        apply_light_dialog_style(self)
        self._run_analysis()

    def _init_ui(self) -> None:
        self.setWindowTitle("Müteselsil Sıra Denetimi & Boşluk Analizi")
        self.resize(600, 420)
        lyt = QVBoxLayout(self)
        lyt.setSpacing(8)

        # Üst filtre
        f_row = QHBoxLayout()
        f_row.addWidget(QLabel("Belge:"))
        self.cmb_type = QComboBox()
        for code, name in ns.ADLAR.items():
            self.cmb_type.addItem(name, code)
        if self.belge_turu:
            idx = self.cmb_type.findData(self.belge_turu)
            if idx >= 0:
                self.cmb_type.setCurrentIndex(idx)
        f_row.addWidget(self.cmb_type)

        f_row.addWidget(QLabel("Yıl:"))
        self.spn_year = QSpinBox()
        self.spn_year.setRange(2000, 2099)
        self.spn_year.setValue(date.today().year)
        f_row.addWidget(self.spn_year)

        btn_run = QPushButton("🔍 Yeniden Analiz Et")
        btn_run.setStyleSheet(btn_style("#2563eb", "#ffffff"))
        btn_run.clicked.connect(self._run_analysis)
        f_row.addWidget(btn_run)
        f_row.addStretch()
        lyt.addLayout(f_row)

        self.lbl_status = QLabel("Analiz ediliyor...")
        self.lbl_status.setStyleSheet("font-weight: 700; color: #0f172a; font-size: 11px;")
        lyt.addWidget(self.lbl_status)

        self.grid = standart_grid(
            "def_doc_gaps",
            [
                ("seq", "SIRA NO"),
                ("missing_number", "EKSİK / ATLANAN NUMARA"),
                ("donem", "DÖNEM / YIL"),
            ],
        )
        lyt.addWidget(self.grid, 1)

        btn_close = QPushButton("Kapat")
        btn_close.clicked.connect(self.accept)
        lyt.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignRight)

    def _run_analysis(self) -> None:
        if not self.db:
            return
        kod = self.cmb_type.currentData()
        yil = self.spn_year.value()
        gaps = ns.find_number_gaps(self.db, kod, company_id=self.company_id, yil=yil)

        tv = self.grid.table_view
        tv.setRowCount(0)

        if not gaps:
            self.lbl_status.setText(f"✔ '{ns.ADLAR.get(kod)}' için {yil} yılında hiçbir müteselsil sıra atlaması bulunamadı. Sıra tamdır.")
            self.lbl_status.setStyleSheet("color: #15803d; font-weight: 700;")
        else:
            self.lbl_status.setText(f"⚠ Toplam {len(gaps)} adet atlanan / eksik sıra numarası tespit edildi:")
            self.lbl_status.setStyleSheet("color: #dc2626; font-weight: 700;")
            for g in gaps:
                r = tv.rowCount()
                tv.insertRow(r)
                tv.setRowHeight(r, getattr(tv, "effective_row_height", 28))
                for col_idx, val in enumerate([str(g["seq"]), g["missing_number"], g["donem"]]):
                    it = QStandardItem(val)
                    it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    tv.setItem(r, col_idx, it)
