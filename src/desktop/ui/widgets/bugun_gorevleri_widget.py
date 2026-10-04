"""TOYA ERP - BugunGorevleriWidget: ana paneldeki "Bugünün Görevleri" kartı.

Gecikmiş ve bugüne düşen açık görevleri/randevuları (yinelenenler dahil) listeler; çift tıkla görev penceresi açılır, "✔ Tamamla" ile
bitirilir, "➕ Görev" yeni görev açar, "Tümü" Görevler ekranını ister (`tumu_istendi`). Varsayılan olarak yalnız giriş yapan kullanıcıya
atanmış ve kimseye atanmamış görevler görünür ("Herkesinki" kutusuyla tümü). Dakikada bir ve kayıttan sonra kendini yeniler."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.services.gorev_service import ONCELIKLER, GorevError, GorevService
from src.desktop.ui.components.button_style import btn_style
from src.desktop.ui.widgets.gorev_dialog import GorevDialog

_ID = Qt.ItemDataRole.UserRole


class BugunGorevleriWidget(QFrame):
    tumu_istendi = pyqtSignal()
    degisti = pyqtSignal()

    def __init__(self, db, kullanici: str = "", parent=None, otomatik_yenile: bool = True) -> None:
        super().__init__(parent)
        self.db, self.kullanici = db, kullanici
        self.setObjectName("BugunGorevleri")
        self.setStyleSheet("#BugunGorevleri { background:#ffffff; border:1px solid #cbd5e1; border-radius:8px; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)
        ust = QHBoxLayout()
        t = QLabel("✅ BUGÜNÜN GÖREVLERİ")
        t.setStyleSheet("font-size:12px; font-weight:800; color:#1e3a8a; letter-spacing:1px; border:none;")
        self.chk_herkes = QCheckBox("Herkesinki")
        self.chk_herkes.setStyleSheet("font-size:11px; color:#475569; border:none;")
        self.chk_herkes.toggled.connect(lambda _b: self.yenile())
        ust.addWidget(t)
        ust.addStretch()
        ust.addWidget(self.chk_herkes)
        v.addLayout(ust)
        self.lbl_ozet = QLabel("")
        self.lbl_ozet.setStyleSheet("font-size:11px; font-weight:600; color:#475569; border:none;")
        v.addWidget(self.lbl_ozet)
        self.liste = QListWidget()
        self.liste.setStyleSheet("QListWidget { border:1px solid #e2e8f0; border-radius:6px; background:#f8fafc; }"
                                 "QListWidget::item { padding:5px 6px; border-bottom:1px solid #e2e8f0; }"
                                 "QListWidget::item:selected { background:#dbeafe; color:#1e3a8a; }")
        self.liste.itemDoubleClicked.connect(lambda it: self.ac(int(it.data(_ID))))
        v.addWidget(self.liste, 1)
        alt = QHBoxLayout()
        self.btn_yeni, self.btn_tamam, self.btn_tumu = QPushButton("➕ Görev"), QPushButton("✔ Tamamla"), QPushButton("Tümü ›")
        for b in (self.btn_yeni, self.btn_tamam, self.btn_tumu):
            b.setStyleSheet(btn_style())
            alt.addWidget(b)
        v.addLayout(alt)
        self.btn_yeni.clicked.connect(self.yeni)
        self.btn_tamam.clicked.connect(self.tamamla)
        self.btn_tumu.clicked.connect(self.tumu_istendi)
        self.liste.itemSelectionChanged.connect(lambda: self.btn_tamam.setEnabled(self.liste.currentItem() is not None and self.liste.currentItem().data(_ID) is not None))
        self.btn_tamam.setEnabled(False)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.yenile)
        if otomatik_yenile:
            self._timer.start(60_000)
            from src.desktop.services import veri_bus
            veri_bus.kur()
            veri_bus.veri_bus().degisti.connect(self._bus_geldi)
        self.yenile()

    def _bus_geldi(self, konu: str) -> None:
        if konu == "gorev" and self.isVisible():
            QTimer.singleShot(150, self.yenile)      # yayın commit içinden gelir; SQL sorgusu ondan sonra çalışmalı

    def yenile(self) -> None:
        if self.db is None:
            return
        try:
            oz = GorevService(self.db).bugun_ozeti(self.kullanici, tumu=self.chk_herkes.isChecked())
        except Exception:  # noqa: BLE001 - ana panel açılışı görev hatasıyla bozulmasın
            self.lbl_ozet.setText("Görevler okunamadı.")
            return
        self.liste.clear()
        gec, bugun = oz["gecikmis"], oz["bugun"]
        self.lbl_ozet.setText(f"⚠ Gecikmiş: {len(gec)}    📆 Bugün: {len(bugun)}")
        self.lbl_ozet.setStyleSheet("font-size:11px; font-weight:700; color:" + ("#b91c1c" if gec else "#475569") + "; border:none;")
        for g in gec:
            self._ekle(f"⚠ {g.bitis:%d.%m} {g.baslik}", g, "#b91c1c")
        for o in bugun:
            g = o.gorev
            saat = o.baslangic or o.bitis
            self._ekle(f"{'⏰' if o.baslangic else '📌'} {saat:%H:%M} {g.baslik}" if saat and not g.tum_gun else f"📌 {g.baslik}", g,
                       "#b45309" if g.oncelik >= 3 else "#0f172a")
        if not gec and not bugun:
            it = QListWidgetItem("Bugün için açık görev yok. 🎉")
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            it.setForeground(QBrush(QColor("#64748b")))
            self.liste.addItem(it)

    def _ekle(self, metin: str, g, renk: str) -> None:
        it = QListWidgetItem(metin)
        it.setData(_ID, g.id)
        it.setToolTip(f"{ONCELIKLER.get(g.oncelik, '')}" + (f" · {g.atanan}" if g.atanan else "") + (f"\n{g.aciklama}" if g.aciklama else ""))
        it.setForeground(QBrush(QColor(renk)))
        self.liste.addItem(it)

    def ac(self, gorev_id: int) -> None:
        if GorevDialog(self.db, gorev_id=gorev_id, kullanici=self.kullanici, parent=self).exec():
            self.yenile()
            self.degisti.emit()

    def yeni(self) -> None:
        if GorevDialog(self.db, varsayilan={"atanan": self.kullanici}, kullanici=self.kullanici, parent=self).exec():
            self.yenile()
            self.degisti.emit()

    def tamamla(self) -> None:
        it = self.liste.currentItem()
        if it is None or it.data(_ID) is None:
            return
        try:
            GorevService(self.db).durum_degistir(int(it.data(_ID)), "tamam")
        except GorevError:
            pass
        self.yenile()
        self.degisti.emit()
