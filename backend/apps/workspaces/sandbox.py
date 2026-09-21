"""Gestion du cycle de vie des conteneurs sandbox (via docker SDK).

Un workspace = un conteneur jetable. Le répertoire de travail est un bind-mount
hôte -> /workspace dans le conteneur, ce qui permet :
  - les opérations fichiers (lecture/écriture) directement sur l'hôte (rapide),
  - l'exécution des commandes (bash/git/build) à l'intérieur du conteneur (isolé).
"""
import logging
import os

import docker

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


class DockerUnavailable(RuntimeError):
    """Le daemon Docker n'est pas joignable (démarrage ou exécution impossible)."""


def docker_available() -> bool:
    try:
        return get_client().ping()
    except Exception:
        return False


def ensure_workspace_dir(workspace):
    path = workspace.host_path
    os.makedirs(path, exist_ok=True)
    return path


def start_container(workspace):
    """Démarre (ou réutilise) le conteneur sandbox du workspace.

    Retourne l'id du conteneur, ou None si Docker est indisponible (dégradé :
    les outils fichiers fonctionnent sur le bind-mount hôte, `bash` échouera).
    """
    if not docker_available():
        logger.warning("Docker indisponible — sandbox dégradée pour %s", workspace.id)
        return None

    client = get_client()
    image = workspace.container_image or settings_sandbox_image()
    host_path = ensure_workspace_dir(workspace)

    container_id = workspace.container_id
    if container_id:
        try:
            container = client.containers.get(container_id)
            if container.status == "running":
                return container_id
            container.start()
            return container_id
        except Exception:
            logger.warning("Conteneur %s introuvable, recréation", container_id)

    container = client.containers.run(
        image,
        command="sleep infinity",
        detach=True,
        working_dir="/workspace",
        volumes={host_path: {"bind": "/workspace", "mode": "rw"}},
        network_mode="bridge",
        labels={"cyonima.workspace": str(workspace.id)},
        remove=False,
    )
    workspace.container_id = container.id
    workspace.container_image = image
    workspace.save(update_fields=["container_id", "container_image"])
    return container.id


def stop_container(workspace):
    client = get_client()
    if not workspace.container_id:
        return
    try:
        client.containers.get(workspace.container_id).stop(timeout=5)
    except Exception as exc:
        logger.warning("Stop conteneur impossible: %s", exc)


def remove_container(workspace):
    client = get_client()
    if not workspace.container_id:
        return
    try:
        client.containers.get(workspace.container_id).remove(force=True)
    except Exception as exc:
        logger.warning("Remove conteneur impossible: %s", exc)
    workspace.container_id = ""
    workspace.save(update_fields=["container_id"])


def exec_command(workspace, command, timeout=30):
    """Exécute une commande dans le conteneur. Retourne (exit_code, stdout, stderr)."""
    container_id = start_container(workspace)
    if not container_id:
        raise DockerUnavailable("Docker indisponible — commande bash impossible.")
    client = get_client()
    container = client.containers.get(container_id)
    exit_code, output = container.exec_run(
        ["/bin/sh", "-c", command], demux=True, timeout=timeout
    )
    stdout = output[0].decode("utf-8", errors="replace") if output[0] else ""
    stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
    return exit_code, stdout, stderr


def container_status(workspace):
    if not workspace.container_id:
        return "stopped"
    try:
        return get_client().containers.get(workspace.container_id).status
    except Exception:
        return "stopped"


def settings_sandbox_image():
    from django.conf import settings

    return settings.SANDBOX_IMAGE
