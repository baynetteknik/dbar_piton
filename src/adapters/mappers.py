from datetime import datetime
from typing import Any

from src.core.models import Customer, Order, Product


def parse_datetime(val: Any) -> datetime | None:
    """Helper to parse datetime from different formats (timestamp, ISO string, custom SQL strings)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return datetime.utcfromtimestamp(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        # Try UNIX timestamp string
        if val.isdigit():
            return datetime.utcfromtimestamp(int(val))
        # Try ISO 8601 string
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                # Geriye dönük uyumluluk için milisaniyeleri ve saat dilimini temizleyelim
                clean_val = val.split(".")[0].rstrip("Z")
                return datetime.strptime(clean_val, fmt)
            except ValueError:
                pass
    return None


class DolibarrMapper:
    """Maps raw Dolibarr JSON API DTO objects to local ORM Models."""

    @staticmethod
    def to_product_orm(site_id: int, data: dict[str, Any]) -> Product:
        remote_id = str(data.get("id"))
        sku = data.get("ref", f"DLI-{remote_id}")
        name = data.get("label", "")
        # Handle string or float prices safely
        try:
            price = float(data.get("price", 0.0))
        except (ValueError, TypeError):
            price = 0.0

        try:
            stock = int(data.get("stock_real", data.get("qty", 0)))
        except (ValueError, TypeError):
            stock = 0

        # Dolibarr modification time is usually tms (unix timestamp) or date_modification
        modified_val = data.get("tms") or data.get("date_modification")
        remote_modified_at = parse_datetime(modified_val)

        return Product(
            site_id=site_id,
            remote_id=remote_id,
            sku=sku,
            name=name,
            price=price,
            stock=stock,
            remote_modified_at=remote_modified_at,
        )

    @staticmethod
    def to_order_orm(site_id: int, data: dict[str, Any]) -> Order:
        remote_id = str(data.get("id"))
        order_number = data.get("ref", f"ORD-DLI-{remote_id}")
        customer_name = data.get("socname", data.get("client", {}).get("socname", "Bilinmeyen Müşteri"))

        try:
            total_amount = float(data.get("total_ttc", 0.0))
        except (ValueError, TypeError):
            total_amount = 0.0

        # Dolibarr uses numeric status code for orders (e.g. 0=Draft, 1=Validated, 2=Shipped, 3=Billed)
        status_code = str(data.get("status", "0"))
        status_map = {
            "0": "Draft",
            "1": "Validated",
            "2": "Shipped",
            "3": "Billed",
            "-1": "Canceled",
        }
        status = status_map.get(status_code, f"Status_{status_code}")

        modified_val = data.get("tms") or data.get("date_modification")
        remote_modified_at = parse_datetime(modified_val)

        return Order(
            site_id=site_id,
            remote_id=remote_id,
            order_number=order_number,
            customer_name=customer_name,
            total_amount=total_amount,
            status=status,
            remote_modified_at=remote_modified_at,
        )

    @staticmethod
    def to_customer_orm(site_id: int, data: dict[str, Any]) -> Customer:
        remote_id = str(data.get("id"))
        fullname = data.get("nom", data.get("name", ""))
        email = data.get("email")
        phone = data.get("phone")
        address = data.get("address")
        tax_office = data.get("tax_office") or data.get("localtax1_ass")
        tax_number = data.get("tva_intra") or data.get("tva_ass")
        customer_code = data.get("code_client")
        
        options = data.get("array_options", {}) or {}
        special_code_1 = options.get("options_special_code_1")
        special_code_2 = options.get("options_special_code_2")
        special_code_3 = options.get("options_special_code_3")
        
        return Customer(
            remote_id=remote_id,
            marketplace="dolibarr",
            fullname=fullname,
            email=email,
            phone=phone,
            address=address,
            tax_office=tax_office,
            tax_number=tax_number,
            customer_code=customer_code,
            special_code_1=special_code_1,
            special_code_2=special_code_2,
            special_code_3=special_code_3,
        )


class WooCommerceMapper:
    """Maps WooCommerce JSON API DTO objects to local ORM Models."""

    @staticmethod
    def to_product_orm(site_id: int, data: dict[str, Any]) -> Product:
        remote_id = str(data.get("id"))
        # Fallback to remote ID if SKU is missing
        sku = data.get("sku") or f"WC-{remote_id}"
        name = data.get("name", "")

        try:
            price = float(data.get("price", 0.0) or 0.0)
        except (ValueError, TypeError):
            price = 0.0

        try:
            # WooCommerce stock_quantity can be None if stock management is disabled
            stock = int(data.get("stock_quantity", 0) or 0)
        except (ValueError, TypeError):
            stock = 0

        remote_modified_at = parse_datetime(data.get("date_modified"))

        return Product(
            site_id=site_id,
            remote_id=remote_id,
            sku=sku,
            name=name,
            price=price,
            stock=stock,
            remote_modified_at=remote_modified_at,
        )

    @staticmethod
    def to_order_orm(site_id: int, data: dict[str, Any]) -> Order:
        remote_id = str(data.get("id"))
        order_number = data.get("number", f"ORD-WC-{remote_id}")

        billing = data.get("billing", {})
        first_name = billing.get("first_name", "")
        last_name = billing.get("last_name", "")
        customer_name = f"{first_name} {last_name}".strip()
        if not customer_name:
            customer_name = "Bilinmeyen Müşteri"

        try:
            total_amount = float(data.get("total", 0.0) or 0.0)
        except (ValueError, TypeError):
            total_amount = 0.0

        status = data.get("status", "pending")

        remote_modified_at = parse_datetime(data.get("date_modified"))

        return Order(
            site_id=site_id,
            remote_id=remote_id,
            order_number=order_number,
            customer_name=customer_name,
            total_amount=total_amount,
            status=status,
            remote_modified_at=remote_modified_at,
        )

    @staticmethod
    def to_customer_orm(site_id: int, data: dict[str, Any]) -> Customer:
        remote_id = str(data.get("id"))
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        fullname = f"{first_name} {last_name}".strip() or data.get("username", "")
        email = data.get("email")
        
        billing = data.get("billing", {}) or {}
        phone = billing.get("phone")
        address = billing.get("address_1", "")
        if billing.get("address_2"):
            address += " " + billing.get("address_2")
            
        return Customer(
            remote_id=remote_id,
            marketplace="woocommerce",
            fullname=fullname,
            email=email,
            phone=phone,
            address=address,
        )


def map_remote_to_product(
    remote_item: dict[str, Any], existing_obj: Product | None = None,
) -> Product:
    """Generic mapper function for PullEngine to upsert Products."""
    cms_type = remote_item.get("cms_type", "woocommerce")
    site_id = remote_item.get("site_id", 1)

    if cms_type == "dolibarr":
        remote_id = str(remote_item.get("id"))
        sku = remote_item.get("ref", f"DLI-{remote_id}")
        name = remote_item.get("label", "")
        try:
            price = float(remote_item.get("price", 0.0))
        except (ValueError, TypeError):
            price = 0.0
        try:
            stock = int(remote_item.get("stock_real", remote_item.get("qty", 0)))
        except (ValueError, TypeError):
            stock = 0
        modified_val = remote_item.get("tms") or remote_item.get("date_modification")
        remote_modified_at = parse_datetime(modified_val)
    else:
        remote_id = str(remote_item.get("id"))
        sku = remote_item.get("sku") or f"WC-{remote_id}"
        name = remote_item.get("name", "")
        try:
            price = float(remote_item.get("price", 0.0) or 0.0)
        except (ValueError, TypeError):
            price = 0.0
        try:
            stock = int(remote_item.get("stock_quantity", 0) or 0)
        except (ValueError, TypeError):
            stock = 0
        remote_modified_at = parse_datetime(remote_item.get("date_modified"))

    if existing_obj is None:
        existing_obj = Product(
            site_id=site_id,
            remote_id=remote_id,
            sku=sku,
            name=name,
            price=price,
            stock=stock,
            remote_modified_at=remote_modified_at,
        )
    else:
        existing_obj.sku = sku
        existing_obj.name = name
        existing_obj.price = price
        existing_obj.stock = stock
        existing_obj.remote_modified_at = remote_modified_at

    return existing_obj


def map_remote_to_order(
    remote_item: dict[str, Any], existing_obj: Order | None = None,
) -> Order:
    """Generic mapper function for PullEngine to upsert Orders."""
    cms_type = remote_item.get("cms_type", "woocommerce")
    site_id = remote_item.get("site_id", 1)

    if cms_type == "dolibarr":
        remote_id = str(remote_item.get("id"))
        order_number = remote_item.get("ref", f"ORD-DLI-{remote_id}")
        customer_name = remote_item.get(
            "socname",
            remote_item.get("client", {}).get("socname", "Bilinmeyen Müşteri"),
        )
        try:
            total_amount = float(remote_item.get("total_ttc", 0.0))
        except (ValueError, TypeError):
            total_amount = 0.0
        status_code = str(remote_item.get("status", "0"))
        status_map = {
            "0": "Draft",
            "1": "Validated",
            "2": "Shipped",
            "3": "Billed",
            "-1": "Canceled",
        }
        status = status_map.get(status_code, f"Status_{status_code}")
        modified_val = remote_item.get("tms") or remote_item.get("date_modification")
        remote_modified_at = parse_datetime(modified_val)
    else:
        remote_id = str(remote_item.get("id"))
        order_number = remote_item.get("number", f"ORD-WC-{remote_id}")
        billing = remote_item.get("billing", {})
        first_name = billing.get("first_name", "")
        last_name = billing.get("last_name", "")
        customer_name = f"{first_name} {last_name}".strip()
        if not customer_name:
            customer_name = "Bilinmeyen Müşteri"
        try:
            total_amount = float(remote_item.get("total", 0.0) or 0.0)
        except (ValueError, TypeError):
            total_amount = 0.0
        status = remote_item.get("status", "pending")
        remote_modified_at = parse_datetime(remote_item.get("date_modified"))

    if existing_obj is None:
        existing_obj = Order(
            site_id=site_id,
            remote_id=remote_id,
            order_number=order_number,
            customer_name=customer_name,
            total_amount=total_amount,
            status=status,
            remote_modified_at=remote_modified_at,
        )
    else:
        existing_obj.order_number = order_number
        existing_obj.customer_name = customer_name
        existing_obj.total_amount = total_amount
        existing_obj.status = status
        existing_obj.remote_modified_at = remote_modified_at

    return existing_obj


def map_remote_to_customer(
    remote_item: dict[str, Any], existing_obj: Customer | None = None,
) -> Customer:
    """Generic mapper function for PullEngine to upsert Customers."""
    cms_type = remote_item.get("cms_type", "woocommerce")
    
    if cms_type == "dolibarr":
        remote_id = str(remote_item.get("id"))
        fullname = remote_item.get("nom", remote_item.get("name", ""))
        email = remote_item.get("email")
        phone = remote_item.get("phone")
        address = remote_item.get("address")
        tax_office = remote_item.get("tax_office") or remote_item.get("localtax1_ass")
        tax_number = remote_item.get("tva_intra") or remote_item.get("tva_ass")
        customer_code = remote_item.get("code_client")
        
        options = remote_item.get("array_options", {}) or {}
        special_code_1 = options.get("options_special_code_1")
        special_code_2 = options.get("options_special_code_2")
        special_code_3 = options.get("options_special_code_3")
        group_name = remote_item.get("group_name")
        sub_group_1 = remote_item.get("sub_group_1")
        sub_group_2 = remote_item.get("sub_group_2")
    else:
        remote_id = str(remote_item.get("id"))
        first_name = remote_item.get("first_name", "")
        last_name = remote_item.get("last_name", "")
        fullname = f"{first_name} {last_name}".strip() or remote_item.get("username", "")
        email = remote_item.get("email")
        
        billing = remote_item.get("billing", {}) or {}
        phone = billing.get("phone")
        address = billing.get("address_1", "")
        if billing.get("address_2"):
            address += " " + billing.get("address_2")
            
        tax_office = None
        tax_number = None
        customer_code = None
        special_code_1 = None
        special_code_2 = None
        special_code_3 = None
        group_name = None
        sub_group_1 = None
        sub_group_2 = None

    if existing_obj is None:
        existing_obj = Customer(
            remote_id=remote_id,
            marketplace=cms_type,
            fullname=fullname,
            email=email,
            phone=phone,
            address=address,
            tax_office=tax_office,
            tax_number=tax_number,
            customer_code=customer_code,
            special_code_1=special_code_1,
            special_code_2=special_code_2,
            special_code_3=special_code_3,
            group_name=group_name,
            sub_group_1=sub_group_1,
            sub_group_2=sub_group_2,
        )
    else:
        existing_obj.fullname = fullname
        existing_obj.email = email
        existing_obj.phone = phone
        existing_obj.address = address
        existing_obj.tax_office = tax_office
        existing_obj.tax_number = tax_number
        existing_obj.customer_code = customer_code
        existing_obj.special_code_1 = special_code_1
        existing_obj.special_code_2 = special_code_2
        existing_obj.special_code_3 = special_code_3
        existing_obj.group_name = group_name
        existing_obj.sub_group_1 = sub_group_1
        existing_obj.sub_group_2 = sub_group_2

    return existing_obj
