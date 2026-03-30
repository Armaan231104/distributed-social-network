from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.views import View
from django.conf import settings
import json
import requests

from posts.models import Entry
from accounts.models import Author
from .models import Like, Comment
from nodes.models import RemoteNode
from nodes.utils import find_remote_node_for_url
from .serializers import (
    LikeSerializer, CommentSerializer,
    serialize_likes, serialize_comments
)


def user_can_access_entry(user, entry):
    """
    Checks if the user has access to the entry based on entry visibility.

    Visibility rules:
    - PUBLIC / UNLISTED: Accessible by anyone
    - DELETED: Accessible only to node admins (is_staff)
    - FRIENDS: Accessible only to the author or mutual followers (friends)
    - Any other visibility types: denied
    """
    if entry.visibility in ['PUBLIC', 'UNLISTED']:
        return True
    if entry.visibility == 'DELETED':
        return user.is_authenticated and user.is_staff
    if entry.visibility == 'FRIENDS':
        if not user.is_authenticated:
            return False
        if user == entry.author:
            return True
        try:
            author = user.author
            entry_author = entry.get_author
            return bool(entry_author and author.is_friend(entry_author))
        except Exception:
            return False
    return False


def get_author_by_serial(author_id):
    """Look up an Author by their serial or FQID.
    
    Handles both:
    - Serial IDs (e.g., "1") - converted to local FQID
    - Full FQIDs (e.g., "http://remote.com/api/authors/1/") - kept as-is
    """
    from accounts.utils import normalize_fqid
    normalized_id = normalize_fqid(author_id)
    return get_object_or_404(Author, id=normalized_id)


# ── UI views ──

@login_required
@require_POST
def toggle_like(request, object_type, object_id):
    """
    Checks if the object (comment or entry) has been liked by the user, then
    either adds or deletes a like depending on current status.
    """
    print(f"\n=== TOGGLE LIKE START ===")
    print(f"User: {request.user.username}")
    print(f"Object type: {object_type}")
    print(f"Object ID: {object_id}")
    
    liking_author = request.user.author
    target_author = None

    if object_type == 'entry':
        obj = get_object_or_404(Entry, id=object_id)
        if not user_can_access_entry(request.user, obj):
            return JsonResponse({'error': 'Forbidden'}, status=403)

        target_author = obj.get_author
        object_url = obj.fqid
        
        print(f"Entry title: {obj.title}")
        print(f"Entry author: {obj.author}")
        print(f"Entry remote_author: {obj.remote_author}")
        print(f"target_author (via get_author): {target_author}")
        print(f"target_author.is_local: {target_author.is_local}")
        print(f"object_url (FQID): {object_url}")

        like, created = Like.objects.get_or_create(author=liking_author, entry=obj, comment=None)

    elif object_type == 'comment':
        obj = get_object_or_404(Comment, id=object_id)
        print(f"Comment obj: {obj}")

        if not user_can_access_entry(request.user, obj.entry):
            return JsonResponse({'error': 'Forbidden'}, status=403)

        entry_author = obj.entry.get_author
        if not entry_author:
            print("Entry author not found")
            return JsonResponse({'error': 'Entry author not found'}, status=400)

        base_author_url = entry_author.id.rstrip('/')
        entry_id = str(obj.entry.id).strip('/')
        comment_id = str(obj.id).strip('/')

        entries_url = f"{base_author_url}/entries/{entry_id}/comments/{comment_id}/"
        posts_url = f"{base_author_url}/posts/{entry_id}/comments/{comment_id}/"

        # Prefer the format already stored on the comment/entry if available
        existing_comment_url = getattr(obj, "fqid", None) or getattr(obj, "id_url", None)
        entry_fqid = getattr(obj.entry, "fqid", None)

        print(f"existing_comment_url: {existing_comment_url}")
        print(f"entry_fqid: {entry_fqid}")
        print(f"entries_url: {entries_url}")
        print(f"posts_url: {posts_url}")

        if existing_comment_url:
            if "/posts/" in existing_comment_url:
                object_url = posts_url
            else:
                object_url = entries_url
        elif entry_fqid and "/posts/" in entry_fqid:
            object_url = posts_url
        else:
            object_url = entries_url

        like, created = Like.objects.get_or_create(
            author=liking_author,
            entry=None,
            comment=obj,
        )

    else:
        return JsonResponse({'error': 'invalid type'}, status=400)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    if target_author and not target_author.is_local:
        print(f"=== REMOTE DETECTED - SENDING TO REMOTE ===")
        print(f"target_author: {target_author.id}")
        if created:
            print(f"Sending NEW like to remote...")
            send_like_to_remote_inbox(liking_author, target_author, object_url)
        else:
            print(f"Sending UNDO like to remote...")
            send_undo_like_to_remote_inbox(liking_author, target_author, object_url)
    else:
        print(f"=== LOCAL AUTHOR - NOT SENDING TO REMOTE ===")

    return JsonResponse({'liked': liked, 'like_count': obj.likes.count()})


