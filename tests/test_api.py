import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.authtoken.models import Token

from publishing import services
from publishing.models import Membership, Workspace


def endpoint(page, suffix=""):
    return f"/api/workspaces/studio/pages/{page.pk}/{suffix}"


def make_live(team, page):
    workspace, users = team
    page = services.transition(
        users["author"], workspace, page.pk, expected_version=page.version, action="submit"
    )
    return services.transition(
        users["editor"], workspace, page.pk, expected_version=page.version, action="publish"
    )


def test_anonymous_cannot_access_drafts(api_client, page):
    assert api_client.get(endpoint(page)).status_code == 401


def test_public_draft_detail_is_not_found(api_client, page):
    assert api_client.get("/api/public/studio/pages/original/").status_code == 404
    assert api_client.get("/api/public/studio/pages/").json()["count"] == 0


@pytest.mark.parametrize("suffix", ["", "revisions/"])
def test_outsider_cannot_read_private_resources(api_client, team, page, suffix):
    _, users = team
    api_client.force_authenticate(users["outsider"])
    assert api_client.get(endpoint(page, suffix)).status_code == 403


def test_wrong_workspace_cannot_read_or_mutate_page(api_client, team, page):
    _, users = team
    other = Workspace.objects.create(name="Other", slug="other")
    Membership.objects.create(workspace=other, user=users["author"], role="owner")
    api_client.force_authenticate(users["author"])
    url = f"/api/workspaces/other/pages/{page.pk}/"
    assert api_client.get(url).status_code == 404
    assert (
        api_client.put(
            url, {"expected_version": 1, "title": "Stolen", "body": "Stolen"}, format="json"
        ).status_code
        == 404
    )


def test_token_authentication(api_client, team):
    _, users = team
    token = Token.objects.create(user=users["author"])
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    assert api_client.get("/api/workspaces/studio/pages/").status_code == 200


def test_viewer_cannot_create(api_client, team):
    _, users = team
    api_client.force_authenticate(users["viewer"])
    response = api_client.post(
        "/api/workspaces/studio/pages/", {"title": "No", "slug": "no", "body": "No"}, format="json"
    )
    assert response.status_code == 403


def test_create_validates_and_returns_created_page(api_client, team):
    _, users = team
    api_client.force_authenticate(users["author"])
    url = "/api/workspaces/studio/pages/"
    assert api_client.post(url, {"title": "No"}, format="json").status_code == 400
    response = api_client.post(
        url, {"title": "Hello", "slug": "hello", "body": "World"}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["version"] == 1


def test_duplicate_slug_is_400(api_client, team, page):
    _, users = team
    api_client.force_authenticate(users["author"])
    response = api_client.post(
        "/api/workspaces/studio/pages/",
        {"title": "Hello", "slug": page.slug, "body": "World"},
        format="json",
    )
    assert response.status_code == 400


def test_stale_edit_is_409(api_client, team, page):
    _, users = team
    api_client.force_authenticate(users["author"])
    payload = {"expected_version": 1, "title": "New title", "body": "New body"}
    assert api_client.put(endpoint(page), payload, format="json").status_code == 200
    assert api_client.put(endpoint(page), payload, format="json").status_code == 409


def test_public_api_and_search_never_expose_draft(api_client, team, page):
    workspace, users = team
    page = make_live(team, page)
    services.update_page(
        users["author"],
        workspace,
        page.pk,
        expected_version=page.version,
        title="SECRET DRAFT",
        body="Secret",
    )
    response = api_client.get("/api/public/studio/pages/original/")
    assert response.status_code == 200
    assert response.json()["title"] == "Original title"
    assert "SECRET" not in response.content.decode()
    assert api_client.get("/api/public/studio/pages/?q=SECRET").json()["count"] == 0
    assert api_client.get("/api/public/studio/pages/?q=Original").json()["count"] == 1


def test_workflow_and_restore_endpoints(api_client, team, page):
    _, users = team
    api_client.force_authenticate(users["author"])
    response = api_client.post(
        endpoint(page, "workflow/"), {"expected_version": 1, "action": "submit"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "review"
    response = api_client.post(
        endpoint(page, "restore/"), {"expected_version": 2, "number": 1}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "draft"
    assert api_client.get(endpoint(page, "revisions/")).json()["count"] == 3


def test_editor_can_publish_via_api(api_client, team, page):
    workspace, users = team
    page = services.transition(
        users["author"], workspace, page.pk, expected_version=1, action="submit"
    )
    api_client.force_authenticate(users["editor"])
    response = api_client.post(
        endpoint(page, "workflow/"),
        {"expected_version": page.version, "action": "publish"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["is_live"]


def test_members_and_events_are_scoped(api_client, team, page):
    _, users = team
    api_client.force_authenticate(users["owner"])
    assert len(api_client.get("/api/workspaces/studio/members/").json()) == 4
    assert api_client.get("/api/workspaces/studio/events/").json()["count"] == 1
    result = api_client.post(
        "/api/workspaces/studio/members/", {"username": "outsider", "role": "viewer"}, format="json"
    )
    assert result.status_code == 200
    assert result.json()["role"] == "viewer"


def test_list_is_paginated_without_n_plus_one_queries(api_client, team):
    workspace, users = team
    for index in range(25):
        services.create_page(
            users["author"], workspace, title=f"Page {index}", slug=f"page-{index}", body="Body"
        )
    api_client.force_authenticate(users["author"])
    with CaptureQueriesContext(connection) as queries:
        response = api_client.get("/api/workspaces/studio/pages/")
    assert response.json()["count"] == 25
    assert len(response.json()["results"]) == 20
    # Workspace + membership + count + select_related list. Never one author query per page.
    assert len(queries) <= 5


def test_invalid_transition_and_missing_revision_are_handled(api_client, team, page):
    _, users = team
    api_client.force_authenticate(users["editor"])
    assert (
        api_client.post(
            endpoint(page, "workflow/"), {"expected_version": 1, "action": "publish"}, format="json"
        ).status_code
        == 400
    )
    assert (
        api_client.post(
            endpoint(page, "restore/"), {"expected_version": 1, "number": 999}, format="json"
        ).status_code
        == 404
    )
