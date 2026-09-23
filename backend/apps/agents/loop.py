"""Boucle de l'agent : streaming Ollama + tool calling + gateway de permissions.

Équivalent serveur de `SessionManager::agent_loop` du backend Rust.

La boucle est **rejouable** (reprise après crash) : elle ne crée pas le message
utilisateur (créé en amont par le dispatcher Celery, avec un `run_id`), et
tronque les éventuels messages partiels d'un run précédent interrompu.

Contraintes async/Django :
  - le streaming Ollama est natif async (httpx),
  - les accès ORM et l'exécution des outils (I/O, docker) sont wrappés dans
    `sync_to_async` pour tourner dans des threads et ne pas bloquer l'event loop.

Approbations : les demandes (`bash`) sont persistées en base
(`PermissionRequest`) et résolues par un endpoint REST ou par le WebSocket. La
boucle attend la résolution en polling (source de vérité = base), avec timeout.
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Awaitable, Callable

import httpx
from asgiref.sync import sync_to_async

from apps.ollama.client import OllamaClient
from apps.sessions.models import Message, Session
from apps.workspaces.models import Workspace

from .models import PermissionRequest
from .permissions import DEFAULT_POLICY, preview_arguments
from .prompt import build_system_prompt
from .tools import TOOLS, run_tool
from . import orchestrator

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 32
APPROVAL_TIMEOUT = 600  # secondes

Emit = Callable[[dict], Awaitable[None]]
CancelCheck = Callable[[], Awaitable[bool]]


def merge_tool_calls(raw_calls: list[dict]) -> list[dict]:
    """Fusionne les fragments de tool_calls streamés par Ollama (par index)."""
    by_index: dict[int, dict] = {}
    for tc in raw_calls:
        idx = tc.get("index", 0)
        fn = tc.get("function", {})
        entry = by_index.setdefault(idx, {"id": f"call_{idx}", "name": "", "arguments": ""})
        if fn.get("name"):
            entry["name"] = fn["name"]
        args = fn.get("arguments", "")
        if isinstance(args, dict):
            entry["arguments"] = args
        elif isinstance(args, str):
            entry["arguments"] = (entry["arguments"] or "") + args
    result = []
    for idx in sorted(by_index):
        e = by_index[idx]
        args = e["arguments"]
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                args = {}
        result.append({"id": e["id"], "name": e["name"], "arguments": args})
    return result


def to_ollama_tool_calls(stored: list[dict]) -> list[dict]:
    return [
        {"function": {"name": tc["name"], "arguments": tc["arguments"]}} for tc in stored
    ]


def message_to_ollama(m: Message) -> dict:
    if m.role == Message.Role.USER:
        return {"role": "user", "content": m.content}
    if m.role == Message.Role.ASSISTANT:
        msg = {"role": "assistant", "content": m.content}
        if m.tool_calls:
            msg["tool_calls"] = to_ollama_tool_calls(m.tool_calls)
        return msg
    if m.role == Message.Role.TOOL:
        return {"role": "tool", "content": m.content, "tool_call_id": m.tool_call_id}
    return {"role": m.role, "content": m.content}


@sync_to_async
def _prepare(session_id, user_message_id):
    return prepare_messages(session_id, user_message_id)


def prepare_messages(session_id, user_message_id):
    """Charge la session et reconstruit le contexte jusqu'au message utilisateur
    cible, en tronquant les messages partiels d'un run précédent (crash)."""
    session = Session.objects.select_related("workspace").get(id=session_id)
    workspace: Workspace = session.workspace
    user_msg = session.messages.get(id=user_message_id, role=Message.Role.USER)

    # Tronque tout message postérieur au message utilisateur (run interrompu)
    session.messages.filter(created_at__gt=user_msg.created_at).delete()

    messages = [{"role": "system", "content": build_system_prompt(workspace)}]
    for m in session.messages.exclude(role=Message.Role.SYSTEM).filter(
        created_at__lte=user_msg.created_at
    ):
        messages.append(message_to_ollama(m))
    return session, workspace, messages, user_msg.content


@sync_to_async
def _create_message(session_id, **fields):
    return Message.objects.create(session_id=session_id, **fields)


@sync_to_async
def _set_title(session_id, title):
    Session.objects.filter(id=session_id, title="").update(title=title[:60])


@sync_to_async
def _create_permission_request(session_id, call_id, tool, arguments, preview):
    PermissionRequest.objects.create(
        session_id=session_id,
        call_id=call_id,
        tool=tool,
        arguments=arguments,
        preview=preview,
    )


@sync_to_async
def _get_request_status(session_id, call_id):
    return (
        PermissionRequest.objects.filter(session_id=session_id, call_id=call_id)
        .values_list("status", flat=True)
        .first()
    )


