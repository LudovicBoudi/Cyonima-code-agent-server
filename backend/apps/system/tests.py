"""Tests de l'app `system` : config HTTPS + LDAP."""

from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.system.middleware import _is_local_host
from apps.system.models import SystemConfig
from apps.system.services import derive_email, display_fullname, generate_self_signed

User = get_user_model()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        email="admin@test.dev", password="pass12345", is_staff=True
    )


@pytest.fixture
def staff_client(api_client, staff_user):
    api_client.force_authenticate(user=staff_user)
    return api_client


# --------------------------------------------------------------------------
# API config
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_config_requires_staff(api_client, auth_client):
    fresh = type(api_client)()
    assert fresh.get(reverse("system-config")).status_code == 401
    assert auth_client.get(reverse("system-config")).status_code == 403


@pytest.mark.django_db
def test_config_get_and_patch(staff_client):
    r = staff_client.get(reverse("system-config"))
    assert r.status_code == 200
    data = r.json()
    assert data["https_enabled"] is False
    assert "ldap_bind_password" not in data  # secret non réémis

    r = staff_client.patch(
        reverse("system-config"),
        data={"ldap_server_uri": "ldap://dc.example.com:389", "ldap_enabled": True},
        format="json",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ldap_server_uri"] == "ldap://dc.example.com:389"
    assert body["ldap_enabled"] is True
    cfg = SystemConfig.get()
    assert cfg.ldap_server_uri == "ldap://dc.example.com:389"


@pytest.mark.django_db
def test_generate_cert(staff_client):
    r = staff_client.post(
        reverse("system-generate-cert"),
        data={"domain": "agent.example.dev"},
        format="json",
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    cfg = SystemConfig.get()
    assert cfg.is_https_ready
    assert cfg.https_domain == "agent.example.dev"
    assert body["config"]["has_tls_cert"] is True


@pytest.mark.django_db
def test_generate_cert_requires_domain(staff_client):
    r = staff_client.post(
        reverse("system-generate-cert"),
        data={"domain": "  "},
        format="json",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_test_ldap_without_server(staff_client):
    r = staff_client.post(
        reverse("system-test-ldap"),
        data={},
        format="json",
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False


@mock.patch("apps.system.views.test_ldap_connection")
def test_test_ldap_return_pass(mock_test, staff_client):
    mock_test.return_value = {"ok": True, "message": "OK"}
    r = staff_client.post(
        reverse("system-test-ldap"),
        data={"ldap_type": "openldap", "ldap_server_uri": "ldap://ldap.example.com"},
        format="json",
    )
    assert r.json()["ok"] is True
    # Les valeurs de test ne doivent pas rester en base.
    assert SystemConfig.get().ldap_server_uri == ""


# --------------------------------------------------------------------------
# Middleware HTTPS
# --------------------------------------------------------------------------
def test_is_local_host():
    assert _is_local_host("localhost")
    assert _is_local_host("127.0.0.1:8000")
    assert _is_local_host("foo.local")
    assert not _is_local_host("agent.example.dev")


@mock.patch("apps.system.middleware.SystemConfig.get")
def test_https_redirect(mock_cfg, settings):
    cfg = SystemConfig(https_enabled=True)
    mock_cfg.return_value = cfg
    settings.ALLOWED_HOSTS = ["*"]
    c = Client()
    r = c.get("/api/auth/me/", HTTP_X_FORWARDED_PROTO="http", HTTP_HOST="agent.example.dev")
    assert r.status_code == 301
    assert r.url.startswith("https://agent.example.dev")


@mock.patch("apps.system.middleware.SystemConfig.get")
def test_https_hsts_and_secure_cookie(mock_cfg, settings):
    cfg = SystemConfig(https_enabled=True)
    mock_cfg.return_value = cfg
    settings.ALLOWED_HOSTS = ["*"]
    c = Client()
    r = c.get("/login/", HTTP_X_FORWARDED_PROTO="https", HTTP_HOST="agent.example.dev")
    assert r.has_header("Strict-Transport-Security")


@mock.patch("apps.system.middleware.SystemConfig.get")
def test_https_ignored_locally_in_dev(mock_cfg, settings):
    cfg = SystemConfig(https_enabled=True)
    mock_cfg.return_value = cfg
    settings.DEBUG = True
    c = Client()
    r = c.get("/login/", HTTP_HOST="localhost", HTTP_X_FORWARDED_PROTO="http")
    assert r.status_code != 301


# --------------------------------------------------------------------------
# LDAP backend
# --------------------------------------------------------------------------
def test_derive_email_from_mail():
    cfg = SystemConfig(ldap_email_domain="corp.example.com")
    assert derive_email(cfg, "jsmith", {"mail": "jsmith@corp.example.com"}) == "jsmith@corp.example.com"


def test_derive_email_uses_upn_fallback():
    cfg = SystemConfig()
    assert derive_email(cfg, "jsmith", {"userPrincipalName": "jsmith@AD.EXAMPLE.COM"}) == "jsmith@AD.EXAMPLE.COM"


def test_derive_email_domain_fallback():
    cfg = SystemConfig(ldap_email_domain="corp.example.com")
    assert derive_email(cfg, "jsmith", {}) == "jsmith@corp.example.com"


def test_derive_email_requires_fallback():
    cfg = SystemConfig()
    with pytest.raises(ValueError):
        derive_email(cfg, "jsmith", {})
    assert derive_email(cfg, "jsmith@ext.example.com", {}) == "jsmith@ext.example.com"


def test_display_fullname():
    assert display_fullname(SystemConfig(ldap_user_attr="displayName"), {"displayName": "Jane Smith"}) == "Jane Smith"


@mock.patch("apps.system.auth.authenticate_ldap")
def test_ldap_backend_creates_local_user(mock_auth, db):
    from django.contrib.auth import authenticate

    mock_auth.return_value = (
        True,
        "ok",
        {"mail": "jane@corp.example.com", "displayName": "Jane Smith"},
    )
    SystemConfig.objects.create(pk=1, ldap_enabled=True, ldap_email_domain="corp.example.com")

    user = authenticate(username="jane", password="secret")

    assert user is not None
    assert user.email == "jane@corp.example.com"
    assert user.name == "Jane Smith"
    assert User.objects.filter(email="jane@corp.example.com").exists()


@mock.patch("apps.system.auth.authenticate_ldap")
def test_ldap_backend_disabled_returns_none(mock_auth, db):
    from django.contrib.auth import authenticate

    SystemConfig.objects.create(pk=1, ldap_enabled=False)

    user = authenticate(username="jane", password="secret")
    assert user is None
    mock_auth.assert_not_called()


@mock.patch("apps.system.auth.authenticate_ldap")
def test_ldap_backend_bad_password_returns_none(mock_auth, db):
    from django.contrib.auth import authenticate

    mock_auth.return_value = (False, "Identifiants incorrects.", None)
    SystemConfig.objects.create(pk=1, ldap_enabled=True)

    user = authenticate(username="jane", password="wrong")
    assert user is None


# --------------------------------------------------------------------------
# Certificat auto-signé
# --------------------------------------------------------------------------
def test_generate_self_signed():
    cert_pem, key_pem = generate_self_signed("example.dev")
    assert "BEGIN CERTIFICATE" in cert_pem
    assert "PRIVATE KEY" in key_pem