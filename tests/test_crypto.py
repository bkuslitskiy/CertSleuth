"""SEC-009: encryption roundtrip + passthrough-without-key behavior."""
from apps.core import crypto


def test_passthrough_without_key(settings):
    settings.FIELD_ENCRYPTION_KEY = ""
    assert crypto.encrypt("ABC-123") == "ABC-123"
    assert crypto.decrypt("ABC-123") == "ABC-123"


def test_roundtrip_with_key(settings):
    from cryptography.fernet import Fernet
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    ct = crypto.encrypt("ABC-123")
    assert ct.startswith(crypto.PREFIX) and "ABC-123" not in ct
    assert crypto.decrypt(ct) == "ABC-123"
