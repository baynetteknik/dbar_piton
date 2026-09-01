"""
ToyaUI — HareketFinansWidget
Fiş detay ekranlarındaki döviz, KDV, şekil, kasa ve işlem seçenekleri paneli.

Kullanım:
    widget = HareketFinansWidget(db_session=db)
    widget.doviz_changed.connect(self.on_doviz_changed)
    layout.addWidget(widget)

    data = widget.get_data()
    widget.set_data(data)
    widget.clear()
"""

import logging
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Varsayılan listeler
DEFAULT_CURRENCIES = [
    {"kod": "TRY", "sembol": "₺", "kur": 1.0,    "aciklama": "Türk Lirası"},
    {"kod": "USD", "sembol": "$", "kur": 38.50,   "aciklama": "Amerikan Doları"},
    {"kod": "EUR", "sembol": "€", "kur": 41.20,   "aciklama": "Euro"},
    {"kod": "GBP", "sembol": "£", "kur": 48.90,   "aciklama": "İngiliz Sterlini"},
]

DEFAULT_KDV_DURUMLARI = [
    "KDV Hariç",
    "KDV Dahil",
    "KDV'siz",
    "Tevkifatlı",
]

DEFAULT_SEKLILER = [
    "Kapalı (Nakit)",
    "Açık - Vadeli",
    "Kredi Kartı",
    "Çek",
    "Senet",
    "Havale / EFT",
    "Diğer",
]

DEFAULT_KASALAR = [
    "K01 - Satış Kasası",
    "K02 - Alış Kasası",
    "K03 - Genel Kasa",
]


