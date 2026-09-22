import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.organizations.models import Membership, Organization
from apps.sessions.models import Session
from apps.workspaces.models import Workspace

User = get_user_model()


@pytest.fixture(autouse=True)
def _no_docker(monkeypatch):
    """Rend les tests hermétiques vis-à-vis de Docker (dispo ou non sur le runner).

    Force le mode « dégradé » de la sandbox : les outils fichiers fonctionnent,
    `bash`/`exec_command` lèvent `DockerUnavailable`.
    """
    from apps.workspaces import sandbox

    monkeypatch.setattr(sandbox, "docker_available", lambda: False)


@pytest.fixture
def user(db):
    return User.objects.create_user(email="user@test.dev", password="pass12345")


@pytest.fixture
def user2(db):
    return User.objects.create_user(email="user2@test.dev", password="pass12345")


@pytest.fixture
def org(db, user):
    o = Organization.objects.create(name="Acme", slug="acme", created_by=user)
    Membership.objects.create(organization=o, user=user, role=Membership.Role.OWNER)
    return o


@pytest.fixture
def workspace(db, org, user, tmp_path, settings):
    settings.SANDBOX_VOLUME_ROOT = str(tmp_path / "sandbox")
    return Workspace.objects.create(
        organization=org,
        name="proj",
        slug="proj",
        created_by=user,
        status=Workspace.Status.READY,
    )


@pytest.fixture
def session(db, workspace, user):
    return Session.objects.create(workspace=workspace, user=user)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client
