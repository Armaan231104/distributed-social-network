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


def validate_remote_node_credentials(url, username, password):
    """
    Validate that a remote node is reachable and accepts the provided credentials.

    Returns a tuple: (is_valid, error_message).
    """
    base_url = str(url).rstrip('/')
    probe_urls = (
        f"{base_url}/api/authors/",
        f"{base_url}/api/",
        base_url,
    )

    try:
        for probe_url in probe_urls:
            response = requests.get(
                probe_url,
                auth=(username, password),
                timeout=5,
                headers={"Accept": "application/json"},
            )

            if 200 <= response.status_code < 300:
                return True, None

            if response.status_code in (401, 403):
                return False, "Connection failed. Check that the username and password are correct."

            if response.status_code != 404:
                return False, (
                    f"Connection failed. The remote node responded with status "
                    f"{response.status_code}."
                )

        return False, (
            "Connection failed. Check that the base URL points to a compatible node."
        )
    except requests.exceptions.MissingSchema:
        return False, "Connection failed. Enter a valid URL including http:// or https://."
    except requests.exceptions.ConnectionError:
        return False, "Connection failed. The remote node could not be reached at that URL."
    except requests.exceptions.Timeout:
        return False, "Connection failed. The remote node took too long to respond."
    except requests.RequestException:
        return False, "Connection failed. Unable to verify the remote node right now."

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
