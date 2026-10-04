"""TOYA ERP - GorevDialog: görev / randevu / hatırlatma giriş penceresi.

Başlangıç ve bitiş isteğe bağlıdır (kutucukla açılır); tarih seçicileri takvimlidir (okunaklı açık renkler). Hatırlatma, tekrar ve
ilişkili kayıt (cari, stok, servis…) buradan girilir. Başka modüller `varsayilan` ile önceden doldurup açabilir:

    GorevDialog(db, varsayilan={"ilgili_tur": "servis", "ilgili_id": 42, "ilgili_ad": "Servis #42"}, kullanici="ayse").exec()
"""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QDate, QDateTime, QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)
from sqlalchemy import select

from src.core.models import User
from src.desktop.services.gorev_service import (
    DURUMLAR,
    ILGILI_TURLERI,
    KATEGORILER,
    ONCELIKLER,
    TEKRARLAR,
    TURLER,
    GorevError,
    GorevService,
)
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.components.grid_delegates import apply_calendar_style

HATIRLATMALAR = [("Hatırlatma yok", None), ("5 dk önce", 5), ("15 dk önce", 15), ("30 dk önce", 30), ("1 saat önce", 60), ("1 gün önce", 1440)]
_BAS_SAAT = QTime(9, 0)


def _qdt(d: datetime | None) -> QDateTime:
    return QDateTime(QDate(d.year, d.month, d.day), QTime(d.hour, d.minute)) if d else QDateTime(QDate.currentDate(), _BAS_SAAT)


_COMBO_STYLE = """
    QComboBox {
        combobox-popup: 0;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        padding: 4px 6px;
        background-color: white;
        color: #0f172a;
        font-size: 11px;
    }
    QComboBox QAbstractItemView {
        outline: 0;
        padding: 0px;
        border: 1px solid #cbd5e1;
        background-color: #ffffff;
        color: #0f172a;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 6px;
        min-height: 20px;
    }
"""

