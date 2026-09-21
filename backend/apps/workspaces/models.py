from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from apps.organizations.models import Organization, Team


class Workspace(BaseModel):
    """Espace de travail : un dépôt de code, exécuté dans un conteneur sandbox."""

    class Status(models.TextChoices):
        CREATING = "creating", "Création"
        READY = "ready", "Prêt"
        RUNNING = "running", "En cours"
        STOPPED = "stopped", "Arrêté"
        ERROR = "error", "Erreur"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="workspaces"
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workspaces",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    description = models.TextField(blank=True)
    git_url = models.URLField(blank=True)
    container_image = models.CharField(max_length=255, blank=True)
    container_id = models.CharField(max_length=128, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.CREATING
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="workspaces",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="unique_org_workspace"
            )
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.organization} / {self.name}"

    @property
    def host_path(self):
        """Chemin hôte du volume monté dans le conteneur."""
        from django.conf import settings as s

        return f"{s.SANDBOX_VOLUME_ROOT}/{self.organization_id}/{self.id}"
