import requests
from urllib.parse import unquote
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Author, FollowRequest, Follow
from posts.models import Entry
from .serializers import (
    AuthorSerializer, AuthorListSerializer, 
    FollowRequestSerializer
)


def get_host_url():
    """Get this node's base URL for constructing FQIDs."""
    allowed_host = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
    if 'localhost' in allowed_host:
        return f'http://{allowed_host}'
    return f'https://{allowed_host}'


def get_or_create_author(author_data):
    """Create or retrieve an author from remote data (e.g., from another node)."""
    author_id = author_data.get('id')
    if not author_id:
        return None
    
    existing = Author.objects.filter(id=author_id).first()
    if existing:
        return existing
    
    return Author.objects.create(
        id=author_id,
        user=None,
        host=author_data.get('host', ''),
        displayName=author_data.get('displayName', 'Unknown'),
        github=author_data.get('github'),
        profileImage=author_data.get('profileImage'),
        web=author_data.get('web'),
        is_approved=True,
    )


# Helpers for autho lookup
# These handle the difference between local authors (user_id) and remote authors (FQID)

def get_current_author(request):
    """Get Author for the logged-in user."""
    return Author.objects.get(user=request.user)


def get_author_by_id(author_id):
    """
    Look up author by user_id (local) or FQID (remote).
    
    Local authors: user_id is an integer (e.g., "1")
    Remote authors: FQID URL (e.g., "http://remote.com/api/authors/abc/")
    Detection: if it starts with 'http', it's a remote FQID.
    """
    is_remote = str(author_id).startswith('http')
    if is_remote:
        return Author.objects.get(id=str(author_id))
    return Author.objects.get(user_id=author_id)


def get_or_create_remote_author(foreign_id):
    """
    Create remote author on first follow.
    Extracts host from the FQID (everything before /api/authors/).
    """
    return Author.objects.get_or_create(
        id=str(foreign_id),
        defaults={
            'host': str(foreign_id).split('/api/authors/')[0] + '/api/',
            'displayName': 'Remote Author',
            'is_approved': True,
        }
    )


def send_follow_to_remote(actor, target):
    """
    Send a follow request to a remote author's inbox.
    Used when following a remote author - their node needs to know about the request.
    """
    is_remote = not target.id.startswith(get_host_url())
    if not is_remote:
        return
    
    try:
        remote_id = target.id.split('/')[-1]
        inbox_url = f"{target.host.rstrip('/')}/api/authors/{remote_id}/inbox/"
        follow_data = {
            'type': 'follow',
            'summary': f'{actor.displayName} wants to follow {target.displayName}',
            'actor': AuthorSerializer(actor).data,
            'object': AuthorSerializer(target).data
        }
        requests.post(inbox_url, json=follow_data, timeout=10)
    except Exception:
        pass


def create_follow_request(actor, target):
    """
    Create a follow request from actor to target.
    Returns the created/updated request.
    """
    existing = FollowRequest.objects.filter(actor=actor, object=target).first()
    
    if existing:
        if existing.status == FollowRequest.Status.PENDING:
            return None, 'pending'
        elif existing.status == FollowRequest.Status.ACCEPTED:
            return None, 'accepted'
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


# API Views

class AuthorListView(APIView):
    """List all authors on this node."""
    permission_classes = [AllowAny]

    def get(self, request):
        authors = Author.objects.filter(is_approved=True)
        serializer = AuthorListSerializer(authors, many=True)
        return Response({
            'type': 'authors',
            'authors': serializer.data
        })


class AuthorDetailView(APIView):
    """Get details for a specific author."""
    permission_classes = [AllowAny]

    def get(self, request, author_id):
        try:
            author = Author.objects.get(user_id=author_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = AuthorSerializer(author)
        return Response(serializer.data)


class FollowingListView(APIView):
    """Get list of authors this author is following."""
    permission_classes = [AllowAny]

    def get(self, request, author_id):
        try:
            author = Author.objects.get(user_id=author_id)
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
    permission_classes = [AllowAny]

    def get(self, request, author_id):
        try:
            author = Author.objects.get(user_id=author_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)
        
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 50))
        
        all_followers = list(author.followers.all())
        total = len(all_followers)
        
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


