from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.organizations.permissions import is_org_member
from apps.workspaces.models import Workspace

from .models import Message, Session
from .serializers import MessageSerializer, SessionSerializer


class SessionViewSet(viewsets.ModelViewSet):
    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = Session.objects.filter(user=self.request.user).select_related("workspace")
        workspace_id = self.request.query_params.get("workspace")
        if workspace_id:
            qs = qs.filter(workspace_id=workspace_id)
        return qs

    def perform_create(self, serializer):
        workspace_id = self.request.data.get("workspace")
        workspace = get_object_or_404(Workspace, id=workspace_id)
        if not is_org_member(self.request.user, workspace.organization):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("Accès au workspace refusé.")
        serializer.save(
            user=self.request.user,
            workspace=workspace,
            model=serializer.validated_data.get("model", "") or settings.OLLAMA_DEFAULT_MODEL,
        )

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        session = self.get_object()
        messages = session.messages.exclude(role=Message.Role.SYSTEM)
        return Response(MessageSerializer(messages, many=True).data)

    @action(detail=True, methods=["get"])
    def git_status(self, request, pk=None):
        from apps.workspaces import files

        session = self.get_object()
        return Response(files.git_status(session.workspace))

    @action(detail=True, methods=["post"])
    def fork(self, request, pk=None):
        source = self.get_object()
        new_session = Session.objects.create(
            workspace=source.workspace,
            user=request.user,
            title=f"{source.title} (fork)" if source.title else "",
            model=source.model,
            reasoning=source.reasoning,
        )
        for m in source.messages.exclude(role=Message.Role.SYSTEM):
            Message.objects.create(
                session=new_session,
                role=m.role,
                content=m.content,
                tool_calls=m.tool_calls,
                tool_call_id=m.tool_call_id,
                meta=m.meta,
            )
        return Response(
            SessionSerializer(new_session, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
