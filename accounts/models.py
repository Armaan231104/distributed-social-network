import uuid
from django.db import models
from django.contrib.auth.models import User


def generate_author_id():
    return str(uuid.uuid4())


class Author(models.Model):
    """
    Author model represents a user in the distributed social network.
    
    The id field uses a fully qualified URL (FQID) to uniquely identify
    authors across different nodes in the federation. This prevents
    ID collisions when different nodes have authors with the same local ID.
    Per spec: "all API objects are identified using fully qualified URLs (FQIDs)"
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
    
    Separating FollowRequest from Follow allows the system to support
    approval workflows - authors can approve or deny follow requests
    rather than having all follows be automatic.
    Per spec: "As an author, I want to be able to approve or deny other 
    authors following me"
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
    Represents an accepted follow relationship between two authors.
    
    Using a separate model for accepted follows (vs pending requests)
    enables efficient queries for followers/following lists and
    simplifies the "friends" detection (mutual follows).
    Per spec: "my node will know about my followers, who I am following, 
    and my friends"
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
