import pytest

from core.models import Target


@pytest.fixture
def target() -> Target:
    return Target.objects.create(seed_username="seed_user")
