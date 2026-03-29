from django.contrib import admin
from .models import RemoteNode

@admin.register(RemoteNode)
class RemoteNodeAdmin(admin.ModelAdmin):
    list_display = ['url', 'username', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['url', 'username']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['enable_nodes', 'disable_nodes']

    @admin.action(description='Enable selected nodes')
    def enable_nodes(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='Disable selected nodes')
    def disable_nodes(self, request, queryset):
        queryset.update(is_active=False)