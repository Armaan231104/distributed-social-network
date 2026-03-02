from django.db import models
from django.contrib.auth.models import User
from posts.models import Entry
from accounts.models import Author
import uuid


class Comment(models.Model):
    """
    Represents a comment on a post.
    A user/author can comment on a post.
    """
    id = models.UUIDField(primary_key=True, max_length=255, unique=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

class Like(models.Model):
    """
    Represents a like on a post.
    A user/author can like a post, with a timestamp of when the like was made.
    """
    id = models.UUIDField(primary_key=True, max_length=255, unique=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='likes')
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='likes', null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='likes', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('author', 'entry')
        unique_together = ('author', 'comment')
        ordering = ['-created_at']

