"""TOYA ERP - Cari hareket giriş formu (yeniden kullanılabilir widget) ve diyaloğu.

Form yalnızca alan toplama/doğrulama önyüzüdür; kaydı çağıran taraf `CariHareketService` ile yapar."""

from __future__ import annotations

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.core.models import CariHareket, Currency, Customer
from src.desktop.services.cari_hareket_service import (
    TURLER,
    YONLER,
    CariHareketError,
    CariHareketService,
)
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.components.grid_delegates import apply_calendar_style
from src.desktop.ui.widgets.money_edit import MoneyEdit


class CariHareketForm(QWidget):
    """Tür seçimine göre alanları açıp kapatan hareket formu."""

    def __init__(self, db, parent=None, tur: str = "tahsilat") -> None:
        super().__init__(parent)
        self.db = db
        f = QFormLayout(self)
        f.setContentsMargins(0, 0, 0, 0)

        self.cmb_tur = QComboBox()
        self.cmb_tur.setStyleSheet("combobox-popup: 0;")
        for k, (etiket, _y) in TURLER.items():
            self.cmb_tur.addItem(etiket, k)
        self.cmb_cari = QComboBox()
        self.cmb_cari.setEditable(True)
        self.cmb_cari.setStyleSheet("combobox-popup: 0;")
        self.cmb_cari.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for c in db.scalars(select(Customer).where(Customer.is_deleted == False).order_by(Customer.fullname)):  # noqa: E712
            self.cmb_cari.addItem(f"{c.customer_code or '-'}  {c.fullname}", c.id)
        self.cmb_cari.setCurrentIndex(-1)
        comp = self.cmb_cari.completer()
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

        self.dt_tarih = QDateEdit(QDate.currentDate())
        apply_calendar_style(self.dt_tarih)
        self.dt_tarih.setDisplayFormat("dd.MM.yyyy")
        self.cmb_yon = QComboBox()
        self.cmb_yon.setStyleSheet("combobox-popup: 0;")
        for k, v in YONLER.items():
            self.cmb_yon.addItem(v, k)
        self.chk_vade = QCheckBox("Vade")
        self.dt_vade = QDateEdit(QDate.currentDate())
        apply_calendar_style(self.dt_vade)
        self.dt_vade.setDisplayFormat("dd.MM.yyyy")
        self.dt_vade.setEnabled(False)
        self.chk_vade.toggled.connect(self.dt_vade.setEnabled)
        self.cmb_para = QComboBox()
        self.cmb_para.setStyleSheet("combobox-popup: 0;")
        self.cmb_para.addItem("TRY", "TRY")
        for c in db.scalars(select(Currency).where(Currency.is_deleted == False, Currency.is_active == True)):  # noqa: E712
            if c.code.upper() != "TRY":
                self.cmb_para.addItem(c.code.upper(), c.code.upper())
        self.ed_kur = MoneyEdit(decimals=4)
        self.ed_tutar = MoneyEdit(decimals=2)
        self.lbl_tl = QLabel("")
        self.ed_belge = QLineEdit()
        self.ed_aciklama = QLineEdit()

        f.addRow("Tür", self.cmb_tur)
        f.addRow("Cari", self.cmb_cari)
        f.addRow("Tarih", self.dt_tarih)
        self.row_yon = (QLabel("Yön"), self.cmb_yon)
        f.addRow(*self.row_yon)
        f.addRow(self.chk_vade, self.dt_vade)
        f.addRow("Para birimi", self.cmb_para)
        self.row_kur = (QLabel("Kur"), self.ed_kur)
        f.addRow(*self.row_kur)
        f.addRow("Tutar", self.ed_tutar)
        f.addRow("", self.lbl_tl)
        f.addRow("Belge no", self.ed_belge)
        f.addRow("Açıklama", self.ed_aciklama)

        self.cmb_tur.currentIndexChanged.connect(self._tur_degisti)
        self.cmb_para.currentIndexChanged.connect(self._para_degisti)
        self.ed_tutar.valueChanged.connect(self._tl_guncelle)
        self.ed_kur.valueChanged.connect(self._tl_guncelle)
        self.cmb_tur.setCurrentIndex(max(self.cmb_tur.findData(tur), 0))
        self._tur_degisti()
        self._para_degisti()

    # ---- görünürlük / hesap ------------------------------------------------
    def _goster(self, row, gorunur: bool) -> None:
        for w in row:
            w.setVisible(gorunur)

    def _tur_degisti(self) -> None:
        tur = self.cmb_tur.currentData()
        self._goster(self.row_yon, tur == "doviz")
        odeme = tur in ("tahsilat", "odeme")
        self.chk_vade.setVisible(odeme)
        self.dt_vade.setVisible(odeme)
        if tur == "doviz" and self.cmb_para.currentData() == "TRY" and self.cmb_para.count() > 1:
            self.cmb_para.setCurrentIndex(1)

    def _para_degisti(self) -> None:
        para = self.cmb_para.currentData()
        self._goster(self.row_kur, para != "TRY")
        if para and para != "TRY":
            from src.desktop.services import money_service
            try:
                self.ed_kur.setValue(money_service.get_rate(self.db, para))
            except money_service.UnknownCurrencyError:
                self.ed_kur.setValue(0)
        self._tl_guncelle()

    def _tl_guncelle(self) -> None:
        para = self.cmb_para.currentData() or "TRY"
        if para == "TRY":
            self.lbl_tl.setText("")
            return
        self.lbl_tl.setText(f"≈ {self.ed_tutar.value() * self.ed_kur.value():,.2f} TRY")

    # ---- veri --------------------------------------------------------------
    def values(self) -> dict:
        tur = self.cmb_tur.currentData()
        para = self.cmb_para.currentData() or "TRY"
        v = {
            "customer_id": self.cmb_cari.currentData() if self.cmb_cari.currentIndex() >= 0 else None,
            "tur": tur,
            "tarih": self.dt_tarih.date().toPyDate(),
            "para_birimi": para,
            "kur": self.ed_kur.value() if para != "TRY" else 1.0,
            "tutar": self.ed_tutar.value(),
            "belge_no": self.ed_belge.text(),
            "aciklama": self.ed_aciklama.text(),
            "vade": self.dt_vade.date().toPyDate() if self.chk_vade.isChecked() and tur in ("tahsilat", "odeme") else None,
        }
        if tur == "doviz":
            v["yon"] = self.cmb_yon.currentData()
        return v          # ödeme aracı / hesap yalnızca cari fişinde girilir (bu form eski tekil kayıtlar içindir)

    def load(self, h: CariHareket) -> None:
        self.cmb_tur.setCurrentIndex(max(self.cmb_tur.findData(h.tur), 0))
        self.cmb_cari.setCurrentIndex(max(self.cmb_cari.findData(h.customer_id), 0))
        self.dt_tarih.setDate(QDate(h.tarih.year, h.tarih.month, h.tarih.day))
        self.cmb_yon.setCurrentIndex(max(self.cmb_yon.findData(h.yon), 0))
        self.chk_vade.setChecked(h.vade is not None)
        if h.vade:
            self.dt_vade.setDate(QDate(h.vade.year, h.vade.month, h.vade.day))
        i = self.cmb_para.findData(h.para_birimi)
        if i < 0:
            self.cmb_para.addItem(h.para_birimi, h.para_birimi)
            i = self.cmb_para.count() - 1
        self.cmb_para.setCurrentIndex(i)
        self.ed_kur.setValue(h.kur or 1.0)      # para değişiminde piyasa kuru yazılır; kayıtlı kuru geri yükle
        self.ed_tutar.setValue(h.tutar)
        self.ed_belge.setText(h.belge_no or "")
        self.ed_aciklama.setText(h.aciklama or "")
        self._tl_guncelle()


