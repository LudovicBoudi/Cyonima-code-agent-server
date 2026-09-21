from django.contrib import admin

from .models import PermissionRequest


@admin.register(PermissionRequest)
class PermissionRequestAdmin(admin.ModelAdmin):
    list_display = ["tool", "status", "session", "call_id", "created_at"]
    list_filter = ["status", "tool"]
    search_fields = ["call_id", "preview"]
