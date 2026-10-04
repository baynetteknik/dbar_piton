"""TOYA ERP - Firma Tanım Alt Diyalogları.

Yetkili, Ortak, Banka Hesabı, Şube ve Depo gibi firma alt tanımlarının
modern, doğrulamalı ve kullanıcı dostu popup diyalogları.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.services.currency_catalog import CURRENCY_CODES
from src.desktop.services.master_definitions_store import MasterDefinitionsStore
from src.desktop.ui.components.dialog_style import apply_light_dialog_style


class YetkiliEkleDialog(QDialog):
    """Yetkili kişi ekleme ve düzenleme popup'ı."""

    def __init__(self, deger: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Yetkili Tanımı" if not deger else "Yetkili Düzenle")
        self.setMinimumWidth(380)
        apply_light_dialog_style(self)

        f = QFormLayout()
        self.txt_ad_soyad = QLineEdit()
        self.txt_ad_soyad.setPlaceholderText("Ad ve Soyad *")
        self.txt_unvan = QLineEdit()
        self.txt_unvan.setPlaceholderText("ör. Genel Müdür, Muhasebe Müdürü")
        self.txt_telefon = QLineEdit()
        self.txt_telefon.setPlaceholderText("ör. 0532 000 00 00")
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("ör. yetkili@firma.com")

        f.addRow("Ad Soyad *", self.txt_ad_soyad)
        f.addRow("Ünvanı", self.txt_unvan)
        f.addRow("Telefon", self.txt_telefon)
        f.addRow("E-Posta", self.txt_email)

        lyt = QVBoxLayout(self)
        lyt.addLayout(f)
        bar = QHBoxLayout()
        bar.addStretch()
        b_kaydet, b_iptal = QPushButton("💾 Kaydet"), QPushButton("✖ Vazgeç")
        b_kaydet.setDefault(True)
        bar.addWidget(b_kaydet)
        bar.addWidget(b_iptal)
        lyt.addLayout(bar)
        b_kaydet.clicked.connect(self._validate_and_accept)
        b_iptal.clicked.connect(self.reject)

        if deger:
            self.txt_ad_soyad.setText(str(deger.get("ad_soyad") or ""))
            self.txt_unvan.setText(str(deger.get("unvan") or ""))
            self.txt_telefon.setText(str(deger.get("telefon") or ""))
            self.txt_email.setText(str(deger.get("e_posta") or ""))

    def _validate_and_accept(self):
        if not self.txt_ad_soyad.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Yetkili ad soyad alanı zorunludur.")
            self.txt_ad_soyad.setFocus()
            return
        self.accept()

    def deger(self) -> dict:
        return {
            "ad_soyad": self.txt_ad_soyad.text().strip(),
            "unvan": self.txt_unvan.text().strip(),
            "telefon": self.txt_telefon.text().strip(),
            "e_posta": self.txt_email.text().strip(),
        }


class OrtakEkleDialog(QDialog):
    """Firma ortağı ekleme ve düzenleme popup'ı."""

    def __init__(self, deger: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ortak Tanımı" if not deger else "Ortak Düzenle")
        self.setMinimumWidth(380)
        apply_light_dialog_style(self)

        f = QFormLayout()
        self.txt_ad_soyad = QLineEdit()
        self.txt_ad_soyad.setPlaceholderText("Ortak Adı / Firma Ünvanı *")
        self.txt_tc_vergi = QLineEdit()
        self.txt_tc_vergi.setPlaceholderText("TCKN veya Vergi No")
        self.txt_pay = QLineEdit()
        self.txt_pay.setPlaceholderText("ör. 50, 100")
        self.txt_gorev = QLineEdit()
        self.txt_gorev.setPlaceholderText("ör. Yönetim Kurulu Başkanı, Ortak")

        f.addRow("Ad Soyad / Ünvan *", self.txt_ad_soyad)
        f.addRow("TC / Vergi No", self.txt_tc_vergi)
        f.addRow("Pay Oranı (%)", self.txt_pay)
        f.addRow("Görevi", self.txt_gorev)

        lyt = QVBoxLayout(self)
        lyt.addLayout(f)
        bar = QHBoxLayout()
        bar.addStretch()
        b_kaydet, b_iptal = QPushButton("💾 Kaydet"), QPushButton("✖ Vazgeç")
        b_kaydet.setDefault(True)
        bar.addWidget(b_kaydet)
        bar.addWidget(b_iptal)
        lyt.addLayout(bar)
        b_kaydet.clicked.connect(self._validate_and_accept)
        b_iptal.clicked.connect(self.reject)

        if deger:
            self.txt_ad_soyad.setText(str(deger.get("ad_soyad") or ""))
            self.txt_tc_vergi.setText(str(deger.get("tc_vergi_no") or ""))
            self.txt_pay.setText(str(deger.get("pay_orani") or ""))
            self.txt_gorev.setText(str(deger.get("gorev") or ""))

    def _validate_and_accept(self):
        if not self.txt_ad_soyad.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Ortak ad soyad alanı zorunludur.")
            self.txt_ad_soyad.setFocus()
            return
        self.accept()

    def deger(self) -> dict:
        return {
            "ad_soyad": self.txt_ad_soyad.text().strip(),
            "tc_vergi_no": self.txt_tc_vergi.text().strip(),
            "pay_orani": self.txt_pay.text().strip(),
            "gorev": self.txt_gorev.text().strip(),
        }


class BankaHesabiEkleDialog(QDialog):
    """Banka hesabı ekleme ve düzenleme popup'ı."""

    def __init__(self, deger: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Banka Hesabı Tanımı" if not deger else "Banka Hesabı Düzenle")
        self.setMinimumWidth(420)
        apply_light_dialog_style(self)

        f = QFormLayout()
        self.cmb_banka = QComboBox()
        self.cmb_banka.setEditable(True)
        self.cmb_banka.addItem("— Seçin veya Yazın —")
        try:
            store = MasterDefinitionsStore()
            for b in store.get_banks(active_only=True):
                self.cmb_banka.addItem(b["name"], b["code"])
        except Exception:  # noqa: BLE001
            for b_name in ["Garanti BBVA", "İş Bankası", "Akbank", "Yapı Kredi", "Ziraat Bankası", "Vakıfbank", "Halkbank", "QNB Finansbank"]:
                self.cmb_banka.addItem(b_name)

        self.txt_sube = QLineEdit()
        self.txt_sube.setPlaceholderText("Şube Adı / Kodu")
        self.txt_hesap_no = QLineEdit()
        self.txt_hesap_no.setPlaceholderText("Hesap Numarası")
        self.txt_iban = QLineEdit()
        self.txt_iban.setPlaceholderText("TR00 0000 0000 0000 0000 0000 00")

        self.cmb_para = QComboBox()
        self.cmb_para.addItems(CURRENCY_CODES[:15] or ["TRY", "USD", "EUR", "GBP"])

        f.addRow("Banka *", self.cmb_banka)
        f.addRow("Şube", self.txt_sube)
        f.addRow("Hesap No", self.txt_hesap_no)
        f.addRow("IBAN *", self.txt_iban)
        f.addRow("Para Birimi", self.cmb_para)

        lyt = QVBoxLayout(self)
        lyt.addLayout(f)
        bar = QHBoxLayout()
        bar.addStretch()
        b_kaydet, b_iptal = QPushButton("💾 Kaydet"), QPushButton("✖ Vazgeç")
        b_kaydet.setDefault(True)
        bar.addWidget(b_kaydet)
        bar.addWidget(b_iptal)
        lyt.addLayout(bar)
        b_kaydet.clicked.connect(self._validate_and_accept)
        b_iptal.clicked.connect(self.reject)

        if deger:
            b_val = str(deger.get("banka") or "")
            idx = self.cmb_banka.findText(b_val)
            if idx >= 0:
                self.cmb_banka.setCurrentIndex(idx)
            else:
                self.cmb_banka.setEditText(b_val)
            self.txt_sube.setText(str(deger.get("sube") or ""))
            self.txt_hesap_no.setText(str(deger.get("hesap_no") or ""))
            self.txt_iban.setText(str(deger.get("iban") or ""))
            p_val = str(deger.get("para_birimi") or "TRY").upper()
            p_idx = self.cmb_para.findText(p_val)
            if p_idx >= 0:
                self.cmb_para.setCurrentIndex(p_idx)

    def _validate_and_accept(self):
        banka = self.cmb_banka.currentText().strip()
        if not banka or banka.startswith("—"):
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen banka adını seçin veya yazın.")
            self.cmb_banka.setFocus()
            return
        iban = self.txt_iban.text().strip().replace(" ", "")
        if iban and len(iban) < 10:
            QMessageBox.warning(self, "Hatalı Bilgi", "Lütfen geçerli bir IBAN girin.")
            self.txt_iban.setFocus()
            return
        self.accept()

    def deger(self) -> dict:
        banka = self.cmb_banka.currentText().strip()
        if banka.startswith("—"):
            banka = ""
        return {
            "banka": banka,
            "sube": self.txt_sube.text().strip(),
            "hesap_no": self.txt_hesap_no.text().strip(),
            "iban": self.txt_iban.text().strip().replace(" ", ""),
            "para_birimi": self.cmb_para.currentText().strip(),
        }


class SubeEkleDialog(QDialog):
    """Şube tanımı ekleme ve düzenleme popup'ı."""

    def __init__(self, deger: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Şube Tanımı" if not deger else "Şube Düzenle")
        self.setMinimumWidth(380)
        apply_light_dialog_style(self)

        f = QFormLayout()
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("ör. 01, MRKZ")
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("ör. Merkez Şube, Fabrika Şubesi")
        self.txt_yetkili = QLineEdit()
        self.txt_yetkili.setPlaceholderText("Şube Sorumlusu / Yetkilisi")
        self.chk_aktif = QCheckBox("Aktif")
        self.chk_aktif.setChecked(True)

        f.addRow("Şube Kodu *", self.txt_code)
        f.addRow("Şube Adı *", self.txt_name)
        f.addRow("Yetkili", self.txt_yetkili)
        f.addRow("", self.chk_aktif)

        lyt = QVBoxLayout(self)
        lyt.addLayout(f)
        bar = QHBoxLayout()
        bar.addStretch()
        b_kaydet, b_iptal = QPushButton("💾 Kaydet"), QPushButton("✖ Vazgeç")
        b_kaydet.setDefault(True)
        bar.addWidget(b_kaydet)
        bar.addWidget(b_iptal)
        lyt.addLayout(bar)
        b_kaydet.clicked.connect(self._validate_and_accept)
        b_iptal.clicked.connect(self.reject)

        if deger:
            self.txt_code.setText(str(deger.get("code") or ""))
            self.txt_name.setText(str(deger.get("name") or ""))
            self.txt_yetkili.setText(str(deger.get("yetkili") or ""))
            self.chk_aktif.setChecked(
                str(deger.get("durum") or deger.get("is_active") or "Aktif").lower() in ("aktif", "true", "1", "evet"),
            )

    def _validate_and_accept(self):
        if not self.txt_code.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Şube kodu zorunludur.")
            self.txt_code.setFocus()
            return
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Şube adı zorunludur.")
            self.txt_name.setFocus()
            return
        self.accept()

    def deger(self) -> dict:
        return {
            "code": self.txt_code.text().strip(),
            "name": self.txt_name.text().strip(),
            "yetkili": self.txt_yetkili.text().strip(),
            "is_active": self.chk_aktif.isChecked(),
            "durum": "Aktif" if self.chk_aktif.isChecked() else "Pasif",
        }


class DepoEkleDialog(QDialog):
    """Depo tanımı ekleme ve düzenleme popup'ı."""

    def __init__(self, deger: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Depo Tanımı" if not deger else "Depo Düzenle")
        self.setMinimumWidth(380)
        apply_light_dialog_style(self)

        f = QFormLayout()
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("ör. D01, ANA_DEPO")
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("ör. Merkez Ana Depo, Sevkiyat Deposu")
        self.txt_address = QLineEdit()
        self.txt_address.setPlaceholderText("Depo Lokasyonu / Adresi")
        self.chk_aktif = QCheckBox("Aktif")
        self.chk_aktif.setChecked(True)

        f.addRow("Depo Kodu *", self.txt_code)
        f.addRow("Depo Adı *", self.txt_name)
        f.addRow("Adres / Konum", self.txt_address)
        f.addRow("", self.chk_aktif)

        lyt = QVBoxLayout(self)
        lyt.addLayout(f)
        bar = QHBoxLayout()
        bar.addStretch()
        b_kaydet, b_iptal = QPushButton("💾 Kaydet"), QPushButton("✖ Vazgeç")
        b_kaydet.setDefault(True)
        bar.addWidget(b_kaydet)
        bar.addWidget(b_iptal)
        lyt.addLayout(bar)
        b_kaydet.clicked.connect(self._validate_and_accept)
        b_iptal.clicked.connect(self.reject)

        if deger:
            self.txt_code.setText(str(deger.get("code") or ""))
            self.txt_name.setText(str(deger.get("name") or ""))
            self.txt_address.setText(str(deger.get("address") or ""))
            self.chk_aktif.setChecked(
                str(deger.get("durum") or deger.get("is_active") or "Aktif").lower() in ("aktif", "true", "1", "evet"),
            )

    def _validate_and_accept(self):
        if not self.txt_code.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Depo kodu zorunludur.")
            self.txt_code.setFocus()
            return
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Depo adı zorunludur.")
            self.txt_name.setFocus()
            return
        self.accept()

    def deger(self) -> dict:
        return {
            "code": self.txt_code.text().strip(),
            "name": self.txt_name.text().strip(),
            "address": self.txt_address.text().strip(),
            "is_active": self.chk_aktif.isChecked(),
            "durum": "Aktif" if self.chk_aktif.isChecked() else "Pasif",
        }


UNIT_TYPES: list[tuple[str, str]] = [
    ("adet", "Adet / Miktar"),
    ("agirlik", "Ağırlık (Kg, Gram, Ton)"),
    ("uzunluk", "Uzunluk (Metre, cm)"),
    ("alan", "Alan (Metrekare)"),
    ("hacim", "Hacim / Sıvı (Litre, m³)"),
    ("paket", "Paket / Koli / Palet"),
    ("zaman", "Zaman (Saat, Gün, Ay)"),
]


class BirimEkleDialog(QDialog):
    """Ölçü birimi ekleme ve düzenleme popup'ı."""

    def __init__(self, deger: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ölçü Birimi Tanımı" if not deger else "Ölçü Birimi Düzenle")
        self.setMinimumWidth(380)
        apply_light_dialog_style(self)

        f = QFormLayout()
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText("ör. C62, KGM, ADT")
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("ör. Adet, Kilogram, Koli")
        self.txt_symbol = QLineEdit()
        self.txt_symbol.setPlaceholderText("ör. Adet, Kg, Kl")

        self.cmb_type = QComboBox()
        for k, label in UNIT_TYPES:
            self.cmb_type.addItem(label, k)

        self.chk_aktif = QCheckBox("Aktif")
        self.chk_aktif.setChecked(True)

        f.addRow("Birim Kodu *", self.txt_code)
        f.addRow("Birim Adı *", self.txt_name)
        f.addRow("Sembol / Simge", self.txt_symbol)
        f.addRow("Birim Türü", self.cmb_type)
        f.addRow("", self.chk_aktif)

        lyt = QVBoxLayout(self)
        lyt.addLayout(f)
        bar = QHBoxLayout()
        bar.addStretch()
        b_kaydet, b_iptal = QPushButton("💾 Kaydet"), QPushButton("✖ Vazgeç")
        b_kaydet.setDefault(True)
        bar.addWidget(b_kaydet)
        bar.addWidget(b_iptal)
        lyt.addLayout(bar)
        b_kaydet.clicked.connect(self._validate_and_accept)
        b_iptal.clicked.connect(self.reject)

        if deger:
            self.txt_code.setText(str(deger.get("code") or ""))
            self.txt_name.setText(str(deger.get("name") or ""))
            self.txt_symbol.setText(str(deger.get("symbol") or ""))
            idx = self.cmb_type.findData(deger.get("unit_type") or "adet")
            if idx >= 0:
                self.cmb_type.setCurrentIndex(idx)
            self.chk_aktif.setChecked(
                str(deger.get("durum") or deger.get("is_active") or "Aktif").lower() in ("aktif", "true", "1", "evet"),
            )

    def _validate_and_accept(self):
        if not self.txt_code.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Birim kodu zorunludur.")
            self.txt_code.setFocus()
            return
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Birim adı zorunludur.")
            self.txt_name.setFocus()
            return
        self.accept()

    def deger(self) -> dict:
        return {
            "code": self.txt_code.text().strip().upper(),
            "name": self.txt_name.text().strip(),
            "symbol": self.txt_symbol.text().strip() or self.txt_name.text().strip(),
            "unit_type": self.cmb_type.currentData() or "adet",
            "is_active": self.chk_aktif.isChecked(),
            "durum": "Aktif" if self.chk_aktif.isChecked() else "Pasif",
        }

