"""TOYA ERP - Kasa Kartları / Banka & POS Kartları liste ekranı (standart 3 panelli).

Tek sınıf iki grubu yönetir (`grup="kasa"` ya da `"banka"`). Sol: işlemler (yeni kart türleri, düzenle, pasife al).
Orta: kart listesi + sayfalama. Sağ: filtreler, özet ve seyrek işlemler (Excel, gizle). Kart penceresi
`FinansHesapEditorDialog`'dur. Silme = görünümden gizleme (kayıt fiziksel olarak kalır; eski cari fişlerinde hesap adı korunur)."""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QStandardItem
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QVBoxLayout,
)

from src.desktop.services.finans_hesap_service import HESAP_TURLERI, FinansHesapService, hesap_bakiyeleri
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.screens.finans_hesap_editor import BANKA_TURLERI, FinansHesapEditorDialog
from src.desktop.ui.widgets.hareket_alt_paneli import HESAP_KOLONLAR, HareketAltPaneli, hesap_saglayici
from src.desktop.ui.widgets.money_edit import bicimle
from src.desktop.ui.widgets.pagination_widget import PaginationWidget

logger = logging.getLogger(__name__)

_BTN = """
    QPushButton { background-color: %s; color: %s; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 10px;
                  font-size: 11px; font-weight: 600; text-align: left; font-family: 'Segoe UI'; }
    QPushButton:hover { background-color: #f1f5f9; }
    QPushButton:disabled { color: #94a3b8; background-color: #f8fafc; border-color: #e2e8f0; }
"""
_INPUT = ("QComboBox, QLineEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px;"
          " background-color: white; color: #0f172a; font-size: 11px; }")

GRUPLAR = {
    "kasa": {"baslik": "Kasa Kartları", "izin": "kasa", "turler": ("kasa",), "modul": "Kasa Kartları",
             "yeni": [("💰 Yeni Kasa", "kasa")],
             "kolonlar": {0: ("☑", "select"), 1: ("Kod", "kod"), 2: ("Kasa Adı", "ad"), 3: ("Döviz", "para_birimi"),
                          4: ("Sorumlu", "sorumlu"), 5: ("Bakiye", "bakiye"), 6: ("Durum", "durum"),
                          7: ("Açıklama", "aciklama")}},
    "banka": {"baslik": "Banka & POS Kartları", "izin": "banka", "turler": BANKA_TURLERI, "modul": "Banka & POS Kartları",
              "yeni": [("🏦 Yeni Banka Hesabı", "banka"), ("💳 Yeni Kredi Kartı", "kredi_karti"), ("📟 Yeni POS", "pos")],
              "kolonlar": {0: ("☑", "select"), 1: ("Kod", "kod"), 2: ("Hesap Adı", "ad"), 3: ("Tür", "tur"), 4: ("Banka", "banka"),
                           5: ("Döviz", "para_birimi"), 6: ("Şube", "sube_adi"), 7: ("Hesap No", "hesap_no"), 8: ("IBAN", "iban"),
                           9: ("Komisyon %", "komisyon"), 10: ("Valör", "valor"), 11: ("Bakiye", "bakiye"),
                           12: ("Durum", "durum")}},
}


