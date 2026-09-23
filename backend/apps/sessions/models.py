from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from apps.workspaces.models import Workspace


class Session(BaseModel):
    """Session d'agent : une conversation isolée sur un répertoire de travail."""

    class Provider(models.TextChoices):
        OLLAMA = "ollama", "Ollama"

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="sessions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions"
    )
    title = models.CharField(max_length=255, blank=True)
    provider = models.CharField(
        max_length=16, choices=Provider.choices, default=Provider.OLLAMA
    )
    model = models.CharField(max_length=255, blank=True)
    reasoning = models.CharField(max_length=16, default="auto")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Session"
        verbose_name_plural = "Sessions"

    def __str__(self):
        return f"{self.title or self.id} ({self.workspace})"


class Message(BaseModel):
    """Message d'une conversation."""

    class Role(models.TextChoices):
        SYSTEM = "system", "Système"
        USER = "user", "Utilisateur"
        ASSISTANT = "assistant", "Assistant"
        TOOL = "tool", "Outil"

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(blank=True)
    tool_calls = models.JSONField(default=list, blank=True)
    tool_call_id = models.CharField(max_length=128, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    run_id = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Message"
        verbose_name_plural = "Messages"

    def __str__(self):
        return f"{self.role}: {self.content[:40]}"
