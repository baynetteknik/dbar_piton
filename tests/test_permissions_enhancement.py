"""Tests for expanded permission catalog and enhanced _PermTreeField."""

from src.desktop.security.permissions import (
    ALL_PERMISSIONS,
    PERMISSION_GROUPS,
    permission_label,
)
from src.desktop.ui.screens.definition_editor_screen import _PermTreeField


def test_permission_catalog_completeness():
    group_codes = {g[0] for g in PERMISSION_GROUPS}
    assert "numara" in group_codes
    assert "yedekleme" in group_codes
    assert "portal" in group_codes
    assert "tasarimci" in group_codes
    assert "doviz" in group_codes
    assert "belge_kilit" in group_codes
    assert "cek_senet" in group_codes
    assert "personel" in group_codes

    assert "numara.view" in ALL_PERMISSIONS
    assert "numara.create" in ALL_PERMISSIONS
    assert "yedekleme.backup" in ALL_PERMISSIONS

    assert "Belge & Seri" in permission_label("numara.view")


def test_perm_tree_field_search_and_presets(qapp):
    field = _PermTreeField(PERMISSION_GROUPS)

    # Test preset application
    field._apply_preset(["teklif.*", "cari.view"])
    val = field.value()
    assert "teklif.view" in val
    assert "teklif.create" in val
    assert "cari.view" in val
    assert "fatura.view" not in val

    # Test view only
    field._set_view_only()
    val_view = field.value()
    assert all(c.endswith(".view") for c in val_view)

    # Test search filter
    field._on_search("Fatura")
    top_fatura = field._top_items.get("fatura")
    assert top_fatura is not None
    assert not top_fatura.isHidden()
