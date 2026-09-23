"""Outils de l'agent (mirroir de `tools/` du backend Rust).

- Les outils fichiers opèrent directement sur le bind-mount hôte (rapide).
- `bash` s'exécute dans le conteneur sandbox (isolation).
- Chaque outil expose un schéma JSON (function-calling Ollama) et une fonction
  `run(workspace, args)`.
"""
import glob as _glob_module
import os
import re

from apps.workspaces import files, sandbox


class Tool:
    def __init__(self, name, description, parameters, run):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.run = run

    def schema(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _read_file(workspace, args):
    path = files.resolve_tool_path(workspace, args["path"])
    return files.read_file_abs(path)


def _write_file(workspace, args):
    path = files.resolve_tool_path(workspace, args["path"])
    files.write_file_abs(path, args["content"])
    return f"Fichier écrit : {args['path']}"


def _edit_file(workspace, args):
    path = files.resolve_tool_path(workspace, args["path"])
    old = args["old_string"]
    new = args["new_string"]
    content = files.read_file_abs(path)
    if old not in content:
        raise ValueError("old_string introuvable dans le fichier")
    if content.count(old) != 1:
        raise ValueError("old_string présent plusieurs fois, remplacement ambigu")
    files.write_file_abs(path, content.replace(old, new))
    return f"Fichier modifié : {args['path']}"


def _glob(workspace, args):
    root = files.ensure_workspace_dir(workspace)
    pattern = args["pattern"].lstrip("/")
    matches = []
    for p in _glob_module.glob(os.path.join(root, "**", pattern), recursive=True):
        if os.path.isfile(p):
            matches.append(os.path.relpath(p, root))
    return "\n".join(matches[:500]) or "(aucun résultat)"


def _grep(workspace, args):
    root = files.ensure_workspace_dir(workspace)
    pattern = args["pattern"]
    regex = re.compile(pattern)
    results = []
    skip = {"node_modules", "target", "dist", ".git", "build", ".venv", "__pycache__"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            rel = os.path.relpath(full, root)
                            results.append(f"{rel}:{i}: {line.strip()[:200]}")
                            if len(results) >= 200:
                                return "\n".join(results)
            except OSError:
                continue
    return "\n".join(results) or "(aucun résultat)"


def _bash(workspace, args):
    code, out, err = sandbox.exec_command(workspace, args["command"])
    result = out
    if err:
        result += ("\n" + err) if out else err
    if code != 0:
        result += f"\n[exit code {code}]"
    return result or "(aucune sortie)"


TOOLS = [
    Tool(
        "read_file",
        "Lire le contenu d'un fichier du workspace.",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Chemin relatif"}},
            "required": ["path"],
        },
        _read_file,
    ),
    Tool(
        "write_file",
        "Créer ou écraser un fichier du workspace.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        _write_file,
    ),
    Tool(
        "edit_file",
        "Remplacer une occurrence exacte et unique dans un fichier.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
            },
            "required": ["path", "old_string", "new_string"],
        },
        _edit_file,
    ),
    Tool(
        "glob",
        "Rechercher des fichiers par motif glob (ex: **/*.py).",
        {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
        _glob,
    ),
    Tool(
        "grep",
        "Rechercher un motif regex dans les fichiers du workspace.",
        {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
        _grep,
    ),
    Tool(
        "bash",
        "Exécuter une commande shell dans le sandbox du workspace.",
        {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
        _bash,
    ),
]

TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def run_tool(name, workspace, args):
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return f"Outil inconnu: {name}", True
    try:
        result = tool.run(workspace, args)
        return result, False
    except Exception as exc:
        return f"Erreur: {exc}", True
