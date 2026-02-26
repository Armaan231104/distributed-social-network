from django.db import models
from django.contrib.auth.models import User


class Author(models.Model):
    """
    Represents a user in the distributed social network.
    Each author has a unique FQID (Fully Qualified ID) like http://127.0.0.1/api/authors/1/
    Remote authors from other nodes also have FQIDs pointing to their servers.
    """
    id = models.URLField(max_length=255, unique=True, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='author', null=True, blank=True)
    host = models.URLField(max_length=255)
    displayName = models.CharField(max_length=255)
    github = models.URLField(max_length=255, blank=True, null=True)
    profileImage = models.URLField(max_length=255, blank=True, null=True)
    web = models.URLField(max_length=255, blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.displayName

    @property
    def is_local(self):
        from django.conf import settings
        allowed = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else '127.0.0.1'
        allowed = allowed.replace('https://', '').replace('http://', '').rstrip('/')
        host = self.host.replace('https://', '').replace('http://', '').rstrip('/')
        return allowed in host or host in allowed

    def get_followers_count(self):
        return self.followers.count()

    def get_following_count(self):
        return self.following.count()

    def is_followed_by(self, author):
        return self.followers.filter(follower=author).exists()

    def is_following(self, author):
        return self.following.filter(followee=author).exists()

    def is_friend(self, author):
        return self.is_following(author) and author.is_following(self)


class FollowRequest(models.Model):
    """
    Tracks follow requests between authors.
    Status can be: pending, accepted, rejected.
    When an author wants to follow you, you get a request you can approve or deny.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        REJECTED = 'rejected', 'Rejected'

    actor = models.ForeignKey(
        Author, 
        on_delete=models.CASCADE, 
        related_name='sent_follow_requests'
    )
    object = models.ForeignKey(
        Author, 
        on_delete=models.CASCADE, 
        related_name='received_follow_requests'
    )
    summary = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['actor', 'object']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.actor.displayName} -> {self.object.displayName} ({self.status})"


class Follow(models.Model):
    """
    An accepted follow relationship between two authors.
    When someone follows you and you approve, this is created.
    """
    follower = models.ForeignKey(
        Author, 
        on_delete=models.CASCADE, 
        related_name='following'
    )
    followee = models.ForeignKey(
        Author, 
        on_delete=models.CASCADE, 
        related_name='followers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['follower', 'followee']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.follower.displayName} follows {self.followee.displayName}"
