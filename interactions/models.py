from django.db import models
from django.contrib.auth.models import User
from posts.models import Entry
from accounts.models import Author


class Like(models.Model):
    """
    Represents a like on a post.
    A user/author can like a post, with a timestamp of when the like was made.
    """
    id = models.URLField(max_length=255, unique=True, primary_key=True)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='likes')
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('author', 'entry')
        ordering = ['-created_at']
