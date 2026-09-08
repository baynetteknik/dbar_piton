"""Company modeli + CompanyService + Firma editör/liste widget testleri."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Company
from src.desktop.services.company_service import CompanyService


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_company_service_save_and_list(db):
    svc = CompanyService(db)
    res = svc.save({
        "code": "000", "short_name": "BAYNET",
        "title": "BAYNET BİLİŞİM LTD. ŞTİ.", "tax_number": "1550442479",
        "city": "ANKARA", "e_invoice_enabled": True,
        "bank_accounts": [{"banka": "Garanti", "iban": "TR00", "para_birimi": "TRY"}],
    })
    assert res.success and res.company_id
    companies = svc.list_companies()
    assert len(companies) == 1
    d = svc.to_dict(companies[0])
    assert d["short_name"] == "BAYNET"
    assert d["bank_accounts"][0]["banka"] == "Garanti"


def test_company_service_requires_code_and_name(db):
    svc = CompanyService(db)
    assert svc.save({"code": "", "short_name": "X"}).success is False
    assert svc.save({"code": "1", "short_name": ""}).success is False


def test_company_service_duplicate_code_rejected(db):
    svc = CompanyService(db)
    assert svc.save({"code": "A", "short_name": "First"}).success is True
    r = svc.save({"code": "A", "short_name": "Second"})
    assert r.success is False and "zaten" in r.error


def test_company_service_update_and_soft_delete(db):
    svc = CompanyService(db)
    cid = svc.save({"code": "A", "short_name": "First"}).company_id
    r = svc.save({"code": "A", "short_name": "Guncel"}, company_id=cid)
    assert r.success
    assert svc.get(cid).short_name == "Guncel"
    assert svc.delete(cid) is True
    assert svc.list_companies() == []


def test_firma_editor_loads_and_collects(qapp, db):
    from src.desktop.ui.screens.firma_editor import FIRMA_TABS
    from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen

    ed = DefinitionEditorScreen(title="Firma Detayı", tabs=FIRMA_TABS)
    ed.set_data({
        "code": "000", "short_name": "BAYNET", "company_type": "Tüzel",
        "e_invoice_enabled": True, "default_vat_rate": 20,
        "bank_accounts": [{"banka": "Garanti", "iban": "TR1"}],
    }, is_edit=True)
    # code alanı düzenleme modunda kilitli
    assert ed._widgets["code"].isEnabled() is False
    out = ed.collect()
    assert out["short_name"] == "BAYNET"
    assert out["e_invoice_enabled"] is True
    assert out["bank_accounts"][0]["banka"] == "Garanti"


def test_firma_editor_validates_required(qapp):
    from src.desktop.ui.screens.firma_editor import FIRMA_TABS
    from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
    ed = DefinitionEditorScreen(title="X", tabs=FIRMA_TABS)
    ed.set_data({"code": "", "short_name": ""})
    seen = []
    ed.saved.connect(seen.append)
    ed._on_save()
    assert not seen  # zorunlu alan boş -> kaydetme sinyali gitmez
    assert "zorunlu" in ed.lbl_status.text()


def test_firma_list_widget_embedded(qapp, db):
    from src.desktop.ui.screens.firma_list_widget import FirmaListWidget
    db.add(Company(code="000", short_name="BAYNET", city="ANKARA"))
    db.add(Company(code="001", short_name="TOYA", city="İSTANBUL"))
    db.commit()
    w = FirmaListWidget(db_session=db, embedded=True)
    assert w.embedded is True
    assert w.left_panel.isVisibleTo(w) is False
    assert w.table_model.rowCount() == 2
    w.apply_quick_search("toya")
    assert w.table_model.rowCount() == 1
