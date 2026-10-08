"""One transactional workflow used by both HTML views and the REST API."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, Membership, Page, Revision, Workspace


class VersionConflict(Exception):
    """The browser or API client tried to overwrite a newer revision."""


def role_for(user, workspace):
    if not user.is_authenticated:
        raise PermissionDenied("Sign in to access this workspace.")
    membership = Membership.objects.filter(user=user, workspace=workspace).first()
    if not membership:
        raise PermissionDenied("You are not a member of this workspace.")
    return membership.role


def can_edit(user, page, role):
    return role in ("owner", "editor") or (role == "author" and page.author_id == user.pk)


def _event(page, actor, action, **detail):
    AuditEvent.objects.create(
        workspace=page.workspace, page=page, actor=actor, action=action, detail=detail
    )


def _revision(page, actor):
    return Revision.objects.create(
        page=page,
        number=page.version,
        title=page.title,
        excerpt=page.excerpt,
        body=page.body,
        actor=actor,
    )


def _locked_page(user, workspace, page_id, expected_version, *, editor=False):
    page = Page.objects.select_for_update().get(workspace=workspace, pk=page_id)
    role = role_for(user, workspace)
    if editor and role not in ("owner", "editor"):
        raise PermissionDenied("Only editors and owners can approve publication.")
    if not editor and not can_edit(user, page, role):
        raise PermissionDenied("You cannot edit this page.")
    if page.version != expected_version:
        raise VersionConflict("This page changed. Reload it before trying again.")
    return page


@transaction.atomic
def create_page(user, workspace, *, title, slug, body, excerpt=""):
    if role_for(user, workspace) not in ("owner", "editor", "author"):
        raise PermissionDenied("Viewers cannot create pages.")
    # Lock the workspace so duplicate slug checks are safe across concurrent creates.
    Workspace.objects.select_for_update().get(pk=workspace.pk)
    page = Page(
        workspace=workspace, author=user, title=title, slug=slug, body=body, excerpt=excerpt
    )
    page.full_clean()
    page.save()
    _revision(page, user)
    _event(page, user, "created", version=page.version)
    return page


@transaction.atomic
def update_page(user, workspace, page_id, *, expected_version, title, body, excerpt=""):
    page = _locked_page(user, workspace, page_id, expected_version)
    page.title, page.body, page.excerpt = title, body, excerpt
    page.version += 1
    page.status = Page.Status.DRAFT
    page.scheduled_for = page.approved_revision = None
    page.full_clean()
    page.save()
    _revision(page, user)
    _event(page, user, "updated", version=page.version)
    return page


@transaction.atomic
def restore_revision(user, workspace, page_id, *, expected_version, number):
    page = _locked_page(user, workspace, page_id, expected_version)
    old = Revision.objects.get(page=page, number=number)
    page = update_page(
        user,
        workspace,
        page_id,
        expected_version=expected_version,
        title=old.title,
        body=old.body,
        excerpt=old.excerpt,
    )
    _event(page, user, "restored", from_version=number, version=page.version)
    return page


@transaction.atomic
def transition(user, workspace, page_id, *, expected_version, action, scheduled_for=None):
    page = _locked_page(
        user,
        workspace,
        page_id,
        expected_version,
        editor=action in ("publish", "schedule", "reject", "archive"),
    )
    if action == "submit":
        if page.status != Page.Status.DRAFT:
            raise ValidationError("Only drafts can be submitted for review.")
        page.status = Page.Status.REVIEW
    elif action in ("publish", "schedule"):
        if page.status != Page.Status.REVIEW:
            raise ValidationError("Submit the current revision for review first.")
        revision = page.revisions.get(number=page.version)
        if action == "schedule":
            if scheduled_for is None or scheduled_for <= timezone.now():
                raise ValidationError("Choose a future publication time.")
            page.status = Page.Status.SCHEDULED
            page.scheduled_for, page.approved_revision = scheduled_for, revision
        else:
            page.status = Page.Status.PUBLISHED
            page.published_revision, page.published_at = revision, timezone.now()
    elif action == "reject":
        if page.status != Page.Status.REVIEW:
            raise ValidationError("Only pages in review can be returned to draft.")
        page.status = Page.Status.DRAFT
    elif action == "archive":
        if page.status == Page.Status.ARCHIVED:
            raise ValidationError("This page is already archived.")
        page.status = Page.Status.ARCHIVED
        page.published_revision = page.scheduled_for = page.approved_revision = None
    else:
        raise ValidationError("Unknown workflow action.")
    # Version represents the entire editable resource, including workflow changes.
    page.version += 1
    page.full_clean()
    page.save()
    _revision(page, user)
    _event(
        page,
        user,
        action,
        version=page.version,
        scheduled_for=scheduled_for.isoformat() if scheduled_for else None,
    )
    return page


def publish_due(*, now=None):
    """Idempotent scheduler. Row locking prevents duplicate publication on PostgreSQL."""
    now = now or timezone.now()
    count = 0
    ids = Page.objects.filter(status=Page.Status.SCHEDULED, scheduled_for__lte=now).values_list(
        "pk", flat=True
    )
    for page_id in list(ids):
        with transaction.atomic():
            page = Page.objects.select_for_update().get(pk=page_id)
            if page.status != Page.Status.SCHEDULED or page.scheduled_for > now:
                continue
            approver = page.revisions.get(number=page.version).actor
            page.published_revision, page.published_at = page.approved_revision, now
            page.status = Page.Status.PUBLISHED
            page.approved_revision = page.scheduled_for = None
            page.version += 1
            page.save()
            _revision(page, approver)
            _event(page, None, "scheduled_publish", version=page.version)
            count += 1
    return count


@transaction.atomic
def set_member(user, workspace, *, member, role):
    Workspace.objects.select_for_update().get(pk=workspace.pk)
    if role_for(user, workspace) != "owner":
        raise PermissionDenied("Only owners can manage the team.")
    if role not in Membership.Role.values:
        raise ValidationError("Invalid role.")
    current = Membership.objects.filter(workspace=workspace, user=member).first()
    if current and current.role == "owner" and role != "owner":
        if workspace.memberships.filter(role="owner").count() == 1:
            raise ValidationError("A workspace must retain at least one owner.")
    membership, _ = Membership.objects.update_or_create(
        workspace=workspace, user=member, defaults={"role": role}
    )
    AuditEvent.objects.create(
        workspace=workspace,
        actor=user,
        action="member_updated",
        detail={"username": member.username, "role": role},
    )
    return membership
