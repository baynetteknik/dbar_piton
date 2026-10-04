"""TOYA ERP - Görevler ekranı (standart 3 panelli): görev / randevu / hatırlatma; Liste, Pano (Kanban) ve Takvim görünümleri.

Sol: yeni kayıt (Görev, Randevu, Hatırlatma), hızlı filtreler (benim, bugün, gecikmiş, açık) ve durum işlemleri.
Orta: seçilen görünüm. Sağ: filtreler, özet, seçili görev ve seyrek işlemler (Excel, gizle).
Genel amaçlıdır: `ilgili=("servis", 42, "Servis #42")` verilirse yalnızca o kayda bağlı görevler listelenir ve yeni görevler o kayda bağlanır
(ör. servis ekranı bu ekranı gömerek kendi görevlerini gösterebilir). Silme = gizleme."""

from __future__ import annotations

import logging
from datetime import date, datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QStandardItem
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.gorev_service import (
    ACIK_DURUMLAR,
    DURUMLAR,
    KATEGORILER,
    ONCELIKLER,
    TEKRARLAR,
    TURLER,
    GorevError,
    GorevFiltre,
    GorevService,
)
from src.desktop.ui.components.button_style import btn_style
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.widgets.gorev_dialog import GorevDialog
from src.desktop.ui.widgets.gorev_kanban_widget import GorevKanbanWidget
from src.desktop.ui.widgets.gorev_takvim_widget import GorevTakvimWidget
from src.desktop.ui.widgets.pagination_widget import PaginationWidget

logger = logging.getLogger(__name__)

_INPUT = ("QComboBox, QLineEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px;"
          " background-color: white; color: #0f172a; font-size: 11px; }")
_ONCELIK_RENK = {1: "#64748b", 2: "#0f172a", 3: "#b45309", 4: "#b91c1c"}
_IKON = {"gorev": "✅", "randevu": "📅", "hatirlatma": "🔔"}
_GORUNUMLER = (("liste", "📋 Liste"), ("pano", "🗂 Pano"), ("takvim", "📅 Takvim"))
_HIZLI = (("hepsi", "📂 Tümü"), ("acik", "🟢 Açık görevler"), ("benim", "👤 Benim görevlerim"), ("bugun", "📆 Bugün"), ("gecikmis", "⚠ Gecikmiş"))


