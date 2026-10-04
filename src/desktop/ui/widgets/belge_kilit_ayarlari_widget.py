"""TOYA ERP - Belge zinciri kilit kuralları ayar bileşeni.

Her kural için sertlik seçilir: Engelle · Uyar ve devam et · Serbest. İş kuralı `belge_kilit_servisi`'ndedir; bu bileşen yalnız
seçimi toplar. Genel Ayarlar'a panel olarak eklenebilir: `BelgeKilitAyarlariWidget(db)`."""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.desktop.services import belge_kilit_servisi as bk
from src.desktop.ui.components import dialog_style
from src.desktop.ui.components.button_style import PRIMARY, btn_style


class BelgeKilitAyarlariWidget(QWidget):
    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.kutular: dict[str, QComboBox] = {}
        lyt = QVBoxLayout(self)
        baslik = QLabel("🔗 Belge Zinciri Kilit Kuralları")
        baslik.setStyleSheet("font-size:14px; font-weight:800; color:#1e3a8a;")
        lyt.addWidget(baslik)
        a = QLabel("Kurallar varsayılan olarak uyarır ve devam ettirir; gereken yerlerde engeller. Her kuralın sertliğini değiştirebilirsiniz. "
                   "Silme, bağ koparma ve kural kararları işlem günlüğüne yazılır.")
        a.setWordWrap(True)
        a.setStyleSheet("color:#64748b; font-size:11px;")
        lyt.addWidget(a)
        g = QGridLayout()
        combo_style = """
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
        for satir, (kural, (ad, _v)) in enumerate(bk.KURALLAR.items()):
            g.addWidget(QLabel(ad), satir, 0)
            cmb = QComboBox()
            cmb.setStyleSheet(combo_style)
            for kod, etiket in bk.SEVIYELER.items():
                cmb.addItem(etiket, kod)
            cmb.setCurrentIndex(cmb.findData(bk.seviye(db, kural)))
            self.kutular[kural] = cmb
            g.addWidget(cmb, satir, 1)
        g.setColumnStretch(0, 1)
        lyt.addLayout(g)
        lyt.addStretch()
        self.btn_kaydet = QPushButton("💾 Kaydet")
        self.btn_kaydet.setStyleSheet(btn_style(PRIMARY, "#ffffff"))
        self.btn_kaydet.clicked.connect(self.kaydet)
        lyt.addWidget(self.btn_kaydet)

    def kaydet(self) -> None:
        for kural, cmb in self.kutular.items():
            bk.seviye_kaydet(self.db, kural, cmb.currentData())
        dialog_style.bilgi(self, "Kilit Kuralları", "Kilit kuralları kaydedildi.")
