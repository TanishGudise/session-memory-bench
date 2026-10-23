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
            for e in range(1, 21):
                rows.append({"episode": f"{task}__{cond}__e{e}", "task": task, "family": fam, "condition": cond, "epoch": e,
                             "stop": "finished", "score": int(cond != "a"), "grade_status": "graded",
                             "tests": {"test_lesson_x": "pass" if cond != "a" else "fail"}, "diag": {}, "lessons": [],
                             "stale_lessons": [], "retrieved": [], "memory_sources": [], "usage": {}, "cost": 0.0,
                             "calls": 1, "reads_before_first_edit": 0, "seconds": 1.0, "memory_chars": 0,
                             "search_queries": [], "suspicious": []})
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (tmp_path / "corpus" / "billing-H1").mkdir(parents=True)
    (tmp_path / "corpus" / "billing-H1" / "attempts.jsonl").write_text(json.dumps({"attempt": 1, "problem": "checks not graded: timeout"}) + "\n")
    r = subprocess.run([sys.executable, "scripts/analyze.py", str(tmp_path), "--corpus", str(tmp_path / "corpus")], capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parents[1])
    assert r.returncode == 0, r.stderr[-1500:]
    out = json.loads((tmp_path / "analysis.json").read_text())
    assert "random_10pct_seed0" in out["hand_check"] and out["family_A_benefit_M"]["A1"]["pairs"] == 20
    assert len(out["hand_check"]["S_tasks_a_vs_c_disagree"]) == 20
    assert out["history_discarded_attempts"]["count"] == 1
    assert len(out["hand_check"]["random_10pct_seed0"]) == 20  # (240 scored - 40 on the disagreement list) // 10
    assert not [x for x in out["hand_check"]["random_10pct_seed0"] if x.startswith(("billing-06__a__", "billing-06__c__"))]


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


def test_history_with_ungraded_checks_posts_no_review_and_paid_survives(tmp_path, monkeypatch, capsys):
    import argparse
    import importlib
    from smb import history
    real = history.grade_workspace
    monkeypatch.setattr(history, "grade_workspace", lambda *a, **k: {**real(*a, **k), "status": "timeout"})
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    paid = importlib.import_module("paid")
    monkeypatch.setattr(paid, "RUNS", tmp_path)
    monkeypatch.setattr(paid.netguard, "install", lambda *a, **k: None)  # leave the test process's sockets alone
    args = argparse.Namespace(stub=True, corpus="c", stage="pilot", model="haiku", repos=["billing"])
    for _ in range(2):  # stops at the first incomplete session, no crash; the resume re-runs it
        paid.cmd_history(args, paid.Session(True, tmp_path / "logs"))
    assert capsys.readouterr().out.count('"reason": "checks not graded: timeout; resume runs it again"') == 2
    d = tmp_path / "history" / "c" / "billing-H1"
    rec = json.loads((d / "session.partial.json").read_text())
    assert rec["complete"] is False and "checks not graded: timeout" in rec["problem"]
    assert "Review from" not in (d / "transcript.jsonl").read_text()
    assert not (d / "session.json").exists()
    attempts = [json.loads(l) for l in (d / "attempts.jsonl").read_text().splitlines()]
    assert [a["problem"] for a in attempts] == ["checks not graded: timeout"] * 2
    assert (d / "attempt-1.transcript.jsonl").exists() and not (d / "attempt-2.transcript.jsonl").exists()


def test_workspace_is_removed_when_setup_fails(tmp_path, monkeypatch):
    from smb import runner
    from smb.memory.provider import NoMemory
    from smb.stub import EvalStub, StubClient
    monkeypatch.setattr(runner, "WORK", tmp_path / "work")

    class Broken(NoMemory):
        def recall(self, *a, **k):
            raise SystemExit("retriever missing")
    t = load("billing-03")
    try:
        runner.run_episode(t, "a", 1, StubClient(EvalStub(t)), "stub", {"none": Broken()}, tmp_path / "run", None)
    except SystemExit:
        pass
    assert list((tmp_path / "work" / "w").iterdir()) == []


