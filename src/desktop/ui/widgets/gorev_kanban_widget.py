"""TOYA ERP - GorevKanbanWidget: görevleri durum sütunlarında gösteren pano; kartı başka sütuna sürükleyince durum değişir.

    w = GorevKanbanWidget(); w.set_gorevler(liste, gecikmis_mi); w.durum_degisti.connect(fn(gorev_id, yeni_durum)); w.gorev_acildi.connect(fn(id))
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.services.gorev_service import DURUMLAR, ONCELIKLER

SUTUNLAR = ("yapilacak", "devam", "inceleme", "tamam")
_RENK = {1: "#94a3b8", 2: "#2563eb", 3: "#f59e0b", 4: "#dc2626"}
_ID = Qt.ItemDataRole.UserRole


class _Liste(QListWidget):
    """Kart listesi: başka sütundan bırakılan kart için `birakildi` yayar (durumu üst widget değiştirir)."""
    birakildi = pyqtSignal(int, str)

    def __init__(self, durum: str) -> None:
        super().__init__()
        self.durum = durum
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(3)
        self.setWordWrap(True)
        self.setStyleSheet("QListWidget { background:#f1f5f9; border:1px solid #e2e8f0; border-radius:6px; }"
                           "QListWidget::item { background:#ffffff; color:#0f172a; border:1px solid #cbd5e1; border-radius:5px; padding:6px; }"
                           "QListWidget::item:selected { background:#dbeafe; color:#1e3a8a; border-color:#2563eb; }")

    def dropEvent(self, e) -> None:  # noqa: N802
        kaynak = e.source()
        if isinstance(kaynak, _Liste) and kaynak is not self and kaynak.currentItem() is not None:
            gid = kaynak.currentItem().data(_ID)
            e.setDropAction(Qt.DropAction.IgnoreAction)          # kartı biz yeniden çizeriz (durum değişince liste tazelenir)
            e.accept()
            self.birakildi.emit(int(gid), self.durum)
            return
        e.ignore()


class GorevKanbanWidget(QWidget):
    durum_degisti = pyqtSignal(int, str)
    gorev_acildi = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self.listeler: dict[str, _Liste] = {}
        self.basliklar: dict[str, QLabel] = {}
        for d in SUTUNLAR:
            kol = QFrame()
            v = QVBoxLayout(kol)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(4)
            b = QLabel(DURUMLAR[d])
            b.setStyleSheet("font-size:11px; font-weight:800; color:#1e3a8a; letter-spacing:1px;")
            lst = _Liste(d)
            lst.birakildi.connect(self.durum_degisti)
            lst.itemDoubleClicked.connect(lambda it: self.gorev_acildi.emit(int(it.data(_ID))))
            v.addWidget(b)
            v.addWidget(lst, 1)
            h.addWidget(kol, 1)
            self.listeler[d], self.basliklar[d] = lst, b

    def set_gorevler(self, gorevler: list, gecikmis_mi=lambda g: False) -> None:
        for d, lst in self.listeler.items():
            lst.clear()
        sayac = dict.fromkeys(SUTUNLAR, 0)
        for g in gorevler:
            d = g.durum if g.durum in self.listeler else None          # iptal edilenler panoda gösterilmez
            if d is None:
                continue
            sayac[d] += 1
            son = f"  ·  ⏰ {g.bitis:%d.%m %H:%M}" if g.bitis else ""
            atanan = f"\n👤 {g.atanan}" if g.atanan else ""
            gec = "⚠ " if gecikmis_mi(g) else ""
            it = QListWidgetItem(f"{gec}{g.baslik}\n{ONCELIKLER.get(g.oncelik, '')}{son}{atanan}")
            it.setData(_ID, g.id)
            it.setForeground(QBrush(QColor("#b91c1c" if gec else "#0f172a")))
            it.setToolTip(g.aciklama or g.baslik)
            it.setBackground(QBrush(QColor("#ffffff")))
            self.listeler[d].addItem(it)
        for d, b in self.basliklar.items():
            b.setText(f"{DURUMLAR[d].upper()}  ({sayac[d]})")
