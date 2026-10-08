from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError

from publishing import services
from publishing.models import Workspace


def test_owner_manages_members_through_browser(client, team):
    workspace, users = team
    client.force_login(users["owner"])
    result = client.post("/workspace/studio/team/", {"username": "outsider", "role": "viewer"})
    assert result.status_code == 302
    assert workspace.memberships.get(user=users["outsider"]).role == "viewer"
    result = client.post("/workspace/studio/team/", {"username": "owner", "role": "viewer"})
    assert result.status_code == 200
    assert b"at least one owner" in result.content


def test_nonowner_cannot_modify_team_via_browser(client, team):
    workspace, users = team
    client.force_login(users["editor"])
    response = client.post("/workspace/studio/team/", {"username": "outsider", "role": "owner"})
    assert response.status_code == 403
    assert not workspace.memberships.filter(user=users["outsider"]).exists()


def test_unknown_team_username_is_validation_error(client, team):
    _, users = team
    client.force_login(users["owner"])
    result = client.post("/workspace/studio/team/", {"username": "missing", "role": "viewer"})
    assert result.status_code == 200
    assert b"does not exist" in result.content


def test_home_redirects_to_workspace_or_shows_no_access(client, team):
    _, users = team
    client.force_login(users["owner"])
    assert client.get("/").url == "/workspace/studio/"
    client.force_login(users["outsider"])
    assert b"Your workspace is waiting" in client.get("/").content


def test_browser_filters_pages(client, team, page):
    _, users = team
    client.force_login(users["viewer"])
    assert b"Original title" in client.get("/workspace/studio/?q=Original&status=draft").content
    assert b"Original title" not in client.get("/workspace/studio/?q=absent").content


def test_browser_reports_invalid_transition(client, team, page):
    _, users = team
    client.force_login(users["editor"])
    url = f"/workspace/studio/pages/{page.pk}/action/"
    result = client.post(url, {"action": "publish", "expected_version": 1}, follow=True)
    assert b"for review first" in result.content
    result = client.post(
        url, {"action": "restore", "expected_version": 1, "number": 999}, follow=True
    )
    assert b"does not exist" in result.content


def test_health_returns_503_without_database_details(client, db):
    with patch(
        "publishing.views.connection.cursor", side_effect=RuntimeError("secret database error")
    ):
        response = client.get("/health/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert b"secret" not in response.content


def test_bootstrap_existing_owner_and_duplicate_workspace(db):
    owner = get_user_model().objects.create_user(username="mohamed")
    call_command(
        "bootstrap_workspace", "my-studio", name="My studio", username="mohamed", stdout=StringIO()
    )
    assert Workspace.objects.get(slug="my-studio").memberships.get().user == owner
    with pytest.raises(CommandError):
        call_command(
            "bootstrap_workspace",
            "my-studio",
            name="Duplicate",
            username="mohamed",
            stdout=StringIO(),
        )


def test_bootstrap_prompts_for_valid_new_owner_password(db):
    with patch(
        "publishing.management.commands.bootstrap_workspace.getpass.getpass",
        return_value="New-owner-safe-password-723!",
    ):
        call_command(
            "bootstrap_workspace",
            "new-studio",
            name="New studio",
            username="new-owner",
            stdout=StringIO(),
        )
    assert (
        get_user_model()
        .objects.get(username="new-owner")
        .check_password("New-owner-safe-password-723!")
    )


def test_bootstrap_password_mismatch_rolls_back(db):
    with patch(
        "publishing.management.commands.bootstrap_workspace.getpass.getpass",
        side_effect=["first", "second"],
    ):
        with pytest.raises(CommandError):
            call_command(
                "bootstrap_workspace",
                "bad-studio",
                name="Bad",
                username="bad-owner",
                stdout=StringIO(),
            )
    assert not Workspace.objects.filter(slug="bad-studio").exists()
    assert not get_user_model().objects.filter(username="bad-owner").exists()


def test_scheduler_command_reports_count(db):
    output = StringIO()
    call_command("publish_due", stdout=output)
    assert "Published 0" in output.getvalue()


def test_unauthenticated_service_access_is_denied(team):
    workspace, _ = team
    with pytest.raises(PermissionDenied):
        services.role_for(AnonymousUser(), workspace)


def test_invalid_content_rolls_back_update_and_audit(team, page):
    workspace, users = team
    initial_events = workspace.events.count()
    with pytest.raises(ValidationError):
        services.update_page(
            users["author"], workspace, page.pk, expected_version=1, title="", body="Invalid"
        )
    page.refresh_from_db()
    assert page.version == 1
    assert page.title == "Original title"
    assert workspace.events.count() == initial_events


def test_api_filters_status_and_title(api_client, team, page):
    _, users = team
    api_client.force_authenticate(users["viewer"])
    assert (
        api_client.get("/api/workspaces/studio/pages/?q=Original&status=draft").json()["count"] == 1
    )
    assert api_client.get("/api/workspaces/studio/pages/?status=published").json()["count"] == 0


def test_public_index_does_not_search_unapproved_content(client, team, page):
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
        title="SECRET",
        body="Private",
    )
    assert b"Original title" in client.get("/sites/studio/?q=Original").content
    response = client.get("/sites/studio/?q=SECRET")
    assert response.context["pages"].paginator.count == 0
