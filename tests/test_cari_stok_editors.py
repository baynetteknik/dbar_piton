"""Cari (Customer) + Stok (Product) servisleri, editörleri ve liste ekranları."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Customer, Product, User
from src.desktop.managers.permission_manager import PermissionManager
from src.desktop.services.customer_service import CustomerService
from src.desktop.services.product_service import ProductService
from src.desktop.services.role_service import RoleService
from src.desktop.services.user_service import hash_password


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


@pytest.fixture(autouse=True)
def _no_modal(monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    for m in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, m, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    # her testte yetki yöneticisini admin'e sabitle
    PermissionManager().set_role("ADMIN")


# ---- CustomerService ----
def test_customer_save_and_list(db):
    svc = CustomerService(db)
    r = svc.save({"fullname": "ACME LTD", "customer_code": "M001",
                  "tax_number": "123", "city": "ANKARA", "is_active": True,
                  "group_name": "Müşteri"})
    assert r.success
    c = svc.get(r.customer_id)
    assert c.marketplace == "local" and c.status == 1
    assert svc.to_dict(c)["city"] == "ANKARA"
    assert len(svc.list_customers(search="acme")) == 1
    assert len(svc.list_customers(search="yok")) == 0


def test_customer_requires_name_and_unique_code(db):
    svc = CustomerService(db)
    assert svc.save({"fullname": ""}).success is False
    svc.save({"fullname": "A", "customer_code": "X"})
    assert svc.save({"fullname": "B", "customer_code": "X"}).success is False


def test_customer_passive_and_soft_delete(db):
    svc = CustomerService(db)
    cid = svc.save({"fullname": "A"}).customer_id
    svc.set_passive(cid, True)
    assert svc.get(cid).status == 0
    assert svc.delete(cid) is True
    assert svc.list_customers() == []


# ---- ProductService ----
def test_product_save_price_and_legacy_sync(db):
    svc = ProductService(db)
    r = svc.save({"sku": "STK-01", "name": "Kamera", "base_price": 1250.5,
                  "vat_rate": 20, "stock": 15, "is_active": True})
    assert r.success
    p = svc.get(r.product_id)
    assert p.base_price == pytest.approx(1250.5)
    assert p.price == pytest.approx(1250.5)  # legacy alan senkron


def test_product_requires_sku_name_and_unique(db):
    svc = ProductService(db)
    assert svc.save({"sku": "", "name": "x"}).success is False
    assert svc.save({"sku": "A", "name": ""}).success is False
    svc.save({"sku": "A", "name": "First"})
    assert svc.save({"sku": "A", "name": "Second"}).success is False


# ---- Editörler ----
def test_cari_editor_config_roundtrip(qapp, db):
    from src.desktop.ui.screens.cari_editor import CARI_TABS
    from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
    ed = DefinitionEditorScreen(title="Cari", tabs=CARI_TABS)
    ed.set_data({"fullname": "ACME", "customer_code": "M1", "is_active": True,
                 "group_name": "Tedarikçi", "city": "İZMİR"}, is_edit=True)
    assert ed._widgets["customer_code"].isEnabled() is False
    out = ed.collect()
    assert out["fullname"] == "ACME" and out["city"] == "İZMİR"


def test_stok_editor_number_fields(qapp, db):
    from src.desktop.ui.screens.stok_kart_editor import STOK_TABS
    from src.desktop.ui.screens.definition_editor_screen import DefinitionEditorScreen
    ed = DefinitionEditorScreen(title="Stok", tabs=STOK_TABS)
    ed.set_data({"sku": "S1", "name": "X", "base_price": 99.9,
                 "vat_rate": 10, "stock": 7}, is_edit=True)
    out = ed.collect()
    assert isinstance(out["base_price"], float) and out["base_price"] == pytest.approx(99.9)
    assert out["vat_rate"] == 10 and out["stock"] == 7


# ---- Liste ekranları + yetki ----
def test_cari_list_screen_loads_and_gates(qapp, db):
    from src.desktop.ui.cari_list_screen import CariListScreen
    db.add(Customer(fullname="ACME", marketplace="local", status=1))
    db.commit()
    w = CariListScreen(db_session=db, company_id=1)
    w.refresh_table()
    assert w.table_model.rowCount() == 1
    assert w.btn_new.isHidden() is False  # ADMIN

    # sadece görüntüleme yetkili
    RoleService(db).save({"name": "CariBakıcı", "permissions": ["cari.view"]})
    role = RoleService(db).get_by_name("CariBakıcı")
    u = User(username="cv", password_hash=hash_password("1"), role="user", role_id=role.id)
    db.add(u)
    db.commit()
    PermissionManager().load_from_db(db)
    PermissionManager().set_current_user(u)
    w2 = CariListScreen(db_session=db, company_id=1)
    assert w2.btn_new.isHidden() is True
    assert w2.btn_delete.isHidden() is True
    assert w2.btn_excel.isHidden() is False  # cari.view var


def test_stok_list_screen_loads_and_gates(qapp, db):
    from src.desktop.ui.stok_list_screen import StokListScreen
    db.add(Product(sku="STK-01", name="Kamera", is_active=True))
    db.commit()
    w = StokListScreen(db_session=db, company_id=1)
    w.refresh_table()
    assert w.table_model.rowCount() >= 1
    assert w.action_bar.btn_new.isHidden() is False

    RoleService(db).save({"name": "StokBakıcı", "permissions": ["stok.view"]})
    role = RoleService(db).get_by_name("StokBakıcı")
    u = User(username="sv", password_hash=hash_password("1"), role="user", role_id=role.id)
    db.add(u)
    db.commit()
    PermissionManager().load_from_db(db)
    PermissionManager().set_current_user(u)
    w2 = StokListScreen(db_session=db, company_id=1)
    assert w2.action_bar.btn_new.isHidden() is True
    assert w2.action_bar.btn_delete.isHidden() is True
