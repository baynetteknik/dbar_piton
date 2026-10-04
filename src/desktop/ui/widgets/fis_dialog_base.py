"""TOYA ERP - FisDialogBase: fiş (belge) giriş penceresi iskeleti.

Cari, stok, kasa ve banka fişleri aynı pencere düzenini ve akışını paylaşır; alt sınıf yalnızca kancaları doldurur:

    başlık widget'ı  →  kalemler grid'i (`FisKalemGrid`)  →  alt bölüm: [özet widget'ı | açıklama satırları | toplamlar]
    hata satırı  →  Kaydet · Kaydet & Yeni · Vazgeç  ······  Yazdır · PDF · Excel

Ortak davranış: ekranı kaplayarak açılır, açık hücre editörü kayıttan önce işlenir, hatalar satırda ve uyarı penceresinde
gösterilir (sessiz kalmaz), çıktılar (yazdır / PDF / Excel) kayıtlı fişten alınır ve yeni ya da değişmiş fiş önce otomatik
kaydedilir (kilitli fiş olduğu gibi kullanılır), kilitli fişte düzenleme kapanır.

Alt sınıfın doldurduğu kancalar: `baslik_olustur`, `kalemler_olustur`, `ozet_olustur`, `toplam_olustur`, `baglantilar`,
`baslik_verisi`, `kaydet_servis`, `yeni_hazirla`, `yukle`, `toplamlari_tazele`, `kilit_alanlari`, `kilitli_mi`,
`rapor_modulu` (rapor_verisi / excel_yaz / pdf_yaz / yazdir / html sağlayan modül) ve `HATA_SINIFI`.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.ui.components.dialog_style import apply_light_dialog_style

logger = logging.getLogger(__name__)


class FisDialogBase(QDialog):
    PENCERE_BASLIGI = "Fiş"
    BASLIK_YENI = "🧾 Yeni Fiş"
    BASLIK_MEVCUT = "🧾 Fiş"
    CIKTI_ONEKI = "fis"
    HATA_SINIFI: type[Exception] = ValueError
    OZET_GENISLIK = 280
    ACIKLAMA_SATIRI = 3

    def __init__(self, db, fis_id: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.fis_id = fis_id
        self._dirty = False
        self.setWindowTitle(self.PENCERE_BASLIGI)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowState(Qt.WindowState.WindowMaximized)          # ekran standardı: ekranı kaplayarak açılır
        apply_light_dialog_style(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)
        self.lbl_baslik = QLabel(self.BASLIK_YENI)
        self.lbl_baslik.setStyleSheet("font-size:15px; font-weight:800; color:#1e3a8a;")
        root.addWidget(self.lbl_baslik)

        self.baslik = self.baslik_olustur()
        root.addWidget(self.baslik)
        self.kalemler = self.kalemler_olustur()
        root.addWidget(self.kalemler, 1)

        alt = QHBoxLayout()
        alt.setSpacing(8)
        self.ozet = self.ozet_olustur()
        if self.ozet is not None:
            self.ozet.setFixedWidth(self.OZET_GENISLIK)
            alt.addWidget(self.ozet)
        acik = QFrame()
        acik.setObjectName("FisAcik")
        acik.setStyleSheet("#FisAcik { background:#f8fafc; border:1px solid #e2e8f0; border-radius:4px; }")
        av = QVBoxLayout(acik)
        av.setContentsMargins(10, 8, 10, 8)
        t = QLabel("AÇIKLAMA")
        t.setStyleSheet("font-size:10px; font-weight:800; color:#1e3a8a; letter-spacing:1px;")
        av.addWidget(t)
        self.txt_acik = [QLineEdit() for _ in range(self.ACIKLAMA_SATIRI)]
        for e in self.txt_acik:
            av.addWidget(e)
        av.addStretch()
        alt.addWidget(acik, 1)
        self.toplam = self.toplam_olustur()
        if self.toplam is not None:
            alt.addWidget(self.toplam, 2)
        root.addLayout(alt)

        self.lbl_hata = QLabel("")
        self.lbl_hata.setWordWrap(True)
        self.lbl_hata.setStyleSheet("color:#dc2626; font-weight:600;")
        root.addWidget(self.lbl_hata)

        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_kaydet = QPushButton("💾 Kaydet")
        self.btn_kaydet.setDefault(True)
        self.btn_yeni = QPushButton("💾 Kaydet && Yeni")
        self.btn_vazgec = QPushButton("✖ Vazgeç")
        for b in (self.btn_kaydet, self.btn_yeni, self.btn_vazgec):
            bar.addWidget(b)
        bar.addSpacing(28)
        self.btn_yazdir = QPushButton("🖨 Yazdır")
        self.btn_pdf = QPushButton("📄 PDF")
        self.btn_excel = QPushButton("📊 Excel")
        for b in (self.btn_yazdir, self.btn_pdf, self.btn_excel):
            b.setToolTip("Fiş değiştiyse önce kaydedilir; çıktı kayıtlı fişten alınır")
            bar.addWidget(b)
        bar.addStretch()
        root.addLayout(bar)

        self.btn_kaydet.clicked.connect(lambda: self._kaydet(yeni=False))
        self.btn_yeni.clicked.connect(lambda: self._kaydet(yeni=True))
        self.btn_vazgec.clicked.connect(self.reject)
        self.btn_yazdir.clicked.connect(lambda: self._cikti("yazdir"))
        self.btn_pdf.clicked.connect(lambda: self._cikti("pdf"))
        self.btn_excel.clicked.connect(lambda: self._cikti("excel"))
        self.kalemler.totals_changed.connect(self.toplamlari_tazele)
        self.kalemler.message.connect(self.lbl_hata.setText)
        self.kalemler.grid.itemChanged.connect(self._kirlendi)      # değişiklik izleme: çıktıdan önce kayıt gerekir mi
        for e in self.txt_acik:
            e.textChanged.connect(self._kirlendi)
        self.baglantilar()

        if fis_id:
            self.yukle(fis_id)
        else:
            self._yeni_fis()
        self._dirty = False

    # ---- alt sınıf kancaları ---------------------------------------------------
    def baslik_olustur(self):
        raise NotImplementedError

    def kalemler_olustur(self):
        raise NotImplementedError

    def ozet_olustur(self):
        return None

    def toplam_olustur(self):
        return None

    def baglantilar(self) -> None:
        """Alt sınıfa özel sinyal bağlantıları (başlık ↔ kalemler ↔ özet)."""

    def baslik_verisi(self) -> dict:
        return {}

    def kaydet_servis(self, baslik: dict, satirlar: list[dict], fis_id: int | None):
        raise NotImplementedError

    def yeni_hazirla(self) -> None:
        """Yeni fiş: başlığı, kalem varsayılanlarını ve özeti başlangıç durumuna getirir."""

    def yukle(self, fis_id: int) -> None:
        raise NotImplementedError

    def toplamlari_tazele(self) -> None:
        """Kalem toplamları değişti."""

    def kilit_alanlari(self) -> list:
        """Fiş kilitliyken devre dışı bırakılacak başlık widget'ları."""
        return []

    def kilitli_mi(self) -> bool:
        return False

    def rapor_modulu(self):
        raise NotImplementedError

    def kilit_uygula(self, kilitli: bool) -> None:
        self.kalemler.setEnabled(not kilitli)
        for w in (*self.kilit_alanlari(), *self.txt_acik):
            w.setEnabled(not kilitli)
        self.btn_yeni.setEnabled(not kilitli)

    # ---- durum -----------------------------------------------------------------
    def _kirlendi(self, *_a) -> None:
        self._dirty = True

    def _yeni_fis(self) -> None:
        self.fis_id = None
        self.yeni_hazirla()
        self.kalemler.clear()
        for e in self.txt_acik:
            e.clear()
        self.lbl_hata.setText("")
        self.lbl_baslik.setText(self.BASLIK_YENI)
        self.kilit_uygula(False)
        self.toplamlari_tazele()
        self._dirty = False

    # ---- kayıt -------------------------------------------------------------------
    def _hata_goster(self, mesaj: str) -> None:
        """Hata hem satırda hem açılır pencerede gösterilir; düğmeye basıldığında 'hiçbir şey olmadı' izlenimi kalmasın."""
        self.lbl_hata.setStyleSheet("color:#dc2626; font-weight:600;")
        self.lbl_hata.setText(mesaj)
        QMessageBox.warning(self, self.PENCERE_BASLIGI, mesaj)

    def _kaydet_sessiz(self):
        """Fişi kaydeder (pencereyi kapatmadan). Başarılıysa fişi, hata varsa mesajı gösterip None döner."""
        self.kalemler.grid.commit_editor()          # yazılmakta olan hücre varsa önce hücreye işlenir
        baslik = self.baslik_verisi()
        for i, e in enumerate(self.txt_acik, start=1):
            baslik[f"aciklama{i}"] = e.text()
        try:
            fis = self.kaydet_servis(baslik, self.kalemler.rows(), self.fis_id)
        except self.HATA_SINIFI as e:
            self._hata_goster(str(e))
            return None
        except Exception as e:  # noqa: BLE001 — beklenmeyen hata sessiz kalmasın (veritabanı kilidi, bozuk oturum vb.)
            logger.exception("Fiş kaydedilemedi")
            self.db.rollback()
            self._hata_goster(f"Fiş kaydedilemedi: {e}")
            return None
        self.fis_id = fis.id
        self._dirty = False
        self.lbl_hata.setText("")
        return fis

    def _kaydedildi_mesaji(self, fis) -> None:
        self.lbl_hata.setStyleSheet("color:#16a34a; font-weight:600;")
        self.lbl_hata.setText(f"✔ {fis.fis_no} numaralı fiş kaydedildi.")

    def _kaydet(self, yeni: bool) -> None:
        fis = self._kaydet_sessiz()
        if fis is None:
            return
        if yeni:
            self._yeni_fis()
            self._kaydedildi_mesaji(fis)
        else:
            self.accept()

    # ---- çıktı (yazdır / PDF / Excel) ------------------------------------------------
    def _cikti_icin_hazirla(self) -> int | None:
        """Çıktı kayıtlı fişten alınır: yeni ya da değişmiş fiş önce kaydedilir (hata varsa çıktı alınmaz).
        Kilitli fiş değiştirilemeyeceğinden olduğu gibi kullanılır."""
        if self.fis_id and (not self._dirty or self.kilitli_mi()):
            return self.fis_id
        fis = self._kaydet_sessiz()
        if fis is None:
            return None
        self.lbl_baslik.setText(f"{self.BASLIK_MEVCUT} — {fis.fis_no}")
        self._kaydedildi_mesaji(fis)
        self._dirty = False
        return fis.id

    def _cikti(self, tur: str) -> None:
        fis_id = self._cikti_icin_hazirla()
        if fis_id is None:
            return
        try:
            self._cikti_uret(tur, fis_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("Fiş çıktısı alınamadı")
            self._hata_goster(f"Çıktı alınamadı: {e}")

    def _cikti_uret(self, tur: str, fis_id: int) -> None:
        rapor = self.rapor_modulu()
        veri = rapor.rapor_verisi(self.db, fis_id)
        ad = f"{self.CIKTI_ONEKI}_{veri['baslik']['fis_no']}"
        if tur == "excel":
            yol, _ = QFileDialog.getSaveFileName(self, "Excel'e Aktar", f"{ad}.xlsx", "Excel (*.xlsx)")
            if yol:
                rapor.excel_yaz(yol, veri)
        elif tur == "pdf":
            yol, _ = QFileDialog.getSaveFileName(self, "PDF Olarak Kaydet", f"{ad}.pdf", "PDF (*.pdf)")
            if yol:
                rapor.pdf_yaz(yol, veri)
        else:
            from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            if QPrintDialog(printer, self).exec():
                rapor.yazdir(printer, veri)
