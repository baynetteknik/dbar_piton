"""Tests for MasterDefinitionsStore, dynamic definitions, and SettingsHubWidget."""

import pytest
from PyQt6.QtWidgets import QApplication

from src.desktop.services.master_definitions_store import (
    MasterDefinitionsStore,
)
from src.desktop.ui.widgets.address_definitions_widget import (
    AddressDefinitionsWidget,
)
from src.desktop.ui.widgets.bank_definitions_widget import BankDefinitionsWidget
from src.desktop.ui.widgets.settings_hub_widget import (
    SettingsHubWidget,
)
from src.desktop.ui.widgets.tax_offices_widget import TaxOfficesWidget


@pytest.fixture(scope="session")
def qapp():
    """Ensure QApplication instance is active for UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def store(tmp_path):
    """Fixture to provide a clean MasterDefinitionsStore with temporary DB."""
    db_path = tmp_path / "test_master_defs.db"
    return MasterDefinitionsStore(db_path=db_path)


class TestMasterDefinitionsStore:
    """Test suite for MasterDefinitionsStore SQLite storage and CRUD."""

    def test_default_seeding(self, store: MasterDefinitionsStore):
        """Test default seeding of countries, cities, banks, and tax offices."""
        countries = store.get_countries()
        assert len(countries) >= 5
        assert any(c["code"] == "TR" for c in countries)

        cities = store.get_cities(country_code="TR")
        assert len(cities) == 81
        assert any(c["plate_code"] == "34" and "STANBUL" in c["name"].upper() for c in cities)

        banks = store.get_banks()
        assert len(banks) >= 10
        assert any(b["code"] == "0010" for b in banks)

        taxes = store.get_tax_offices(city_plate="34")
        assert len(taxes) >= 5

    def test_country_crud(self, store: MasterDefinitionsStore):
        """Test country insert, list, and toggle active."""
        store.add_country("JP", "JAPONYA", "+81", "JPY")
        countries = store.get_countries()
        japan = next((c for c in countries if c["code"] == "JP"), None)
        assert japan is not None
        assert japan["currency"] == "JPY"
        assert japan["phone_code"] == "+81"

    def test_city_crud(self, store: MasterDefinitionsStore):
        """Test city save and update."""
        store.add_city("99", "YENİ ŞEHİR", "TR", "0999")
        cities = store.get_cities(country_code="TR")
        city = next((c for c in cities if c["plate_code"] == "99"), None)
        assert city is not None
        assert city["name"] == "YENİ ŞEHİR"
        assert city["phone_code"] == "0999"

        # Update
        store.update_city(city["id"], name="GÜNCEL ŞEHİR", phone_code="0998")
        cities_updated = store.get_cities(country_code="TR")
        city_up = next((c for c in cities_updated if c["plate_code"] == "99"), None)
        assert city_up is not None
        assert city_up["name"] == "GÜNCEL ŞEHİR"

    def test_district_and_sub_district_crud(self, store: MasterDefinitionsStore):
        """Test district and sub_district creation and querying."""
        dist_id = store.add_district("06", "ÇANKAYA")
        assert dist_id > 0

        districts = store.get_districts("06")
        assert any(d["name"] == "ÇANKAYA" for d in districts)

        # Add sub_district
        sub_id = store.add_sub_district("06", "ÇANKAYA", "KIZILAY", "06420")
        assert sub_id > 0

        sub_districts = store.get_sub_districts("06", "ÇANKAYA")
        assert len(sub_districts) == 1
        assert sub_districts[0]["name"] == "KIZILAY"
        assert sub_districts[0]["postcode"] == "06420"

        # Delete sub_district
        store.delete_sub_district(sub_id)
        assert len(store.get_sub_districts("06", "ÇANKAYA")) == 0

        # Delete district
        store.delete_district(dist_id)
        assert not any(d["id"] == dist_id for d in store.get_districts("06"))

    def test_tax_offices_crud_and_search(self, store: MasterDefinitionsStore):
        """Test tax office add, search, and delete."""
        tax_id = store.add_tax_office("34999", "ÖZEL VERGİ DAİRESİ", "34", "KADIKÖY", "34999")
        assert tax_id > 0

        # List
        results = store.get_tax_offices(city_plate="34")
        found = next((t for t in results if t["code"] == "34999"), None)
        assert found is not None
        assert found["name"] == "ÖZEL VERGİ DAİRESİ"

        store.delete_tax_office(tax_id)
        assert not any(t["id"] == tax_id for t in store.get_tax_offices(city_plate="34"))

    def test_bank_and_branches_crud(self, store: MasterDefinitionsStore):
        """Test bank and bank branch CRUD."""
        bank_id = store.add_bank("9999", "TEST BANKASI", "TBANKTR", "999")
        assert bank_id > 0

        banks = store.get_banks()
        bank = next((b for b in banks if b["code"] == "9999"), None)
        assert bank is not None
        assert bank["name"] == "TEST BANKASI"
        assert bank["swift_code"] == "TBANKTR"

        # Add branch
        branch_id = store.add_bank_branch("9999", "001", "MERKEZ ŞUBE", "34", "KADIKÖY")
        assert branch_id > 0

        branches = store.get_bank_branches("9999")
        assert len(branches) == 1
        assert branches[0]["branch_name"] == "MERKEZ ŞUBE"

        # Delete branch
        store.delete_bank_branch(branch_id)
        assert len(store.get_bank_branches("9999")) == 0

        # Delete bank
        store.delete_bank(bank_id)
        assert not any(b["id"] == bank_id for b in store.get_banks())


class TestSettingsHubWidget:
    """Test suite for SettingsHubWidget UI and search filtering."""

    def test_settings_hub_creation_and_search(self, qapp):
        """Test SettingsHubWidget initialization and tile search filter."""
        hub = SettingsHubWidget()
        assert len(hub._buttons) >= 20

        # Test search filter for 'adres'
        hub.txt_search.setText("adres")
        visible_tiles = [b for b in hub._buttons if not b.isHidden()]
        assert any(b.panel_id == "adres_tanimlari" for b in visible_tiles)

        # Clear search filter
        hub.txt_search.setText("")
        visible_all = [b for b in hub._buttons if not b.isHidden()]
        assert len(visible_all) == len(hub._buttons)

    def test_settings_hub_signals(self, qapp):
        """Test that clicking a tile emits navigate_requested signal."""
        hub = SettingsHubWidget()
        emitted = []
        hub.navigate_requested.connect(lambda pid: emitted.append(pid))

        tile = next((b for b in hub._buttons if b.panel_id == "firma_bilgileri"), None)
        assert tile is not None
        tile.click()
        assert emitted == ["firma_bilgileri"]


class TestDefinitionsWidgetsUI:
    """Test suite for AddressDefinitionsWidget, TaxOfficesWidget, and BankDefinitionsWidget."""

    def test_address_definitions_widget_init(self, qapp):
        """Test AddressDefinitionsWidget loads tabs and tables."""
        widget = AddressDefinitionsWidget()
        assert widget.tabs.count() == 4
        assert widget.grid_countries.table_view.rowCount() >= 5
        assert widget.grid_cities.table_view.rowCount() == 81

    def test_tax_offices_widget_init_and_search(self, qapp):
        """Test TaxOfficesWidget loads tax offices and applies search filter."""
        widget = TaxOfficesWidget()
        assert widget.grid.table_view.rowCount() >= 10

        widget.txt_search.setText("Kadıköy")
        assert widget.grid.table_view.rowCount() >= 1

    def test_bank_definitions_widget_init(self, qapp):
        """Test BankDefinitionsWidget loads banks and branch panels."""
        widget = BankDefinitionsWidget()
        assert widget.tabs.count() == 2
        assert widget.grid_banks.table_view.rowCount() >= 10
        assert widget.grid_branches.table_view.rowCount() >= 0
