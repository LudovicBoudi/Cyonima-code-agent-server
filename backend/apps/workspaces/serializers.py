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
            "status",
            "container_status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "container_status", "created_at"]

    def get_container_status(self, obj):
        return sandbox.container_status(obj)

    def create(self, validated_data):
        org = self.context["organization"]
        validated_data["organization"] = org
        validated_data["created_by"] = self.context["request"].user
        workspace = Workspace.objects.create(**validated_data)

        from .services import provision_workspace

        provision_workspace(workspace)
        return workspace
