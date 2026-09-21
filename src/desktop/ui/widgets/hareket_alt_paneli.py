"""TOYA ERP - HareketAltPaneli: liste ekranlarının altında bir düğmeyle açılıp kapanan "seçili kaydın hareketleri" bölümü.

Cari, Kasa ve Banka listelerinde seçili kaydın giriş/çıkış (borç/alacak) hareketleri altta, ana listeyi kapatmadan görünür
(bkz. klasik muhasebe programlarındaki alt hareket sekmesi). Bölüm açık/kapalı durumu hatırlanır; kapalıyken veri yüklenmez.

    panel = HareketAltPaneli(db, KOLONLAR, cari_saglayici, preset_id="dbgrid_cari_alt_hareket", durum_anahtari="cari")
    panel.set_kayit(customer_id, "ACME Ltd.")          # liste seçimi değişince
Sağlayıcı: `saglayici(db, kayit_id) -> PanelVeri` (satırlar hazır metin, ozet alt çubuk metnidir).
Hareket girişi ve ayrıntı ekranları ayrıdır (kenar panellerindeki işlemler); bu bölüm yalnızca izlemedir."""

from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem, QVBoxLayout

from src.desktop.core.grid_presets import GRID_PRESETS, register_preset
from src.desktop.services import settings_store
from src.desktop.ui.components.app_grid import AppGrid
from src.desktop.ui.widgets.money_edit import bicimle

_RENK = {"borc": QColor("#dc2626"), "alacak": QColor("#16a34a"), "giris": QColor("#16a34a"), "cikis": QColor("#dc2626")}


@dataclass(frozen=True)
class PanelKolon:
    baslik: str
    oran: float
    hiza: str = "L"                 # L | R | C
    renk: str | None = None         # borc | alacak | giris | cikis: dolu ve sıfırdan farklıysa renklendirilir


@dataclass
class PanelVeri:
    satirlar: list[list[str]] = field(default_factory=list)
    ozet: str = ""


_HIZA = {"L": Qt.AlignmentFlag.AlignLeft, "R": Qt.AlignmentFlag.AlignRight, "C": Qt.AlignmentFlag.AlignCenter}


class HareketAltPaneli(QFrame):
    def __init__(self, db, kolonlar: list[PanelKolon], saglayici, preset_id: str, durum_anahtari: str,
                 baslik: str = "Hareketleri", varsayilan_acik: bool = True, yukseklik: int = 230, parent=None) -> None:
        super().__init__(parent)
        self.db, self.kolonlar, self.saglayici = db, kolonlar, saglayici
        self._anahtar = f"panel.{durum_anahtari}.acik"
        self._baslik = baslik
        self._kayit_id = None
        self._kayit_adi = ""
        self.setObjectName("HareketAltPaneli")
        self.setStyleSheet("#HareketAltPaneli { background:#f8fafc; border:1px solid #cbd5e1; border-radius:4px; }")
        if preset_id not in GRID_PRESETS:
            register_preset(preset_id, [k.baslik for k in kolonlar], [k.oran for k in kolonlar], [k.hiza for k in kolonlar],
                            name=f"{baslik} (alt panel)")
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(3)
        ust = QHBoxLayout()
        self.btn_toggle = QPushButton()
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setStyleSheet(
            "QPushButton { background:#1e3a8a; color:white; border:none; border-radius:4px; padding:4px 12px;"
            " font-size:11px; font-weight:700; text-align:left; }"
            " QPushButton:hover { background:#2563eb; }")
        self.btn_toggle.clicked.connect(self.toggle)
        self.lbl_kayit = QLabel("")
        self.lbl_kayit.setStyleSheet("font-size:11px; font-weight:600; color:#334155;")
        ust.addWidget(self.btn_toggle)
        ust.addWidget(self.lbl_kayit, 1)
        v.addLayout(ust)

        self.body = QFrame()
        bv = QVBoxLayout(self.body)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(3)
        self.grid = AppGrid(preset_id)
        if db is not None:
            self.grid.enable_layout_persistence(db)
        self.grid.setMinimumHeight(yukseklik)
        bv.addWidget(self.grid, 1)
        self.lbl_ozet = QLabel("")
        self.lbl_ozet.setStyleSheet("font-size:11px; font-weight:700; color:#1e293b; background:#fef9c3; padding:3px 8px;"
                                    " border:1px solid #e5e7eb;")
        bv.addWidget(self.lbl_ozet)
        v.addWidget(self.body)

        acik = settings_store.get_bool(db, self._anahtar, varsayilan_acik) if db is not None else varsayilan_acik
        self._uygula(acik)

    # ---- açık / kapalı ------------------------------------------------------------
    @property
    def acik(self) -> bool:
        return not self.body.isHidden()

    def toggle(self) -> None:
        self._uygula(not self.acik)
        if self.db is not None:
            try:
                settings_store.set_setting(self.db, self._anahtar, "1" if self.acik else "0")
            except Exception:  # noqa: BLE001 — durum kaydı ekranı bozmamalı
                pass
        if self.acik:
            self.yenile()

    def _uygula(self, acik: bool) -> None:
        self.body.setVisible(acik)
        self.btn_toggle.setText(("▼ " if acik else "▲ ") + self._baslik)

    # ---- veri ---------------------------------------------------------------------------
    def set_kayit(self, kayit_id, ad: str = "") -> None:
        self._kayit_id, self._kayit_adi = kayit_id, ad
        self.lbl_kayit.setText(ad)
        if self.acik:
            self.yenile()

    def yenile(self) -> None:
        g = self.grid
        g.setRowCount(0)
        if not self._kayit_id or self.db is None:
            self.lbl_ozet.setText("Kayıt seçin." if not self._kayit_id else "")
            return
        veri = self.saglayici(self.db, self._kayit_id)
        for satir in veri.satirlar:
            r = g.rowCount()
            g.insertRow(r)
            g.setRowHeight(r, g.effective_row_height)
            for c, metin in enumerate(satir):
                it = QTableWidgetItem(metin)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                k = self.kolonlar[c]
                it.setTextAlignment(_HIZA[k.hiza] | Qt.AlignmentFlag.AlignVCenter)
                if k.renk and metin and metin.replace(".", "").replace(",", "").strip("0") != "":
                    it.setForeground(QBrush(_RENK[k.renk]))
                g.setItem(r, c, it)
        if g.rowCount():
            g.scrollToBottom()
        self.lbl_ozet.setText(veri.ozet)


