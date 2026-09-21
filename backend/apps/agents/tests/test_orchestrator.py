import pytest

import fakeredis

from apps.agents import orchestrator


@pytest.fixture
def redis(monkeypatch):
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(orchestrator, "_client", client)
    return client


def test_acquire_and_release(redis):
    assert orchestrator.acquire_run("s", "v1") is True
    assert orchestrator.acquire_run("s", "v2") is False  # déjà verrouillé
    assert orchestrator.is_running("s") is True
    assert orchestrator.get_run_value("s") == "v1"
    orchestrator.release_run("s", "v1")
    assert orchestrator.is_running("s") is False
    assert orchestrator.acquire_run("s", "v2") is True


def test_release_wrong_value_noop(redis):
    orchestrator.acquire_run("s", "v1")
    orchestrator.release_run("s", "v2")  # mauvaise valeur → pas de release
    assert orchestrator.is_running("s") is True
    assert orchestrator.get_run_value("s") == "v1"


def test_force_acquire(redis):
    orchestrator.acquire_run("s", "v1")
    orchestrator.force_acquire_run("s", "v2")
    assert orchestrator.get_run_value("s") == "v2"


def test_cancel_flag(redis):
    assert orchestrator.is_cancelled("s") is False
    orchestrator.request_cancel("s")
    assert orchestrator.is_cancelled("s") is True
