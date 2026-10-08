import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from publishing.models import Membership, Workspace


class Command(BaseCommand):
    help = "Create a workspace with an owner. Prompts for a password only for a new account."

    def add_arguments(self, parser):
        parser.add_argument("slug")
        parser.add_argument("--name", required=True)
        parser.add_argument("--username", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        if Workspace.objects.filter(slug=options["slug"]).exists():
            raise CommandError("This workspace slug is already in use.")
        user = get_user_model().objects.filter(username=options["username"]).first()
        if user is None:
            user = get_user_model()(username=options["username"])
            password = getpass.getpass("Password for the new owner account: ")
            if password != getpass.getpass("Confirm password: "):
                raise CommandError("Passwords do not match.")
            validate_password(password, user)
            user.set_password(password)
            user.full_clean()
            user.save()
        workspace = Workspace(name=options["name"], slug=options["slug"])
        workspace.full_clean()
        workspace.save()
        Membership.objects.create(workspace=workspace, user=user, role="owner")
        self.stdout.write(self.style.SUCCESS(f"Workspace {workspace.slug} is ready."))
