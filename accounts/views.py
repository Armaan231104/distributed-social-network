import requests
from urllib.parse import unquote
from django.contrib import messages
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.authentication import SessionAuthentication
from django.contrib.admin.views.decorators import staff_member_required
from nodes.authentication import RemoteNodeAuthentication
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm

from .models import Author, FollowRequest, Follow
from posts.models import Entry
from interactions.models import Like, Comment
from .forms import SignUpForm
from functools import wraps
from .serializers import (
    AuthorSerializer, AuthorListSerializer, 
    FollowRequestSerializer
)
from .utils import get_host_url, is_local_author, normalize_fqid
from nodes.utils import find_remote_node_for_url, get_remote_inbox_url
def resolve_profile_image(profile_image_val, host):
    """Normalize a profileImage value to a usable URL or None."""
    if not profile_image_val or not isinstance(profile_image_val, str):
        return None
    
    # base64 image — can't store as URL, skip
    if profile_image_val.startswith('data:'):
        return None
    
    # relative URL — prepend host
    if profile_image_val.startswith('/'):
        base = host.rstrip('/').replace('/api/', '').replace('/api', '')
        return base + profile_image_val
    
    # absolute URL — use as-is
    return profile_image_val

def build_local_author_id(user):
    host = get_host_url()
    return f"{host}/api/authors/{user.id}/"

def get_or_create_author(author_data):
    """Create or retrieve an author from remote data (e.g., from another node)."""
    author_id = author_data.get('id')
    if not author_id:
        return None

    author_id = normalize_fqid(author_id)
    
    existing = Author.objects.filter(id=author_id).first()
    if existing:
        return existing
    
    profile_image_val = author_data.get('profileImage')
    resolved_url = resolve_profile_image(profile_image_val, author_data.get('host', ''))

    return Author.objects.create(
        id=author_id,
        user=None,
        host=author_data.get('host', ''),
        displayName=author_data.get('displayName', 'Unknown'),
        github=author_data.get('github'),
        profileImage=profile_image_val if not isinstance(profile_image_val, str) else None,
        profileImageUrl=resolved_url,
        web=author_data.get('web'),
        is_approved=True,
    )


# Helpers for author lookup
# These handle the difference between local authors (user_id) and remote authors (FQID)

def get_current_author(request):
    """Get Author for the logged-in user."""
    return Author.objects.get(user=request.user)


def get_author_by_id(author_id):
    """Look up author by FQID using centralized normalization."""
    return Author.objects.get(id=normalize_fqid(author_id))

def verify_remote_author_exists(foreign_id):
    """
    Fetch the remote author URL and return their data if they exist, None otherwise.
    """
    node = find_remote_node_for_url(foreign_id)
    if not node:
        print(f"DEBUG: No node found for {foreign_id}")
        return None
    
    try:
        response = requests.get(
            foreign_id,
            auth=(node.username, node.password),
            timeout=10
        )

        print(f"DEBUG: Response status: {response.status_code}")
        print(f"DEBUG: Response body: {response.text}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Could not verify remote author at {foreign_id}: {e}")
        return None


def get_or_create_remote_author(foreign_id, remote_author=None):
    foreign_id = normalize_fqid(foreign_id)

    author, created = Author.objects.get_or_create(
        id=foreign_id,
        defaults={
            'host': foreign_id.split('/api/authors/')[0] + '/api/',
            'displayName': 'Remote Author',
            'is_approved': True,
        }
    )

    if remote_author:
        updated = False

        field_map = {
            "displayName": "displayName",
            "github": "github",
            "web": "web",
            "host": "host",
        }

        for api_field, model_field in field_map.items():
            new_val = remote_author.get(api_field)
            if new_val and getattr(author, model_field) != new_val:
                setattr(author, model_field, new_val)
                updated = True

        # Handle profileImage separately — remote nodes send it as a string URL
        profile_image_val = remote_author.get('profileImage')
        resolved_url = resolve_profile_image(profile_image_val, remote_author.get('host', ''))
        if resolved_url and author.profileImageUrl != resolved_url:
            author.profileImageUrl = resolved_url
            updated = True

        if updated:
            author.save()

    return author, created

