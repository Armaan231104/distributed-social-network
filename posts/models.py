from django.db import models
from django.contrib.auth.models import User
import uuid
from datetime import timedelta
from accounts.utils import get_host_url
from accounts.models import Author
from django.conf import settings
from cloudinary_storage.storage import MediaCloudinaryStorage

# The following class edited by Open AI, Chat GPT 5.2, "please adjust this class to properly handle image, plaintext, and commonmark input", 2026-02-26 
class Entry(models.Model):
    """
    Represents a post created by a local user on this node.

    Supports: Plain text posts, Markdown posts, Image posts

    Visibility Levels:
    - PUBLIC: Visible to everyone.
    - UNLISTED: Accessible via direct link.
    - FRIENDS: Restricted to mutual followers (friends).
    - DELETED: Soft-deleted entry. Hidden from all users except node admins.

    Soft deletion keeps the entry in the database but changes its visibility to DELETED.
    """

    if not settings.DEBUG:
        image_storage = MediaCloudinaryStorage()
    else:
        image_storage = None  # uses default local storage

    VISIBILITY_CHOICES = [
        ("PUBLIC", "Public"),
        ("UNLISTED", "Unlisted"),
        ("FRIENDS", "Friends"),
        ("DELETED", "Deleted"),
    ]

    CONTENT_TYPES = [
        ("text/plain", "Plain Text"),
        ("text/markdown", "CommonMark"),
        ("image", "Image"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fqid = models.URLField(max_length=500, null=True, blank=True, unique=True)
    github_event_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )
    # local user, null if remote entry
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts', null=True, blank=True)
    # remote author
    remote_author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='remote_posts', null=True, blank=True)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="PUBLIC", db_index=True)
    published_at = models.DateTimeField(auto_now_add=True, db_index=True)

    updated_at = models.DateTimeField(auto_now=True)
    
    content_type = models.CharField(
        max_length = 20,
        choices=CONTENT_TYPES,
        default = "text/plain"
    )
    
    image = models.ImageField(upload_to="entries/", blank=True, null=True, storage=image_storage)

    class Meta:
        """
        Default ordering: newest entries first.
        """
        ordering = ['-published_at']

    def __str__(self):
        """
        Returns a readable representation of the entry.
        """
        return f"{self.title} by {self.author.username}"

    def soft_delete(self):
        """
        Performs a soft delete by setting visibility to DELETED.

        The entry remains in the database but becomes inaccessible
        to non-admin users.
        """
        self.visibility = "DELETED"
        self.save()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.fqid:
            host = get_host_url()

            if hasattr(self.author, "author"):
                author_obj = self.author.author
                author_id = author_obj.id
            else:
                return

            author_id = author_obj.id.rstrip("/")  # remove trailing /

            self.fqid = f"{author_id}/entries/{self.id}"
            super().save(update_fields=["fqid"])

    @property
    def is_edited(self):
        return (self.updated_at - self.published_at) > timedelta(seconds=1)
    @property
    def get_author(self):
        """Returns the Author object for this post. Prefer local author over remote."""
        if self.author:
            try:
                return self.author.author  # The local Author linked to the Django User
            except Exception:
                pass
        return self.remote_author
    
class HostedImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="hosted_images")

    if not settings.DEBUG:
        image_storage = MediaCloudinaryStorage()
    else:
        image_storage = None
    uploaded_at = models.DateTimeField(auto_now_add=True)


    image = models.ImageField(upload_to="hosted_images/",storage=image_storage)

    def __str__(self):
        return f"{self.author.username} - {self.id}"