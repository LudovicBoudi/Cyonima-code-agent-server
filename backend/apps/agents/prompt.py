"""Construction du system prompt : snapshot workspace + AGENTS.md + consignes agent."""
import os

from apps.workspaces import files

IGNORE_DIRS = {".git", "target", "node_modules", "dist", "build", ".venv", "__pycache__"}
KEY_FILES = [
    "AGENTS.md",
    "README.md",
    "package.json",
    "Cargo.toml",
    "pyproject.toml",
    "requirements.txt",
    "go.mod",
    "Makefile",
    "docker-compose.yml",
    "Dockerfile",
]

AGENT_INSTRUCTIONS = """Tu es un agent de code autonome qui travaille dans le workspace de l'utilisateur.
Tu peux lire, écrire et modifier des fichiers, et exécuter des commandes shell via les outils.
- Agis de manière autonome : utilise les outils nécessaires pour accomplir la tâche.
- Les outils de lecture/écriture de fichiers sont auto-approuvés.
- Les commandes bash nécessitent une approbation utilisateur.
- Sois concis. Documente les choix non évidents brièvement.
"""


def _tree(host_path, depth=2, root_label="workspace"):
    lines = []
    lines.append(f"{root_label}/")

    def walk(d, pfx, level):
        if level > depth:
            return
        try:
            entries = sorted(os.listdir(d))
        except OSError:
            return
        for name in entries:
            if name in IGNORE_DIRS or name.startswith("."):
                continue
            full = os.path.join(d, name)
            if os.path.isdir(full):
                lines.append(f"{pfx}{name}/")
                walk(full, pfx + "  ", level + 1)
            else:
                lines.append(f"{pfx}{name}")

    walk(host_path, "  ", 1)
    return "\n".join(lines[:400])


def _key_files(host_path):
    parts = []
    for name in KEY_FILES:
        full = os.path.join(host_path, name)
        if os.path.isfile(full):
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(4000)
            except OSError:
                continue
            parts.append(f"### {name}\n```\n{content}\n```")
    return "\n\n".join(parts)


def build_system_prompt(workspace):
    host_path = files.ensure_workspace_dir(workspace)
    snapshot = _tree(host_path, root_label=workspace.name)
    key_files = _key_files(host_path)
    agents_md = ""
    agents_path = os.path.join(host_path, "AGENTS.md")
    if os.path.isfile(agents_path):
        try:
            with open(agents_path, "r", encoding="utf-8", errors="ignore") as f:
                agents_md = f.read()
        except OSError:
            agents_md = ""

    parts = [AGENT_INSTRUCTIONS]
    if agents_md:
        parts.append("## Instructions du projet (AGENTS.md)\n" + agents_md)
    parts.append("## Structure du workspace\n" + snapshot)
    if key_files:
        parts.append("## Fichiers de configuration clés\n" + key_files)
    return "\n\n".join(parts)
