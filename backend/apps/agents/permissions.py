"""Politique de permissions par outil (auto / ask / deny).

Défauts prudents : lecture/écriture de fichiers auto-approuvées, `bash` demande
une approbation (comme l'app desktop v1.1+).
"""
from dataclasses import dataclass


@dataclass
class Policy:
    auto: set
    ask: set
    deny: set = None

    def __post_init__(self):
        self.deny = self.deny or set()

    def decision(self, tool: str) -> str:
        if tool in self.deny:
            return "deny"
        if tool in self.ask:
            return "ask"
        if tool in self.auto:
            return "auto"
        return "ask"  # défaut prudent


DEFAULT_POLICY = Policy(
    auto={"read_file", "write_file", "edit_file", "glob", "grep"},
    ask={"bash"},
)


def preview_arguments(tool: str, args: dict) -> str:
    """Aperçu lisible des arguments pour le dialogue d'approbation."""
    if tool == "bash":
        return f"$ {args.get('command', '')}"
    if "path" in args:
        return f"→ {args.get('path', '')}"
    return str(args)[:200]
