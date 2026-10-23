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


def test_symlinks_made_by_agent_code_are_not_followed(ws, tmp_path):
    secret = tmp_path.parent / "secret-outside.txt"
    secret.write_text("def test_lesson_secret(): pass\n")
    os.symlink(secret, tmp_path / "pkg" / "link.py")
    assert "secret" not in ws.search_code("test_lesson")
    assert "link.py" not in ws.list_dir(".")
    assert "pkg/link.py" not in ws.files()


def test_odd_inputs_are_tool_errors(ws, tmp_path):
    os.mkfifo(tmp_path / "pkg" / "pipe.py")
    for name, args in [("run_tests", {"path": "a\x00b"}), ("run_tests", {"path": "x" * 5000}),
                       ("search_code", {"pattern": "a{99999999999}"}), ("replace_in_file", {"path": "pkg/pipe.py", "old_text": "a", "new_text": "b"}),
                       ("write_file", {"path": "pkg/pipe.py", "content": "x"}), ("read_file", {"path": "pkg/pipe.py"}),
                       ("read_file", {"path": 3}), ("nope", {})]:
        with pytest.raises(ToolError):
            ws.call(name, args)
    (tmp_path / "pkg" / "locked.py").write_text("x")
    os.chmod(tmp_path / "pkg" / "locked.py", 0)
    try:
        assert "pkg/locked.py" not in ws.files()
    finally:
        os.chmod(tmp_path / "pkg" / "locked.py", 0o644)


def test_unreadable_dirs_inner_links_and_slow_regex(ws, tmp_path):
    import time
    d = tmp_path / "lockdir"
    d.mkdir()
    (d / "x.py").write_text("x")
    os.chmod(d, 0o600)
    try:
        assert "pkg/a.py" in ws.files() and "lockdir/x.py" not in ws.files()
        assert "pkg/a.py" in ws.list_dir(".")
        assert "pkg/a.py:1" in ws.search_code("x = 1")
    finally:
        os.chmod(d, 0o755)
    os.symlink(tmp_path / "pkg" / "a.py", tmp_path / "alias.py")
    for name, args in [("read_file", {"path": "alias.py"}), ("write_file", {"path": "alias.py", "content": "y"})]:
        with pytest.raises(ToolError):
            ws.call(name, args)
    assert (tmp_path / "pkg" / "a.py").read_text() == "x = 1\nx = 1\n"
    (tmp_path / "pkg" / "long.py").write_text("a" * 40 + "!\n")
    t0 = time.monotonic()
    with pytest.raises(ToolError):
        ws.call("search_code", {"pattern": r"(a+)+$"})
    assert time.monotonic() - t0 < 30