class FollowView(APIView):
    """
    Handle following and unfollowing authors.
    
    User story: As an author, I want to follow local authors, so that I can see their entries.
    User story: As an author, I want to follow remote authors, so that I can see their entries. (Part 3-5)
    User story: As an author, I want to unfollow authors I am following, so that I don't have to see their entries anymore.
    
    Note: Follow requests go to inbox first, Follow only created after approval.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, author_id, foreign_id):
        """Send a follow request to another author."""
        current_author = get_current_author(request)
        
        if str(current_author.user_id) != str(author_id):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        is_remote = str(foreign_id).startswith('http')
        
        if is_remote:
            foreign_author, _ = get_or_create_remote_author(foreign_id)
        else:
            foreign_author = get_author_by_id(foreign_id)

        if current_author.id == foreign_author.id:
            return Response({'error': 'Cannot follow yourself'}, status=status.HTTP_400_BAD_REQUEST)

        if current_author.is_following(foreign_author):
            return Response({'error': 'Already following'}, status=status.HTTP_400_BAD_REQUEST)

        request_result, state = create_follow_request(current_author, foreign_author)
        
        if state == 'pending':
            return Response({'error': 'Follow request already pending'}, status=status.HTTP_400_BAD_REQUEST)
        elif state == 'accepted':
            return Response({'error': 'Already following'}, status=status.HTTP_400_BAD_REQUEST)
        
        send_follow_to_remote(current_author, foreign_author)
        return Response({'status': 'follow request sent'}, status=status.HTTP_201_CREATED)

    def delete(self, request, author_id, foreign_id):
        """Unfollow an author."""
        current_author = get_current_author(request)
        
        if str(current_author.user_id) != str(author_id):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        foreign_author = get_author_by_id(foreign_id)

        Follow.objects.filter(follower=current_author, followee=foreign_author).delete()
        FollowRequest.objects.filter(actor=current_author, object=foreign_author).delete()

        return Response({'status': 'unfollowed'}, status=status.HTTP_200_OK)


class AcceptFollowView(APIView):
    """
    Handle approving or rejecting follow requests.
    
    User story: As an author, I want to be able to approve or deny other authors following me, 
    so that I don't get followed by people I don't like.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, author_id, foreign_id):
        """Accept a follow request."""
        current_author = get_current_author(request)
        
        if str(current_author.user_id) != str(author_id):
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
        
        if str(current_author.user_id) != str(author_id):
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
    
    User story: As an author, I want to know if I have "follow requests," so I can approve them.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, author_id):
        current_author = get_current_author(request)
        
        if str(current_author.user_id) != str(author_id):
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


