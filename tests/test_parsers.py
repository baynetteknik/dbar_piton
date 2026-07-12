from src.core.backup.parsers import CMSConfigParser


def test_dolibarr_config_parser(tmp_path):
    # Create mock Dolibarr conf.php
    conf_content = """<?php
$dolibarr_main_db_host='localhost';
$dolibarr_main_db_name='dolibarr_db';
$dolibarr_main_db_user='dolibarr_user';
$dolibarr_main_db_pass='dolibarr_pass';
$dolibarr_main_db_port='3306';
$dolibarr_main_data_dir='/var/www/dolibarr/documents';
"""
    config_file = tmp_path / "conf.php"
    config_file.write_text(conf_content, encoding="utf-8")

    parsed = CMSConfigParser.parse_dolibarr(config_file)
    assert parsed is not None
    assert parsed["db_host"] == "localhost"
    assert parsed["db_name"] == "dolibarr_db"
    assert parsed["db_user"] == "dolibarr_user"
    assert parsed["db_pass"] == "dolibarr_pass"
    assert parsed["db_port"] == 3306


def test_dolibarr_parser_missing_file(tmp_path):
    config_file = tmp_path / "nonexistent_conf.php"
    parsed = CMSConfigParser.parse_dolibarr(config_file)
    assert parsed is None


def test_wordpress_config_parser(tmp_path):
    # Create mock WordPress wp-config.php
    wp_content = """<?php
define( 'DB_NAME', 'wp_db' );
define( 'DB_USER', 'wp_user' );
define( 'DB_PASSWORD', 'wp_pass' );
define( 'DB_HOST', 'localhost:3307' );
"""
    config_file = tmp_path / "wp-config.php"
    config_file.write_text(wp_content, encoding="utf-8")

    parsed = CMSConfigParser.parse_wordpress(config_file)
    assert parsed is not None
    assert parsed["db_host"] == "localhost"
    assert parsed["db_port"] == 3307
    assert parsed["db_name"] == "wp_db"
    assert parsed["db_user"] == "wp_user"
    assert parsed["db_pass"] == "wp_pass"


def test_wordpress_parser_missing_file(tmp_path):
    config_file = tmp_path / "nonexistent_wp-config.php"
    parsed = CMSConfigParser.parse_wordpress(config_file)
    assert parsed is None