def send_follow_to_remote(actor, target):
    if target.is_local:
        return True, None

    try:
        print(f"target.id: {target.id}")
        print(f"target.host: {target.host}")
        inbox_url = get_remote_inbox_url(target.id)

        follow_data = {
            'type': 'Follow',
            'summary': f'{actor.displayName} wants to follow {target.displayName}',
            'actor': AuthorSerializer(actor).data,
            'object': AuthorSerializer(target).data
        }

        node = find_remote_node_for_url(target.id) or find_remote_node_for_url(target.host)
        if not node:
            error = f"No active remote node credentials configured for {target.host}"
            print(error)
            return False, error

        response = requests.post(
            inbox_url,
            json=follow_data,
            timeout=30,  # increased from 10
            auth=(node.username, node.password)
        )

        response.raise_for_status()
        return True, None

    except requests.exceptions.ChunkedEncodingError:
        # Remote node closed connection mid-response but likely processed the request
        print("IncompleteRead — treating as success")
        return True, None
    except Exception as e:
        print(f"Failed to send follow request to remote node: {e}")
        return False, str(e)

def create_follow_request(actor, target):
    existing = FollowRequest.objects.filter(actor=actor, object=target).first()
    
    if existing:
        if existing.status == FollowRequest.Status.PENDING:
            return None, 'pending'
        elif existing.status == FollowRequest.Status.ACCEPTED:
            # Check if Follow actually exists — if not, the relationship is broken
            actually_following = Follow.objects.filter(follower=actor, followee=target).exists()
            if actually_following:
                return None, 'accepted'
            else:
                # stale accepted request, reset it
                existing.status = FollowRequest.Status.PENDING
                existing.save()
                return existing, 'resent'
        else:
            existing.status = FollowRequest.Status.PENDING
            existing.save()
            return existing, 'resent'
    
    return FollowRequest.objects.create(
        actor=actor,
        object=target,
        summary=f'{actor.displayName} wants to follow {target.displayName}',
        status=FollowRequest.Status.PENDING
    ), 'created'

class IsApprovedAuthor(BasePermission):
    """
    Allows access only to approved authors.
    Staff users are always allowed.
    """
    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_staff:
            return True

        try:
            return user.author.is_approved
        except Author.DoesNotExist:
            return False
        
# API Views
def approved_author_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        try:
            author = request.user.author
        except Author.DoesNotExist:
            return redirect("login")

        if not author.is_approved:
            return redirect("pending-approval")

        return view_func(request, *args, **kwargs)
    return wrapper

class AuthorListView(APIView):
    """List authors on this node."""
    authentication_classes = [RemoteNodeAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # If admin → see all authors
        if user.is_authenticated and getattr(user, 'is_superuser', False):
            authors = Author.objects.all()
        else:
            # Everyone else → only approved authors
            authors = Author.objects.filter(is_approved=True)

        serializer = AuthorListSerializer(authors, many=True)
        return Response({
            'type': 'authors',
            'authors': serializer.data
        })
    
class AuthorDetailView(APIView):
    """Get details for a specific author."""
    authentication_classes = [RemoteNodeAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, author_id):
        author_id = normalize_fqid(author_id)
        try:
            author = Author.objects.get(id=author_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = AuthorSerializer(author)
        return Response(serializer.data)


class FollowingListView(APIView):
    """Get list of authors this author is following."""
    authentication_classes = [RemoteNodeAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, author_id):
        author_id = normalize_fqid(author_id)
        try:
            author = Author.objects.get(id=author_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)
        
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 50))
        
        all_following = list(author.following.all())
        total = len(all_following)
        
        start = (page - 1) * size
        end = start + size
        paginated_following = all_following[start:end]
        
        following_authors = [f.followee for f in paginated_following]
        serializer = AuthorSerializer(following_authors, many=True)
        return Response({
            'type': 'following',
            'following': serializer.data,
            'page_number': page,
            'size': size,
            'count': total
        })


class FollowersListView(APIView):
    """Get list of authors who follow this author."""
    authentication_classes = [RemoteNodeAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, author_id):
        author_id = normalize_fqid(author_id)
        try:
            author = Author.objects.get(id=author_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)
        
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 50))
        
        all_followers = list(author.followers.all())
        total = len(all_followers)
        
        # pagination logic since the follower list could grow large.
        start = (page - 1) * size
        end = start + size
        paginated_followers = all_followers[start:end]
        
        follower_authors = [f.follower for f in paginated_followers]
        serializer = AuthorSerializer(follower_authors, many=True)
        return Response({
            'type': 'followers',
            'followers': serializer.data,
            'page_number': page,
            'size': size,
            'count': total
        })


class FriendsListView(APIView):
    """Get list of friends (mutual follows) for an author."""
    authentication_classes = [RemoteNodeAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, author_id):
        author_id = normalize_fqid(author_id)
        try:
            author = Author.objects.get(id=author_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)
        
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 50))
        
        all_friends = list(author.get_friends())
        total = len(all_friends)
        
        start = (page - 1) * size
        end = start + size
        paginated_friends = all_friends[start:end]
        
        serializer = AuthorSerializer(paginated_friends, many=True)
        return Response({
            'type': 'friends',
            'friends': serializer.data,
            'page_number': page,
            'size': size,
            'count': total
        })


