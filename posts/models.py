from django.db import models
from django.contrib.auth.models import User
import uuid


class Entry(models.Model):
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
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="PUBLIC")
    published_at = models.DateTimeField(auto_now_add=True)
    
    content_type = models.CharField(
        max_length = 20,
        choices=CONTENT_TYPES,
        default = "text/plain"
    )
    
    image = models.ImageField(upload_to="entries/", blank=True, null=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return f"{self.title} by {self.author.username}"

    def soft_delete(self):
        self.visibility = "DELETED"
        self.save()
