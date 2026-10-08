from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import services
from .forms import MemberForm, PageForm, WorkflowForm
from .models import Page, Revision, Workspace
from .rendering import render_body


def _workspace(request, slug):
    workspace = get_object_or_404(Workspace, slug=slug)
    role = services.role_for(request.user, workspace)
    return workspace, role


@login_required
def home(request):
    workspaces = Workspace.objects.filter(memberships__user=request.user)
    first = workspaces.first()
    if first:
        return redirect("dashboard", workspace_slug=first.slug)
    return render(request, "publishing/no_workspace.html")


@login_required
def dashboard(request, workspace_slug):
    workspace, role = _workspace(request, workspace_slug)
    pages = workspace.pages.select_related("author")
    counts = {
        entry["status"]: entry["total"]
        for entry in pages.values("status").annotate(total=Count("id"))
    }
    total, live = pages.count(), pages.filter(published_revision__isnull=False).count()
    term, selected_status = request.GET.get("q", ""), request.GET.get("status", "")
    if term:
        pages = pages.filter(Q(title__icontains=term) | Q(excerpt__icontains=term))
    if selected_status:
        pages = pages.filter(status=selected_status)
    return render(
        request,
        "publishing/dashboard.html",
        {
            "workspace": workspace,
            "role": role,
            "section": "content",
            "total": total,
            "live": live,
            "review_count": counts.get("review", 0),
            "scheduled_count": counts.get("scheduled", 0),
            "pages": Paginator(pages, 12).get_page(request.GET.get("page")),
            "term": term,
            "selected_status": selected_status,
            "statuses": Page.Status.choices,
            "workspaces": Workspace.objects.filter(memberships__user=request.user),
        },
    )


@login_required
def page_edit(request, workspace_slug, page_id=None):
    workspace, role = _workspace(request, workspace_slug)
    page = get_object_or_404(workspace.pages, pk=page_id) if page_id else None
    if page and not services.can_edit(request.user, page, role):
        raise PermissionDenied("You cannot edit this page.")
    if not page and role == "viewer":
        raise PermissionDenied("Viewers cannot create pages.")
    initial = (
        {
            "title": page.title,
            "slug": page.slug,
            "excerpt": page.excerpt,
            "body": page.body,
            "expected_version": page.version,
        }
        if page
        else {}
    )
    form = PageForm(request.POST or None, initial=initial)
    if page:
        form.fields["slug"].disabled = True
        form.fields["expected_version"].required = True
    response_status = 200
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            if page:
                saved = services.update_page(
                    request.user,
                    workspace,
                    page.pk,
                    expected_version=data["expected_version"],
                    title=data["title"],
                    body=data["body"],
                    excerpt=data["excerpt"],
                )
            else:
                saved = services.create_page(
                    request.user,
                    workspace,
                    title=data["title"],
                    slug=data["slug"],
                    body=data["body"],
                    excerpt=data["excerpt"],
                )
        except services.VersionConflict as error:
            form.add_error(None, str(error))
            response_status = 409
        except ValidationError as error:
            form.add_error(None, " ".join(error.messages))
        else:
            messages.success(
                request, "Draft saved. The live version stays unchanged until publication."
            )
            return redirect("page-detail", workspace_slug=workspace.slug, page_id=saved.pk)
    return render(
        request,
        "publishing/editor.html",
        {"workspace": workspace, "role": role, "section": "content", "page": page, "form": form},
        status=response_status,
    )


@login_required
def page_detail(request, workspace_slug, page_id):
    workspace, role = _workspace(request, workspace_slug)
    page = get_object_or_404(
        workspace.pages.select_related("author", "published_revision"), pk=page_id
    )
    return render(
        request,
        "publishing/detail.html",
        {
            "workspace": workspace,
            "role": role,
            "section": "content",
            "page": page,
            "can_edit": services.can_edit(request.user, page, role),
            "is_editor": role in ("owner", "editor"),
            "rendered_body": render_body(page.body),
            "revisions": Paginator(page.revisions.select_related("actor"), 10).get_page(
                request.GET.get("page")
            ),
        },
    )


@login_required
@require_POST
def page_action(request, workspace_slug, page_id):
    workspace, _role = _workspace(request, workspace_slug)
    get_object_or_404(workspace.pages, pk=page_id)
    form = WorkflowForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Check the workflow fields and publication date.")
        return redirect("page-detail", workspace_slug=workspace.slug, page_id=page_id)
    data = form.cleaned_data
    try:
        if data["action"] == "restore":
            if not data["number"]:
                raise ValidationError("Choose a revision to restore.")
            services.restore_revision(
                request.user,
                workspace,
                page_id,
                expected_version=data["expected_version"],
                number=data["number"],
            )
        else:
            services.transition(
                request.user,
                workspace,
                page_id,
                expected_version=data["expected_version"],
                action=data["action"],
                scheduled_for=data["scheduled_for"],
            )
    except (ValidationError, services.VersionConflict) as error:
        messages.error(
            request, " ".join(error.messages) if isinstance(error, ValidationError) else str(error)
        )
    except Revision.DoesNotExist:
        messages.error(request, "That revision does not exist on this page.")
    else:
        messages.success(request, "Workflow updated.")
    return redirect("page-detail", workspace_slug=workspace.slug, page_id=page_id)


@login_required
def activity(request, workspace_slug):
    workspace, role = _workspace(request, workspace_slug)
    events = workspace.events.select_related("actor", "page")
    return render(
        request,
        "publishing/activity.html",
        {
            "workspace": workspace,
            "role": role,
            "section": "activity",
            "events": Paginator(events, 25).get_page(request.GET.get("page")),
        },
    )


@login_required
def team(request, workspace_slug):
    workspace, role = _workspace(request, workspace_slug)
    form = MemberForm(request.POST or None)
    if request.method == "POST":
        if role != "owner":
            raise PermissionDenied("Only owners can manage the team.")
        if form.is_valid():
            try:
                services.set_member(
                    request.user, workspace, member=form.member, role=form.cleaned_data["role"]
                )
            except ValidationError as error:
                form.add_error(None, " ".join(error.messages))
            else:
                messages.success(request, "Team member updated.")
                return redirect("team", workspace_slug=workspace.slug)
    return render(
        request,
        "publishing/team.html",
        {
            "workspace": workspace,
            "role": role,
            "section": "team",
            "members": workspace.memberships.select_related("user"),
            "form": form,
        },
    )


@require_GET
def public_index(request, workspace_slug):
    workspace = get_object_or_404(Workspace, slug=workspace_slug)
    pages = (
        workspace.pages.filter(published_revision__isnull=False)
        .select_related("published_revision")
        .order_by("-published_at", "id")
    )
    term = request.GET.get("q", "")
    if term:
        pages = pages.filter(
            Q(published_revision__title__icontains=term)
            | Q(published_revision__excerpt__icontains=term)
        )
    return render(
        request,
        "publishing/public_index.html",
        {
            "workspace": workspace,
            "pages": Paginator(pages, 12).get_page(request.GET.get("page")),
            "term": term,
        },
    )


@require_GET
def public_page(request, workspace_slug, slug):
    page = get_object_or_404(
        Page.objects.select_related("published_revision", "workspace"),
        workspace__slug=workspace_slug,
        slug=slug,
        published_revision__isnull=False,
    )
    return render(
        request,
        "publishing/public_page.html",
        {
            "workspace": page.workspace,
            "page": page,
            "revision": page.published_revision,
            "rendered_body": render_body(page.published_revision.body),
        },
    )


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