class HareketFinansWidget(QFrame):
    """
    Hareket Ayarları & Finans Widget'ı.

    Sinyaller:
        doviz_changed(str, float): Döviz veya kur değiştiğinde (kod, kur)
        kdv_changed(str): KDV durumu değiştiğinde
        data_changed(): Herhangi bir alan değiştiğinde
    """

    doviz_changed = pyqtSignal(str, float)  # kod, kur
    kdv_changed   = pyqtSignal(str)
    data_changed  = pyqtSignal()

    FIELD_H = 24
    LBL_STYLE = "font-size:9px; font-weight:600; color:#475569; min-width:60px;"
    FIELD_STYLE = (
        "font-size:10px; padding:1px 4px; border:1px solid #cbd5e1; "
        "border-radius:3px; background:#ffffff; color:#0f172a;"
    )
    CHK_STYLE = "font-size:10px; font-weight:600; color:#1e3a8a;"

    def __init__(
        self,
        currencies: list[dict] | None = None,
        kasalar: list[str] | None = None,
        db_session=None,
        parent=None,
    ):
        super().__init__(parent)
        self.currencies = currencies or DEFAULT_CURRENCIES
        self.kasalar    = kasalar or DEFAULT_KASALAR
        self.db         = db_session

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            HareketFinansWidget {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
        """)
        self.setFixedHeight(108)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self._init_ui()
        self._load_from_db()

    # ─────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────

    def _init_ui(self):
        main_lyt = QVBoxLayout(self)
        main_lyt.setContentsMargins(6, 4, 6, 4)
        main_lyt.setSpacing(2)
        main_lyt.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── BAŞLIK ──
        hdr_row = QHBoxLayout()
        hdr_row.setContentsMargins(0, 0, 0, 2)
        lbl_hdr = QLabel("⚙️ HAREKET AYARLARI & FİNANS")
        lbl_hdr.setStyleSheet(
            "font-weight:800; color:#1e3a8a; font-size:10px;",
        )
        lbl_hdr.setFixedHeight(18)
        hdr_row.addWidget(lbl_hdr)
        hdr_row.addStretch()
        main_lyt.addLayout(hdr_row)

        # ── FORM ──
        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setSpacing(3)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ── SATIR 1: Döviz | Kur | KDV Durumu ──
        lbl_dov = QLabel("Döviz/Kur:")
        lbl_dov.setStyleSheet(self.LBL_STYLE)
        lbl_dov.setFixedWidth(64)

        # Döviz seçici
        self.cmb_doviz = QComboBox()
        self.cmb_doviz.setFixedHeight(self.FIELD_H)
        self.cmb_doviz.setMaximumHeight(self.FIELD_H)
        self.cmb_doviz.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.cmb_doviz.setStyleSheet(self.FIELD_STYLE)
        for c in self.currencies:
            self.cmb_doviz.addItem(
                f"{c['kod']} ({c['sembol']})", c,
            )
        self.cmb_doviz.currentIndexChanged.connect(
            self._on_doviz_changed,
        )

        # Kur
        self.txt_kur = QLineEdit("1.0000")
        self.txt_kur.setFixedHeight(self.FIELD_H)
        self.txt_kur.setMaximumHeight(self.FIELD_H)
        self.txt_kur.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.txt_kur.setFixedWidth(50)
        self.txt_kur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.txt_kur.setStyleSheet(self.FIELD_STYLE)
        self.txt_kur.setPlaceholderText("Kur")
        self.txt_kur.textChanged.connect(
            lambda: self.data_changed.emit(),
        )

        # KDV Durumu
        lbl_kdv = QLabel("KDV:")
        lbl_kdv.setStyleSheet("font-size:9px; font-weight:600; color:#475569; padding:0 2px;")
        lbl_kdv.setFixedWidth(28)

        self.cmb_kdv = QComboBox()
        self.cmb_kdv.setFixedHeight(self.FIELD_H)
        self.cmb_kdv.setMaximumHeight(self.FIELD_H)
        self.cmb_kdv.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.cmb_kdv.setStyleSheet(self.FIELD_STYLE)
        self.cmb_kdv.addItems(DEFAULT_KDV_DURUMLARI)
        self.cmb_kdv.currentTextChanged.connect(
            lambda t: (self.kdv_changed.emit(t), self.data_changed.emit()),
        )

        dov_row = QHBoxLayout()
        dov_row.setSpacing(3)
        dov_row.addWidget(self.cmb_doviz, 2)
        dov_row.addWidget(self.txt_kur)
        dov_row.addWidget(lbl_kdv)
        dov_row.addWidget(self.cmb_kdv, 2)

        grid.addWidget(lbl_dov, 0, 0)
        grid.addLayout(dov_row, 0, 1, 1, 5)

        # ── SATIR 2: Şekil | Kasa ──
        lbl_sek = QLabel("Şekil/Kasa:")
        lbl_sek.setStyleSheet(self.LBL_STYLE)
        lbl_sek.setFixedWidth(64)

        self.cmb_sekil = QComboBox()
        self.cmb_sekil.setFixedHeight(self.FIELD_H)
        self.cmb_sekil.setMaximumHeight(self.FIELD_H)
        self.cmb_sekil.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.cmb_sekil.setStyleSheet(self.FIELD_STYLE)
        self.cmb_sekil.addItems(DEFAULT_SEKLILER)
        self.cmb_sekil.currentIndexChanged.connect(
            lambda: self.data_changed.emit(),
        )

        self.cmb_kasa = QComboBox()
        self.cmb_kasa.setFixedHeight(self.FIELD_H)
        self.cmb_kasa.setMaximumHeight(self.FIELD_H)
        self.cmb_kasa.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.cmb_kasa.setStyleSheet(self.FIELD_STYLE)
        for k in self.kasalar:
            self.cmb_kasa.addItem(k)
        self.cmb_kasa.currentIndexChanged.connect(
            lambda: self.data_changed.emit(),
        )

        sek_row = QHBoxLayout()
        sek_row.setSpacing(3)
        sek_row.addWidget(self.cmb_sekil, 1)
        sek_row.addWidget(self.cmb_kasa, 1)

        grid.addWidget(lbl_sek, 1, 0)
        grid.addLayout(sek_row, 1, 1, 1, 5)

        # ── SATIR 3: İşlemler ──
        lbl_isl = QLabel("İşlemler:")
        lbl_isl.setStyleSheet(self.LBL_STYLE)
        lbl_isl.setFixedWidth(64)

        self.chk_cari = QCheckBox("Cari")
        self.chk_cari.setChecked(True)
        self.chk_cari.setFixedHeight(self.FIELD_H)
        self.chk_cari.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.chk_cari.setStyleSheet(self.CHK_STYLE)
        self.chk_cari.stateChanged.connect(
            lambda: self.data_changed.emit(),
        )

        self.chk_stok = QCheckBox("Stok")
        self.chk_stok.setChecked(True)
        self.chk_stok.setFixedHeight(self.FIELD_H)
        self.chk_stok.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.chk_stok.setStyleSheet(self.CHK_STYLE)
        self.chk_stok.stateChanged.connect(
            lambda: self.data_changed.emit(),
        )

        isl_row = QHBoxLayout()
        isl_row.setSpacing(12)
        isl_row.addWidget(self.chk_cari)
        isl_row.addWidget(self.chk_stok)
        isl_row.addStretch()

        grid.addWidget(lbl_isl, 2, 0)
        grid.addLayout(isl_row, 2, 1, 1, 5)

        main_lyt.addLayout(grid)
        main_lyt.addStretch()

    # ─────────────────────────────────────────────
    # DB YÜKLEME
    # ─────────────────────────────────────────────

    def _load_from_db(self):
        """DB'den döviz ve kasa listelerini yükle."""
        if not self.db:
            return
        try:
            from sqlalchemy import select
            # Dövizler
            try:
                from src.core.models import Currency
                rows = self.db.scalars(
                    select(Currency).where(
                        Currency.is_deleted == False,
                        Currency.is_active == True,
                    ),
                ).all()
                if rows:
                    self.cmb_doviz.blockSignals(True)
                    self.cmb_doviz.clear()
                    for r in rows:
                        c = {
                            "kod": r.code, "sembol": r.symbol or "",
                            "kur": float(r.rate or 1),
                            "aciklama": r.name or "",
                        }
                        self.cmb_doviz.addItem(
                            f"{c['kod']} ({c['sembol']})", c,
                        )
                    self.cmb_doviz.blockSignals(False)
            except Exception:
                pass  # Model yoksa varsayılan kullan
        except Exception as e:
            logger.warning(f"Finans DB yüklenemedi: {e}")

    # ─────────────────────────────────────────────
    # OLAYLAR
    # ─────────────────────────────────────────────

    def _on_doviz_changed(self, idx: int):
        """Döviz seçilince kuru otomatik doldur."""
        currency = self.cmb_doviz.currentData()
        if not currency:
            return
        kur = float(currency.get("kur", 1.0))
        kod = currency.get("kod", "TRY")

        # TRY seçilince kur 1 olur ve readonly
        if kod == "TRY":
            self.txt_kur.setText("1.0000")
            self.txt_kur.setReadOnly(True)
            self.txt_kur.setStyleSheet(
                self.FIELD_STYLE +
                "QLineEdit { background:#f8fafc; color:#94a3b8; }",
            )
        else:
            self.txt_kur.setText(f"{kur:.4f}")
            self.txt_kur.setReadOnly(False)
            self.txt_kur.setStyleSheet(self.FIELD_STYLE)

        self.doviz_changed.emit(kod, kur)
        self.data_changed.emit()

    # ─────────────────────────────────────────────
    # YARDIMCI
    # ─────────────────────────────────────────────

    def get_currency_symbol(self) -> str:
        """Seçili dövizin sembolünü döndürür."""
        c = self.cmb_doviz.currentData()
        if c:
            return c.get("sembol", "₺")
        return "₺"

    def get_exchange_rate(self) -> float:
        """Güncel kuru döndürür."""
        try:
            return float(
                self.txt_kur.text().replace(",", ".") or "1",
            )
        except Exception:
            return 1.0

    def update_currencies(self, currencies: list[dict]):
        """Döviz listesini güncelle."""
        self.currencies = currencies
        current = self.cmb_doviz.currentText()
        self.cmb_doviz.blockSignals(True)
        self.cmb_doviz.clear()
        for c in currencies:
            self.cmb_doviz.addItem(
                f"{c['kod']} ({c['sembol']})", c,
            )
        self.cmb_doviz.blockSignals(False)
        idx = self.cmb_doviz.findText(current)
        if idx >= 0:
            self.cmb_doviz.setCurrentIndex(idx)

    def update_kasalar(self, kasalar: list[str]):
        """Kasa listesini güncelle."""
        current = self.cmb_kasa.currentText()
        self.cmb_kasa.blockSignals(True)
        self.cmb_kasa.clear()
        self.cmb_kasa.addItems(kasalar)
        self.cmb_kasa.blockSignals(False)
        idx = self.cmb_kasa.findText(current)
        if idx >= 0:
            self.cmb_kasa.setCurrentIndex(idx)

    # ─────────────────────────────────────────────
    # VERİ OKUMA / YAZMA
    # ─────────────────────────────────────────────

    def get_data(self) -> dict[str, Any]:
        """Tüm alan değerlerini dict olarak döndürür."""
        c = self.cmb_doviz.currentData() or {}
        return {
            "doviz_kod":    c.get("kod", "TRY"),
            "doviz_sembol": c.get("sembol", "₺"),
            "doviz_kur":    self.get_exchange_rate(),
            "kdv_durumu":   self.cmb_kdv.currentText(),
            "sekil":        self.cmb_sekil.currentText(),
            "kasa":         self.cmb_kasa.currentText(),
            "cari_islemi":  self.chk_cari.isChecked(),
            "stok_islemi":  self.chk_stok.isChecked(),
        }

    def set_data(self, data: dict):
        """Dict'ten alan değerlerini yazar."""
        # Döviz
        doviz = data.get("doviz_kod", "TRY")
        for i in range(self.cmb_doviz.count()):
            c = self.cmb_doviz.itemData(i)
            if c and c.get("kod") == doviz:
                self.cmb_doviz.setCurrentIndex(i)
                break

        # Kur
        kur = data.get("doviz_kur", 1.0)
        self.txt_kur.setText(f"{float(kur):.4f}")

        # KDV
        kdv = data.get("kdv_durumu", "KDV Hariç")
        idx = self.cmb_kdv.findText(kdv)
        if idx >= 0:
            self.cmb_kdv.setCurrentIndex(idx)

        # Şekil
        sekil = data.get("sekil", "")
        idx = self.cmb_sekil.findText(sekil)
        if idx >= 0:
            self.cmb_sekil.setCurrentIndex(idx)

        # Kasa
        kasa = data.get("kasa", "")
        idx = self.cmb_kasa.findText(kasa)
        if idx >= 0:
            self.cmb_kasa.setCurrentIndex(idx)

        # İşlemler
        self.chk_cari.setChecked(data.get("cari_islemi", True))
        self.chk_stok.setChecked(data.get("stok_islemi", True))

    def clear(self):
        """Varsayılan değerlere döner."""
        self.cmb_doviz.setCurrentIndex(0)  # TRY
        self.txt_kur.setText("1.0000")
        self.cmb_kdv.setCurrentIndex(0)    # KDV Hariç
        self.cmb_sekil.setCurrentIndex(0)  # Kapalı (Nakit)
        self.cmb_kasa.setCurrentIndex(0)
        self.chk_cari.setChecked(True)
        self.chk_stok.setChecked(True)


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = HareketFinansWidget()

    widget.doviz_changed.connect(
        lambda kod, kur: print(f"💱 Döviz: {kod} — Kur: {kur}"),
    )
    widget.kdv_changed.connect(
        lambda t: print(f"🧾 KDV: {t}"),
    )

    win = QWidget()
    win.setWindowTitle("HareketFinansWidget Test")
    win.setMinimumWidth(550)
    lyt = QVBoxLayout(win)
    lyt.addWidget(widget)
    lyt.addStretch()
    win.show()
    sys.exit(app.exec())
