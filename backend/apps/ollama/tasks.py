"""Tâches Celery — pull de modèles Ollama avec suivi de progression.

Le pull stream les lignes NDJSON de `POST /api/pull` et agrège la progression
par couche (digest) pour exposer un pourcentage global.
"""
import asyncio
import logging

from celery import shared_task

from .client import OllamaClient
from .progress import set_progress

logger = logging.getLogger(__name__)


def _aggregate(layers: dict) -> tuple[int, int, int]:
    """Retourne (percent, completed, total) agrégés sur toutes les couches."""
    total = sum(layer.get("total", 0) for layer in layers.values())
    completed = sum(layer.get("completed", 0) for layer in layers.values())
    percent = int(completed * 100 / total) if total else 0
    return percent, completed, total


@shared_task(bind=True)
def pull_model_task(self, model_name: str) -> dict:
    client = OllamaClient()
    state: dict = {
        "task_id": self.request.id,
        "model": model_name,
        "status": "pulling",
        "message": "initialisation",
        "percent": 0,
        "completed": 0,
        "total": 0,
    }
    layers: dict = {}

    async def on_progress(data: dict) -> None:
        status = data.get("status", "")
        if status == "downloading":
            digest = data.get("digest", "layer")
            layers[digest] = {
                "total": data.get("total", 0),
                "completed": data.get("completed", 0),
            }
        percent, completed, total = _aggregate(layers)
        state.update(
            {
                "status": "pulling",
                "message": status,
                "percent": percent,
                "completed": completed,
                "total": total,
            }
        )
        set_progress(self.request.id, state)

    set_progress(self.request.id, state)
    try:
        ok = asyncio.run(client.pull(model_name, on_progress=on_progress))
        state["status"] = "success" if ok else "error"
        state["message"] = "terminé" if ok else "échec"
    except Exception as exc:
        logger.exception("Pull échoué pour %s", model_name)
        state["status"] = "error"
        state["message"] = str(exc)[:200]
    set_progress(self.request.id, state)
    return state
