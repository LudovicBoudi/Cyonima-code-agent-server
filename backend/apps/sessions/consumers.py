import asyncio
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings

from .models import Session

logger = logging.getLogger(__name__)


@sync_to_async
def _load_session(session_id):
    try:
        return Session.objects.select_related("workspace__organization").get(id=session_id)
    except Session.DoesNotExist:
        return None


class SessionConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket d'une session d'agent : reçoit `send`/`cancel`/`permission_response`,
    émet les événements de streaming (token, thinking, tool_call, tool_result, done)."""

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.session = await _load_session(self.session_id)
        if self.session is None or str(self.session.user_id) != str(self.user.id):
            await self.close(code=4403)
            return

        self.cancel_event = asyncio.Event()
        self.pending = {}  # call_id -> asyncio.Future
        self.task = None
        await self.accept()

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")
        if msg_type == "send":
            await self._handle_send(content)
        elif msg_type == "cancel":
            self.cancel_event.set()
            for fut in self.pending.values():
                if not fut.done():
                    fut.set_result(False)
        elif msg_type == "permission_response":
            fut = self.pending.pop(content.get("call_id"), None)
            if fut and not fut.done():
                fut.set_result(bool(content.get("approved", False)))

    async def _handle_send(self, content):
        if self.task and not self.task.done():
            await self.send_json({"type": "error", "error": "Génération déjà en cours"})
            return

        message = content.get("message", "").strip()
        if not message:
            await self.send_json({"type": "error", "error": "Message vide"})
            return

        model = content.get("model") or self.session.model or settings.OLLAMA_DEFAULT_MODEL
        reasoning = content.get("reasoning", "auto")
        self.session.model = model
        self.session.reasoning = reasoning
        await sync_to_async(self.session.save)(update_fields=["model", "reasoning"])

        self.cancel_event = asyncio.Event()
        self.task = asyncio.create_task(self._run(model, reasoning, message))

    async def _run(self, model, reasoning, message):
        from apps.agents.loop import run_agent

        async def emit(event):
            event["session_id"] = self.session_id
            await self.send_json(event)

        async def approve(request):
            fut = asyncio.get_running_loop().create_future()
            self.pending[request["call_id"]] = fut
            try:
                return await asyncio.wait_for(fut, timeout=600)
            except asyncio.TimeoutError:
                return False

        try:
            await run_agent(
                self.session_id, message, model, reasoning, emit, approve, self.cancel_event
            )
        except Exception as exc:
            logger.exception("Erreur agent dans la session %s", self.session_id)
            await self.send_json({"type": "error", "error": str(exc)})
            await self.send_json({"type": "done", "usage": {}})

    async def disconnect(self, close_code):
        if self.task and not self.task.done():
            self.cancel_event.set()
