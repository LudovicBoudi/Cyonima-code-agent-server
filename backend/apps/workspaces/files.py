"""Opérations fichiers sur le workspace (bind-mount hôte), avec sandboxing des chemins."""
import os

from .sandbox import ensure_workspace_dir


def resolve_workspace_path(workspace, rel_path):
    """Résout un chemin relatif dans le workspace, en refusant toute évasion."""
    host_root = ensure_workspace_dir(workspace)
    rel_path = (rel_path or "").lstrip("/")
    full = os.path.realpath(os.path.join(host_root, rel_path))
    root = os.path.realpath(host_root)
    if full != root and not full.startswith(root + os.sep):
        raise PermissionError(f"Chemin hors du workspace: {rel_path}")
    return full


def list_dir(workspace, rel_path=""):
    full = resolve_workspace_path(workspace, rel_path)
    if not os.path.isdir(full):
        raise NotADirectoryError(rel_path)
    entries = []
    for name in sorted(os.listdir(full)):
        p = os.path.join(full, name)
        entries.append(
            {
                "name": name,
                "path": os.path.relpath(p, ensure_workspace_dir(workspace)),
                "is_dir": os.path.isdir(p),
                "size": os.path.getsize(p) if os.path.isfile(p) else None,
            }
        )
    return entries


def read_file(workspace, rel_path):
    full = resolve_workspace_path(workspace, rel_path)
    if not os.path.isfile(full):
        raise FileNotFoundError(rel_path)
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_file(workspace, rel_path, content):
    full = resolve_workspace_path(workspace, rel_path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return full


def git_status(workspace):
    from .sandbox import DockerUnavailable, exec_command

    try:
        code, out, _ = exec_command(workspace, "git status --porcelain", timeout=15)
    except DockerUnavailable:
        # Fallback dev : git sur l'hôte (le bind-mount est partagé)
        import subprocess

        ensure_workspace_dir(workspace)
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace.host_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
        code, out = r.returncode, r.stdout
    if code != 0:
        return {"is_repo": False, "changes": []}
    changes = []
    for line in out.splitlines():
        if not line.strip():
            continue
        changes.append({"status": line[:2].strip(), "path": line[3:]})
    return {"is_repo": True, "changes": changes}


def is_within_roots(path, roots):
    """True si `path` (resolu) est == à une racine ou dessous."""
    return any(
        path == root or (path + os.sep).startswith(root.rstrip(os.sep) + os.sep)
        for root in roots
    )


def list_local_dirs(path=""):
    """Liste les sous-dossiers d'un répertoire serveur autorisé (WORKSPACE_LOCAL_ROOTS).

    Permet à l'utilisateur de choisir un dossier de travail local "comme le client
    original", sans exposer tout le système de fichiers.
    """
    from django.conf import settings as s

    roots = [
        os.path.realpath(os.path.expanduser(r))
        for r in s.WORKSPACE_LOCAL_ROOTS
        if r.strip()
    ]
    if not roots:
        raise PermissionError("Choix d'un dossier local désactivé (WORKSPACE_LOCAL_ROOTS vide).")

    base = os.path.realpath(os.path.expanduser(path or roots[0]))
    if not is_within_roots(base, roots):
        raise PermissionError(f"Chemin hors des racines autorisées: {path}")
    if not os.path.isdir(base):
        raise NotADirectoryError(path)

    dirs = []
    for name in sorted(os.listdir(base)):
        full = os.path.join(base, name)
        if os.path.isdir(full) and not os.path.islink(full):
            dirs.append({"name": name, "path": full})

    parent = os.path.dirname(base)
    if is_within_roots(parent, roots) and parent != base:
        parent_path = parent
    else:
        parent_path = None

    return {
        "path": base,
        "parent": parent_path,
        "roots": roots,
        "dirs": dirs,
    }
