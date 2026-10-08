import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from publishing.models import Membership, Workspace
from publishing.services import create_page


@pytest.fixture(autouse=True)
def fast_test_passwords(settings):
    # Production retains Django's default secure hashers. Test accounts are disposable.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def clean_throttle_cache():
    cache.clear()


@pytest.fixture
def team(db):
    workspace = Workspace.objects.create(name="Test studio", slug="studio")
    users = {}
    for role in ["owner", "editor", "author", "viewer"]:
        user = get_user_model().objects.create_user(username=role, password="Test-password-492!")
        Membership.objects.create(workspace=workspace, user=user, role=role)
        users[role] = user
    users["outsider"] = get_user_model().objects.create_user(username="outsider")
    return workspace, users


@pytest.fixture
def page(team):
    workspace, users = team
    return create_page(
        users["author"],
        workspace,
        title="Original title",
        slug="original",
        body="Original body",
        excerpt="Original excerpt",
    )


@pytest.fixture
def api_client():
    return APIClient()
