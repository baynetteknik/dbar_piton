"""TOYA ERP - Ekranlar arası canlı yenileme (veri değişim yayını).

Herhangi bir oturumda (SQLAlchemy Session) değişiklik onaylanınca (commit), değişen kayıtların ait olduğu
KONULAR (cari, finans, stok, gorev, belge...) `veri_bus().degisti` sinyaliyle yayınlanır. Açık ekranlar
ilgilendikleri konuları dinleyip kendini yeniler (bkz. ThreePanelBaseWidget.BUS_KONULARI); böylece kasada
yapılan tahsilat, açık duran Cari Hareketleri ekranında pencereyi kapatıp açmadan görünür.
Yayın tek bir global Session olayından gelir; servis/ekran kodunun ayrıca emit etmesi gerekmez."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from sqlalchemy import event
from sqlalchemy.orm import Session

#: Model sınıf adı -> konu(lar)
KONULAR: dict[str, tuple[str, ...]] = {
    "Customer": ("cari", "cari_kart"),
    "CariFis": ("cari", "finans"),
    "CariHareket": ("cari", "finans"),
    "FinansHesap": ("finans", "finans_hesap"),
    "FinansFis": ("finans", "cari"),
    "FinansHareket": ("finans", "cari"),
    "Product": ("stok", "stok_kart"),
    "StokFis": ("stok",),
    "StokHareket": ("stok",),
    "StokRezerv": ("stok",),
    "Gorev": ("gorev",),
    "Bildirim": ("bildirim",),
    "Company": ("firma",),
    "Quotation": ("belge", "cari", "stok"),
    "QuotationLine": ("belge",),
    "BelgeBag": ("belge",),
}
_INFO_KEY = "_veri_bus_konular"


class VeriBus(QObject):
    degisti = pyqtSignal(str)


_bus: VeriBus | None = None
_kuruldu = False


def veri_bus() -> VeriBus:
    global _bus
    if _bus is None:
        _bus = VeriBus()
    return _bus


def yayinla(*konular: str) -> None:
    """Elle yayın (Session dışı değişiklikler için)."""
    b = veri_bus()
    for k in dict.fromkeys(konular):
        b.degisti.emit(k)


def _topla(session: Session, _ctx, _instances) -> None:
    kume = session.info.setdefault(_INFO_KEY, set())
    for obj in (*session.new, *session.dirty, *session.deleted):
        kume.update(KONULAR.get(type(obj).__name__, ()))


def _onaylandi(session: Session) -> None:
    kume = session.info.pop(_INFO_KEY, None)
    if kume:
        yayinla(*sorted(kume))


def _geri_alindi(session: Session) -> None:
    session.info.pop(_INFO_KEY, None)


def kur() -> None:
    """Global Session olaylarını bir kez bağlar (idempotent)."""
    global _kuruldu
    if _kuruldu:
        return
    event.listen(Session, "before_flush", _topla)
    event.listen(Session, "after_commit", _onaylandi)
    event.listen(Session, "after_soft_rollback", lambda s, _p: _geri_alindi(s))
    _kuruldu = True
