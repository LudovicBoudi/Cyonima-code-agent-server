import pytest

from apps.agents.tools import run_tool
from apps.workspaces import files


@pytest.mark.django_db
def test_glob_tool(workspace):
    files.write_file(workspace, "sub/hello.py", "x")
    files.write_file(workspace, "hello.txt", "y")
    output, is_error = run_tool("glob", workspace, {"pattern": "**/*.py"})
    assert is_error is False
    assert "sub/hello.py" in output


@pytest.mark.django_db
def test_unknown_tool_returns_error(workspace):
    output, is_error = run_tool("nope", workspace, {})
    assert is_error is True


@pytest.mark.django_db
def test_read_file_tool(workspace):
    files.write_file(workspace, "a.txt", "coucou")
    output, is_error = run_tool("read_file", workspace, {"path": "a.txt"})
    assert is_error is False
    assert output == "coucou"
