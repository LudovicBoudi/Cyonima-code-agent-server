from rest_framework import serializers

from . import sandbox
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
