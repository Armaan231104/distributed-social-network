from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseNotFound
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Entry
import json

# -------------------------
# Author sees their own entries until deleted
# -------------------------
@login_required
def stream(request):
    if request.user.is_staff:
        posts = Entry.objects.filter(author=request.user)
    else:
        posts = Entry.objects.filter(author=request.user).exclude(visibility="DELETED")

    return render(request, "posts/stream.html", {"posts": posts})

# -------------------------
# Entry detail page
# -------------------------
def entry_detail(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)

    # Deleted entries: only admin can view
    if entry.visibility == "DELETED":
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseNotFound("Entry not found.")

    # Friends only: only the author
    if entry.visibility == "FRIENDS":
        if not request.user.is_authenticated or request.user != entry.author:
            return HttpResponseForbidden("Forbidden.")

    # Public (Accessible by link)
    return render(request, "posts/detail.html", {"entry": entry})

# -------------------------
# Author can delete their own entries
# -------------------------
@login_required
@require_POST
def delete_entry_ui(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)

    # Other authors cannot modify/delete my entries
    if entry.author != request.user:
        return HttpResponseForbidden("You cannot delete this entry.")

    entry.soft_delete()
    return redirect("stream")

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
def delete_entry(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)

    if entry.author != request.user:
        return HttpResponseForbidden()
    
    if request.method != "DELETE":
        return JsonResponse({"error": "DELETE required"}, status=400)

    entry.soft_delete()
    return JsonResponse({"deleted": True})