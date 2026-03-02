from django import template
from django.utils.safestring import mark_safe
import markdown as md

register = template.Library()

@register.filter
def render_markdown(value):
    if not value:
        return ""
    html = md.markdown(value, extensions=["extra"])
    return mark_safe(html)

