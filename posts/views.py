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
def entry_detail(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)
    comments = entry.comments.all()
    return render(request, 'interactions/entry_detail.html', {
        'entry': entry,
        'comments': comments,
    })

@login_required
def create_entry(request):
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
            content_type=content_type,  # probably "image"
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
    content_type = data.get("contentType", "text/plaintext")

    if content_type not in ["text/plaintext", "text/markdown"]:
        return JsonResponse({"error": "Invalid contentType for JSON post"}, status=400)

    entry = Entry.objects.create(
        author=request.user,
        title=title,
        content=content,
        content_type=content_type
    )
    return JsonResponse({"id": str(entry.id)}, status=201)

    


  


@login_required
def my_entries(request):
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
            "contentType": getattr(e, "content_type", "text/plaintext"),
            "image": image_url,
            "visibility": e.visibility,
            "published": e.published_at.isoformat(),
        }

    data = [entry_to_dict(e) for e in entries]
    return JsonResponse(data, safe=False)


@login_required
def edit_entry(request, entry_id):
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

        ct = request.POST.get("contentType", getattr(entry, "content_type", "text/plaintext"))
        if ct not in ["text/plaintext", "text/markdown", "image"]:
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
        if ct not in ["text/plaintext", "text/markdown", "image"]:
            return JsonResponse({"error": "Invalid contentType"}, status=400)
        entry.content_type = ct

    entry.save()
    return JsonResponse({"updated": True}, status=200)

@login_required
def delete_entry(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)

    # story 3
    if entry.author != request.user:
        return HttpResponseForbidden()

    # story 1
    entry.soft_delete()
    return JsonResponse({"deleted": True})

