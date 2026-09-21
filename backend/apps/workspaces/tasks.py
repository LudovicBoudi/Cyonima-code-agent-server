"""Tâches Celery — provisioning des workspaces (clone + sandbox Docker).

Le provisioning est long (clone git, démarrage de conteneur) : il est donc
exécuté hors du cycle requête/réponse. Le statut du workspace (`creating` →
`ready`/`error`) est suivi par le frontend en polling.
"""
import logging

from celery import shared_task

from .models import Workspace

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def provision_workspace_task(self, workspace_id: str) -> dict:
    from .services import provision_workspace

    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        return {"workspace_id": workspace_id, "status": "error", "error": "workspace introuvable"}

    try:
        provision_workspace(workspace)
    except Exception as exc:
        logger.exception("Provision échouée pour %s", workspace_id)
        workspace.status = Workspace.Status.ERROR
        workspace.save(update_fields=["status"])
        return {"workspace_id": workspace_id, "status": "error", "error": str(exc)[:200]}

    return {"workspace_id": workspace_id, "status": workspace.status}


@shared_task(bind=True)
def destroy_workspace_task(self, workspace_id: str) -> dict:
    from .services import destroy_workspace

    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        return {"workspace_id": workspace_id, "status": "error", "error": "workspace introuvable"}

    destroy_workspace(workspace)
    workspace.delete()
    return {"workspace_id": workspace_id, "status": "deleted"}
