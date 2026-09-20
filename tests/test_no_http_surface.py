from django.urls import Resolver404, resolve
import pytest


def test_there_is_no_admin_surface():
    with pytest.raises(Resolver404):
        resolve("/admin/")


def test_there_are_no_urls_at_all():
    from personalitree import urls

    assert urls.urlpatterns == []
