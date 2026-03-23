"""
saas/auth/crypto.py
Shared Fernet encryption for channel credentials.
Single source of truth for key derivation.
"""
import base64
import hashlib

from cryptography.fernet import Fernet

from saas.config import get_settings


def get_fernet() -> Fernet:
    """Get Fernet cipher derived from SECRET_KEY. Used everywhere credentials are encrypted/decrypted."""
    settings = get_settings()
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.secret_key.encode()).digest()
    )
    return Fernet(key)
