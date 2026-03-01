from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from posts.models import Entry
from accounts.models import Author
from .models import Like


@login_required
@require_POST
def toggle_like(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)
    author = request.user.author
    like, created = Like.objects.get_or_create(author=author, entry=entry)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    return JsonResponse({
        'liked': liked,
        'like_count': entry.likes.count()
    })
