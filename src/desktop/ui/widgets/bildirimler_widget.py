"""TOYA ERP - Bildirimler kartı: online portal müşteri kararları (kabul / ret / karşı teklif / süre dolumu) listesi.

Ana panelde kart olarak ve zil düğmesinin açılır penceresinde kullanılır. Çift tıklama ilgili teklifi açtırır (`ac_istendi`) ve
bildirimi okundu yapar. Yeni bildirim geldiğinde veri yayını (`veri_bus`) ile kendini yeniler."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from src.desktop.services.bildirim_service import TURLER, BildirimService

_ID = Qt.ItemDataRole.UserRole
_NO = Qt.ItemDataRole.UserRole + 1


class BildirimlerWidget(QFrame):
    ac_istendi = pyqtSignal(str, str)      # ilgili_tur, ilgili_no
    degisti = pyqtSignal()                 # okundu durumu değişti (zil rozeti güncellensin)
    kontrol_istendi = pyqtSignal()         # "Portalı şimdi kontrol et"

    def __init__(self, db, parent=None, *, limit: int = 30, otomatik_yenile: bool = True) -> None:
        super().__init__(parent)
        self.db, self.limit = db, limit
        self.setObjectName("Bildirimler")
        self.setStyleSheet("#Bildirimler { background:#ffffff; border:1px solid #cbd5e1; border-radius:8px; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 10, 12, 10)
        v.setSpacing(6)
        ust = QHBoxLayout()
        self.lbl_baslik = QLabel("🔔 BİLDİRİMLER")
        self.lbl_baslik.setStyleSheet("font-size:12px; font-weight:800; color:#1e3a8a; letter-spacing:1px; border:none;")
        self.btn_hepsi = QPushButton("Tümü okundu")
        self.btn_hepsi.setStyleSheet("QPushButton{border:none; color:#2563eb; font-size:11px;} QPushButton:hover{text-decoration:underline;}")
        self.btn_hepsi.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_kontrol = QPushButton("🔄 Kontrol et")
        self.btn_kontrol.setStyleSheet(self.btn_hepsi.styleSheet())
        self.btn_kontrol.setToolTip("Portalı şimdi kontrol et (müşteri kararları)")
        self.btn_kontrol.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_kontrol.clicked.connect(self.kontrol_istendi)
        ust.addWidget(self.lbl_baslik)
        ust.addStretch()
        ust.addWidget(self.btn_kontrol)
        ust.addWidget(self.btn_hepsi)
        v.addLayout(ust)
        self.liste = QListWidget()
        self.liste.setStyleSheet("QListWidget{border:none; background:transparent; color:#1e293b;} "
                                 "QListWidget::item{padding:5px 4px; border-bottom:1px solid #f1f5f9;} "
                                 "QListWidget::item:selected{background:#dbeafe; color:#1e3a8a;}")
        self.liste.setWordWrap(True)
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.liste.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.liste.setToolTip("Çift tıklayınca ilgili teklif açılır")
        v.addWidget(self.liste, 1)
        self.btn_hepsi.clicked.connect(self.hepsini_okundu)
        self.liste.itemDoubleClicked.connect(self._ac)
        if otomatik_yenile:
            from src.desktop.services import veri_bus
            veri_bus.kur()
            veri_bus.veri_bus().degisti.connect(self._bus_geldi)
        self.yenile()

    def _bus_geldi(self, konu: str) -> None:
        if konu == "bildirim":
            QTimer.singleShot(150, self.yenile)      # yayın commit içinden gelir; SQL sorgusu ondan sonra çalışmalı

    def yenile(self) -> None:
        if self.db is None:
            return
        svc = BildirimService(self.db)
        try:
            kayitlar, okunmamis = svc.liste(limit=self.limit), svc.okunmamis_sayisi()
        except Exception:  # noqa: BLE001 - ana panel açılışı bildirim hatasıyla bozulmasın
            self.lbl_baslik.setText("🔔 BİLDİRİMLER — okunamadı")
            return
        self.lbl_baslik.setText("🔔 BİLDİRİMLER" + (f" — {okunmamis} yeni" if okunmamis else ""))
        self.btn_hepsi.setEnabled(okunmamis > 0)
        self.liste.clear()
        if not kayitlar:
            it = QListWidgetItem("Henüz bildirim yok. Müşteri portaldan teklife cevap verdiğinde burada görünür.")
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.liste.addItem(it)
            return
        for b in kayitlar:
            simge = TURLER.get(b.tur, ("🔔", "info"))[0]
            zaman = b.created_at.strftime("%d.%m %H:%M") if b.created_at else ""
            it = QListWidgetItem(f"{simge} {b.baslik}\n{b.mesaj or ''}\n{zaman}")
            it.setData(_ID, b.id)
            it.setData(_NO, b.ilgili_no or "")
            f = QFont(it.font())
            f.setBold(not b.okundu)
            it.setFont(f)
            if b.okundu:
                it.setForeground(Qt.GlobalColor.gray)
            self.liste.addItem(it)

    def _ac(self, item: QListWidgetItem) -> None:
        bid = item.data(_ID)
        if bid is None:
            return
        BildirimService(self.db).okundu(bid)
        no = item.data(_NO)
        self.yenile()
        self.degisti.emit()
        if no:
            self.ac_istendi.emit("teklif", no)

    def hepsini_okundu(self) -> None:
        BildirimService(self.db).hepsini_okundu()
        self.yenile()
        self.degisti.emit()
