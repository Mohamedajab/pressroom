from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from publishing.models import Membership, Workspace
from publishing.services import create_page, transition, update_page

STORIES = [
    (
        "The art of paying attention",
        "the-art-of-paying-attention",
        "A few small ways to notice more, slow down and find ideas hiding in plain sight.",
        "published",
    ),
    (
        "Building a slower, better internet",
        "a-better-internet",
        "What happens when we build digital spaces around people, rather than clicks?",
        "published",
    ),
    (
        "A place for unfinished ideas",
        "unfinished-ideas",
        "The notebook, the rough draft, the almost-there. Why the middle matters.",
        "published",
    ),
    (
        "Small teams, meaningful work",
        "small-teams",
        "A field guide to making things together without getting in each other’s way.",
        "published",
    ),
    (
        "Why we’re making space for stories",
        "space-for-stories",
        "A note from the team on what comes next, and why we’re glad you’re here.",
        "review",
    ),
    (
        "Notes from the studio: October",
        "october-notes",
        "A monthly collection of things we’ve made, learned and changed our minds about.",
        "scheduled",
    ),
    (
        "Less noise. More signal.",
        "less-noise",
        "Some thoughts on clear writing, thoughtful editing and leaving room to breathe.",
        "draft",
    ),
    (
        "The next chapter starts here",
        "next-chapter",
        "Early notes on the work ahead. Still finding the right words.",
        "draft",
    ),
]


class Command(BaseCommand):
    help = "Create local-only demo accounts and an example publication. Safe to run twice."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password", required=True, help="Password for newly created demo accounts."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo seeding is disabled when DEBUG=false.")
        if Workspace.objects.filter(slug="fieldnotes").exists():
            self.stdout.write(
                "Demo workspace already exists. Existing data and passwords were preserved."
            )
            return
        users = {}
        for username, role in [
            ("owner", "owner"),
            ("editor", "editor"),
            ("author", "author"),
            ("viewer", "viewer"),
        ]:
            user, created = get_user_model().objects.get_or_create(
                username=username, defaults={"email": f"{username}@example.com"}
            )
            if created:
                user.set_password(options["password"])
                user.save()
            users[role] = user
        workspace = Workspace.objects.create(
            name="Fieldnotes Studio",
            slug="fieldnotes",
            description="An independent collection of ideas on creativity, thoughtful technology and making things that matter.",
        )
        for role, user in users.items():
            Membership.objects.create(workspace=workspace, user=user, role=role)
        for index, (title, slug, excerpt, state) in enumerate(STORIES):
            body = f"## A little room to think\n\n{excerpt}\n\nWe started with a simple question: what would this look like if we gave it the time and attention it deserved?\n\nThe answer wasn’t a bigger plan. It was a smaller, clearer first step.\n\n## What we’re learning\n\n- Make the first version simple enough to finish.\n- Ask someone else to take a look.\n- Keep the changes that make things clearer.\n\n> Good work rarely arrives fully formed. It gets there one thoughtful revision at a time.\n\n## Where we go from here\n\nWe’re sharing these notes as we go. Some ideas will change. Some will grow. That’s part of the process."
            page = create_page(
                users["author"] if index % 2 == 0 else users["editor"],
                workspace,
                title=title,
                slug=slug,
                excerpt=excerpt,
                body=body,
            )
            if state != "draft":
                page = transition(
                    users["editor"],
                    workspace,
                    page.pk,
                    expected_version=page.version,
                    action="submit",
                )
            if state == "published":
                page = transition(
                    users["editor"],
                    workspace,
                    page.pk,
                    expected_version=page.version,
                    action="publish",
                )
            elif state == "scheduled":
                transition(
                    users["editor"],
                    workspace,
                    page.pk,
                    expected_version=page.version,
                    action="schedule",
                    scheduled_for=timezone.now() + timedelta(days=2),
                )
            if index == 0:
                update_page(
                    users["editor"],
                    workspace,
                    page.pk,
                    expected_version=page.version,
                    title=title,
                    excerpt=excerpt,
                    body=body + "\n\nA new paragraph, still in draft.",
                )
        self.stdout.write(
            self.style.SUCCESS("Demo ready: /workspace/fieldnotes/ and /sites/fieldnotes/")
        )
        self.stdout.write(
            "Accounts: owner, editor, author, viewer. Password: the value you supplied."
        )
