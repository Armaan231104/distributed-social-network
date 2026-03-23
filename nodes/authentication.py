"""
Node-to-node authentication using HTTP Basic Auth.

This module provides authentication for remote nodes attempting to connect
to this node's API endpoints. It validates credentials against stored
RemoteNode records and this node's own credentials from settings.
"""
import base64
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import RemoteNode


class RemoteNodeUser:
    """
    Represents a remote node as an authenticated user.
    
    This is a pseudo-user object that represents an authenticated
    remote node for authorization purposes.
    """
    def __init__(self, node_id, url, username):
        self.id = node_id
        self.node_url = url
        self.username = username
        self.is_authenticated = True
        self.is_remote_node = True
        self.is_local = False

    def __str__(self):
        return f"remote_node:{self.username}@{self.node_url}"


class LocalNodeUser:
    """
    Represents this node's own authentication for node-to-node requests.
    """
    def __init__(self):
        self.id = 'local'
        self.username = 'local_node'
        self.is_authenticated = True
        self.is_remote_node = False
        self.is_local = True

    def __str__(self):
        return "local_node"


def get_node_credentials():
    """
    Get this node's credentials from settings.
    
    These are used when OTHER nodes connect to THIS node.
    """
    username = getattr(settings, 'NODE_USERNAME', 'admin')
    password = getattr(settings, 'NODE_PASSWORD', 'password')
    return username, password


def authenticate_remote_node(auth_header):
    """
    Authenticate a remote node using HTTP Basic Auth.
    
    Args:
        auth_header: The value of the Authorization header (e.g., "Basic dXNlcm5hbWU6cGFzc3dvcmQ=")
    
    Returns:
        A tuple of (user, auth_info) if authenticated, None otherwise.
        The auth_info contains the node that was authenticated.
    """
    if not auth_header or not auth_header.startswith('Basic '):
        return None
    
    try:
        encoded_credentials = auth_header[6:]
        decoded = base64.b64decode(encoded_credentials).decode('utf-8')
        # Split only on first colon - password may contain colons
        username, password = decoded.split(':', 1)
    except Exception:
        return None
    
    # First, check against stored remote nodes
    # Must match both username AND a node that we know about
    node = RemoteNode.objects.filter(
        username=username,
        is_active=True
    ).first()
    
    if node and node.password == password:
        user = RemoteNodeUser(node.id, node.url, node.username)
        return (user, {'type': 'remote_node', 'node': node})

    # Second, check against this node's own credentials (from settings)
    local_username, local_password = get_node_credentials()
    if username == local_username and password == local_password:
        user = LocalNodeUser()
        return (user, {'type': 'local_node'})

    return None


def get_remote_node_auth(request):
    """
    Get the authenticated remote node from a request.
    
    Checks the Authorization header and validates credentials.
    
    Args:
        request: The Django HTTP request object
    
    Returns:
        A user object if authenticated, None otherwise.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    result = authenticate_remote_node(auth_header)
    
    if result:
        return result[0]
    return None


class RemoteNodeAuthentication(BaseAuthentication):
    """
    Django REST Framework authentication class for remote node requests.
    
    This class authenticates requests from remote nodes using HTTP Basic Auth.
    It validates credentials against stored RemoteNode records and this node's
    own credentials from settings.
    
    Usage in DRF views:
        from nodes.authentication import RemoteNodeAuthentication
        
        class MyView(APIView):
            authentication_classes = [RemoteNodeAuthentication]
            permission_classes = [IsAuthenticated]
    """
    
    def authenticate(self, request):
        """
        Authenticate the request using HTTP Basic Auth.
        
        Returns a tuple of (user, auth_info) if successful, None if no
        authentication credentials were provided.
        
        Raises:
            AuthenticationFailed: If credentials are provided but invalid.
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return None
        
        if not auth_header.startswith('Basic '):
            return None
        
        result = authenticate_remote_node(auth_header)
        
        if result is None:
            raise AuthenticationFailed('Invalid credentials')
        
        user, auth_info = result
        return (user, auth_info)
    
    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the WWW-Authenticate
        header in a 401 response, when returning challenge for authentication.
        """
        return 'Basic realm="Node-to-Node Authentication"'
