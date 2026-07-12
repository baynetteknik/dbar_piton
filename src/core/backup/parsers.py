import re
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


class CMSConfigParser:
    """Dolibarr ve WordPress konfigürasyon dosyalarından veri ayıklayan servis."""

    @staticmethod
    def parse_dolibarr(file_path: Path | str) -> dict[str, Any] | None:
        """Dolibarr conf.php dosyasını okur ve veritabanı bağlantı bilgilerini ayıklar."""
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error("dolibarr_conf_not_found", path=str(file_path))
            return None

        try:
            content = file_path.read_text(encoding="utf-8")

            # PHP değişkenlerini yakalamak için esnek Regex kalıpları
            patterns = {
                "db_host": r"\$dolibarr_main_db_host\s*=\s*['\"](.*?)['\"];",
                "db_name": r"\$dolibarr_main_db_name\s*=\s*['\"](.*?)['\"];",
                "db_user": r"\$dolibarr_main_db_user\s*=\s*['\"](.*?)['\"];",
                "db_pass": r"\$dolibarr_main_db_pass\s*=\s*['\"](.*?)['\"];",
                "db_port": r"\$dolibarr_main_db_port\s*=\s*['\"](.*?)['\"];",
                "data_dir": r"\$dolibarr_main_data_dir\s*=\s*['\"](.*?)['\"];",
            }

            result = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if key == "db_port":
                    result[key] = int(match.group(1)) if match else 3306
                else:
                    result[key] = match.group(1) if match else ""

            logger.info(
                "dolibarr_conf_parsed_successfully",
                host=result.get("db_host"),
                db=result.get("db_name"),
            )
            return result

        except Exception as e:
            logger.critical(
                "dolibarr_conf_parse_failed",
                error=str(e),
                path=str(file_path),
            )
            raise

    @staticmethod
    def parse_wordpress(file_path: Path | str) -> dict[str, Any] | None:
        """WordPress wp-config.php dosyasını okur ve DB define kurallarını ayıklar."""
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error("wp_config_not_found", path=str(file_path))
            return None

        try:
            content = file_path.read_text(encoding="utf-8")

            # WordPress define('NAME', 'VALUE'); kalıpları için Regex
            patterns = {
                "db_host": r"define\s*\(\s*['\"]DB_HOST['\"]\s*,\s*['\"](.*?)['\"]\s*\);",
                "db_name": r"define\s*\(\s*['\"]DB_NAME['\"]\s*,\s*['\"](.*?)['\"]\s*\);",
                "db_user": r"define\s*\(\s*['\"]DB_USER['\"]\s*,\s*['\"](.*?)['\"]\s*\);",
                "db_pass": r"define\s*\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"](.*?)['\"]\s*\);",
            }

            result = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, content, re.IGNORECASE)
                result[key] = match.group(1) if match else ""

            # Port ayrımı (Örn: localhost:3307 durumu için)
            if ":" in result.get("db_host", ""):
                host_parts = result["db_host"].split(":")
                result["db_host"] = host_parts[0]
                result["db_port"] = int(host_parts[1])
            else:
                result["db_port"] = 3306

            logger.info(
                "wordpress_conf_parsed_successfully",
                host=result.get("db_host"),
                db=result.get("db_name"),
            )
            return result

        except Exception as e:
            logger.critical(
                "wordpress_conf_parse_failed",
                error=str(e),
                path=str(file_path),
            )
            raise
