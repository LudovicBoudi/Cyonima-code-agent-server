from rest_framework import serializers

from apps.agents.models import PermissionRequest

from .models import Message, Session


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            "id",
            "role",
            "content",
            "tool_calls",
            "tool_call_id",
            "meta",
            "created_at",
        ]
        read_only_fields = ["id", "role", "content", "tool_calls", "tool_call_id", "meta", "created_at"]


class SessionSerializer(serializers.ModelSerializer):
    workspace_name = serializers.CharField(source="workspace.name", read_only=True)

    class Meta:
        model = Session
        fields = [
            "id",
            "workspace",
            "workspace_name",
            "title",
            "model",
            "reasoning",
            "provider",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace_name", "created_at", "updated_at"]


class PermissionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionRequest
        fields = ["id", "call_id", "tool", "arguments", "preview", "status", "created_at"]
        read_only_fields = ["id", "call_id", "tool", "arguments", "preview", "status", "created_at"]
