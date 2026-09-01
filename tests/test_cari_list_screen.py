"""
Unit tests for CariListScreen with ToyaUI widgets (ActionBarWidget, FilterWidget, PaginationWidget, ExportWidget).
"""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base, Customer
from src.desktop.ui.cari_list_screen import CariListScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()


    # Örnek cariler ekle
    c1 = Customer(
        customer_code="CAR001",
        fullname="ABC Ltd. Şti.",
        marketplace="LOCAL",
        group_name="Müşteriler",
        status=1,
        is_deleted=False,
    )
    c2 = Customer(
        customer_code="CAR002",
        fullname="XYZ Tedarik A.Ş.",
        marketplace="LOCAL",
        group_name="Tedarikçiler",
        status=0,
        is_deleted=False,
    )
    session.add_all([c1, c2])
    session.commit()

    yield session
    session.close()


def test_cari_list_screen_init(qapp, db_session):
    screen = CariListScreen(db_session=db_session, company_id=1)
    screen.show()

    # Widget'ların varlığını ve entegrasyonunu kontrol et
    assert hasattr(screen, "action_bar")
    assert hasattr(screen, "filter_widget")
    assert hasattr(screen, "pagination_widget")
    assert hasattr(screen, "export_widget")

    # Tablo satır sayısı ve sayfalama
    assert screen.table_model.rowCount() == 2
    assert screen.pagination_widget.current_page() == 1


def test_cari_list_screen_filtering(qapp, db_session):
    screen = CariListScreen(db_session=db_session, company_id=1)

    # 1. Arama filtresi
    screen.search_box.setText("ABC")
    assert screen.table_model.rowCount() == 1

    # 2. Durum filtresi
    screen.clear_filters()
    assert screen.table_model.rowCount() == 2

    screen.cmb_status.setCurrentText("Sadece Aktifler")
    assert screen.table_model.rowCount() == 1

    screen.cmb_status.setCurrentText("Sadece Pasifler")
    assert screen.table_model.rowCount() == 1

    # 3. Grup filtresi
    screen.clear_filters()
    assert screen.table_model.rowCount() == 2

    screen.cmb_group.setCurrentText("Müşteriler")
    assert screen.table_model.rowCount() == 1

    screen.cmb_group.setCurrentText("Tedarikçiler")
    assert screen.table_model.rowCount() == 1

    screen.clear_filters()
    assert screen.table_model.rowCount() == 2


def test_cari_list_screen_actions(qapp, db_session):
    screen = CariListScreen(db_session=db_session, company_id=1)

    # 1. satırı seç
    screen.table_view.selectRow(0)
    assert screen.get_selected_id() is not None

    # Pasife al
    c = screen.get_selected_customer()
    assert c is not None
    initial_status = c.status
    screen.on_passive_clicked()
    assert c.status != initial_status
