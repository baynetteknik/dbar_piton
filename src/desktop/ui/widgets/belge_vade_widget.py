"""
ToyaUI — BelgeVadeWidget
Fiş detay ekranlarındaki belge, tarih ve vade bilgileri paneli.

Kullanım:
    widget = BelgeVadeWidget(payment_plans=[], db_session=db)
    widget.vade_changed.connect(self.on_vade_changed)
    layout.addWidget(widget)

    data = widget.get_data()
    widget.set_data(data)
    widget.clear()
"""

import logging
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QDate, Qt, QTime, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
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

# Varsayılan ödeme planları — DB'den yüklenince bunlar kullanılmaz
DEFAULT_PAYMENT_PLANS = [
    {"kod": "30GVD",   "aciklama": "30 GÜN VADE",        "gun": 30,  "tip": "Açık Hesap"},
    {"kod": "45GVD",   "aciklama": "45 GÜNLÜK VADE",      "gun": 45,  "tip": "Açık Hesap"},
    {"kod": "60GVD",   "aciklama": "60 GÜNLÜK VADE",      "gun": 60,  "tip": "Açık Hesap"},
    {"kod": "60GUNKK", "aciklama": "60 GÜN KREDİ KARTI",  "gun": 60,  "tip": "Kredi Kartı"},
    {"kod": "AH",      "aciklama": "AÇIK HESAP",           "gun": 0,   "tip": "Açık Hesap"},
    {"kod": "PESIN",   "aciklama": "PEŞİN",                "gun": 0,   "tip": "Peşin"},
]

# Vade formülleri
VADE_FORMULLERI = [
    "(+30 Gün)",
    "(+45 Gün)",
    "(+60 Gün)",
    "(+90 Gün)",
    "(Ay Sonu)",
    "(Peşin)",
]