class FollowView(APIView):
    """
    Handle following and unfollowing authors.
    
    Note: Follow requests go to inbox first, Follow only created after approval.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, author_id, foreign_id):
        """Send a follow request to another author."""
        current_author = get_current_author(request)
        
        # Normalize author_id to FQID for comparison
        author_id = normalize_fqid(author_id)
        
        if current_author.id != author_id:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        is_remote = str(foreign_id).startswith('http')
        
        if is_remote:
            author_data = verify_remote_author_exists(foreign_id)
            foreign_author, _ = get_or_create_remote_author(foreign_id, author_data)
        else:
            foreign_author = get_author_by_id(foreign_id)

        if current_author.id == foreign_author.id:
            return Response({'error': 'Cannot follow yourself'}, status=status.HTTP_400_BAD_REQUEST)

        if current_author.is_following(foreign_author):
            return Response({'error': 'Already following'}, status=status.HTTP_400_BAD_REQUEST)

        request_result, state = create_follow_request(current_author, foreign_author)
        
        # For remote authors, create Follow object immediately so stream can fetch posts
        # Per spec: "A's node can assume that A is following B, even before author B accepts"
        if not foreign_author.user:
            Follow.objects.get_or_create(follower=current_author, followee=foreign_author)
        
        if state == 'pending':
            return Response({'error': 'Follow request already pending'}, status=status.HTTP_400_BAD_REQUEST)
        elif state == 'accepted':
            return Response({'error': 'Already following'}, status=status.HTTP_400_BAD_REQUEST)
        
        success, error = send_follow_to_remote(current_author, foreign_author)
        if not success:
            return Response({
                'error': 'Failed to deliver follow request to remote node',
                'details': error,
            }, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'status': 'follow request sent'}, status=status.HTTP_201_CREATED)

    def delete(self, request, author_id, foreign_id):
        current_author = get_current_author(request)
        author_id = normalize_fqid(author_id)
        if current_author.id != author_id:
            return Response({'error': 'Unauthorized'}, status=403)

        foreign_id = normalize_fqid(foreign_id)
        foreign_author = get_author_by_id(foreign_id)   # or get_or_create_remote_author if needed

        Follow.objects.filter(follower=current_author, followee=foreign_author).delete()
        FollowRequest.objects.filter(actor=current_author, object=foreign_author).delete()

        # Optional: send rejected to remote (good for consistency)
        if not foreign_author.user:
            send_reject_unfollow_to_remote(current_author, foreign_author)

        return Response({'status': 'unfollowed'}, status=200)

class AcceptFollowView(APIView):
    """
    Handle approving or rejecting follow requests.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, author_id, foreign_id):
        """Accept a follow request."""
        current_author = get_current_author(request)
        
        # Normalize author_id to FQID for comparison
        author_id = normalize_fqid(author_id)
        
        if current_author.id != author_id:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        foreign_author = get_author_by_id(foreign_id)

        follow_request = FollowRequest.objects.filter(
            actor=foreign_author,
            object=current_author,
            status=FollowRequest.Status.PENDING
        ).first()

        if not follow_request:
            return Response({'error': 'No pending follow request'}, status=status.HTTP_404_NOT_FOUND)

        follow_request.status = FollowRequest.Status.ACCEPTED
        follow_request.save()

        Follow.objects.get_or_create(follower=foreign_author, followee=current_author)

        return Response({'status': 'follow request accepted'}, status=status.HTTP_200_OK)

    def delete(self, request, author_id, foreign_id):
        """Reject or remove a follower."""
        current_author = get_current_author(request)
        
        # Normalize author_id to FQID for comparison
        author_id = normalize_fqid(author_id)
        
        if current_author.id != author_id:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        foreign_author = get_author_by_id(foreign_id)

        Follow.objects.filter(follower=foreign_author, followee=current_author).delete()
        FollowRequest.objects.filter(
            actor=foreign_author, 
            object=current_author
        ).update(status=FollowRequest.Status.REJECTED)

        return Response({'status': 'follower removed'}, status=status.HTTP_200_OK)


