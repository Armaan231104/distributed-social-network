from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models import Q
from django.contrib.auth.models import User
from .models import Entry, HostedImage
from accounts.models import Author, Follow
from interactions.views import user_can_access_entry
import json


def get_stream_entries_for_user(user):
    """
    Determines which entries should appear in a user's stream.

    Visibility Rules:
    - Unauthenticated users see only PUBLIC entries.
    - Authenticated users see:
        • Their own entries (excluding DELETED)
        • All PUBLIC entries on the node
        • UNLISTED entries from authors they follow
        • FRIENDS entries from mutual followers
    """

    base_qs = Entry.objects.exclude(
        visibility="DELETED"
    ).select_related('author__author')

    if not user.is_authenticated:
        return base_qs.filter(
            visibility="PUBLIC"
        ).order_by('-published_at')

    try:
        current_author = user.author
    except Author.DoesNotExist:
        return base_qs.filter(
            Q(author=user) | Q(visibility="PUBLIC")
        ).order_by('-published_at').distinct()

    following_qs = Follow.objects.filter(
        follower=current_author,
        followee__user__isnull=False
    ).select_related('followee__user')

    followed_authors = [f.followee for f in following_qs]
    followed_users = [a.user for a in followed_authors if a.user]

    friend_users = [
        a.user for a in followed_authors
        if a.user and a.is_following(current_author)
    ]

    return base_qs.filter(
        Q(author=user) |
        Q(visibility="PUBLIC") |
        Q(author__in=followed_users, visibility="UNLISTED") |
        Q(author__in=friend_users, visibility="FRIENDS")
    ).order_by('-published_at').distinct()


def stream(request):
    """
    Renders the main timeline page.

    Visibility Rules:
    - Unauthenticated users see only PUBLIC entries.
    - Authenticated users see:
        • Their own entries (excluding DELETED)
        • All PUBLIC entries on the node
        • UNLISTED entries from authors they follow
        • FRIENDS entries from mutual followers
    """

    posts = get_stream_entries_for_user(request.user)

    return render(request, 'posts/stream.html', {'posts': posts})


def serialize_entry_for_stream(request, entry):
    """
    Converts an entry into JSON format for the stream API.
    """

    image_url = None

    if entry.image:
        try:
            image_url = request.build_absolute_uri(entry.image.url)
        except ValueError:
            image_url = None

    author_obj = None

    if hasattr(entry.author, "author"):
        author_profile = entry.author.author
        author_obj = {
            "id": author_profile.id,
            "displayName": author_profile.displayName,
            "host": author_profile.host,
            "web": author_profile.web,
            "github": author_profile.github,
            "profileImage": request.build_absolute_uri(author_profile.profileImage.url)
            if author_profile.profileImage else None,
        }

    return {
        "id": str(entry.id),
        "title": entry.title,
        "content": entry.content,
        "contentType": entry.content_type,
        "visibility": entry.visibility,
        "published": entry.published_at.isoformat(),
        "updated": entry.updated_at.isoformat(),
        "isEdited": entry.is_edited,
        "image": image_url,
        "author": author_obj,
    }


def stream_api(request):
    """
    Returns entries that should appear in the user's stream.

    Visibility Rules:
    - Unauthenticated users receive PUBLIC entries only.
    - Authenticated users receive:
        • Their own entries (excluding DELETED)
        • All PUBLIC entries
        • UNLISTED entries from authors they follow
        • FRIENDS entries from mutual followers
    """

    posts = get_stream_entries_for_user(request.user)

    data = [serialize_entry_for_stream(request, post) for post in posts]

    return JsonResponse({
        "type": "entries",
        "count": len(data),
        "src": data,
    })


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
    author_path = entry.author.id

    return render(request, 'interactions/entry_detail.html', {
        'entry': entry,
        'comments': comments,
        'author_path': author_path,
    })


@login_required
def create_entry(request):
    """
    Creates a new entry.

    Supports:
    - JSON requests for text/plain and text/markdown entries
    - multipart uploads for image entries
    """

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    valid_visibilities = [v[0] for v in Entry.VISIBILITY_CHOICES]

    if request.content_type and request.content_type.startswith("multipart/form-data"):

        title = request.POST.get("title", "")
        content = request.POST.get("content", "")
        content_type = request.POST.get("contentType", "image")
        visibility = request.POST.get("visibility", "PUBLIC")

        if visibility not in valid_visibilities:
            return JsonResponse({"error": "Invalid visibility"}, status=400)

        image_file = request.FILES.get("image")

        if not image_file:
            return JsonResponse({"error": "Image file required for image posts"}, status=400)

        entry = Entry.objects.create(
            author=request.user,
            title=title,
            content=content,
            content_type=content_type,
            visibility=visibility,
            image=image_file
        )

        return JsonResponse({"id": str(entry.id)}, status=201)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    title = data.get("title", "")
    content = data.get("content", "")
    content_type = data.get("contentType", "text/plain")
    visibility = data.get("visibility", "PUBLIC")

    if content_type not in dict(Entry.CONTENT_TYPES).keys():
        return JsonResponse({"error": "Invalid contentType"}, status=400)

    if visibility not in valid_visibilities:
        return JsonResponse({"error": "Invalid visibility"}, status=400)

    entry = Entry.objects.create(
        author=request.user,
        title=title,
        content=content,
        content_type=content_type,
        visibility=visibility
    )

    return JsonResponse({"id": str(entry.id)}, status=201)


