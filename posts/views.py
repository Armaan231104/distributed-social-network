from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Q
from .models import Entry
from accounts.models import Author, Follow
from interactions.views import user_can_access_entry
import json

def stream(request):
    """
    Renders the main timeline page.

    Visibility Rules:
    - Unauthenticated users see only PUBLIC entries.
    - Authenticated users see:
        • Their own entries (excluding DELETED)
        • PUBLIC and UNLISTED entries from authors they follow
        • FRIENDS entries from mutual followers
    """
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
def entry_detail(request, entry_id):
    """
    Renders the detailed view of a single entry.
    Returns 403 if the user is not permitted to view the entry.
    """
    entry = get_object_or_404(Entry, id=entry_id)
    if not user_can_access_entry(request.user, entry):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    comments = entry.comments.all()
    return render(request, 'interactions/entry_detail.html', {
        'entry': entry,
        'comments': comments,
    })

@login_required
def create_entry(request):
    """
    Creates a new entry. 
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    # A) multipart/form-data => image upload
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        title = request.POST.get("title", "")
        content = request.POST.get("content", "")
        content_type = request.POST.get("contentType", "image")

        image_file = request.FILES.get("image")
        if not image_file:
            return JsonResponse({"error": "Image file required for image posts"}, status=400)

        entry = Entry.objects.create(
            author=request.user,
            title=title,
            content=content,
            content_type=content_type,
            image=image_file
        )
        return JsonResponse({"id": str(entry.id)}, status=201)

    # B) JSON => text/plain or text/markdown
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    title = data.get("title", "")
    content = data.get("content", "")
    content_type = data.get("contentType", "text/plain")

    if content_type not in dict(Entry.CONTENT_TYPES).keys():
        return JsonResponse({"error": "Invalid contentType for JSON post"}, status=400)

    visibility = data.get("visibility", "PUBLIC")

    entry = Entry.objects.create(
        author=request.user,
        title=title,
        content=content,
        content_type=content_type,
        visibility=visibility
    )
    return JsonResponse({"id": str(entry.id)}, status=201)

def get_entry(request, entry_id):
    """
    Returns a JSON representation of an entry.

    Visibility Enforcement:
    - DELETED: Only accessible to node admins.
    - PUBLIC / UNLISTED: Accessible by anyone.
    - FRIENDS: Accessible only to the author (API restriction).
    """
    entry = get_object_or_404(Entry, id=entry_id)

    if entry.visibility == "DELETED":
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse({"error": "Not found"}, status=404)

    if entry.visibility in ["PUBLIC", "UNLISTED"]:
        pass    

    elif entry.visibility == "FRIENDS":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Forbidden"}, status=403)
        if request.user != entry.author:
            return JsonResponse({"error": "Forbidden"}, status=403)

    return JsonResponse({
        "id": str(entry.id),
        "title": entry.title,
        "content": entry.content,
        "contentType": entry.content_type,
        "visibility": entry.visibility,
        "published": entry.published_at.isoformat(),
    })  

@login_required
def my_entries(request):
    """
    Returns all non-deleted entries created by the user.
    """
    entries = Entry.objects.filter(author=request.user).exclude(visibility="DELETED")

    def entry_to_dict(e):
        image_url = None
        if getattr(e, "image", None):
            try:
                image_url = request.build_absolute_uri(e.image.url)
            except ValueError:
                image_url = None

        return {
            "id": str(e.id),
            "title": e.title,
            "content": e.content,
            "contentType": getattr(e, "content_type", "text/plain"),
            "image": image_url,
            "visibility": e.visibility,
            "published": e.published_at.isoformat(),
        }

    data = [entry_to_dict(e) for e in entries]
    return JsonResponse(data, safe=False)


@login_required
def edit_entry(request, entry_id):
    """
    Updates an existing entry.

    Only the author may edit.
    Deleted entries cannot be edited.
    """
    entry = get_object_or_404(Entry, id=entry_id)

    if entry.author != request.user:
        return HttpResponseForbidden()

    if entry.visibility == "DELETED":
        return JsonResponse({"error": "Entry not found"}, status=404)

    if request.method != "PUT":
        return JsonResponse({"error": "PUT required"}, status=400)

    # A) multipart/form-data => editing image/caption/title, optionally replace image
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        entry.title = request.POST.get("title", entry.title)
        entry.content = request.POST.get("content", entry.content)

        ct = request.POST.get("contentType", getattr(entry, "content_type", "text/plain"))
        if ct not in dict(Entry.CONTENT_TYPES).keys():
            return JsonResponse({"error": "Invalid contentType"}, status=400)
        entry.content_type = ct

        new_image = request.FILES.get("image")
        if new_image:
            entry.image = new_image

        entry.save()
        return JsonResponse({"updated": True}, status=200)

    # B) JSON => editing title/content/contentType for text posts
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if "title" in data:
        entry.title = data["title"]

    if "content" in data:
        entry.content = data["content"]

    if "contentType" in data:
        ct = data["contentType"]
        if ct not in dict(Entry.CONTENT_TYPES).keys():
            return JsonResponse({"error": "Invalid contentType"}, status=400)
        entry.content_type = ct

    entry.save()
    return JsonResponse({"updated": True}, status=200)
  
@login_required
@require_POST
def delete_entry_ui(request, entry_id):
    """
    Soft deletes an entry via the UI.

    Only the author may delete.
    """
    entry = get_object_or_404(Entry, id=entry_id)

    if entry.author != request.user:
        return HttpResponseForbidden("You cannot delete this entry.")

    entry.soft_delete()
    return redirect("stream")

@login_required
def delete_entry(request, entry_id):
    """
    Soft deletes an entry via the API.

    Only the author may delete.
    """
    entry = get_object_or_404(Entry, id=entry_id)

    if entry.author != request.user:
        return HttpResponseForbidden()
    
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE required"}, status=400)

    entry.soft_delete()
    return JsonResponse({"deleted": True})

