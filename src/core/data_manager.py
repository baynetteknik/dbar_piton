from sqlalchemy.orm import Session

from src.adapters.dolibarr.dolibarr_adapter import DolibarrAdapter
from src.adapters.dolibarr.dolibarr_client import DolibarrClient
from src.adapters.mappers import DolibarrMapper
from src.core.models import Customer, Product, Site
from src.core.security.keyring_store import get_api_key


class DataManager:
    """Orchestrates data operations by routing them either to local SQLite or direct Dolibarr API."""

    @staticmethod
    def get_company_mode(db: Session, company_id: int) -> str:
        """Reads the working mode of the selected company/site."""
        company = db.query(Site).filter(Site.id == company_id).first()
        return company.working_mode if company else "local_master"

    @staticmethod
    def _get_adapter(db: Session, company_id: int) -> DolibarrAdapter:
        """Instantiates client and adapter for direct online connections."""
        company = db.query(Site).filter(Site.id == company_id).first()
        if not company:
            raise ValueError(f"Company ID {company_id} not found.")

        api_key = get_api_key(company.api_key_account)
        if not api_key:
            raise ValueError(f"API key not found for account: {company.api_key_account}")

        client = DolibarrClient(base_url=company.url, api_key=api_key)
        return DolibarrAdapter(site_id=company_id, client=client)

    @classmethod
    def get_customers(
        cls,
        db: Session,
        company_id: int,
        page: int = 1,
        per_page: int = 25,
        search_text: str = "",
        group_filter: str = "Tümü",
        status_filter: int = -1,
        marketplace_filter: str = "Tümü",
        special_code_1: str = "",
    ) -> tuple[list[Customer], int]:
        """Fetches customers from SQLite or directly from Dolibarr API based on company mode."""
        mode = cls.get_company_mode(db, company_id)

        if mode == "local_master":
            # 1. Query from SQLite
            query = db.query(Customer).filter(Customer.is_deleted == False)

            if search_text:
                query = query.filter(
                    (Customer.fullname.like(f"%{search_text}%")) |
                    (Customer.customer_code.like(f"%{search_text}%")) |
                    (Customer.tax_number.like(f"%{search_text}%")) |
                    (Customer.email.like(f"%{search_text}%")),
                )

            if group_filter != "Tümü":
                query = query.filter(Customer.group_name == group_filter)

            if status_filter != -1:
                query = query.filter(Customer.status == status_filter)

            if marketplace_filter != "Tümü":
                if marketplace_filter == "LOCAL":
                    query = query.filter((Customer.marketplace == "local") | (Customer.marketplace.is_(None)))
                else:
                    query = query.filter(Customer.marketplace == marketplace_filter.lower())

            if special_code_1:
                query = query.filter(Customer.special_code_1.like(f"%{special_code_1}%"))

            total_records = query.count()
            offset = (page - 1) * per_page
            records = query.limit(per_page).offset(offset).all()
            return records, total_records

        else:
            # 2. Fetch directly from Dolibarr API
            adapter = cls._get_adapter(db, company_id)
            # Dolibarr API does not natively support complex multi-criteria local-like searching,
            # so we fetch and map them to ORM objects.
            raw_customers = adapter.fetch_customers(page=page, per_page=per_page)
            customers = [DolibarrMapper.to_customer_orm(company_id, item) for item in raw_customers]

            # In direct API mode, total records can be estimated by looking at the page count
            # since SQL count(*) on remote API is expensive or unsupported via standard REST endpoints.
            if len(raw_customers) < per_page:
                total_records = (page - 1) * per_page + len(raw_customers)
            else:
                total_records = page * per_page + 1 # Dummy indicator there might be more pages

            return customers, total_records

    @classmethod
    def get_products(
        cls,
        db: Session,
        company_id: int,
        page: int = 1,
        per_page: int = 50,
        search_text: str = "",
        category_id: int = -1,
    ) -> tuple[list[Product], int]:
        """Fetches products from SQLite or directly from Dolibarr API based on company mode."""
        mode = cls.get_company_mode(db, company_id)

        if mode == "local_master":
            query = db.query(Product).filter(Product.is_deleted == False)

            if search_text:
                query = query.filter(
                    (Product.name.like(f"%{search_text}%")) |
                    (Product.sku.like(f"%{search_text}%")),
                )

            if category_id != -1:
                query = query.filter(Product.category_id == category_id)

            total_records = query.count()
            offset = (page - 1) * per_page
            records = query.limit(per_page).offset(offset).all()
            return records, total_records

        else:
            # Fetch directly from Dolibarr API
            adapter = cls._get_adapter(db, company_id)
            raw_products = adapter.fetch_products(page=page, per_page=per_page)
            products = [DolibarrMapper.to_product_orm(company_id, item) for item in raw_products]

            if len(raw_products) < per_page:
                total_records = (page - 1) * per_page + len(raw_products)
            else:
                total_records = page * per_page + 1

            return products, total_records

    @classmethod
    def save_customer(cls, db: Session, company_id: int, customer: Customer) -> bool:
        """Saves a customer to SQLite or pushes it directly to Dolibarr based on company mode."""
        mode = cls.get_company_mode(db, company_id)

        if mode == "local_master":
            # Add or merge in SQLite local DB session
            db.add(customer)
            db.commit()
            return True
        else:
            # Push directly to Dolibarr API without writing locally
            adapter = cls._get_adapter(db, company_id)
            
            # Map Customer ORM to Dolibarr DTO format
            customer_data = {
                "nom": customer.fullname,
                "name": customer.fullname,
                "email": customer.email,
                "phone": customer.phone,
                "address": customer.address,
                "tva_intra": customer.tax_number,
                "code_client": customer.customer_code,
                "array_options": {
                    "options_special_code_1": customer.special_code_1,
                    "options_special_code_2": customer.special_code_2,
                    "options_special_code_3": customer.special_code_3,
                },
            }
            if customer.remote_id:
                customer_data["id"] = customer.remote_id

            res = adapter.push_customer(customer_data)
            return bool(res.get("id"))

    @classmethod
    def save_product(cls, db: Session, company_id: int, product: Product) -> bool:
        """Saves a product to SQLite or pushes it directly to Dolibarr based on company mode."""
        mode = cls.get_company_mode(db, company_id)

        if mode == "local_master":
            db.add(product)
            db.commit()
            return True
        else:
            adapter = cls._get_adapter(db, company_id)
            product_data = {
                "ref": product.sku,
                "label": product.name,
                "description": product.description,
                "price": product.base_price,
            }
            if product.remote_id:
                product_data["id"] = product.remote_id

            res = adapter.push_product(product_data)
            return bool(res.get("id"))

    @classmethod
    def delete_customer(cls, db: Session, company_id: int, customer_id: int, remote_id: str | None = None) -> bool:
        """Deletes a customer locally or remotely depending on company mode."""
        mode = cls.get_company_mode(db, company_id)

        if mode == "local_master":
            cust = db.query(Customer).filter(Customer.id == customer_id).first()
            if cust:
                cust.is_deleted = True
                db.commit()
                return True
            return False
        else:
            if not remote_id:
                return False
            adapter = cls._get_adapter(db, company_id)
            return adapter.delete_customer(remote_id)

    @classmethod
    def delete_product(cls, db: Session, company_id: int, product_id: int, remote_id: str | None = None) -> bool:
        """Deletes a product locally or remotely depending on company mode."""
        mode = cls.get_company_mode(db, company_id)

        if mode == "local_master":
            prod = db.query(Product).filter(Product.id == product_id).first()
            if prod:
                prod.is_deleted = True
                db.commit()
                return True
            return False
        else:
            if not remote_id:
                return False
            adapter = cls._get_adapter(db, company_id)
            return adapter.delete_product(remote_id)
