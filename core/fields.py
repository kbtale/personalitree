"""Custom model fields."""

from typing import Any

from django.db import models

from core.utils.crypto import decrypt_value, encrypt_value


class EncryptedTextField(models.TextField):
    """A text field whose value is encrypted at rest."""

    def from_db_value(
        self,
        value: str | None,
        expression: Any,
        connection: Any,
    ) -> str | None:
        if value is None:
            return None
        return decrypt_value(value)

    def get_prep_value(self, value: str | None) -> str | None:
        if not value:
            return value
        return encrypt_value(value)
