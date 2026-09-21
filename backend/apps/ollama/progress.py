"""Stockage de la progression des pulls Ollama dans Redis.

Clé : `ollama:pull:<task_id>`. La progression est lue par l'API de statut
(`GET /api/ollama/pulls/<task_id>/`) et consommée par le frontend en polling.
"""
import json
import logging

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


def _conn() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _key(task_id: str) -> str:
    return f"ollama:pull:{task_id}"


def set_progress(task_id: str, state: dict) -> None:
    try:
        _conn().set(_key(task_id), json.dumps(state), ex=86400)
    except Exception as exc:  # Redis indisponible : le pull continue sans suivi
        logger.warning("Impossible d'écrire la progression (%s)", exc)


def get_progress(task_id: str) -> dict | None:
    try:
        raw = _conn().get(_key(task_id))
    except Exception as exc:
        logger.warning("Impossible de lire la progression (%s)", exc)
        return None
    return json.loads(raw) if raw else None