class BelgeVadeWidget(QFrame):
    """Belge numarası, tarih, vade ve ödeme planı bileşeni.

    Fiş detay ekranlarının üst kısmında yer alır.
    Ödeme planları DB'den otomatik yüklenir.
    """

    # Sinyaller
    vade_changed = pyqtSignal(QDate)
    odeme_plani_changed = pyqtSignal(dict)
    data_changed = pyqtSignal()

    # Stil sabitleri — CariKunyeWidget ile birebir aynı
    FIELD_H = 24
    LBL_STYLE = "font-size:9px; font-weight:600; color:#475569; min-width:60px;"
    FIELD_STYLE = (
        "font-size:10px; padding:1px 4px; border:1px solid #cbd5e1; "
        "border-radius:3px; background:#ffffff; color:#0f172a;"
    )

    def __init__(
        self,
        payment_plans: list[dict] = None,
        db_session=None,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db_session
        self.payment_plans = payment_plans or []
        self._current_plan: dict | None = None

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            BelgeVadeWidget {
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
        self._load_payment_plans()

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
        lbl_hdr = QLabel("📅 BELGE & VADE DETAYLARI")
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

        # ── SATIR 1: Seri | Belge No | Fiş No ──
        lbl_seri = QLabel("Seri/No/Fiş:")
        lbl_seri.setStyleSheet(self.LBL_STYLE)
        lbl_seri.setFixedWidth(64)

        # Seri
        self.txt_seri = QLineEdit()
        self.txt_seri.setFixedHeight(self.FIELD_H)
        self.txt_seri.setMaximumHeight(self.FIELD_H)
        self.txt_seri.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.txt_seri.setStyleSheet(self.FIELD_STYLE)
        self.txt_seri.setPlaceholderText("Seri")
        self.txt_seri.textChanged.connect(lambda: self.data_changed.emit())

        # Belge No
        self.txt_belge_no = QLineEdit()
        self.txt_belge_no.setFixedHeight(self.FIELD_H)
        self.txt_belge_no.setMaximumHeight(self.FIELD_H)
        self.txt_belge_no.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.txt_belge_no.setStyleSheet(self.FIELD_STYLE)
        self.txt_belge_no.setPlaceholderText("Belge No")
        self.txt_belge_no.textChanged.connect(lambda: self.data_changed.emit())

        # Fiş No
        self.txt_fis_no = QLineEdit()
        self.txt_fis_no.setFixedHeight(self.FIELD_H)
        self.txt_fis_no.setMaximumHeight(self.FIELD_H)
        self.txt_fis_no.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.txt_fis_no.setStyleSheet(self.FIELD_STYLE)
        self.txt_fis_no.setPlaceholderText("Fiş No")
        self.txt_fis_no.textChanged.connect(lambda: self.data_changed.emit())

        seri_row = QHBoxLayout()
        seri_row.setSpacing(3)
        seri_row.addWidget(self.txt_seri, 2)
        seri_row.addWidget(self.txt_belge_no, 3)
        seri_row.addWidget(self.txt_fis_no, 2)

        grid.addWidget(lbl_seri, 0, 0)
        grid.addLayout(seri_row, 0, 1, 1, 5)

        # ── SATIR 2: Tarih | Saat | Vade | Formül ──
        lbl_tarih = QLabel("Tarih/Vade:")
        lbl_tarih.setStyleSheet(self.LBL_STYLE)
        lbl_tarih.setFixedWidth(64)

        # Tarih
        self.date_belge = QDateEdit(QDate.currentDate())
        self.date_belge.setFixedHeight(self.FIELD_H)
        self.date_belge.setMaximumHeight(self.FIELD_H)
        self.date_belge.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.date_belge.setCalendarPopup(True)
        self.date_belge.setDisplayFormat("dd.MM.yyyy")
        self.date_belge.setStyleSheet(self.FIELD_STYLE)
        self.date_belge.dateChanged.connect(lambda: self.data_changed.emit())

        # Saat
        self.txt_saat = QLineEdit(
            QTime.currentTime().toString("HH:mm"),
        )
        self.txt_saat.setFixedHeight(self.FIELD_H)
        self.txt_saat.setMaximumHeight(self.FIELD_H)
        self.txt_saat.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.txt_saat.setFixedWidth(42)
        self.txt_saat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.txt_saat.setStyleSheet(self.FIELD_STYLE)
        self.txt_saat.setPlaceholderText("ss:dk")

        # Vade Tarihi
        self.date_vade = QDateEdit(
            QDate.currentDate().addDays(30),
        )
        self.date_vade.setFixedHeight(self.FIELD_H)
        self.date_vade.setMaximumHeight(self.FIELD_H)
        self.date_vade.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.date_vade.setCalendarPopup(True)
        self.date_vade.setDisplayFormat("dd.MM.yyyy")
        self.date_vade.setStyleSheet(self.FIELD_STYLE)
        self.date_vade.dateChanged.connect(self._on_vade_changed)

        # Vade Formül
        self.cmb_vade_formul = QComboBox()
        self.cmb_vade_formul.addItems(VADE_FORMULLERI)
        self.cmb_vade_formul.setCurrentText("(+30 Gün)")
        self.cmb_vade_formul.setFixedHeight(self.FIELD_H)
        self.cmb_vade_formul.setMaximumHeight(self.FIELD_H)
        self.cmb_vade_formul.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.cmb_vade_formul.setFixedWidth(78)
        self.cmb_vade_formul.setStyleSheet(self.FIELD_STYLE)
        self.cmb_vade_formul.currentTextChanged.connect(
            self._on_formul_changed,
        )

        tarih_row = QHBoxLayout()
        tarih_row.setSpacing(3)
        tarih_row.addWidget(self.date_belge, 3)
        tarih_row.addWidget(self.txt_saat)
        tarih_row.addWidget(self.date_vade, 3)
        tarih_row.addWidget(self.cmb_vade_formul)

        grid.addWidget(lbl_tarih, 1, 0)
        grid.addLayout(tarih_row, 1, 1, 1, 5)

        # ── SATIR 3: Ödeme Planı ──
        lbl_odeme = QLabel("Ödeme Planı:")
        lbl_odeme.setStyleSheet(self.LBL_STYLE)
        lbl_odeme.setFixedWidth(64)

        self.cmb_odeme_plani = QComboBox()
        self.cmb_odeme_plani.setFixedHeight(self.FIELD_H)
        self.cmb_odeme_plani.setMaximumHeight(self.FIELD_H)
        self.cmb_odeme_plani.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.cmb_odeme_plani.setStyleSheet(self.FIELD_STYLE)
        self.cmb_odeme_plani.currentIndexChanged.connect(
            self._on_odeme_plani_changed,
        )

        grid.addWidget(lbl_odeme,           2, 0)
        grid.addWidget(self.cmb_odeme_plani, 2, 1, 1, 5)

        main_lyt.addLayout(grid)
        main_lyt.addStretch()

    # ─────────────────────────────────────────────
    # ÖDEME PLANLARI
    # ─────────────────────────────────────────────

    def _load_payment_plans(self):
        """Ödeme planlarını DB'den veya varsayılan listeden yükle."""
        plans = self._get_plans()
        self.cmb_odeme_plani.blockSignals(True)
        self.cmb_odeme_plani.clear()
        self.cmb_odeme_plani.addItem("--- Ödeme Planı Seçin ---", None)
        for p in plans:
            label = f"{p['kod']} - {p['aciklama']}"
            self.cmb_odeme_plani.addItem(label, p)
        self.cmb_odeme_plani.blockSignals(False)

    def _get_plans(self) -> list[dict]:
        """DB'den veya varsayılan listeden ödeme planlarını döndür."""
        if self.db:
            try:
                from sqlalchemy import select

                from src.core.models import PaymentPlan
                rows = self.db.scalars(
                    select(PaymentPlan).where(
                        PaymentPlan.is_deleted == False,
                        PaymentPlan.is_active == True,
                    ),
                ).all()
                if rows:
                    return [
                        {
                            "kod":      r.code or "",
                            "aciklama": r.description or "",
                            "gun":      int(r.days or 0),
                            "tip":      r.payment_type or "Açık Hesap",
                        }
                        for r in rows
                    ]
            except Exception as e:
                logger.warning(f"Ödeme planları DB'den alınamadı: {e}")
        return self.payment_plans

    def _on_odeme_plani_changed(self, idx: int):
        """Ödeme planı seçilince vadeyi otomatik hesapla."""
        plan = self.cmb_odeme_plani.currentData()
        if not plan:
            return
        self._current_plan = plan
        gun = int(plan.get("gun", 0))

        # Vade tarihini güncelle
        self.date_vade.setDate(
            QDate.currentDate().addDays(gun),
        )

        # Formül seçicisini güncelle
        formul = f"(+{gun} Gün)" if gun > 0 else "(Elle gir)"
        idx_f = self.cmb_vade_formul.findText(formul)
        if idx_f >= 0:
            self.cmb_vade_formul.blockSignals(True)
            self.cmb_vade_formul.setCurrentIndex(idx_f)
            self.cmb_vade_formul.blockSignals(False)

        self.odeme_plani_changed.emit(plan)
        self.data_changed.emit()

    def _on_formul_changed(self, text: str):
        """Vade formülü seçilince vadeyi hesapla."""
        if text == "(Elle gir)":
            return
        import re
        match = re.search(r'([+-]?\d+)', text)
        if match:
            gun = int(match.group(1))
            self.date_vade.setDate(
                QDate.currentDate().addDays(gun),
            )

    def _on_vade_changed(self, date: QDate):
        """Vade tarihi değişince gün farkını göster."""
        today = QDate.currentDate()
        _diff = today.daysTo(date)
        self.vade_changed.emit(date)
        self.data_changed.emit()

    # ─────────────────────────────────────────────
    # DIŞ MÜDAHALE
    # ─────────────────────────────────────────────

    def set_vade_from_terms(self, days: int):
        """
        Cari seçilince vade gün sayısını dışarıdan ayarla.
        Örn: cari_widget.customer_selected → widget.set_vade_from_terms(30)
        """
        self.date_vade.setDate(QDate.currentDate().addDays(days))
        formul = f"(+{days} Gün)"
        idx = self.cmb_vade_formul.findText(formul)
        if idx >= 0:
            self.cmb_vade_formul.blockSignals(True)
            self.cmb_vade_formul.setCurrentIndex(idx)
            self.cmb_vade_formul.blockSignals(False)

    def update_payment_plans(self, plans: list[dict]):
        """Ödeme planı listesini güncelle."""
        self.payment_plans = plans
        current = self.cmb_odeme_plani.currentText()
        self._load_payment_plans()
        idx = self.cmb_odeme_plani.findText(current)
        if idx >= 0:
            self.cmb_odeme_plani.setCurrentIndex(idx)

    # ─────────────────────────────────────────────
    # VERİ OKUMA / YAZMA
    # ─────────────────────────────────────────────

    def get_data(self) -> dict[str, Any]:
        """Tüm alan değerlerini dict olarak döndürür."""
        d = self.date_belge.date()
        v = self.date_vade.date()
        return {
            "seri":          self.txt_seri.text().strip(),
            "belge_no":      self.txt_belge_no.text().strip(),
            "fis_no":        self.txt_fis_no.text().strip(),
            "tarih":         f"{d.year()}-{d.month():02d}-{d.day():02d}",
            "saat":          self.txt_saat.text().strip(),
            "vade":          f"{v.year()}-{v.month():02d}-{v.day():02d}",
            "vade_gun":      self.date_belge.date().daysTo(self.date_vade.date()),
            "odeme_plani":   self.cmb_odeme_plani.currentText(),
            "odeme_plani_data": self._current_plan,
            # PyQt6 QDate objeleri (widget erişimi için)
            "date_belge_qdate": self.date_belge.date(),
            "date_vade_qdate":  self.date_vade.date(),
        }

    def set_data(self, data: dict):
        """Dict'ten alan değerlerini yazar."""
        if data.get("seri"):
            self.txt_seri.setText(data["seri"])
        if data.get("belge_no"):
            self.txt_belge_no.setText(data["belge_no"])
        if data.get("fis_no"):
            self.txt_fis_no.setText(data["fis_no"])
        if data.get("saat"):
            self.txt_saat.setText(data["saat"])

        # Tarih
        tarih = data.get("tarih", "")
        if tarih:
            try:
                dt = datetime.strptime(tarih[:10], "%Y-%m-%d")
                self.date_belge.setDate(
                    QDate(dt.year, dt.month, dt.day),
                )
            except Exception:
                pass

        # Vade
        vade = data.get("vade", "")
        if vade:
            try:
                dv = datetime.strptime(vade[:10], "%Y-%m-%d")
                self.date_vade.setDate(
                    QDate(dv.year, dv.month, dv.day),
                )
            except Exception:
                pass

        # Ödeme planı
        plan_text = data.get("odeme_plani", "")
        if plan_text:
            idx = self.cmb_odeme_plani.findText(plan_text)
            if idx >= 0:
                self.cmb_odeme_plani.setCurrentIndex(idx)

    def clear(self):
        """Tüm alanları temizler, bugünün tarihi ve +30 gün vade ile başlar."""
        self.txt_seri.clear()
        self.txt_belge_no.clear()
        self.txt_fis_no.clear()
        self.txt_saat.setText(QTime.currentTime().toString("HH:mm"))
        self.date_belge.setDate(QDate.currentDate())
        self.date_vade.setDate(QDate.currentDate().addDays(30))
        self.cmb_vade_formul.setCurrentText("(+30 Gün)")
        self.cmb_odeme_plani.setCurrentIndex(0)
        self._current_plan = None


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    widget = BelgeVadeWidget(payment_plans=DEFAULT_PAYMENT_PLANS)

    widget.vade_changed.connect(
        lambda d: print(f"📅 Vade değişti: {d.toString('dd.MM.yyyy')}"),
    )
    widget.odeme_plani_changed.connect(
        lambda p: print(f"💳 Ödeme planı: {p['kod']} — {p['aciklama']}"),
    )
    widget.data_changed.connect(
        lambda: print(f"📝 Veri: {widget.get_data()}"),
    )

    win = QWidget()
    win.setWindowTitle("BelgeVadeWidget Test")
    win.setMinimumWidth(600)
    lyt = QVBoxLayout(win)
    lyt.addWidget(widget)
    lyt.addStretch()
    win.show()
    sys.exit(app.exec())
