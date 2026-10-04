"""TOYA ERP - BankaOdemePlaniEkleDialog: Banka Ödeme Planı tanımı ekleme/düzenleme popup'ı (2026-10-02).

Taksit sayısına göre değişen komisyon/BSMV/hizmet bedeli yapısını tanımlar (bkz. `BankaOdemePlani`,
gelistirme/04_odeme_planlari/tasarim.md). Genel Ayarlar'daki "Banka Ödeme Planları" panelinde kayıt
eklemek/düzenlemek bu formla yapılır; grid hücreleri yine doğrudan düzenlenebilir kalır."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from src.desktop.ui.components.dialog_style import apply_light_dialog_style


class BankaOdemePlaniEkleDialog(QDialog):
    def __init__(self, hesap_secenekleri: list[str], deger: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Banka Ödeme Planı Tanımı")
        self.setMinimumWidth(380)
        apply_light_dialog_style(self)

        f = QFormLayout()
        self.txt_kod = QLineEdit()
        self.txt_kod.setPlaceholderText("ör. GARANTI-POS-3TAK")
        self.txt_aciklama = QLineEdit()
        self.txt_aciklama.setPlaceholderText("ör. Garanti Bankası POS - 3 Taksit")
        self.cmb_hesap = QComboBox()
        self.cmb_hesap.addItems(hesap_secenekleri)
        self.spin_taksit = QSpinBox()
        self.spin_taksit.setRange(1, 36)
        self.spin_komisyon = QDoubleSpinBox()
        self.spin_komisyon.setRange(0, 100)
        self.spin_komisyon.setSuffix(" %")
        self.spin_komisyon.setDecimals(2)
        self.spin_komisyon.setToolTip("Bu taksit sayısı için bankanın/POS sağlayıcının tahsilat tutarından kestiği oran.")
        self.spin_bsmv = QDoubleSpinBox()
        self.spin_bsmv.setRange(0, 100)
        self.spin_bsmv.setSuffix(" %")
        self.spin_bsmv.setDecimals(2)
        self.spin_bsmv.setValue(5.0)
        self.spin_bsmv.setToolTip("KOMİSYON TUTARI üzerinden hesaplanır (tutarın tamamı üzerinden değil) — bankaların standart uygulaması.")
        self.spin_hizmet = QDoubleSpinBox()
        self.spin_hizmet.setRange(0, 1_000_000)
        self.spin_hizmet.setSuffix(" ₺")
        self.spin_hizmet.setDecimals(2)
        self.spin_hizmet.setToolTip("İşlem başına, orana bakılmaksızın kesilen sabit tutar (varsa).")
        self.chk_aktif = QCheckBox("Aktif")
        self.chk_aktif.setChecked(True)

        f.addRow("Kod *", self.txt_kod)
        f.addRow("Açıklama", self.txt_aciklama)
        f.addRow("Hesap", self.cmb_hesap)
        f.addRow("Taksit Sayısı", self.spin_taksit)
        f.addRow("Komisyon Oranı", self.spin_komisyon)
        f.addRow("BSMV Oranı", self.spin_bsmv)
        f.addRow("Hizmet Bedeli", self.spin_hizmet)
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
            if deger.get("hesap"):
                self.cmb_hesap.setCurrentIndex(max(self.cmb_hesap.findText(deger["hesap"]), 0))
            try:
                self.spin_taksit.setValue(int(deger.get("taksit") or 1))
                self.spin_komisyon.setValue(float(deger.get("komisyon") or 0))
                self.spin_bsmv.setValue(float(deger.get("bsmv") or 5))
                self.spin_hizmet.setValue(float(deger.get("hizmet") or 0))
            except ValueError:
                pass
            self.chk_aktif.setChecked(str(deger.get("aktif", "aktif")).strip().lower() not in ("pasif", "false", "0"))

    def deger(self) -> dict:
        return {
            "kod": self.txt_kod.text().strip(),
            "aciklama": self.txt_aciklama.text().strip(),
            "hesap": self.cmb_hesap.currentText(),
            "taksit": str(self.spin_taksit.value()),
            "komisyon": f"{self.spin_komisyon.value():.2f}",
            "bsmv": f"{self.spin_bsmv.value():.2f}",
            "hizmet": f"{self.spin_hizmet.value():.2f}",
            "aktif": "Aktif" if self.chk_aktif.isChecked() else "Pasif",
        }
