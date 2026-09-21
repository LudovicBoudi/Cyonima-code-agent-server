import pytest

from apps.organizations.models import Membership, Organization


@pytest.mark.django_db
def test_create_org_creates_owner(auth_client, user):
    r = auth_client.post("/api/orgs/", {"name": "Acme2", "slug": "acme2"}, format="json")
    assert r.status_code == 201
    assert r.data["role"] == "owner"
    assert Membership.objects.filter(
        user=user, organization__slug="acme2", role=Membership.Role.OWNER
    ).exists()


@pytest.mark.django_db
def test_list_orgs(auth_client, org):
    r = auth_client.get("/api/orgs/")
    assert r.status_code == 200
    slugs = [o["slug"] for o in r.data["results"]]
    assert "acme" in slugs


@pytest.mark.django_db
def test_non_member_sees_no_org(api_client, user2, org):
    api_client.force_authenticate(user=user2)
    r = api_client.get("/api/orgs/")
    assert r.status_code == 200
    assert r.data["results"] == []


@pytest.mark.django_db
def test_member_cannot_delete_org(api_client, org, user2):
    Membership.objects.create(organization=org, user=user2, role=Membership.Role.MEMBER)
    api_client.force_authenticate(user=user2)
    r = api_client.delete(f"/api/orgs/{org.id}/")
    assert r.status_code == 403


@pytest.mark.django_db
def test_org_model(org):
    assert Organization.objects.count() == 1
    assert str(org) == "Acme"
