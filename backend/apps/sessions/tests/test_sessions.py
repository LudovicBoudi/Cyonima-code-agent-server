import pytest

from apps.sessions.models import Message, Session
from apps.workspaces.models import Workspace


@pytest.mark.django_db
def test_create_session_with_name_and_local_path(auth_client, user, tmp_path, settings):
    settings.WORKSPACE_LOCAL_ROOTS = [str(tmp_path)]
    local_path = tmp_path / "mon-projet"
    local_path.mkdir()

    r = auth_client.post(
        "/api/sessions/",
        {"name": "Mon projet", "local_path": str(local_path)},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["title"] == "Mon projet"
    assert r.data["local_path"] == str(local_path.resolve())
    session = Session.objects.get(id=r.data["id"])
    assert session.user == user
    assert session.workspace.local_path == str(local_path.resolve())
    assert session.workspace.status == Workspace.Status.READY


@pytest.mark.django_db
def test_create_session_requires_name_and_path(auth_client, tmp_path, settings):
    settings.WORKSPACE_LOCAL_ROOTS = [str(tmp_path)]
    r = auth_client.post("/api/sessions/", {"name": ""}, format="json")
    assert r.status_code == 400


@pytest.mark.django_db
def test_create_session_rejects_path_outside_roots(auth_client, tmp_path, settings):
    settings.WORKSPACE_LOCAL_ROOTS = [str(tmp_path / "autorise")]
    outside = tmp_path / "hors-racines"
    outside.mkdir()
    r = auth_client.post(
        "/api/sessions/",
        {"name": "X", "local_path": str(outside)},
        format="json",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_session_serializer_exposes_local_path(auth_client, session, tmp_path, settings):
    settings.WORKSPACE_LOCAL_ROOTS = [str(tmp_path)]
    session.workspace.local_path = str(tmp_path)
    session.workspace.save()
    r = auth_client.get(f"/api/sessions/{session.id}/")
    assert r.status_code == 200
    assert r.data["local_path"] == str(tmp_path)


@pytest.mark.django_db
def test_local_dirs_endpoint(auth_client, tmp_path, settings):
    settings.WORKSPACE_LOCAL_ROOTS = [str(tmp_path)]
    (tmp_path / "dossier-a").mkdir()
    r = auth_client.get("/api/sessions/local_dirs/", {"path": str(tmp_path)})
    assert r.status_code == 200
    names = [entry["name"] for entry in r.data["dirs"]]
    assert "dossier-a" in names


@pytest.mark.django_db
def test_history_excludes_system(auth_client, session):
    Message.objects.create(session=session, role=Message.Role.SYSTEM, content="sys")
    Message.objects.create(session=session, role=Message.Role.USER, content="hi")
    r = auth_client.get(f"/api/sessions/{session.id}/history/")
    assert r.status_code == 200
    assert len(r.data) == 1
    assert r.data[0]["role"] == "user"


@pytest.mark.django_db
def test_fork_session_copies_messages(auth_client, session):
    Message.objects.create(session=session, role=Message.Role.USER, content="hello")
    Message.objects.create(session=session, role=Message.Role.ASSISTANT, content="world")
    r = auth_client.post(f"/api/sessions/{session.id}/fork/")
    assert r.status_code == 201
    new_id = r.data["id"]
    assert new_id != str(session.id)
    assert Session.objects.filter(id=new_id).exists()
    assert Session.objects.get(id=new_id).messages.count() == 2


@pytest.mark.django_db
def test_session_not_visible_to_other_user(api_client, session, user2):
    api_client.force_authenticate(user=user2)
    r = api_client.get("/api/sessions/")
    assert r.status_code == 200
    assert r.data["results"] == []