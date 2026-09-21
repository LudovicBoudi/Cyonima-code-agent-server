from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    MembershipViewSet,
    OrganizationViewSet,
    TeamMembershipViewSet,
    TeamViewSet,
)

router = DefaultRouter()
router.register("", OrganizationViewSet, basename="organization")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "<uuid:org_pk>/members/",
        MembershipViewSet.as_view({"get": "list", "post": "create"}),
        name="org-members",
    ),
    path(
        "<uuid:org_pk>/members/<uuid:pk>/",
        MembershipViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="org-member-detail",
    ),
    path(
        "<uuid:org_pk>/teams/",
        TeamViewSet.as_view({"get": "list", "post": "create"}),
        name="org-teams",
    ),
    path(
        "<uuid:org_pk>/teams/<uuid:pk>/",
        TeamViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="org-team-detail",
    ),
    path(
        "teams/<uuid:team_pk>/members/",
        TeamMembershipViewSet.as_view({"get": "list", "post": "create"}),
        name="team-members",
    ),
]
