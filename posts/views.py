from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from .models import Entry
import json


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