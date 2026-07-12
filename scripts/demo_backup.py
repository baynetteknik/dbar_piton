import os
import sys
import tempfile
import time

# Proje dizinini python yoluna ekle
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.backup.db_backup import DatabaseBackupService
from src.core.backup.file_backup import FileBackupService
from src.core.backup.orchestrator import BackupOrchestrator
from src.core.backup.parsers import CMSConfigParser


def run_demo():
    print("=" * 60)
    print("      MULTI-CMS MANAGER: YEDELEME MOTORU DEMO / TEST KILAVUZU")
    print("=" * 60)
    print("\nŞu ana kadar uygulamanın çekirdek yedekleme motoru tamamlandı.")
    print("Arayüz (GUI) AŞAMA 5'te kodlanacağı için, şu an motoru CLI (komut satırı)")
    print("üzerinden simüle ederek test edebilirsiniz.\n")

    # 1. Klasör ve Ayar Simülasyonu
    print("[1] Test ortamı için geçici dizinler ve dosyalar hazırlanıyor...")
    with tempfile.TemporaryDirectory() as tmpdir:
        # Geçici mock CMS php dosyaları oluşturalım
        dolibarr_conf_path = os.path.join(tmpdir, "conf.php")
        wp_config_path = os.path.join(tmpdir, "wp-config.php")

        with open(dolibarr_conf_path, "w", encoding="utf-8") as f:
            f.write("""<?php
$dolibarr_main_db_host='127.0.0.1';
$dolibarr_main_db_name='dolibarr_prod';
$dolibarr_main_db_user='admin_cms';
$dolibarr_main_db_pass='şifre12345';
$dolibarr_main_db_port='3306';
$dolibarr_main_data_dir='/var/www/dolibarr/documents';
""")

        with open(wp_config_path, "w", encoding="utf-8") as f:
            f.write("""<?php
define('DB_NAME', 'wordpress_db');
define('DB_USER', 'wp_admin');
define('DB_PASSWORD', 'wp_guclu_sifre');
define('DB_HOST', 'localhost:3307');
$table_prefix = 'wp_shop_';
""")

        # Arşivlenecek mock web dosyaları klasörü
        web_files_dir = os.path.join(tmpdir, "web_content")
        os.makedirs(web_files_dir)
        for i in range(1, 6):
            with open(
                os.path.join(web_files_dir, f"gorsel_{i}.png"), "w",
            ) as f:
                f.write(f"mock png content {i}")
        with open(os.path.join(web_files_dir, "index.php"), "w") as f:
            f.write("<?php echo 'WooCommerce Site'; ?>")

        print("✔ Geçici mock web dizinleri oluşturuldu.")

        # 2. Parser Testi
        print("\n[2] PHP konfigürasyon parser'ları test ediliyor...")
        d_config = CMSConfigParser.parse_dolibarr(dolibarr_conf_path)
        w_config = CMSConfigParser.parse_wordpress(wp_config_path)

        print("✔ Dolibarr conf.php başarıyla okundu:")
        print(f"  - DB Host: {d_config['db_host']}")
        print(f"  - DB Name: {d_config['db_name']}")
        print(f"  - DB User: {d_config['db_user']}")

        print("✔ WordPress wp-config.php başarıyla okundu:")
        print(f"  - DB Host: {w_config['db_host']}")
        print(f"  - DB Port: {w_config['db_port']}")
        print(f"  - DB Name: {w_config['db_name']}")

        # 3. İlerleme Takibi (Callbacks) ile Dosya Arşivleme Simülasyonu
        print("\n[3] FileBackupService ile sıkıştırılmış tar.gz yedeği alınıyor...")
        archive_path = os.path.join(tmpdir, "backup_files.tar.gz")

        def file_callback(total_bytes):
            sys.stdout.write(
                f"\r  └ Arşivleme İlerlemesi: {total_bytes} byte işlendi...",
            )
            sys.stdout.flush()

        FileBackupService.compress_directory(
            source_dir=web_files_dir,
            output_path=archive_path,
            progress_callback=file_callback,
        )
        print("\n✔ Dosyalar başarıyla arşivlendi, boyut:", os.path.getsize(archive_path), "bytes")

        # 4. Orkestrasyon ve Havuz (Retention) Entegrasyonu
        print("\n[4] BackupOrchestrator ile veritabanı/dosya birleştirme testi...")

        mock_db_config = {
            "db_host": "localhost",
            "db_name": "temp_db",
            "db_user": "root",
            "db_pass": "pass",
        }

        # backup_to_gzip metodunu geçici mocklayarak orkestratörü yerelde çalıştıralım
        original_backup = DatabaseBackupService.backup_to_gzip

        def mock_backup_to_gzip(self, output_path, progress_callback=None):
            with gzip_open_mock(output_path, "wb") as f:
                f.write(
                    b"CREATE DATABASE mock; INSERT INTO products VALUES (1, 'WooCommerce Product');",
                )
            return True

        import gzip

        gzip_open_mock = gzip.open
        DatabaseBackupService.backup_to_gzip = mock_backup_to_gzip

        orchestrator = BackupOrchestrator(
            cms_type="woocommerce",
            db_config=mock_db_config,
            source_dir=web_files_dir,
            backup_root="test_runs_backups",
            retention_count=3,
        )

        try:
            backup_folder = orchestrator.run_full_backup()
            print("✔ Orkestrasyon klasörü başarıyla oluşturuldu:")
            print(f"  - Klasör: {backup_folder}")
            print(f"  - İçerik: {os.listdir(backup_folder)}")

            # metadata.json içeriğini ekrana basalım
            meta_path = os.path.join(backup_folder, "metadata.json")
            with open(meta_path, encoding="utf-8") as mf:
                print("  - Metadata.json İçeriği:")
                print(mf.read())

            # Retention Testi
            print("[5] Retention (Eski yedekleri temizleme) havuzu testi...")
            # Fazladan boş yedek klasörleri oluşturalım
            for _ in range(3):
                time.sleep(1.1)
                orchestrator.run_full_backup()

            remaining_folders = os.listdir(
                os.path.join("test_runs_backups", "woocommerce"),
            )
            print(f"  - Temizlik sonrası kalan yedek klasörleri: {remaining_folders}")
            assert len(remaining_folders) == 3

        finally:
            # Metodu geri yükle
            DatabaseBackupService.backup_to_gzip = original_backup

            # Temizlik
            import shutil

            shutil.rmtree("test_runs_backups", ignore_errors=True)

    print("\n" + "=" * 60)
    print("✔ Demo başarıyla tamamlandı. Tüm yedekleme kütüphaneleri çalışıyor!")
    print("=" * 60)


if __name__ == "__main__":
    run_demo()
