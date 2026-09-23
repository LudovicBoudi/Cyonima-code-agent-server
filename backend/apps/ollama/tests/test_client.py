import asyncio
import json

import httpx

from apps.ollama.client import OllamaClient


def test_capabilities_from_list(monkeypatch):
    client = OllamaClient(base_url="http://x")

    async def fake_show(name):
        return {
            "details": {"families": ["qwen35"], "parameter_size": "9.0B"},
            "capabilities": ["tools", "thinking"],
            "model_info": {"qwen3.context_length": 262144},
        }

    monkeypatch.setattr(client, "show", fake_show)
    caps = asyncio.run(client.capabilities("m"))
    assert caps["supports_tools"] is True
    assert caps["supports_thinking"] is True
    assert caps["context_length"] == 262144


def test_capabilities_from_dict(monkeypatch):
    client = OllamaClient(base_url="http://x")

    async def fake_show(name):
        return {"details": {}, "capabilities": {"tools": True}, "model_info": {}}

    monkeypatch.setattr(client, "show", fake_show)
    caps = asyncio.run(client.capabilities("m"))
    assert caps["supports_tools"] is True
    assert caps["supports_thinking"] is False


def test_pull_success(monkeypatch):
    client = OllamaClient(base_url="http://x")
    lines = [
        {"status": "pulling manifest"},
        {"status": "downloading", "digest": "a", "total": 100, "completed": 40},
        {"status": "success"},
    ]

    async def handler(request):
        body = "\n".join(json.dumps(line) for line in lines)
        return httpx.Response(200, content=body)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(client, "_client", lambda: httpx.AsyncClient(transport=transport))

    seen = []

    async def on_progress(d):
        seen.append(d["status"])

    ok = asyncio.run(client.pull("test", on_progress=on_progress))
    assert ok is True
    assert seen == ["pulling manifest", "downloading", "success"]


def test_pull_http_error_returns_false(monkeypatch):
    client = OllamaClient(base_url="http://x")

    async def handler(request):
        return httpx.Response(404, content='{"error": "not found"}')

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(client, "_client", lambda: httpx.AsyncClient(transport=transport))

    ok = asyncio.run(client.pull("nope"))
    assert ok is False


def test_resolve_model_falls_back_to_installed(monkeypatch):
    client = OllamaClient(base_url="http://x")

    async def fake_list():
        return [{"name": "ornith:9b"}, {"name": "qwen2.5-coder:7b"}]

    monkeypatch.setattr(client, "list_models", fake_list)
    # modèle demandé non installé -> tombe sur le défaut installé
    assert asyncio.run(client.resolve_model("llama3:8b")) == "qwen2.5-coder:7b"


def test_resolve_model_matches_without_tag(monkeypatch):
    client = OllamaClient(base_url="http://x")

    async def fake_list():
        return [{"name": "qwen2.5-coder:7b"}]

    monkeypatch.setattr(client, "list_models", fake_list)
    assert asyncio.run(client.resolve_model("qwen2.5-coder")) == "qwen2.5-coder:7b"


def test_resolve_model_first_available(monkeypatch):
    client = OllamaClient(base_url="http://x")

    async def fake_list():
        return [{"name": "ornith:9b"}]

    monkeypatch.setattr(client, "list_models", fake_list)
    assert asyncio.run(client.resolve_model("")) == "ornith:9b"
