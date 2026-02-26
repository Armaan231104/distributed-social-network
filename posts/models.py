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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="PUBLIC")

    def soft_delete(self):
        self.visibility = "DELETED"
        self.save()
