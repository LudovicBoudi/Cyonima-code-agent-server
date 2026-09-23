"""Politique de permissions par outil (auto / ask / deny).

Règle clé : lire/écrire des fichiers DANS le répertoire de travail est
auto-approuvé. Tout chemin hors du workspace (absolu, ex. `/tmp`) déclenche une
approbation. `bash` demande toujours une approbation (comme l'app desktop v1.1+).
"""
from dataclasses import dataclass


def is_external_path(args) -> bool:
    """Un chemin est « hors workspace » lorsqu'il est absolu."""
    path = (args or {}).get("path")
    return isinstance(path, str) and path.startswith("/")


@dataclass
class Policy:
    auto: set
    ask: set
    path_auto: set = None
    deny: set = None

    def __post_init__(self):
        self.path_auto = self.path_auto or set()
        self.deny = self.deny or set()

    def decision(self, tool: str, args: dict | None = None) -> str:
        if tool in self.deny:
            return "deny"
        if tool in self.ask:
            return "ask"
        if tool in self.path_auto:
            return "ask" if is_external_path(args) else "auto"
        if tool in self.auto:
            return "auto"
        return "ask"  # défaut prudent


# Outils fichiers : auto dans le workspace, ask dès qu'on en sort.
DEFAULT_POLICY = Policy(
    auto={"glob", "grep"},
    path_auto={"read_file", "write_file", "edit_file"},
    ask={"bash"},
)


def preview_arguments(tool: str, args: dict) -> str:
    """Aperçu lisible des arguments pour le dialogue d'approbation."""
    if tool == "bash":
        return f"$ {args.get('command', '')}"
    if "path" in args:
        outside = " (hors workspace)" if is_external_path(args) else ""
        return f"→ {args.get('path', '')}{outside}"
    return str(args)[:200]