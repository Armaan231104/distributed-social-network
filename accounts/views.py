import requests
from urllib.parse import unquote
from django.conf import settings
from django.db import IntegrityError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import SessionAuthentication, BasicAuthentication

from .models import Author, FollowRequest, Follow
from .serializers import (
    AuthorSerializer, AuthorListSerializer, 
    FollowRequestSerializer, FollowSerializer,
    FollowersSerializer, FollowingSerializer,
    InboxFollowSerializer
)


def get_host_url():
    """Returns the base URL for this node for constructing FQIDs."""
    allowed_host = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
    if 'localhost' in allowed_host:
        return f'http://{allowed_host}'
    return f'https://{allowed_host}'


def get_or_create_author(author_data):
    """
    Gets an existing author by ID or creates a new one from data.
    Used when receiving remote authors via follow requests or federation.
    Remote authors don't have local User accounts, so we allow user_id to be null.
    """
    author_id = author_data.get('id')
    if not author_id:
        return None
    
    # Check if author already exists
    existing = Author.objects.filter(id=author_id).first()
    if existing:
        return existing
    
    # Create new remote author (without local User)
    return Author.objects.create(
        id=author_id,
        user=None,  # Remote authors don't have local accounts
        host=author_data.get('host', ''),
        displayName=author_data.get('displayName', 'Unknown'),
        github=author_data.get('github'),
        profileImage=author_data.get('profileImage'),
        web=author_data.get('web'),
        is_approved=True,
    )


