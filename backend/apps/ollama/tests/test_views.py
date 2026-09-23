from unittest.mock import AsyncMock, patch

from django.urls import reverse

from apps.ollama.catalog import CATALOG_MODELS


def test_catalog_requires_auth(api_client):
    r = api_client.get(reverse("ollama-catalog"))
    assert r.status_code == 401


def test_catalog_marks_installed(auth_client):
    overrides = {"ornith:9b", "qwen2.5-coder:7b"}
    installed_list = [{"name": n} for n in overrides]

    with patch("apps.ollama.views.OllamaClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.list_models = AsyncMock(return_value=installed_list)
        r = auth_client.get(reverse("ollama-catalog"))

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == len(CATALOG_MODELS)
    assert len(data["catalog"]) == len(CATALOG_MODELS)
    by_tag = {m["ollama_tag"]: m for m in data["catalog"]}
    assert by_tag["ornith:9b"]["installed"] is True
    assert by_tag["qwen2.5-coder:7b"]["installed"] is True
    assert by_tag["qwen3:8b"]["installed"] is False
    assert "ram_min_gb" in by_tag["qwen3:8b"]
    assert by_tag["qwen3:8b"]["model_type"] in ("general", "coding")


def test_catalog_available_without_ollama(auth_client):
    with patch("apps.ollama.views.OllamaClient") as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.list_models = AsyncMock(side_effect=Exception("Ollama down"))
        r = auth_client.get(reverse("ollama-catalog"))

    assert r.status_code == 200
    data = r.json()
    assert any(not m["installed"] for m in data["catalog"])