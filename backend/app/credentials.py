"""
Credential storage via OS keyring (Keychain / Credential Manager / Secret Service).
Credentials are NEVER written to SQLite, log files, or env vars by this module.
"""
import sys

_SERVICE = "com.r3thinklabs.migration-tool"
_USERNAME_KEY = "alsoenergy_username"
_PASSWORD_KEY = "alsoenergy_password"

# Keyring may not be available in dev without install; fail gracefully.
try:
    import keyring as _keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False


def _kr():
    if not _KEYRING_AVAILABLE:
        raise RuntimeError("keyring package not available")
    return _keyring


def save(username: str, password: str) -> None:
    kr = _kr()
    kr.set_password(_SERVICE, _USERNAME_KEY, username)
    kr.set_password(_SERVICE, _PASSWORD_KEY, password)


def load() -> tuple[str, str]:
    """Return (username, password). Returns ('', '') if not stored."""
    if not _KEYRING_AVAILABLE:
        return ("", "")
    kr = _kr()
    username = kr.get_password(_SERVICE, _USERNAME_KEY) or ""
    password = kr.get_password(_SERVICE, _PASSWORD_KEY) or ""
    return (username, password)


def delete() -> None:
    if not _KEYRING_AVAILABLE:
        return
    kr = _kr()
    try:
        kr.delete_password(_SERVICE, _USERNAME_KEY)
    except Exception:
        pass
    try:
        kr.delete_password(_SERVICE, _PASSWORD_KEY)
    except Exception:
        pass


def has_credentials() -> bool:
    username, password = load()
    return bool(username and password)
