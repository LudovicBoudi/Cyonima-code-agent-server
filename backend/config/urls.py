"""Routage URL racine."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/orgs/", include("apps.organizations.urls")),
    path("api/orgs/", include("apps.workspaces.urls")),
    path("api/sessions/", include("apps.sessions.urls")),
    path("api/ollama/", include("apps.ollama.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
