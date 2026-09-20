from cryptography.fernet import Fernet
import pytest

from core.constants import ConfigKey
from core.exceptions import ConfigurationError
from core.fields import EncryptedTextField
from core.utils.crypto import decrypt_value, encrypt_value

pytestmark = pytest.mark.django_db

KEY = Fernet.generate_key().decode("utf-8")


def _set_key(monkeypatch, key: str | None) -> None:
    if key is None:
        monkeypatch.delenv(ConfigKey.FIELD_ENCRYPTION_KEY, raising=False)
    else:
        monkeypatch.setenv(ConfigKey.FIELD_ENCRYPTION_KEY, key)


def test_value_round_trips(monkeypatch):
    _set_key(monkeypatch, KEY)

    encrypted = encrypt_value("s3cret")

    assert encrypted != "s3cret"
    assert encrypted.startswith("gAAAAA")
    assert decrypt_value(encrypted) == "s3cret"


def test_missing_key_is_reported(monkeypatch):
    _set_key(monkeypatch, None)

    with pytest.raises(ConfigurationError):
        encrypt_value("s3cret")


def test_invalid_key_is_reported(monkeypatch):
    _set_key(monkeypatch, "not-a-fernet-key")

    with pytest.raises(ConfigurationError):
        encrypt_value("s3cret")


def test_wrong_key_cannot_decrypt(monkeypatch):
    _set_key(monkeypatch, KEY)
    encrypted = encrypt_value("s3cret")
    _set_key(monkeypatch, Fernet.generate_key().decode("utf-8"))

    with pytest.raises(ConfigurationError):
        decrypt_value(encrypted)


def test_plaintext_written_before_encryption_is_passed_through(monkeypatch):
    _set_key(monkeypatch, KEY)

    assert decrypt_value("stored-in-the-clear") == "stored-in-the-clear"


def test_field_encrypts_on_write_and_decrypts_on_read(monkeypatch):
    _set_key(monkeypatch, KEY)
    field = EncryptedTextField()

    stored = field.get_prep_value("s3cret")

    assert stored != "s3cret"
    assert field.from_db_value(stored, None, None) == "s3cret"


def test_field_leaves_empty_values_alone(monkeypatch):
    _set_key(monkeypatch, KEY)
    field = EncryptedTextField()

    assert field.get_prep_value("") == ""
    assert field.get_prep_value(None) is None
