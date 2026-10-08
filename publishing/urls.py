from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("workspace/<slug:workspace_slug>/", views.dashboard, name="dashboard"),
    path("workspace/<slug:workspace_slug>/new/", views.page_edit, name="page-new"),
    path(
        "workspace/<slug:workspace_slug>/pages/<uuid:page_id>/",
        views.page_detail,
        name="page-detail",
    ),
    path(
        "workspace/<slug:workspace_slug>/pages/<uuid:page_id>/edit/",
        views.page_edit,
        name="page-edit",
    ),
    path(
        "workspace/<slug:workspace_slug>/pages/<uuid:page_id>/action/",
        views.page_action,
        name="page-action",
    ),
    path("workspace/<slug:workspace_slug>/activity/", views.activity, name="activity"),
    path("workspace/<slug:workspace_slug>/team/", views.team, name="team"),
    path("sites/<slug:workspace_slug>/", views.public_index, name="public-index"),
    path("sites/<slug:workspace_slug>/<slug:slug>/", views.public_page, name="public-page"),
]
