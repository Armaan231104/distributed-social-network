from django.core.management.base import BaseCommand
from posts.github_sync import sync_github_activity

class Command(BaseCommand):
    help = "Sync GitHub activity"
    def handle(self, *args, **kwargs):
        sync_github_activity()
        self.stdout.write(self.style.SUCCESS("GitHub sync complete"))