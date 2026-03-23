from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.conf import settings
from .models import Author
from .views import get_host_url


@receiver(post_save, sender=User)
def create_author(sender, instance, created, **kwargs):
    """
    When a new User is created, automatically create an Author profile.
    New normal users require approval.
    Staff/admin users are approved automatically.
    """
    if created:
        # Use the centralized get_host_url function for consistency
        host_url = get_host_url() + '/api/'

        author_id = f'{host_url}authors/{instance.id}/'

        Author.objects.create(
            id=author_id,
            user=instance,
            host=host_url,
            displayName=instance.get_full_name() or instance.username,
            is_approved=instance.is_staff or instance.is_superuser,
        )