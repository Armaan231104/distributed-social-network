from django.contrib import admin
from .models import Entry


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'visibility', 'published_at', 'updated_at')
    list_filter = ('visibility',)
    search_fields = ('title', 'author__username')
    ordering = ('-updated_at',)