import pytest

from apps.sessions.models import Message, Session


@pytest.mark.django_db
def test_create_session(auth_client, workspace):
    r = auth_client.post(
        "/api/sessions/", {"workspace": str(workspace.id)}, format="json"
    )
    assert r.status_code == 201
    assert str(r.data["workspace"]) == str(workspace.id)


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
