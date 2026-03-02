from django import template
from interactions.models import Like, Comment
from posts.models import Entry

register = template.Library()

@register.simple_tag
def user_has_liked(obj, user):
    if not user.is_authenticated:
        return False
    author = user.author

    if isinstance(obj, Entry):
        return Like.objects.filter(entry=obj, comment=None, author=author).exists()
    else:
        return Like.objects.filter(entry=None, comment=obj, author=author).exists()