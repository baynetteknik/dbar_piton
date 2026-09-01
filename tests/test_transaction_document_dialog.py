"""Unit tests for TransactionDocumentDialog - YZ2 Task 17 features.

Covers:
- 17.1 Field dimensions (minimum widths for cari and document fields)
- 17.2 & 17.3 Items table context menu, sorting, and min 1 row constraint
- 17.4 Alt iskonto table context menu, sorting, min 1 row constraint
- 17.5 Initial single-row setup for both grids
- 17.6 Right EdgeTriggeredPanel (printing, summary, quick actions)
"""

import pytest
from PyQt6.QtWidgets import QApplication, QLineEdit
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import Base
from src.desktop.managers.theme_manager import ThemeManager
from src.desktop.ui.dialogs.transaction_document_dialog import TransactionDocumentDialog


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
    yield session
    session.close()


def test_task17_field_dimensions(qapp, db_session):
    """17.1 — Alan genişliklerinin doğrulanması."""
    dialog = TransactionDocumentDialog(db_session=db_session, company_id=1)

    assert dialog.txt_cari_kodu.minimumWidth() >= 120
    assert dialog.txt_vergi_daire.minimumWidth() >= 130
    assert dialog.txt_vergi_no.minimumWidth() >= 110
    assert dialog.txt_fatura_seri.minimumWidth() >= 70
    assert dialog.txt_fis_no.minimumWidth() >= 80


def test_task17_initial_single_row(qapp, db_session):
    """17.5 — Başlangıçta kalemler ve alt iskonto için 1 satır açılması."""
    dialog = TransactionDocumentDialog(db_session=db_session, company_id=1)

    assert dialog.table_items.rowCount() == 1
    assert dialog.table_alt_iskonto.rowCount() == 1


def test_task17_items_table_min_row_and_deletion(qapp, db_session):
    """17.3 — Hareket kalemleri tablosunda son satırın silinememesi, sıfırlanması."""
    dialog = TransactionDocumentDialog(db_session=db_session, company_id=1)

    # 1. Başlangıçta 1 satır var, veri dolduralım
    dialog.set_row_data(0, {
        "item_type": "Malzeme",
        "code": "TEST-01",
        "name": "Test Ürün",
        "qty": 3.0,
        "price": 100.0,
    })
    assert dialog.get_row_data(0)["code"] == "TEST-01"

    # Son satırı silmeye çalış -> silinmez, temizlenir
    dialog.remove_item_row(0)
    assert dialog.table_items.rowCount() == 1
    row_data = dialog.get_row_data(0)
    assert row_data["code"] == ""
    assert row_data["name"] == ""

    # 2 satır varken 1 satır silinebilmeli
    dialog.add_item_row(item_type="Malzeme", code="ITEM-2", name="Ürün 2")
    assert dialog.table_items.rowCount() == 2
    dialog.remove_item_row(1)
    assert dialog.table_items.rowCount() == 1


def test_task17_items_table_sorting(qapp, db_session):
    """17.2 — Hareket kalemleri tablosu sütuna göre sıralama."""
    dialog = TransactionDocumentDialog(db_session=db_session, company_id=1)

    dialog.set_row_data(0, {"name": "Zebra Kalem", "price": 50.0})
    dialog.add_item_row(item_type="Malzeme", name="Ahşap Cetvel", price=10.0)
    assert dialog.table_items.rowCount() == 2

    # İsim sütununa (col 4) göre artan sırala
    dialog._sort_items_table(col=4, ascending=True)
    assert dialog.get_row_data(0)["name"] == "Ahşap Cetvel"
    assert dialog.get_row_data(1)["name"] == "Zebra Kalem"

    # İsim sütununa göre azalan sırala
    dialog._sort_items_table(col=4, ascending=False)
    assert dialog.get_row_data(0)["name"] == "Zebra Kalem"
    assert dialog.get_row_data(1)["name"] == "Ahşap Cetvel"


def test_task17_alt_iskonto_features(qapp, db_session):
    """17.4 — Alt iskonto tablosu silinemezlik ve sıralama özellikleri."""
    dialog = TransactionDocumentDialog(db_session=db_session, company_id=1)

    # Başlangıçta 1 satır var
    assert dialog.table_alt_iskonto.rowCount() == 1

    # Son satırı silmeye çalış -> temizlenir (0.00)
    dialog.remove_alt_iskonto_row(0)
    assert dialog.table_alt_iskonto.rowCount() == 1
    w_val = dialog.table_alt_iskonto.cellWidget(0, 3)
    assert isinstance(w_val, QLineEdit)
    assert w_val.text() == "0.00"

    # 2. satır ekle ve sırala
    dialog.add_alt_iskonto_row(tur="İndirim", val=15.0)
    dialog.add_alt_iskonto_row(tur="İndirim", val=5.0)
    assert dialog.table_alt_iskonto.rowCount() == 3

    dialog._sort_alt_iskonto(ascending=True)
    val0 = float(dialog.table_alt_iskonto.cellWidget(0, 3).text().replace(",", "."))
    val2 = float(dialog.table_alt_iskonto.cellWidget(2, 3).text().replace(",", "."))
    assert val0 <= val2

    dialog._sort_alt_iskonto(ascending=False)
    val0_desc = float(dialog.table_alt_iskonto.cellWidget(0, 3).text().replace(",", "."))
    val2_desc = float(dialog.table_alt_iskonto.cellWidget(2, 3).text().replace(",", "."))
    assert val0_desc >= val2_desc


def test_task17_right_panel_and_summary(qapp, db_session):
    """17.6 — Sağ panel bileşenleri ve özet güncelleme."""
    dialog = TransactionDocumentDialog(db_session=db_session, company_id=1)

    # Sağ panelin varlığı
    assert hasattr(dialog, "right_panel")
    assert dialog.right_panel is not None

    # Özet labelları
    assert hasattr(dialog, "lbl_right_teklif_no")
    assert hasattr(dialog, "lbl_right_musteri")
    assert hasattr(dialog, "lbl_right_toplam")
    assert hasattr(dialog, "lbl_right_durum")

    # Satır ekleyip özetin güncellendiğini kontrol et
    dialog.set_row_data(0, {"name": "Test", "qty": 2.0, "price": 500.0, "vat": 20})
    dialog.calculate_totals()

    assert "1.200,00" in dialog.lbl_right_toplam.text() or "1,200.00" in dialog.lbl_right_toplam.text()
    assert dialog.lbl_right_musteri.text() != "👤 —"


def test_transaction_dialog_bottom_bar_and_theme(qapp, db_session):
    """Alt sabit bar butonları ve ThemeManager entegrasyonu."""
    dialog = TransactionDocumentDialog(db_session=db_session, company_id=1)

    assert hasattr(dialog, "btn_bottom_save")
    assert hasattr(dialog, "btn_bottom_cancel")
    assert hasattr(dialog, "btn_bottom_save_new")
    assert hasattr(dialog, "btn_bottom_save_print")

    theme_mgr = ThemeManager()
    assert dialog.table_items.verticalHeader().defaultSectionSize() == theme_mgr.row_height