@sync_to_async
def _expire_request(session_id, call_id):
    from django.utils import timezone

    PermissionRequest.objects.filter(
        session_id=session_id, call_id=call_id, status=PermissionRequest.Status.PENDING
    ).update(status=PermissionRequest.Status.EXPIRED, resolved_at=timezone.now())


async def _wait_decision(session_id, call_id, timeout=APPROVAL_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = await _get_request_status(session_id, call_id)
        if status == PermissionRequest.Status.APPROVED:
            return True
        if status == PermissionRequest.Status.DENIED:
            return False
        await asyncio.sleep(1)
    await _expire_request(session_id, call_id)
    return False


_run_tool = sync_to_async(run_tool)
_redis_cancelled = sync_to_async(orchestrator.is_cancelled)


def make_cancel_check(session_id: str, local_event: asyncio.Event | None = None) -> CancelCheck:
    """Fabrique une fonction d'annulation : événement local (immédiat) + drapeau
    Redis (cross-worker, sondé au plus 1×/s)."""
    last = [0.0]

    async def check() -> bool:
        if local_event is not None and local_event.is_set():
            return True
        now = time.monotonic()
        if now - last[0] >= 1.0:
            last[0] = now
            if await _redis_cancelled(session_id):
                return True
        return False

    return check


async def run_agent(
    session_id: str,
    user_message_id: str,
    model: str,
    reasoning: str,
    emit: Emit,
    cancel_check: CancelCheck,
):
    session, workspace, messages, user_text = await _prepare(session_id, user_message_id)
    client = OllamaClient()
    policy = DEFAULT_POLICY
    tool_schemas = [t.schema() for t in TOOLS]

    for _ in range(MAX_TOOL_ITERATIONS):
        if await cancel_check():
            await emit({"type": "done", "cancelled": True, "usage": {}})
            return

        assistant_content = ""
        tool_calls_raw: list[dict] = []
        usage: dict = {}

        try:
            async for chunk in client.chat_stream(messages, model, tool_schemas, reasoning):
                if await cancel_check():
                    break
                if chunk.content:
                    assistant_content += chunk.content
                    await emit({"type": "token", "token": chunk.content})
                if chunk.thinking:
                    await emit({"type": "thinking", "token": chunk.thinking})
                tool_calls_raw.extend(chunk.tool_calls)
                if chunk.done:
                    usage = chunk.usage
        except httpx.HTTPStatusError as exc:
            detail = ""
            if exc.response is not None:
                try:
                    detail = exc.response.json().get("error", "")
                except Exception:
                    detail = ""
            if detail:
                detail = f" — {detail}"
            logger.warning(
                "Erreur Ollama (%s) session %s: %s", exc.response.status_code if exc.response else "?", session_id, detail
            )
            await emit({"type": "error", "error": str(exc) + detail})
            await emit({"type": "done", "usage": {}})
            return

        if await cancel_check():
            await emit({"type": "done", "cancelled": True, "usage": {}})
            return

        merged = merge_tool_calls(tool_calls_raw)

        if merged:
            await _create_message(
                session_id,
                role=Message.Role.ASSISTANT,
                content=assistant_content,
                tool_calls=merged,
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_content,
                    "tool_calls": to_ollama_tool_calls(merged),
                }
            )

            for tc in merged:
                decision = policy.decision(tc["name"])

                if decision == "auto":
                    approved = True
                elif decision == "deny":
                    approved = False
                else:  # ask
                    request_id = str(uuid.uuid4())
                    preview = preview_arguments(tc["name"], tc["arguments"])
                    await _create_permission_request(
                        session_id, request_id, tc["name"], tc["arguments"], preview
                    )
                    await emit(
                        {
                            "type": "permission_request",
                            "call_id": request_id,
                            "tool": tc["name"],
                            "arguments": tc["arguments"],
                            "preview": preview,
                        }
                    )
                    approved = await _wait_decision(session_id, request_id)

                await emit(
                    {
                        "type": "tool_call",
                        "call_id": tc["id"],
                        "tool": tc["name"],
                        "arguments": tc["arguments"],
                    }
                )

                if approved:
                    output, is_error = await _run_tool(tc["name"], workspace, tc["arguments"])
                else:
                    output, is_error = "Refusé par l'utilisateur.", True

                await emit(
                    {
                        "type": "tool_result",
                        "call_id": tc["id"],
                        "tool": tc["name"],
                        "output": output,
                        "is_error": is_error,
                    }
                )
                await _create_message(
                    session_id,
                    role=Message.Role.TOOL,
                    content=output,
                    tool_call_id=tc["id"],
                    meta={"tool": tc["name"], "is_error": is_error},
                )
                messages.append(
                    {"role": "tool", "content": output, "tool_call_id": tc["id"]}
                )
            continue

        await _create_message(
            session_id, role=Message.Role.ASSISTANT, content=assistant_content
        )
        await _set_title(session_id, user_text or assistant_content)
        await emit({"type": "done", "usage": usage})
        return

    await emit({"type": "done", "usage": usage, "truncated": True})
