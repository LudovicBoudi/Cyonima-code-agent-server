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
