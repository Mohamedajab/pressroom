from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from publishing import services
from publishing.models import Page, Workspace


def submit(team, page):
    workspace, users = team
    return services.transition(
        users["author"], workspace, page.pk, expected_version=page.version, action="submit"
    )


def publish(team, page):
    workspace, users = team
    page = submit(team, page)
    return services.transition(
        users["editor"], workspace, page.pk, expected_version=page.version, action="publish"
    )


def test_creation_records_revision_and_audit(page):
    assert page.revisions.get().body == "Original body"
    assert page.workspace.events.get().action == "created"


@pytest.mark.parametrize("role", ["viewer", "outsider"])
def test_readonly_and_outsider_cannot_create(team, role):
    workspace, users = team
    with pytest.raises(PermissionDenied):
        services.create_page(users[role], workspace, title="No", slug="no", body="No")
    assert workspace.pages.count() == 0


def test_duplicate_slug_returns_validation_error_without_partial_writes(team, page):
    workspace, users = team
    with pytest.raises(ValidationError):
        services.create_page(
            users["author"], workspace, title="Duplicate", slug=page.slug, body="No"
        )
    assert workspace.pages.count() == 1
    assert workspace.events.count() == 1


def test_author_cannot_edit_another_authors_page(team, page):
    workspace, users = team
    other = services.create_page(
        users["editor"], workspace, title="Other", slug="other", body="Other"
    )
    with pytest.raises(PermissionDenied):
        services.update_page(
            users["author"], workspace, other.pk, expected_version=1, title="Hijack", body="No"
        )


def test_stale_update_does_not_overwrite_new_content(team, page):
    workspace, users = team
    services.update_page(
        users["author"], workspace, page.pk, expected_version=1, title="New title", body="New"
    )
    with pytest.raises(services.VersionConflict):
        services.update_page(
            users["author"], workspace, page.pk, expected_version=1, title="Stale", body="Stale"
        )
    page.refresh_from_db()
    assert page.title == "New title"
    assert page.revisions.count() == 2


@pytest.mark.parametrize("role", ["author", "viewer", "outsider"])
def test_only_editors_can_publish(team, page, role):
    workspace, users = team
    page = submit(team, page)
    with pytest.raises(PermissionDenied):
        services.transition(
            users[role], workspace, page.pk, expected_version=page.version, action="publish"
        )
    page.refresh_from_db()
    assert page.published_revision_id is None


def test_publish_requires_review(team, page):
    workspace, users = team
    with pytest.raises(ValidationError):
        services.transition(
            users["editor"], workspace, page.pk, expected_version=page.version, action="publish"
        )


def test_published_snapshot_survives_new_draft(team, page):
    workspace, users = team
    page = publish(team, page)
    live_id = page.published_revision_id
    page = services.update_page(
        users["author"],
        workspace,
        page.pk,
        expected_version=page.version,
        title="SECRET DRAFT",
        body="Unapproved body",
    )
    assert page.status == Page.Status.DRAFT
    assert page.published_revision_id == live_id
    assert page.published_revision.title == "Original title"


def test_edit_invalidates_review_and_stale_approval(team, page):
    workspace, users = team
    page = submit(team, page)
    review_version = page.version
    page = services.update_page(
        users["author"],
        workspace,
        page.pk,
        expected_version=review_version,
        title="Changed",
        body="Changed",
    )
    with pytest.raises(services.VersionConflict):
        services.transition(
            users["editor"], workspace, page.pk, expected_version=review_version, action="publish"
        )
    assert page.status == Page.Status.DRAFT


def test_restore_creates_revision_without_rewriting_history(team, page):
    workspace, users = team
    page = services.update_page(
        users["author"], workspace, page.pk, expected_version=1, title="New", body="New"
    )
    page = services.restore_revision(
        users["author"], workspace, page.pk, expected_version=page.version, number=1
    )
    assert page.title == "Original title"
    assert page.version == 3
    assert page.revisions.get(number=2).title == "New"
    assert workspace.events.first().action == "restored"


def test_scheduler_is_due_only_and_idempotent(team, page):
    workspace, users = team
    page = submit(team, page)
    due = timezone.now() + timedelta(hours=2)
    page = services.transition(
        users["editor"],
        workspace,
        page.pk,
        expected_version=page.version,
        action="schedule",
        scheduled_for=due,
    )
    assert services.publish_due(now=due - timedelta(seconds=1)) == 0
    assert services.publish_due(now=due) == 1
    assert services.publish_due(now=due) == 0
    page.refresh_from_db()
    assert page.published_revision.body == "Original body"
    assert page.scheduled_for is None
    assert workspace.events.filter(action="scheduled_publish").count() == 1


def test_edit_cancels_schedule(team, page):
    workspace, users = team
    page = submit(team, page)
    due = timezone.now() + timedelta(hours=1)
    page = services.transition(
        users["editor"],
        workspace,
        page.pk,
        expected_version=page.version,
        action="schedule",
        scheduled_for=due,
    )
    page = services.update_page(
        users["author"],
        workspace,
        page.pk,
        expected_version=page.version,
        title="Not approved",
        body="Private",
    )
    assert page.approved_revision_id is None
    assert services.publish_due(now=due) == 0


@pytest.mark.parametrize("when", [None, "past"])
def test_schedule_rejects_missing_or_past_time(team, page, when):
    workspace, users = team
    page = submit(team, page)
    scheduled_for = timezone.now() - timedelta(minutes=1) if when else None
    with pytest.raises(ValidationError):
        services.transition(
            users["editor"],
            workspace,
            page.pk,
            expected_version=page.version,
            action="schedule",
            scheduled_for=scheduled_for,
        )


def test_archive_removes_public_snapshot(team, page):
    workspace, users = team
    page = publish(team, page)
    page = services.transition(
        users["editor"], workspace, page.pk, expected_version=page.version, action="archive"
    )
    assert page.published_revision_id is None
    assert page.revisions.count() == 4


def test_last_owner_cannot_be_demoted(team):
    workspace, users = team
    with pytest.raises(ValidationError):
        services.set_member(users["owner"], workspace, member=users["owner"], role="author")
    assert workspace.memberships.get(user=users["owner"]).role == "owner"


def test_owner_can_delegate_then_change_own_role(team):
    workspace, users = team
    services.set_member(users["owner"], workspace, member=users["editor"], role="owner")
    services.set_member(users["owner"], workspace, member=users["owner"], role="author")
    assert workspace.memberships.filter(role="owner").count() == 1


@pytest.mark.parametrize("role", ["editor", "author", "viewer"])
def test_nonowners_cannot_manage_members(team, role):
    workspace, users = team
    with pytest.raises(PermissionDenied):
        services.set_member(users[role], workspace, member=users["outsider"], role="owner")


def test_same_slug_allowed_in_different_workspace(team, page):
    _, users = team
    other = Workspace.objects.create(name="Other", slug="other")
    from publishing.models import Membership

    Membership.objects.create(user=users["author"], workspace=other, role="author")
    new = services.create_page(users["author"], other, title="Other", slug=page.slug, body="Other")
    assert new.workspace_id != page.workspace_id
