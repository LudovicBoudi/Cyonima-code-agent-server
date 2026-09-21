from django.db import models

from apps.common.models import BaseModel


class PermissionRequest(BaseModel):
    """Demande d'approbation d'un outil (ex. `bash`), persistée pour survivre
    à la déconnexion/reconnexion WebSocket."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvé"
        DENIED = "denied", "Refusé"
        EXPIRED = "expired", "Expiré"

    session = models.ForeignKey(
        "agent_sessions.Session",
        on_delete=models.CASCADE,
        related_name="permission_requests",
    )
    call_id = models.CharField(max_length=64, db_index=True)
    tool = models.CharField(max_length=64)
    arguments = models.JSONField(default=dict, blank=True)
    preview = models.CharField(max_length=512, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.tool} [{self.status}] ({self.session_id})"