class FinansHesapListScreen(ThreePanelBaseWidget):
    def __init__(self, db_session=None, grup: str = "kasa", parent=None, embedded: bool = False) -> None:
        self.grup = grup
        self.cfg = GRUPLAR[grup]
        self._kayitlar: list = []
        super().__init__(db_session=db_session, profile_key=f"finans_hesap_{grup}", module_name=self.cfg["baslik"],
                         parent=parent, embedded=embedded)
        self.setObjectName("FinansHesapCanvas")
        self.svc = FinansHesapService(db_session) if db_session is not None else None

        self.pagination_widget = PaginationWidget(page_sizes=[25, 50, 100], parent=self)
        self.pagination_widget.page_changed.connect(self._sayfa_degisti)
        self.pagination_widget.page_size_changed.connect(self._sayfa_boyu_degisti)
        self.bottom_bar_layout.addWidget(self.pagination_widget)

        self.filterable_table.enable_auto_save_layout()
        # Alt panel: seçili kartın giriş/çıkış hareketleri (bir düğmeyle açılıp kapanır)
        self.alt_panel = HareketAltPaneli(db_session, HESAP_KOLONLAR, hesap_saglayici, preset_id="dbgrid_hesap_alt_hareket",
                                          durum_anahtari=f"finans_{grup}", baslik="Hareketleri")
        self.center_layout.insertWidget(self.center_layout.indexOf(self.bottom_bar_widget), self.alt_panel)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_view.doubleClicked.connect(lambda _i: self.on_edit_clicked())
        self._apply_permissions()
        if self.svc is not None:
            self.load_data()

    # ---- yapı --------------------------------------------------------------
    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return GRUPLAR[getattr(self, "grup", "kasa")]["kolonlar"]

    def setup_left_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        sec = CollapsibleSection("KART İŞLEMLERİ", is_expanded=True)
        sec.setObjectName(f"cmp.act.finans_{self.grup}")
        self.btn_yeni: list[QPushButton] = []
        for i, (etiket, tur) in enumerate(self.cfg["yeni"]):
            b = QPushButton(etiket + (" (F2)" if i == 0 else ""))
            if i == 0:
                b.setShortcut("F2")
            b.setStyleSheet(_BTN % ("#2563eb" if i == 0 else "#ffffff", "#ffffff" if i == 0 else "#1e293b"))
            b.clicked.connect(lambda _=False, t=tur: self.on_new_clicked(t))
            sec.add_widget(b)
            self.btn_yeni.append(b)
        self.btn_edit = QPushButton("✏️ Düzenle")
        self.btn_pasif = QPushButton("⏸ Pasife Al / Aktife Al")
        for b, fn in ((self.btn_edit, self.on_edit_clicked), (self.btn_pasif, self.on_pasif_clicked)):
            b.setStyleSheet(_BTN % ("#ffffff", "#1e293b"))
            b.clicked.connect(fn)
            sec.add_widget(b)
        layout.addWidget(sec)
        layout.addStretch()

    def setup_right_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        sec_f = CollapsibleSection("FİLTRELER", is_expanded=True)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Kod / ad / banka / hesap no ara...")
        self.search_box.setStyleSheet(_INPUT)
        self.search_box.textChanged.connect(self.on_filter_changed)
        self.cmb_tur, self.cmb_durum = QComboBox(), QComboBox()
        self.cmb_tur.addItem("Tüm türler", None)
        for t in self.cfg["turler"]:
            self.cmb_tur.addItem(HESAP_TURLERI[t], t)
        self.cmb_durum.addItem("Tümü", None)
        self.cmb_durum.addItem("Aktif", True)
        self.cmb_durum.addItem("Pasif", False)
        for cmb in (self.cmb_tur, self.cmb_durum):
            cmb.setStyleSheet(_INPUT + "QComboBox { combobox-popup: 0; }")
            cmb.currentIndexChanged.connect(self.on_filter_changed)
        sec_f.add_widget(self.search_box)
        if len(self.cfg["turler"]) > 1:
            sec_f.add_widget(self.cmb_tur)
        sec_f.add_widget(self.cmb_durum)
        btn_temizle = QPushButton("🧹 Filtreleri Temizle")
        btn_temizle.setStyleSheet(_BTN % ("#ffffff", "#1e293b"))
        btn_temizle.clicked.connect(self.clear_filters)
        sec_f.add_widget(btn_temizle)
        layout.addWidget(sec_f)

        sec_t = CollapsibleSection("ÖZET", is_expanded=True)
        self.lbl_adet, self.lbl_bakiye = QLabel(), QLabel()
        for w in (self.lbl_adet, self.lbl_bakiye):
            w.setWordWrap(True)
            w.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e293b;")
            sec_t.add_widget(w)
        layout.addWidget(sec_t)

        sec_d = CollapsibleSection("SEÇİLİ KART", is_expanded=True)
        self.lbl_detay = QLabel("Bir kart seçin.")
        self.lbl_detay.setWordWrap(True)
        self.lbl_detay.setStyleSheet("color: #334155; font-size: 11px;")
        sec_d.add_widget(self.lbl_detay)
        layout.addWidget(sec_d)

        sec_i = CollapsibleSection("DİĞER İŞLEMLER", is_expanded=False)
        self.btn_excel = QPushButton("📊 Excel'e Aktar")
        self.btn_hide = QPushButton("🗑️ Seçilileri Gizle")
        self.btn_excel.clicked.connect(self.on_excel_clicked)
        self.btn_hide.clicked.connect(self.on_hide_clicked)
        for b in (self.btn_excel, self.btn_hide):
            b.setStyleSheet(_BTN % ("#ffffff", "#1e293b"))
            sec_i.add_widget(b)
        layout.addWidget(sec_i)
        layout.addStretch()

    def _apply_permissions(self) -> None:
        from src.desktop.security.gate import gate
        izin = self.cfg["izin"]
        for b in self.btn_yeni:
            gate(b, f"{izin}.create", hide=True)
        gate(self.btn_edit, f"{izin}.edit", hide=True)
        gate(self.btn_pasif, f"{izin}.edit", hide=True)
        gate(self.btn_hide, f"{izin}.delete", hide=True)
        gate(self.btn_excel, f"{izin}.view", hide=True)

    # ---- veri --------------------------------------------------------------
    def on_filter_changed(self) -> None:
        if not hasattr(self, "pagination_widget") or getattr(self, "svc", None) is None:
            return
        self.current_page = 1
        self.pagination_widget.set_current_page(1)
        self.load_data()

    def clear_filters(self) -> None:
        for w in (self.search_box, self.cmb_tur, self.cmb_durum):
            w.blockSignals(True)
        self.search_box.clear()
        self.cmb_tur.setCurrentIndex(0)
        self.cmb_durum.setCurrentIndex(0)
        for w in (self.search_box, self.cmb_tur, self.cmb_durum):
            w.blockSignals(False)
        self.on_filter_changed()

    def _sayfa_degisti(self, page: int) -> None:
        self.current_page = page
        self.load_data()

    def _sayfa_boyu_degisti(self, size: int) -> None:
        self.per_page, self.current_page = size, 1
        self.load_data()

    def _filtreli(self) -> list:
        turler = [self.cmb_tur.currentData()] if self.cmb_tur.currentData() else list(self.cfg["turler"])
        liste = self.svc.liste(turler=turler, arama=self.search_box.text())
        durum = self.cmb_durum.currentData()
        return [h for h in liste if durum is None or bool(h.aktif) == durum]

    def _hucre(self, h, alan: str) -> str:
        if alan == "durum":
            return "Aktif" if h.aktif else "Pasif"
        if alan == "tur":
            return HESAP_TURLERI.get(h.tur, h.tur)
        if alan == "bakiye":
            bak = hesap_bakiyeleri(self.db, h.id)
            return " · ".join(f"{bicimle(v, 2)} {d}" for d, v in sorted(bak.items())) or f"{bicimle(0, 2)} {h.para_birimi}"
        if alan == "komisyon":
            return bicimle(h.komisyon_orani, 2) if h.komisyon_orani else ""
        if alan == "valor":
            return str(h.valor_gun) if h.valor_gun else ""
        return str(getattr(h, alan, "") or "")

    def load_data(self) -> None:
        if self.svc is None:
            return
        hepsi = self._filtreli()
        self.per_page = self.pagination_widget.current_page_size()
        self.current_page = self.pagination_widget.current_page()
        self.total_records = len(hepsi)
        bas = (self.current_page - 1) * self.per_page
        self._kayitlar = hepsi[bas:bas + self.per_page]
        m = self.table_model
        m.removeRows(0, m.rowCount())
        alanlar = [self.cfg["kolonlar"][i][1] for i in sorted(self.cfg["kolonlar"])]
        for h in self._kayitlar:
            items = []
            for alan in alanlar:
                it = QStandardItem("☐" if alan == "select" else self._hucre(h, alan))
                if alan in ("bakiye", "komisyon", "valor"):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if alan == "durum" and not h.aktif:
                    it.setForeground(QBrush(QColor("#94a3b8")))
                items.append(it)
            items[0].setCheckable(True)
            items[0].setCheckState(Qt.CheckState.Unchecked)
            items[0].setData(h.id, Qt.ItemDataRole.UserRole)
            m.appendRow(items)
        for col, (_b, alan) in self.cfg["kolonlar"].items():        # metin sütunları kırpılmasın
            if alan in ("ad", "banka", "sorumlu", "bakiye", "iban"):
                self.table_view.resizeColumnToContents(col)
        self.pagination_widget.set_total(self.total_records)
        aktif = sum(1 for h in hepsi if h.aktif)
        self.lbl_adet.setText(f"Kart: {len(hepsi)} (aktif {aktif}, pasif {len(hepsi) - aktif})")
        toplam: dict[str, float] = {}
        for h in hepsi:
            for d, v in hesap_bakiyeleri(self.db, h.id).items():
                toplam[d] = toplam.get(d, 0.0) + v
        self.lbl_bakiye.setText("Toplam bakiye: " + (" · ".join(f"{bicimle(v, 2)} {k}" for k, v in sorted(toplam.items())) or "—"))
        self.lbl_detay.setText("Bir kart seçin.")

    # ---- seçim / işlemler --------------------------------------------------
    def _secili(self):
        idx = self.table_view.selectionModel().selectedRows()
        if not idx or idx[0].row() >= len(self._kayitlar):
            return None
        return self._kayitlar[idx[0].row()]

    def _isaretliler(self) -> list[int]:
        ids = [self._kayitlar[r].id for r in range(self.table_model.rowCount())
               if r < len(self._kayitlar) and self.table_model.item(r, 0).checkState() == Qt.CheckState.Checked]
        if not ids and self._secili():
            ids = [self._secili().id]
        return ids

    def on_selection_changed(self, *_a) -> None:
        h = self._secili()
        if h is None:
            return
        self.alt_panel.set_kayit(h.id, f"{h.kod} — {h.ad}")
        satirlar = [f"<b>{h.kod}</b> — {h.ad}", f"{HESAP_TURLERI.get(h.tur, h.tur)} · {h.para_birimi}"]
        if h.banka:
            satirlar.append(f"Banka: {h.banka}" + (f" / {h.sube_adi}" if h.sube_adi else ""))
        if h.iban or h.hesap_no:
            satirlar.append(f"IBAN / Hesap: {h.iban or h.hesap_no}")
        if h.sorumlu:
            satirlar.append(f"Sorumlu: {h.sorumlu}")
        if h.komisyon_orani:
            satirlar.append(f"Komisyon: %{bicimle(h.komisyon_orani, 2)}" + (f" · Valör {h.valor_gun} gün" if h.valor_gun else ""))
        satirlar.append("Bakiye: " + self._hucre(h, "bakiye"))
        if h.doviz_kisitli:
            satirlar.append(f"Yalnızca {h.para_birimi} ile işlem")
        self.lbl_detay.setText("<br>".join(satirlar))

    def on_new_clicked(self, tur: str | None = None) -> None:
        dlg = FinansHesapEditorDialog(self.db, grup=self.grup, tur=tur, parent=self)
        if dlg.exec():
            self.load_data()
            self.data_changed.emit()

    def on_edit_clicked(self) -> None:
        h = self._secili()
        if h is None:
            return
        if FinansHesapEditorDialog(self.db, grup=self.grup, hesap_id=h.id, parent=self).exec():
            self.load_data()
            self.data_changed.emit()

    def on_pasif_clicked(self) -> None:
        for i in self._isaretliler():
            from src.core.models import FinansHesap
            h = self.db.get(FinansHesap, i)
            if h is not None:
                self.svc.pasif_yap(i, pasif=bool(h.aktif))
        self.load_data()
        self.data_changed.emit()

    def on_hide_clicked(self) -> None:
        ids = self._isaretliler()
        if not ids:
            return
        if QMessageBox.question(self, "Kartları Gizle",
                                f"{len(ids)} kart listeden kaldırılacak (kayıt silinmez; eski fişlerde hesap adı korunur). Devam?"
                                ) != QMessageBox.StandardButton.Yes:
            return
        for i in ids:
            self.svc.gizle(i)
        self.load_data()
        self.data_changed.emit()

    def on_excel_clicked(self) -> None:
        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(self, "Uyarı", "openpyxl bulunamadı.\npip install openpyxl")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", f"{self.grup}_kartlari.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = self.cfg["baslik"]
        alanlar = [self.cfg["kolonlar"][i] for i in sorted(self.cfg["kolonlar"]) if i]
        ws.append([b for b, _a in alanlar])
        for h in self._filtreli():
            ws.append([self._hucre(h, a) for _b, a in alanlar])
        wb.save(path)

    def show_context_menu(self, pos) -> None:
        from src.desktop.managers.theme_manager import ThemeManager
        idx = self.table_view.indexAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())
        for etiket, tur in self.cfg["yeni"]:
            a = QAction(f"➕ {etiket.split(' ', 1)[1]}", self)
            a.triggered.connect(lambda _=False, t=tur: self.on_new_clicked(t))
            menu.addAction(a)
        if idx.isValid():
            self.table_view.selectRow(idx.row())
            menu.addSeparator()
            for text, fn in (("✏️ Düzenle", self.on_edit_clicked), ("⏸ Pasife Al / Aktife Al", self.on_pasif_clicked),
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
