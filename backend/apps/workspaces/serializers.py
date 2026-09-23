from rest_framework import serializers

from . import files, sandbox
from .models import Workspace


class WorkspaceSerializer(serializers.ModelSerializer):
    container_status = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "id",
            "organization",
            "team",
            "name",
            "slug",
            "description",
            "git_url",
            "local_path",
            "allow_network",
            "status",
            "container_status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "status",
            "container_status",
            "created_at",
        ]

    def get_container_status(self, obj):
        return sandbox.container_status(obj)

    def validate_local_path(self, value):
        import os

        from django.conf import settings

        if not value:
            return value
        path = os.path.realpath(os.path.expanduser(value))
        if not os.path.isdir(path):
            raise serializers.ValidationError(
                "Le dossier local n'existe pas ou n'est pas un dossier."
            )
        roots = [
            os.path.realpath(os.path.expanduser(r))
            for r in settings.WORKSPACE_LOCAL_ROOTS
            if r.strip()
        ]
        if roots and not files.is_within_roots(path, roots):
            raise serializers.ValidationError(
                "Le dossier local doit se trouver sous une racine autorisée."
            )
        return value

    def create(self, validated_data):
        org = self.context["organization"]
        validated_data["organization"] = org
        validated_data["created_by"] = self.context["request"].user
        validated_data["status"] = Workspace.Status.CREATING
        workspace = Workspace.objects.create(**validated_data)

        from .tasks import provision_workspace_task

        try:
            provision_workspace_task.delay(str(workspace.id))
        except Exception:
            # Fallback synchrone (dev sans broker/worker)
            from .services import provision_workspace

            provision_workspace(workspace)
        return workspace
