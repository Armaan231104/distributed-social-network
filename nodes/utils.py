import requests
from nodes.models import RemoteNode
from posts.utils import encode_image

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