class FollowRequestListView(APIView):
    """
    Get pending follow requests for an author.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, author_id):
        current_author = get_current_author(request)
        
        # Normalize author_id to FQID for comparison
        author_id = normalize_fqid(author_id)
        
        if current_author.id != author_id:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 50))
        
        all_requests = list(FollowRequest.objects.filter(
            object=current_author,
            status=FollowRequest.Status.PENDING
        ))
        total = len(all_requests)
        
        start = (page - 1) * size
        end = start + size
        paginated_requests = all_requests[start:end]
        
        serializer = FollowRequestSerializer(paginated_requests, many=True)
        return Response({
            'type': 'follow_requests',
            'follow_requests': serializer.data,
            'page_number': page,
            'size': size,
            'count': total
        })

# ---------- INBOX ---------- #
class InboxView(APIView):
    """
    Handle incoming messages from remote nodes:
    - Follow requests
    - Unfollow notifications (status=rejected)
    - New/updated/deleted entries (posts)
    - Likes
    - Comments
    """
    authentication_classes = [RemoteNodeAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, author_id):
        author_id = normalize_fqid(author_id)

        try:
            author = Author.objects.get(id=author_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        msg_type = str(data.get('type', '')).lower()
        follow_status = str(data.get('status', 'pending')).lower()

        # ====================== FOLLOW / UNFOLLOW ======================
        if msg_type == 'follow':
            print("FOLLOW REQUEST RECEIVED")

            actor_data = data.get('actor', {})
            object_data = data.get('object', {})
            object_id = object_data.get('id', '')

            # Security check: ensure this message is for the correct author
            if object_id.rstrip('/') != author.id.rstrip('/'):
                return Response(
                    {'error': 'Not the intended recipient'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            actor = get_or_create_author(actor_data)
            if not actor:
                return Response({'error': 'Invalid actor'}, status=status.HTTP_400_BAD_REQUEST)

            # Handle UNFOLLOW (status=rejected)
            if follow_status == 'rejected':
                # Remote author unfollowed us → clean up the reverse Follow
                Follow.objects.filter(follower=actor, followee=author).delete()
                # Optionally clean up FollowRequest too
                FollowRequest.objects.filter(actor=actor, object=author).delete()
                print(f"Received unfollow (rejected) from {actor.displayName}")
                return Response({'status': 'unfollow processed'}, status=status.HTTP_200_OK)

            # Handle normal FOLLOW request (pending)
            if follow_status in ('pending', ''):
                follow_request, created = FollowRequest.objects.get_or_create(
                    actor=actor,
                    object=author,
                    defaults={
                        'summary': data.get('summary', f'{actor.displayName} wants to follow {author.displayName}'),
                        'status': FollowRequest.Status.PENDING
                    }
                )

                if not created and follow_request.status == FollowRequest.Status.PENDING:
                    return Response({'status': 'follow request already exists'}, status=status.HTTP_200_OK)

                # Reset to pending if it was previously rejected/accepted
                if follow_request.status != FollowRequest.Status.PENDING:
                    follow_request.status = FollowRequest.Status.PENDING
                    follow_request.save()

                return Response({'status': 'follow request received'}, status=status.HTTP_201_CREATED)

        # ====================== ENTRY (Post) ======================
        elif msg_type == 'entry':
            entry_id = data.get('id')
            if not entry_id:
                return Response({'error': 'Missing entry id'}, status=status.HTTP_400_BAD_REQUEST)

            remote_author_data = data.get('author', {})
            remote_author = get_or_create_author(remote_author_data)
            if not remote_author:
                return Response({'error': 'Invalid author'}, status=status.HTTP_400_BAD_REQUEST)

            # Handle base64 image if present
            image_file = None
            content_type = data.get('contentType', 'text/plain')
            if content_type and "base64" in content_type:
                try:
                    import base64
                    from django.core.files.base import ContentFile
                    image_file = ContentFile(
                        base64.b64decode(data.get('content', '')),
                        name="remote_image.png"
                    )
                except Exception as e:
                    print(f"Failed to decode base64 image: {e}")

            # Create or update the entry
            entry, created = Entry.objects.update_or_create(
                fqid=entry_id,
                defaults={
                    'remote_author': remote_author,
                    'title': data.get('title', ''),
                    'content': data.get('content', ''),
                    'content_type': content_type,
                    'visibility': data.get('visibility', 'PUBLIC'),
                    'image': image_file
                }
            )

            return Response(
                {'status': 'entry received'},
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )

        # ====================== LIKE ======================
        elif msg_type == 'like':
            from posts.views import get_entry_by_id

            actor = get_or_create_author(data.get('author', {}))
            obj_url = str(data.get('object', '')).strip()

            if actor and obj_url:
                try:
                    entry = get_entry_by_id(obj_url)
                    if entry:
                        Like.objects.get_or_create(author=actor, entry=entry)
                        return Response({'status': 'like received'}, status=status.HTTP_201_CREATED)
                except Exception as e:
                    print(f"Error processing like: {e}")

            return Response({'status': 'Entry not found for like'}, status=status.HTTP_404_NOT_FOUND)

        # ====================== COMMENT ======================
        elif msg_type == 'comment':
            from posts.views import get_entry_by_id
            from interactions.models import Comment

            actor = get_or_create_author(data.get('author', {}))
            content = data.get('comment', 'remote comment')
            contentType = data.get('contentType', 'text/plain')
            entry_url = str(data.get('entry', '')).strip()

            if actor and entry_url:
                try:
                    entry = get_entry_by_id(entry_url)
                    comment = Comment.objects.create(
                        author=actor,
                        entry=entry,
                        content=content,
                        contentType=contentType
                    )
                    return Response({'status': 'comment received', 'id': str(comment.id)}, status=status.HTTP_201_CREATED)
                except Exception as e:
                    print(f"Comment received but entry not found: {e}")
                    # Still acknowledge receipt (important for federation)
                    return Response({'status': 'comment received (entry not found)'}, status=status.HTTP_201_CREATED)

            return Response({'error': 'Invalid comment data'}, status=status.HTTP_400_BAD_REQUEST)

        # Unknown message type
        return Response({'error': f'Unknown message type: {msg_type}'}, status=status.HTTP_400_BAD_REQUEST)
    
# UI views
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
@approved_author_required
def authors_list(request):
    """Show all authors on the node."""
    if request.user.is_authenticated and request.user.is_superuser:
        # Admin sees all authors
        authors = Author.objects.all()
    else:
        # Everyone else sees only approved authors
        authors = Author.objects.filter(is_approved=True)

    current_user_author = None
    if request.user.is_authenticated:
        try:
            current_user_author = request.user.author
        except Author.DoesNotExist:
            pass
    
    return render(request, 'accounts/authors_list.html', {
        'authors': authors,
        'current_user_author': current_user_author,
    })


@login_required
def follow_remote_author(request):
    """Follow a remote author by their FQID."""
    if request.method != 'POST':
        return redirect('authors-list')
    
    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        messages.error(request, 'You must have an approved author profile to follow others.')
        return redirect('authors-list')
    
    remote_fqid = request.POST.get('remote_author_fqid', '').strip()
    
    if not remote_fqid:
        messages.error(request, 'Please enter an author URL.')
        return redirect('authors-list')
    
    # Validate it's a proper FQID format
    if not remote_fqid.startswith('http'):
        messages.error(request, 'Please enter a valid author URL (e.g., https://other-node.com/api/authors/123/).')
        return redirect('authors-list')
    
    # Check if it's a local author
    if is_local_author(remote_fqid):
        messages.error(request, 'To follow local authors, use the Follow button on their profile.')
        return redirect('authors-list')
    
    # Check if the requested author exists
    author_data = verify_remote_author_exists(remote_fqid)
    if not author_data:
        messages.error(request, 'Could not find that author on their node. Please check the URL and try again.')
        return redirect('authors-list')
    
    try:
        # Get or create the remote author
        remote_author, created = get_or_create_remote_author(remote_fqid, author_data)

        # Check if already following
        if current_author.is_following(remote_author):
            messages.info(request, f'You are already following {remote_author.displayName}.')
            return redirect('authors-list')
        
        # Check if there's already a pending request
        existing_request = FollowRequest.objects.filter(
            actor=current_author,
            object=remote_author,
            status=FollowRequest.Status.PENDING
        ).first()
        
        if existing_request:
            messages.info(request, f'You already have a pending follow request to {remote_author.displayName}.')
            return redirect('authors-list')
        
        # Create the follow request
        follow_request, state = create_follow_request(current_author, remote_author)
        
        # For remote authors, create Follow object immediately so stream can fetch posts
        # Per spec: "A's node can assume that A is following B, even before author B accepts"
        if not remote_author.user:
            Follow.objects.get_or_create(follower=current_author, followee=remote_author)
        
        if state == 'pending':
            messages.info(request, f'You already have a pending follow request to {remote_author.displayName}.')
        elif state == 'accepted':
            messages.info(request, f'You are already following {remote_author.displayName}.')
        else:
            success, error = send_follow_to_remote(current_author, remote_author)
            if success:
                messages.success(request, f'Follow request sent to {remote_author.displayName}!')
            else:
                messages.error(
                    request,
                    f'Could not deliver follow request to {remote_author.displayName}. {error}'
                )
                
        return redirect('authors-list')
        
    except Exception as e:
        messages.error(request, f'Could not follow author: {str(e)}')
        return redirect('authors-list')


@approved_author_required
def author_followers(request, author_id):
    """Show list of an author's followers."""
    if not author_id.endswith('/'):
        author_id += '/'
    author = get_object_or_404(Author, id=author_id)
    followers = [f.follower for f in author.followers.all()]
    
    current_user_author = None
    if request.user.is_authenticated:
        try:
            current_user_author = request.user.author
        except Author.DoesNotExist:
            pass
    
    return render(request, 'accounts/authors_list.html', {
        'authors': followers,
        'current_user_author': current_user_author,
        'page_title': f"{author.displayName.capitalize()}'s Followers",
    })