class CariHareketDialog(QDialog):
    """Yeni / düzenle diyaloğu. `hareket` verilirse düzenleme kipindedir."""

    def __init__(self, db, hareket: CariHareket | None = None, tur: str = "tahsilat", customer_id: int | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.db, self.hareket = db, hareket
        self.setWindowTitle("Cari Hareketi Düzenle" if hareket else "Yeni Cari Hareketi")
        self.setMinimumWidth(460)
        apply_light_dialog_style(self)
        lyt = QVBoxLayout(self)
        self.form = CariHareketForm(db, tur=tur)
        lyt.addWidget(self.form)
        if hareket:
            self.form.load(hareket)
        elif customer_id:
            self.form.cmb_cari.setCurrentIndex(max(self.form.cmb_cari.findData(customer_id), -1))
        self.lbl_hata = QLabel("")
        self.lbl_hata.setStyleSheet("color: #dc2626; font-weight: 600;")
        lyt.addWidget(self.lbl_hata)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Kaydet")
        bb.button(QDialogButtonBox.StandardButton.Save).setDefault(True)
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        bb.accepted.connect(self._kaydet)
        bb.rejected.connect(self.reject)
        lyt.addWidget(bb)

    def _kaydet(self) -> None:
        svc = CariHareketService(self.db)
        try:
            v = self.form.values()
            self.saved = svc.update(self.hareket.id, **v) if self.hareket else svc.create(**v)
        except CariHareketError as e:
            self.db.rollback()
            self.lbl_hata.setText(str(e))
            return
        self.accept()
