import asyncio

import pytest

from apps.agents.loop import (
    merge_tool_calls,
    message_to_ollama,
    prepare_messages,
    to_ollama_tool_calls,
    _wait_decision,
)
from apps.agents.services import get_or_create_user_message, respond
from apps.sessions.models import Message


def test_merge_tool_calls_fragments():
    raw = [
        {"index": 0, "function": {"name": "read_file", "arguments": '{"pa'}},
        {"index": 0, "function": {"arguments": 'th": "a.txt"}'}},
    ]
    merged = merge_tool_calls(raw)
    assert merged == [{"id": "call_0", "name": "read_file", "arguments": {"path": "a.txt"}}]


def test_merge_tool_calls_dict_args():
    raw = [{"index": 0, "function": {"name": "bash", "arguments": {"command": "ls"}}}]
    merged = merge_tool_calls(raw)
    assert merged[0]["arguments"] == {"command": "ls"}


def test_to_ollama_tool_calls():
    stored = [{"id": "c1", "name": "read_file", "arguments": {"path": "a"}}]
    assert to_ollama_tool_calls(stored) == [
        {"function": {"name": "read_file", "arguments": {"path": "a"}}}
    ]


def test_message_to_ollama(session):
    m = Message(
        session=session,
        role=Message.Role.ASSISTANT,
        content="ok",
        tool_calls=[{"id": "c1", "name": "read_file", "arguments": {"path": "a"}}],
    )
    msg = message_to_ollama(m)
    assert msg["role"] == "assistant"
    assert msg["tool_calls"] == [{"function": {"name": "read_file", "arguments": {"path": "a"}}}]


@pytest.mark.django_db
def test_get_or_create_user_message_idempotent(session):
    m1, created1 = get_or_create_user_message(str(session.id), "run-1", "bonjour")
    m2, created2 = get_or_create_user_message(str(session.id), "run-1", "bonjour")
    assert created1 is True
    assert created2 is False
    assert m1.id == m2.id


@pytest.mark.django_db
def test_prepare_messages_truncates_partials(session):
    m1, _ = get_or_create_user_message(str(session.id), "run-1", "bonjour")
    Message.objects.create(session=session, role=Message.Role.ASSISTANT, content="partial")
    assert Message.objects.filter(session=session).count() == 2

    _session, _ws, messages, user_text = prepare_messages(str(session.id), str(m1.id))
    assert user_text == "bonjour"
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user"]
    assert Message.objects.filter(session=session).count() == 1


@pytest.mark.django_db
def test_respond_updates_status(session):
    from apps.agents.models import PermissionRequest

    p = PermissionRequest.objects.create(
        session=session, call_id="abc", tool="bash", arguments={}, preview="$ ls"
    )
    assert respond(str(session.id), "abc", True) is True
    p.refresh_from_db()
    assert p.status == PermissionRequest.Status.APPROVED
    # une seconde réponse échoue (déjà résolue)
    assert respond(str(session.id), "abc", False) is False


@pytest.mark.django_db(transaction=True)
def test_wait_decision_approved(session):
    from asgiref.sync import sync_to_async

    from apps.agents.models import PermissionRequest

    PermissionRequest.objects.create(
        session=session, call_id="x", tool="bash", arguments={}, preview="$ ls"
    )

    async def run():
        async def approve_later():
            await asyncio.sleep(0.5)
            await sync_to_async(respond)(str(session.id), "x", True)

        task = asyncio.create_task(approve_later())
        result = await _wait_decision(str(session.id), "x", timeout=5)
        await task
        return result

    assert asyncio.run(run()) is True


@pytest.mark.django_db(transaction=True)
def test_wait_decision_timeout(session):
    from apps.agents.models import PermissionRequest

    PermissionRequest.objects.create(
        session=session, call_id="y", tool="bash", arguments={}, preview="$ ls"
    )
    result = asyncio.run(_wait_decision(str(session.id), "y", timeout=1))
    assert result is False
