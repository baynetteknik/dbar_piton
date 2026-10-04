"""TOYA ERP - Stok Hareketleri ekranı (standart 3 panelli).

Sol: fiş girişi (Giriş, Çıkış, Transfer, Sayım, Açılış). Orta: hareket listesi + sayfalama.
Sağ: filtreler, filtre toplamları, seçili hareket ve seyrek işlemler (Excel, fişi gizle).
Fiş penceresi `StokFisDialog`'dur. Silme = fişi görünümden gizleme (stok etkisi geri alınır, kayıt fiziksel olarak kalır)."""

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
from sqlalchemy import select

from src.core.models import StokHareket, WarehouseDefinition
from src.desktop.services.stok_fis_service import (
    FIS_TIPLERI,
    TURLER,
    StokFiltre,
    StokFisError,
    StokFisService,
)
from src.desktop.ui.components.button_style import btn_style
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.grid_delegates import apply_calendar_style
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.widgets.money_edit import bicimle
from src.desktop.ui.widgets.pagination_widget import PaginationWidget
from src.desktop.ui.widgets.stok_fis_dialog import StokFisDialog

logger = logging.getLogger(__name__)

_GIRIS, _CIKIS = QColor("#16a34a"), QColor("#dc2626")
_INPUT = ("QComboBox, QLineEdit, QDateEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px;"
          " background-color: white; color: #0f172a; font-size: 11px; }")
_IKON = {"giris": "📥", "cikis": "📤", "transfer": "🔁", "sayim": "🧮", "acilis": "🚪"}


