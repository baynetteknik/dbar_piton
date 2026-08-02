from sqlalchemy.orm import Session

from src.core.models import Customer
from src.core.repository import SqliteCustomerRepository


def test_sqlite_customer_repository(db_session: Session) -> None:
    # 1. Add test data
    cust1 = Customer(
        fullname="Ahmet Yilmaz",
        customer_code="C001",
        group_name="ALICI",
        status=1,
        marketplace="local",
    )
    cust2 = Customer(
        fullname="Mehmet Demir",
        customer_code="C002",
        group_name="SATICI",
        status=0,
        marketplace="dolibarr",
    )
    db_session.add(cust1)
    db_session.add(cust2)
    db_session.commit()

    # 2. Instantiate repository
    repo = SqliteCustomerRepository(db_session, company_id=1)

    # 3. Fetch without filters
    customers, total = repo.get_page_data(
        filters={},
        sort_by=None,
        sort_order="asc",
        page=1,
        per_page=10,
    )
    assert total == 2
    assert len(customers) == 2
    assert customers[0].fullname == "Mehmet Demir"

    # 4. Fetch with filter (fullname)
    customers_filtered, total_filtered = repo.get_page_data(
        filters={"fullname": "Ahmet"},
        sort_by=None,
        sort_order="asc",
        page=1,
        per_page=10,
    )
    assert total_filtered == 1
    assert customers_filtered[0].fullname == "Ahmet Yilmaz"

    # 5. Add custom details to احمد or verify default fields
    cust1.tax_office = "Kadikoy"
    cust1.address = "Bagdat Cad."
    cust1.special_code_2 = "SP2"
    db_session.commit()

    # Test tax_office filter
    res, tot = repo.get_page_data(filters={"tax_office": "Kadikoy"}, sort_by=None, sort_order="asc", page=1, per_page=10)
    assert tot == 1
    assert res[0].fullname == "Ahmet Yilmaz"

    # Test address filter
    res, tot = repo.get_page_data(filters={"address": "Bagdat"}, sort_by=None, sort_order="asc", page=1, per_page=10)
    assert tot == 1

    # Test special_code_2 filter
    res, tot = repo.get_page_data(filters={"special_code_2": "SP2"}, sort_by=None, sort_order="asc", page=1, per_page=10)
    assert tot == 1
