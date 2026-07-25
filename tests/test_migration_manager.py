"""Unit tests for MigrationManager."""

import pytest
from src.desktop.managers.migration_manager import MigrationManager


def test_migration_legacy_dict():
    """Test converting legacy v1.0 column visibility dict to v2.0.0 ViewProfile."""
    legacy_data = {
        "id": True,
        "cari_kodu": True,
        "ticari_unvan": True,
        "telefon": False,
    }

    profile = MigrationManager.migrate_profile_dict(
        "Özel Görünüm", legacy_data, "customers"
    )

    assert profile.version == "2.0.0"
    assert profile.profile.name == "Özel Görünüm"
    assert profile.column_settings.individual_columns["telefon"].visible is False
    # Check mandatory locked group exists
    assert profile.column_settings.groups[0].is_locked is True


def test_migration_nested_dict():
    """Test converting legacy dict with visible and positions dicts."""
    legacy_nested = {
        "visible": {"id": True, "cari_kodu": True, "telefon": False},
        "positions": {"id": 0, "cari_kodu": 1, "telefon": 2},
    }

    profile = MigrationManager.migrate_profile_dict(
        "Sıralı Görünüm", legacy_nested, "customers"
    )

    assert profile.version == "2.0.0"
    assert profile.column_settings.individual_columns["id"].order == 0
    assert profile.column_settings.individual_columns["telefon"].order == 2
