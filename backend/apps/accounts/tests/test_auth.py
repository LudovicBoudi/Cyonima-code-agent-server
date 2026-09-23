import pytest

from apps.accounts.models import User


@pytest.mark.django_db
def test_register_disabled(api_client):
    """L'inscription publique est fermée : seuls les admins créent des comptes."""
    r = api_client.post(
        "/api/auth/register/",
        {"email": "new@test.dev", "name": "New", "password": "pass12345"},
        format="json",
    )
    assert r.status_code == 404
    assert not User.objects.filter(email="new@test.dev").exists()


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


@pytest.mark.django_db
def test_admin_users_list_for_staff(api_client, user):
    user.is_staff = True
    user.is_superuser = True
    user.save()
    api_client.force_authenticate(user=user)
    r = api_client.get("/api/auth/admin/users/")
    assert r.status_code == 200
    assert "results" in r.data


@pytest.mark.django_db
def test_admin_users_denied_for_member(api_client, user):
    api_client.force_authenticate(user=user)
    assert api_client.get("/api/auth/admin/users/").status_code == 403


@pytest.mark.django_db
def test_admin_create_user_and_toggle(api_client, user):
    user.is_staff = True
    user.is_superuser = True
    user.save()
    api_client.force_authenticate(user=user)
    r = api_client.post(
        "/api/auth/admin/users/",
        {
            "email": "staff@test.dev",
            "name": "Staff",
            "password": "pass12345",
            "is_staff": True,
        },
        format="json",
    )
    assert r.status_code == 201
    new_user = User.objects.get(email="staff@test.dev")
    assert new_user.is_staff is True

    r2 = api_client.patch(
        f"/api/auth/admin/users/{new_user.id}/",
        {"is_staff": False},
        format="json",
    )
    assert r2.status_code == 200
    new_user.refresh_from_db()
    assert new_user.is_staff is False
