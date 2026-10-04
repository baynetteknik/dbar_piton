"""TOYA ERP - Geliştirme ekranı (standart 3 panelli): geliştirici ile yapay zekânın birlikte tuttuğu öneri / yapılacak / hata listesi.

Veri müşteri veritabanında DEĞİL, ayrı `dev_tracker.db` dosyasındadır; ekran yalnız geliştirme yapılarında görünür
(`dev_tracker_store.gelistirme_acik()`). Sürüm planlama, filtreleme, toplu sürüm atama, sürüm yayınlama ve `SURUM_NOTLARI.md`
otomasyonunu içerir. Silme = gizleme.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QBrush, QColor, QStandardItem
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.services.dev_tracker_store import (
    ACIK,
    DURUMLAR,
    ONCELIKLER,
    TURLER,
    DevTracker,
    DevTrackerError,
)
from src.desktop.ui.components.button_style import btn_style
from src.desktop.ui.components.collapsible_section import CollapsibleSection
from src.desktop.ui.components.dialog_style import bilgi, uyari
from src.desktop.ui.components.three_panel_base import ThreePanelBaseWidget
from src.desktop.ui.widgets.dev_item_dialog import DevItemDialog
from src.desktop.ui.widgets.dev_version_dialog import (
    DevAssignVersionDialog,
    DevReleaseDialog,
    DevVersionManageDialog,
)

logger = logging.getLogger(__name__)

_INPUT = ("QComboBox, QLineEdit { border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px;"
          " background-color: white; color: #0f172a; font-size: 11px; }")
_IKON = {"oneri": "💡", "gorev": "📌", "hata": "🐞", "gelistirme": "🛠️"}
_DURUM_RENK = {"oneri": "#64748b", "planli": "#2563eb", "devam": "#b45309", "test": "#7c3aed", "tamam": "#15803d", "reddedildi": "#94a3b8"}


class DevTrackerScreen(ThreePanelBaseWidget):
    def __init__(self, db_session=None, parent=None, embedded: bool = False, tracker: DevTracker | None = None, kullanici: str = "") -> None:
        self.tracker = tracker or DevTracker()
        self.kullanici = kullanici
        self._kayitlar: list[dict] = []
        super().__init__(db_session=db_session, profile_key="dev_tracker", module_name="Geliştirme", parent=parent, embedded=embedded)
        self.setObjectName("DevTrackerCanvas")
        self.filterable_table.enable_auto_save_layout()
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table_view.doubleClicked.connect(lambda _i: self.on_edit_clicked())
        self._filtre_listelerini_doldur()
        self.load_data()

    # ---- yapı --------------------------------------------------------------
    def setup_headers_dict(self) -> dict[int, tuple[str, str]]:
        return {
            0: ("☑", "select"),
            1: ("No", "id"),
            2: ("Tür", "tur"),
            3: ("Başlık", "baslik"),
            4: ("Modül", "modul"),
            5: ("Sürüm", "surum"),
            6: ("Öncelik", "oncelik"),
            7: ("Durum", "durum"),
            8: ("Ekleyen", "ekleyen"),
            9: ("Commit", "commit_hash"),
            10: ("Güncelleme", "guncelleme"),
        }

    def setup_left_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        # 1. YENİ KAYIT
        sec = CollapsibleSection("YENİ KAYIT", is_expanded=True)
        sec.setObjectName("cmp.act.dev_yeni")
        self.btn_yeni: dict[str, QPushButton] = {}
        for i, (tur, ad) in enumerate(TURLER.items()):
            b = QPushButton(f"{_IKON[tur]} Yeni {ad}" + (" (F2)" if i == 0 else ""))
            if i == 0:
                b.setShortcut("F2")
            b.setStyleSheet(btn_style("#2563eb" if i == 0 else "#ffffff", "#ffffff" if i == 0 else "#1e293b"))
            b.clicked.connect(lambda _=False, t=tur: self.on_new_clicked(t))
            sec.add_widget(b)
            self.btn_yeni[tur] = b
        self.btn_edit = QPushButton("✏️ Aç / Geçmiş")
        self.btn_edit.setStyleSheet(btn_style("#ffffff", "#1e293b"))
        self.btn_edit.clicked.connect(self.on_edit_clicked)
        sec.add_widget(self.btn_edit)
        layout.addWidget(sec)

        # 2. SÜRÜM & MİLESTONE YÖNETİMİ
        sec_v = CollapsibleSection("SÜRÜM & MİLESTONE", is_expanded=True)
        sec_v.setObjectName("cmp.act.dev_surum")

        self.btn_manage_versions = QPushButton("🎯 Sürümleri Planla / Yönet")
        self.btn_manage_versions.setStyleSheet(btn_style("#ffffff", "#1e3a8a"))
        self.btn_manage_versions.clicked.connect(self.on_manage_versions_clicked)
        sec_v.add_widget(self.btn_manage_versions)

        self.btn_assign_version = QPushButton("📦 Seçilileri Sürüme Ata")
        self.btn_assign_version.setStyleSheet(btn_style("#ffffff", "#1e293b"))
        self.btn_assign_version.clicked.connect(self.on_assign_version_clicked)
        sec_v.add_widget(self.btn_assign_version)

        self.btn_release_version = QPushButton("🚀 Sürümü Yayınla / Kapat")
        self.btn_release_version.setStyleSheet(btn_style("#059669", "#ffffff"))
        self.btn_release_version.clicked.connect(self.on_release_version_clicked)
        sec_v.add_widget(self.btn_release_version)

        layout.addWidget(sec_v)

        # 3. DURUM İŞLEMİ
        sec_d = CollapsibleSection("DURUM İŞLEMİ (seçililere)", is_expanded=True)
        self.btn_durum: dict[str, QPushButton] = {}
        for durum, etiket in (("planli", "📅 Planla"), ("devam", "▶ Başla / Devam"), ("test", "🧪 Teste Al"), ("tamam", "✔ Tamamlandı"), ("reddedildi", "✖ Reddet")):
            b = QPushButton(etiket)
            b.setStyleSheet(btn_style("#ffffff", "#1e293b"))
            b.clicked.connect(lambda _=False, d=durum: self.on_durum_clicked(d))
            sec_d.add_widget(b)
            self.btn_durum[durum] = b
        layout.addWidget(sec_d)
        layout.addStretch()

    def setup_right_panel_content(self, container: QFrame, layout: QVBoxLayout) -> None:
        # FİLTRELER
        sec_f = CollapsibleSection("FİLTRELER", is_expanded=True)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Başlık / modül / sürüm / commit...")
        self.search_box.setStyleSheet(_INPUT)
        self.search_box.textChanged.connect(self.on_filter_changed)

        self.cmb_tur = QComboBox()
        self.cmb_durum = QComboBox()
        self.cmb_modul = QComboBox()
        self.cmb_surum = QComboBox()
        self.cmb_oncelik = QComboBox()

        self.cmb_tur.addItem("Tüm türler", None)
        for k, e in TURLER.items():
            self.cmb_tur.addItem(e, k)

        self.cmb_durum.addItem("Tüm durumlar", None)
        self.cmb_durum.addItem("Açık olanlar", "acik")
        for k, e in DURUMLAR.items():
            self.cmb_durum.addItem(e, k)
        self.cmb_durum.setCurrentIndex(1)  # varsayılan: açık kayıtlar

        self.cmb_surum.addItem("Tüm sürümler", None)

        self.cmb_oncelik.addItem("Tüm öncelikler", None)
        for k, e in ONCELIKLER.items():
            self.cmb_oncelik.addItem(e, k)

        self.cmb_modul.addItem("Tüm modüller", None)

        for c in (self.cmb_tur, self.cmb_durum, self.cmb_surum, self.cmb_modul, self.cmb_oncelik):
            c.setStyleSheet(_INPUT + "QComboBox { combobox-popup: 0; }")
            c.currentIndexChanged.connect(self.on_filter_changed)

        sec_f.add_widget(self.search_box)
        sec_f.add_widget(self.cmb_surum)
        sec_f.add_widget(self.cmb_tur)
        sec_f.add_widget(self.cmb_durum)
        sec_f.add_widget(self.cmb_modul)
        sec_f.add_widget(self.cmb_oncelik)

        btn_temizle = QPushButton("🧹 Filtreleri Temizle")
        btn_temizle.setStyleSheet(btn_style("#ffffff", "#1e293b"))
        btn_temizle.clicked.connect(self.clear_filters)
        sec_f.add_widget(btn_temizle)
        layout.addWidget(sec_f)

        # SÜRÜM ÖZETİ & İLERLEME
        self.sec_ver_progress = CollapsibleSection("SÜRÜM İLERLEMESİ", is_expanded=True)
        self.lbl_ver_title = QLabel("Tüm Proje İlerlemesi")
        self.lbl_ver_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #1e40af;")
        self.pbar_version = QProgressBar()
        self.pbar_version.setRange(0, 100)
        self.pbar_version.setValue(0)
        self.pbar_version.setStyleSheet("""
            QProgressBar {
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                text-align: center;
                height: 16px;
                font-size: 10px;
                background-color: white;
                color: #0f172a;
            }
            QProgressBar::chunk { background-color: #2563eb; }
        """)
        self.lbl_ver_detail = QLabel("")
        self.lbl_ver_detail.setStyleSheet("font-size: 10px; color: #475569;")
        self.sec_ver_progress.add_widget(self.lbl_ver_title)
        self.sec_ver_progress.add_widget(self.pbar_version)
        self.sec_ver_progress.add_widget(self.lbl_ver_detail)
        layout.addWidget(self.sec_ver_progress)

        # GENEL ÖZET
        sec_t = CollapsibleSection("GENEL ÖZET", is_expanded=True)
        self.lbl_ozet = QLabel()
        self.lbl_ozet.setWordWrap(True)
        self.lbl_ozet.setStyleSheet("font-size: 11px; font-weight: 600; color: #1e293b;")
        sec_t.add_widget(self.lbl_ozet)
        layout.addWidget(sec_t)

        # SEÇİLİ KAYIT
        sec_s = CollapsibleSection("SEÇİLİ KAYIT", is_expanded=True)
        self.lbl_detay = QLabel("Bir kayıt seçin.")
        self.lbl_detay.setWordWrap(True)
        self.lbl_detay.setStyleSheet("color: #334155; font-size: 11px;")
        sec_s.add_widget(self.lbl_detay)
        layout.addWidget(sec_s)

        # DİĞER İŞLEMLER
        sec_i = CollapsibleSection("DİĞER İŞLEMLER", is_expanded=False)
        self.btn_surum = QPushButton("📝 Sürüm Notlarına Yaz")
        self.btn_git = QPushButton("📥 Git Takip Görevlerini Al")
        self.btn_hide = QPushButton("🗑️ Seçilileri Gizle")
        self.btn_surum.clicked.connect(self.on_surum_clicked)
        self.btn_git.clicked.connect(self.on_git_clicked)
        self.btn_hide.clicked.connect(self.on_hide_clicked)
        for b in (self.btn_surum, self.btn_git, self.btn_hide):
            b.setStyleSheet(btn_style("#ffffff", "#1e293b"))
            sec_i.add_widget(b)
        layout.addWidget(sec_i)
        layout.addStretch()

    def _filtre_listelerini_doldur(self) -> None:
        # Modüller
        secili_m = self.cmb_modul.currentData()
        self.cmb_modul.blockSignals(True)
        self.cmb_modul.clear()
        self.cmb_modul.addItem("Tüm modüller", None)
        for m in self.tracker.moduller():
            self.cmb_modul.addItem(m, m)
        self.cmb_modul.setCurrentIndex(max(self.cmb_modul.findData(secili_m), 0))
        self.cmb_modul.blockSignals(False)

        # Sürümler
        secili_s = self.cmb_surum.currentData()
        self.cmb_surum.blockSignals(True)
        self.cmb_surum.clear()
        self.cmb_surum.addItem("Tüm sürümler", None)
        self.cmb_surum.addItem("Atanmamış (Sürümsüz)", "atanmamis")
        for v in self.tracker.surumler():
            self.cmb_surum.addItem(f"📦 {v}", v)
        self.cmb_surum.setCurrentIndex(max(self.cmb_surum.findData(secili_s), 0))
        self.cmb_surum.blockSignals(False)

    # ---- veri --------------------------------------------------------------
    def _liste(self) -> list[dict]:
        d = self.cmb_durum.currentData()
        durumlar = ACIK if d == "acik" else ((d,) if d else None)
        return self.tracker.liste(
            arama=self.search_box.text(),
            durumlar=durumlar,
            tur=self.cmb_tur.currentData(),
            modul=self.cmb_modul.currentData(),
            oncelik=self.cmb_oncelik.currentData(),
            surum=self.cmb_surum.currentData(),
        )

    def on_filter_changed(self) -> None:
        if not hasattr(self, "lbl_ozet") or not hasattr(self, "table_view"):
            return
        self.load_data()

    def clear_filters(self) -> None:
        combos = (self.cmb_tur, self.cmb_durum, self.cmb_surum, self.cmb_modul, self.cmb_oncelik)
        for w in (self.search_box, *combos):
            w.blockSignals(True)
        self.search_box.clear()
        for c in combos:
            c.setCurrentIndex(0)
        for w in (self.search_box, *combos):
            w.blockSignals(False)
        self.load_data()

    def load_data(self) -> None:
        self._kayitlar = self._liste()
        m = self.table_model
        m.removeRows(0, m.rowCount())

        for r in self._kayitlar:
            surum_str = r.get("surum") or ""
            cells = [
                "",
                str(r["id"]),
                f"{_IKON.get(r['tur'], '')} {TURLER.get(r['tur'], r['tur'])}",
                r["baslik"],
                r["modul"] or "",
                surum_str,
                ONCELIKLER.get(r["oncelik"], ""),
                DURUMLAR.get(r["durum"], r["durum"]),
                r["ekleyen"] or "",
                (r["commit_hash"] or "")[:7],
                (r["guncelleme"] or "")[:16],
            ]
            items = [QStandardItem(t) for t in cells]
            items[0].setCheckable(True)
            items[0].setCheckState(Qt.CheckState.Unchecked)
            items[0].setData(r["id"], Qt.ItemDataRole.UserRole)
            items[5].setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            items[7].setForeground(QBrush(QColor(_DURUM_RENK.get(r["durum"], "#0f172a"))))
            if r["durum"] in ("tamam", "reddedildi"):
                for it in items[1:7] + items[8:]:
                    it.setForeground(QBrush(QColor("#94a3b8")))
            m.appendRow(items)

        for col in (2, 3, 4, 5):
            self.table_view.resizeColumnToContents(col)

        # Sürüm Kartını Güncelle
        selected_surum = self.cmb_surum.currentData()
        if selected_surum and selected_surum != "atanmamis":
            ver = self.tracker.surum_getir_kod(selected_surum)
            v_items = self.tracker.liste(surum=selected_surum)
            v_comp = len([x for x in v_items if x.get("durum") == "tamam"])
            v_tot = len(v_items)
            v_pct = int((v_comp / v_tot) * 100) if v_tot > 0 else 0
            self.lbl_ver_title.setText(f"📦 {selected_surum}" + (f" — {ver['title']}" if ver and ver.get("title") else ""))
            self.pbar_version.setValue(v_pct)
            t_date = ver.get("target_date") if ver else None
            t_str = f" · Hedef: {t_date}" if t_date else ""
            self.lbl_ver_detail.setText(f"{v_comp}/{v_tot} İş Tamamlandı (%{v_pct}){t_str}")
        else:
            all_items = self.tracker.liste()
            tot = len(all_items)
            comp = len([x for x in all_items if x.get("durum") == "tamam"])
            pct = int((comp / tot) * 100) if tot > 0 else 0
            self.lbl_ver_title.setText("Tüm Proje İlerlemesi")
            self.pbar_version.setValue(pct)
            self.lbl_ver_detail.setText(f"{comp}/{tot} İş Tamamlandı (%{pct})")

        o = self.tracker.ozet()
        acik = sum(v for k, v in o.items() if k in ACIK)
        self.lbl_ozet.setText(f"Açık: {acik}\nTamamlanan: {o.get('tamam', 0)}\nReddedilen: {o.get('reddedildi', 0)}\nListelenen: {len(self._kayitlar)}")
        self.lbl_detay.setText("Bir kayıt seçin.")

    # ---- seçim / işlemler --------------------------------------------------
    def _secili(self) -> dict | None:
        idx = self.table_view.selectionModel().selectedRows()
        if not idx or idx[0].row() >= len(self._kayitlar):
            return None
        return self._kayitlar[idx[0].row()]

    def _hedef_idler(self) -> list[int]:
        ids = [self._kayitlar[r]["id"] for r in range(self.table_model.rowCount())
               if r < len(self._kayitlar) and self.table_model.item(r, 0).checkState() == Qt.CheckState.Checked]
        if not ids and self._secili():
            ids = [self._secili()["id"]]
        return ids

    def on_selection_changed(self, *_a) -> None:
        r = self._secili()
        if r is None:
            return
        s = [
            f"<b>#{r['id']} {r['baslik']}</b>",
            f"{TURLER.get(r['tur'], '')} · {r['modul'] or '—'} · {ONCELIKLER.get(r['oncelik'], '')}",
            f"Sürüm: <b>{r.get('surum') or 'Atanmamış'}</b>",
            f"Durum: {DURUMLAR.get(r['durum'], r['durum'])}",
            f"Ekleyen: {r['ekleyen'] or '—'}",
        ]
        if r["commit_hash"]:
            s.append(f"Commit: {r['commit_hash'][:10]}")
        if r["tamamlanma"]:
            s.append(f"Tamamlanma: {r['tamamlanma'][:16]}")
        if r["aciklama"]:
            s.append(r["aciklama"])
        self.lbl_detay.setText("<br>".join(s))

    def on_new_clicked(self, tur: str = "oneri") -> None:
        def_surum = self.cmb_surum.currentData()
        varsayilan = {"tur": tur}
        if def_surum and def_surum != "atanmamis":
            varsayilan["surum"] = def_surum

        if DevItemDialog(self.tracker, kim=self.kullanici, varsayilan=varsayilan, parent=self).exec():
            self._filtre_listelerini_doldur()
            self.load_data()

    def on_edit_clicked(self) -> None:
        r = self._secili()
        if r and DevItemDialog(self.tracker, item_id=r["id"], kim=self.kullanici, parent=self).exec():
            self._filtre_listelerini_doldur()
            self.load_data()

    def on_manage_versions_clicked(self) -> None:
        dlg = DevVersionManageDialog(self.tracker, parent=self)
        dlg.exec()
        self._filtre_listelerini_doldur()
        self.load_data()

    def on_assign_version_clicked(self) -> None:
        ids = self._hedef_idler()
        if not ids:
            uyari(self, "Seçim Yapılmadı", "Lütfen bir sürüme atamak istediğiniz kayıtları seçiniz.")
            return

        dlg = DevAssignVersionDialog(self.tracker, selected_count=len(ids), parent=self)
        if dlg.exec():
            vcode = dlg.get_version_code()
            self.tracker.surume_gorevleri_ata(ids, vcode, kim=self.kullanici)
            self._filtre_listelerini_doldur()
            self.load_data()
            v_text = f"'{vcode}' sürümüne" if vcode else "sürümsüz duruma"
            bilgi(self, "Sürüme Atandı", f"{len(ids)} adet kayıt {v_text} başarıyla aktarıldı.")

    def on_release_version_clicked(self) -> None:
        # Sürüm belirle (filtredeki veya seçili kayıttaki)
        cur_v = self.cmb_surum.currentData()
        secili = self._secili()
        vcode = cur_v if (cur_v and cur_v != "atanmamis") else (secili.get("surum") if secili else None)

        if not vcode:
            # Sürüm seçimi için sürüm yöneticisini aç
            dlg_m = DevVersionManageDialog(self.tracker, parent=self)
            dlg_m.exec()
            self._filtre_listelerini_doldur()
            self.load_data()
            return

        dlg = DevReleaseDialog(self.tracker, version_code=vcode, parent=self)
        if dlg.exec():
            self._filtre_listelerini_doldur()
            self.load_data()

    def on_durum_clicked(self, durum: str) -> None:
        try:
            for i in self._hedef_idler():
                self.tracker.durum_degistir(i, durum, kim=self.kullanici)
        except DevTrackerError as e:
            QMessageBox.warning(self, "Geliştirme", str(e))
        self.load_data()

    def on_hide_clicked(self) -> None:
        ids = self._hedef_idler()
        if ids and QMessageBox.question(self, "Kayıtları Gizle", f"{len(ids)} kayıt listeden kaldırılacak (silinmez; geçmişi kalır). Devam?") == QMessageBox.StandardButton.Yes:
            for i in ids:
                self.tracker.gizle(i, kim=self.kullanici)
            self.load_data()

    def on_surum_clicked(self) -> None:
        yol = self.tracker.surum_notlarina_yaz()
        QMessageBox.information(self, "Sürüm Notları", f"Tamamlanan kayıtlar sürüm bazlı yazıldı:\n{yol}")

    def on_git_clicked(self) -> None:
        n = self.tracker.git_gorevlerini_al()
        QMessageBox.information(self, "Git Takip", f"{n} yeni görev alındı." if n else "Alınacak yeni görev yok.")
        self._filtre_listelerini_doldur()
        self.load_data()

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
            for text, fn in (
                ("✏️ Aç / Geçmiş", self.on_edit_clicked),
                ("📦 Sürüme Ata", self.on_assign_version_clicked),
                ("▶ Başla / Devam", lambda: self.on_durum_clicked("devam")),
                ("✔ Tamamlandı", lambda: self.on_durum_clicked("tamam")),
                ("🗑️ Gizle", self.on_hide_clicked),
            ):
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
