from django.contrib import admin
from .models import Author, FollowRequest, Follow


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ['displayName', 'id', 'host', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'host']
    search_fields = ['displayName', 'id']


@admin.register(FollowRequest)
class FollowRequestAdmin(admin.ModelAdmin):
    list_display = ['actor', 'object', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['actor__displayName', 'object__displayName']


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ['follower', 'followee', 'created_at']
    search_fields = ['follower__displayName', 'followee__displayName']
