"""
TOYA ERP - Dynamic Module Taxonomy & Master Atomic Widget Registry Unit Tests
"""

import pytest
from src.desktop.core.module_taxonomy import taxonomy_manager
from src.desktop.ui.widgets.widget_registry import WIDGET_REGISTRY, create_widget_by_id
from src.desktop.core.screen_registry import get_screen_definition


def test_taxonomy_manager_load_and_categories():
    categories = taxonomy_manager.get_categories()
    assert isinstance(categories, list)
    assert len(categories) > 0
    cat_codes = [c["code"] for c in categories]
    assert "tan" in cat_codes
    assert "isl" in cat_codes


def test_taxonomy_manager_add_category_and_module():
    new_cat = taxonomy_manager.add_category("crm", "CRM & Müşteri İlişkileri", "🤝")
    assert new_cat["code"] == "crm"
    
    new_mod = taxonomy_manager.add_module("crm", "crm.opp", "Fırsat Takibi")
    assert new_mod is not None
    assert new_mod["code"] == "crm.opp"


def test_widget_registry_contents():
    assert "widget_crud_actions" in WIDGET_REGISTRY
    assert "widget_cari_kunyesi" in WIDGET_REGISTRY
    assert "widget_belge_vade" in WIDGET_REGISTRY
    assert "widget_hareket_kalemleri" in WIDGET_REGISTRY
    assert "widget_alt_iskonto_masraflar" in WIDGET_REGISTRY
    assert "widget_belge_notlari" in WIDGET_REGISTRY
    assert "widget_finans" in WIDGET_REGISTRY


def test_screen_registry_fallback_resolution():
    # Defined screen
    def_quo = get_screen_definition("isl.quo.001")
    assert def_quo["title"] == "Teklif Yönetimi"
    assert def_quo["base_template"] == "tpl_fis_list"
    
    # Unknown screen fallback to tpl_default_list or prefix fallback
    unknown_def = get_screen_definition("custom.unknown.module")
    assert unknown_def.get("is_fallback") is True
    assert "tpl_default_list" in unknown_def.get("fallback_template_id", "")