class AuthorListView(APIView):
    """
    GET /api/authors/ - List all authors on the node.
    
    Per spec: "As an author, I want to browse the public entries of everyone"
    This enables discovering local authors to follow.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        authors = Author.objects.filter(is_approved=True)
        serializer = AuthorListSerializer(authors, many=True)
        return Response({
            'type': 'authors',
            'items': serializer.data
        })


class AuthorDetailView(APIView):
    """
    GET /api/authors/{id}/ - Get a single author's details.
    
    Returns full author object with profile information.
    """
    permission_classes = [AllowAny]

    def get(self, request, author_id):
        try:
            author = Author.objects.get(user_id=author_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = AuthorSerializer(author)
        return Response(serializer.data)


class FollowingListView(APIView):
    """
    GET /api/authors/{id}/following/ - List authors that this author follows.
    
    Per spec: "my node will know about my followers, who I am following, and my friends"
    """
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
            'items': serializer.data,
            'page_number': page,
            'size': size,
            'count': total
        })


class FollowersListView(APIView):
    """
    GET /api/authors/{id}/followers/ - List authors that follow this author.
    
    Per spec: "my node will know about my followers, who I am following, and my friends"
    """
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
            'items': serializer.data,
            'page_number': page,
            'size': size,
            'count': total
        })


class FollowView(APIView):
    """
    PUT /api/authors/{id}/following/{foreign_id}/ - Create a follow request.
    DELETE /api/authors/{id}/following/{foreign_id}/ - Unfollow an author.
    
    Per spec:
    - "As an author, I want to follow local authors"
    - "As an author, I want to follow remote authors" (Part 3-5)
    - "As an author, I want to unfollow authors I am following"
    
    Note: Per spec, follow requests go to inbox first and require approval.
    The Follow relationship is only created after the request is accepted.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, author_id, foreign_id):
        try:
            author = Author.objects.get(user=request.user)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        if str(author.user_id) != str(author_id):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        # Check if foreign_id is remote (contains http) or local (integer)
        is_remote = str(foreign_id).startswith('http')
        
        if is_remote:
            foreign_author, _ = Author.objects.get_or_create(
                id=str(foreign_id),
                defaults={
                    'host': str(foreign_id).split('/api/authors/')[0] + '/api/',
                    'displayName': 'Remote Author',
                    'is_approved': True,
                }
            )
        else:
            try:
                foreign_author = Author.objects.get(user_id=foreign_id)
            except Author.DoesNotExist:
                return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if already following (has accepted follow request)
        if author.is_following(foreign_author):
            return Response({'error': 'Already following'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if there's already a pending request
        existing_request = FollowRequest.objects.filter(
            actor=author,
            object=foreign_author,
            status=FollowRequest.Status.PENDING
        ).first()

        if existing_request:
            return Response({'error': 'Follow request already pending'}, status=status.HTTP_400_BAD_REQUEST)

        # Create follow request (per spec - requests go to inbox first)
        FollowRequest.objects.create(
            actor=author,
            object=foreign_author,
            summary=f'{author.displayName} wants to follow {foreign_author.displayName}',
            status=FollowRequest.Status.PENDING
        )

        # For remote authors, notify their inbox
        if is_remote:
            inbox_url = f"{foreign_author.host.rstrip('/')}/api/authors/{foreign_id}/inbox/"
            try:
                follow_data = {
                    'type': 'follow',
                    'summary': f'{author.displayName} wants to follow {foreign_author.displayName}',
                    'actor': AuthorSerializer(author).data,
                    'object': AuthorSerializer(foreign_author).data
                }
                requests.post(inbox_url, json=follow_data, timeout=10)
            except Exception:
                pass

        return Response({'status': 'follow request sent'}, status=status.HTTP_201_CREATED)

    def delete(self, request, author_id, foreign_id):
        try:
            author = Author.objects.get(user=request.user)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        if str(author.user_id) != str(author_id):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        is_remote = str(foreign_id).startswith('http')
        
        try:
            if is_remote:
                foreign_author = Author.objects.get(id=str(foreign_id))
            else:
                foreign_author = Author.objects.get(user_id=foreign_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        # Remove follow relationship if exists
        Follow.objects.filter(follower=author, followee=foreign_author).delete()
        # Also remove any pending follow request
        FollowRequest.objects.filter(actor=author, object=foreign_author).delete()

        return Response({'status': 'unfollowed'}, status=status.HTTP_200_OK)


class AcceptFollowView(APIView):
    """
    PUT /api/authors/{id}/followers/{foreign_id}/ - Accept a follow request.
    DELETE /api/authors/{id}/followers/{foreign_id}/ - Reject/remove a follower.
    
    Per spec:
    - "As an author, I want to be able to approve or deny other authors following me"
    - Follow requests must be approved before the follower is added.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, author_id, foreign_id):
        try:
            author = Author.objects.get(user=request.user)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check authorization - compare string versions
        if str(author.user_id) != str(author_id):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        is_remote = str(foreign_id).startswith('http')
        
        try:
            if is_remote:
                foreign_author = Author.objects.get(id=str(foreign_id))
            else:
                foreign_author = Author.objects.get(user_id=foreign_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        # Find pending follow request from this author
        follow_request = FollowRequest.objects.filter(
            actor=foreign_author,
            object=author,
            status=FollowRequest.Status.PENDING
        ).first()

        if not follow_request:
            return Response({'error': 'No pending follow request'}, status=status.HTTP_404_NOT_FOUND)

        # Accept the follow request - create the Follow relationship
        follow_request.status = FollowRequest.Status.ACCEPTED
        follow_request.save()

        Follow.objects.get_or_create(follower=foreign_author, followee=author)

        return Response({'status': 'follow request accepted'}, status=status.HTTP_200_OK)

    def delete(self, request, author_id, foreign_id):
        try:
            author = Author.objects.get(user=request.user)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        if str(author.user_id) != str(author_id):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        is_remote = str(foreign_id).startswith('http')
        
        try:
            if is_remote:
                foreign_author = Author.objects.get(id=str(foreign_id))
            else:
                foreign_author = Author.objects.get(user_id=foreign_id)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        # Remove follower relationship
        Follow.objects.filter(follower=foreign_author, followee=author).delete()
        # Reject any pending follow request
        FollowRequest.objects.filter(
            actor=foreign_author, 
            object=author
        ).update(status=FollowRequest.Status.REJECTED)

        return Response({'status': 'follower removed'}, status=status.HTTP_200_OK)


class FollowRequestListView(APIView):
    """
    GET /api/authors/{id}/follow_requests/ - Get pending follow requests.
    
    Per spec: "As an author, I want to know if I have 'follow requests,' 
    so I can approve them."
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, author_id):
        try:
            author = Author.objects.get(user=request.user)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        if str(author.user_id) != str(author_id):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 50))
        
        all_requests = list(FollowRequest.objects.filter(
            object=author,
            status=FollowRequest.Status.PENDING
        ))
        total = len(all_requests)
        
        start = (page - 1) * size
        end = start + size
        paginated_requests = all_requests[start:end]
        
        serializer = FollowRequestSerializer(paginated_requests, many=True)
        return Response({
            'type': 'follow_requests',
            'items': serializer.data,
            'page_number': page,
            'size': size,
            'count': total
        })


