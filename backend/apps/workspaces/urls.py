from django.urls import path

from .views import WorkspaceViewSet

urlpatterns = [
    path(
        "<uuid:org_pk>/workspaces/",
        WorkspaceViewSet.as_view({"get": "list", "post": "create"}),
        name="workspace-list",
    ),
    path(
        "<uuid:org_pk>/workspaces/local_dirs/",
        WorkspaceViewSet.as_view({"get": "local_dirs"}),
        name="workspace-local-dirs",
    ),
    path(
        "<uuid:org_pk>/workspaces/<uuid:pk>/",
        WorkspaceViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="workspace-detail",
    ),
    path(
        "<uuid:org_pk>/workspaces/<uuid:pk>/start/",
        WorkspaceViewSet.as_view({"post": "start"}),
        name="workspace-start",
    ),
    path(
        "<uuid:org_pk>/workspaces/<uuid:pk>/stop/",
        WorkspaceViewSet.as_view({"post": "stop"}),
        name="workspace-stop",
    ),
    path(
        "<uuid:org_pk>/workspaces/<uuid:pk>/files/",
        WorkspaceViewSet.as_view({"get": "files"}),
        name="workspace-files",
    ),
    path(
        "<uuid:org_pk>/workspaces/<uuid:pk>/file/",
        WorkspaceViewSet.as_view({"get": "file"}),
        name="workspace-file",
    ),
    path(
        "<uuid:org_pk>/workspaces/<uuid:pk>/git-status/",
        WorkspaceViewSet.as_view({"get": "git_status"}),
        name="workspace-git-status",
    ),
]
