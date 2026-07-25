"""Migration Manager for View Profiles.

Converts legacy v1.0.0 profile dicts into ViewProfile v2.0.0 dataclass structures.
"""

import logging
from typing import Any

from src.desktop.models.profile_models import (
    ColumnGroup,
    ColumnSettings,
    FrozenColumns,
    IndividualColumn,
    ProfileMetadata,
    ViewProfile,
)

logger = logging.getLogger(__name__)


class MigrationManager:
    """Manages migration of profile data structures between versions."""

    CURRENT_VERSION = "2.0.0"

    @classmethod
    def migrate_profile_dict(
        cls, profile_name: str, raw_data: Any, profile_key: str = "customers",
    ) -> ViewProfile:
        """Migrate raw profile data (v1.0 dict/legacy) to a ViewProfile (v2.0.0).

        Args:
            profile_name: Name of the profile.
            raw_data: Legacy dict or raw JSON structure.
            profile_key: Identifies table profile (e.g. customers, backup).

        Returns:
            ViewProfile v2.0.0 instance.
        """
        # If it's already v2.0.0 dict structure with version key:
        if isinstance(raw_data, dict) and raw_data.get("version") == cls.CURRENT_VERSION:
            try:
                return ViewProfile.from_dict(raw_data)
            except Exception as e:
                logger.warning(f"Error parsing v2.0.0 profile {profile_name}: {e}")

        logger.info(f"Migrating profile '{profile_name}' to v2.0.0 format...")

        visible_map: dict[str, bool] = {}
        positions_map: dict[str, int] = {}

        if isinstance(raw_data, dict):
            if "visible" in raw_data and isinstance(raw_data["visible"], dict):
                visible_map = {str(k): bool(v) for k, v in raw_data["visible"].items()}
                if "positions" in raw_data and isinstance(raw_data["positions"], dict):
                    positions_map = {
                        str(k): int(v) for k, v in raw_data["positions"].items()
                    }
            else:
                # Direct field -> visible map
                visible_map = {str(k): bool(v) for k, v in raw_data.items()}

        indiv_columns: dict[str, IndividualColumn] = {}
        for col_name, vis in visible_map.items():
            order = positions_map.get(col_name, 0)
            indiv_columns[col_name] = IndividualColumn(visible=vis, width=120, order=order)

        # Core mandatory locked group
        core_group = ColumnGroup(
            id="group_core",
            name="Temel Bilgiler",
            is_collapsible=True,
            is_collapsed=False,
            columns=["id", "cari_kodu", "ticari_unvan"],
            is_locked=True,
        )

        col_settings = ColumnSettings(
            groups=[core_group],
            individual_columns=indiv_columns,
            frozen_columns=FrozenColumns(count=2, columns=["id", "cari_kodu"]),
        )

        meta = ProfileMetadata(
            id=f"prof_{profile_key}_{profile_name.lower().replace(' ', '_')}",
            name=profile_name,
            table_id=f"{profile_key}_table",
            profile_type="user_defined" if profile_name != "Varsayılan" else "system_default",
        )

        return ViewProfile(
            version=cls.CURRENT_VERSION,
            profile=meta,
            column_settings=col_settings,
        )
