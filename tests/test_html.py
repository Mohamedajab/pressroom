from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client

from publishing import services
from publishing.models import Workspace
from publishing.rendering import render_body


def test_markdown_sanitizes_scripts_event_handlers_and_javascript_links():
    html = render_body(
        '<script>alert(1)</script><img src=x onerror="alert(2)">\n\n[bad](javascript:alert(3))\n\n**good**'
    )
    assert "<script" not in html
    assert "onerror" not in html
    assert "javascript:" not in html
    assert "<strong>good</strong>" in html


@pytest.mark.parametrize("route", ["", "activity/", "team/"])
def test_workspace_pages_render(client, team, page, route):
    _, users = team
    client.force_login(users["editor"])
    response = client.get(f"/workspace/studio/{route}")
    assert response.status_code == 200
    assert "Pressroom" in response.content.decode()


def test_detail_editor_and_creation_render(client, team, page):
    _, users = team
    client.force_login(users["author"])
    for route in [
        f"/workspace/studio/pages/{page.pk}/",
        f"/workspace/studio/pages/{page.pk}/edit/",
        "/workspace/studio/new/",
    ]:
        assert client.get(route).status_code == 200


def test_form_create_edit_and_submit(client, team):
    workspace, users = team
    client.force_login(users["author"])
    response = client.post(
        "/workspace/studio/new/", {"title": "Hello", "slug": "hello", "body": "World"}
    )
    assert response.status_code == 302
    page = workspace.pages.get()
    response = client.post(
        f"/workspace/studio/pages/{page.pk}/edit/",
        {"title": "Edited", "body": "New", "expected_version": 1},
    )
    assert response.status_code == 302
    response = client.post(
        f"/workspace/studio/pages/{page.pk}/action/", {"expected_version": 2, "action": "submit"}
    )
    assert response.status_code == 302
    page.refresh_from_db()
    assert page.status == "review"


def test_stale_form_preserves_submitted_text(client, team, page):
    workspace, users = team
    client.force_login(users["author"])
    services.update_page(
        users["author"], workspace, page.pk, expected_version=1, title="New", body="New"
    )
    response = client.post(
        f"/workspace/studio/pages/{page.pk}/edit/",
        {"title": "Unsaved work", "body": "Keep me", "expected_version": 1},
    )
    assert response.status_code == 409
    assert b"Keep me" in response.content


def test_html_enforces_csrf(team, page):
    _, users = team
    browser = Client(enforce_csrf_checks=True)
    browser.force_login(users["author"])
    assert (
        browser.post(
            f"/workspace/studio/pages/{page.pk}/action/",
            {"action": "submit", "expected_version": 1},
        ).status_code
        == 403
    )


def test_public_html_uses_approved_snapshot(client, team, page):
    workspace, users = team
    page = services.transition(
        users["author"], workspace, page.pk, expected_version=1, action="submit"
    )
    page = services.transition(
        users["editor"], workspace, page.pk, expected_version=page.version, action="publish"
    )
    services.update_page(
        users["author"],
        workspace,
        page.pk,
        expected_version=page.version,
        title="SECRET DRAFT",
        body="Private",
    )
    response = client.get("/sites/studio/original/")
    assert b"Original title" in response.content
    assert b"SECRET DRAFT" not in response.content


def test_viewer_and_outsider_cannot_open_editor(client, team, page):
    _, users = team
    for role in ["viewer", "outsider"]:
        client.force_login(users[role])
        assert client.get(f"/workspace/studio/pages/{page.pk}/edit/").status_code == 403


def test_health_checks_database(client, db):
    assert client.get("/health/").json() == {"status": "ok"}


def test_demo_seed_is_idempotent(db, settings):
    settings.DEBUG = True
    call_command("seed_demo", password="Local-demo-only-123!", stdout=StringIO())
    call_command("seed_demo", password="Local-demo-only-123!", stdout=StringIO())
    assert Workspace.objects.get(slug="fieldnotes").pages.count() == 8


def test_demo_seed_rejected_in_production(db, settings):
    from django.core.management.base import CommandError

    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_demo", password="No", stdout=StringIO())
