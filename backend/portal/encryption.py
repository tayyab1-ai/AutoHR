import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    raw = (
        getattr(settings, "TOKEN_ENCRYPTION_KEY", None)
        or settings.SECRET_KEY
        or "dev-only-secret-key-for-autohr-frontend-demo-change-me"
    )
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_text(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_text(cipher: str) -> str:
    if not cipher:
        return ""
    try:
        return _fernet().decrypt(cipher.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
