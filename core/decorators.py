from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

def approved_author_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):

        author = getattr(request.user, "author", None)

        if author and getattr(author, "is_approved", False):
            return view_func(request, *args, **kwargs)

        return redirect("pending-approval")

    return _wrapped_view