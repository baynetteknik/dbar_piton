import json
from pathlib import Path

from src.core.config import Settings


def test_default_settings():
    """Verify default configurations are set correctly."""
    settings = Settings()
    assert settings.app_name == "Multi-CMS Manager"
    assert settings.db.db_path == "data/app.db"
    assert settings.sync.sync_interval_minutes == 15


def test_env_overrides(monkeypatch):
    """Verify settings can be overridden via environment variables."""
    monkeypatch.setenv("APP_NAME", "Test App")
    monkeypatch.setenv("DB__DB_PATH", "test.db")
    monkeypatch.setenv("SYNC__SYNC_INTERVAL_MINUTES", "45")

    settings = Settings()
    assert settings.app_name == "Test App"
    assert settings.db.db_path == "test.db"
    assert settings.sync.sync_interval_minutes == 45


def test_json_config_loading(tmp_path, monkeypatch):
    """Verify configuration loads correctly from config.json."""
    config_data = {
        "app_name": "JSON App",
        "db": {"db_path": "json.db", "db_key": "secret123"},
        "sync": {"sync_interval_minutes": 30},
    }

    # Write config.json in the current working directory during the test
    config_file = Path("config.json")
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        settings = Settings()
        assert settings.app_name == "JSON App"
        assert settings.db.db_path == "json.db"
        assert settings.db.db_key == "secret123"
        assert settings.sync.sync_interval_minutes == 30
    finally:
        if config_file.exists():
            config_file.unlink()
        # Reset Settings instantiation cache if any
