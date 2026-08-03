"""Unit tests for ERP Integration Adapters (Akınsoft, Logo, Zirve)."""

from src.adapters.akinsoft.akinsoft_adapter import AkinsoftERPAdapter
from src.adapters.logo.logo_adapter import LogoERPAdapter
from src.adapters.zirve.zirve_adapter import ZirveERPAdapter


def test_akinsoft_adapter():
    adapter = AkinsoftERPAdapter({"host": "localhost"})
    assert adapter.test_connection() is True
    custs = adapter.fetch_customers()
    assert len(custs) >= 1
    assert custs[0]["marketplace"] == "akinsoft"

    prods = adapter.fetch_products()
    assert len(prods) >= 1
    assert prods[0]["price"] == 1500.0


def test_logo_adapter():
    adapter = LogoERPAdapter({"host": "localhost"})
    assert adapter.test_connection() is True
    custs = adapter.fetch_customers()
    assert len(custs) >= 1
    assert custs[0]["marketplace"] == "logo"


def test_zirve_adapter():
    adapter = ZirveERPAdapter({"host": "localhost"})
    assert adapter.test_connection() is True
    prods = adapter.fetch_products()
    assert len(prods) >= 1
    assert prods[0]["marketplace"] if "marketplace" in prods[0] else True
