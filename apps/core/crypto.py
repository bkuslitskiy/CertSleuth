"""SEC-009: app-layer envelope encryption for cert numbers. Fernet (AES128-CBC+HMAC)
keyed from FIELD_ENCRYPTION_KEY (Secret Manager in prod). Empty key = passthrough,
so sqlite dev works before keys exist — production MUST set the key (checked in deploy)."""
from django.conf import settings
from django.db import models


def _fernet():
    if not settings.FIELD_ENCRYPTION_KEY:
        return None
    from cryptography.fernet import Fernet
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


PREFIX = "enc:"


def encrypt(value: str) -> str:
    f = _fernet()
    if not value or f is None:
        return value
    return PREFIX + f.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    f = _fernet()
    if not value or not value.startswith(PREFIX) or f is None:
        return value
    return f.decrypt(value[len(PREFIX):].encode()).decode()


class EncryptedCharField(models.CharField):
    """Encrypts on write, decrypts on read. DB column holds ciphertext (longer than
    plaintext — size max_length accordingly; 4x is safe)."""

    def get_prep_value(self, value):
        return encrypt(super().get_prep_value(value) or "")

    def from_db_value(self, value, expression, connection):
        return decrypt(value or "")
