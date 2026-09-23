"""Client HTTP vers l'instance Ollama partagée.

Reprend la logique du provider Ollama de l'app desktop :
  - listage des modèles (`GET /api/tags`)
  - capacités d'un modèle (`POST /api/show`) : tools, thinking, taille de contexte
  - chat streaming NDJSON (`POST /api/chat`) avec tool calling et thinking
  - pull / delete de modèles
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class ChatChunk:
    content: str = ""
    thinking: str = ""
    tool_calls: list = field(default_factory=list)
    done: bool = False
    usage: dict = field(default_factory=dict)


class OllamaClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))

    # ------------------------------------------------------------------ listage
    async def list_models(self) -> list[dict]:
        async with self._client() as c:
            r = await c.get(f"{self.base_url}/api/tags")
            r.raise_for_status()
            return r.json().get("models", [])

    async def show(self, name: str) -> dict:
        async with self._client() as c:
            r = await c.post(f"{self.base_url}/api/show", json={"name": name})
            r.raise_for_status()
            return r.json()

    async def resolve_model(self, name: str) -> str:
        """Retourne un modèle réellement disponible, le plus proche de `name`.

        Priorité :
          1. le modèle demandé s'il est installé (correspondance exacte),
          2. le modèle par défaut configuré s'il est installé,
          3. le premier modèle installé,
          4. `name` en dernier recours.
        """
        if not name or not name.strip():
            name = settings.OLLAMA_DEFAULT_MODEL or ""
        try:
            available = await self.list_models()
        except Exception as exc:
            logger.warning("Liste des modèles indisponible, retour de %s (%s)", name, exc)
            return name
        names = [m.get("name", "") for m in available if m.get("name")]
        if name in names:
            return name
        if settings.OLLAMA_DEFAULT_MODEL in names:
            return settings.OLLAMA_DEFAULT_MODEL
        if names and name:
            # tolérance : "qwen2.5-coder" ==> "qwen2.5-coder:7b"
            base = name.split(":")[0]
            for n in names:
                if n.split(":")[0] == base:
                    return n
        if names:
            return names[0]
        return name

    async def capabilities(self, name: str) -> dict:
        """Retourne les capacités d'un modèle (tools, thinking, context)."""
        try:
            info = await self.show(name)
        except Exception as exc:
            logger.warning("Impossible de lire les capacités de %s: %s", name, exc)
            return {}
        details = info.get("details", {})
        families = details.get("families") or [details.get("family")]
        caps = info.get("capabilities") or {}
        if isinstance(caps, list):
            caps = {c: True for c in caps}
        model_info = info.get("model_info") or {}
        context_length = None
        for key, val in model_info.items():
            if key.endswith(".context_length"):
                context_length = val
                break
        return {
            "supports_tools": bool(caps.get("tools")),
            "supports_thinking": bool(caps.get("thinking")),
            "context_length": context_length,
            "families": families,
            "parameter_size": details.get("parameter_size"),
            "size": info.get("size"),
        }

    # -------------------------------------------------------------------- pull
    async def pull(self, name: str, on_progress=None) -> bool:
        async with self._client() as c:
            async with c.stream(
                "POST", f"{self.base_url}/api/pull", json={"name": name}
            ) as r:
                if r.status_code != 200:
                    if on_progress:
                        await on_progress({"status": "error", "error": f"HTTP {r.status_code}"})
                    return False
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if on_progress:
                        await on_progress(data)
                    if data.get("status") == "success":
                        return True
        return False

    async def delete(self, name: str) -> bool:
        async with self._client() as c:
            r = await c.delete(f"{self.base_url}/api/delete", json={"name": name})
            return r.status_code == 200

    # -------------------------------------------------------------------- chat
    async def chat_stream(
        self,
        messages: list[dict],
        model: str,
        tools: Optional[list[dict]] = None,
        reasoning: Optional[str] = None,
    ) -> AsyncIterator[ChatChunk]:
        """Streaming du chat, yield un ChatChunk par morceau significatif."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
        if reasoning and reasoning != "auto":
            # think est dérivé de l'intensité de raisonnement (modèles thinking)
            payload["think"] = reasoning != "off"

        async with self._client() as c:
            async with c.stream(
                "POST", f"{self.base_url}/api/chat", json=payload
            ) as r:
                if r.status_code == 400:
                    body = await r.aread()
                    # Fallback: certains modèles refusent les tools
                    if "does not support tools" in body.decode(errors="ignore"):
                        logger.warning("%s ne supporte pas les tools, retry sans tools", model)
                        async for chunk in self.chat_stream(messages, model, None, reasoning):
                            yield chunk
                        return
                    raise RuntimeError(f"Ollama 400: {body[:500]}")
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    chunk = ChatChunk()
                    if data.get("error"):
                        raise RuntimeError(f"Ollama: {data['error']}")
                    msg = data.get("message") or {}
                    if msg.get("content"):
                        chunk.content = msg["content"]
                    if msg.get("thinking"):
                        chunk.thinking = msg["thinking"]
                    if msg.get("tool_calls"):
                        chunk.tool_calls = msg["tool_calls"]
                    if data.get("done"):
                        chunk.done = True
                        chunk.usage = {
                            "prompt_tokens": data.get("prompt_eval_count"),
                            "completion_tokens": data.get("eval_count"),
                        }
                    yield chunk
