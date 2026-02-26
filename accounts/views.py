import requests
from urllib.parse import unquote
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Author, FollowRequest, Follow
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


class AuthorListView(APIView):
    """List all authors on this node."""
    permission_classes = [AllowAny]

    def get(self, request):
        authors = Author.objects.filter(is_approved=True)
        serializer = AuthorListSerializer(authors, many=True)
        return Response({
            'type': 'authors',
            'items': serializer.data
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
            'items': serializer.data,
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
            'items': serializer.data,
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
    
    Note: Per the spec, follow requests go to inbox first. The actual "following" relationship
    is only created after the target author approves the request.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, author_id, foreign_id):
        """Send a follow request to another author."""
        try:
            author = Author.objects.get(user=request.user)
        except Author.DoesNotExist:
            return Response({'error': 'Author not found'}, status=status.HTTP_404_NOT_FOUND)

        if str(author.user_id) != str(author_id):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

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

        if author.is_following(foreign_author):
            return Response({'error': 'Already following'}, status=status.HTTP_400_BAD_REQUEST)

        existing_request = FollowRequest.objects.filter(
            actor=author,
            object=foreign_author,
            status=FollowRequest.Status.PENDING
        ).first()

        if existing_request:
            return Response({'error': 'Follow request already pending'}, status=status.HTTP_400_BAD_REQUEST)

        FollowRequest.objects.create(
            actor=author,
            object=foreign_author,
            summary=f'{author.displayName} wants to follow {foreign_author.displayName}',
            status=FollowRequest.Status.PENDING
        )

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
        """Unfollow an author."""
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

        Follow.objects.filter(follower=author, followee=foreign_author).delete()
        FollowRequest.objects.filter(actor=author, object=foreign_author).delete()

        return Response({'status': 'unfollowed'}, status=status.HTTP_200_OK)


class AcceptFollowView(APIView):
    """
    Handle approving or rejecting follow requests.
    
    User story: As an author, I want to be able to approve or deny other authors following me, 
    so that I don't get followed by people I don't like.
    
    When you approve, a Follow relationship is created. When you reject, only the request
    status is updated to rejected.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, author_id, foreign_id):
        """Accept a follow request."""
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

        follow_request = FollowRequest.objects.filter(
            actor=foreign_author,
            object=author,
            status=FollowRequest.Status.PENDING
        ).first()

        if not follow_request:
            return Response({'error': 'No pending follow request'}, status=status.HTTP_404_NOT_FOUND)

        follow_request.status = FollowRequest.Status.ACCEPTED
        follow_request.save()

        Follow.objects.get_or_create(follower=foreign_author, followee=author)

        return Response({'status': 'follow request accepted'}, status=status.HTTP_200_OK)

    def delete(self, request, author_id, foreign_id):
        """Reject or remove a follower."""
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

        Follow.objects.filter(follower=foreign_author, followee=author).delete()
        FollowRequest.objects.filter(
            actor=foreign_author, 
            object=author
        ).update(status=FollowRequest.Status.REJECTED)

        return Response({'status': 'follower removed'}, status=status.HTTP_200_OK)


class FollowRequestListView(APIView):
    """
    Get pending follow requests for an author.
    
    User story: As an author, I want to know if I have "follow requests," so I can approve them.
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


# UI Views
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
    """Show an author's profile."""
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
