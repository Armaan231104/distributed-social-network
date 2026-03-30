from django.db import models
from django.contrib.auth.models import User
import uuid
from datetime import timedelta
from accounts.utils import get_host_url
from accounts.models import Author
from django.conf import settings
from cloudinary_storage.storage import MediaCloudinaryStorage

class Entry(models.Model):
    """
    Represents a post (text, markdown, or image).
    Local posts use 'author' + 'image' field.
    Remote posts use 'remote_author' + 'image_url' or base64 in 'content'.
    """
    if not settings.DEBUG:
        image_storage = MediaCloudinaryStorage()
    else:
        image_storage = None

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

    # Local author (linked to Django User)
    author = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='posts', 
        null=True, 
        blank=True
    )
    
    # Remote author
    remote_author = models.ForeignKey(
        Author, 
        on_delete=models.CASCADE, 
        related_name='remote_posts', 
        null=True, 
        blank=True
    )

    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(blank=True)
    
    visibility = models.CharField(
        max_length=10, 
        choices=VISIBILITY_CHOICES, 
        default="PUBLIC", 
        db_index=True
    )
    
    published_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    content_type = models.CharField(
        max_length=20,
        choices=CONTENT_TYPES,
        default="text/plain"
    )

    # Main image field for locally uploaded images
    image = models.ImageField(
        upload_to="entries/", 
        blank=True, 
        null=True, 
        storage=image_storage
    )

    # For remote images or external URLs
    image_url = models.URLField(max_length=1000, blank=True, null=True)

    github_event_id = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        author = self.get_author
        name = author.displayName if author else "Unknown"
        return f"{self.title} by {name}"

    def soft_delete(self):
        self.visibility = "DELETED"
        self.save()

    def save(self, *args, **kwargs):
        # Generate fqid for local entries only
        if not self.fqid and self.author:
            try:
                author_obj = self.author.author  # local Author
                base = author_obj.id.rstrip('/')
                self.fqid = f"{base}/entries/{self.id}/"
            except Exception:
                pass  # remote entries don't need auto fqid here

        super().save(*args, **kwargs)

    @property
    def is_edited(self):
        return (self.updated_at - self.published_at) > timedelta(seconds=1)

    @property
    def get_author(self):
        """Return the Author object - prefer local over remote."""
        if self.author:
            try:
                return self.author.author
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