"""
Shared utilities for the accounts app.

Contains functions used across multiple modules to avoid code duplication.
"""
# accounts/utils.py
from django.conf import settings

def get_host_url():
    """
    Get this node's base URL for constructing FQIDs.
    Pulls directly from settings to ensure background tasks and signals
    always have the correct absolute URL.
    """
    # Grab the URL and strip any accidental trailing slashes
    return getattr(settings, 'NODE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')

def is_local_author(author_id):
    """Check if an author ID belongs to this node."""
    if not author_id:
        return False
    
    host_url = get_host_url()
    return author_id.startswith(host_url)
