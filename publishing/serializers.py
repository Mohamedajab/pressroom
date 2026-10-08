from rest_framework import serializers

from .models import AuditEvent, Membership, Page, Revision


class PageSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.username", read_only=True)
    is_live = serializers.SerializerMethodField()

    class Meta:
        model = Page
        fields = [
            "id",
            "slug",
            "title",
            "excerpt",
            "body",
            "status",
            "version",
            "author",
            "is_live",
            "scheduled_for",
            "published_at",
            "created_at",
            "updated_at",
        ]

    def get_is_live(self, obj) -> bool:
        return obj.published_revision_id is not None


class PublicPageSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="published_revision.title")
    excerpt = serializers.CharField(source="published_revision.excerpt")
    body = serializers.CharField(source="published_revision.body")
    revision = serializers.IntegerField(source="published_revision.number")

    class Meta:
        model = Page
        fields = ["id", "slug", "title", "excerpt", "body", "revision", "published_at"]


class CreatePageSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=160)
    slug = serializers.SlugField(max_length=100)
    body = serializers.CharField(max_length=100000)
    excerpt = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class UpdatePageSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=160)
    body = serializers.CharField(max_length=100000)
    excerpt = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class TransitionSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    action = serializers.ChoiceField(choices=["submit", "publish", "schedule", "reject", "archive"])
    scheduled_for = serializers.DateTimeField(required=False)


class RestoreSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
    number = serializers.IntegerField(min_value=1)


class RevisionSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username")

    class Meta:
        model = Revision
        fields = ["number", "title", "excerpt", "body", "actor", "created_at"]


class EventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", allow_null=True)

    class Meta:
        model = AuditEvent
        fields = ["id", "page", "actor", "action", "detail", "created_at"]


class MemberInputSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=Membership.Role.choices)


class MemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")

    class Meta:
        model = Membership
        fields = ["username", "role"]
