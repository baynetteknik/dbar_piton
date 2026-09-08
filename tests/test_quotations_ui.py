"""Unit tests for QuotationsWidget and OrdersWidget UI components."""

import pytest
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.ui.quotations import OrdersWidget, QuotationsWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance exists for GUI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def db_session():
    """Sets up an in-memory SQLite database session for UI testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_quotations_widget_initialization(qapp, db_session):
    """Test QuotationsWidget 3-panel initialization."""
    widget = QuotationsWidget(db_session=db_session)
    assert widget.quotation_type == "Quotation"
    assert widget.profile_key == "quotations"
    assert widget.filterable_table is not None
    assert widget.left_panel is not None
    assert widget.right_panel is not None


def test_new_document_screen_is_default(qapp):
    from src.desktop.ui import quotations as q
    assert q.USE_NEW_DOCUMENT_SCREEN is True


def test_bulk_print_sections_and_menu(qapp, db_session):
    """Sağ panelde TOPLU İŞLEMLER bölümü ve yazdırma metotları bulunmalı."""
    w = QuotationsWidget(db_session=db_session)
    assert w.sec_bulk is not None
    assert w.lbl_bulk.text() == "İşaretli belge yok"
    # yazdırma metotları
    for name in ("on_preview_clicked", "on_print_clicked",
                 "on_bulk_pdf_clicked", "on_bulk_email_clicked"):
        assert callable(getattr(w, name))
    # ExportWidget'te Yazdır + PDF butonları görünür
    assert "print" in w.export_widget.buttons_dict
    assert w.export_widget.btn_print.isVisibleTo(w.export_widget)


def test_bulk_label_updates_on_check(qapp, db_session):
    from src.core.models import Quotation
    from PyQt6.QtCore import Qt
    for num in ("TK-1", "TK-2"):
        db_session.add(Quotation(quotation_number=num, title=num,
                                 quotation_type="Quotation", grand_total=10,
                                 customer_name_free="X"))
    db_session.commit()
    w = QuotationsWidget(db_session=db_session)
    w.refresh_table()
    w.table_model.item(0, 0).setCheckState(Qt.CheckState.Checked)
    w.table_model.item(1, 0).setCheckState(Qt.CheckState.Checked)
    assert "2" in w.lbl_bulk.text()
    assert w.get_checked_ids()  # id listesi dolu


def test_orders_widget_initialization(qapp, db_session):
    """Test OrdersWidget 3-panel initialization."""
    widget = OrdersWidget(db_session=db_session)
    assert widget.quotation_type == "Order"
    assert widget.profile_key == "orders"
    assert widget.filterable_table is not None
    assert widget.left_panel is not None
    assert widget.right_panel is not None


def test_quotations_widget_shows_saved_quotation(qapp, db_session):
    """Test QuotationsWidget displays newly saved quotation from TransactionDocumentDialog."""
    from src.desktop.services.quotation_save_service import QuotationSaveService
    from src.desktop.ui.dialogs.transaction_document_dialog import (
        TransactionDocumentDialog,
    )

    # 1. Create a dialog and save a quotation
    dialog = TransactionDocumentDialog(
        db_session=db_session,
        initial_type_idx=5,  # TEKLİF: (1) VERİLEN SATIŞ TEKLİFİ
    )
    dialog.txt_top_doc_no.setText("TEK-2026-TEST")
    dialog.txt_cari_unvan.setText("ABC TEKNOLOJİ LTD.")
    dialog.set_row_data(0, {
        "item_type": "Malzeme",
        "code": "STK-001",
        "name": "Kablo",
        "qty": 5.0,
        "price": 200.0,
        "vat": 20,
    })
    dialog.calculate_totals()

    service = QuotationSaveService(db_session=db_session, company_id=1)
    res = service.save_from_dialog(dialog)
    assert res.success is True

    # 2. QuotationsWidget refresh_table should show the record
    widget = QuotationsWidget(db_session=db_session)
    widget.refresh_table()

    assert widget.table_model.rowCount() == 1
    # Col 2 is quotation_number, Col 3 is title, Col 4 is customer
    assert widget.table_model.item(0, 2).text() == "TEK-2026-TEST"
    assert "ABC TEKNOLOJİ" in widget.table_model.item(0, 4).text()


def test_column_filter_operators_on_grand_total(qapp, db_session):
    """Grid üstündeki kolon filtre kutusu, Genel Toplam sütununda >, >=, <, <=, =
    operatörlerini uygulamalı (önceden filter_changed sinyali hiçbir yere bağlı
    değildi ve bu kutular hiçbir etki yapmıyordu)."""
    from src.core.models import Quotation

    for num, total in [("TEK-001", 50), ("TEK-002", 150), ("TEK-003", 1000),
                        ("TEK-004", 3000), ("TEK-005", 5000)]:
        db_session.add(Quotation(
            quotation_number=num, title=f"Kalem {num}", quotation_type="Quotation",
            grand_total=total, customer_name_free="Müşteri X",
        ))
    db_session.commit()

    widget = QuotationsWidget(db_session=db_session)
    widget.refresh_table()
    assert widget.table_model.rowCount() == 5

    gt_col = next(c for c, (_l, f) in widget.headers_dict.items() if f == "grand_total")
    filter_box = widget.filterable_table.filter_widgets[gt_col]

    filter_box.setText(">100")
    assert widget.table_model.rowCount() == 4  # 150, 1000, 3000, 5000

    filter_box.setText("=1000")
    assert widget.table_model.rowCount() == 1
    from PyQt6.QtCore import Qt
    assert widget.table_model.item(0, gt_col).data(Qt.ItemDataRole.UserRole) == 1000.0

    filter_box.setText("<=3000")
    assert widget.table_model.rowCount() == 4  # 50, 150, 1000, 3000

    filter_box.clear()
    assert widget.table_model.rowCount() == 5

