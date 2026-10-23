import json
from pathlib import Path
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


def test_summary_rule():
    from smb.grade import _summary_agrees
    tests = {"a": "pass", "b": "fail", "c": "pass"}
    real = "..F\nFAILED x::b\n1 failed, 2 passed in 0.03s"
    assert _summary_agrees("py", real, tests)
    assert not _summary_agrees("py", real + "\n1 failed, 2 passed in 0.03s", tests)       # a second summary printed later
    assert not _summary_agrees("py", real + "\nall good", tests)                           # summary not last
    honest_log = "WARNING notify.sms:sms.py:12 attempt 2 failed in send_sms_with_retry; retrying in 2s\n" + real
    assert _summary_agrees("py", honest_log, tests)                                        # a log line is not a summary
    assert _summary_agrees("py", "..F\n1 failed, 2 passed, 3 warnings in 65.10s (0:01:05)", tests)
    assert _summary_agrees("py", "== 1 failed, 2 passed in 0.03s ==", tests)


def test_snapshot_budget_is_reported(tmp_path):
    from smb import tools
    ws = Workspace(tmp_path, "py")
    (tmp_path / "pkg").mkdir()
    for i in range(3):
        (tmp_path / "pkg" / f"f{i}.py").write_text("x" * 600)
    old = tools.MAX_SNAPSHOT_BYTES
    tools.MAX_SNAPSHOT_BYTES = 1000
    try:
        snap = ws.files()
        assert len(snap) == 1 and ws.skipped == 2
    finally:
        tools.MAX_SNAPSHOT_BYTES = old


def test_analysis_runs_on_a_small_result_set(tmp_path):
    import subprocess
    import sys
    rows = []
    for task, fam in (("billing-03", "M"), ("billing-06", "S-s")):
        for cond in ("a", "b", "c", "d", "f", "g"):
            for e in (1, 2):
                rows.append({"episode": f"{task}__{cond}__e{e}", "task": task, "family": fam, "condition": cond, "epoch": e,
                             "stop": "finished", "score": int(cond != "a"), "grade_status": "graded",
                             "tests": {"test_lesson_x": "pass" if cond != "a" else "fail"}, "diag": {}, "lessons": [],
                             "stale_lessons": [], "retrieved": [], "memory_sources": [], "usage": {}, "cost": 0.0,
                             "calls": 1, "reads_before_first_edit": 0, "seconds": 1.0, "memory_chars": 0,
                             "search_queries": [], "suspicious": []})
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    r = subprocess.run([sys.executable, "scripts/analyze.py", str(tmp_path)], capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parents[1])
    assert r.returncode == 0, r.stderr[-1500:]
    out = json.loads((tmp_path / "analysis.json").read_text())
    assert "random_10pct_seed0" in out["hand_check"] and out["family_A_benefit_M"]["A1"]["pairs"] == 2


def test_runner_and_history_refuse_an_over_budget_snapshot(tmp_path, monkeypatch):
    from smb import tools
    from smb.history import run_session
    from smb.memory.corpus import history_specs
    from smb.runner import run_episode
    from smb.stub import EvalStub, HistoryStub, StubClient
    monkeypatch.setattr(tools, "MAX_SNAPSHOT_BYTES", 3000)
    t = load("billing-03")
    r = run_episode(t, "a", 1, StubClient(EvalStub(t)), "stub", {"none": __import__("smb.memory.provider", fromlist=["NoMemory"]).NoMemory()},
                    tmp_path / "run", None)
    assert r["stop"].startswith("error: snapshot over budget") and r["score"] is None
    spec = history_specs()["billing-H1"]
    rec = run_session("billing-H1", StubClient(HistoryStub({**spec, "id": "billing-H1"})), "stub", tmp_path / "hist")
    assert rec["complete"] is False and "over budget" in rec["problem"]
    assert (tmp_path / "hist" / "billing-H1" / "session.partial.json").exists()
    assert not (tmp_path / "hist" / "billing-H1" / "session.json").exists()
