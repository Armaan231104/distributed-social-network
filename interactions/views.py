from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from posts.models import Entry
from accounts.models import Author
from interactions.models import Like, Comment
from .models import Like

def user_can_access_entry(user, entry):
    if entry.visibility in ['PUBLIC', 'UNLISTED']:
        return True
    if entry.visibility == 'FRIENDS':
        if not user.is_authenticated:
            return False
        if user == entry.author:
            return True
        # check if they are friends (mutual follow)
        try:
            author = user.author
            return author.is_friend(entry.author.author)
        except Exception:
            return False
    return False

@login_required
@require_POST
def toggle_like(request, object_type, object_id):
    author = request.user.author
    if object_type == 'entry':
        obj = get_object_or_404(Entry, id=object_id)
        if not user_can_access_entry(request.user, obj):
            return JsonResponse({'error': 'Forbidden'}, status=403)
        like, created = Like.objects.get_or_create(author=author, entry=obj, comment=None)
    elif object_type == 'comment':
        obj = get_object_or_404(Comment, id=object_id)
        if not user_can_access_entry(request.user, obj.entry):
            return JsonResponse({'error': 'Forbidden'}, status=403)
        like, created = Like.objects.get_or_create(author=author, entry=None, comment=obj)
    else:
        return JsonResponse({'error': 'invalid type'}, status=400)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True

    return JsonResponse({
        'liked': liked,
        'like_count': obj.likes.count()
    })

@login_required
def add_comment(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)
    if not user_can_access_entry(request.user, entry):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Comment.objects.create(
                entry = entry,
                author = request.user.author,
                content = content,
            )
    return redirect('entry_detail', entry_id=entry_id)
