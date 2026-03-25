"""
Shared utilities for the accounts app.

Contains functions used across multiple modules to avoid code duplication.
"""
from django.conf import settings

def get_host_url():
    """
    Get this node's base URL for constructing FQIDs.
    Pulls directly from settings to ensure background tasks and signals
    always have the correct absolute URL.
    """
    return getattr(settings, 'NODE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')


def normalize_fqid(author_id):
    """
    Normalize an author ID to a proper FQID format with trailing slash.
    
    Handles:
    - IDs without trailing slash: "http://host/api/authors/1" -> "http://host/api/authors/1/"
    - Raw local IDs: "1" -> "http://host/api/authors/1/"
    - Already normalized IDs: "http://host/api/authors/1/" -> "http://host/api/authors/1/"
    
    Returns the normalized FQID string.
    """
    if not author_id:
        return None
    
    author_id_str = str(author_id)
    
    # Ensure trailing slash
    if not author_id_str.endswith('/'):
        author_id_str += '/'
    
    # If it's a raw local ID (no http), build the FQID
    if not author_id_str.startswith('http'):
        host_url = get_host_url()
        author_id_str = f"{host_url}/api/authors/{author_id_str}"
    
    return author_id_str


# utils.py - make more flexible
def is_local_author(author_id):
    if not author_id:
        return False
    
    host_url = get_host_url()
    # Match with OR without port
    local_hosts = [
        host_url.rstrip(':8000'),  # http://127.0.0.1
        host_url,                  # http://127.0.0.1:8000
    ]
    return any(author_id.startswith(h) for h in local_hosts)
