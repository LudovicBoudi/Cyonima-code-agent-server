import logging

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.agents.services import list_pending, respond
from apps.workspaces import files
from apps.workspaces.models import Workspace

from .models import Message, Session
from .serializers import MessageSerializer, PermissionRequestSerializer, SessionSerializer

logger = logging.getLogger(__name__)


def resolve_model_name(model):
    """Résout un modèle Ollama (défaut → valide installé), sans échec en dur."""
    from asgiref.sync import async_to_sync
    from apps.ollama.client import OllamaClient

    value = model or settings.OLLAMA_DEFAULT_MODEL
    try:
        return async_to_sync(OllamaClient().resolve_model)(value)
    except Exception:
        logger.warning("Résolution du modèle impossible, on garde %s", value, exc_info=True)
        return value


def ensure_personal_org(user):
    """Org invisible « personnelle » de l'utilisateur (pour la création auto de workspaces)."""
    from apps.organizations.models import Membership, Organization

    org, created = Organization.objects.get_or_create(
        slug=f"perso-{user.id}",
        defaults={"name": f"Espace de {user.email}", "created_by": user},
    )
    if created:
        Membership.objects.create(organization=org, user=user, role=Membership.Role.OWNER)
    return org


def local_slug(base, qs, field="slug"):
    """Génère un slug unique dans un queryset en suffixant -2, -3…"""
    from django.utils.text import slugify

    slug = slugify(base) or "projet"
    n = 2
    candidate = slug
    while qs.filter(**{f"{field}__startswith": candidate}).exists():
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


class SessionViewSet(viewsets.ModelViewSet):
    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        return (
            Session.objects.filter(user=self.request.user)
            .select_related("workspace", "workspace__organization")
        )

    def perform_create(self, serializer):
        name = (self.request.data.get("name") or "").strip()
        local_path = (self.request.data.get("local_path") or "").strip()
        if not name:
            raise ValidationError({"name": "Nom du projet requis."})
        if not local_path:
            raise ValidationError({"local_path": "Choisissez un dossier de travail."})

        try:
            path = files.resolve_local_path(local_path)
        except PermissionError as exc:
            raise ValidationError({"local_path": str(exc)})
        except (OSError, NotADirectoryError) as exc:
            raise ValidationError({"local_path": str(exc)})

        org = ensure_personal_org(self.request.user)
        workspace = Workspace.objects.create(
            organization=org,
            name=name,
            slug=local_slug(name, Workspace.objects.filter(organization=org)),
            local_path=path,
            created_by=self.request.user,
            status=Workspace.Status.READY,  # dossier local existant : pas de provision
        )
        serializer.save(
            user=self.request.user,
            workspace=workspace,
            title=name,
            model=resolve_model_name(serializer.validated_data.get("model", "")),
        )

    @action(detail=False, methods=["get"])
    def local_dirs(self, request):
        """Parcourez les dossiers serveur autorisés (choix du dossier de travail)."""
        from rest_framework.exceptions import ValidationError

        path = request.query_params.get("path", "")
        try:
            return Response(files.list_local_dirs(path))
        except PermissionError as exc:
            raise ValidationError({"path": str(exc)})
        except (OSError, NotADirectoryError):
            raise ValidationError({"path": "Dossier inaccessible."})

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        session = self.get_object()
        messages = session.messages.exclude(role=Message.Role.SYSTEM)
        return Response(MessageSerializer(messages, many=True).data)

    @action(detail=True, methods=["get"])
    def git_status(self, request, pk=None):
        session = self.get_object()
        return Response(files.git_status(session.workspace))

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        session = self.get_object()
        pending = list_pending(session.id)
        return Response(PermissionRequestSerializer(pending, many=True).data)

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        session = self.get_object()
        call_id = request.data.get("call_id")
        approved = bool(request.data.get("approved", False))
        if not call_id:
            return Response({"error": "call_id manquant"}, status=status.HTTP_400_BAD_REQUEST)
        ok = respond(session.id, call_id, approved)
        if not ok:
            return Response({"error": "demande introuvable ou déjà résolue"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"call_id": call_id, "status": "approved" if approved else "denied"})

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
