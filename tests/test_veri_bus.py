from PyQt6.QtTest import QTest

from src.core.models import Currency, Customer
from src.desktop.services import veri_bus
from src.desktop.services.cari_hareket_service import CariHareketService
from src.desktop.ui.cari_hareket_screen import CariHareketScreen
from src.desktop.ui.stok_hareket_screen import StokHareketScreen


def _db(db_session):
    db_session.add_all([Customer(fullname="ACME", marketplace="local", customer_code="C1"),
                        Currency(code="USD", name="Dolar", rate=30.0, is_active=True)])
    db_session.commit()
    return db_session


def test_commit_yayini_acik_ekrani_yeniler(qapp, db_session):
    db = _db(db_session)
    s = CariHareketScreen(db_session=db)
    s.show()
    assert s.table_model.rowCount() == 0
    CariHareketService(db).create(customer_id=1, tur="tahsilat", tutar=100)   # başka bir yerden kayıt
    QTest.qWait(500)
    assert s.table_model.rowCount() == 1
    s.close()


def test_ilgisiz_konu_yenilemez(qapp, db_session):
    db = _db(db_session)
    s = StokHareketScreen(db_session=db)
    s.show()
    sayac = []
    s.refresh_table = lambda: sayac.append(1)
    CariHareketService(db).create(customer_id=1, tur="tahsilat", tutar=5)
    QTest.qWait(400)
    assert sayac == []
    s.close()


def test_gorunmeyen_ekran_acilinca_yenilenir(qapp, db_session):
    db = _db(db_session)
    s = CariHareketScreen(db_session=db)               # gösterilmedi (başka sekmede gibi)
    CariHareketService(db).create(customer_id=1, tur="tahsilat", tutar=100)
    QTest.qWait(400)
    assert s.table_model.rowCount() == 0 and s._bus_bayat is True
    s.show()
    assert s.table_model.rowCount() == 1
    s.close()


def test_geri_alinan_islem_yayin_yapmaz(qapp, db_session):
    db = _db(db_session)
    veri_bus.kur()
    gelen = []
    veri_bus.veri_bus().degisti.connect(gelen.append)
    db.add(Customer(fullname="X", marketplace="local", customer_code="C9"))
    db.flush()
    db.rollback()
    assert gelen == []
    veri_bus.veri_bus().degisti.disconnect(gelen.append)
