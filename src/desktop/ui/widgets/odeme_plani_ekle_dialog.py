"""TOYA ERP - OdemePlaniEkleDialog: Ödeme Planı tanımı ekleme/düzenleme popup'ı (2026-10-02).

Genel Ayarlar'daki "Ödeme Planları" panelinde kayıt eklemek/düzenlemek artık (Dönem'de olduğu gibi) bu
formla da yapılabilir — grid'in kendisi hâlâ doğrudan (hücre bazında) düzenlenebilir kalır, popup YALNIZCA
ek/alternatif bir giriş yolu. Ödeme Tipi, Hedef Hesap ve Banka Ödeme Planı seçenekleri DIŞARIDAN verilir
(dialog kendi DB sorgusu yapmaz, test edilebilirliği ve çağıran tarafın "canlı liste" sorumluluğunu korur)."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from src.desktop.ui.components.dialog_style import apply_light_dialog_style


class OdemePlaniEkleDialog(QDialog):
    def __init__(
        self,
        odeme_tipi_secenekleri: list[str],
        hesap_secenekleri: list[str],
        banka_odeme_plani_secenekleri: list[str],
        deger: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ödeme Planı Tanımı")
        self.setMinimumWidth(380)
        apply_light_dialog_style(self)

        f = QFormLayout()
        self.txt_kod = QLineEdit()
        self.txt_kod.setPlaceholderText("ör. 30GVD, NAKIT, CF3TAK")
        self.txt_aciklama = QLineEdit()
        self.txt_aciklama.setPlaceholderText("ör. 30 Gün Vade, Nakit, Cardfinans 3 Taksit")
        self.spin_gun = QSpinBox()
        self.spin_gun.setRange(0, 365)
        self.cmb_tip = QComboBox()
        self.cmb_tip.addItems(odeme_tipi_secenekleri)
        self.cmb_tip.setToolTip(
            "Nakit → Kasa fişi, Havale/EFT/Kredi Kartı/POS → Banka fişi, Açık Hesap → otomatik fiş yok "
            "(yalnız cari borç kalır). Bu, 'Otomatik Fiş' açıksa fatura kaydedilince otomatik oluşur.",
        )
        self.cmb_hesap = QComboBox()
        self.cmb_hesap.addItems(hesap_secenekleri)
        self.cmb_hesap.setToolTip("Otomatik oluşan fişin düşeceği kasa/banka/POS hesabı.")
        self.cmb_banka_plani = QComboBox()
        self.cmb_banka_plani.addItems(banka_odeme_plani_secenekleri)
        self.cmb_banka_plani.setToolTip(
            "Yalnız Kredi Kartı/POS/Havale gibi banka ile ilgili tiplerde anlamlı — taksit sayısına göre "
            "değişen komisyon/BSMV/hizmet bedeli tanımına bağlar (isteğe bağlı).",
        )
        self.chk_otomatik = QCheckBox("Faturadan otomatik kasa/banka fişi oluştur")
        self.chk_otomatik.setChecked(True)
        self.chk_aktif = QCheckBox("Aktif")
        self.chk_aktif.setChecked(True)

        f.addRow("Kod *", self.txt_kod)
        f.addRow("Açıklama", self.txt_aciklama)
        f.addRow("Gün", self.spin_gun)
        f.addRow("Ödeme Tipi", self.cmb_tip)
        f.addRow("Hedef Hesap", self.cmb_hesap)
        f.addRow("Banka Ödeme Planı", self.cmb_banka_plani)
        f.addRow("", self.chk_otomatik)
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
        b_kaydet.clicked.connect(self.accept)
        b_iptal.clicked.connect(self.reject)

        if deger:
            self.txt_kod.setText(deger.get("kod") or "")
            self.txt_aciklama.setText(deger.get("aciklama") or "")
            try:
                self.spin_gun.setValue(int(deger.get("gun") or 0))
            except ValueError:
                pass
            if deger.get("tip"):
                self.cmb_tip.setCurrentIndex(max(self.cmb_tip.findText(deger["tip"]), 0))
            if deger.get("hesap"):
                self.cmb_hesap.setCurrentIndex(max(self.cmb_hesap.findText(deger["hesap"]), 0))
            if deger.get("banka_plani"):
                self.cmb_banka_plani.setCurrentIndex(max(self.cmb_banka_plani.findText(deger["banka_plani"]), 0))
            self.chk_otomatik.setChecked(str(deger.get("otomatik", "evet")).strip().lower() in ("evet", "true", "1"))
            self.chk_aktif.setChecked(str(deger.get("aktif", "aktif")).strip().lower() not in ("pasif", "false", "0"))

    def deger(self) -> dict:
        return {
            "kod": self.txt_kod.text().strip(),
            "aciklama": self.txt_aciklama.text().strip(),
            "gun": str(self.spin_gun.value()),
            "tip": self.cmb_tip.currentText(),
            "hesap": self.cmb_hesap.currentText(),
            "banka_plani": self.cmb_banka_plani.currentText(),
            "otomatik": "Evet" if self.chk_otomatik.isChecked() else "Hayır",
            "aktif": "Aktif" if self.chk_aktif.isChecked() else "Pasif",
        }
