from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Membership, Organization, Team, TeamMembership
from .permissions import IsOrgAdmin, IsOrgMember, is_org_admin
from .serializers import (
    MembershipSerializer,
    OrganizationSerializer,
    TeamMembershipSerializer,
    TeamSerializer,
)


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Organization.objects.filter(memberships__user=self.request.user).distinct()

    def get_permissions(self):
        # La visibilité est garantie par get_queryset (orgs de l'utilisateur) ;
        # les mutations sont restreintes aux admins via check_object_permissions.
        return [IsAuthenticated()]

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if self.action in ("update", "partial_update", "destroy"):
            if not is_org_admin(request.user, obj):
                self.permission_denied(request, message="Réservé aux administrateurs.")


class OrgScopedViewSetMixin:
    """Mixins pour résoudre l'organisation depuis l'URL (pk d'organisation)."""

    organization = None

    def initial(self, request, *args, **kwargs):
        # Résoudre l'organisation AVANT les contrôles de permissions
        org_pk = self.kwargs.get("org_pk")
        if org_pk:
            self.organization = Organization.objects.get(pk=org_pk)
        super().initial(request, *args, **kwargs)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.organization:
            ctx["organization"] = self.organization
        return ctx


class MembershipViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get_queryset(self):
        return Membership.objects.filter(organization=self.organization)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrgMember()]


class TeamViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated, IsOrgMember]

    def get_queryset(self):
        return Team.objects.filter(organization=self.organization)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrgMember()]


class TeamMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = TeamMembershipSerializer
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        self.team = Team.objects.get(pk=self.kwargs["team_pk"])
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        return TeamMembership.objects.filter(team=self.team)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["team"] = self.team
        return ctx
