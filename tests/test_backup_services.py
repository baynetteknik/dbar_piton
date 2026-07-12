import gzip
import tarfile
from unittest.mock import MagicMock, patch

from src.core.backup.db_backup import DatabaseBackupService
from src.core.backup.file_backup import FileBackupService


@patch("subprocess.Popen")
def test_database_backup_service_success(mock_popen, tmp_path):
    # Setup mock subprocess output
    mock_process = MagicMock()
    mock_process.stdout.read.side_effect = [b"CREATE TABLE test;", b""]
    mock_process.communicate.return_value = (b"", b"")
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    output_file = tmp_path / "db.sql.gz"
    progress_updates = []

    def callback(val):
        progress_updates.append(val)

    config = {
        "db_host": "localhost",
        "db_user": "root",
        "db_pass": "pwd",
        "db_name": "test_db",
    }
    service = DatabaseBackupService(config)
    success = service.backup_to_gzip(
        output_path=output_file,
        progress_callback=callback,
    )

    assert success is True
    assert output_file.exists()
    assert len(progress_updates) > 0

    # Read gzip back to verify it got the mock output
    with gzip.open(output_file, "rb") as f:
        content = f.read()
    assert b"CREATE TABLE test;" in content


@patch("subprocess.Popen")
def test_database_backup_service_failure(mock_popen, tmp_path):
    mock_process = MagicMock()
    mock_process.stdout.read.return_value = b""
    mock_process.stderr.read.return_value = b"Access Denied"
    mock_process.communicate.return_value = (b"", b"Access Denied")
    mock_process.returncode = 1
    mock_popen.return_value = mock_process

    output_file = tmp_path / "failed_db.sql.gz"

    config = {
        "db_host": "localhost",
        "db_user": "invalid_user",
        "db_pass": "pwd",
        "db_name": "test_db",
    }
    service = DatabaseBackupService(config)
    success = service.backup_to_gzip(output_path=output_file)

    assert success is False
    assert not output_file.exists()


def test_file_backup_service(tmp_path):
    # Create mock directory layout
    src_dir = tmp_path / "source"
    src_dir.mkdir()
    (src_dir / "file1.txt").write_text("Hello", encoding="utf-8")
    (src_dir / "subdir").mkdir()
    (src_dir / "subdir" / "file2.txt").write_text("World", encoding="utf-8")

    archive_file = tmp_path / "archive.tar.gz"
    progress_records = []

    def callback(total_bytes):
        progress_records.append(total_bytes)

    success = FileBackupService.compress_directory(
        source_dir=src_dir,
        output_path=archive_file,
        progress_callback=callback,
    )

    assert success is True
    assert archive_file.exists()
    assert len(progress_records) > 0

    # Read archive back
    with tarfile.open(archive_file, "r:gz") as tar:
        names = tar.getnames()
        assert "file1.txt" in names
        assert "subdir/file2.txt" in names
