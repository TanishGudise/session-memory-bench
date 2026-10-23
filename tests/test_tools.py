import os

import pytest

from smb.tools import ToolError, Workspace


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x = 1\nx = 1\n")
    return Workspace(tmp_path, "py")


def test_paths_are_confined(ws, tmp_path):
    for bad in ["../x", "/etc/passwd", "~/x", "pkg/../../x"]:
        with pytest.raises(ToolError):
            ws.read_file(bad)
    os.symlink("/etc", tmp_path / "link")
    with pytest.raises(ToolError):
        ws.read_file("link/hosts")
    with pytest.raises(ToolError):
        ws.write_file("link/x", "y")


def test_replace_needs_exactly_one_match(ws):
    with pytest.raises(ToolError):
        ws.replace_in_file("pkg/a.py", "x = 1", "x = 2")
    ws.write_file("pkg/b.py", "y = 1\n")
    ws.replace_in_file("pkg/b.py", "y = 1", "y = 2")
    assert ws.read_file("pkg/b.py") == "y = 2\n"
    assert ws.edits == ["pkg/b.py", "pkg/b.py"]


def test_search_and_list(ws):
    assert ws.search_code(r"x = \d") == "pkg/a.py:1: x = 1\npkg/a.py:2: x = 1"
    assert "pkg/a.py" in ws.list_dir(".")
