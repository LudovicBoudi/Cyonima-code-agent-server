from django.urls import include, path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminUsersViewSet,
    LoginView,
    MeView,
    SessionTokenView,
    SsoProvidersView,
)

router = SimpleRouter()
router.register("admin/users", AdminUsersViewSet, basename="admin-users")

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("session-token/", SessionTokenView.as_view(), name="session-token"),
    path("sso/", SsoProvidersView.as_view(), name="sso-providers"),
    # SSO (OIDC/SAML) via allauth (flux redirect classique)
    path("accounts/", include("allauth.urls")),
] + router.urls
