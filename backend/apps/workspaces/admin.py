from django.contrib import admin

from .models import Workspace


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "team", "status", "created_by", "created_at"]
    list_filter = ["status", "organization"]
    search_fields = ["name", "slug"]
