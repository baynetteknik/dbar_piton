"""CariEkstreWidget — cari belge listesi + bakiye/risk özeti."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Customer, Quotation
from src.desktop.ui.widgets.cari_ekstre_widget import CariEkstreWidget


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_lists_customer_documents_and_balance(qapp, db):
    c = Customer(fullname="ACME", marketplace="local", customer_code="C1",
                 balance=1500.0, risk_limit=10000.0)
    db.add(c)
    db.commit()
    db.add_all([
        Quotation(quotation_number="TEK-1", customer_id=c.id, quotation_type="Quotation",
                  grand_total=1200.0, status="draft", company_id=1),
        Quotation(quotation_number="FTR-1", customer_id=c.id, quotation_type="Invoice",
                  grand_total=300.0, status="approved", company_id=1),
    ])
    db.add(Quotation(quotation_number="X", customer_id=None, quotation_type="Quotation",
                     grand_total=9.0, company_id=1))
    db.commit()

    w = CariEkstreWidget(db_session=db)
    w.set_customer(c.id)
    assert w.table.rowCount() == 2                      # yalnız bu carinin belgeleri
    assert "1.500,00" in w.lbl_balance.text()
    assert "Borç" in w.lbl_balance.text()
    assert "10.000,00" in w.lbl_risk.text()


def test_empty_customer(qapp, db):
    c = Customer(fullname="Bos", marketplace="local")
    db.add(c)
    db.commit()
    w = CariEkstreWidget(db_session=db)
    w.set_customer(c.id)
    assert w.table.rowCount() == 0
    assert not w.lbl_empty.isHidden()
