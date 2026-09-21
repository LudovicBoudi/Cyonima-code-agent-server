import pytest

import fakeredis

import apps.agents.tasks as tasks
from apps.agents import orchestrator
from apps.sessions.models import Message


@pytest.fixture
def redis(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(orchestrator, "_client", client)
    return client


@pytest.fixture
def stub_run(monkeypatch):
    calls = []

    async def _run(session_id, user_message_id, model, reasoning, emit, cancel_check):
        calls.append(session_id)
        await emit({"type": "done", "usage": {}})

    monkeypatch.setattr(tasks, "run_agent", _run)
    return calls


@pytest.mark.django_db
def test_run_agent_task_normal(session, redis, stub_run):
    sid = str(session.id)
    r = tasks.run_agent_task.apply(args=[sid, "run-A", "salut", "m", "off"])
    assert r.result["status"] == "done"
    assert len(stub_run) == 1
    assert Message.objects.filter(session=session, run_id="run-A").count() == 1
    assert orchestrator.is_running(sid) is False  # verrou libéré


@pytest.mark.django_db
def test_run_agent_task_redelivery_idempotent(session, redis, stub_run):
    sid = str(session.id)
    # verrou stale laissé par le worker mort
    orchestrator.force_acquire_run(sid, "run-A")
    tasks.run_agent_task.apply(args=[sid, "run-A", "salut", "m", "off"])
    # message utilisateur non dupliqué, mais run rejoué
    assert Message.objects.filter(session=session, run_id="run-A").count() == 1
    assert len(stub_run) == 1


@pytest.mark.django_db
def test_run_agent_task_busy(session, redis, stub_run):
    sid = str(session.id)
    orchestrator.force_acquire_run(sid, "run-B")
    r = tasks.run_agent_task.apply(args=[sid, "run-C", "hey", "m", "off"])
    assert r.result["status"] == "busy"
    assert len(stub_run) == 0
