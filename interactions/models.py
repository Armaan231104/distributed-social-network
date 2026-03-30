from django.db import models
from django.contrib.auth.models import User
from posts.models import Entry
from accounts.models import Author
from accounts.utils import get_host_url
import uuid


class Comment(models.Model):
    """
    Represents a comment on a post
    An author can comment on a post they have access to
    """
    id = models.UUIDField(primary_key=True, max_length=255, unique=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    contentType = models.CharField(max_length=50, default='text/plain')
    created_at = models.DateTimeField(auto_now_add=True)
    fqid = models.URLField(max_length=500, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.fqid:
            host = get_host_url()
            # Extract serial from author FQID (e.g., http://host/api/authors/1/ -> 1)
            author_serial = str(self.author.id).rstrip('/').split('/')[-1]
            self.fqid = f"{host}/api/authors/{author_serial}/commented/{self.id}"
            super().save(update_fields=["fqid"])

    class Meta:
        ordering = ['created_at']

class Like(models.Model):
    """
    Represents a like on a post or comment

    An author can like any post or comment they have access to.
    A Like targets exactly one object: either an Entry or a Comment (never both,
    never neither). The constraints below ensures that an author
    cannot like the same entry or the same comment more than once, preventing
    duplicate rows from accumulating in the database over time.

    Constraints:
    - unique_like_author_entry: one Like per (author, entry) pair when entry is set.
    - unique_like_author_comment: one Like per (author, comment) pair when comment is set.
    """
    id = models.UUIDField(primary_key=True, max_length=255, unique=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='likes')
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='likes', null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='likes', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    fqid = models.URLField(max_length=500, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if not self.fqid:
            host = get_host_url()
            # Extract serial from author FQID (e.g., http://host/api/authors/1/ -> 1)
            author_serial = str(self.author.id).rstrip('/').split('/')[-1]
            self.fqid = f"{host}/api/authors/{author_serial}/liked/{self.id}"
            super().save(update_fields=["fqid"])

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['author', 'entry'],
                condition=models.Q(entry__isnull=False),
                name='unique_like_author_entry',
            ),
            models.UniqueConstraint(
                fields=['author', 'comment'],
                condition=models.Q(comment__isnull=False),
                name='unique_like_author_comment',
            ),
        ]
        ordering = ['-created_at']