def send_like_to_remote_inbox(sender, recipient, object_url):
    """
    Sends a standard 'Like' activity to the recipient's inbox.
    Uses the same node lookup pattern as the rest of the codebase.
    """
    print(f"\n=== SEND LIKE TO REMOTE ===")
    print(f"sender: {sender.id}")
    print(f"recipient: {recipient.id}")
    print(f"object_url: {object_url}")
    
    inbox_url = recipient.id.rstrip('/') + '/inbox/'
    print(f"inbox_url: {inbox_url}")

    node = find_remote_node_for_url(recipient.id) or find_remote_node_for_url(recipient.host)
    if not node:
        print(f"ERROR: No credentials found for host: {recipient.host}")
        return None

    print(f"Found node: {node.url}")

    payload = {
        "type": "Like",
        "id": f"{sender.id.rstrip('/')}liked/{object_url}",
        "author": {
            "type": "author",
            "id": sender.id,
            "host": sender.host,
            "displayName": sender.displayName,
            "url": sender.id,
            "github": sender.github,
            "profileImage": sender.profileImage.url if sender.profileImage else None,
        },
        "object": object_url
    }

    try:
        response = requests.post(
            inbox_url,
            json=payload,
            auth=(node.username, node.password),
            timeout=5
        )
        print(f"Like sent to {inbox_url} → {response.status_code}")
        return response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Remote conn failed: {e}")
        return None


def send_undo_like_to_remote_inbox(sender, recipient, object_url):
    """
    Sends an 'Undo' wrapping a 'Like' to the recipient's inbox when a user unlikes.
    """
    print(f"\n=== SEND UNDO LIKE TO REMOTE ===")
    print(f"sender: {sender.id}")
    print(f"recipient: {recipient.id}")
    print(f"object_url: {object_url}")
    
    inbox_url = recipient.id.rstrip('/') + '/inbox/'
    print(f"inbox_url: {inbox_url}")

    node = find_remote_node_for_url(recipient.id) or find_remote_node_for_url(recipient.host)
    if not node:
        print(f"ERROR: No credentials found for host: {recipient.host}")
        return None

    print(f"Found node: {node.url}")

    payload = {
        "type": "Undo",
        "actor": {
            "type": "author",
            "id": sender.id,
            "host": sender.host,
            "displayName": sender.displayName,
            "url": sender.id,
            "github": sender.github,
            "profileImage": sender.profileImage.url if sender.profileImage else None,
        },
        "object": {
            "type": "Like",
            "author": {
                "type": "author",
                "id": sender.id,
                "host": sender.host,
                "displayName": sender.displayName,
                "url": sender.id,
                "github": sender.github,
                "profileImage": sender.profileImage.url if sender.profileImage else None,
            },
            "object": object_url
        }
    }

    try:
        response = requests.post(
            inbox_url,
            json=payload,
            auth=(node.username, node.password),
            timeout=5
        )
        print(f"Undo Like sent to {inbox_url} → {response.status_code}")
        return response.status_code
    except requests.exceptions.RequestException as e:
        print(f"Remote conn failed: {e}")
        return None


@login_required
def add_comment(request, entry_id):
    """
    UI view — create a comment and redirect back to the entry page.
    """
    print(f"\n=== ADD COMMENT START ===")
    print(f"User: {request.user.username}")
    print(f"Entry ID: {entry_id}")
    
    entry = get_object_or_404(Entry, id=entry_id)
    print(f"Entry title: {entry.title}")
    print(f"Entry author: {entry.author}")
    print(f"Entry remote_author: {entry.remote_author}")
    
    if not user_can_access_entry(request.user, entry):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    if request.method == 'POST':
        content = request.POST.get('content')
        print(f"Comment content: {content}")
        if content:
            comment = Comment.objects.create(
                entry=entry,
                author=request.user.author,
                content=content,
            )
            print(f"Comment created: {comment.id}")

            # Check if we should send to remote
            target_author = entry.get_author
            print(f"Comment target_author (via get_author): {target_author}")
            if target_author:
                print(f"target_author.is_local: {target_author.is_local}")
            
            if target_author and not target_author.is_local:
                print(f"=== REMOTE DETECTED - SENDING COMMENT TO REMOTE ===")
                send_comment_to_remote_inbox(comment, entry)
            else:
                print(f"=== LOCAL AUTHOR - NOT SENDING COMMENT TO REMOTE ===")

    return redirect('entry_detail', entry_id=entry_id)