@approved_author_required
def author_following(request, author_id):
    """Show list of authors that this author is following."""
    if not author_id.endswith('/'):
        author_id += '/'
    author = get_object_or_404(Author, id=author_id)
    following = [f.followee for f in author.following.all()]
    
    current_user_author = None
    if request.user.is_authenticated:
        try:
            current_user_author = request.user.author
        except Author.DoesNotExist:
            pass
    
    return render(request, 'accounts/authors_list.html', {
        'authors': following,
        'current_user_author': current_user_author,
        'page_title': f"{author.displayName.capitalize()} is Following",
    })

@approved_author_required
def author_friends(request, author_id):
    """Show list of an author's friends (mutual follows)."""
    if not author_id.endswith('/'):
        author_id += '/'
    author = get_object_or_404(Author, id=author_id)
    friends = list(author.get_friends())
    
    current_user_author = None
    if request.user.is_authenticated:
        try:
            current_user_author = request.user.author
        except Author.DoesNotExist:
            pass
    
    return render(request, 'accounts/authors_list.html', {
        'authors': friends,
        'current_user_author': current_user_author,
        'page_title': f"{author.displayName.capitalize()}'s Friends",
    })
@approved_author_required
def author_profile(request, author_id):
    """Show an author's profile along with their posts."""
    if not author_id.endswith('/'):
        author_id += '/'
    author = get_object_or_404(Author, id=author_id)

    # Refresh remote author data on profile visit
    if not author.user:
        fresh_data = verify_remote_author_exists(author.id)
        if fresh_data:
            author, _ = get_or_create_remote_author(author.id, fresh_data)

    current_user_author = None
    is_following = False
    is_friend = False
    has_pending_request = False

    if request.user.is_authenticated:
        try:
            current_user_author = request.user.author
            is_following = current_user_author.is_following(author)
            is_friend = current_user_author.is_friend(author)
            has_pending_request = FollowRequest.objects.filter(
                actor=current_user_author,
                object=author,
                status=FollowRequest.Status.PENDING
            ).exists()
        except Author.DoesNotExist:
            pass

    posts = []

    if author.user:
        # Local author
        qs = Entry.objects.exclude(visibility="DELETED")
        qs = qs.filter(author=author.user)

        if current_user_author and current_user_author.id == author.id:
            posts = qs  # own profile, see everything
        elif is_friend:
            posts = qs.filter(visibility__in=["PUBLIC", "UNLISTED", "FRIENDS"])
        elif is_following:
            posts = qs.filter(visibility__in=["PUBLIC", "UNLISTED"])
        else:
            posts = qs.filter(visibility="PUBLIC")

        posts = posts.order_by('-published_at')

    else:
        # Remote author — fetch from their node
        from posts.views import fetch_remote_author_posts
        try:
            remote_posts = fetch_remote_author_posts(author)
            stored_ids = list(remote_posts.values_list('id', flat=True))

            qs = Entry.objects.filter(id__in=stored_ids).exclude(visibility="DELETED")

            if is_friend:
                posts = qs.filter(visibility__in=["PUBLIC", "UNLISTED", "FRIENDS"])
            elif is_following:
                posts = qs.filter(visibility__in=["PUBLIC", "UNLISTED"])
            else:
                posts = qs.filter(visibility="PUBLIC")

            posts = posts.order_by('-published_at')

        except Exception as e:
            print(f"Error fetching remote posts: {e}")
            posts = Entry.objects.filter(
                remote_author=author,
                visibility="PUBLIC"
            ).order_by('-published_at')

    return render(request, 'accounts/profile.html', {
        'profile_author': author,
        'current_user_author': current_user_author,
        'is_following': is_following,
        'has_pending_request': has_pending_request,
        'posts': posts,
    })