class StokHareketScreen(ThreePanelBaseWidget):
    PROFIL_BOLUMU = True

    BUS_KONULARI = ("stok",)
    def __init__(self, db_session=None, parent=None, embedded: bool = False) -> None:
        self._kayitlar: list[StokHareket] = []
        self._depo_kod: dict[int, str] = {}
        super().__init__(db_session=db_session, profile_key="stok_hareket", module_name="Stok Hareketleri",
                         parent=parent, embedded=embedded)
        self.setObjectName("StokHareketCanvas")
        self.svc = StokFisService(db_session) if db_session is not None else None

        self.pagination_widget = PaginationWidget(page_sizes=[25, 50, 100], parent=self)
        self.pagination_widget.page_changed.connect(self._sayfa_degisti)
        self.pagination_widget.page_size_changed.connect(self._sayfa_boyu_degisti)
        self.bottom_bar_layout.addWidget(self.pagination_widget)

        self.filterable_table.enable_auto_save_layout()      # sütun sırası / görünürlük / genişlik otomatik hatırlanır
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_view.doubleClicked.connect(lambda _i: self.on_edit_clicked())
        self._apply_permissions()
        if self.svc is not None:
            self._filtre_listelerini_doldur()
            self.load_data()

    # ---- yapı --------------------------------------------------------------
    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return {
            0: ("☑", "select"), 1: ("Tarih", "tarih"), 2: ("Fiş No", "fis_no"), 3: ("Tür", "tur"),
            4: ("Stok Kodu", "kod"), 5: ("Stok Adı", "ad"), 6: ("Depo", "depo"), 7: ("Hedef Depo", "hedef"),
            8: ("Miktar", "miktar"), 9: ("Birim", "birim"), 10: ("B.Fiyat", "fiyat"), 11: ("Tutar", "tutar"),
            12: ("Not", "aciklama"),
        }

    def setup_left_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        sec = CollapsibleSection("HAREKET GİRİŞİ", is_expanded=True)
        sec.setObjectName("cmp.act.stok_hareket")
        self.btn_tur: dict[str, QPushButton] = {}
        kisayol = {"giris": "F2", "cikis": "F3"}
        for tur, etiket in FIS_TIPLERI.items():
            b = QPushButton(f"{_IKON[tur]} {etiket}" + (f" ({kisayol[tur]})" if tur in kisayol else ""))
            if tur in kisayol:
                b.setShortcut(kisayol[tur])
            b.setStyleSheet(btn_style("#2563eb" if tur == "giris" else "#ffffff", "#ffffff" if tur == "giris" else "#1e293b"))
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
        self.search_box.setPlaceholderText("Stok kodu / adı / barkod / fiş no...")
        self.search_box.setStyleSheet(_INPUT)
        self.search_box.textChanged.connect(self.on_filter_changed)
        self.cmb_tur, self.cmb_depo = QComboBox(), QComboBox()
        for cmb in (self.cmb_tur, self.cmb_depo):
            cmb.setStyleSheet(_INPUT + "QComboBox { combobox-popup: 0; }")
            cmb.currentIndexChanged.connect(self.on_filter_changed)
        self.cmb_tur.addItem("Tüm türler", None)
        for k, (e, _i) in TURLER.items():
            self.cmb_tur.addItem(e, k)
        self.cmb_depo.addItem("Tüm depolar", None)
        self.chk_tarih = QCheckBox("Tarih aralığı")
        self.dt_bas, self.dt_bit = QDateEdit(QDate.currentDate().addMonths(-1)), QDateEdit(QDate.currentDate())
        for d in (self.dt_bas, self.dt_bit):
            apply_calendar_style(d)
            d.setDisplayFormat("dd.MM.yyyy")
            d.setStyleSheet(_INPUT)
            d.setEnabled(False)
            d.dateChanged.connect(self.on_filter_changed)
        self.chk_tarih.toggled.connect(lambda on: (self.dt_bas.setEnabled(on), self.dt_bit.setEnabled(on), self.on_filter_changed()))
        for w in (self.search_box, self.cmb_tur, self.cmb_depo, self.chk_tarih, self.dt_bas, self.dt_bit):
            sec_f.add_widget(w)
        btn_temizle = QPushButton("🧹 Filtreleri Temizle")
        btn_temizle.setStyleSheet(btn_style("#ffffff", "#1e293b"))
        btn_temizle.clicked.connect(self.clear_filters)
        sec_f.add_widget(btn_temizle)
        layout.addWidget(sec_f)

        sec_t = CollapsibleSection("FİLTRE TOPLAMLARI", is_expanded=True)
        self.lbl_adet, self.lbl_giris, self.lbl_cikis, self.lbl_tutar = (QLabel() for _ in range(4))
        for w in (self.lbl_adet, self.lbl_giris, self.lbl_cikis, self.lbl_tutar):
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
        layout.addWidget(sec_i)
        layout.addStretch()

    def _apply_permissions(self) -> None:
        from src.desktop.security.gate import gate
        for b in self.btn_tur.values():
            gate(b, "stok.movement", hide=True)
        gate(self.btn_edit, "stok.movement", hide=True)
        gate(self.btn_hide, "stok.movement", hide=True)
        gate(self.btn_excel, "stok.view", hide=True)

    def _filtre_listelerini_doldur(self) -> None:
        self._depo_kod = {}
        self.cmb_depo.blockSignals(True)
        self.cmb_depo.clear()
        self.cmb_depo.addItem("Tüm depolar", None)
        for w in self.db.scalars(select(WarehouseDefinition).where(WarehouseDefinition.is_deleted == False)  # noqa: E712
                                 .order_by(WarehouseDefinition.code)):
            self._depo_kod[w.id] = w.code
            self.cmb_depo.addItem(f"{w.code} — {w.name or ''}", w.id)
        self.cmb_depo.blockSignals(False)

    # ---- veri --------------------------------------------------------------
    def _filtre(self) -> StokFiltre:
        return StokFiltre(
            arama=self.search_box.text(), tur=self.cmb_tur.currentData(), depo_id=self.cmb_depo.currentData(),
            tarih_bas=self.dt_bas.date().toPyDate() if self.chk_tarih.isChecked() else None,
            tarih_bit=self.dt_bit.date().toPyDate() if self.chk_tarih.isChecked() else None)

    def on_filter_changed(self) -> None:
        if not hasattr(self, "pagination_widget") or self.svc is None:      # kurulum sırasında oluşan sinyaller
            return
        self.current_page = 1
        self.pagination_widget.set_current_page(1)
        self.load_data()

    def clear_filters(self) -> None:
        for w in (self.search_box, self.cmb_tur, self.cmb_depo, self.chk_tarih):
            w.blockSignals(True)
        self.search_box.clear()
        for c in (self.cmb_tur, self.cmb_depo):
            c.setCurrentIndex(0)
        self.chk_tarih.setChecked(False)
        for d in (self.dt_bas, self.dt_bit):
            d.setEnabled(False)
        for w in (self.search_box, self.cmb_tur, self.cmb_depo, self.chk_tarih):
            w.blockSignals(False)
        self.on_filter_changed()

    def _sayfa_degisti(self, page: int) -> None:
        self.current_page = page
        self.load_data()

    def _sayfa_boyu_degisti(self, size: int) -> None:
        self.per_page, self.current_page = size, 1
        self.load_data()

    def load_data(self) -> None:
        if self.svc is None:
            return
        f = self._filtre()
        self.per_page = self.pagination_widget.current_page_size()
        self.current_page = self.pagination_widget.current_page()
        self._kayitlar, self.total_records = self.svc.liste(f, self.current_page, self.per_page)
        m = self.table_model
        m.removeRows(0, m.rowCount())
        for h in self._kayitlar:
            p = h.product
            cells = ["", h.tarih.strftime("%d.%m.%Y"), h.fis.fis_no if h.fis else "", TURLER.get(h.tur, (h.tur,))[0], p.sku, p.name or "",
                     self._depo_kod.get(h.depo_id, ""), self._depo_kod.get(h.hedef_depo_id, "") if h.hedef_depo_id else "",
                     bicimle(h.miktar, 3), h.birim or "", bicimle(h.birim_fiyat, 2) if h.birim_fiyat else "",
                     bicimle(h.tutar, 2) if h.tutar else "", h.aciklama or ""]
            items = [QStandardItem(t) for t in cells]
            items[0].setCheckable(True)
            items[0].setCheckState(Qt.CheckState.Unchecked)
            items[0].setData(h.id, Qt.ItemDataRole.UserRole)
            for i in (8, 10, 11):
                items[i].setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            renk = _GIRIS if h.toplam_etki > 0 else _CIKIS if h.toplam_etki < 0 else None
            if renk:
                items[8].setForeground(QBrush(renk))
            m.appendRow(items)
        for col in (3, 5, 12):                        # metin sütunları kırpılmasın
            self.table_view.resizeColumnToContents(col)
        self.pagination_widget.set_total(self.total_records)
        o = self.svc.ozet(f)
        self.lbl_adet.setText(f"Hareket: {o.adet}")
        self.lbl_giris.setText(f"Giriş: {bicimle(o.giris, 3)}")
        self.lbl_giris.setStyleSheet("font-size: 12px; font-weight: 600; color: #16a34a;")
        self.lbl_cikis.setText(f"Çıkış: {bicimle(o.cikis, 3)}")
        self.lbl_cikis.setStyleSheet("font-size: 12px; font-weight: 600; color: #dc2626;")
        self.lbl_tutar.setText(f"Tutar: {bicimle(o.tutar, 2)}")
        self.lbl_detay.setText("Bir hareket seçin.")

    # ---- seçim / işlemler --------------------------------------------------
    def _secili(self) -> StokHareket | None:
        idx = self.table_view.selectionModel().selectedRows()
        if not idx or idx[0].row() >= len(self._kayitlar):
            return None
        return self._kayitlar[idx[0].row()]

    def _isaretli_fisler(self) -> list[int]:
        ids = {self._kayitlar[r].fis_id for r in range(self.table_model.rowCount())
               if self.table_model.item(r, 0).checkState() == Qt.CheckState.Checked and r < len(self._kayitlar)}
        if not ids and self._secili():
            ids = {self._secili().fis_id}
        return sorted(i for i in ids if i)

    def on_selection_changed(self, *_a) -> None:
        h = self._secili()
        if h is None:
            return
        self.lbl_detay.setText(
            f"<b>{TURLER.get(h.tur, (h.tur,))[0]}</b> — {h.product.sku} {h.product.name}<br>"
            f"{h.tarih:%d.%m.%Y} · {bicimle(h.miktar, 3)} {h.birim or ''}"
            + (f" · {bicimle(h.tutar, 2)}" if h.tutar else "")
            + f"<br>Depo: {self._depo_kod.get(h.depo_id, '')}"
            + (f" → {self._depo_kod.get(h.hedef_depo_id, '')}" if h.hedef_depo_id else "")
            + (f"<br>Fiş: {h.fis.fis_no}" if h.fis else "") + (f"<br>{h.aciklama}" if h.aciklama else ""))

    def on_new_clicked(self, tur: str = "giris") -> None:
        if StokFisDialog(self.db, tur=tur, parent=self).exec():
            self._filtre_listelerini_doldur()
            self.load_data()
            self.data_changed.emit()

    def on_edit_clicked(self) -> None:
        h = self._secili()
        if h is None or not h.fis_id:
            return
        if StokFisDialog(self.db, fis_id=h.fis_id, parent=self).exec():
            self.load_data()
            self.data_changed.emit()

    def on_hide_clicked(self) -> None:
        ids = self._isaretli_fisler()
        if not ids:
            return
        if QMessageBox.question(self, "Fişleri Gizle",
                                f"{len(ids)} fiş listeden kaldırılacak ve stok etkileri geri alınacak (kayıt silinmez). Devam?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        try:
            for i in ids:
                self.svc.fis_gizle(i)
        except StokFisError as e:
            QMessageBox.warning(self, "Fişleri Gizle", str(e))
        self.load_data()
        self.data_changed.emit()

    def on_excel_clicked(self) -> None:
        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(self, "Uyarı", "openpyxl bulunamadı.\npip install openpyxl")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "stok_hareketleri.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        rows, _n = self.svc.liste(self._filtre(), 1, 1_000_000)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Stok Hareketleri"
        ws.append([self.headers_dict[i][0] for i in sorted(self.headers_dict) if i])
        for h in rows:
            ws.append([h.tarih, h.fis.fis_no if h.fis else "", TURLER.get(h.tur, (h.tur,))[0], h.product.sku, h.product.name,
                       self._depo_kod.get(h.depo_id, ""), self._depo_kod.get(h.hedef_depo_id, "") if h.hedef_depo_id else "",
                       h.miktar, h.birim, h.birim_fiyat, h.tutar, h.aciklama])
        wb.save(path)

    def show_context_menu(self, pos) -> None:
        from src.desktop.managers.theme_manager import ThemeManager
        idx = self.table_view.indexAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())
        for tur, etiket in FIS_TIPLERI.items():
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
