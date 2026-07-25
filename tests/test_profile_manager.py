"""Unit tests for ProfileManager and ViewProfile models."""

import pytest
from src.desktop.managers.profile_manager import ProfileManager
from src.desktop.models.profile_models import (
    ColumnGroup,
    ColumnSettings,
    ProfileMetadata,
    ViewProfile,
)


def test_view_profile_serialization():
    """Test ViewProfile to_dict and from_dict roundtrip."""
    meta = ProfileMetadata(id="p1", name="Test Profile")
    col_group = ColumnGroup(
        id="g1", name="Core Group", columns=["id", "code"], is_locked=True
    )
    col_settings = ColumnSettings(groups=[col_group])

    profile = ViewProfile(
        version="2.0.0",
        profile=meta,
        column_settings=col_settings,
    )

    data_dict = profile.to_dict()
    assert data_dict["version"] == "2.0.0"
    assert data_dict["profile"]["name"] == "Test Profile"
    assert data_dict["column_settings"]["groups"][0]["is_locked"] is True

    json_str = profile.to_json()
    loaded_profile = ViewProfile.from_json(json_str)

    assert loaded_profile.version == "2.0.0"
    assert loaded_profile.profile.name == "Test Profile"
    assert loaded_profile.column_settings.groups[0].columns == ["id", "code"]


def test_profile_manager_defaults():
    """Test ProfileManager default profile creation."""
    pm = ProfileManager(profile_key="test_table")
    default_p = pm.create_default_profile()

    assert default_p.version == "2.0.0"
    assert default_p.profile.name == "Varsayılan"
    # Mandatory core group locked check
    assert default_p.column_settings.groups[0].is_locked is True
    assert "id" in default_p.column_settings.groups[0].columns
    assert "cari_kodu" in default_p.column_settings.groups[0].columns


def test_profile_manager_debtors_template():
    """Test debtors profile template creation."""
    pm = ProfileManager(profile_key="test_table")
    debtors_p = pm.create_debtors_profile()

    assert debtors_p.profile.name == "Borçlu Müşteriler"
    assert len(debtors_p.visual_rules) == 3
    # First rule should be debt highlight with priority 1
    assert debtors_p.visual_rules[0].priority == 1
    assert debtors_p.visual_rules[0].style.icon == "💰"