def send_comment_to_remote_inbox(comment, entry):
    """Send a comment to the remote entry author's inbox."""
    print(f"\n=== SEND COMMENT TO REMOTE ===")
    print(f"Comment ID: {comment.id}")
    print(f"Comment FQID: {comment.fqid}")
    print(f"Entry: {entry.title}")
    
    remote_author = entry.remote_author
    print(f"remote_author: {remote_author}")
    
    if not remote_author or remote_author.is_local:
        print("NOT SENDING: remote_author is local or None")
        return

    node = find_remote_node_for_url(remote_author.id) or find_remote_node_for_url(remote_author.host)
    if not node:
        print(f"ERROR: No credentials found for host: {remote_author.host}")
        return

    print(f"Found node: {node.url}")
    
    inbox_url = f"{remote_author.id.rstrip('/')}/inbox/"
    print(f"inbox_url: {inbox_url}")

    payload = {
        'type': 'comment',
        'id': comment.fqid,
        'author': {
            'type': 'author',
            'id': comment.author.id,
            'displayName': comment.author.displayName,
            'host': comment.author.host,
            'github': comment.author.github or None,
            'profileImage': comment.author.profileImage.url if comment.author.profileImage else None,
            'web': comment.author.web or None,
        },
        'comment': comment.content,
        'contentType': getattr(comment, 'contentType', 'text/plain'),
        'published': comment.created_at.isoformat(),
        'entry': entry.fqid or str(entry.id),
    }

    inbox_url = f"{remote_author.id.rstrip('/')}/inbox/"
    try:
        requests.post(
            inbox_url,
            json=payload,
            auth=(node.username, node.password),
            timeout=5
        )
    except requests.RequestException:
        pass


# ── API views — comments ──

# The following API classes were written with assistance from Anthropic,
# Claude Sonnet 4.6, 2026-03-16

class EntryCommentsView(View):
    """GET comments on a specific entry."""
    def get(self, request, author_id, entry_id):
        from posts.views import get_entry_by_id
        entry = get_entry_by_id(entry_id)
        if not user_can_access_entry(request.user, entry):
            return JsonResponse({'error': 'Forbidden'}, status=403)
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', 5))
        return JsonResponse(serialize_comments(entry.comments.all(), page, size))


class CommentDetailView(View):
    """GET a single comment on a specific entry."""
    def get(self, request, author_id, entry_id, comment_id):
        from posts.views import get_entry_by_id
        entry = get_entry_by_id(entry_id)
        comment = get_object_or_404(Comment, id=comment_id, entry=entry)
        if not user_can_access_entry(request.user, comment.entry):
            return JsonResponse({'error': 'Forbidden'}, status=403)
        return JsonResponse(CommentSerializer(comment).data)


class AuthorCommentedView(View):
    """GET list of comments made by an author. POST to create a new comment."""
    def get(self, request, author_id):
        author = get_author_by_serial(author_id)
        comments = Comment.objects.filter(author=author)
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', 5))
        return JsonResponse(serialize_comments(comments, page, size))

    def post(self, request, author_id):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        entry_id = data.get('entry')
        content = data.get('comment', '').strip()
        if not entry_id or not content:
            return JsonResponse({'error': 'entry and comment fields required'}, status=400)

        entry = get_object_or_404(Entry, id=entry_id)
        if not user_can_access_entry(request.user, entry):
            return JsonResponse({'error': 'Forbidden'}, status=403)

        comment = Comment.objects.create(
            author=request.user.author,
            entry=entry,
            content=content,
            contentType=data.get('contentType', 'text/plain')
        )

        send_comment_to_remote_inbox(comment, entry)

        return JsonResponse(CommentSerializer(comment).data, status=201)


class CommentedDetailView(View):
    """GET a single comment by the author's serial and the comment's UUID."""
    def get(self, request, author_id, comment_id):
        author = get_author_by_serial(author_id)
        comment = get_object_or_404(Comment, id=comment_id, author=author)
        if not user_can_access_entry(request.user, comment.entry):
            return JsonResponse({'error': 'Forbidden'}, status=403)
        return JsonResponse(CommentSerializer(comment).data)


# ── API views — likes ──

class EntryLikesView(View):
    """GET likes on a specific entry."""
    def get(self, request, author_id, entry_id):
        from posts.views import get_entry_by_id
        entry = get_entry_by_id(entry_id)
        if not user_can_access_entry(request.user, entry):
            return JsonResponse({'error': 'Forbidden'}, status=403)
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', 50))
        return JsonResponse(serialize_likes(entry.likes.all(), page, size))


class AuthorLikedView(View):
    """GET list of things liked by an author."""
    def get(self, request, author_id):
        author = get_author_by_serial(author_id)
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', 50))
        return JsonResponse(serialize_likes(author.likes.all(), page, size))


class LikeDetailView(View):
    """GET a single like by the author's serial and the like's UUID."""
    def get(self, request, author_id, like_id):
        author = get_author_by_serial(author_id)
        like = get_object_or_404(Like, id=like_id, author=author)
        return JsonResponse(LikeSerializer(like).data)
