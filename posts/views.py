from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Entry
from accounts.models import Author, Follow
import json

def stream(request):
    # Unauthenticated users see only public posts from all authors
    if not request.user.is_authenticated:
        posts = Entry.objects.filter(
            visibility="PUBLIC"
        ).select_related('author__author').order_by('-published_at')
        return render(request, 'posts/stream.html', {'posts': posts})

    try:
        current_author = request.user.author
    except Author.DoesNotExist:
        # Authenticated user with no Author profile: own posts + all public posts
        posts = Entry.objects.filter(
            Q(author=request.user) | Q(visibility="PUBLIC")
        ).exclude(visibility="DELETED").select_related('author__author').order_by('-published_at')
        return render(request, 'posts/stream.html', {'posts': posts})

    # Collect local authors the current user follows
    following_qs = Follow.objects.filter(
        follower=current_author
    ).select_related('followee__user')
    followed_authors = [f.followee for f in following_qs if f.followee.user]
    followed_users = [a.user for a in followed_authors]

    # Subset of followed authors who also follow back (friends / mutual followers)
    friend_users = [a.user for a in followed_authors if a.is_following(current_author)]

    posts = Entry.objects.filter(
        # Users own posts, excluding deleted
        (Q(author=request.user) & ~Q(visibility="DELETED")) |
        # Showing posts of authors followed by the user (public and unlisted posts)
        Q(author__in=followed_users, visibility__in=["PUBLIC", "UNLISTED"]) |
        # showing posts from user's friends, including FRIENDS-only posts
        Q(author__in=friend_users, visibility="FRIENDS")
    ).select_related('author__author').order_by('-published_at')

    return render(request, 'posts/stream.html', {'posts': posts})


@login_required
def create_entry(request):
    if request.method == "POST":
        data = json.loads(request.body)
        entry = Entry.objects.create(
            author=request.user,
            title=data.get("title", ""),
            content=data.get("content", "")
        )
        return JsonResponse({"id": str(entry.id)})

    return JsonResponse({"error": "POST required"}, status=400)


@login_required
def my_entries(request):
    entries = Entry.objects.filter(author=request.user).exclude(visibility="DELETED")
    data = [
        {
            "id": str(e.id),
            "title": e.title,
            "content": e.content,
            "visibility": e.visibility
        }
        for e in entries
    ]
    return JsonResponse(data, safe=False)


@login_required
def edit_entry(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)

    # story 3
    if entry.author != request.user:
        return HttpResponseForbidden()
    
    if entry.visibility == "DELETED":
        return JsonResponse({"error": "Entry not found"}, status=404)

    if request.method == "PUT":
        data = json.loads(request.body)
        entry.title = data.get("title", entry.title)
        entry.content = data.get("content", entry.content)
        entry.save()
        return JsonResponse({"updated": True})

    return JsonResponse({"error": "PUT required"}, status=400)


@login_required
def delete_entry(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)

    # story 3
    if entry.author != request.user:
        return HttpResponseForbidden()

    # story 1
    entry.soft_delete()
    return JsonResponse({"deleted": True})