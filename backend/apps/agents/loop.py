"""Boucle de l'agent : streaming Ollama + tool calling + gateway de permissions.

Équivalent serveur de `SessionManager::agent_loop` du backend Rust.

Contraintes async/Django :
  - le streaming Ollama est natif async (httpx),
  - les accès ORM et l'exécution des outils (I/O, docker) sont wrappés dans
    `sync_to_async` pour tourner dans des threads et ne pas bloquer l'event loop.
"""
import asyncio
import json
import logging
from typing import Awaitable, Callable

from asgiref.sync import sync_to_async

from apps.ollama.client import OllamaClient
from apps.sessions.models import Message, Session
from apps.workspaces.models import Workspace

from .permissions import DEFAULT_POLICY, preview_arguments
from .prompt import build_system_prompt
from .tools import TOOLS, run_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 32

Emit = Callable[[dict], Awaitable[None]]
Approve = Callable[[dict], Awaitable[bool]]


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
def _prepare(session_id):
    """Charge la session et reconstruit le contexte de messages (ORM, thread)."""
    session = Session.objects.select_related("workspace").get(id=session_id)
    workspace: Workspace = session.workspace
    system_prompt = build_system_prompt(workspace)
    messages = [{"role": "system", "content": system_prompt}]
    for m in session.messages.exclude(role=Message.Role.SYSTEM):
        messages.append(message_to_ollama(m))
    return session, workspace, messages


@sync_to_async
def _create_message(session_id, **fields):
    return Message.objects.create(session_id=session_id, **fields)


@sync_to_async
def _set_title(session_id, title):
    Session.objects.filter(id=session_id, title="").update(title=title[:60])


_run_tool = sync_to_async(run_tool)


async def run_agent(
    session_id: str,
    user_message: str,
    model: str,
    reasoning: str,
    emit: Emit,
    approve: Approve,
    cancel_event: asyncio.Event,
):
    session, workspace, messages = await _prepare(session_id)
    client = OllamaClient()
    policy = DEFAULT_POLICY

    messages.append({"role": "user", "content": user_message})
    await _create_message(session_id, role=Message.Role.USER, content=user_message)

    tool_schemas = [t.schema() for t in TOOLS]

    for _ in range(MAX_TOOL_ITERATIONS):
        if cancel_event.is_set():
            await emit({"type": "done", "cancelled": True, "usage": {}})
            return

        assistant_content = ""
        tool_calls_raw: list[dict] = []
        usage: dict = {}

        async for chunk in client.chat_stream(messages, model, tool_schemas, reasoning):
            if cancel_event.is_set():
                break
            if chunk.content:
                assistant_content += chunk.content
                await emit({"type": "token", "token": chunk.content})
            if chunk.thinking:
                await emit({"type": "thinking", "token": chunk.thinking})
            tool_calls_raw.extend(chunk.tool_calls)
            if chunk.done:
                usage = chunk.usage

        if cancel_event.is_set():
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
                approved = decision != "deny"
                if decision == "ask":
                    request = {
                        "call_id": tc["id"],
                        "tool": tc["name"],
                        "arguments": tc["arguments"],
                        "preview": preview_arguments(tc["name"], tc["arguments"]),
                    }
                    await emit({"type": "permission_request", **request})
                    approved = await approve(request)

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
        await _set_title(session_id, user_message or assistant_content)
        await emit({"type": "done", "usage": usage})
        return

    await emit({"type": "done", "usage": usage, "truncated": True})
