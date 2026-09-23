import pytest

from apps.organizations.models import Membership
from apps.workspaces import files
from apps.workspaces.models import Workspace


@pytest.mark.django_db
def test_create_workspace(auth_client, org):
    r = auth_client.post(
        f"/api/orgs/{org.id}/workspaces/", {"name": "p", "slug": "p"}, format="json"
    )
    assert r.status_code == 201
    # réponse = contrat async (provisioning différé)
    assert r.data["status"] == "creating"
    # en eager (test), le provisioning a déjà eu lieu en base
    ws = Workspace.objects.get(id=r.data["id"])
    assert ws.status == "ready"


@pytest.mark.django_db
def test_list_workspaces(auth_client, org, workspace):
    r = auth_client.get(f"/api/orgs/{org.id}/workspaces/")
    assert r.status_code == 200
    names = [w["name"] for w in r.data["results"]]
    assert "proj" in names


@pytest.mark.django_db
def test_member_cannot_create_workspace(api_client, org, user2):
    Membership.objects.create(organization=org, user=user2, role=Membership.Role.MEMBER)
    api_client.force_authenticate(user=user2)
    r = api_client.post(
        f"/api/orgs/{org.id}/workspaces/", {"name": "x", "slug": "x"}, format="json"
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_file_operations(workspace):
    files.write_file(workspace, "a.txt", "hello")
    assert files.read_file(workspace, "a.txt") == "hello"
    entries = files.list_dir(workspace, "")
    assert any(e["name"] == "a.txt" for e in entries)


@pytest.mark.django_db
def test_resolve_path_escape_raises(workspace):
    with pytest.raises(PermissionError):
        files.read_file(workspace, "../../etc/passwd")


@pytest.mark.django_db
def test_git_status_not_a_repo(workspace):
    result = files.git_status(workspace)
    assert result["is_repo"] is False


@pytest.mark.django_db
def test_workspace_allow_network_default(workspace):
    assert workspace.allow_network is False


@pytest.mark.django_db
def test_create_workspace_with_local_path(auth_client, org, tmp_path):
    r = auth_client.post(
        f"/api/orgs/{org.id}/workspaces/",
        {"name": "loc", "slug": "loc", "local_path": str(tmp_path)},
        format="json",
    )
    assert r.status_code == 400, "tmp_path doit être hors des racines par défaut (hors home)"


@pytest.mark.django_db
def test_create_workspace_local_path_allowed_under_root(auth_client, org, tmp_path, monkeypatch):
    from django.conf import settings

    sub = tmp_path / "sub"
    sub.mkdir()
    monkeypatch.setattr(settings, "WORKSPACE_LOCAL_ROOTS", [str(tmp_path)])
    r = auth_client.post(
        f"/api/orgs/{org.id}/workspaces/",
        {"name": "loc", "slug": "loc", "local_path": str(sub)},
        format="json",
    )
    assert r.status_code == 201
    assert r.data["local_path"] == str(sub)


@pytest.mark.django_db
def test_create_workspace_local_path_outside_roots(auth_client, org, tmp_path, monkeypatch):
    from django.conf import settings

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setattr(settings, "WORKSPACE_LOCAL_ROOTS", [str(allowed)])
    r = auth_client.post(
        f"/api/orgs/{org.id}/workspaces/",
        {"name": "loc", "slug": "loc", "local_path": str(tmp_path)},
        format="json",
    )
    assert r.status_code == 400

    # chemin avec ".." tentant une évasion
    r2 = auth_client.post(
        f"/api/orgs/{org.id}/workspaces/",
        {"name": "loc", "slug": "loc", "local_path": str(allowed / "..")},
        format="json",
    )
    assert r2.status_code == 400


@pytest.mark.django_db
def test_create_workspace_local_path_missing_dir(auth_client, org, tmp_path, monkeypatch):
    from django.conf import settings

    monkeypatch.setattr(settings, "WORKSPACE_LOCAL_ROOTS", [str(tmp_path)])
    missing = tmp_path / "nope"
    r = auth_client.post(
        f"/api/orgs/{org.id}/workspaces/",
        {"name": "loc", "slug": "loc", "local_path": str(missing)},
        format="json",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_local_dirs_endpoint(auth_client, org, tmp_path, monkeypatch):
    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "file.txt").write_text("x")
    from django.conf import settings

    monkeypatch.setattr(settings, "WORKSPACE_LOCAL_ROOTS", [str(tmp_path)])
    r = auth_client.get(f"/api/orgs/{org.id}/workspaces/local_dirs/")
    assert r.status_code == 200
    names = [d["name"] for d in r.data["dirs"]]
    assert names == ["sub"]
    assert r.data["path"] == str(tmp_path)


@pytest.mark.django_db
def test_local_dirs_blocks_escape(auth_client, org, tmp_path, monkeypatch):
    from django.conf import settings

    from apps.workspaces import files

    monkeypatch.setattr(settings, "WORKSPACE_LOCAL_ROOTS", [str(tmp_path)])
    with pytest.raises(PermissionError):
        files.list_local_dirs("/etc")
