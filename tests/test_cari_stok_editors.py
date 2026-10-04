"""Cari (Customer) + Stok (Product) servisleri, editörleri ve liste ekranları."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Customer, Gorev, Product, User
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


# ---- Standart kart (tpl.card.001) ----
def test_cari_editor_standard_header_and_finance_fields(qapp, db):
    from src.core.models import PaymentPlan
    from src.desktop.ui.screens.cari_editor import CariEditorDialog
    db.add(PaymentPlan(code="P30", description="30 Gün Vadeli"))
    db.commit()

    dlg = CariEditorDialog(db_session=db)
    assert dlg.editor.tabw.count() == 3             # Stok Kartı ile aynı çok kolonlu düzen
    dlg.editor._widgets["customer_code"].setText("CR-9")
    dlg.editor._widgets["fullname"].setPlainText("ACME LTD")
    dlg.editor._widgets["risk_limit"].setValue(5000)
    dlg.editor._widgets["payment_plan_name"].setCurrentText("30 Gün Vadeli")
    assert "CR-9" in dlg.editor.lbl_record.text()
    assert dlg.editor.cmb_header_status.currentText() == "Aktif"  # Stok'taki gibi tekrarsız

    dlg.editor._on_save()
    c = db.query(Customer).filter_by(customer_code="CR-9").first()
    assert c.risk_limit == 5000 and c.payment_plan_id is not None
    assert c.balance == 0.0                        # karttan yazılmaz


def test_cari_editor_loads_payment_plan_name(qapp, db):
    from src.core.models import PaymentPlan
    from src.desktop.ui.screens.cari_editor import CariEditorDialog
    pp = PaymentPlan(code="P60", description="60 Gün")
    db.add(pp)
    db.commit()
    c = Customer(fullname="X", marketplace="local", customer_code="C1",
                 payment_plan_id=pp.id)
    db.add(c)
    db.commit()

    dlg = CariEditorDialog(db_session=db, customer_id=c.id)
    assert dlg.editor._widgets["payment_plan_name"].currentText() == "60 Gün"


def test_stok_editor_standard(qapp, db):
    from src.desktop.ui.screens.stok_kart_editor import StokKartEditorDialog
    p = Product(sku="STK-Z", name="Kamera", stock=42)
    db.add(p)
    db.commit()

    dlg = StokKartEditorDialog(db_session=db, product_id=p.id)
    assert dlg.editor.tabw.count() == 5              # yeni çok kolonlu düzen
    assert dlg.editor._nav_sidebar is True           # sol nav (İşlemler/Raporlar) var
    assert dlg.editor._summary_widget is not None
    assert "stock" not in dlg.editor._widgets        # Mevcut Stok formdan kaldırıldı
    assert "is_active" not in dlg.editor._widgets    # Aktif yalnızca header'da (tekrar yok)
    assert dlg.editor.cmb_header_status.currentText() == "Aktif"
    assert dlg.summary.lbl_kpi_value.text() == "42"  # mevcut stok özet panelinden okunur

    dlg.editor._widgets["product_type"].setCurrentText("Hizmet")
    dlg.editor._widgets["base_price"].setValue(1850)
    dlg.editor._refresh_summary()
    assert "STK-Z" in dlg.editor.lbl_record.text() and "Kamera" in dlg.editor.lbl_record.text()
    assert dlg.summary.lbl_kpi_value.text() == "42"  # form alanı olmadığı için değişmez

    dlg.editor._on_save()
    assert p.product_type == "Hizmet" and p.currency == "TRY"
    assert p.base_price == 1850 and p.stock == 42    # stok karttan değil hareketlerden yönetilir


def test_stok_editor_hizmet_tanimlari_alanlari_kaydedip_geri_yukler(qapp, db):
    """Hizmet Tanımları (2026-09-29): stok takibi bayrağı + hesap kodları + KDV tevkifatı + KKEG + fatura
    açıklama şablonu — yeni kart varsayılan olarak stok takip eder (Ticari Mal), kullanıcı kapatabilir."""
    from src.desktop.ui.screens.stok_kart_editor import StokKartEditorDialog
    p = Product(sku="HZ-DAN", name="Danışmanlık")
    db.add(p)
    db.commit()

    dlg = StokKartEditorDialog(db_session=db, product_id=p.id)
    assert dlg.editor._widgets["tracks_stock"].isChecked() is True   # varsayılan: stok takip edilir

    dlg.editor._widgets["product_type"].setCurrentText("Hizmet")
    dlg.editor._widgets["tracks_stock"].setChecked(False)
    dlg.editor._widgets["sales_account_code"].setText("600")
    dlg.editor._widgets["purchase_account_code"].setText("770")
    dlg.editor._widgets["nondeductible_expense"].setChecked(True)
    dlg.editor._widgets["invoice_description_template"].setText("Aylık danışmanlık hizmet bedeli")
    dlg.editor._on_save()

    assert p.tracks_stock is False
    assert (p.sales_account_code, p.purchase_account_code) == ("600", "770")
    assert p.nondeductible_expense is True
    assert p.invoice_description_template == "Aylık danışmanlık hizmet bedeli"

    dlg2 = StokKartEditorDialog(db_session=db, product_id=p.id)
    assert dlg2.editor._widgets["tracks_stock"].isChecked() is False
    assert dlg2.editor._widgets["sales_account_code"].text() == "600"


def test_masraf_karti_duzenli_odeme_isaretlenince_gorevler_modulunde_hatirlatma_acar(db):
    """Masraf Tanımları (2026-09-30): 'Düzenli Ödenen' işaretli bir Masraf kartı kaydedilince Görevler
    modülünde aylık tekrarlı bir hatırlatma görevi otomatik açılır; tekrar kaydetmek yeni görev üretmez
    (idempotent), bayrak kapatılınca açık hatırlatma gizlenir (silme=gizleme kuralı, 03.09 vb.)."""
    svc = ProductService(db)
    r = svc.save({"sku": "MSR-1", "name": "Ofis Kirası", "product_type": "Masraf",
                  "is_recurring_expense": True, "recurring_due_day": 5,
                  "recurring_reminder_days_before": 3})
    assert r.success

    gorevler = db.query(Gorev).filter_by(ilgili_tur="masraf", ilgili_id=r.product_id, is_deleted=False).all()
    assert len(gorevler) == 1
    assert gorevler[0].tur == "hatirlatma"
    assert gorevler[0].tekrar == "aylik"
    assert "Ofis Kirası" in gorevler[0].baslik
    ilk_baslangic = gorevler[0].baslangic

    # Aynı kart tekrar kaydedilince ikinci bir görev AÇILMAZ, var olan güncellenir.
    svc.save({"sku": "MSR-1", "name": "Ofis Kirası", "product_type": "Masraf",
              "is_recurring_expense": True, "recurring_due_day": 20,
              "recurring_reminder_days_before": 3}, product_id=r.product_id)
    gorevler2 = db.query(Gorev).filter_by(ilgili_tur="masraf", ilgili_id=r.product_id, is_deleted=False).all()
    assert len(gorevler2) == 1
    assert gorevler2[0].baslangic != ilk_baslangic  # vade günü değişti, hatırlatma zamanı da değişti

    # Bayrak kapatılınca açık hatırlatma gizlenir.
    svc.save({"sku": "MSR-1", "name": "Ofis Kirası", "product_type": "Masraf",
              "is_recurring_expense": False}, product_id=r.product_id)
    acik = db.query(Gorev).filter_by(ilgili_tur="masraf", ilgili_id=r.product_id, is_deleted=False).all()
    assert acik == []


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
