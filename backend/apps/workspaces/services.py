import logging

from . import sandbox

logger = logging.getLogger(__name__)


def provision_workspace(workspace):
    """Provisionne un workspace : crée le répertoire, clone le dépôt si besoin,
    démarre le conteneur sandbox."""
    from .models import Workspace

    try:
        host_path = sandbox.ensure_workspace_dir(workspace)
        if workspace.git_url:
            clone(host_path, workspace.git_url)
        sandbox.start_container(workspace)
        workspace.status = Workspace.Status.READY
        workspace.save(update_fields=["status"])
    except Exception:
        logger.exception("Provision échouée pour %s", workspace)
        workspace.status = Workspace.Status.ERROR
        workspace.save(update_fields=["status"])
        raise


def clone(host_path, git_url):
    import subprocess

    subprocess.run(
        ["git", "clone", "--depth", "1", git_url, host_path],
        check=True,
        timeout=600,
    )


def destroy_workspace(workspace):
    sandbox.remove_container(workspace)
    import shutil

    shutil.rmtree(workspace.host_path, ignore_errors=True)
