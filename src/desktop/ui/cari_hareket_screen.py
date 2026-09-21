"""TOYA ERP - Cari Hareketleri ekranı (standart 3 panelli).

Sol: hareket giriş işlemleri (Tahsilat, Ödeme, Dekontlar, Döviz). Orta: hareket listesi + sayfalama.
Sağ: filtreler, filtre toplamları, seçili hareket ve seyrek işlemler (Excel, ekstre, gizle).
Silme = görünümden gizleme (kayıt fiziksel olarak kalır)."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QStandardItem
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QFileDialog, QFrame, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton,
    QVBoxLayout,
)
from sqlalchemy import select

from src.core.models import CariHareket, Customer
from src.desktop.services.cari_hareket_service import (
    FIS_TIPLERI, TURLER, YONLER, CariHareketService, HareketFiltre, arac_etiket,
)
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.grid_delegates import apply_calendar_style
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.widgets.cari_fis_dialog import CariFisDialog
from src.desktop.ui.widgets.cari_hareket_form import CariHareketDialog
from src.desktop.ui.widgets.pagination_widget import PaginationWidget

logger = logging.getLogger(__name__)

_KIRMIZI, _YESIL = QColor("#dc2626"), QColor("#16a34a")
_BTN = """
    QPushButton { background-color: %s; color: %s; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;
                  font-size: 11px; font-weight: 600; text-align: left; font-family: 'Segoe UI'; }
    QPushButton:hover { background-color: #f1f5f9; }
    QPushButton:disabled { color: #94a3b8; background-color: #f8fafc; border-color: #e2e8f0; }
"""
_INPUT = ("QComboBox, QLineEdit, QDateEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px;"
          " background-color: white; color: #0f172a; font-size: 11px; }")


def _tl(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class CariHareketScreen(ThreePanelBaseWidget):
    def __init__(self, db_session=None, parent=None, embedded: bool = False) -> None:
        self._kayitlar: list[CariHareket] = []
        super().__init__(db_session=db_session, profile_key="cari_hareket", module_name="Cari Hareketleri",
                         parent=parent, embedded=embedded)
        self.setObjectName("CariHareketCanvas")
        self.svc = CariHareketService(db_session) if db_session is not None else None

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
            self._cari_listesini_doldur()
            self.load_data()

    # ---- yapı --------------------------------------------------------------
    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return {
            0: ("☑", "select"), 1: ("Tarih", "tarih"), 2: ("Fiş No", "fis_no"), 3: ("Tür", "tur"),
            4: ("Cari Kodu", "kod"), 5: ("Cari Ünvanı", "cari"), 6: ("Belge No", "belge_no"),
            7: ("Açıklama", "aciklama"), 8: ("Araç / Hesap", "arac"), 9: ("Vade", "vade"), 10: ("P.B.", "para_birimi"),
            11: ("Kur", "kur"), 12: ("Tutar", "tutar"), 13: ("Borç (TL)", "borc"), 14: ("Alacak (TL)", "alacak"),
        }

    def setup_left_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        sec = CollapsibleSection("HAREKET GİRİŞİ", is_expanded=True)
        sec.setObjectName("cmp.act.cari_hareket")
        self.btn_tur: dict[str, QPushButton] = {}
        kisayol = {"tahsilat": "F2", "odeme": "F3"}
        for tur, etiket in FIS_TIPLERI.items():
            ikon = {"tahsilat": "📥", "odeme": "📤", "borc_dekontu": "➖", "alacak_dekontu": "➕", "virman_borc": "🔁",
                    "acilis_borc": "🚪"}[tur]
            b = QPushButton(f"{ikon} {etiket}" + (f" ({kisayol[tur]})" if tur in kisayol else ""))
            if tur in kisayol:
                b.setShortcut(kisayol[tur])
            b.setStyleSheet(_BTN % ("#2563eb" if tur == "tahsilat" else "#ffffff", "#ffffff" if tur == "tahsilat" else "#1e293b"))
            b.clicked.connect(lambda _=False, t=tur: self.on_new_clicked(t))
            sec.add_widget(b)
            self.btn_tur[tur] = b
        self.btn_edit = QPushButton("✏️ Fişi / Hareketi Aç")
        self.btn_edit.setStyleSheet(_BTN % ("#ffffff", "#1e293b"))
        self.btn_edit.clicked.connect(self.on_edit_clicked)
        sec.add_widget(self.btn_edit)
        layout.addWidget(sec)

        sec_view = CollapsibleSection("GÖRÜNÜM", is_expanded=False)
        lbl = QLabel("Sütunlar tablo başlığına sağ tıklanarak seçilir.")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        sec_view.add_widget(lbl)
        layout.addWidget(sec_view)
        layout.addStretch()

    def setup_right_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        sec_f = CollapsibleSection("FİLTRELER", is_expanded=True)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Cari / belge no / açıklama ara...")
        self.search_box.setStyleSheet(_INPUT)
        self.search_box.textChanged.connect(self.on_filter_changed)
        self.cmb_cari = QComboBox()
        self.cmb_tur = QComboBox()
        self.cmb_para = QComboBox()
        for cmb in (self.cmb_cari, self.cmb_tur, self.cmb_para):
            cmb.setStyleSheet(_INPUT + "QComboBox { combobox-popup: 0; }")
        self.cmb_cari.setEditable(False)
        self.cmb_tur.addItem("Tüm türler", None)
        for k, (e, _y) in TURLER.items():
            self.cmb_tur.addItem(e, k)
        self.cmb_para.addItem("Tüm para birimleri", None)
        self.chk_tarih = QCheckBox("Tarih aralığı")
        self.dt_bas, self.dt_bit = QDateEdit(QDate.currentDate().addMonths(-1)), QDateEdit(QDate.currentDate())
        for d in (self.dt_bas, self.dt_bit):
            apply_calendar_style(d)
            d.setDisplayFormat("dd.MM.yyyy")
            d.setStyleSheet(_INPUT)
            d.setEnabled(False)
            d.dateChanged.connect(self.on_filter_changed)
        self.chk_tarih.toggled.connect(lambda on: (self.dt_bas.setEnabled(on), self.dt_bit.setEnabled(on), self.on_filter_changed()))
        for cmb in (self.cmb_cari, self.cmb_tur, self.cmb_para):
            cmb.currentIndexChanged.connect(self.on_filter_changed)
        for w in (self.search_box, self.cmb_cari, self.cmb_tur, self.cmb_para, self.chk_tarih, self.dt_bas, self.dt_bit):
            sec_f.add_widget(w)
        btn_temizle = QPushButton("🧹 Filtreleri Temizle")
        btn_temizle.setStyleSheet(_BTN % ("#ffffff", "#1e293b"))
        btn_temizle.clicked.connect(self.clear_filters)
        sec_f.add_widget(btn_temizle)
        layout.addWidget(sec_f)

        sec_t = CollapsibleSection("FİLTRE TOPLAMLARI", is_expanded=True)
        self.lbl_adet, self.lbl_borc, self.lbl_alacak, self.lbl_bakiye = (QLabel() for _ in range(4))
        for w in (self.lbl_adet, self.lbl_borc, self.lbl_alacak, self.lbl_bakiye):
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
        self.btn_ekstre = QPushButton("💳 Cari Ekstresi")
        self.btn_excel = QPushButton("📊 Excel'e Aktar")
        self.btn_hide = QPushButton("🗑️ Seçilileri Gizle")
        self.btn_hesaplar = QPushButton("🏦 Finans Hesapları (Kasa / Banka / KK / POS)")
        self.btn_hesaplar.clicked.connect(self.on_hesaplar_clicked)
        self.btn_ekstre.clicked.connect(self.on_ekstre_clicked)
        self.btn_excel.clicked.connect(self.on_excel_clicked)
        self.btn_hide.clicked.connect(self.on_hide_clicked)
        for b in (self.btn_ekstre, self.btn_excel, self.btn_hide, self.btn_hesaplar):
            b.setStyleSheet(_BTN % ("#ffffff", "#1e293b"))
            sec_i.add_widget(b)
        layout.addWidget(sec_i)
        layout.addStretch()

    def _apply_permissions(self) -> None:
        from src.desktop.security.gate import gate
        for b in self.btn_tur.values():
            gate(b, "cari.create", hide=True)
        gate(self.btn_edit, "cari.edit", hide=True)
        gate(self.btn_hide, "cari.delete", hide=True)
        gate(self.btn_excel, "cari.view", hide=True)
        gate(self.btn_ekstre, "cari.balance", hide=True)

    def _cari_listesini_doldur(self) -> None:
        self.cmb_cari.blockSignals(True)
        self.cmb_cari.clear()
        self.cmb_cari.addItem("Tüm cariler", None)
        for c in self.db.scalars(select(Customer).where(Customer.is_deleted == False).order_by(Customer.fullname)):  # noqa: E712
            self.cmb_cari.addItem(f"{c.customer_code or '-'}  {c.fullname}", c.id)
        self.cmb_cari.blockSignals(False)
        for code in sorted({p for (p,) in self.db.execute(select(CariHareket.para_birimi).distinct())}):
            if self.cmb_para.findData(code) < 0:
                self.cmb_para.addItem(code, code)

    # ---- veri --------------------------------------------------------------
    def _filtre(self) -> HareketFiltre:
        return HareketFiltre(
            arama=self.search_box.text(), customer_id=self.cmb_cari.currentData(), tur=self.cmb_tur.currentData(),
            para_birimi=self.cmb_para.currentData(),
            tarih_bas=self.dt_bas.date().toPyDate() if self.chk_tarih.isChecked() else None,
            tarih_bit=self.dt_bit.date().toPyDate() if self.chk_tarih.isChecked() else None,
        )

    def on_filter_changed(self) -> None:
        self.current_page = 1
        self.pagination_widget.set_current_page(1)
        self.load_data()

    def clear_filters(self) -> None:
        for w in (self.search_box, self.cmb_cari, self.cmb_tur, self.cmb_para, self.chk_tarih):
            w.blockSignals(True)
        self.search_box.clear()
        for c in (self.cmb_cari, self.cmb_tur, self.cmb_para):
            c.setCurrentIndex(0)
        self.chk_tarih.setChecked(False)
        for d in (self.dt_bas, self.dt_bit):
            d.setEnabled(False)
        for w in (self.search_box, self.cmb_cari, self.cmb_tur, self.cmb_para, self.chk_tarih):
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
        self._kayitlar, self.total_records = self.svc.list(f, self.current_page, self.per_page)
        m = self.table_model
        m.removeRows(0, m.rowCount())
        for h in self._kayitlar:
            c = h.customer
            arac = " / ".join(x for x in (arac_etiket(h.odeme_araci), h.hesap or "") if x)
            borc = h.tutar_tl if h.yon == "borc" else 0.0
            alacak = h.tutar_tl if h.yon == "alacak" else 0.0
            cells = [
                "☐", h.tarih.strftime("%d.%m.%Y"), h.fis.fis_no if h.fis else "", TURLER.get(h.tur, (h.tur,))[0],
                c.customer_code or "", c.fullname,
                h.belge_no or "", h.aciklama or "", arac, h.vade.strftime("%d.%m.%Y") if h.vade else "",
                h.para_birimi, "" if h.para_birimi == "TRY" else f"{h.kur:.4f}", _tl(h.tutar),
                _tl(borc) if borc else "", _tl(alacak) if alacak else "",
            ]
            items = [QStandardItem(t) for t in cells]
            items[0].setCheckable(True)
            items[0].setCheckState(Qt.CheckState.Unchecked)
            items[0].setData(h.id, Qt.ItemDataRole.UserRole)
            for i in (11, 12, 13, 14):
                items[i].setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            items[13].setForeground(QBrush(_KIRMIZI))
            items[14].setForeground(QBrush(_YESIL))
            m.appendRow(items)
        for col in (3, 5, 7, 8):                       # metin sütunları kırpılmasın
            self.table_view.resizeColumnToContents(col)
        self.pagination_widget.set_total(self.total_records)
        o = self.svc.ozet(f)
        self.lbl_adet.setText(f"Hareket: {o.adet}")
        self.lbl_borc.setText(f"Borç: {_tl(o.borc)} TL")
        self.lbl_borc.setStyleSheet("font-size: 12px; font-weight: 600; color: #dc2626;")
        self.lbl_alacak.setText(f"Alacak: {_tl(o.alacak)} TL")
        self.lbl_alacak.setStyleSheet("font-size: 12px; font-weight: 600; color: #16a34a;")
        yon = "Borçlu" if o.bakiye > 0 else "Alacaklı" if o.bakiye < 0 else "Kapalı"
        self.lbl_bakiye.setText(f"Bakiye: {_tl(abs(o.bakiye))} TL ({yon})")
        self.lbl_detay.setText("Bir hareket seçin.")

    # ---- seçim / işlemler --------------------------------------------------
    def _secili(self) -> CariHareket | None:
        idx = self.table_view.selectionModel().selectedRows()
        if not idx or idx[0].row() >= len(self._kayitlar):
            return None
        return self._kayitlar[idx[0].row()]

    def _isaretliler(self) -> list[int]:
        ids = [self.table_model.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in range(self.table_model.rowCount())
               if self.table_model.item(r, 0).checkState() == Qt.CheckState.Checked]
        if not ids and self._secili():
            ids = [self._secili().id]
        return ids

    def on_selection_changed(self, *_a) -> None:
        h = self._secili()
        if h is None:
            return
        self.lbl_detay.setText(
            f"<b>{TURLER.get(h.tur, (h.tur,))[0]}</b> — {YONLER.get(h.yon, h.yon)}<br>{h.customer.fullname}<br>"
            f"{h.tarih:%d.%m.%Y} · {h.para_birimi} {_tl(h.tutar)}"
            + (f" (kur {h.kur:.4f} → {_tl(h.tutar_tl)} TL)" if h.para_birimi != "TRY" else "")
            + (f"<br>Belge: {h.belge_no}" if h.belge_no else "") + (f"<br>{h.aciklama}" if h.aciklama else "")
        )

    def on_new_clicked(self, tur: str = "tahsilat") -> None:
        """Yeni cari hesap fişi (çok satırlı; her satırın cari / tür / dövizi ayrı)."""
        if CariFisDialog(self.db, tur=tur, parent=self).exec():
            self._cari_listesini_doldur()
            self.load_data()
            self.data_changed.emit()

    def on_edit_clicked(self) -> None:
        h = self._secili()
        if h is None:
            return
        dlg = CariFisDialog(self.db, fis_id=h.fis_id, parent=self) if h.fis_id else CariHareketDialog(self.db, hareket=h, parent=self)
        if dlg.exec():
            self.load_data()
            self.data_changed.emit()

    def on_hesaplar_clicked(self) -> None:
        """Ödeme aracı olarak seçilecek kasa / banka / kredi kartı / POS tanımları (bağlantıları sonraki aşama)."""
        from src.desktop.ui.widgets.finans_hesap_widgets import FinansHesapTanimDialog
        FinansHesapTanimDialog(self.db, parent=self).exec()

    def on_hide_clicked(self) -> None:
        ids = self._isaretliler()
        if not ids:
            return
        if QMessageBox.question(self, "Hareketleri Gizle",
                                f"{len(ids)} hareket listeden kaldırılacak (kayıt silinmez). Devam?") != QMessageBox.StandardButton.Yes:
            return
        self.svc.hide(ids)
        self.load_data()
        self.data_changed.emit()

    def on_ekstre_clicked(self) -> None:
        h = self._secili()
        cid = h.customer_id if h else self.cmb_cari.currentData()
        if not cid:
            QMessageBox.information(self, "Cari Ekstresi", "Bir hareket seçin veya cari filtresi belirleyin.")
            return
        from src.desktop.ui.widgets.cari_ekstre_dialog import CariEkstreDialog
        CariEkstreDialog(self.db, customer_id=cid, parent=self).exec()

    def on_excel_clicked(self) -> None:
        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(self, "Uyarı", "openpyxl bulunamadı.\npip install openpyxl")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "cari_hareketleri.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        rows, _n = self.svc.list(self._filtre(), 1, 1_000_000)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cari Hareketleri"
        ws.append([self.headers_dict[i][0] for i in sorted(self.headers_dict) if i])
        for h in rows:
            ws.append([h.tarih, h.fis.fis_no if h.fis else "", TURLER.get(h.tur, (h.tur,))[0], h.customer.customer_code, h.customer.fullname,
                       h.belge_no, h.aciklama, arac_etiket(h.odeme_araci), h.vade, h.para_birimi,
                       h.kur, h.tutar, h.tutar_tl if h.yon == "borc" else 0, h.tutar_tl if h.yon == "alacak" else 0])
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
            for text, fn in (("✏️ Fişi / Hareketi Aç", self.on_edit_clicked), ("💳 Cari Ekstresi", self.on_ekstre_clicked),
                             ("🗑️ Gizle", self.on_hide_clicked)):
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