def test_every_discarded_history_attempt_is_numbered_and_kept(tmp_path, monkeypatch):
    from smb import history
    from smb.memory.corpus import history_specs
    from smb.stub import HistoryStub, StubClient
    spec, out = history_specs()["billing-H1"], tmp_path / "hist"
    d = out / "billing-H1"

    class BadRequest(Exception):
        status_code = 400

    class FailsOnSecondCall(StubClient):
        n = 0

        def _create(self, **kw):
            self.n += 1
            if self.n == 2:
                raise BadRequest("rejected")
            return super()._create(**kw)

    def stub():
        return StubClient(HistoryStub({**spec, "id": "billing-H1"}))
    with pytest.raises(BadRequest):  # attempt 1: an API error propagates, after its record is written
        history.run_session("billing-H1", FailsOnSecondCall(HistoryStub({**spec, "id": "billing-H1"})), "stub", out)
    real = history.grade_workspace
    with monkeypatch.context() as m:  # attempt 2: checks can't be graded
        m.setattr(history, "grade_workspace", lambda *a, **k: {**real(*a, **k), "status": "timeout"})
        assert history.run_session("billing-H1", stub(), "stub", out)["complete"] is False
    with monkeypatch.context() as m:  # attempt 3: killed mid-run, so it leaves a transcript and no record
        m.setattr(history, "_not_kept", lambda *a, **k: None)
        with pytest.raises(BadRequest):
            history.run_session("billing-H1", FailsOnSecondCall(HistoryStub({**spec, "id": "billing-H1"})), "stub", out)
    rec = history.run_session("billing-H1", stub(), "stub", out)  # attempt 4 is kept
    assert rec["complete"] is True and rec["attempt"] == 4 and (d / "session.json").exists()
    lines = [json.loads(l) for l in (d / "attempts.jsonl").read_text().splitlines()]
    assert [l["attempt"] for l in lines] == [1, 2, 3]
    assert lines[0]["problem"].startswith("error: BadRequest") and lines[1]["problem"] == "checks not graded: timeout"
    assert lines[2]["problem"] == "ended without a record (killed, or its record could not be written)"
    assert all((d / f"attempt-{n}.transcript.jsonl").exists() for n in (1, 2, 3))


def test_attempt_numbers_survive_setup_failures_caps_and_gaps(tmp_path, monkeypatch):
    from smb import history
    from smb.meter import CapReached
    from smb.memory.corpus import history_specs
    from smb.stub import HistoryStub, StubClient
    spec = history_specs()["billing-H1"]

    def stub():
        return StubClient(HistoryStub({**spec, "id": "billing-H1"}))

    def lines(d):
        return [(l["attempt"], l["problem"]) for l in map(json.loads, (d / "attempts.jsonl").read_text().splitlines())]

    # a setup failure, then a killed draw, then a kept one: the killed draw still gets its own number and line
    out = tmp_path / "a"
    d = out / "billing-H1"
    with monkeypatch.context() as m:
        m.setattr(history, "TranscriptWriter", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        with pytest.raises(OSError):
            history.run_session("billing-H1", stub(), "stub", out)
    with monkeypatch.context() as m:
        m.setattr(history, "_not_kept", lambda *a, **k: None)
        m.setattr(history, "grade_workspace", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):
            history.run_session("billing-H1", stub(), "stub", out)
    assert history.run_session("billing-H1", stub(), "stub", out)["attempt"] == 3
    assert lines(d) == [(1, "error: OSError: disk full"), (2, "ended without a record (killed, or its record could not be written)")]
    assert sorted(p.name for p in d.glob("attempt-*")) == ["attempt-2.transcript.jsonl"]

    # a spend cap is recorded with its cause
    class CapOnThird:
        n = 0

        def reserve(self, *a, **k):
            self.n += 1
            if self.n >= 3:
                raise CapReached("cap")
            return object()

        def settle(self, *a, **k):
            return 0.0

        def release(self, *a, **k):
            pass
    out = tmp_path / "b"
    rec = history.run_session("billing-H1", stub(), "stub", out, meter=CapOnThird())
    assert rec["complete"] is False and rec["problem"].startswith("spend cap")
    assert lines(out / "billing-H1") == [(1, rec["problem"])]

    # numbering takes the highest number, so a gap never overwrites an earlier transcript
    out = tmp_path / "c"
    d = out / "billing-H1"
    d.mkdir(parents=True)
    (d / "attempt-2.transcript.jsonl").write_text("A2")
    (d / "attempts.jsonl").write_text(json.dumps({"attempt": 2, "problem": "x"}) + "\n")
    (d / "transcript.jsonl").write_text("A3")
    assert history.run_session("billing-H1", stub(), "stub", out)["attempt"] == 4
    assert (d / "attempt-2.transcript.jsonl").read_text() == "A2" and (d / "attempt-3.transcript.jsonl").read_text() == "A3"
    assert [a for a, _ in lines(d)] == [2, 3]


def test_history_workspace_is_removed_when_setup_fails(tmp_path, monkeypatch):
    from smb import history
    from smb.stub import HistoryStub, StubClient
    from smb.memory.corpus import history_specs
    monkeypatch.setattr(history, "WORK", tmp_path / "work")

    def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(history, "TranscriptWriter", broken)
    spec = history_specs()["billing-H1"]
    with pytest.raises(OSError):
        history.run_session("billing-H1", StubClient(HistoryStub({**spec, "id": "billing-H1"})), "stub", tmp_path / "hist")
    assert list((tmp_path / "work" / "h").iterdir()) == []
    line = json.loads((tmp_path / "hist" / "billing-H1" / "attempts.jsonl").read_text())
    assert line["attempt"] == 1 and line["problem"] == "error: OSError: disk full"
