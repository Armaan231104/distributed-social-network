import requests
from nodes.models import RemoteNode
from posts.utils import encode_image


def get_remote_inbox_url(author_fqid):
    """Build a remote inbox URL from a fully-qualified author ID."""
    return f"{str(author_fqid).rstrip('/')}/inbox/"


def get_remote_author_entries_url(author_fqid):
    """Build a remote author entries URL from a fully-qualified author ID."""
    return f"{str(author_fqid).rstrip('/')}/entries/"


def find_remote_node_for_url(url):
    """
    Match a remote URL to a configured RemoteNode.

    Supports nodes saved either as a bare host (https://node.example)
    or with an API suffix (https://node.example/api).
    """
    if not url:
        return None

    normalized_url = str(url).rstrip('/')

    for node in RemoteNode.objects.filter(is_active=True):
        node_url = node.url.rstrip('/')
        node_api_url = f"{node_url}/api"

        if normalized_url.startswith(node_url) or normalized_url.startswith(node_api_url):
            return node

    return None

def send_entry_to_remote(entry):
    nodes = RemoteNode.objects.filter(is_active=True)

    print("SENDING ENTRY TO REMOTES...")

    author = entry.author.author

    for node in nodes:
        try:
            print(f"Sending to {node.url}")

            author_id = author.id.rstrip('/')

            inbox_url = f"{node.get_host()}/api/authors/{author_id.split('/')[-1]}/inbox/"

            payload = {
                "type": "entry",
                "id": entry.fqid,
                "title": entry.title,
                "content": entry.content,
                "visibility": entry.visibility,
                "author": {
                    "id": author.id,
                    "displayName": author.displayName,
                    "host": author.host,
                }
            }

            if entry.image:
                encoded = encode_image(entry)
                payload["contentType"] = "image/png;base64"
                payload["content"] = encoded
            else:
                payload["contentType"] = entry.content_type

            response = requests.post(
                inbox_url,
                json=payload,
                auth=(node.username, node.password),
                timeout=10
            )

            print(f"Response status: {response.status_code}")
            print(response.text)

        except Exception as e:
            print(f"Failed to send entry to {node.url}: {e}")