class GorevDialog(QDialog):
    def __init__(self, db, gorev_id: int | None = None, varsayilan: dict | None = None, kullanici: str = "", parent=None) -> None:
        super().__init__(parent)
        self.db, self.gorev_id, self.kullanici = db, gorev_id, kullanici
        self.svc = GorevService(db)
        self.kaydedilen = None
        self._ilgili_id: int | None = None
        self.setWindowTitle("Görev" if gorev_id else "Yeni Görev")
        self.setMinimumWidth(560)
        apply_light_dialog_style(self)

        f = QFormLayout()
        self.cmb_tur = QComboBox()
        self.cmb_tur.setStyleSheet(_COMBO_STYLE)
        for k, e in TURLER.items():
            self.cmb_tur.addItem(e, k)
        self.txt_baslik = QLineEdit()
        self.txt_baslik.setPlaceholderText("Ne yapılacak?")
        self.cmb_kategori, self.cmb_oncelik, self.cmb_durum = QComboBox(), QComboBox(), QComboBox()
        for _cb in (self.cmb_kategori, self.cmb_oncelik, self.cmb_durum):
            _cb.setStyleSheet(_COMBO_STYLE)
        for k, e in KATEGORILER.items():
            self.cmb_kategori.addItem(e, k)
        for k, e in ONCELIKLER.items():
            self.cmb_oncelik.addItem(e, k)
        for k, e in DURUMLAR.items():
            self.cmb_durum.addItem(e, k)
        self.cmb_oncelik.setCurrentIndex(self.cmb_oncelik.findData(2))
        self.cmb_atanan = QComboBox()
        self.cmb_atanan.setStyleSheet(_COMBO_STYLE)
        self.cmb_atanan.setEditable(True)
        self.cmb_atanan.addItem("")
        for (ad,) in db.execute(select(User.username).where(User.is_deleted == False).order_by(User.username)):  # noqa: E712
            self.cmb_atanan.addItem(ad)
        self.chk_bas, self.chk_bit = QCheckBox("Başlangıç"), QCheckBox("Bitiş / son tarih")
        self.dt_bas, self.dt_bit = QDateTimeEdit(_qdt(None)), QDateTimeEdit(_qdt(None))
        for d in (self.dt_bas, self.dt_bit):
            d.setDisplayFormat("dd.MM.yyyy HH:mm")
            d.setCalendarPopup(True)
            apply_calendar_style(d)
            d.setEnabled(False)
        self.chk_bas.toggled.connect(self.dt_bas.setEnabled)
        self.chk_bit.toggled.connect(self.dt_bit.setEnabled)
        self.chk_tum_gun = QCheckBox("Tüm gün")
        self.cmb_hatirlat = QComboBox()
        self.cmb_hatirlat.setStyleSheet(_COMBO_STYLE)
        for e, k in HATIRLATMALAR:
            self.cmb_hatirlat.addItem(e, k)
        self.cmb_tekrar = QComboBox()
        self.cmb_tekrar.setStyleSheet(_COMBO_STYLE)
        for k, e in TEKRARLAR.items():
            self.cmb_tekrar.addItem(e, k)
        self.chk_tekrar_bitis = QCheckBox("Şu tarihe kadar")
        self.dt_tekrar_bitis = QDateEdit(QDate.currentDate().addMonths(3))
        apply_calendar_style(self.dt_tekrar_bitis)
        self.dt_tekrar_bitis.setDisplayFormat("dd.MM.yyyy")
        self.dt_tekrar_bitis.setEnabled(False)
        self.chk_tekrar_bitis.toggled.connect(self.dt_tekrar_bitis.setEnabled)
        self.cmb_ilgili = QComboBox()
        self.cmb_ilgili.setStyleSheet(_COMBO_STYLE)
        self.cmb_ilgili.addItem("— (bağlı kayıt yok)", None)
        for k, e in ILGILI_TURLERI.items():
            self.cmb_ilgili.addItem(e, k)
        self.txt_ilgili_ad = QLineEdit()
        self.txt_ilgili_ad.setPlaceholderText("Bağlı kaydın adı / numarası (ör. ACME, Servis #42)")
        self.txt_aciklama = QPlainTextEdit()
        self.txt_aciklama.setFixedHeight(90)

        f.addRow("Tür", self.cmb_tur)
        f.addRow("Başlık *", self.txt_baslik)
        f.addRow("Kategori", self.cmb_kategori)
        f.addRow("Öncelik", self._yan(self.cmb_oncelik, QLabel("Durum"), self.cmb_durum))
        f.addRow("Atanan", self.cmb_atanan)
        f.addRow(self.chk_bas, self._yan(self.dt_bas, self.chk_tum_gun))
        f.addRow(self.chk_bit, self.dt_bit)
        f.addRow("Hatırlat", self.cmb_hatirlat)
        f.addRow("Tekrar", self._yan(self.cmb_tekrar, self.chk_tekrar_bitis, self.dt_tekrar_bitis))
        f.addRow("Bağlı kayıt", self._yan(self.cmb_ilgili, self.txt_ilgili_ad))
        f.addRow("Açıklama", self.txt_aciklama)
        lyt = QVBoxLayout(self)
        lyt.addLayout(f)
        self.lbl_hata = QLabel("")
        self.lbl_hata.setStyleSheet("color:#dc2626; font-weight:600;")
        self.lbl_hata.setWordWrap(True)
        lyt.addWidget(self.lbl_hata)
        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_kaydet, btn_iptal = QPushButton("💾 Kaydet"), QPushButton("✖ Vazgeç")
        self.btn_kaydet.setDefault(True)
        bar.addWidget(self.btn_kaydet)
        bar.addWidget(btn_iptal)
        lyt.addLayout(bar)
        self.btn_kaydet.clicked.connect(self.kaydet)
        btn_iptal.clicked.connect(self.reject)

        if gorev_id:
            self._yukle(self.svc.getir(gorev_id))
        else:
            self._varsayilanlar(varsayilan or {})

    @staticmethod
    def _yan(*widgets) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        for w in widgets:
            h.addWidget(w, 1 if not isinstance(w, (QLabel, QCheckBox)) else 0)
        return h

    # ---- doldur / oku ------------------------------------------------------------
    def _varsayilanlar(self, v: dict) -> None:
        self.cmb_tur.setCurrentIndex(max(self.cmb_tur.findData(v.get("tur", "gorev")), 0))
        self.txt_baslik.setText(v.get("baslik", ""))
        self.cmb_kategori.setCurrentIndex(max(self.cmb_kategori.findData(v.get("kategori", "genel")), 0))
        self.cmb_atanan.setCurrentText(v.get("atanan", self.kullanici))
        for chk, dt, key in ((self.chk_bas, self.dt_bas, "baslangic"), (self.chk_bit, self.dt_bit, "bitis")):
            if v.get(key):
                dt.setDateTime(_qdt(v[key]))
                chk.setChecked(True)
        if v.get("tur") == "randevu" and not self.chk_bas.isChecked():
            self.chk_bas.setChecked(True)
        self.cmb_ilgili.setCurrentIndex(max(self.cmb_ilgili.findData(v.get("ilgili_tur")), 0))
        self.txt_ilgili_ad.setText(v.get("ilgili_ad", ""))
        self._ilgili_id = v.get("ilgili_id")

    def _yukle(self, g) -> None:
        self.cmb_tur.setCurrentIndex(self.cmb_tur.findData(g.tur))
        self.txt_baslik.setText(g.baslik)
        self.cmb_kategori.setCurrentIndex(max(self.cmb_kategori.findData(g.kategori), 0))
        self.cmb_oncelik.setCurrentIndex(max(self.cmb_oncelik.findData(g.oncelik), 0))
        self.cmb_durum.setCurrentIndex(max(self.cmb_durum.findData(g.durum), 0))
        self.cmb_atanan.setCurrentText(g.atanan or "")
        for chk, dt, val in ((self.chk_bas, self.dt_bas, g.baslangic), (self.chk_bit, self.dt_bit, g.bitis)):
            chk.setChecked(val is not None)
            if val:
                dt.setDateTime(_qdt(val))
        self.chk_tum_gun.setChecked(bool(g.tum_gun))
        self.cmb_hatirlat.setCurrentIndex(max(self.cmb_hatirlat.findData(g.hatirlat_dk), 0))
        self.cmb_tekrar.setCurrentIndex(max(self.cmb_tekrar.findData(g.tekrar), 0))
        if g.tekrar_bitis:
            self.chk_tekrar_bitis.setChecked(True)
            self.dt_tekrar_bitis.setDate(QDate(g.tekrar_bitis.year, g.tekrar_bitis.month, g.tekrar_bitis.day))
        self.cmb_ilgili.setCurrentIndex(max(self.cmb_ilgili.findData(g.ilgili_tur), 0))
        self.txt_ilgili_ad.setText(g.ilgili_ad or "")
        self._ilgili_id = g.ilgili_id
        self.txt_aciklama.setPlainText(g.aciklama or "")

    def degerler(self) -> dict:
        ilgili = self.cmb_ilgili.currentData()
        return {
            "tur": self.cmb_tur.currentData(), "baslik": self.txt_baslik.text(), "kategori": self.cmb_kategori.currentData(),
            "oncelik": self.cmb_oncelik.currentData(), "durum": self.cmb_durum.currentData(), "atanan": self.cmb_atanan.currentText(),
            "baslangic": self.dt_bas.dateTime().toPyDateTime() if self.chk_bas.isChecked() else None,
            "bitis": self.dt_bit.dateTime().toPyDateTime() if self.chk_bit.isChecked() else None,
            "tum_gun": self.chk_tum_gun.isChecked(), "hatirlat_dk": self.cmb_hatirlat.currentData(), "tekrar": self.cmb_tekrar.currentData(),
            "tekrar_bitis": self.dt_tekrar_bitis.date().toPyDate() if self.chk_tekrar_bitis.isChecked() else None,
            "ilgili_tur": ilgili, "ilgili_id": self._ilgili_id if ilgili else None, "ilgili_ad": self.txt_ilgili_ad.text() if ilgili else None,
            "aciklama": self.txt_aciklama.toPlainText(), "olusturan": self.kullanici,
        }

    def kaydet(self) -> None:
        try:
            self.kaydedilen = self.svc.kaydet(self.degerler(), self.gorev_id)
        except GorevError as e:
            self.lbl_hata.setText(str(e))
            QMessageBox.warning(self, "Görev", str(e))
            return
        self.accept()
