from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from accounts.models import Author
from accounts.views import verify_remote_author_exists, get_or_create_remote_author

class Command(BaseCommand):
    help = 'Sync remote author data from their nodes'

    def handle(self, *args, **kwargs):
        stale_threshold = timezone.now() - timedelta(minutes=10)
        stale_authors = Author.objects.filter(
            user=None,
            updated_at__lt=stale_threshold
        )

        self.stdout.write(f"Syncing {stale_authors.count()} remote authors...")

        for author in stale_authors:
            fresh_data = verify_remote_author_exists(author.id)
            if fresh_data:
                get_or_create_remote_author(author.id, fresh_data)
                self.stdout.write(f"  ✓ Synced {author.displayName}")
            else:
                self.stdout.write(f"  ✗ Could not reach {author.id}")

        self.stdout.write("Done.")