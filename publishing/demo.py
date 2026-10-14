"""Opt-in, bounded, visitor-isolated portfolio workspaces; no shared passwords."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import DemoSession, Membership, Page, Workspace
from .services import create_page, transition


def current_demo(request):
    if not request.user.is_authenticated:
        return None
    return (
        DemoSession.objects.filter(Q(author=request.user) | Q(editor=request.user))
        .select_related("workspace", "author", "editor")
        .first()
    )


def demo_context(request):
    return {"demo_enabled": settings.DEMO_ENABLED, "demo_session": getattr(request, "demo", None)}


class DemoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.demo = current_demo(request)
        if request.demo:
            if not settings.DEMO_ENABLED or request.demo.expires_at <= timezone.now():
                logout(request)
                return redirect("demo")
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                if (
                    "/team/" in request.path
                    or "/members/" in request.path
                    or request.path.startswith("/admin/")
                ):
                    return HttpResponse("Team changes are unavailable in the demo.", status=403)
                if len(request.body) > 20_000:
                    return HttpResponse("Use a shorter sample document in the demo.", status=413)
                if request.path not in ("/demo/switch/", "/accounts/logout/"):
                    updated = DemoSession.objects.filter(pk=request.demo.pk, writes__lt=60).update(
                        writes=F("writes") + 1
                    )
                    if not updated:
                        return HttpResponse(
                            "This demo has reached its edit limit. Try again after it expires.",
                            status=429,
                        )
        return self.get_response(request)


@require_GET
def landing(request):
    if not settings.DEMO_ENABLED:
        raise Http404
    return render(request, "publishing/demo.html")


@require_POST
def start(request):
    if not settings.DEMO_ENABLED:
        raise Http404
    existing = current_demo(request)
    if existing and existing.expires_at > timezone.now():
        return redirect("dashboard", workspace_slug=existing.workspace.slug)
    if request.user.is_authenticated:
        raise PermissionDenied("Sign out of your account before starting a demo.")
    cleanup_expired()
    if DemoSession.objects.filter(expires_at__gt=timezone.now()).count() >= 100:
        return HttpResponse("The demo is busy. Please try again later.", status=503)
    with transaction.atomic():
        workspace = Workspace.objects.create(
            name="Your Fieldnotes Studio", slug="demo-" + __import__("uuid").uuid4().hex
        )
        suffix = workspace.slug.removeprefix("demo-")
        users = {}
        for role in ("author", "editor"):
            user = get_user_model().objects.create_user(
                username=f"demo-{role}-{suffix}", first_name=role.title()
            )
            users[role] = user
            Membership.objects.create(workspace=workspace, user=user, role=role)
        DemoSession.objects.create(
            workspace=workspace,
            author=users["author"],
            editor=users["editor"],
            expires_at=timezone.now() + timedelta(hours=1),
        )
        page = create_page(
            users["author"],
            workspace,
            title="A place for unfinished ideas",
            slug="unfinished-ideas",
            excerpt="Try editing a published story without changing the live version.",
            body="## Your next chapter\n\nGood stories begin with a small first step. Edit this story, submit it for review, then switch to editor to publish your changes.",
        )
        page = transition(
            users["author"], workspace, page.pk, expected_version=page.version, action="submit"
        )
        transition(
            users["editor"], workspace, page.pk, expected_version=page.version, action="publish"
        )
        create_page(
            users["author"],
            workspace,
            title="Notes from the studio",
            slug="studio-notes",
            body="## Still in draft\n\nThis document stays private until an editor approves it.",
        )
    login(request, users["author"], backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(3600)
    return redirect("dashboard", workspace_slug=workspace.slug)


@require_POST
def switch_role(request):
    demo = current_demo(request)
    if not settings.DEMO_ENABLED or not demo or demo.expires_at <= timezone.now():
        raise Http404
    role = request.POST.get("role")
    if role not in ("author", "editor"):
        return HttpResponse("Choose author or editor.", status=400)
    login(request, getattr(demo, role), backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(max(1, int((demo.expires_at - timezone.now()).total_seconds())))
    return redirect("dashboard", workspace_slug=demo.workspace.slug)


def cleanup_expired():
    """Delete only explicitly registered expired demos, including their dedicated users."""
    total = 0
    for demo_id in DemoSession.objects.filter(expires_at__lte=timezone.now()).values_list(
        "pk", flat=True
    ):
        with transaction.atomic():
            demo = DemoSession.objects.select_for_update().filter(pk=demo_id).first()
            if not demo:
                continue
            user_ids = (demo.author_id, demo.editor_id)
            Page.objects.filter(workspace=demo.workspace).update(
                status="draft", scheduled_for=None, published_revision=None, approved_revision=None
            )
            demo.workspace.delete()
            get_user_model().objects.filter(pk__in=user_ids).delete()
            total += 1
    return total
