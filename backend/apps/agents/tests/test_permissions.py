import pytest

from apps.agents.permissions import DEFAULT_POLICY, is_external_path
from apps.agents.tools import run_tool
from apps.workspaces import files


def test_file_tools_auto_inside_workspace():
    for tool in ("read_file", "write_file", "edit_file"):
        assert DEFAULT_POLICY.decision(tool, {"path": "src/main.py"}) == "auto"
        assert DEFAULT_POLICY.decision(tool, {"path": "app.js"}) == "auto"


def test_file_tools_ask_outside_workspace():
    for tool in ("read_file", "write_file", "edit_file"):
        assert DEFAULT_POLICY.decision(tool, {"path": "/tmp/toto.txt"}) == "ask"


def test_glob_grep_always_auto():
    assert DEFAULT_POLICY.decision("glob", {"pattern": "**/*.py"}) == "auto"
    assert DEFAULT_POLICY.decision("grep", {"pattern": "def main"}) == "auto"


def test_bash_always_ask():
    assert DEFAULT_POLICY.decision("bash", {"command": "ls"}) == "ask"


def test_unknown_tool_ask():
    assert DEFAULT_POLICY.decision("whatever", {}) == "ask"


def test_path_scoping():
    assert is_external_path({"path": "/etc/hosts"}) is True
    assert is_external_path({"path": "rel/path"}) is False


@pytest.mark.django_db
def test_read_absolute_path_inside_external_roots(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setattr("django.conf.settings.WORKSPACE_EXTERNAL_ROOTS", [str(root)])

    files.write_file_abs(str(root / "x.txt"), "contenu")
    output, is_error = run_tool("read_file", None, {"path": str(root / "x.txt")})
    assert is_error is False
    assert output == "contenu"


@pytest.mark.django_db
def test_read_absolute_path_outside_external_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "django.conf.settings.WORKSPACE_EXTERNAL_ROOTS", [str(tmp_path / "root")]
    )
    output, is_error = run_tool(
        "read_file", None, {"path": "/etc/passwd"}
    )
    assert is_error is True
    assert "non autoris" in output


@pytest.mark.django_db
def test_write_absolute_path_outside_workspace_scope(tmp_path, monkeypatch):
    external_root = tmp_path / "ext"
    external_root.mkdir()
    monkeypatch.setattr(
        "django.conf.settings.WORKSPACE_EXTERNAL_ROOTS", [str(external_root)]
    )
    target = external_root / "notes.txt"
    output, is_error = run_tool(
        "write_file", None, {"path": str(target), "content": "hi"}
    )
    assert is_error is False
    assert target.read_text() == "hi"