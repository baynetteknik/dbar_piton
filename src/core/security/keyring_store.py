
import keyring

SERVICE_NAME = "multi_cms_manager"


def save_api_key(account_name: str, api_key: str) -> None:
    """Saves the API key securely to the OS Credential Store (Windows Credential Manager / macOS Keychain)."""
    keyring.set_password(SERVICE_NAME, account_name, api_key)


def get_api_key(account_name: str) -> str | None:
    """Retrieves the API key from the OS Credential Store.

    Returns None if not found.
    """
    return keyring.get_password(SERVICE_NAME, account_name)


def delete_api_key(account_name: str) -> None:
    """Removes the API key from the OS Credential Store.

    Fails silently if not found.
    """
    try:
        keyring.delete_password(SERVICE_NAME, account_name)
    except keyring.errors.PasswordDeleteError:
        pass
