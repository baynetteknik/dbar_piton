import os
import pytest
import pandas as pd
from sqlalchemy.orm import Session

from src.core.importer import (
    CUSTOMER_FIELDS, PRODUCT_FIELDS, find_best_match,
    generate_template_file, export_to_excel_file, import_excel_data
)
from src.core.models import Customer, Product, ChangeLog


def test_find_best_match():
    # Tam eşleşme testi
    assert find_best_match("Cari Kodu", CUSTOMER_FIELDS) == "customer_code"
    # Alias eşleşme testi
    assert find_best_match("v.d.", CUSTOMER_FIELDS) == "tax_office"
    # Fuzzy eşleşme testi (%70+ benzerlik)
    assert find_best_match("Vergi Numarasi", CUSTOMER_FIELDS) == "tax_number"
    assert find_best_match("urun kodu", PRODUCT_FIELDS) == "sku"
    # Eşleşmeme testi
    assert find_best_match("alakasiz baslik", CUSTOMER_FIELDS) is None


def test_generate_template_and_export(tmp_path):
    temp_excel = tmp_path / "test_template.xlsx"
    generate_template_file(str(temp_excel), CUSTOMER_FIELDS)
    assert os.path.exists(temp_excel)
    
    # Başlıkları kontrol et
    df = pd.read_excel(temp_excel, engine="openpyxl")
    headers = list(df.columns)
    assert "Cari Kodu" in headers
    assert "Ticari Unvanı" in headers


def test_import_customers(db_session, tmp_path):
    # Test verisi oluştur
    data = {
        "Cari Kodu": ["C001", "C002"],
        "Ticari Unvanı": ["Ahmet A.Ş.", "Mehmet Ltd."],
        "Vergi Numarası": ["1234567890", "9876543210"],
        "E-Posta": ["ahmet@test.com", "mehmet@test.com"]
    }
    df = pd.DataFrame(data)
    excel_file = tmp_path / "customers.xlsx"
    df.to_excel(excel_file, index=False, engine="openpyxl")
    
    field_mapping = {
        "customer_code": "A",
        "fullname": "B",
        "tax_number": "C",
        "email": "D"
    }
    
    # 1. İlk defa içeri aktarma (Insert testi)
    added, updated, skipped = import_excel_data(
        file_path=str(excel_file),
        fields_dict=CUSTOMER_FIELDS,
        field_mapping=field_mapping,
        db=db_session,
        entity_type="customer",
        conflict_exist="skip",
        conflict_not_exist="insert",
        site_id=1
    )
    
    assert added == 2
    assert updated == 0
    assert skipped == 0
    
    # Veritabanı durumunu doğrula
    customers = db_session.query(Customer).all()
    assert len(customers) == 2
    assert customers[0].fullname == "Ahmet A.Ş."
    assert customers[0].customer_code == "C001"
    
    # ChangeLog durumunu doğrula (PushEngine için PENDING_PUSH kayıtları oluşmalı)
    logs = db_session.query(ChangeLog).all()
    assert len(logs) == 2
    assert logs[0].entity_type == "customer"
    assert logs[0].action == "create"
    assert logs[0].status == "PENDING_PUSH"
    
    # 2. Çakışma Durumu (Update testi)
    # Yeni bir excel oluştur, Ahmet A.Ş.'nin ismini ve e-postasını değiştirelim
    data_update = {
        "Cari Kodu": ["C001", "C003"],
        "Ticari Unvanı": ["Ahmet A.Ş. Yeni Ünvan", "Zeynep A.Ş."],
        "Vergi Numarası": ["1234567890", "5555555555"],
        "E-Posta": ["ahmet_yeni@test.com", "zeynep@test.com"]
    }
    df_update = pd.DataFrame(data_update)
    excel_file_update = tmp_path / "customers_update.xlsx"
    df_update.to_excel(excel_file_update, index=False, engine="openpyxl")
    
    added_2, updated_2, skipped_2 = import_excel_data(
        file_path=str(excel_file_update),
        fields_dict=CUSTOMER_FIELDS,
        field_mapping=field_mapping,
        db=db_session,
        entity_type="customer",
        conflict_exist="update",
        conflict_not_exist="insert",
        site_id=1
    )
    
    # C001 güncellendi, C003 yeni eklendi
    assert added_2 == 1
    assert updated_2 == 1
    assert skipped_2 == 0
    
    updated_cust = db_session.query(Customer).filter(Customer.customer_code == "C001").first()
    assert updated_cust.fullname == "Ahmet A.Ş. Yeni Ünvan"
    assert updated_cust.email == "ahmet_yeni@test.com"


def test_import_products(db_session, tmp_path):
    # Test verisi oluştur
    data = {
        "Ürün Kodu": ["P001", "P002"],
        "Ürün Adı": ["Klavye", "Mouse"],
        "Satış Fiyatı": [150.0, 80.0],
        "Stok Miktarı": [10, 20]
    }
    df = pd.DataFrame(data)
    excel_file = tmp_path / "products.xlsx"
    df.to_excel(excel_file, index=False, engine="openpyxl")
    
    field_mapping = {
        "sku": "A",
        "name": "B",
        "price": "C",
        "stock": "D"
    }
    
    added, updated, skipped = import_excel_data(
        file_path=str(excel_file),
        fields_dict=PRODUCT_FIELDS,
        field_mapping=field_mapping,
        db=db_session,
        entity_type="product",
        conflict_exist="skip",
        conflict_not_exist="insert",
        site_id=1
    )
    
    assert added == 2
    assert updated == 0
    assert skipped == 0
    
    products = db_session.query(Product).all()
    assert len(products) == 2
    assert products[0].name == "Klavye"
    assert products[0].price == 150.0
    assert products[0].site_id == 1
