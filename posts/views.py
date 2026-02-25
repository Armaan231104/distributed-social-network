from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Post

@login_required
def stream(request):
    posts = Post.objects.filter(author=request.user)
    return render(request, 'posts/stream.html', {'posts': posts})
