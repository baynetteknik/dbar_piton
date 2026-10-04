"""TOYA ERP - Numara şablonları ayar bileşeni (belge ve fiş numaraları).

Her belge/fiş türü için şablon düzenlenir; yanında güncel şablonla üretilecek örnek numara canlı görünür. Boş bırakılan şablon
varsayılana döner. İş kuralı `numara_servisi`'ndedir (doğrulama, kayıt); bu bileşen yalnız girdiyi toplar. Genel Ayarlar'a bir panel
olarak eklenebilir: `NumaraSablonlariWidget(db)`."""

from __future__ import annotations

from datetime import date

from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from src.desktop.services import numara_servisi as ns
from src.desktop.ui.components import dialog_style
from src.desktop.ui.components.button_style import PRIMARY, btn_style


class NumaraSablonlariWidget(QWidget):
    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.alanlar: dict[str, QLineEdit] = {}
        self.ornekler: dict[str, QLabel] = {}
        lyt = QVBoxLayout(self)
        baslik = QLabel("🔢 Belge ve Fiş Numara Şablonları")
        baslik.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(baslik)
        a = QLabel("Belirteçler: {YYYY} yıl · {YY} kısa yıl · {MM} ay · {#####} sıra (# sayısı = hane). Sıra, şablondaki {MM} varsa her ay, yalnız yıl "
                   "varsa her yıl sıfırlanır. Fatura varsayılanı e-Fatura numarası biçimindedir (3 harf + yıl + 9 hane). Boş = varsayılan.")
        a.setWordWrap(True)
        a.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(a)
        govde = QWidget()
        g = QGridLayout(govde)
        for satir, (kod, ad) in enumerate(ns.ADLAR.items()):
            g.addWidget(QLabel(ad), satir, 0)
            ed = QLineEdit(ns.sablon(db, kod) if ns.sablon(db, kod) != ns.VARSAYILANLAR[kod] else "")
            ed.setPlaceholderText(ns.VARSAYILANLAR[kod])
            ed.textChanged.connect(lambda _t, k=kod: self._ornek_guncelle(k))
            self.alanlar[kod] = ed
            g.addWidget(ed, satir, 1)
            o = QLabel("")
            o.setMinimumWidth(190)
            self.ornekler[kod] = o
            g.addWidget(o, satir, 2)
            self._ornek_guncelle(kod)
        g.setColumnStretch(1, 1)
        kaydirma = QScrollArea()
        kaydirma.setWidgetResizable(True)
        kaydirma.setWidget(govde)
        lyt.addWidget(kaydirma, 1)
        alt = QHBoxLayout()
        self.lbl_hata = QLabel("")
        self.lbl_hata.setStyleSheet("color:#dc2626; font-weight:600;")
        alt.addWidget(self.lbl_hata, 1)
        self.btn_kaydet = QPushButton("💾 Kaydet")
        self.btn_kaydet.setStyleSheet(btn_style(PRIMARY, "#ffffff"))
        self.btn_kaydet.clicked.connect(self.kaydet)
        alt.addWidget(self.btn_kaydet)
        lyt.addLayout(alt)

    def _ornek_guncelle(self, kod: str) -> None:
        metin = self.alanlar[kod].text().strip() or ns.VARSAYILANLAR[kod]
        try:
            ns.dogrula(metin)
            self.ornekler[kod].setText("→ " + ns.uret(metin, date.today(), 1))
            self.ornekler[kod].setStyleSheet("color:#0f766e; font-weight:600;")
        except ns.SablonHatasi as e:
            self.ornekler[kod].setText("⚠ " + str(e)[:40])
            self.ornekler[kod].setStyleSheet("color:#dc2626;")

    def kaydet(self) -> bool:
        for kod, ed in self.alanlar.items():
            try:
                ns.sablon_kaydet(self.db, kod, ed.text())
            except ns.SablonHatasi as e:
                self.lbl_hata.setText(f"{ns.ADLAR[kod]}: {e}")
                return False
        self.lbl_hata.setText("")
        dialog_style.bilgi(self, "Numara Şablonları", "Şablonlar kaydedildi. Bundan sonra üretilen numaralar yeni şablonu kullanır.")
        return True
