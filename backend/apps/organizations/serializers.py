from rest_framework import serializers

from .models import Membership, Organization, Team, TeamMembership


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "role", "created_at"]
        read_only_fields = ["id", "role", "created_at"]

    def get_role(self, obj):
        user = self.context["request"].user
        m = obj.memberships.filter(user=user).first()
        return m.role if m else None

    def create(self, validated_data):
        user = self.context["request"].user
        org = Organization.objects.create(**validated_data, created_by=user)
        Membership.objects.create(
            organization=org, user=user, role=Membership.Role.OWNER
        )
        return org


class MembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True, required=False)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user", "email", "role", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def create(self, validated_data):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        email = validated_data.pop("email", None)
        org = self.context["organization"]
        if email:
            user = User.objects.get(email=email)
        else:
            user = self.context["request"].user
        membership = Membership.objects.create(
            organization=org, user=user, **validated_data
        )
        return membership


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        org = self.context["organization"]
        return Team.objects.create(organization=org, **validated_data)


class TeamMembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True, required=False)
    user = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = TeamMembership
        fields = ["id", "user", "email", "role", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def create(self, validated_data):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        email = validated_data.pop("email", None)
        team = self.context["team"]
        if email:
            user = User.objects.get(email=email)
        else:
            user = self.context["request"].user
        return TeamMembership.objects.create(team=team, user=user, **validated_data)