class InboxView(APIView):
    """
    Receive follow requests from remote nodes.
    
    When a remote author wants to follow you, their node contacts this endpoint
    to create a follow request in your inbox.
    """
    permission_classes = [AllowAny]

    def post(self, request, author_id):
        try:
            author = Author.objects.get(user_id=author_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        
        if data.get('type') == 'follow':
            actor_data = data.get('actor', {})
            object_data = data.get('object', {})
            
            object_id = object_data.get('id', '')
            if str(author_id) not in object_id and author.id not in object_id:
                return Response({'error': 'Not the intended recipient'}, status=status.HTTP_400_BAD_REQUEST)

            actor = get_or_create_author(actor_data)
            if not actor:
                return Response({'error': 'Invalid actor'}, status=status.HTTP_400_BAD_REQUEST)

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
            
            if follow_request.status != FollowRequest.Status.PENDING:
                follow_request.status = FollowRequest.Status.PENDING
                follow_request.save()

            return Response({'status': 'follow request received'}, status=status.HTTP_201_CREATED)

        return Response({'error': 'Unknown inbox item type'}, status=status.HTTP_400_BAD_REQUEST)


# UI views
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def authors_list(request):
    """Show all authors on the node."""
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

def author_profile(request, author_id):
    """Show an author's profile along with their posts."""
    author = get_object_or_404(Author, id=author_id)

    current_user_author = None
    is_following = False
    has_pending_request = False

    if request.user.is_authenticated:
        try:
            current_user_author = request.user.author
            is_following = current_user_author.is_following(author)
            has_pending_request = FollowRequest.objects.filter(
                actor=current_user_author,
                object=author,
                status=FollowRequest.Status.PENDING
            ).exists()
        except Author.DoesNotExist:
            pass

    # For local authors, get their posts
    posts = []
    if author.user:  # only if this author has a local User
        if current_user_author == author:
            # Viewing your own profile → show all except deleted
            posts = Entry.objects.filter(
                author=author.user
            ).exclude(visibility="DELETED")
        elif current_user_author and current_user_author.is_friend(author):
            # Mutual followers (friends) can see public, unlisted, and friends posts
            posts = Entry.objects.filter(
                author=author.user,
                visibility__in=["PUBLIC", "UNLISTED", "FRIENDS"]
            )
        elif is_following:
            # One-way followers can see public and unlisted posts
            posts = Entry.objects.filter(
                author=author.user,
                visibility__in=["PUBLIC", "UNLISTED"]
            )
        else:
            # Viewing someone else's profile → only public
            posts = Entry.objects.filter(
                author=author.user,
                visibility="PUBLIC"
            )
    return render(request, 'accounts/profile.html', {
        'profile_author': author,
        'current_user_author': current_user_author,
        'is_following': is_following,
        'has_pending_request': has_pending_request,
        'posts': posts,
    })

@login_required
def follow_author(request, author_id):
    """Follow an author from the UI."""
    author_id = unquote(author_id)
    
    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        return redirect('authors-list')
    
    try:
        target_author = Author.objects.get(id=author_id)
    except Author.DoesNotExist:
        return redirect('authors-list')
    
    if current_author == target_author:
        return redirect('author-profile', author_id=author_id)
    
    if current_author.is_following(target_author):
        return redirect('author-profile', author_id=author_id)
    
    request_result, state = create_follow_request(current_author, target_author)
    
    if state in ('pending', 'accepted'):
        return redirect('author-profile', author_id=author_id)
    
    send_follow_to_remote(current_author, target_author)
    return redirect('author-profile', author_id=author_id)


@login_required
def unfollow_author(request, author_id):
    """Unfollow an author from the UI."""
    author_id = unquote(author_id)
    
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
        return redirect('authors-list')
    
    # Only delete the FollowRequest, not the Follow (if exists)
    FollowRequest.objects.filter(
        actor=current_author,
        object=target_author,
        status=FollowRequest.Status.PENDING
    ).delete()
    
    return redirect('author-profile', author_id=author_id)


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


@login_required
def my_profile(request):
    """Go to current user's profile."""
    try:
        current_author = request.user.author
        return redirect('author-profile', author_id=current_author.id)
    except Author.DoesNotExist:
        return redirect('authors-list')

from .forms import AuthorUpdateForm

@login_required
def edit_profile(request):
    try:
        author = request.user.author
    except Author.DoesNotExist:
        return redirect('authors-list')  # fallback if user has no author

    # Optional: prevent editing remote authors
    if not author.is_local:
        return redirect('author-profile', author_id=author.id)

    if request.method == "POST":
        # Pass request.FILES to handle uploaded images
        form = AuthorUpdateForm(request.POST, request.FILES, instance=author)
        if form.is_valid():
            form.save()
            return redirect('author-profile', author_id=author.id)
    else:
        form = AuthorUpdateForm(instance=author)

    return render(request, "accounts/edit_profile.html", {"form": form})

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required

def logout_view(request):
    """
    Logs out the user only if the request is POST.
    Redirects to login page after logout.
    """
    if request.method == "POST":
        if request.user.is_authenticated:
            logout(request)
        return redirect('login')  # or 'authors-list'
    else:
        # Block GET or other methods
        return HttpResponseForbidden("Logout must be via POST.")
