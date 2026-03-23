from django.db import models


class RemoteNode(models.Model):
    """
    Represents a connected node in the distributed social network.
    
    Stores the connection details (URL, credentials) needed to authenticate
    with remote nodes when sending posts, likes, comments, and follow requests.
    
    The is_active flag can be used to disable a node connection without
    deleting it, allowing the admin to stop sharing with that node.
    """
    url = models.URLField(max_length=255, unique=True, help_text="Base URL of the remote node")
    username = models.CharField(max_length=150, help_text="Username for HTTP Basic Auth")
    password = models.CharField(max_length=128, help_text="Password for HTTP Basic Auth")
    is_active = models.BooleanField(default=True, help_text="Whether this node can connect")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Remote Node'
        verbose_name_plural = 'Remote Nodes'

    def __str__(self):
        return self.url

    def get_host(self):
        """Returns the base host URL without trailing slash."""
        return self.url.rstrip('/')
    
    def disable(self):
        """Disables this node from connecting."""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    def enable(self):
        """Enables this node to connect."""
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])
