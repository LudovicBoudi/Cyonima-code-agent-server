import logging

from asgiref.sync import async_to_sync
from django.conf import settings
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .client import OllamaClient

logger = logging.getLogger(__name__)


class OllamaModelsView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        models = async_to_sync(OllamaClient().list_models)()
        return Response({"models": models, "default_model": settings.OLLAMA_DEFAULT_MODEL})


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
    permission_classes = [IsAuthenticated]

    def post(self, request, name):
        client = OllamaClient()
        progress = []

        def _on_progress(data):
            progress.append(data)

        ok = async_to_sync(client.pull)(name, on_progress=_on_progress)
        if not ok:
            return Response({"error": "Pull échoué"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"pulled": name, "status": "success"})