class InboxView(APIView):
    """
    POST /api/authors/{id}/inbox/ - Receive remote follow requests.
    
    Per spec, remote nodes send follow requests to this endpoint.
    This is how remote authors initiate following - their node contacts
    our inbox to create the follow request.
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
            
            # Check if this is for this author
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


# UI Views below
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseForbidden


def get_host_url():
    from django.conf import settings
    allowed_host = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'
    if 'localhost' in allowed_host:
        return f'http://{allowed_host}'
    return f'https://{allowed_host}'


def authors_list(request):
    """
    Display a list of all authors on the local node.
    Per spec: "As an author, I want to browse the public entries of everyone"
    """
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
    """
    Display an author's profile page with their public entries.
    Per spec: "As an author, I want a public page with my profile information"
    """
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
    
    return render(request, 'accounts/profile.html', {
        'profile_author': author,
        'current_user_author': current_user_author,
        'is_following': is_following,
        'has_pending_request': has_pending_request,
    })


@login_required
def follow_author(request, author_id):
    """
    Follow an author (local or remote).
    Per spec: "As an author, I want to follow local authors"
    """
    author_id = unquote(author_id)
    
    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        return redirect('authors-list')
    
    try:
        target_author = Author.objects.get(id=author_id)
    except Author.DoesNotExist:
        return redirect('authors-list')
    
    if current_author.is_following(target_author):
        return redirect('author-profile', author_id=author_id)
    
    FollowRequest.objects.get_or_create(
        actor=current_author,
        object=target_author,
        defaults={
            'summary': f'{current_author.displayName} wants to follow {target_author.displayName}',
            'status': FollowRequest.Status.PENDING
        }
    )
    
    Follow.objects.get_or_create(follower=current_author, followee=target_author)
    
    is_remote = not target_author.id.startswith(get_host_url())
    if is_remote:
        try:
            remote_id = target_author.id.split('/')[-1]
            inbox_url = f"{target_author.host.rstrip('/')}/api/authors/{remote_id}/inbox/"
            follow_data = {
                'type': 'follow',
                'summary': f'{current_author.displayName} wants to follow {target_author.displayName}',
                'actor': {
                    'type': 'author',
                    'id': current_author.id,
                    'host': current_author.host,
                    'displayName': current_author.displayName,
                    'github': current_author.github,
                    'profileImage': current_author.profileImage,
                    'web': current_author.web,
                },
                'object': {
                    'type': 'author',
                    'id': target_author.id,
                    'host': target_author.host,
                    'displayName': target_author.displayName,
                }
            }
            requests.post(inbox_url, json=follow_data, timeout=10)
        except Exception:
            pass
    
    return redirect('author-profile', author_id=author_id)


@login_required
def unfollow_author(request, author_id):
    """
    Unfollow an author.
    Per spec: "As an author, I want to unfollow authors I am following"
    """
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
def follow_requests(request):
    """
    Display pending follow requests for the current user.
    Per spec: "As an author, I want to know if I have 'follow requests,' 
    so I can approve them."
    """
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
    """
    Accept a follow request.
    Per spec: "As an author, I want to be able to approve or deny other 
    authors following me"
    """
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
    """
    Reject a follow request.
    Per spec: "As an author, I want to be able to approve or deny other 
    authors following me"
    """
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
    """
    Redirect to current user's profile.
    """
    try:
        current_author = request.user.author
        return redirect('author-profile', author_id=current_author.id)
    except Author.DoesNotExist:
        return redirect('authors-list')
