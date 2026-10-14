from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from publishing.demo import cleanup_expired
from publishing.models import DemoSession, Workspace

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def enable_demo(settings):
    settings.DEMO_ENABLED = True


def test_demo_is_opt_in_and_post_only(client, settings):
    settings.DEMO_ENABLED = False
    assert client.get("/demo/").status_code == 404
    assert client.post("/demo/start/").status_code == 404
    settings.DEMO_ENABLED = True
    assert client.get("/demo/start/").status_code == 405


def test_visitors_have_isolated_workspaces_and_can_switch_roles(client):
    other = Client()
    first = client.post("/demo/start/")
    second = other.post("/demo/start/")
    assert first.url != second.url
    assert client.get(second.url).status_code == 403
    demo = DemoSession.objects.get(author_id=client.session["_auth_user_id"])
    assert not demo.author.has_usable_password()
    assert b"Author access" in client.get(first.url).content
    assert client.post("/demo/switch/", {"role": "editor"}).url == first.url
    assert b"Editor access" in client.get(first.url).content
    assert client.post("/demo/start/").url == first.url
    assert DemoSession.objects.count() == 2


def test_demo_creation_enforces_csrf():
    client = Client(enforce_csrf_checks=True)
    assert client.post("/demo/start/").status_code == 403


def test_expired_demo_logs_out_and_cleanup_preserves_real_workspaces(client):
    real = Workspace.objects.create(name="Real", slug="real")
    response = client.post("/demo/start/")
    demo = DemoSession.objects.get()
    ids = (demo.author_id, demo.editor_id)
    DemoSession.objects.filter(pk=demo.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    assert client.get(response.url).url == "/demo/"
    assert "_auth_user_id" not in client.session
    assert cleanup_expired() == 1
    assert Workspace.objects.filter(pk=real.pk).exists()
    assert not get_user_model().objects.filter(pk__in=ids).exists()


def test_demo_blocks_team_changes_and_bounds_writes(client):
    response = client.post("/demo/start/")
    demo = DemoSession.objects.get()
    assert (
        client.post(response.url + "team/", {"username": "owner", "role": "owner"}).status_code
        == 403
    )
    DemoSession.objects.filter(pk=demo.pk).update(writes=60)
    assert client.post(response.url + "new/", {}).status_code == 429
    assert client.post("/demo/switch/", {"role": "editor"}).status_code == 302


def test_demo_publishes_approved_snapshot_and_keeps_drafts_private(client):
    client.post("/demo/start/")
    demo = DemoSession.objects.get()
    base = f"/sites/{demo.workspace.slug}/"
    assert client.get(base + "unfinished-ideas/").status_code == 200
    assert client.get(base + "studio-notes/").status_code == 404
