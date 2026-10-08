from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.utils import timezone

from publishing import services
from publishing.models import Workspace

pytestmark = pytest.mark.django_db(transaction=True)


def postgres_only():
    if connection.vendor != "postgresql":
        pytest.skip("Real row-lock concurrency requires PostgreSQL; exercised in CI.")


def test_two_editors_cannot_silently_overwrite_the_same_version(team, page):
    postgres_only()
    workspace, users = team
    barrier = Barrier(2)

    def edit(title):
        close_old_connections()
        try:
            user = get_user_model().objects.get(pk=users["editor"].pk)
            space = Workspace.objects.get(pk=workspace.pk)
            barrier.wait(timeout=10)
            try:
                services.update_page(
                    user, space, page.pk, expected_version=1, title=title, body=title
                )
            except services.VersionConflict:
                return "conflict"
            return "saved"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(edit, ["First editor", "Second editor"]))
    assert sorted(outcomes) == ["conflict", "saved"]
    page.refresh_from_db()
    assert page.version == 2
    assert page.revisions.count() == 2


def test_two_scheduler_workers_publish_once(team, page):
    postgres_only()
    workspace, users = team
    page = services.transition(
        users["author"], workspace, page.pk, expected_version=1, action="submit"
    )
    due = timezone.now() + timedelta(minutes=1)
    page = services.transition(
        users["editor"],
        workspace,
        page.pk,
        expected_version=page.version,
        action="schedule",
        scheduled_for=due,
    )
    barrier = Barrier(2)

    def run_worker(_):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return services.publish_due(now=due)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(run_worker, range(2)))
    assert sum(outcomes) == 1
    assert workspace.events.filter(action="scheduled_publish").count() == 1
    page.refresh_from_db()
    assert page.status == "published"
    assert page.revisions.first().actor == users["editor"]
