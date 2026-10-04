"""TOYA ERP - GorevTakvimWidget: aylık takvim; günlerde görev/randevu/hatırlatmalar listelenir.

Genel amaçlı: olayları dışarıdan alır (`set_olaylar([Olay…])`), ay değişince `ay_degisti(ilk_gun, son_gun)` yayar (görünen 6 hafta),
olaya çift tıklayınca `gorev_acildi(id)`, boş güne çift tıklayınca `gun_yeni(tarih)`. Haftanın ilk günü Pazartesi'dir."""

from __future__ import annotations

from datetime import date, timedelta

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]
_RENK = {1: "#64748b", 2: "#1d4ed8", 3: "#b45309", 4: "#b91c1c"}
_ID = Qt.ItemDataRole.UserRole
_EN_FAZLA = 4


def ay_gorunumu(yil: int, ay: int) -> list[date]:
    """Ayı kapsayan, Pazartesi'den başlayan 42 günlük (6 hafta) liste."""
    ilk = date(yil, ay, 1)
    bas = ilk - timedelta(days=ilk.weekday())
    return [bas + timedelta(days=i) for i in range(42)]


class _Gun(QFrame):
    def __init__(self, gun: date, bu_ay: bool, bugun: bool, ust: "GorevTakvimWidget") -> None:
        super().__init__()
        self.gun, self.ust = gun, ust
        hafta_sonu = gun.weekday() >= 5
        zemin = "#dbeafe" if bugun else ("#ffffff" if bu_ay else "#f1f5f9")
        self.setStyleSheet(f"QFrame {{ background:{zemin}; border:1px solid {'#2563eb' if bugun else '#e2e8f0'}; }}")
        v = QVBoxLayout(self)
        v.setContentsMargins(3, 2, 3, 2)
        v.setSpacing(1)
        self.baslik = QLabel(str(gun.day))
        renk = "#94a3b8" if not bu_ay else ("#dc2626" if hafta_sonu else "#1e293b")
        self.baslik.setStyleSheet(f"font-weight:{'800' if bugun else '600'}; font-size:11px; color:{renk}; border:none; background:transparent;")
        self.liste = QListWidget()
        self.liste.setStyleSheet("QListWidget { border:none; background:transparent; } QListWidget::item { padding:0px 2px; }"
                                 "QListWidget::item:selected { background:#bfdbfe; color:#1e3a8a; }")
        self.liste.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.liste.itemDoubleClicked.connect(lambda it: ust.gorev_acildi.emit(int(it.data(_ID))) if it.data(_ID) else ust.gun_yeni.emit(gun))
        v.addWidget(self.baslik)
        v.addWidget(self.liste, 1)

    def mouseDoubleClickEvent(self, e) -> None:  # noqa: N802
        self.ust.gun_yeni.emit(self.gun)


class GorevTakvimWidget(QWidget):
    gorev_acildi = pyqtSignal(int)
    gun_yeni = pyqtSignal(object)
    ay_degisti = pyqtSignal(object, object)

    def __init__(self, parent=None, bugun: date | None = None) -> None:
        super().__init__(parent)
        self._bugun = bugun or date.today()
        self.yil, self.ay = self._bugun.year, self._bugun.month
        self._olaylar: list = []
        self.gunler: dict[date, _Gun] = {}
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        ust = QHBoxLayout()
        self.btn_onceki, self.btn_bugun, self.btn_sonraki = QPushButton("◀"), QPushButton("Bugün"), QPushButton("▶")
        self.lbl_ay = QLabel()
        self.lbl_ay.setStyleSheet("font-size:15px; font-weight:800; color:#1e3a8a;")
        for b in (self.btn_onceki, self.btn_bugun, self.btn_sonraki):
            b.setFixedHeight(26)
            ust.addWidget(b)
        ust.addSpacing(10)
        ust.addWidget(self.lbl_ay)
        ust.addStretch()
        v.addLayout(ust)
        self.izgara_kap = QWidget()
        self.izgara = QGridLayout(self.izgara_kap)
        self.izgara.setContentsMargins(0, 0, 0, 0)
        self.izgara.setSpacing(0)
        v.addWidget(self.izgara_kap, 1)
        self.btn_onceki.clicked.connect(lambda: self.git(-1))
        self.btn_sonraki.clicked.connect(lambda: self.git(1))
        self.btn_bugun.clicked.connect(self.bugune_git)
        self._kur()

    # ---- gezinme ----------------------------------------------------------
    def aralik(self) -> tuple[date, date]:
        g = ay_gorunumu(self.yil, self.ay)
        return g[0], g[-1]

    def git(self, ay_farki: int) -> None:
        m = self.ay - 1 + ay_farki
        self.yil, self.ay = self.yil + m // 12, m % 12 + 1
        self._kur()
        self.ay_degisti.emit(*self.aralik())

    def bugune_git(self) -> None:
        self.yil, self.ay = self._bugun.year, self._bugun.month
        self._kur()
        self.ay_degisti.emit(*self.aralik())

    # ---- çizim -------------------------------------------------------------
    def _kur(self) -> None:
        while self.izgara.count():
            w = self.izgara.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self.gunler = {}
        self.lbl_ay.setText(f"{AYLAR[self.ay - 1]} {self.yil}")
        for i, ad in enumerate(GUNLER):
            l = QLabel(ad)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setStyleSheet(f"font-size:11px; font-weight:700; color:{'#dc2626' if i >= 5 else '#475569'}; padding:3px;")
            self.izgara.addWidget(l, 0, i)
        for i, g in enumerate(ay_gorunumu(self.yil, self.ay)):
            cell = _Gun(g, g.month == self.ay, g == self._bugun, self)
            self.izgara.addWidget(cell, 1 + i // 7, i % 7)
            self.gunler[g] = cell
        for r in range(1, 7):
            self.izgara.setRowStretch(r, 1)
        self._olaylari_yaz()

    def set_olaylar(self, olaylar: list) -> None:
        self._olaylar = list(olaylar)
        self._olaylari_yaz()

    def _olaylari_yaz(self) -> None:
        for c in self.gunler.values():
            c.liste.clear()
        gruplar: dict[date, list] = {}
        for o in self._olaylar:
            gruplar.setdefault(o.gun, []).append(o)
        for gun, liste in gruplar.items():
            cell = self.gunler.get(gun)
            if cell is None:
                continue
            for o in liste[:_EN_FAZLA]:
                g = o.gorev
                saat = f"{o.baslangic:%H:%M} " if (o.baslangic and not g.tum_gun) else ""
                bitti = g.durum in ("tamam", "iptal")
                it = QListWidgetItem(("✔ " if g.durum == "tamam" else "") + saat + g.baslik)
                it.setData(_ID, g.id)
                it.setToolTip(f"{g.baslik}\n{g.aciklama or ''}".strip())
                it.setForeground(QBrush(QColor("#94a3b8" if bitti else _RENK.get(g.oncelik, "#1d4ed8"))))
                cell.liste.addItem(it)
            if len(liste) > _EN_FAZLA:
                fazla = QListWidgetItem(f"+{len(liste) - _EN_FAZLA} daha…")
                fazla.setForeground(QBrush(QColor("#64748b")))
                cell.liste.addItem(fazla)
