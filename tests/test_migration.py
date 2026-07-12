from unittest.mock import MagicMock, patch

from src.core.backup.migration import MigrationService


@patch("paramiko.SSHClient")
def test_migration_service_connection_password(mock_ssh):
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client

    ssh_config = {
        "ssh_host": "127.0.0.1",
        "ssh_port": 2222,
        "ssh_user": "testuser",
        "ssh_pass": "testpass",
    }

    service = MigrationService(ssh_config)
    client = service._connect()

    assert client == mock_client
    mock_client.connect.assert_called_once_with(
        "127.0.0.1",
        port=2222,
        username="testuser",
        password="testpass",
        timeout=15,
    )


@patch("paramiko.SSHClient")
def test_migration_service_execute_remote_command(mock_ssh):
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client

    # Mock exec_command output
    mock_stdin = MagicMock()
    mock_stdout = MagicMock()
    mock_stderr = MagicMock()

    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stdout.read.return_value = b"Remote Command Success"
    mock_stderr.read.return_value = b""

    mock_client.exec_command.return_value = (
        mock_stdin,
        mock_stdout,
        mock_stderr,
    )

    ssh_config = {
        "ssh_host": "127.0.0.1",
        "ssh_user": "testuser",
    }
    service = MigrationService(ssh_config)
    exit_status, out_str, err_str = service.execute_remote_command("ls -la")

    assert exit_status == 0
    assert out_str == "Remote Command Success"
    assert err_str == ""


@patch("paramiko.SSHClient")
def test_migration_service_upload_file_via_sftp(mock_ssh, tmp_path):
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client

    mock_sftp = MagicMock()
    mock_client.open_sftp.return_value = mock_sftp

    # Create dummy local file
    local_file = tmp_path / "migration_backup.tar.gz"
    local_file.write_text("dummy archive content", encoding="utf-8")

    ssh_config = {
        "ssh_host": "127.0.0.1",
        "ssh_user": "testuser",
    }
    service = MigrationService(ssh_config)

    progress_calls = []

    def callback(current, total):
        progress_calls.append((current, total))

    success = service.upload_file_via_sftp(
        local_file=local_file,
        remote_dir="/var/www/backups",
        progress_callback=callback,
    )

    assert success is True
    # Verify sftp directory change/check is performed
    mock_sftp.chdir.assert_called_once_with("/var/www/backups")
    # Verify file upload is triggered
    mock_sftp.put.assert_called_once_with(
        localpath=str(local_file),
        remotepath="/var/www/backups/migration_backup.tar.gz",
        callback=callback,
    )


@patch("paramiko.SSHClient")
def test_migration_service_disconnect(mock_ssh):
    mock_client = MagicMock()
    mock_ssh.return_value = mock_client

    ssh_config = {
        "ssh_host": "127.0.0.1",
        "ssh_user": "testuser",
    }
    service = MigrationService(ssh_config)
    service._connect()  # Establish connection
    service.disconnect()  # Disconnect

    mock_client.close.assert_called_once()
    assert service._ssh_client is None
