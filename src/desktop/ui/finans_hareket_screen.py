"""TOYA ERP - Kasa Hareketleri / Banka Hareketleri ekranı (standart 3 panelli).

Tek sınıf iki grubu yönetir (`grup="kasa"` ya da `"banka"`). Sol: fiş girişi (kasa: tahsilat, tediye, açılış, virman;
banka: gelen/giden havale, gelen/giden EFT, virman, açılış). Orta: hareket listesi + sayfalama. Sağ: filtreler, filtre
toplamları, seçili hareket ve seyrek işlemler (Excel, fişi gizle). Fiş penceresi `FinansFisDialog`'dur.
Silme = fişi ve cari karşılıklarını görünümden gizleme (kayıt fiziksel olarak kalır)."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QStandardItem
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.core.models import FinansHareket
from src.desktop.services import money_service
from src.desktop.services.finans_fis_service import (
    FIS_TIPLERI,
    GRUP_HESAP_TURLERI,
    TURLER,
    FinansFiltre,
    FinansFisError,
    FinansFisService,
)
from src.desktop.ui.components.button_style import btn_style
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.grid_delegates import apply_calendar_style
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.widgets.finans_fis_dialog import FinansFisDialog
from src.desktop.ui.widgets.money_edit import bicimle
from src.desktop.ui.widgets.pagination_widget import PaginationWidget

logger = logging.getLogger(__name__)

_GIRIS, _CIKIS = QColor("#16a34a"), QColor("#dc2626")
_INPUT = ("QComboBox, QLineEdit, QDateEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px;"
          " background-color: white; color: #0f172a; font-size: 11px; }")
_IKON = {"kasa_tahsilat": "📥", "kasa_tediye": "📤", "kasa_acilis": "🚪", "kasa_virman": "🔁", "havale_gelen": "📥", "havale_giden": "📤",
         "eft_gelen": "⬇️", "eft_giden": "⬆️", "banka_virman": "🔁", "banka_acilis": "🚪"}
_KISAYOL = {"kasa_tahsilat": "F2", "kasa_tediye": "F3", "havale_gelen": "F2", "havale_giden": "F3"}
_PROFIL = {"kasa": ("kasa_hareket", "Kasa Hareketleri", "kasa"), "banka": ("banka_hareket", "Banka Hareketleri", "banka")}


class FinansHareketScreen(ThreePanelBaseWidget):
    PROFIL_BOLUMU = True

    BUS_KONULARI = ("finans",)
    def __init__(self, db_session=None, grup: str = "kasa", parent=None, embedded: bool = False) -> None:
        self.grup = grup
        self._kayitlar: list[FinansHareket] = []
        self._yerel = money_service.yerel_para(db_session) if db_session is not None else "TRY"
        self._pb = "TL" if self._yerel == "TRY" else self._yerel
        profil, baslik, self.izin = _PROFIL[grup]
        super().__init__(db_session=db_session, profile_key=profil, module_name=baslik, parent=parent, embedded=embedded)
        self.setObjectName("FinansHareketCanvas")
        self.svc = FinansFisService(db_session) if db_session is not None else None

        self.pagination_widget = PaginationWidget(page_sizes=[25, 50, 100], parent=self)
        self.pagination_widget.page_changed.connect(self._sayfa_degisti)
        self.pagination_widget.page_size_changed.connect(self._sayfa_boyu_degisti)
        self.bottom_bar_layout.addWidget(self.pagination_widget)

        self.filterable_table.enable_auto_save_layout()
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_view.doubleClicked.connect(lambda _i: self.on_edit_clicked())
        self._apply_permissions()
        if self.svc is not None:
            if self.grup == "banka":
                self._pos_mahsuplarini_tara()
            self._filtre_listelerini_doldur()
            self.load_data()

    def _pos_mahsuplarini_tara(self) -> None:
        """Ekran her açıldığında (bkz. gelistirme/04_odeme_planlari/tasarim.md, 04.09): valörü geçmiş,
        otomatik mahsup açık POS bakiyelerini tarayıp hedef banka hesabına virman fişiyle aktarır. Ekranın
        açılmasını ASLA engellemez — bir hata olursa sessizce loglanır, kullanıcı manuel mahsup edebilir."""
        try:
            from src.desktop.services.pos_mahsup_servisi import vadesi_gelenleri_tara
            sonuclar = vadesi_gelenleri_tara(self.db)
            if sonuclar:
                logger.info("POS otomatik mahsup: %d hesap için virman oluşturuldu.", len(sonuclar))
        except Exception:  # noqa: BLE001
            logger.exception("POS otomatik mahsup taraması başarısız oldu.")

    def _pos_mahsup_takip_ac(self) -> None:
        from src.desktop.ui.widgets.pos_mahsup_takip_dialog import PosMahsupTakipDialog
        dlg = PosMahsupTakipDialog(self.db, parent=self)
        dlg.exec()
        self.load_data()

    # ---- yapı --------------------------------------------------------------
    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return {0: ("☑", "select"), 1: ("Tarih", "tarih"), 2: ("Fiş No", "fis_no"), 3: ("Tür", "tur"), 4: ("Hesap", "hesap"),
                5: ("Cari / Karşı Hesap", "cari"), 6: ("Giriş", "giris"), 7: ("Çıkış", "cikis"), 8: ("Döviz", "doviz"),
                9: ("Kur", "kur"), 10: ("Yerel Tutar", "yerel"), 11: ("Belge No", "belge"), 12: ("Not", "aciklama")}

    def setup_left_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        sec = CollapsibleSection("HAREKET GİRİŞİ", is_expanded=True)
        sec.setObjectName(f"cmp.act.{self.grup}_hareket")
        self.btn_tur: dict[str, QPushButton] = {}
        for i, (tur, etiket) in enumerate(FIS_TIPLERI[self.grup].items()):
            b = QPushButton(f"{_IKON[tur]} {etiket}" + (f" ({_KISAYOL[tur]})" if tur in _KISAYOL else ""))
            if tur in _KISAYOL:
                b.setShortcut(_KISAYOL[tur])
            b.setStyleSheet(btn_style("#2563eb" if i == 0 else "#ffffff", "#ffffff" if i == 0 else "#1e293b"))
            b.clicked.connect(lambda _=False, t=tur: self.on_new_clicked(t))
            sec.add_widget(b)
            self.btn_tur[tur] = b
        self.btn_edit = QPushButton("✏️ Fişi Aç")
        self.btn_edit.setStyleSheet(btn_style("#ffffff", "#1e293b"))
        self.btn_edit.clicked.connect(self.on_edit_clicked)
        sec.add_widget(self.btn_edit)
        layout.addWidget(sec)
        layout.addStretch()

    def setup_right_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        sec_f = CollapsibleSection("FİLTRELER", is_expanded=True)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Fiş no / hesap / cari / belge / not...")
        self.search_box.setStyleSheet(_INPUT)
        self.search_box.textChanged.connect(self.on_filter_changed)
        self.cmb_tur, self.cmb_hesap = QComboBox(), QComboBox()
        for cmb in (self.cmb_tur, self.cmb_hesap):
            cmb.setStyleSheet(_INPUT + "QComboBox { combobox-popup: 0; }")
            cmb.currentIndexChanged.connect(self.on_filter_changed)
        self.cmb_tur.addItem("Tüm türler", None)
        for k, e in FIS_TIPLERI[self.grup].items():
            self.cmb_tur.addItem(e, k)
        self.cmb_hesap.addItem("Tüm hesaplar", None)
        self.chk_tarih = QCheckBox("Tarih aralığı")
        self.dt_bas, self.dt_bit = QDateEdit(QDate.currentDate().addMonths(-1)), QDateEdit(QDate.currentDate())
        for d in (self.dt_bas, self.dt_bit):
            apply_calendar_style(d)
            d.setDisplayFormat("dd.MM.yyyy")
            d.setStyleSheet(_INPUT)
            d.setEnabled(False)
            d.dateChanged.connect(self.on_filter_changed)
        self.chk_tarih.toggled.connect(lambda on: (self.dt_bas.setEnabled(on), self.dt_bit.setEnabled(on), self.on_filter_changed()))
        for w in (self.search_box, self.cmb_tur, self.cmb_hesap, self.chk_tarih, self.dt_bas, self.dt_bit):
            sec_f.add_widget(w)
        btn_temizle = QPushButton("🧹 Filtreleri Temizle")
        btn_temizle.setStyleSheet(btn_style("#ffffff", "#1e293b"))
        btn_temizle.clicked.connect(self.clear_filters)
        sec_f.add_widget(btn_temizle)
        layout.addWidget(sec_f)

        sec_t = CollapsibleSection("FİLTRE TOPLAMLARI", is_expanded=True)
        self.lbl_adet, self.lbl_giris, self.lbl_cikis, self.lbl_net = (QLabel() for _ in range(4))
        for w in (self.lbl_adet, self.lbl_giris, self.lbl_cikis, self.lbl_net):
            w.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e293b;")
            sec_t.add_widget(w)
        layout.addWidget(sec_t)

        sec_d = CollapsibleSection("SEÇİLİ HAREKET", is_expanded=True)
        self.lbl_detay = QLabel("Bir hareket seçin.")
        self.lbl_detay.setWordWrap(True)
        self.lbl_detay.setStyleSheet("color: #334155; font-size: 11px;")
        sec_d.add_widget(self.lbl_detay)
        layout.addWidget(sec_d)

        sec_i = CollapsibleSection("DİĞER İŞLEMLER", is_expanded=False)
        self.btn_excel = QPushButton("📊 Excel'e Aktar")
        self.btn_hide = QPushButton("🗑️ Seçili Fişleri Gizle")
        self.btn_excel.clicked.connect(self.on_excel_clicked)
        self.btn_hide.clicked.connect(self.on_hide_clicked)
        for b in (self.btn_excel, self.btn_hide):
            b.setStyleSheet(btn_style("#ffffff", "#1e293b"))
            sec_i.add_widget(b)
        if self.grup == "banka":
            self.btn_pos_takip = QPushButton("🔁 POS Mahsup Takip")
            self.btn_pos_takip.setStyleSheet(btn_style("#ffffff", "#1e293b"))
            self.btn_pos_takip.clicked.connect(self._pos_mahsup_takip_ac)
            sec_i.add_widget(self.btn_pos_takip)
        layout.addWidget(sec_i)
        layout.addStretch()

    def _apply_permissions(self) -> None:
        from src.desktop.security.gate import gate
        for b in self.btn_tur.values():
            gate(b, f"{self.izin}.movement", hide=True)
        gate(self.btn_edit, f"{self.izin}.movement", hide=True)
        gate(self.btn_hide, f"{self.izin}.movement", hide=True)
        gate(self.btn_excel, f"{self.izin}.view", hide=True)
        if hasattr(self, "btn_pos_takip"):
            gate(self.btn_pos_takip, f"{self.izin}.movement", hide=True)

    def _filtre_listelerini_doldur(self) -> None:
        self.cmb_hesap.blockSignals(True)
        secili = self.cmb_hesap.currentData()
        self.cmb_hesap.clear()
        self.cmb_hesap.addItem("Tüm hesaplar", None)
        for h in self.svc.hesaplar(self.grup, sadece_aktif=False):
            self.cmb_hesap.addItem(f"{h.kod} — {h.ad}", h.id)
        i = self.cmb_hesap.findData(secili)
        self.cmb_hesap.setCurrentIndex(max(i, 0))
        self.cmb_hesap.blockSignals(False)

    # ---- veri --------------------------------------------------------------
    def _filtre(self) -> FinansFiltre:
        return FinansFiltre(
            grup=self.grup, arama=self.search_box.text(), tur=self.cmb_tur.currentData(), hesap_id=self.cmb_hesap.currentData(),
            tarih_bas=self.dt_bas.date().toPyDate() if self.chk_tarih.isChecked() else None,
            tarih_bit=self.dt_bit.date().toPyDate() if self.chk_tarih.isChecked() else None)

    def on_filter_changed(self) -> None:
        if not hasattr(self, "pagination_widget") or getattr(self, "svc", None) is None:      # kurulum sırasında oluşan sinyaller
            return
        self.current_page = 1
        self.pagination_widget.set_current_page(1)
        self.load_data()

    def clear_filters(self) -> None:
        for w in (self.search_box, self.cmb_tur, self.cmb_hesap, self.chk_tarih):
            w.blockSignals(True)
        self.search_box.clear()
        for c in (self.cmb_tur, self.cmb_hesap):
            c.setCurrentIndex(0)
        self.chk_tarih.setChecked(False)
        for d in (self.dt_bas, self.dt_bit):
            d.setEnabled(False)
        for w in (self.search_box, self.cmb_tur, self.cmb_hesap, self.chk_tarih):
            w.blockSignals(False)
        self.on_filter_changed()

    def _sayfa_degisti(self, page: int) -> None:
        self.current_page = page
        self.load_data()

    def _sayfa_boyu_degisti(self, size: int) -> None:
        self.per_page, self.current_page = size, 1
        self.load_data()

    def _gelen_virman(self, h: FinansHareket) -> bool:
        """Başka gruptaki hesaptan bu ekranın grubundaki hesaba giren virman (bu ekranda giriş görünür)."""
        izinli = GRUP_HESAP_TURLERI[self.grup]
        return bool(h.karsi_hesap and h.karsi_hesap.tur in izinli and h.hesap.tur not in izinli)

    def _yonler(self, h: FinansHareket) -> tuple[float, float]:
        """(giriş, çıkış) — virman çıkış hesabında çıkış, karşı hesap bu ekrandaysa giriş görünür."""
        if self._gelen_virman(h) or h.yon == "giris":
            return h.tutar, 0.0
        return 0.0, h.tutar

    def _cari_metni(self, h: FinansHareket) -> str:
        if self._gelen_virman(h):
            return f"← {h.hesap.kod} {h.hesap.ad}"
        if h.karsi_hesap:
            return f"→ {h.karsi_hesap.kod} {h.karsi_hesap.ad}"
        return h.customer.fullname if h.customer else ""

    def load_data(self) -> None:
        if self.svc is None:
            return
        f = self._filtre()
        self.per_page = self.pagination_widget.current_page_size()
        self.current_page = self.pagination_widget.current_page()
        self._kayitlar, self.total_records = self.svc.list(f, self.current_page, self.per_page)
        m = self.table_model
        m.removeRows(0, m.rowCount())
        for h in self._kayitlar:
            giris, cikis = self._yonler(h)
            cells = ["", h.tarih.strftime("%d.%m.%Y"), h.fis.fis_no if h.fis else "", TURLER.get(h.tur, (h.tur,))[0],
                     f"{h.hesap.kod} {h.hesap.ad}", self._cari_metni(h), bicimle(giris, 2) if giris else "", bicimle(cikis, 2) if cikis else "",
                     h.para_birimi, bicimle(h.kur, 4) if h.para_birimi != self._yerel else "", bicimle(h.tutar_tl, 2), h.belge_no or "", h.aciklama or ""]
            items = [QStandardItem(t) for t in cells]
            items[0].setCheckable(True)
            items[0].setCheckState(Qt.CheckState.Unchecked)
            items[0].setData(h.id, Qt.ItemDataRole.UserRole)
            for i in (6, 7, 9, 10):
                items[i].setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            items[6].setForeground(QBrush(_GIRIS))
            items[7].setForeground(QBrush(_CIKIS))
            m.appendRow(items)
        for col in (3, 4, 5, 12):                     # metin sütunları kırpılmasın
            self.table_view.resizeColumnToContents(col)
        self.pagination_widget.set_total(self.total_records)
        o = self.svc.ozet(f)
        self.lbl_adet.setText(f"Hareket: {o.adet}")
        self.lbl_giris.setText(f"Giriş ({self._pb}): {bicimle(o.giris_tl, 2)}")
        self.lbl_giris.setStyleSheet("font-size: 12px; font-weight: 600; color: #16a34a;")
        self.lbl_cikis.setText(f"Çıkış ({self._pb}): {bicimle(o.cikis_tl, 2)}")
        self.lbl_cikis.setStyleSheet("font-size: 12px; font-weight: 600; color: #dc2626;")
        self.lbl_net.setText(f"Net ({self._pb}): {bicimle(o.giris_tl - o.cikis_tl, 2)}   (virman hariç)")
        self.lbl_detay.setText("Bir hareket seçin.")

    # ---- seçim / işlemler --------------------------------------------------
    def _secili(self) -> FinansHareket | None:
        idx = self.table_view.selectionModel().selectedRows()
        if not idx or idx[0].row() >= len(self._kayitlar):
            return None
        return self._kayitlar[idx[0].row()]

    def _isaretli_fisler(self) -> list[int]:
        ids = {self._kayitlar[r].fis_id for r in range(self.table_model.rowCount())
               if r < len(self._kayitlar) and self.table_model.item(r, 0).checkState() == Qt.CheckState.Checked}
        if not ids and self._secili():
            ids = {self._secili().fis_id}
        return sorted(i for i in ids if i)

    def on_selection_changed(self, *_a) -> None:
        h = self._secili()
        if h is None:
            return
        self.lbl_detay.setText(
            f"<b>{TURLER.get(h.tur, (h.tur,))[0]}</b> — {h.hesap.kod} {h.hesap.ad}<br>"
            f"{h.tarih:%d.%m.%Y} · {bicimle(h.tutar, 2)} {h.para_birimi}"
            + (f" (kur {bicimle(h.kur, 4)} → {bicimle(h.tutar_tl, 2)} {self._pb})" if h.para_birimi != self._yerel else "")
            + (f"<br>Cari: {h.customer.fullname}" if h.customer else "")
            + (f"<br>Karşı hesap: {h.karsi_hesap.kod} {h.karsi_hesap.ad}" if h.karsi_hesap else "")
            + (f"<br>Fiş: {h.fis.fis_no}" if h.fis else "") + (f"<br>{h.aciklama}" if h.aciklama else ""))

    def on_new_clicked(self, tur: str | None = None) -> None:
        if FinansFisDialog(self.db, grup=self.grup, tur=tur, hesap_id=self.cmb_hesap.currentData(), parent=self).exec():
            self._filtre_listelerini_doldur()
            self.load_data()
            self.data_changed.emit()

    def on_edit_clicked(self) -> None:
        h = self._secili()
        if h is None or not h.fis_id:
            return
        if FinansFisDialog(self.db, fis_id=h.fis_id, parent=self).exec():
            self.load_data()
            self.data_changed.emit()

    def on_hide_clicked(self) -> None:
        ids = self._isaretli_fisler()
        if not ids:
            return
        if QMessageBox.question(self, "Fişleri Gizle", f"{len(ids)} fiş listeden kaldırılacak; cari karşılıkları da görünümden çıkar "
                                                      "(kayıt fiziksel olarak silinmez). Devam?") != QMessageBox.StandardButton.Yes:
            return
        try:
            for i in ids:
                self.svc.fis_gizle(i)
        except FinansFisError as e:
            QMessageBox.warning(self, "Fişleri Gizle", str(e))
        self.load_data()
        self.data_changed.emit()

    def on_excel_clicked(self) -> None:
        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(self, "Uyarı", "openpyxl bulunamadı.\npip install openpyxl")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", f"{self.grup}_hareketleri.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        rows, _n = self.svc.list(self._filtre(), 1, 1_000_000)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = _PROFIL[self.grup][1]
        ws.append([self.headers_dict[i][0] for i in sorted(self.headers_dict) if i])
        for h in rows:
            giris, cikis = self._yonler(h)
            ws.append([h.tarih, h.fis.fis_no if h.fis else "", TURLER.get(h.tur, (h.tur,))[0], f"{h.hesap.kod} {h.hesap.ad}", self._cari_metni(h),
                       giris, cikis, h.para_birimi, h.kur, h.tutar_tl, h.belge_no, h.aciklama])
        wb.save(path)

    def show_context_menu(self, pos) -> None:
        from src.desktop.managers.theme_manager import ThemeManager
        idx = self.table_view.indexAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())
        for tur, etiket in FIS_TIPLERI[self.grup].items():
            a = QAction(f"➕ {etiket}", self)
            a.triggered.connect(lambda _=False, t=tur: self.on_new_clicked(t))
            menu.addAction(a)
        if idx.isValid():
            self.table_view.selectRow(idx.row())
            menu.addSeparator()
            for text, fn in (("✏️ Fişi Aç", self.on_edit_clicked), ("🗑️ Fişi Gizle", self.on_hide_clicked)):
                a = QAction(text, self)
                a.triggered.connect(fn)
                menu.addAction(a)
        self.filterable_table.add_column_actions_to_menu(menu)
        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def close_tab(self) -> None:
        p = self.parentWidget()
        while p and not hasattr(p, "removeTab"):
            p = p.parentWidget()
        if p:
            i = p.indexOf(self) if hasattr(p, "indexOf") else p.currentIndex()
            if i >= 0:
                p.removeTab(i)