@approved_author_required
@login_required
def follow_author(request, author_id):
    author_id = unquote(author_id)
    
    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        return redirect('authors-list')
    
    # Check if they are local or remote, and create if remote
    if is_local_author(author_id):
        try:
            target_author = get_author_by_id(author_id)
        except Author.DoesNotExist:
            return redirect('authors-list')
    else:
        author_data = verify_remote_author_exists(author_id)
        target_author, _ = get_or_create_remote_author(author_id,author_data)
    
    if current_author == target_author:
        return redirect('author-profile', author_id=author_id)
    
    if current_author.is_following(target_author):
        return redirect('author-profile', author_id=author_id)
    
    request_result, state = create_follow_request(current_author, target_author)
    
    if state in ('pending', 'accepted'):
        return redirect('author-profile', author_id=author_id)
    
    success, error = send_follow_to_remote(current_author, target_author)
    if not success:
        messages.error(request, f'Could not deliver follow request. {error}')
    return redirect('author-profile', author_id=author_id)

@approved_author_required
@login_required
def unfollow_author(request, author_id):
    """Unfollow an author from the UI."""
    author_id = unquote(author_id)
    if not author_id.endswith('/'):
        author_id += '/'
    
    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        return redirect('authors-list')
    
    try:
        target_author = Author.objects.get(id=author_id)
    except Author.DoesNotExist:
        return redirect('authors-list')
    
    Follow.objects.filter(follower=current_author, followee=target_author).delete()
    FollowRequest.objects.filter(actor=current_author, object=target_author).delete()
    
    return redirect('author-profile', author_id=author_id)

