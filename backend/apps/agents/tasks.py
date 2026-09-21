"""Tâche Celery d'exécution d'un agent, avec reprise après crash.

- `acks_late` + `reject_on_worker_lost` : si le worker meurt en cours de
  génération, le message est redélivré à un autre worker.
- Idempotence de reprise : le message utilisateur est créé une seule fois
  (`run_id`), et la boucle tronque les messages partiels du run interrompu.
- Le verrou Redis est à valeur (`run_id`) : en redélivraison, on ré-acquiert
  le verrou laissé par le worker mort ; on n'écrase jamais un run concurrent.
"""
import asyncio
import logging

from celery import shared_task
from channels.layers import get_channel_layer

from . import orchestrator
from .loop import make_cancel_check, run_agent
from .services import get_or_create_user_message

logger = logging.getLogger(__name__)


async def _emit(session_id: str, event: dict) -> None:
    event["session_id"] = session_id
    channel_layer = get_channel_layer()
    await channel_layer.group_send(
        f"session_{session_id}", {"type": "session.event", "event": event}
    )


@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    ignore_result=True,
)
def run_agent_task(self, session_id: str, run_id: str, message: str, model: str, reasoning: str):
    # 1. Message utilisateur idempotent (créé une seule fois par run)
    user_msg, _created = get_or_create_user_message(session_id, run_id, message)

    # 2. Verrou d'exécution (à valeur)
    if not orchestrator.acquire_run(session_id, run_id):
        if orchestrator.get_run_value(session_id) != run_id:
            logger.info("Session %s déjà en cours, run ignoré", session_id)
            return {"status": "busy"}
        orchestrator.force_acquire_run(session_id, run_id)  # redélivraison

    async def emit(event):
        await _emit(session_id, event)

    cancel_check = make_cancel_check(session_id)

    try:
        asyncio.run(
            run_agent(session_id, str(user_msg.id), model, reasoning, emit, cancel_check)
        )
    except Exception as exc:
        logger.exception("Erreur agent dans la session %s", session_id)
        asyncio.run(_emit(session_id, {"type": "error", "error": str(exc)}))
        asyncio.run(_emit(session_id, {"type": "done", "usage": {}}))
    finally:
        orchestrator.release_run(session_id, run_id)

    return {"status": "done"}