# ---------------------------------------------------------------------------------------------------
# Sağlayıcılar
# ---------------------------------------------------------------------------------------------------
CARI_KOLONLAR = [
    PanelKolon("TARİH", 0.09, "C"), PanelKolon("FİŞ TİPİ", 0.13), PanelKolon("FİŞ NO", 0.08, "C"),
    PanelKolon("BORÇ", 0.11, "R", "borc"), PanelKolon("ALACAK", 0.11, "R", "alacak"), PanelKolon("AÇIKLAMA", 0.24),
    PanelKolon("Y.P.B BAKİYE", 0.11, "R"), PanelKolon("B/A", 0.04, "C"), PanelKolon("VADE", 0.09, "C"),
]
HESAP_KOLONLAR = [
    PanelKolon("TARİH", 0.08, "C"), PanelKolon("HAREKET", 0.09), PanelKolon("FİŞ NO", 0.07, "C"), PanelKolon("CARİ", 0.20),
    PanelKolon("GİRİŞ", 0.10, "R", "giris"), PanelKolon("ÇIKIŞ", 0.10, "R", "cikis"), PanelKolon("DVZ", 0.04, "C"),
    PanelKolon("AÇIKLAMA", 0.15), PanelKolon("BAKİYE", 0.10, "R"), PanelKolon("VADE", 0.07, "C"),
]


def _t(d) -> str:
    return d.strftime("%d.%m.%Y") if d else ""


def cari_saglayici(db, customer_id: int) -> PanelVeri:
    """Carinin fiş hareketleri (borç/alacak, yürüyen TL bakiye)."""
    from src.desktop.services.cari_hareket_service import TURLER, CariHareketService
    satirlar, borc, alacak = [], 0.0, 0.0
    for r in CariHareketService(db).ekstre(customer_id):
        h = r["hareket"]
        borc += r["borc"]
        alacak += r["alacak"]
        satirlar.append([_t(h.tarih), TURLER.get(h.tur, (h.tur,))[0], h.fis.fis_no if h.fis else "",
                         bicimle(r["borc"], 2) if r["borc"] else "", bicimle(r["alacak"], 2) if r["alacak"] else "",
                         h.aciklama or "", bicimle(abs(r["bakiye"]), 2), "B" if r["bakiye"] > 0 else "A" if r["bakiye"] < 0 else "",
                         _t(h.vade)])
    bak = borc - alacak
    yon = "Borçlu" if bak > 0 else "Alacaklı" if bak < 0 else "Kapalı"
    return PanelVeri(satirlar, f"{len(satirlar)} Kayıt   ·   Borç: {bicimle(borc, 2)}   ·   Alacak: {bicimle(alacak, 2)}   ·   "
                               f"Bakiye: {bicimle(abs(bak), 2)} ({yon})")


def hesap_saglayici(db, hesap_id: int) -> PanelVeri:
    """Kasa / banka / kart hesabının giriş-çıkış hareketleri (döviz bazlı yürüyen bakiye)."""
    from src.desktop.services.finans_hesap_service import hesap_hareketleri
    satirlar, top = [], {}
    for h in hesap_hareketleri(db, hesap_id):
        t = top.setdefault(h["doviz"], [0.0, 0.0])
        t[0] += h["giris"]
        t[1] += h["cikis"]
        satirlar.append([_t(h["tarih"]), h["tur"], h["fis_no"], h["cari"], bicimle(h["giris"], 2) if h["giris"] else "",
                         bicimle(h["cikis"], 2) if h["cikis"] else "", h["doviz"], h["aciklama"], bicimle(h["bakiye"], 2), _t(h["vade"])])
    parca = "   |   ".join(f"{d}: Giriş {bicimle(g, 2)} · Çıkış {bicimle(c_, 2)} · Bakiye {bicimle(g - c_, 2)}"
                           for d, (g, c_) in sorted(top.items()))
    return PanelVeri(satirlar, f"{len(satirlar)} Kayıt" + (f"   ·   {parca}" if parca else ""))
