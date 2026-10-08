from django.urls import path

from . import api

urlpatterns = [
    path("workspaces/<slug:workspace_slug>/pages/", api.PageListView.as_view()),
    path("workspaces/<slug:workspace_slug>/pages/<uuid:page_id>/", api.PageDetailView.as_view()),
    path(
        "workspaces/<slug:workspace_slug>/pages/<uuid:page_id>/workflow/",
        api.WorkflowView.as_view(),
    ),
    path(
        "workspaces/<slug:workspace_slug>/pages/<uuid:page_id>/revisions/",
        api.RevisionListView.as_view(),
    ),
    path(
        "workspaces/<slug:workspace_slug>/pages/<uuid:page_id>/restore/", api.RestoreView.as_view()
    ),
    path("workspaces/<slug:workspace_slug>/events/", api.EventListView.as_view()),
    path("workspaces/<slug:workspace_slug>/members/", api.MemberView.as_view()),
    path("public/<slug:workspace_slug>/pages/", api.PublicListView.as_view()),
    path("public/<slug:workspace_slug>/pages/<slug:slug>/", api.PublicDetailView.as_view()),
]
