import logging
from abc import ABC, abstractmethod

from src.core.models import Customer

logger = logging.getLogger(__name__)


class BaseRepository(ABC):
    """Soyut veri katmanı taban sınıfı."""

    @abstractmethod
    def get_page_data(
        self, filters: dict, sort_by: str, sort_order: str, page: int, per_page: int,
    ):
        """Filtrelenmiş, sıralanmış ve sayfalanmış veri döndürür.

        Args:
            filters (dict): Sütun adına göre filtre değerleri
            sort_by (str): Sıralanacak sütun adı
            sort_order (str): "asc" veya "desc"
            page (int): Sayfa numarası (1-indexed)
            per_page (int): Sayfa başına kayıt sayısı

        Returns:
            tuple: (veri_listesi, toplam_kayit_sayisi)
        """
        pass


class SqliteCustomerRepository(BaseRepository):
    """SQLite veritabanı üzerindeki Cari Kartlar (Customer) için repository adaptörü."""

    def __init__(self, db_session, company_id: int):
        self.db = db_session
        self.company_id = company_id

    def get_page_data(
        self, filters: dict, sort_by: str, sort_order: str, page: int, per_page: int,
    ):
        try:
            query = self.db.query(Customer).filter(
                Customer.is_deleted == False,
            )

            # Dinamik Filtreleme
            for col_name, value in filters.items():
                if value is None:
                    continue
                val_str = str(value).strip()
                if not val_str:
                    continue

                if col_name == "id":
                    try:
                        query = query.filter(Customer.id == int(val_str))
                    except ValueError:
                        pass
                elif col_name in ("fullname", "name"):
                    query = query.filter(Customer.fullname.like(f"%{val_str}%"))
                elif col_name in ("customer_code", "code"):
                    query = query.filter(
                        Customer.customer_code.like(f"%{val_str}%"),
                    )
                elif col_name == "tax_office":
                    query = query.filter(Customer.tax_office.like(f"%{val_str}%"))
                elif col_name == "tax_number":
                    query = query.filter(Customer.tax_number.like(f"%{val_str}%"))
                elif col_name == "phone":
                    query = query.filter(Customer.phone.like(f"%{val_str}%"))
                elif col_name == "email":
                    query = query.filter(Customer.email.like(f"%{val_str}%"))
                elif col_name == "address":
                    query = query.filter(Customer.address.like(f"%{val_str}%"))
                elif col_name == "group_name":
                    if val_str != "Tümü":
                        query = query.filter(Customer.group_name == val_str)
                elif col_name == "sub_group_1":
                    query = query.filter(Customer.sub_group_1.like(f"%{val_str}%"))
                elif col_name == "sub_group_2":
                    query = query.filter(Customer.sub_group_2.like(f"%{val_str}%"))
                elif col_name == "special_code_1":
                    query = query.filter(
                        Customer.special_code_1.like(f"%{val_str}%"),
                    )
                elif col_name == "special_code_2":
                    query = query.filter(
                        Customer.special_code_2.like(f"%{val_str}%"),
                    )
                elif col_name == "special_code_3":
                    query = query.filter(
                        Customer.special_code_3.like(f"%{val_str}%"),
                    )
                elif col_name == "status":
                    try:
                        val_int = int(val_str)
                        if val_int != -1:
                            query = query.filter(Customer.status == val_int)
                    except ValueError:
                        pass
                elif col_name == "marketplace":
                    if val_str != "Tümü":
                        query = query.filter(Customer.marketplace == val_str)

            # Toplam Kayıt Sayısı
            total_records = query.count()

            # Sıralama (Sorting)
            if sort_by:
                model_attr = getattr(Customer, sort_by, None)
                if model_attr:
                    if sort_order == "desc":
                        query = query.order_by(model_attr.desc())
                    else:
                        query = query.order_by(model_attr.asc())
            else:
                query = query.order_by(Customer.id.desc())

            # Sayfalama (Pagination)
            offset = (page - 1) * per_page
            data = query.offset(offset).limit(per_page).all()

            return data, total_records

        except Exception as e:
            logger.error(f"SQLite repository get_page_data hatası: {e}")
            return [], 0
