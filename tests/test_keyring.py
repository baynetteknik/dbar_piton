from unittest.mock import patch

import keyring

from src.core.security.keyring_store import (
    delete_api_key,
    get_api_key,
    save_api_key,
)


@patch("keyring.set_password")
def test_save_api_key(mock_set):
    save_api_key("test_site_account", "api_val_123")
    mock_set.assert_called_once_with(
        "multi_cms_manager", "test_site_account", "api_val_123",
    )


@patch("keyring.get_password")
def test_get_api_key(mock_get):
    mock_get.return_value = "secret_key"
    val = get_api_key("site_account")
    assert val == "secret_key"
    mock_get.assert_called_once_with("multi_cms_manager", "site_account")


@patch("keyring.delete_password")
def test_delete_api_key(mock_delete):
    delete_api_key("site_account")
    mock_delete.assert_called_once_with("multi_cms_manager", "site_account")


@patch("keyring.delete_password")
def test_delete_api_key_not_found(mock_delete):
    # Simulate PasswordDeleteError when password is not found in store
    mock_delete.side_effect = keyring.errors.PasswordDeleteError("Not found")
    # Should fail silently without raising exception
    delete_api_key("nonexistent_account")
    mock_delete.assert_called_once_with(
        "multi_cms_manager", "nonexistent_account",
    )
