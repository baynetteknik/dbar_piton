"""Profile Manager for View Profiles v2.0.0.

Manages saving, loading, group mapping, and template generation for View Profiles.
"""

import json
import logging

from PyQt6.QtCore import QSettings

from src.desktop.managers.migration_manager import MigrationManager
from src.desktop.models.profile_models import (
    ColumnGroup,
    ColumnSettings,
    FrozenColumns,
    IndividualColumn,
    ProfileMetadata,
    SummaryBarSettings,
    SummaryField,
    ViewProfile,
)
from src.desktop.models.virtual_column_model import VirtualColumn
from src.desktop.models.visual_rule_model import (
    VisualRule,
    VisualRuleCondition,
    VisualRuleStyle,
)

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages View Profiles persistence, defaults, and group operations."""

    ORGANIZATION_NAME = "baynetteknik"
    APPLICATION_NAME = "dbar_piton"

    CUSTOM_CODE_GROUPS = {
        "group_cc_1_20": {"start": 1, "end": 20, "name": "Özel Kod 1-20"},
        "group_cc_21_50": {"start": 21, "end": 50, "name": "Özel Kod 21-50"},
        "group_cc_51_100": {"start": 51, "end": 100, "name": "Özel Kod 51-100"},
        "group_cc_101_200": {"start": 101, "end": 200, "name": "Özel Kod 101-200"},
        "group_cc_201_500": {"start": 201, "end": 500, "name": "Özel Kod 201-500"},
    }

    def __init__(self, profile_key: str = "customers"):
        self.profile_key = profile_key
        self.settings = QSettings(self.ORGANIZATION_NAME, self.APPLICATION_NAME)

    def load_profiles(self) -> dict[str, ViewProfile]:
        """Loads all profiles for the profile key from QSettings."""
        key = f"view_profiles_v2_{self.profile_key}"
        raw_json = self.settings.value(key, "{}", type=str)
        result: dict[str, ViewProfile] = {}

        try:
            raw_dict = json.loads(raw_json)
            for name, p_data in raw_dict.items():
                profile = MigrationManager.migrate_profile_dict(
                    name, p_data, self.profile_key,
                )
                result[name] = profile
        except Exception as e:
            logger.error(f"Error loading profiles for {self.profile_key}: {e}")

        # Ensure default templates exist if list is empty
        if "Varsayılan" not in result:
            result["Varsayılan"] = self.create_default_profile()
        if self.profile_key == "customers" and "Borçlu Müşteriler" not in result:
            result["Borçlu Müşteriler"] = self.create_debtors_profile()

        return result

    @classmethod
    def reset_all_profiles_to_factory_defaults(cls) -> None:
        """Clears all saved view profiles and settings across all modules from QSettings."""
        settings = QSettings(cls.ORGANIZATION_NAME, cls.APPLICATION_NAME)
        all_keys = list(settings.allKeys())
        for key in all_keys:
            if "view_profile" in key.lower() or "column_profile" in key.lower():
                settings.remove(key)
        settings.sync()

    def save_profile(self, profile: ViewProfile) -> None:
        """Saves or updates a ViewProfile in QSettings."""
        profiles = self.load_profiles()
        profiles[profile.profile.name] = profile
        self._save_all_profiles(profiles)

    def delete_profile(self, profile_name: str) -> bool:
        """Deletes a user-defined profile."""
        if profile_name == "Varsayılan":
            logger.warning("Cannot delete default system profile.")
            return False

        profiles = self.load_profiles()
        if profile_name in profiles:
            del profiles[profile_name]
            self._save_all_profiles(profiles)

            if self.get_active_profile_name() == profile_name:
                self.set_active_profile_name("Varsayılan")
            return True
        return False

    def get_active_profile(self) -> ViewProfile:
        """Gets currently active ViewProfile."""
        active_name = self.get_active_profile_name()
        profiles = self.load_profiles()
        return profiles.get(active_name, self.create_default_profile())

    def get_active_profile_name(self) -> str:
        """Returns name of active profile."""
        key = f"active_view_profile_{self.profile_key}"
        return self.settings.value(key, "Varsayılan", type=str)

    def set_active_profile_name(self, name: str) -> None:
        """Sets active profile name."""
        key = f"active_view_profile_{self.profile_key}"
        self.settings.setValue(key, name)
        self.settings.sync()

    def _save_all_profiles(self, profiles: dict[str, ViewProfile]) -> None:
        key = f"view_profiles_v2_{self.profile_key}"
        serialized = {name: p.to_dict() for name, p in profiles.items()}
        self.settings.setValue(key, json.dumps(serialized, ensure_ascii=False))
        self.settings.sync()

    def create_default_profile(self) -> ViewProfile:
        """Creates the default system ViewProfile."""
        if self.profile_key in ("backup_tasks", "restore_tasks", "backup", "restore"):
            core_cols = ["id", "name", "source", "target_type", "schedule", "status"]
        elif self.profile_key in ("quotations", "orders"):
            core_cols = ["id", "quotation_number", "title", "customer_name", "grand_total", "currency", "status", "issue_date"]
        elif self.profile_key == "sites":
            core_cols = ["id", "code", "name", "url", "status"]
        elif self.profile_key == "products":
            core_cols = ["id", "code", "name", "price", "stock", "unit"]
        elif self.profile_key == "users":
            core_cols = ["id", "username", "full_name", "role", "email", "status"]
        else:
            core_cols = ["id", "cari_kodu", "ticari_unvan", "vergi_dairesi", "vergi_no"]

        core_group = ColumnGroup(
            id="group_core",
            name="Temel Bilgiler",
            is_collapsible=True,
            is_collapsed=False,
            columns=core_cols,
            is_locked=True,
        )
        cc_group1 = ColumnGroup(
            id="group_custom_codes_1",
            name="Özel Kod 1-20",
            is_collapsible=True,
            is_collapsed=True,
            columns=[f"ozel_kod_{i}" for i in range(1, 21)],
        )

        indiv_cols = {
            col: IndividualColumn(visible=True, width=150, order=idx)
            for idx, col in enumerate(core_cols)
        }

        vc_balance = VirtualColumn(
            id="vc_balance",
            name="Bakiye",
            formula="alacak - borç",
            data_type="decimal",
            format="#,##0.00 ₺",
            is_visible=True,
            order=3,
        )

        summary_bar = SummaryBarSettings(
            is_enabled=True,
            position="bottom",
            fields=[
                SummaryField(
                    id="total_debt",
                    name="Toplam Borç",
                    aggregation="sum",
                    field="borç",
                ),
                SummaryField(
                    id="total_credit",
                    name="Toplam Alacak",
                    aggregation="sum",
                    field="alacak",
                ),
                SummaryField(
                    id="net_balance",
                    name="Net Bakiye",
                    aggregation="formula",
                    formula="total_credit - total_debt",
                ),
            ],
        )

        return ViewProfile(
            version="2.0.0",
            profile=ProfileMetadata(
                id=f"prof_{self.profile_key}_default",
                name="Varsayılan",
                profile_type="system_default",
            ),
            column_settings=ColumnSettings(
                groups=[core_group, cc_group1],
                individual_columns=indiv_cols,
                frozen_columns=FrozenColumns(count=2, columns=core_cols[:2]),
            ),
            virtual_columns=[vc_balance],
            summary_bar=summary_bar,
        )

    def create_debtors_profile(self) -> ViewProfile:
        """Creates system template for Debtors View with visual rules."""
        profile = self.create_default_profile()
        profile.profile.id = f"prof_{self.profile_key}_debtors"
        profile.profile.name = "Borçlu Müşteriler"

        rule_debt = VisualRule(
            id="rule_debt_highlight",
            name="Borçlu Vurgusu",
            priority=1,
            condition=VisualRuleCondition(
                field="bakiye", operator="less_than", value=0,
            ),
            style=VisualRuleStyle(
                background_color="#f8d7da",
                text_color="#721c24",
                font_weight="bold",
                icon="💰",
            ),
        )
        rule_credit = VisualRule(
            id="rule_credit_highlight",
            name="Alacaklı Vurgusu",
            priority=2,
            condition=VisualRuleCondition(
                field="bakiye", operator="greater_than", value=0,
            ),
            style=VisualRuleStyle(
                background_color="#d4edda",
                text_color="#155724",
            ),
        )
        rule_passive = VisualRule(
            id="rule_passive_highlight",
            name="Pasif Cari Vurgusu",
            priority=3,
            condition=VisualRuleCondition(
                field="durum", operator="equals", value="Pasif",
            ),
            style=VisualRuleStyle(
                background_color="#fff3cd",
                text_color="#856404",
                opacity=0.7,
            ),
        )

        profile.visual_rules = [rule_debt, rule_credit, rule_passive]
        return profile
