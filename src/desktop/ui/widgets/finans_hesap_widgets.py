"""TOYA ERP - Finans hesapları (kasa / banka / kredi kartı / POS) widget'ları.

- `FinansHesapSecimDialog`: cari seçimi gibi aramalı hesap seçim listesi (tür kısıtlı olabilir).
- `FinansHesapTanimWidget`: hücre içi düzenlemeli tanım tablosu (Genel Ayarlar'a da gömülebilir).
- `FinansHesapTanimDialog`: tanım widget'ını saran pencere.
Kasa-banka hareketlerine bağlantı sonraki aşamadır."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.core.grid_presets import GRID_PRESETS, register_preset
from src.desktop.services.finans_hesap_service import (
    HESAP_TURLERI,
    FinansHesapError,
    FinansHesapService,
)
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.components.combo_delegate import ComboDelegate
from src.desktop.ui.components.dialog_style import apply_light_dialog_style

SEC_PRESET = "dbgrid_finans_hesap_sec"
TANIM_PRESET = "dbgrid_finans_hesap"
_TUR_ANAHTAR = {v: k for k, v in HESAP_TURLERI.items()}


def _kaydir(it: QTableWidgetItem, hizala: str = "L") -> QTableWidgetItem:
    it.setTextAlignment({"L": Qt.AlignmentFlag.AlignLeft, "R": Qt.AlignmentFlag.AlignRight, "C": Qt.AlignmentFlag.AlignCenter}[hizala]
                        | Qt.AlignmentFlag.AlignVCenter)
    return it


class FinansHesapSecimDialog(QDialog):
    """Aramalı hesap seçimi. Seçilen hesap `secilen` sözlüğünde ({id, kod, ad, tur}) kalır; vazgeçilirse None."""

    def __init__(self, db, tur: str | None = None, ilk_arama: str = "", parent=None) -> None:
        super().__init__(parent)
        self.svc = FinansHesapService(db)
        self.tur = tur
        self.secilen: dict | None = None
        self._satirlar = []
        self.setWindowTitle(f"🏦 {HESAP_TURLERI.get(tur, 'Finans')} Hesabı Seçimi")
        self.setMinimumSize(720, 420)
        apply_light_dialog_style(self)
        if SEC_PRESET not in GRID_PRESETS:
            register_preset(SEC_PRESET, ["KOD", "TÜR", "AD", "PARA B.", "BANKA", "HESAP / TERMİNAL NO"],
                            [0.12, 0.12, 0.26, 0.08, 0.18, 0.24], name="Finans Hesap Seçimi")
        lyt = QVBoxLayout(self)
        self.txt_ara = QLineEdit(ilk_arama)
        self.txt_ara.setPlaceholderText("Kod, ad, banka veya hesap no ile ara...")
        self.txt_ara.textChanged.connect(self._yukle)
        lyt.addWidget(self.txt_ara)
        self.grid = AppGrid(SEC_PRESET)
        self.grid.cellDoubleClicked.connect(lambda r, _c: self._sec(r))
        lyt.addWidget(self.grid, 1)
        self.lbl_bilgi = QLabel("")
        self.lbl_bilgi.setStyleSheet("color:#64748b;")
        lyt.addWidget(self.lbl_bilgi)
        row = QHBoxLayout()
        row.addStretch()
        self.btn_sec = QPushButton("Seç")
        self.btn_sec.setDefault(True)
        self.btn_sec.clicked.connect(lambda: self._sec(self.grid.currentRow()))
        btn_iptal = QPushButton("Vazgeç")
        btn_iptal.clicked.connect(self.reject)
        row.addWidget(self.btn_sec)
        row.addWidget(btn_iptal)
        lyt.addLayout(row)
        self._yukle()

    def _yukle(self) -> None:
        self._satirlar = self.svc.liste(tur=self.tur, arama=self.txt_ara.text(), sadece_aktif=True)
        g = self.grid
        g.setRowCount(0)
        for h in self._satirlar:
            r = g.rowCount()
            g.insertRow(r)
            g.setRowHeight(r, g.effective_row_height)
            for c, t in enumerate([h.kod, HESAP_TURLERI.get(h.tur, h.tur), h.ad, h.para_birimi, h.banka or "", h.hesap_no or ""]):
                it = _kaydir(QTableWidgetItem(t), "C" if c == 3 else "L")
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                g.setItem(r, c, it)
        if self._satirlar:
            g.selectRow(0)
        self.lbl_bilgi.setText(f"{len(self._satirlar)} hesap" if self._satirlar else
                               "Tanımlı hesap yok. Cari Hareketleri > Diğer İşlemler > Finans Hesapları'ndan ekleyin.")

    def _sec(self, r: int) -> None:
        if 0 <= r < len(self._satirlar):
            h = self._satirlar[r]
            self.secilen = {"id": h.id, "kod": h.kod, "ad": h.ad, "tur": h.tur}
            self.accept()


class FinansHesapTanimWidget(QWidget):
    """Finans hesap tanımları: standart, hücre içi düzenlemeli AppGrid + Yeni / Kaydet / Gizle."""

    COLS = ["KOD", "TÜR", "AD", "PARA B.", "BANKA", "HESAP / TERMİNAL NO", "KOMİSYON %", "DURUM"]
    C_KOD, C_TUR, C_AD, C_PARA, C_BANKA, C_NO, C_KOM, C_DURUM = range(8)

    def __init__(self, db_session, parent=None) -> None:
        super().__init__(parent)
        self.db = db_session
        self.svc = FinansHesapService(db_session)
        if TANIM_PRESET not in GRID_PRESETS:
            register_preset(TANIM_PRESET, self.COLS, [0.10, 0.10, 0.24, 0.07, 0.17, 0.20, 0.06, 0.06],
                            ["L", "L", "L", "C", "L", "L", "R", "C"], name="Finans Hesap Tanımları")
        lyt = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.btn_yeni = QPushButton("➕ Yeni Hesap")
        self.btn_kaydet = QPushButton("💾 Kaydet")
        self.btn_gizle = QPushButton("🗑️ Seçiliyi Gizle")
        for b in (self.btn_yeni, self.btn_kaydet, self.btn_gizle):
            bar.addWidget(b)
        bar.addStretch()
        lyt.addLayout(bar)
        self.lbl_mesaj = QLabel("")
        self.lbl_mesaj.setWordWrap(True)
        self.grid = AppGrid(TANIM_PRESET, editable=True)
        self.grid.setItemDelegateForColumn(self.C_TUR, ComboDelegate(lambda: list(HESAP_TURLERI.values()), self.grid))
        self.grid.setItemDelegateForColumn(self.C_DURUM, ComboDelegate(lambda: ["Aktif", "Pasif"], self.grid))
        self.grid.context_actions_provider = lambda: [("➕ Yeni Hesap", self.yeni), ("🗑️ Seçiliyi Gizle", self.gizle)]
        self.grid.enable_layout_persistence(db_session)
        lyt.addWidget(self.grid, 1)
        lyt.addWidget(self.lbl_mesaj)
        self.btn_yeni.clicked.connect(self.yeni)
        self.btn_kaydet.clicked.connect(self.kaydet)
        self.btn_gizle.clicked.connect(self.gizle)
        self.yukle()

    def _satir_ekle(self, h=None) -> int:
        g = self.grid
        r = g.rowCount()
        g.insertRow(r)
        g.setRowHeight(r, g.effective_row_height)
        vals = ["", HESAP_TURLERI["kasa"], "", "TRY", "", "", "", "Aktif"]
        if h is not None:
            vals = [h.kod, HESAP_TURLERI.get(h.tur, h.tur), h.ad, h.para_birimi, h.banka or "", h.hesap_no or "",
                    "" if h.komisyon_orani is None else f"{h.komisyon_orani:g}", "Aktif" if h.aktif else "Pasif"]
        for c, t in enumerate(vals):
            g.setItem(r, c, _kaydir(QTableWidgetItem(t), {self.C_PARA: "C", self.C_KOM: "R", self.C_DURUM: "C"}.get(c, "L")))
        g.item(r, self.C_KOD).setData(Qt.ItemDataRole.UserRole, h.id if h is not None else None)
        return r

    def yukle(self) -> None:
        self.grid.setRowCount(0)
        for h in self.svc.liste():
            self._satir_ekle(h)

    def yeni(self) -> None:
        r = self._satir_ekle()
        tur = _TUR_ANAHTAR.get(self.grid.item(r, self.C_TUR).text(), "kasa")
        self.grid.item(r, self.C_KOD).setText(self.svc.sonraki_kod(tur))
        self.grid.setCurrentCell(r, self.C_AD)
        self.grid.editItem(self.grid.item(r, self.C_AD))

    def kaydet(self) -> bool:
        hatalar, kaydedilen = [], 0
        for r in range(self.grid.rowCount()):
            t = lambda c: self.grid.item(r, c).text().strip()  # noqa: E731
            hid = self.grid.item(r, self.C_KOD).data(Qt.ItemDataRole.UserRole)
            try:
                kom = t(self.C_KOM).replace(",", ".")
                h = self.svc.kaydet({
                    "kod": t(self.C_KOD), "tur": _TUR_ANAHTAR.get(t(self.C_TUR)), "ad": t(self.C_AD), "para_birimi": t(self.C_PARA),
                    "banka": t(self.C_BANKA), "hesap_no": t(self.C_NO), "komisyon_orani": float(kom) if kom else None,
                    "aktif": t(self.C_DURUM) != "Pasif"}, hesap_id=hid)
                self.grid.item(r, self.C_KOD).setData(Qt.ItemDataRole.UserRole, h.id)
                self.grid.item(r, self.C_KOD).setText(h.kod)
                kaydedilen += 1
            except (FinansHesapError, ValueError) as e:
                self.db.rollback()
                hatalar.append(f"Satır {r + 1}: {e}")
        self.lbl_mesaj.setStyleSheet("color:#dc2626; font-weight:600;" if hatalar else "color:#16a34a; font-weight:600;")
        self.lbl_mesaj.setText("\n".join(hatalar) if hatalar else f"✔ {kaydedilen} hesap kaydedildi.")
        return not hatalar

    def gizle(self) -> None:
        for r in sorted({i.row() for i in self.grid.selectedIndexes()}, reverse=True):
            hid = self.grid.item(r, self.C_KOD).data(Qt.ItemDataRole.UserRole)
            if hid:
                self.svc.gizle(hid)
            self.grid.removeRow(r)


class FinansHesapTanimDialog(QDialog):
    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Finans Hesapları — Kasa / Banka / Kredi Kartı / POS")
        self.setWindowState(Qt.WindowState.WindowMaximized)          # ekran standardı: ekranı kaplayarak açılır
        apply_light_dialog_style(self)
        lyt = QVBoxLayout(self)
        info = QLabel("Cari fişlerinde ödeme aracı olarak seçilecek hesaplar. Kasa/banka hareketlerine bağlantı sonraki aşamada yapılır.")
        info.setStyleSheet("color:#64748b;")
        info.setWordWrap(True)
        lyt.addWidget(info)
        self.tanim = FinansHesapTanimWidget(db)
        lyt.addWidget(self.tanim, 1)
        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton("Kapat")
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lyt.addLayout(row)
