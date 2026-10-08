from django.core.management.base import BaseCommand

from publishing.services import publish_due


class Command(BaseCommand):
    help = "Publish approved scheduled revisions whose publication time has arrived."

    def handle(self, *args, **options):
        count = publish_due()
        self.stdout.write(self.style.SUCCESS(f"Published {count} scheduled page(s)."))
