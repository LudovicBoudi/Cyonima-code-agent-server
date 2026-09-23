import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .client import OllamaClient
from .progress import get_progress
from .tasks import pull_model_task

logger = logging.getLogger(__name__)


class OllamaModelsView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client = OllamaClient()
        models = async_to_sync(client.list_models)()
        default_model = async_to_sync(client.resolve_model)(
            settings.OLLAMA_DEFAULT_MODEL
        )
        return Response({"models": models, "default_model": default_model})


class OllamaModelDetailView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, name):
        client = OllamaClient()
        caps = async_to_sync(client.capabilities)(name)
        return Response({"name": name, **caps})

    def delete(self, request, name):
        ok = async_to_sync(OllamaClient().delete)(name)
        if not ok:
            return Response({"error": "Suppression impossible"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"deleted": name})


class OllamaPullView(views.APIView):
    """Lance un pull en tâche Celery. Retourne le task_id (202 Accepted).

    Fallback : si le broker (Redis) est indisponible, le pull est exécuté de
    manière synchrone (bloquant) — utile uniquement en dev sans worker.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, name):
        try:
            task = pull_model_task.delay(name)
            return Response(
                {"task_id": task.id, "model": name, "status": "pulling"},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as exc:
            logger.warning("Broker indisponible, pull synchrone (%s)", exc)
            try:
                ok = async_to_sync(OllamaClient().pull)(name)
                return Response({"model": name, "status": "success" if ok else "error"})
            except Exception as pull_exc:
                logger.exception("Pull synchrone échoué")
                return Response(
                    {"model": name, "status": "error", "error": str(pull_exc)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )


class OllamaPullStatusView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        state = get_progress(task_id)
        if state is None:
            return Response(
                {"task_id": task_id, "status": "unknown"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(state)
