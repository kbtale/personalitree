"""Encrypt credential values that are still stored in plaintext."""

from typing import Any

from django.core.management.base import BaseCommand

from core.models import BurnerAccount


class Command(BaseCommand):
    help = "Re-save burner accounts so plaintext passwords become ciphertext."

    def handle(self, *args: Any, **options: Any) -> None:
        re_encrypted = 0
        for account in BurnerAccount.objects.all():
            if not account.password:
                continue
            account.save(update_fields=["password"])
            re_encrypted += 1

        self.stdout.write(f"Re-encrypted {re_encrypted} burner account(s)")
