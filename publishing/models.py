import uuid

from django.conf import settings
from django.db import models


class Workspace(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        EDITOR = "editor", "Editor"
        AUTHOR = "author", "Author"
        VIEWER = "viewer", "Viewer"

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=Role.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "user"], name="unique_member")]


class Page(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "In review"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="pages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    slug = models.SlugField(max_length=100)
    title = models.CharField(max_length=160)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    published_revision = models.ForeignKey(
        "Revision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="live_pages",
    )
    approved_revision = models.ForeignKey(
        "Revision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="scheduled_pages",
    )
    scheduled_for = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["workspace", "slug"], name="unique_workspace_slug"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="positive_version"),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="scheduled",
                        scheduled_for__isnull=False,
                        approved_revision__isnull=False,
                    )
                    | (
                        ~models.Q(status="scheduled")
                        & models.Q(scheduled_for__isnull=True, approved_revision__isnull=True)
                    )
                ),
                name="schedule_requires_approval",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "status"]),
            models.Index(fields=["scheduled_for"]),
        ]

    def __str__(self):
        return self.title


class Revision(models.Model):
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=160)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [models.UniqueConstraint(fields=["page", "number"], name="unique_revision")]


class AuditEvent(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="events")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    action = models.CharField(max_length=40)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