@require_http_methods(["GET", "PATCH", "DELETE"])
def entry_detail_api(request, entry_id):
    """
    Handles GET (read), PATCH (partial update), and DELETE for a single entry.
    
    - GET: Returns a JSON representation of an entry.
    - PATCH: Partially updates an entry (only author).
    - DELETE: Soft deletes an entry (only author).
    """
    entry = get_object_or_404(Entry, id=entry_id)
    
    # GET - Read entry
    if request.method == "GET":
        if entry.visibility == "DELETED":
            if not request.user.is_authenticated or not request.user.is_staff:
                return JsonResponse({"error": "Not found"}, status=404)

        if entry.visibility in ["PUBLIC", "UNLISTED"]:
            pass
        elif entry.visibility == "FRIENDS":
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Forbidden"}, status=403)
            if request.user != entry.author:
                try:
                    viewer_author = request.user.author
                    entry_author = entry.author.author
                except Author.DoesNotExist:
                    return JsonResponse({"error": "Forbidden"}, status=403)
                if not viewer_author.is_friend(entry_author):
                    return JsonResponse({"error": "Forbidden"}, status=403)

        image_url = None
        if entry.image:
            try:
                image_url = request.build_absolute_uri(entry.image.url)
            except ValueError:
                image_url = None

        return JsonResponse({
            "id": str(entry.id),
            "title": entry.title,
            "content": entry.content,
            "contentType": entry.content_type,
            "visibility": entry.visibility,
            "published": entry.published_at.isoformat(),
            "image": image_url,
        })
    
    # PATCH - Partial update (only author)
    if request.method == "PATCH":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        if entry.author != request.user:
            return HttpResponseForbidden()
        
        if entry.visibility == "DELETED":
            return JsonResponse({"error": "Entry not found"}, status=404)
        
        try:
            data = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if "content" in data:
            entry.content = data["content"].strip()
        
        if "title" in data:
            entry.title = data["title"]
        
        entry.save()

        return JsonResponse({
            "id": str(entry.id),
            "message": "Updated successfully",
            "content": entry.content
        }, status=200)
    
    # DELETE - Soft delete (only author)
    if request.method == "DELETE":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        
        if entry.author != request.user:
            return HttpResponseForbidden()
        
        entry.soft_delete()
        return JsonResponse({"deleted": True})


@login_required
def upload_hosted_image(request):
    """
    Uploads an image hosted by this node.
    """

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)

    image_file = request.FILES.get("image")

    if not image_file:
        return JsonResponse({"error": "Image file required"}, status=400)

    hosted_image = HostedImage.objects.create(
        author=request.user,
        image=image_file
    )

    image_url = request.build_absolute_uri(hosted_image.image.url)

    return JsonResponse({
        "id": str(hosted_image.id),
        "url": image_url
    }, status=201)


@login_required
def my_entries(request):
    """
    Returns all non-deleted entries created by the user.
    """

    entries = Entry.objects.filter(
        author=request.user
    ).exclude(
        visibility="DELETED"
    )

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

    referrer = request.META.get("HTTP_REFERER")

    if referrer:
        return redirect(referrer)
    else:
        return redirect("stream")


@login_required
def deleted_entries(request):
    """
    Node admin view: lists all soft-deleted entries across all authors.

    Access Control:
    - Must be authenticated (enforced by @login_required → redirects to login).
    - Must be staff (is_staff=True); non-staff receive 403 Forbidden.

    Behaviour:
    - Entries are never hard-deleted; soft_delete() sets visibility to "DELETED".
    - This view is the only place in the UI where DELETED entries are visible.
    - Results are ordered by updated_at descending (most recently deleted first).
    """
    if not request.user.is_staff:
        return HttpResponseForbidden()

    entries = Entry.objects.filter(visibility="DELETED").select_related('author__author').order_by('-updated_at')
    return render(request, 'posts/deleted_entries.html', {'entries': entries})
