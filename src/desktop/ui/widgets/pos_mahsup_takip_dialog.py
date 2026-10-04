"""TOYA ERP - PosMahsupTakipDialog: bekleyen POS→Banka bakiyelerini gösteren takip ekranı (2026-10-03).

Kullanıcı isteği: "bu fişler ayrı bir ekranda takip edilerek ya ödeme planına göre zamanı gelince ya
otomatik yada sorularak tahsil edilerek POS hesabına aktarılacak". `pos_otomatik_mahsup` açık hesaplar
zaten Banka Hareketleri ekranı her açıldığında sessizce mahsup ediliyor (bkz. `pos_mahsup_servisi.py`,
04.09) — ama o akış görünmüyordu ve `pos_otomatik_mahsup` KAPALI hesaplar için hiçbir manuel yol yoktu.
Bu ekran ikisini de çözer: tüm POS hesaplarının bekleyen (vadesi gelmiş / gelmemiş) bakiyesini listeler,
"Tahsil Et" butonu kullanıcıya SORARAK (QMessageBox onayı) manuel mahsup tetikler — otomatik mahsup açık
hesaplarda da erken/elle tetiklemek için kullanılabilir."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.desktop.services import pos_mahsup_servisi
from src.desktop.ui.components.dialog_style import apply_light_dialog_style
from src.desktop.ui.widgets.money_edit import bicimle

_SUTUNLAR = ["POS Hesabı", "Hedef Banka Hesabı", "Otomatik", "Vadesi Gelmiş (Bekleyen)", "Vadesi Gelmemiş", "En Eski İşlem", ""]


def _tutar_metni(d: dict[str, float]) -> str:
    return ", ".join(f"{bicimle(v)} {pb}" for pb, v in d.items() if v) or "—"


class PosMahsupTakipDialog(QDialog):
    def __init__(self, db, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("POS Mahsup Takip")
        self.resize(860, 420)
        apply_light_dialog_style(self)

        lyt = QVBoxLayout(self)
        ipucu = QLabel(
            "Her POS hesabının bankaya henüz aktarılmamış bakiyesi. <b>Otomatik Mahsup</b> açık hesaplar "
            "Banka Hareketleri ekranı her açıldığında kendiliğinden aktarılır; kapalı olanlar yalnızca "
            "buradaki <b>Tahsil Et</b> ile (valör günü geçmiş tutar için) aktarılır.",
        )
        ipucu.setWordWrap(True)
        ipucu.setStyleSheet("color:#475569;font-size:11px;background:#f8fafc;border:1px solid #e2e8f0;"
                             "border-radius:6px;padding:8px;")
        lyt.addWidget(ipucu)

        self.tbl = QTableWidget(0, len(_SUTUNLAR))
        self.tbl.setHorizontalHeaderLabels(_SUTUNLAR)
        header = self.tbl.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in (2, 3, 4, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lyt.addWidget(self.tbl, 1)

        bar = QHBoxLayout()
        self.lbl_durum = QLabel("")
        self.lbl_durum.setStyleSheet("color:#16a34a;font-size:11px;font-weight:600;")
        bar.addWidget(self.lbl_durum)
        bar.addStretch()
        btn_yenile = QPushButton("🔄 Yenile")
        btn_yenile.clicked.connect(self._yukle)
        btn_kapat = QPushButton("✖ Kapat")
        btn_kapat.clicked.connect(self.accept)
        bar.addWidget(btn_yenile)
        bar.addWidget(btn_kapat)
        lyt.addLayout(bar)

        self._yukle()

    def _yukle(self) -> None:
        self.lbl_durum.setText("")
        bakiyeler = pos_mahsup_servisi.bekleyen_bakiyeler(self.db)
        self.tbl.setRowCount(0)
        for b in bakiyeler:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            pos = b.pos_hesap
            hedef = f"{pos.pos_hedef_hesap.kod} — {pos.pos_hedef_hesap.ad}" if pos.pos_hedef_hesap else "(Seçilmedi)"
            self.tbl.setItem(r, 0, QTableWidgetItem(f"{pos.kod} — {pos.ad}"))
            self.tbl.setItem(r, 1, QTableWidgetItem(hedef))
            self.tbl.setItem(r, 2, QTableWidgetItem("Evet" if pos.pos_otomatik_mahsup else "Hayır"))
            self.tbl.setItem(r, 3, QTableWidgetItem(_tutar_metni(b.vadesi_gelmis)))
            self.tbl.setItem(r, 4, QTableWidgetItem(_tutar_metni(b.vadesi_gelmemis)))
            self.tbl.setItem(r, 5, QTableWidgetItem(b.en_eski_tarih.strftime("%d.%m.%Y") if b.en_eski_tarih else "—"))
            btn = QPushButton("💸 Tahsil Et")
            btn.setEnabled(bool(b.vadesi_gelmis) and pos.pos_hedef_hesap_id is not None)
            btn.clicked.connect(lambda _c=False, hesap_id=pos.id, kod=pos.kod: self._tahsil_et(hesap_id, kod))
            self.tbl.setCellWidget(r, 6, btn)
        if self.tbl.rowCount() == 0:
            self.lbl_durum.setText("Bekleyen POS bakiyesi yok.")

    def _tahsil_et(self, pos_hesap_id: int, kod: str) -> None:
        if QMessageBox.question(
            self, "Tahsil Et",
            f"{kod} hesabının vadesi gelmiş bekleyen bakiyesi hedef banka hesabına aktarılsın mı?",
        ) != QMessageBox.StandardButton.Yes:
            return
        sonuclar = pos_mahsup_servisi.tek_hesabi_mahsup_et(self.db, pos_hesap_id)
        self._yukle()
        if sonuclar:
            toplam = " + ".join(f"{bicimle(s.tutar)} {s.para_birimi}" for s in sonuclar)
            self.lbl_durum.setText(f"✔ {kod}: {toplam} aktarıldı ({sonuclar[0].fis.fis_no}).")
        else:
            self.lbl_durum.setText(f"{kod} için aktarılacak vadesi gelmiş tutar bulunamadı.")
