import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from packaging.version import Version

logger = logging.getLogger(__name__)

CURRENT_VERSION = "0.1.0"
APPCAST_URL = "https://raw.githubusercontent.com/your-repo/multi-cms-manager/main/appcast.json"


@dataclass
class UpdateInfo:
    """Güncelleme bilgisi."""

    version: str
    release_date: str
    download_url: str
    release_notes: str
    file_size: int
    min_version: str | None = None

    @property
    def parsed_version(self) -> Version:
        return Version(self.version)

    def is_compatible(self, current_version: str) -> bool:
        """Bu güncelleme mevcut sürümle uyumlu mu?"""
        if self.min_version:
            return Version(current_version) >= Version(self.min_version)
        return True


class AutoUpdater:
    """Otomatik güncelleme sistemi.

    Uygulama yeni sürümü olup olmadığını kontrol eder ve
    kullanıcıya güncelleme seçeneği sunar.

    Özellikler:
    - Appcast JSON üzerinden güncelleme kontrolü
    - Sessiz arka plan kontrolü
    - Kullanıcı bildirimi
    - İsteğe bağlı indirme

    Kullanım:
        updater = AutoUpdater()

        # Güncelleme var mı?
        update = updater.check_for_updates()
        if update:
            print(f"Yeni sürüm: {update.version}")
            updater.download_update(update)
    """

    def __init__(self, appcast_url: str | None = None, current_version: str | None = None):
        self.appcast_url = appcast_url or APPCAST_URL
        self.current_version = current_version or CURRENT_VERSION
        self._last_check: datetime | None = None
        self._check_interval_hours = 24

    def check_for_updates(self) -> UpdateInfo | None:
        """Appcast URL'inden güncelleme olup olmadığını kontrol eder.

        Returns:
            UpdateInfo: Güncelleme varsa, None ise güncel.
        """
        try:
            logger.info("update_check_started url=%s", self.appcast_url)

            response = requests.get(self.appcast_url, timeout=10)
            response.raise_for_status()

            appcast = response.json()
            latest = self._parse_appcast(appcast)

            if latest is None:
                logger.info("update_check_no_updates")
                return None

            current = Version(self.current_version)
            if latest.parsed_version > current:
                logger.info(
                    "update_available current=%s latest=%s",
                    self.current_version,
                    latest.version,
                )
                self._last_check = datetime.utcnow()
                return latest
            else:
                logger.info("update_check_up_to_date version=%s", self.current_version)
                return None

        except requests.RequestException as e:
            logger.error("update_check_network_error error=%s", str(e))
            return None
        except Exception as e:
            logger.error("update_check_failed error=%s", str(e))
            return None

    def _parse_appcast(self, appcast: dict[str, Any]) -> UpdateInfo | None:
        """Appcast JSON'unu UpdateInfo'ye dönüştürür."""
        releases = appcast.get("releases", [])
        if not releases:
            return None

        # En son sürümü bul
        latest = max(releases, key=lambda r: Version(r.get("version", "0.0.0")))

        return UpdateInfo(
            version=latest.get("version", ""),
            release_date=latest.get("release_date", ""),
            download_url=latest.get("download_url", ""),
            release_notes=latest.get("release_notes", ""),
            file_size=latest.get("file_size", 0),
            min_version=latest.get("min_version"),
        )

    def should_check(self) -> bool:
        """Son kontrolden bu yana yeterli süre geçti mi?"""
        if self._last_check is None:
            return True

        elapsed = datetime.utcnow() - self._last_check
        return elapsed.total_seconds() > (self._check_interval_hours * 3600)

    def get_current_version(self) -> str:
        """Mevcut sürümü döndürür."""
        return self.current_version

    def create_appcast_template(self) -> dict[str, Any]:
        """Appcast JSON şablonu oluşturur (hosting için)."""
        return {
            "app_name": "Multi-CMS Manager",
            "releases": [
                {
                    "version": self.current_version,
                    "release_date": datetime.utcnow().isoformat(),
                    "download_url": "https://github.com/your-repo/releases/latest",
                    "release_notes": "İlk sürüm",
                    "file_size": 0,
                    "min_version": None,
                },
            ],
        }


class UpdateChecker:
    """Arka plan güncelleme kontrolcüsü.

    QThread kullanarak arka planında güncelleme kontrolü yapar.
    """

    def __init__(self, updater: AutoUpdater, parent=None):
        self.updater = updater
        self.parent = parent
        self._running = False

    def check(self) -> UpdateInfo | None:
        """Senkron güncelleme kontrolü."""
        if not self.updater.should_check():
            return None
        return self.updater.check_for_updates()
