"""
Shared utilities for the accounts app.

Contains functions used across multiple modules to avoid code duplication.
"""
from django.conf import settings


def get_host_url():
    """Get this node's base URL for constructing FQIDs."""
    allowed_host = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
    if 'localhost' in allowed_host or '127.0.0.1' in allowed_host:
        return f'http://{allowed_host.rstrip("/")}'
    return f'https://{allowed_host.rstrip("/")}'


def is_local_author(author_id):
    """
    Check if an author ID belongs to this node (local) or a remote node.
    
    Compares the author ID against all known local hosts, not just the first one.
    This handles localhost, 127.0.0.1, and production domains correctly.
    """
    local_hosts = []
    for host in settings.ALLOWED_HOSTS:
        h = host.replace('https://', '').replace('http://', '').rstrip('/')
        if ':' in h:
            h = h.split(':')[0]
        local_hosts.append(h)
    
    author_host = author_id.replace('https://', '').replace('http://', '').rstrip('/')
    if ':' in author_host:
        author_host = author_host.split(':')[0]
    
    return any(author_host == h or author_host.startswith(h + '/') for h in local_hosts)
