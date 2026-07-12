import json
from unittest.mock import patch

from src.core.backup.orchestrator import BackupOrchestrator


@patch("src.core.backup.db_backup.DatabaseBackupService.backup_to_gzip")
@patch("src.core.backup.file_backup.FileBackupService.compress_directory")
def test_backup_orchestrator(
    mock_compress_directory, mock_backup_to_gzip, tmp_path,
):
    # Setup mocks
    def fake_backup_to_gzip(output_path, progress_callback=None):
        with open(output_path, "w") as f:
            f.write("dummy db dump contents")
        return True

    mock_backup_to_gzip.side_effect = fake_backup_to_gzip

    def fake_compress_directory(source_dir, output_path, progress_callback=None):
        # Write dummy file to output path to simulate tar.gz creation
        with open(output_path, "w") as f:
            f.write("dummy tar contents")
        return True

    mock_compress_directory.side_effect = fake_compress_directory

    db_config = {
        "db_host": "localhost",
        "db_name": "test_db",
        "db_user": "root",
        "db_pass": "pass",
    }

    orchestrator = BackupOrchestrator(
        cms_type="woocommerce",
        db_config=db_config,
        source_dir=tmp_path / "source",
        backup_root=tmp_path,
        retention_count=5,
    )

    # Run backup orchestration
    backup_path = orchestrator.run_full_backup()

    assert backup_path is not None
    assert backup_path.exists()
    metadata_file = backup_path / "metadata.json"
    assert metadata_file.exists()

    # Read and assert metadata schema
    with open(metadata_file, encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["cms_type"] == "woocommerce"
    assert meta["database"] is not None
    assert meta["database"]["filename"].startswith("database_")
    assert meta["files"] is not None
    assert meta["files"]["filename"].startswith("files_")


def test_backup_orchestrator_retention(tmp_path):
    orchestrator = BackupOrchestrator(
        cms_type="woocommerce",
        db_config={},
        source_dir=tmp_path / "source",
        backup_root=tmp_path,
        retention_count=3,
    )

    # Create 6 dummy backup directories
    # Sadece 'backup_' ile başlayan klasörleri listeler ve sıralar
    cms_dir = tmp_path / "woocommerce"
    cms_dir.mkdir(parents=True, exist_ok=True)

    for i in range(6):
        # time-stamps in names: backup_0, backup_1, ...
        # Chronological sort will delete backup_0, backup_1, backup_2
        folder_path = cms_dir / f"backup_{i}"
        folder_path.mkdir()
        # Add a dummy file inside so it's not empty
        (folder_path / "dummy.txt").write_text("test")

    # We want to retain max 3 backups
    orchestrator.enforce_retention()

    # Check remaining subdirs (only the 3 newest should remain: 3, 4, 5)
    remaining = [d.name for d in cms_dir.iterdir() if d.is_dir()]
    assert len(remaining) == 3
    assert "backup_0" not in remaining
    assert "backup_1" not in remaining
    assert "backup_2" not in remaining
    assert "backup_3" in remaining
    assert "backup_4" in remaining
    assert "backup_5" in remaining
