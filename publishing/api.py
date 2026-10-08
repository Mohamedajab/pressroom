from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Page, Revision, Workspace
from .serializers import (
    CreatePageSerializer,
    EventSerializer,
    MemberInputSerializer,
    MemberSerializer,
    PageSerializer,
    PublicPageSerializer,
    RestoreSerializer,
    RevisionSerializer,
    TransitionSerializer,
    UpdatePageSerializer,
)


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This page changed. Reload it before trying again."


class BaseView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, services.VersionConflict):
            exc = Conflict(str(exc))
        elif isinstance(exc, DjangoValidationError):
            exc = ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        elif isinstance(exc, (Page.DoesNotExist, Revision.DoesNotExist)):
            exc = Http404()
        return super().handle_exception(exc)

    def workspace(self, slug):
        workspace = get_object_or_404(Workspace, slug=slug)
        services.role_for(self.request.user, workspace)
        return workspace

    def paginated(self, queryset, serializer):
        paginator = PageNumberPagination()
        paginator.page_size = 20
        objects = paginator.paginate_queryset(queryset, self.request, view=self)
        return paginator.get_paginated_response(serializer(objects, many=True).data)


class PageListView(BaseView):
    @extend_schema(
        responses=PageSerializer(many=True),
        parameters=[
            OpenApiParameter("q", str),
            OpenApiParameter("status", str),
            OpenApiParameter("page", int),
        ],
    )
    def get(self, request, workspace_slug):
        workspace = self.workspace(workspace_slug)
        pages = workspace.pages.select_related("author")
        if term := request.query_params.get("q", ""):
            pages = pages.filter(Q(title__icontains=term) | Q(excerpt__icontains=term))
        if value := request.query_params.get("status"):
            pages = pages.filter(status=value)
        return self.paginated(pages, PageSerializer)

    @extend_schema(request=CreatePageSerializer, responses={201: PageSerializer})
    def post(self, request, workspace_slug):
        workspace = self.workspace(workspace_slug)
        data = CreatePageSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        page = services.create_page(request.user, workspace, **data.validated_data)
        return Response(PageSerializer(page).data, status=201)


class PageDetailView(BaseView):
    @extend_schema(responses=PageSerializer)
    def get(self, request, workspace_slug, page_id):
        workspace = self.workspace(workspace_slug)
        return Response(
            PageSerializer(
                get_object_or_404(workspace.pages.select_related("author"), pk=page_id)
            ).data
        )

    @extend_schema(request=UpdatePageSerializer, responses={200: PageSerializer, 409: None})
    def put(self, request, workspace_slug, page_id):
        workspace = self.workspace(workspace_slug)
        data = UpdatePageSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        page = services.update_page(request.user, workspace, page_id, **data.validated_data)
        return Response(PageSerializer(page).data)


class WorkflowView(BaseView):
    @extend_schema(request=TransitionSerializer, responses={200: PageSerializer, 409: None})
    def post(self, request, workspace_slug, page_id):
        workspace = self.workspace(workspace_slug)
        data = TransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        page = services.transition(request.user, workspace, page_id, **data.validated_data)
        return Response(PageSerializer(page).data)


class RevisionListView(BaseView):
    @extend_schema(responses=RevisionSerializer(many=True))
    def get(self, request, workspace_slug, page_id):
        workspace = self.workspace(workspace_slug)
        page = get_object_or_404(workspace.pages, pk=page_id)
        return self.paginated(page.revisions.select_related("actor"), RevisionSerializer)


class RestoreView(BaseView):
    @extend_schema(request=RestoreSerializer, responses={200: PageSerializer, 409: None})
    def post(self, request, workspace_slug, page_id):
        workspace = self.workspace(workspace_slug)
        data = RestoreSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        page = services.restore_revision(request.user, workspace, page_id, **data.validated_data)
        return Response(PageSerializer(page).data)


class EventListView(BaseView):
    @extend_schema(responses=EventSerializer(many=True))
    def get(self, request, workspace_slug):
        workspace = self.workspace(workspace_slug)
        return self.paginated(workspace.events.select_related("actor"), EventSerializer)


class MemberView(BaseView):
    @extend_schema(responses=MemberSerializer(many=True))
    def get(self, request, workspace_slug):
        workspace = self.workspace(workspace_slug)
        return Response(
            MemberSerializer(workspace.memberships.select_related("user"), many=True).data
        )

    @extend_schema(request=MemberInputSerializer, responses=MemberSerializer)
    def post(self, request, workspace_slug):
        workspace = self.workspace(workspace_slug)
        data = MemberInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        member = get_object_or_404(get_user_model(), username=data.validated_data["username"])
        membership = services.set_member(
            request.user, workspace, member=member, role=data.validated_data["role"]
        )
        return Response(MemberSerializer(membership).data)


class PublicListView(BaseView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        responses=PublicPageSerializer(many=True),
        parameters=[
            OpenApiParameter("q", str),
            OpenApiParameter("page", int),
        ],
    )
    def get(self, request, workspace_slug):
        workspace = get_object_or_404(Workspace, slug=workspace_slug)
        pages = (
            workspace.pages.filter(published_revision__isnull=False)
            .select_related("published_revision")
            .order_by("-published_at", "id")
        )
        if term := request.query_params.get("q", ""):
            pages = pages.filter(
                Q(published_revision__title__icontains=term)
                | Q(published_revision__excerpt__icontains=term)
            )
        return self.paginated(pages, PublicPageSerializer)


class PublicDetailView(BaseView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=PublicPageSerializer)
    def get(self, request, workspace_slug, slug):
        page = get_object_or_404(
            Page.objects.select_related("published_revision"),
            workspace__slug=workspace_slug,
            slug=slug,
            published_revision__isnull=False,
        )
        return Response(PublicPageSerializer(page).data)
