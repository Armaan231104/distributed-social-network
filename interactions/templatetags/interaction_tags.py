from django import template
from interactions.models import Like

register = template.Library()

@register.simple_tag
def user_has_liked(post, user):
    author = user.author
    if not user.is_authenticated:
        return False
    return Like.objects.filter(entry=post, author=author).exists()