class GorevlerScreen(ThreePanelBaseWidget):

    BUS_KONULARI = ("gorev",)
    def __init__(self, db_session=None, parent=None, embedded: bool = False, kullanici: str = "",
                 ilgili: tuple[str, int, str] | None = None) -> None:
        self.kullanici = kullanici
        self.ilgili = ilgili
        self.gorunum = "liste"
        self.hizli = "hepsi"
        self._kayitlar: list = []
        super().__init__(db_session=db_session, profile_key="gorevler", module_name="Görevler", parent=parent, embedded=embedded)
        self.setObjectName("GorevlerCanvas")
        self.svc = GorevService(db_session) if db_session is not None else None

        self.pagination_widget = PaginationWidget(page_sizes=[25, 50, 100], parent=self)
        self.pagination_widget.page_changed.connect(self._sayfa_degisti)
        self.pagination_widget.page_size_changed.connect(self._sayfa_boyu_degisti)
        self.bottom_bar_layout.addWidget(self.pagination_widget)

        # görünüm seçici + pano + takvim (orta bölge)
        bar = QWidget()
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        self.btn_gorunum: dict[str, QPushButton] = {}
        for k, e in _GORUNUMLER:
            b = QPushButton(e)
            b.setCheckable(True)
            b.setStyleSheet(btn_style("#ffffff", "#1e293b"))
            b.clicked.connect(lambda _=False, g=k: self.set_gorunum(g))
            h.addWidget(b)
            self.btn_gorunum[k] = b
        h.addStretch()
        self.center_layout.insertWidget(1, bar)
        self.kanban = GorevKanbanWidget()
        self.takvim = GorevTakvimWidget()
        i = self.center_layout.indexOf(self.bottom_bar_widget)
        self.center_layout.insertWidget(i, self.kanban, 1)
        self.center_layout.insertWidget(i + 1, self.takvim, 1)
        self.kanban.durum_degisti.connect(self._surukle_birak)
        self.kanban.gorev_acildi.connect(self.gorev_ac)
        self.takvim.gorev_acildi.connect(self.gorev_ac)
        self.takvim.gun_yeni.connect(self._takvimden_yeni)
        self.takvim.ay_degisti.connect(lambda *_a: self.load_data())

        self.filterable_table.enable_auto_save_layout()
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_view.doubleClicked.connect(lambda _i: self.on_edit_clicked())
        self._apply_permissions()
        self._gorunum_uygula()
        if self.svc is not None:
            self.load_data()

    # ---- yapı --------------------------------------------------------------
    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return {0: ("☑", "select"), 1: ("Başlık", "baslik"), 2: ("Tür", "tur"), 3: ("Kategori", "kategori"), 4: ("Öncelik", "oncelik"),
                5: ("Durum", "durum"), 6: ("Atanan", "atanan"), 7: ("Başlangıç", "baslangic"), 8: ("Bitiş", "bitis"),
                9: ("Bağlı Kayıt", "ilgili"), 10: ("Tekrar", "tekrar")}

    def setup_left_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        sec = CollapsibleSection("YENİ KAYIT", is_expanded=True)
        sec.setObjectName("cmp.act.gorev_yeni")
        self.btn_yeni: dict[str, QPushButton] = {}
        for i, (tur, ad) in enumerate(TURLER.items()):
            b = QPushButton(f"{_IKON[tur]} Yeni {ad}" + (" (F2)" if i == 0 else ""))
            if i == 0:
                b.setShortcut("F2")
            b.setStyleSheet(btn_style("#2563eb" if i == 0 else "#ffffff", "#ffffff" if i == 0 else "#1e293b"))
            b.clicked.connect(lambda _=False, t=tur: self.on_new_clicked(t))
            sec.add_widget(b)
            self.btn_yeni[tur] = b
        self.btn_edit = QPushButton("✏️ Aç / Düzenle")
        self.btn_edit.setStyleSheet(btn_style("#ffffff", "#1e293b"))
        self.btn_edit.clicked.connect(self.on_edit_clicked)
        sec.add_widget(self.btn_edit)
        layout.addWidget(sec)

        sec_h = CollapsibleSection("HIZLI FİLTRE", is_expanded=True)
        self.btn_hizli: dict[str, QPushButton] = {}
        for k, e in _HIZLI:
            b = QPushButton(e)
            b.setCheckable(True)
            b.setStyleSheet(btn_style("#ffffff", "#1e293b"))
            b.clicked.connect(lambda _=False, x=k: self.set_hizli(x))
            sec_h.add_widget(b)
            self.btn_hizli[k] = b
        self.btn_hizli["hepsi"].setChecked(True)
        layout.addWidget(sec_h)

        sec_d = CollapsibleSection("DURUM İŞLEMİ (seçililere)", is_expanded=True)
        self.btn_durum: dict[str, QPushButton] = {}
        for durum, etiket in (("tamam", "✔ Tamamlandı"), ("devam", "▶ Devam Ediyor"), ("inceleme", "🔎 İncelemeye Al"),
                              ("yapilacak", "↺ Yeniden Aç"), ("iptal", "✖ İptal Et")):
            b = QPushButton(etiket)
            b.setStyleSheet(btn_style("#ffffff", "#1e293b"))
            b.clicked.connect(lambda _=False, d=durum: self.on_durum_clicked(d))
            sec_d.add_widget(b)
            self.btn_durum[durum] = b
        layout.addWidget(sec_d)
        layout.addStretch()

    def setup_right_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        sec_f = CollapsibleSection("FİLTRELER", is_expanded=True)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Başlık / açıklama / atanan / bağlı kayıt...")
        self.search_box.setStyleSheet(_INPUT)
        self.search_box.textChanged.connect(self.on_filter_changed)
        self.cmb_durum, self.cmb_oncelik, self.cmb_kategori, self.cmb_tur = QComboBox(), QComboBox(), QComboBox(), QComboBox()
        self.cmb_durum.addItem("Tüm durumlar", None)
        for k, e in DURUMLAR.items():
            self.cmb_durum.addItem(e, k)
        self.cmb_oncelik.addItem("Tüm öncelikler", None)
        for k, e in ONCELIKLER.items():
            self.cmb_oncelik.addItem(e, k)
        self.cmb_kategori.addItem("Tüm kategoriler", None)
        for k, e in KATEGORILER.items():
            self.cmb_kategori.addItem(e, k)
        self.cmb_tur.addItem("Görev + randevu + hatırlatma", None)
        for k, e in TURLER.items():
            self.cmb_tur.addItem(e, k)
        for c in (self.cmb_durum, self.cmb_oncelik, self.cmb_kategori, self.cmb_tur):
            c.setStyleSheet(_INPUT + "QComboBox { combobox-popup: 0; }")
            c.currentIndexChanged.connect(self.on_filter_changed)
        sec_f.add_widget(self.search_box)
        for c in (self.cmb_tur, self.cmb_durum, self.cmb_oncelik, self.cmb_kategori):
            sec_f.add_widget(c)
        btn_temizle = QPushButton("🧹 Filtreleri Temizle")
        btn_temizle.setStyleSheet(btn_style("#ffffff", "#1e293b"))
        btn_temizle.clicked.connect(self.clear_filters)
        sec_f.add_widget(btn_temizle)
        layout.addWidget(sec_f)

        sec_t = CollapsibleSection("ÖZET", is_expanded=True)
        self.lbl_ozet = QLabel()
        self.lbl_ozet.setWordWrap(True)
        self.lbl_ozet.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e293b;")
        sec_t.add_widget(self.lbl_ozet)
        layout.addWidget(sec_t)

        sec_d = CollapsibleSection("SEÇİLİ GÖREV", is_expanded=True)
        self.lbl_detay = QLabel("Bir görev seçin.")
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
            b.setStyleSheet(btn_style("#ffffff", "#1e293b"))
            sec_i.add_widget(b)
        layout.addWidget(sec_i)
        layout.addStretch()

    def _apply_permissions(self) -> None:
        from src.desktop.security.gate import gate
        for b in self.btn_yeni.values():
            gate(b, "gorev.create", hide=True)
        gate(self.btn_edit, "gorev.edit", hide=True)
        for b in self.btn_durum.values():
            gate(b, "gorev.edit", hide=True)
        gate(self.btn_hide, "gorev.delete", hide=True)
        gate(self.btn_excel, "gorev.view", hide=True)

    # ---- görünüm / filtre ----------------------------------------------------------
    def set_gorunum(self, g: str) -> None:
        self.gorunum = g
        self._gorunum_uygula()
        self.load_data()

    def _gorunum_uygula(self) -> None:
        for k, b in self.btn_gorunum.items():
            b.setChecked(k == self.gorunum)
        liste = self.gorunum == "liste"
        self.filterable_table.setVisible(liste)
        self.bottom_bar_widget.setVisible(liste)
        self.kanban.setVisible(self.gorunum == "pano")
        self.takvim.setVisible(self.gorunum == "takvim")

    def set_hizli(self, k: str) -> None:
        self.hizli = k
        for x, b in self.btn_hizli.items():
            b.setChecked(x == k)
        self.on_filter_changed()

    def _filtre(self) -> GorevFiltre:
        f = GorevFiltre(arama=self.search_box.text(), oncelik=self.cmb_oncelik.currentData(), kategori=self.cmb_kategori.currentData(),
                        tur=self.cmb_tur.currentData())
        if self.cmb_durum.currentData():
            f.durumlar = (self.cmb_durum.currentData(),)
        if self.ilgili:
            f.ilgili_tur, f.ilgili_id = self.ilgili[0], self.ilgili[1]
        if self.hizli == "acik":
            f.durumlar = ACIK_DURUMLAR
        elif self.hizli == "benim":
            f.atanan = self.kullanici or "\0"
        elif self.hizli == "bugun":
            f.tarih_bas = f.tarih_bit = date.today()
        elif self.hizli == "gecikmis":
            f.sadece_gecikmis = True
        return f

    def on_filter_changed(self) -> None:
        if not hasattr(self, "pagination_widget") or getattr(self, "svc", None) is None:
            return
        self.current_page = 1
        self.pagination_widget.set_current_page(1)
        self.load_data()

    def clear_filters(self) -> None:
        combos = (self.cmb_durum, self.cmb_oncelik, self.cmb_kategori, self.cmb_tur)
        for w in (self.search_box, *combos):
            w.blockSignals(True)
        self.search_box.clear()
        for c in combos:
            c.setCurrentIndex(0)
        for w in (self.search_box, *combos):
            w.blockSignals(False)
        self.set_hizli("hepsi")

    def _sayfa_degisti(self, page: int) -> None:
        self.current_page = page
        self.load_data()

    def _sayfa_boyu_degisti(self, size: int) -> None:
        self.per_page, self.current_page = size, 1
        self.load_data()

    # ---- veri --------------------------------------------------------------
    @staticmethod
    def _zaman(d: datetime | None, tum_gun: bool = False) -> str:
        return "" if d is None else d.strftime("%d.%m.%Y" if tum_gun else "%d.%m.%Y %H:%M")

    def load_data(self) -> None:
        if self.svc is None:
            return
        f = self._filtre()
        simdi = datetime.now()
        if self.gorunum == "liste":
            self.per_page = self.pagination_widget.current_page_size()
            self.current_page = self.pagination_widget.current_page()
            self._kayitlar, self.total_records = self.svc.liste(f, self.current_page, self.per_page)
            self._liste_doldur(simdi)
            self.pagination_widget.set_total(self.total_records)
        elif self.gorunum == "pano":
            self.kanban.set_gorevler(self.svc.hepsi(f), lambda g: self.svc.gecikmis_mi(g, simdi))
        else:
            bas, bit = self.takvim.aralik()
            self.takvim.set_olaylar(self.svc.takvim(bas, bit, f))
        o = self.svc.ozet(f, simdi)
        self.lbl_ozet.setText(f"Toplam: {o.toplam}\nAçık: {o.acik}   Tamamlanan: {o.tamam}\nBugün: {o.bugun}\nGecikmiş: {o.gecikmis}")
        self.lbl_ozet.setStyleSheet("font-size: 12px; font-weight: 600; color: " + ("#b91c1c" if o.gecikmis else "#1e293b") + ";")
        self.lbl_detay.setText("Bir görev seçin.")

    def _liste_doldur(self, simdi: datetime) -> None:
        m = self.table_model
        m.removeRows(0, m.rowCount())
        for g in self._kayitlar:
            gec = self.svc.gecikmis_mi(g, simdi)
            cells = ["", g.baslik, f"{_IKON.get(g.tur, '')} {TURLER.get(g.tur, g.tur)}", KATEGORILER.get(g.kategori, g.kategori),
                     ONCELIKLER.get(g.oncelik, ""), DURUMLAR.get(g.durum, g.durum), g.atanan or "", self._zaman(g.baslangic, g.tum_gun),
                     ("⚠ " if gec else "") + self._zaman(g.bitis, g.tum_gun), (f"{g.ilgili_tur}: {g.ilgili_ad}" if g.ilgili_tur else ""),
                     TEKRARLAR.get(g.tekrar, "") if g.tekrar != "yok" else ""]
            items = [QStandardItem(t) for t in cells]
            items[0].setCheckable(True)
            items[0].setCheckState(Qt.CheckState.Unchecked)
            items[0].setData(g.id, Qt.ItemDataRole.UserRole)
            items[4].setForeground(QBrush(QColor(_ONCELIK_RENK.get(g.oncelik, "#0f172a"))))
            if gec:
                items[8].setForeground(QBrush(QColor("#b91c1c")))
            if g.durum in ("tamam", "iptal"):
                for it in items[1:]:
                    it.setForeground(QBrush(QColor("#94a3b8")))
            m.appendRow(items)
        for col in (1, 3, 9):
            self.table_view.resizeColumnToContents(col)

    # ---- seçim / işlemler --------------------------------------------------
    def _secili(self):
        idx = self.table_view.selectionModel().selectedRows()
        if not idx or idx[0].row() >= len(self._kayitlar):
            return None
        return self._kayitlar[idx[0].row()]

    def _hedef_idler(self) -> list[int]:
        """Durum/gizle işleminin hedefi: listede işaretliler ya da seçili satır; panoda seçili kart."""
        if self.gorunum == "pano":
            return [int(l.currentItem().data(Qt.ItemDataRole.UserRole)) for l in self.kanban.listeler.values() if l.currentItem() is not None][:1]
        ids = [self._kayitlar[r].id for r in range(self.table_model.rowCount())
               if r < len(self._kayitlar) and self.table_model.item(r, 0).checkState() == Qt.CheckState.Checked]
        if not ids and self._secili():
            ids = [self._secili().id]
        return ids

    def on_selection_changed(self, *_a) -> None:
        g = self._secili()
        if g is None:
            return
        satirlar = [f"<b>{g.baslik}</b>", f"{_IKON.get(g.tur, '')} {TURLER.get(g.tur, g.tur)} · {KATEGORILER.get(g.kategori, '')} · {ONCELIKLER.get(g.oncelik, '')}",
                    f"Durum: {DURUMLAR.get(g.durum, g.durum)}"]
        if g.atanan:
            satirlar.append(f"Atanan: {g.atanan}")
        if g.baslangic or g.bitis:
            satirlar.append(f"{self._zaman(g.baslangic, g.tum_gun)}" + (f" → {self._zaman(g.bitis, g.tum_gun)}" if g.bitis else ""))
        if g.tekrar != "yok":
            satirlar.append(f"Tekrar: {TEKRARLAR[g.tekrar]}")
        if g.ilgili_tur:
            satirlar.append(f"Bağlı: {g.ilgili_tur} — {g.ilgili_ad or ''}")
        if g.aciklama:
            satirlar.append(g.aciklama)
        self.lbl_detay.setText("<br>".join(satirlar))

    def _varsayilan(self, tur: str) -> dict:
        v: dict = {"tur": tur, "atanan": self.kullanici}
        if self.ilgili:
            v.update(ilgili_tur=self.ilgili[0], ilgili_id=self.ilgili[1], ilgili_ad=self.ilgili[2])
        return v

    def on_new_clicked(self, tur: str = "gorev", varsayilan: dict | None = None) -> None:
        v = dict(self._varsayilan(tur), **(varsayilan or {}))
        if GorevDialog(self.db, varsayilan=v, kullanici=self.kullanici, parent=self).exec():
            self.load_data()
            self.data_changed.emit()

    def _takvimden_yeni(self, gun: date) -> None:
        self.on_new_clicked("gorev", {"bitis": datetime.combine(gun, datetime.min.time()).replace(hour=17)})

    def gorev_ac(self, gorev_id: int) -> None:
        if GorevDialog(self.db, gorev_id=gorev_id, kullanici=self.kullanici, parent=self).exec():
            self.load_data()
            self.data_changed.emit()

    def on_edit_clicked(self) -> None:
        ids = self._hedef_idler()
        if ids:
            self.gorev_ac(ids[0])

    def _surukle_birak(self, gorev_id: int, durum: str) -> None:
        try:
            self.svc.durum_degistir(gorev_id, durum)
        except GorevError as e:
            QMessageBox.warning(self, "Görev", str(e))
        self.load_data()
        self.data_changed.emit()

    def on_durum_clicked(self, durum: str) -> None:
        try:
            for i in self._hedef_idler():
                self.svc.durum_degistir(i, durum)
        except GorevError as e:
            QMessageBox.warning(self, "Görev", str(e))
        self.load_data()
        self.data_changed.emit()

    def on_hide_clicked(self) -> None:
        ids = self._hedef_idler()
        if not ids:
            return
        if QMessageBox.question(self, "Görevleri Gizle", f"{len(ids)} görev listeden kaldırılacak (kayıt silinmez). Devam?") != QMessageBox.StandardButton.Yes:
            return
        self.svc.gizle(ids)
        self.load_data()
        self.data_changed.emit()

    def on_excel_clicked(self) -> None:
        try:
            import openpyxl
        except ImportError:
            QMessageBox.warning(self, "Uyarı", "openpyxl bulunamadı.\npip install openpyxl")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Excel Kaydet", "gorevler.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Görevler"
        ws.append([self.headers_dict[i][0] for i in sorted(self.headers_dict) if i])
        for g in self.svc.hepsi(self._filtre()):
            ws.append([g.baslik, TURLER.get(g.tur, g.tur), KATEGORILER.get(g.kategori, ""), ONCELIKLER.get(g.oncelik, ""), DURUMLAR.get(g.durum, ""),
                       g.atanan, g.baslangic, g.bitis, f"{g.ilgili_tur or ''} {g.ilgili_ad or ''}".strip(), g.tekrar if g.tekrar != "yok" else ""])
        wb.save(path)

    def show_context_menu(self, pos) -> None:
        from src.desktop.managers.theme_manager import ThemeManager
        idx = self.table_view.indexAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(ThemeManager().get_context_menu_stylesheet())
        for tur, ad in TURLER.items():
            a = QAction(f"➕ {ad}", self)
            a.triggered.connect(lambda _=False, t=tur: self.on_new_clicked(t))
            menu.addAction(a)
        if idx.isValid():
            self.table_view.selectRow(idx.row())
            menu.addSeparator()
            for text, fn in (("✏️ Aç / Düzenle", self.on_edit_clicked), ("✔ Tamamlandı", lambda: self.on_durum_clicked("tamam")),
                             ("▶ Devam Ediyor", lambda: self.on_durum_clicked("devam")), ("🗑️ Gizle", self.on_hide_clicked)):
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
