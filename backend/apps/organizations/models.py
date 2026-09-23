from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class Organization(BaseModel):
    """Organisation (tenant) regroupant équipes, workspaces et utilisateurs."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_organizations",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Organisation"
        verbose_name_plural = "Organisations"

    def __str__(self):
        return self.name


class Membership(BaseModel):
    """Appartenance d'un utilisateur à une organisation, avec un rôle."""

    class Role(models.TextChoices):
        OWNER = "owner", "Propriétaire"
        ADMIN = "admin", "Administrateur"
        MEMBER = "member", "Membre"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "user"], name="unique_org_membership"
            )
        ]
        verbose_name = "Membre"
        verbose_name_plural = "Membres"

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"


class Team(BaseModel):
    """Équipe au sein d'une organisation."""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="teams"
    )
    name = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_org_team")
        ]
        verbose_name = "Équipe"
        verbose_name_plural = "Équipes"

    def __str__(self):
        return f"{self.organization} / {self.name}"


class TeamMembership(BaseModel):
    """Appartenance d'un utilisateur (ou d'une équipe) à une équipe."""

    class Role(models.TextChoices):
        LEAD = "lead", "Responsable"
        MEMBER = "member", "Membre"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "user"], name="unique_team_membership")
        ]
        verbose_name = "Membre d'équipe"
        verbose_name_plural = "Membres d'équipe"

    def __str__(self):
        return f"{self.user} @ {self.team} ({self.role})"
