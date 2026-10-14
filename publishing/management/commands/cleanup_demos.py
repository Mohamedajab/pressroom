from django.core.management.base import BaseCommand

from publishing.demo import cleanup_expired


class Command(BaseCommand):
    help = "Remove expired visitor demo workspaces and their dedicated accounts."

    def handle(self, *args, **options):
        self.stdout.write(f"Removed {cleanup_expired()} expired demos.")
