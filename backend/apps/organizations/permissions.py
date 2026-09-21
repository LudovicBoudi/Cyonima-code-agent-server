from rest_framework.permissions import BasePermission

from .models import Membership


def get_membership(user, organization):
    if not user or not user.is_authenticated:
        return None
    return (
        Membership.objects.filter(organization=organization, user=user)
        .select_related("organization", "user")
        .first()
    )


def is_org_member(user, organization):
    return get_membership(user, organization) is not None


def is_org_admin(user, organization):
    m = get_membership(user, organization)
    return m is not None and m.role in (Membership.Role.OWNER, Membership.Role.ADMIN)


def user_organizations(user):
    return [
        m.organization
        for m in Membership.objects.filter(user=user).select_related("organization")
    ]


class IsOrgMember(BasePermission):
    """Autorise l'accès si l'utilisateur est membre de l'organisation ciblée."""

    def has_permission(self, request, view):
        org = getattr(view, "organization", None)
        if org is None:
            return False
        return is_org_member(request.user, org)


class IsOrgAdmin(BasePermission):
    """Autorise l'accès uniquement aux admin/owner de l'organisation."""

    def has_permission(self, request, view):
        org = getattr(view, "organization", None)
        if org is None:
            return False
        return is_org_admin(request.user, org)
