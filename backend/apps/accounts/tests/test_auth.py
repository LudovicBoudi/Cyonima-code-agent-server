import pytest

from apps.accounts.models import User


@pytest.mark.django_db
def test_register_creates_user(api_client):
    r = api_client.post(
        "/api/auth/register/",
        {"email": "new@test.dev", "name": "New", "password": "pass12345"},
        format="json",
    )
    assert r.status_code == 201
    assert User.objects.filter(email="new@test.dev").exists()


@pytest.mark.django_db
def test_login_returns_jwt(api_client, user):
    r = api_client.post(
        "/api/auth/login/", {"email": user.email, "password": "pass12345"}, format="json"
    )
    assert r.status_code == 200
    assert "access" in r.data and "refresh" in r.data
    assert r.data["user"]["email"] == user.email


@pytest.mark.django_db
def test_login_wrong_password(api_client, user):
    r = api_client.post(
        "/api/auth/login/", {"email": user.email, "password": "wrong"}, format="json"
    )
    assert r.status_code == 401


@pytest.mark.django_db
def test_me(auth_client, user):
    r = auth_client.get("/api/auth/me/")
    assert r.status_code == 200
    assert r.data["email"] == user.email


@pytest.mark.django_db
def test_me_requires_auth(api_client):
    assert api_client.get("/api/auth/me/").status_code == 401


@pytest.mark.django_db
def test_session_token(api_client, user):
    api_client.force_login(user)
    r = api_client.get("/api/auth/session-token/")
    assert r.status_code == 200
    assert "access" in r.data and "refresh" in r.data


@pytest.mark.django_db
def test_sso_providers_empty(api_client):
    r = api_client.get("/api/auth/sso/")
    assert r.status_code == 200
    assert r.data["providers"] == []