@login_required
def cancel_follow_request(request, author_id):
    """Cancel a pending follow request (withdraw request)."""
    author_id = unquote(author_id)
    
    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        return redirect('authors-list')
    
    try:
        target_author = Author.objects.get(id=author_id)
    except Author.DoesNotExist:
        try:
            target_author = Author.objects.get(id__endswith=f'{author_id}/')
        except Author.DoesNotExist:
            return redirect('authors-list')
    
    FollowRequest.objects.filter(
        actor=current_author,
        object=target_author,
        status=FollowRequest.Status.PENDING
    ).delete()
    
    return redirect('author-profile', author_id=author_id)

@approved_author_required
@login_required
def follow_requests(request):
    """Show pending follow requests."""
    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        return redirect('authors-list')
    
    pending_requests = FollowRequest.objects.filter(
        object=current_author,
        status=FollowRequest.Status.PENDING
    )
    
    return render(request, 'accounts/follow_requests.html', {
        'pending_requests': pending_requests,
    })

@approved_author_required
@login_required
def accept_follow_request(request, request_id):
    """Accept a follow request."""
    follow_request = get_object_or_404(FollowRequest, id=request_id)
    
    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        return redirect('follow-requests')
    
    if follow_request.object != current_author:
        return HttpResponseForbidden()
    
    follow_request.status = FollowRequest.Status.ACCEPTED
    follow_request.save()
    
    Follow.objects.get_or_create(
        follower=follow_request.actor,
        followee=current_author
    )
    
    return redirect('follow-requests')



@approved_author_required
@login_required
def reject_follow_request(request, request_id):
    """Reject a follow request."""
    follow_request = get_object_or_404(FollowRequest, id=request_id)
    
    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        return redirect('follow-requests')
    
    if follow_request.object != current_author:
        return HttpResponseForbidden()
    
    follow_request.status = FollowRequest.Status.REJECTED
    follow_request.save()
    
    return redirect('follow-requests')

@approved_author_required
@login_required
def my_profile(request):
    """Go to current user's profile."""
    try:
        current_author = request.user.author
        return redirect('author-profile', author_id=current_author.id)
    except Author.DoesNotExist:
        return redirect('authors-list')

from .forms import AuthorUpdateForm


@approved_author_required
@login_required
def edit_profile(request, author_id=None):
    # Admin editing someone OR direct URL
    if author_id:
        author_id = normalize_fqid(author_id)
        author = get_object_or_404(Author, id=author_id)
    else:
        # Normal user editing themselves
        try:
            author = request.user.author
        except Author.DoesNotExist:
            return redirect('authors-list')

    # Permission check
    if not request.user.is_superuser:
        if author != getattr(request.user, "author", None):
            return redirect('author-profile', author_id=author.id)

    # Prevent editing remote authors
    if not author.is_local:
        return redirect('author-profile', author_id=author.id)


    current_user_author = getattr(request.user, "author", None)
    if request.method == "POST":
        form = AuthorUpdateForm(
            request.POST,
            request.FILES,
            instance=author,
            user=request.user   # needed for is_approved
        )
        if form.is_valid():
            form.save()
            return redirect('author-profile', author_id=author.id)
    else:
        form = AuthorUpdateForm(instance=author, user=request.user)

    return render(request, "accounts/edit_profile.html", {
        "form": form,
        "author": author,
        "current_user_author": current_user_author,
    })
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required

def logout_view(request):
    if request.method != "POST":
        return redirect("login")

    logout(request)
    return redirect("login")

