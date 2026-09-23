from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.organizations.models import Membership

User = get_user_model()


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    verbose_name = "Membre d'organisation"
    verbose_name_plural = "Membres d'organisations"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "name", "is_staff", "is_active", "date_joined"]
    list_filter = ["is_active", "is_staff", "is_superuser"]
    search_fields = ["email", "name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations", {"fields": ("name",)}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "name", "password1", "password2")}),
    )
    inlines = [MembershipInline]
