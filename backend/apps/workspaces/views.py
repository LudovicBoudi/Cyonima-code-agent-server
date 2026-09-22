from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organizations.permissions import IsOrgAdmin, IsOrgMember
from apps.organizations.views import OrgScopedViewSetMixin

from . import files, sandbox, services
from .models import Workspace
from .serializers import WorkspaceSerializer


class WorkspaceViewSet(OrgScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer
    permission_classes = [IsAuthenticated, IsOrgMember]
    lookup_field = "pk"

    def get_queryset(self):
        qs = Workspace.objects.filter(organization=self.organization)
        # Un membre ne voit que les workspaces de son équipe (ou non restreints)
        return qs

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsOrgAdmin()]
        return [IsAuthenticated(), IsOrgMember()]

    def perform_destroy(self, instance):
        from .tasks import destroy_workspace_task

        try:
            destroy_workspace_task.delay(str(instance.id))
        except Exception:
            # Fallback synchrone (dev sans broker/worker)
            services.destroy_workspace(instance)
            instance.delete()

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None, org_pk=None):
        workspace = self.get_object()
        sandbox.start_container(workspace)
        workspace.status = Workspace.Status.READY
        workspace.save(update_fields=["status"])
        return Response(WorkspaceSerializer(workspace, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None, org_pk=None):
        workspace = self.get_object()
        sandbox.stop_container(workspace)
        workspace.status = Workspace.Status.STOPPED
        workspace.save(update_fields=["status"])
        return Response(WorkspaceSerializer(workspace, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get"])
    def files(self, request, pk=None, org_pk=None):
        workspace = self.get_object()
        rel = request.query_params.get("path", "")
        return Response(files.list_dir(workspace, rel))

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None, org_pk=None):
        workspace = self.get_object()
        rel = request.query_params.get("path", "")
        return Response({"path": rel, "content": files.read_file(workspace, rel)})

    @action(detail=True, methods=["get"])
    def git_status(self, request, pk=None, org_pk=None):
        workspace = self.get_object()
        return Response(files.git_status(workspace))
