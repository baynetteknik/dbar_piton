import json
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class DbSettings(BaseSettings):
    db_path: str = Field(default="data/app.db", description="Database file path")
    db_key: str | None = Field(default=None, description="Encryption key for SQLCipher")


class SyncSettings(BaseSettings):
    sync_interval_minutes: int = Field(
        default=15, description="Automatic sync interval in minutes",
    )


class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    """Loads configuration from an optional config.json file in the root directory."""

    def get_field_value(
        self, field: Any, field_name: str,
    ) -> tuple[Any, str, bool]:
        # This is fallback, full dict load is implemented in __call__
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        config_path = Path("config.json")
        if not config_path.exists():
            return {}
        try:
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "Multi-CMS Manager"
    debug: bool = False
    db: DbSettings = DbSettings()
    sync: SyncSettings = SyncSettings()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            JsonConfigSettingsSource(settings_cls),
        )


# Instantiate settings globally
settings = Settings()
