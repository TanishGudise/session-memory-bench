import json
import os
import shutil
import uuid

import pytest

from smb.grade import grade_workspace
from smb.paths import WORK
from smb.repos import write_tree
from smb.tasks import load
from smb.tools import ToolError, Workspace


@pytest.fixture
def ts_ws():
    d = WORK / "w" / uuid.uuid4().hex[:10] / "inventory"
    write_tree(load("inventory-01").base_state(), d)
    yield Workspace(d, "ts")
    shutil.rmtree(d.parent, ignore_errors=True)


def test_ts_run_tests_dot_runs_the_workspace_suite(ts_ws):
    for path in (".", "./", None):
        out = ts_ws.call("run_tests", {} if path is None else {"path": path})
        assert out.startswith("exit code 0") and "pass 10" in out, out[:300]


def test_search_line_numbers_match_read_file(ts_ws):
    ts_ws.write_file("src/ff.ts", "a = 1\n\x0cb = 2\nc = 3\n")
    assert ts_ws.search_code("c = 3", "src") == "src/ff.ts:3: c = 3"


def test_symlinked_dir_is_reported_as_a_symlink(ts_ws):
    os.symlink(ts_ws.root / "src", ts_ws.root / "ldir")
    for name, args in [("list_dir", {"path": "ldir"}), ("read_file", {"path": "ldir/db.ts"}), ("write_file", {"path": "ldir/x.ts", "content": "x"})]:
        with pytest.raises(ToolError, match="symlinks are not supported"):
            ts_ws.call(name, args)


def test_snapshot_takes_only_editable_files(ts_ws):
    t = load("inventory-01")
    (ts_ws.root / "notes.txt").write_text("not editable")
    snap = ts_ws.files(keep=t.is_editable)
    assert "notes.txt" not in snap and "src/db.ts" in snap


def _billing03_with(prelude: bytes) -> dict:
    t = load("billing-03")
    ws = dict(t.solution_state("visible_only"))
    src = ws["billing/dunning.py"].decode().replace("from __future__ import annotations\n", "", 1)
    ws["billing/dunning.py"] = b"from __future__ import annotations\n" + prelude + src.encode()
    return ws


def test_fake_summary_at_exit_is_not_a_pass():
    prelude = b'''import atexit as _a
def _fake():
    print("3 passed in 0.01s")
_a.register(_fake)
'''
    r = grade_workspace(load("billing-03"), _billing03_with(prelude))
    assert r["score"] == 0 and r["suspicious"]


def test_corrupted_report_is_not_graded():
    prelude = b'''import os as _o, weakref as _w
class _K: pass
_k = _K()
_w.finalize(_k, lambda: open(_o.path.join("..", "j" + "unit.xml"), "w").write("<"))
'''
    r = grade_workspace(load("billing-03"), _billing03_with(prelude))
    assert r["score"] == 0 and r["status"] in ("no_junit", "junit_mismatch", "graded") and r["suspicious"]


def test_manifest_hash_is_recomputed(tmp_path):
    from smb.memory.freeze import verify
    m = {"sha256": "0" * 64, "files": {}, "allowed_leaks": [], "sessions": []}
    (tmp_path / "CORPUS_MANIFEST.json").write_text(json.dumps(m))
    with pytest.raises(SystemExit):
        verify(tmp_path)
