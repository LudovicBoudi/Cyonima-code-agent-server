"""Orchestration multi-workers via Redis.

L'état d'exécution des agents (session en cours, annulation) est partagé entre
les workers via Redis, ce qui permet à plusieurs processus (daphne/uvicorn) de
coopérer :

  - `agent:run:<session_id>`     — verrou d'exécution (SET NX + TTL),
  - `agent:cancel:<session_id>`  — drapeau d'annulation (pollé par la boucle).

En cas d'indisponibilité de Redis (dev mono-process), les fonctions se dégradent
proprement et le `SessionManager` retombe sur son état en mémoire.
"""
import logging

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

RUN_TTL = 3600  # durée max d'une génération (auto-libération en cas de crash)
CANCEL_TTL = 300

_client = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def _run_key(session_id: str) -> str:
    return f"agent:run:{session_id}"


def _cancel_key(session_id: str) -> str:
    return f"agent:cancel:{session_id}"


def acquire_run(session_id: str, value: str) -> bool:
    """Tente d'acquérir le verrou d'exécution avec la valeur `value` (SET NX)."""
    try:
        return bool(_redis().set(_run_key(session_id), value, nx=True, ex=RUN_TTL))
    except Exception as exc:
        logger.warning("Redis indisponible (acquire_run): %s", exc)
        return True  # dégradé : mono-process, on laisse passer


def get_run_value(session_id: str) -> str | None:
    try:
        return _redis().get(_run_key(session_id))
    except Exception as exc:
        logger.warning("Redis indisponible (get_run_value): %s", exc)
        return None


def force_acquire_run(session_id: str, value: str) -> None:
    """Ré-acquiert le verrou (redélivraison après crash du worker)."""
    try:
        _redis().set(_run_key(session_id), value, ex=RUN_TTL)
    except Exception as exc:
        logger.warning("Redis indisponible (force_acquire_run): %s", exc)


def release_run(session_id: str, value: str) -> None:
    """Libère le verrou uniquement s'il est encore détenu par `value`."""
    try:
        r = _redis()
        if r.get(_run_key(session_id)) == value:
            r.delete(_run_key(session_id))
    except Exception as exc:
        logger.warning("Redis indisponible (release_run): %s", exc)


def is_running(session_id: str) -> bool:
    try:
        return bool(_redis().exists(_run_key(session_id)))
    except Exception as exc:
        logger.warning("Redis indisponible (is_running): %s", exc)
        return False


def request_cancel(session_id: str) -> None:
    try:
        _redis().set(_cancel_key(session_id), "1", ex=CANCEL_TTL)
    except Exception as exc:
        logger.warning("Redis indisponible (request_cancel): %s", exc)


def is_cancelled(session_id: str) -> bool:
    try:
        return bool(_redis().exists(_cancel_key(session_id)))
    except Exception as exc:
        logger.warning("Redis indisponible (is_cancelled): %s", exc)
        return False
