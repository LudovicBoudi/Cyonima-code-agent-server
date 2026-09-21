"""Gestionnaire de sessions d'agent — exécution déléguée à Celery.

En production, `send` délègue l'exécution à la tâche Celery `run_agent_task`
(file `agents` queue), ce qui découple l'agent des workers web/WS et permet la
reprise après crash (`acks_late`). Sans broker (dev), retombée sur une tâche
asyncio locale.

L'annulation et l'anti double-send passent par Redis (`orchestrator.py`),
partagés entre workers.
"""
import asyncio
import logging
import uuid

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer

from . import orchestrator
from .loop import make_cancel_check, run_agent
from .services import get_or_create_user_message
from .tasks import run_agent_task

logger = logging.getLogger(__name__)

_manager = None


def get_manager() -> "SessionManager":
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager


class SessionManager:
    def __init__(self):
        self._tasks: dict[str, dict] = {}

    def _local_running(self, session_id: str) -> bool:
        entry = self._tasks.get(session_id)
        return bool(entry and entry["task"] and not entry["task"].done())

    def is_running(self, session_id: str) -> bool:
        return self._local_running(session_id) or orchestrator.is_running(session_id)

    def send(self, session_id: str, model: str, reasoning: str, message: str) -> bool:
        if self._local_running(session_id) or orchestrator.is_running(session_id):
            return False

        run_id = str(uuid.uuid4())
        try:
            run_agent_task.delay(session_id, run_id, message, model, reasoning)
        except Exception as exc:
            logger.warning("Broker indisponible, exécution locale (%s)", exc)
            self._send_local(session_id, run_id, message, model, reasoning)
        return True

    def cancel(self, session_id: str) -> None:
        orchestrator.request_cancel(session_id)
        entry = self._tasks.get(session_id)
        if entry:
            entry["cancel"].set()

    # ------------------------------------------------------------------ local
    def _send_local(self, session_id, run_id, message, model, reasoning):
        cancel = asyncio.Event()

        async def emit(event):
            event["session_id"] = session_id
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f"session_{session_id}", {"type": "session.event", "event": event}
            )

        async def runner():
            try:
                user_msg, _ = await sync_to_async(get_or_create_user_message)(
                    session_id, run_id, message
                )
                cancel_check = make_cancel_check(session_id, cancel)
                await run_agent(
                    session_id, str(user_msg.id), model, reasoning, emit, cancel_check
                )
            except Exception as exc:
                logger.exception("Erreur agent (local) dans la session %s", session_id)
                await emit({"type": "error", "error": str(exc)})
                await emit({"type": "done", "usage": {}})

        task = asyncio.create_task(runner())
        self._tasks[session_id] = {"task": task, "cancel": cancel}
        task.add_done_callback(lambda _: self._cleanup(session_id))

    def _cleanup(self, session_id: str) -> None:
        entry = self._tasks.get(session_id)
        if entry and entry["task"].done():
            self._tasks.pop(session_id, None)