def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"]
            )

            author = user.author
            author.displayName = form.cleaned_data["display_name"]
            author.is_approved = False
            author.save()

            login(request, user)
            return redirect("pending-approval")
    else:
        form = SignUpForm()

    return render(request, "accounts/signup.html", {"form": form})

@login_required
def pending_approval(request):
    try:
        author = request.user.author
    except Author.DoesNotExist:
        return redirect("login")

    if author.is_approved:
        return redirect("home")

    return render(request, "accounts/pending_approval.html")

@approved_author_required
@login_required
def pending_authors(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Admins only.")

    pending_authors = Author.objects.filter(
        user__isnull=False,
        is_approved=False
    ).select_related("user")

    return render(request, "accounts/pending_authors_admin.html", {
        "pending_authors_admin": pending_authors
    })

@approved_author_required
@staff_member_required
def pending_authors_admin(request):
    pending_authors = Author.objects.filter(
        is_approved=False,
        user__isnull=False
    )

    return render(request, "accounts/pending_authors_admin.html", {
        "pending_authors": pending_authors
    })

@approved_author_required
@login_required
def approve_author(request, author_id):
    if not request.user.is_staff:
        return HttpResponseForbidden("Admins only.")

    if not author_id.endswith('/'):
        author_id += '/'
    author = get_object_or_404(Author, id=author_id, user__isnull=False)
    author.is_approved = True
    author.save()

    return redirect("pending-authors-admin")

@approved_author_required
@login_required
def reject_author(request, author_id):
    if not request.user.is_staff:
        return HttpResponseForbidden("Admins only.")

    if not author_id.endswith('/'):
        author_id += '/'
    author = get_object_or_404(Author, id=author_id, user__isnull=False)

    if author.user:
        author.user.delete()
    else:
        author.delete()

    return redirect("pending-authors-admin")

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            if user.is_staff:
                return redirect("home")

            try:
                author = user.author
            except Author.DoesNotExist:
                return redirect("login")

            if not author.is_approved:
                return redirect("pending-approval")

            return redirect("home")
    else:
        form = AuthenticationForm()

    return render(request, "accounts/login.html", {"form": form})


#TESTING

def send_reject_unfollow_to_remote(actor, target):
    """Send unfollow notification as status=rejected (simple & matches your request)."""
    if target.is_local or not target.id:
        return True

    try:
        inbox_url = get_remote_inbox_url(target.id)

        data = {
            'type': 'Follow',
            'summary': f'{actor.displayName} unfollowed {target.displayName}',
            'actor': AuthorSerializer(actor).data,
            'object': AuthorSerializer(target).data,
            'status': 'rejected'   # <--- what you asked for
        }

        node = find_remote_node_for_url(target.id) or find_remote_node_for_url(target.host)
        if not node:
            print(f"Warning: No remote node credentials for {target.host}")
            return False

        response = requests.post(
            inbox_url,
            json=data,
            timeout=15,
            auth=(node.username, node.password)
        )
        response.raise_for_status()
        print(f"Sent unfollow (status=rejected) to {inbox_url}")
        return True

    except requests.exceptions.ChunkedEncodingError:
        print("ChunkedEncodingError - treated as success")
        return True
    except Exception as e:
        print(f"Failed to send unfollow notification: {e}")
        return False
@approved_author_required
@login_required
def unfollow_author(request, author_id):
    """Unfollow an author (local or remote) - cleans local data + notifies remote."""
    author_id = unquote(author_id).strip()
    if not author_id.endswith('/'):
        author_id += '/'

    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        messages.error(request, "You must be logged in as an approved author.")
        return redirect('authors-list')

    try:
        target_author = Author.objects.get(id=author_id)
    except Author.DoesNotExist:
        messages.error(request, "Author not found.")
        return redirect('author-profile', author_id=author_id)

    if current_author.id == target_author.id:
        messages.error(request, "You cannot unfollow yourself.")
        return redirect('author-profile', author_id=author_id)

    # Clean up local relationship (this is the most important part)
    Follow.objects.filter(follower=current_author, followee=target_author).delete()
    FollowRequest.objects.filter(actor=current_author, object=target_author).delete()

    # Notify remote node (simple "rejected" status as you wanted)
    if not target_author.user:  # remote author
        success = send_reject_unfollow_to_remote(current_author, target_author)
        if success:
            messages.success(request, f"Successfully unfollowed {target_author.displayName}.")
        else:
            messages.warning(request, f"Unfollowed locally. Could not notify remote node (they may still send posts).")
    else:
        messages.success(request, f"Successfully unfollowed {target_author.displayName}.")

    return redirect('author-profile', author_id=author_id)