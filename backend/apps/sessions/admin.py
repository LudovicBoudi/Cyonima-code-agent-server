from django.contrib import admin

from .models import Message, Session


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["title", "workspace", "user", "model", "created_at"]
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["session", "role", "created_at"]
    list_filter = ["role"]
