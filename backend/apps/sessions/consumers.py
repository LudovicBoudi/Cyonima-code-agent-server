import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from apps.agents.manager import get_manager
from apps.agents.services import respond

from .models import Session

logger = logging.getLogger(__name__)


@sync_to_async
def _load_session(session_id):
    try:
        return Session.objects.select_related("workspace__organization").get(id=session_id)
    except Session.DoesNotExist:
        return None


class SessionConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket d'une session d'agent.

    Rejoint le groupe `session_<id>` pour recevoir les événements de la boucle
    agent (qui tourne dans le SessionManager, indépendamment de cette connexion)
    et transmet les commandes `send`/`cancel`/`permission_response`.
    """

    async def connect(self):
        self.session_id = str(self.scope["url_route"]["kwargs"]["session_id"])
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.session = await _load_session(self.session_id)
        if self.session is None or str(self.session.user_id) != str(self.user.id):
            await self.close(code=4403)
            return

        self.group_name = f"session_{self.session_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")
        if msg_type == "send":
            await self._handle_send(content)
        elif msg_type == "cancel":
            get_manager().cancel(self.session_id)
        elif msg_type == "permission_response":
            call_id = content.get("call_id")
            approved = bool(content.get("approved", False))
            if call_id:
                await sync_to_async(respond)(self.session_id, call_id, approved)

    async def _handle_send(self, content):
        message = content.get("message", "").strip()
        if not message:
            await self.send_json({"type": "error", "error": "Message vide"})
            return

        model = content.get("model") or self.session.model or settings.OLLAMA_DEFAULT_MODEL

        from apps.ollama.client import OllamaClient

        try:
            model = await OllamaClient().resolve_model(model)
        except Exception as exc:
            logger.warning("Résolution du modèle impossible: %s", exc)
        if not model:
            await self.send_json(
                {"type": "error", "error": "Aucun modèle Ollama disponible."}
            )
            return

        reasoning = content.get("reasoning", "auto")
        self.session.model = model
        self.session.reasoning = reasoning
        await sync_to_async(self.session.save)(update_fields=["model", "reasoning"])

        started = get_manager().send(self.session_id, model, reasoning, message)
        if not started:
            await self.send_json(
                {"type": "error", "error": "Génération déjà en cours"}
            )

    async def session_event(self, event):
        await self.send_json(event["event"])

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
