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
    - Localhost switching: "http://127.0.0.1:8000/api/authors/1/" -> "https://deployed-host.com/api/authors/1/"
    """
    if not author_id:
        return None
    
    author_id_str = str(author_id)
    host_url = get_host_url().rstrip('/')
    
    # Replace localhost with deployed host if we are running on prod directly.
    if "127.0.0.1:8000" in author_id_str or "localhost:8000" in author_id_str:
        author_id_str = author_id_str.replace("http://127.0.0.1:8000", host_url)
        author_id_str = author_id_str.replace("http://localhost:8000", host_url)

    # older versions used a raw id so this helps with compatibility
    if not author_id_str.startswith('http'):
        clean_id = author_id_str.strip('/')
        author_id_str = f"{host_url}/api/authors/{clean_id}"

    if not author_id_str.endswith('/'):
        author_id_str += '/'

    return author_id_str


def is_local_author(author_id):
    """
    Check if an author ID belongs to this node.
    """
    if not author_id:
        return False
    
    # normalize the host url in case of trailing slashes
    host_url = get_host_url().rstrip('/')
    author_id_str = str(author_id)
    
    # add a '/' to the end of the author_id_str to prevent substring hijacking
    return author_id_str.startswith(f"{host_url}/")
