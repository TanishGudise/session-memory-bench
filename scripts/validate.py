"""G1 validation ($0). Writes validation/report.json and prints a summary; exits non-zero on any failure.

  python scripts/validate.py [--repeats 5] [--workers 8]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smb import netguard  # noqa: E402
from smb.grade import grade_tree, run_visible  # noqa: E402
from smb.history import history_task  # noqa: E402
from smb.leakage import find_leaks  # noqa: E402
from smb.memory.corpus import authored_spans, chat_messages, history_specs, lessons  # noqa: E402
from smb.paths import ROOT  # noqa: E402
from smb.repos import main_state, repo_language, state  # noqa: E402
from smb.tasks import all_tasks  # noqa: E402

REPOS = ["billing", "notify", "inventory", "ingest"]
CHECKS_FAIL_ON_START = {"billing-H1", "billing-H5", "notify-H3", "notify-H5", "inventory-H3", "ingest-H3"}
CHECKS_PASS_ON_START = {"billing-H3"}


def check(cond: bool, msg: str, errors: list) -> None:
    if not cond:
        errors.append(msg)


def registry(errors: list) -> dict:
    L = lessons()
    specs = history_specs()
    chat = {m["id"]: m for m in chat_messages()}
    tasks = all_tasks()
    fam = Counter(t.family for t in tasks)
    check(dict(fam) == {"M": 14, "D": 4, "S-u": 4, "S-s": 4, "X": 2, "C": 4}, f"family counts {dict(fam)}", errors)
    for t in tasks:
        for lid in t.lessons + t.extra.get("stale_lessons", []) + t.extra.get("other_lessons", []):
            check(lid in L, f"{t.id}: unknown lesson {lid}", errors)
        if t.family in ("S-u", "S-s"):
            check(bool(t.extra.get("stale_lessons")), f"{t.id}: S task without stale_lessons", errors)
            check("stale_rule" in t.solutions(), f"{t.id}: S task without stale_rule solution", errors)
        if t.family == "X":
            check(bool(t.extra.get("other_lessons")) and "other_repo" in t.solutions(), f"{t.id}: X task incomplete", errors)
        if t.family in ("M", "D"):
            check("visible_only" in t.solutions(), f"{t.id}: no visible_only solution", errors)
        check("oracle" in t.solutions(), f"{t.id}: no oracle", errors)
    spans = authored_spans()
    for lid, d in L.items():
        if d["source"] == "repo":
            continue
        for src in d["source"]:
            check(src in specs or src in chat, f"{lid}: unknown source {src}", errors)
            check(any(l == lid for l, _ in spans.get(src, [])), f"{lid}: source {src} does not carry it", errors)
    return {"tasks": len(tasks), "families": dict(fam), "lessons": len(L), "sessions": len(specs), "chat": len(chat)}


def visible_suites(errors: list) -> dict:
    out = {}
    for repo in REPOS:
        lang = repo_language(repo)
        r = run_visible(main_state(repo), lang, "UTC", label=f"main-{repo}")
        out[f"{repo}/main/UTC"] = r.code
        check(r.code == 0, f"{repo}: main visible tests fail under TZ=UTC\n{r.output[-1500:]}", errors)
    r = run_visible(main_state("billing"), "py", "America/Los_Angeles", label="main-billing-la")
    out["billing/main/America/Los_Angeles"] = r.code
    check(r.code != 0 and "test_settlement_cutoff" in r.output and r.output.count("FAILED") == 1,
          "billing: the timezone flake should be the only failure under a non-UTC TZ", errors)
    return out


def history_checks(errors: list) -> dict:
    out = {}
    for sid, spec in sorted(history_specs().items()):
        task = history_task(sid)
        start = task.base_state()
        r = run_visible(start, task.lang, "UTC", label=f"hist-{sid}")
        check(r.code == 0, f"{sid}: start state visible tests fail under UTC\n{r.output[-800:]}", errors)
        row = {"start_visible": r.code}
        if task.has_checks():
            g0 = grade_tree(task, start, "start")
            after = _after(task)
            g1 = grade_tree(task, after, "ref")
            row.update(start=g0["score"], ref=g1["score"])
            if sid in CHECKS_FAIL_ON_START:
                check(g0["score"] == 0, f"{sid}: checks should fail on the start state", errors)
            if sid in CHECKS_PASS_ON_START:
                check(g0["score"] == 1, f"{sid}: checks should pass on the start state", errors)
            check(g1["score"] == 1, f"{sid}: checks should pass on the reference change ({g1.get('output_tail', '')[-600:]})", errors)
        for r_ in spec["review"]:
            if r_["when"].startswith("failed:"):
                check(task.has_checks(), f"{sid}: conditional comment without checks", errors)
        out[sid] = row
    return out


def _after(task) -> dict:
    """Start state plus this session's own reference step (if it merged one)."""
    from datetime import timedelta
    return state(task.repo, before=task.date + timedelta(days=1))


def solution_matrix(errors: list, repeats: int, workers: int) -> dict:
    jobs = []
    for t in all_tasks():
        for s in ["noop", *t.solutions()]:
            for k in range(repeats):
                jobs.append((t, s, k))

    def one(job):
        t, s, k = job
        r = grade_tree(t, t.solution_state(s), f"{s}{k}")
        return t.id, s, k, r

    with ThreadPoolExecutor(workers) as ex:
        results = list(ex.map(one, jobs))
    by = {}
    for tid, s, k, r in results:
        by.setdefault((tid, s), []).append(r)
    out = {}
    tasks = {t.id: t for t in all_tasks()}
    for (tid, s), rs in sorted(by.items()):
        sigs = {json.dumps([r["status"], r["score"], r["tests"]], sort_keys=True) for r in rs}
        check(len(sigs) == 1, f"{tid}/{s}: nondeterministic grade over {len(rs)} repeats", errors)
        r = rs[0]
        lesson_fail = any(v != "pass" for n, v in r["tests"].items() if "lesson" in n)
        diag_pass = any(v == "pass" for v in (r.get("diag") or {}).values())
        if s == "oracle":
            check(r["score"] == 1 and not diag_pass, f"{tid}: oracle should pass with no diagnostic firing ({r['status']})", errors)
        elif s == "noop":
            check(r["score"] == 0, f"{tid}: noop should fail", errors)
        elif s == "visible_only":
            check(r["score"] == 0 and lesson_fail, f"{tid}: visible_only should fail a lesson test", errors)
        elif s in ("stale_rule", "other_repo"):
            check(r["score"] == 0 and lesson_fail and diag_pass, f"{tid}: {s} should fail a lesson test and fire a diagnostic", errors)
        out[f"{tid}/{s}"] = {"status": r["status"], "score": r["score"], "repeats": len(rs), "lesson_fail": lesson_fail,
                             "diag_pass": diag_pass}
    # the visible suites must not reveal the lesson: every non-noop solution passes them under CI's TZ
    for t in tasks.values():
        for s in t.solutions():
            v = run_visible(t.solution_state(s), t.lang, "UTC", label=f"{t.id}-{s}")
            out[f"{t.id}/{s}"]["visible_utc"] = v.code
            check(v.code == 0, f"{t.id}/{s}: visible tests fail under UTC\n{v.output[-800:]}", errors)
    return out


def evidence(errors: list) -> dict:
    out = {}
    for lid, d in lessons().items():
        if d["kind"] != "M":
            continue
        files = main_state(lid.split(".")[0])
        hits = [f"{rel}:{i}" for pat in d["evidence"] for rel, data in files.items()
                for i, line in enumerate(data.decode(errors="replace").splitlines(), 1) if re.search(pat, line, re.I)]
        out[lid] = hits
        check(not hits, f"{lid}: memory-only lesson has evidence in the eval-time repo: {hits[:5]}", errors)
    return out


def leakage(errors: list) -> dict:
    """No oracle line that the task adds, and no hidden-test string literal, appears in any memory text we wrote.
    (The frozen corpus, with the agents' own transcripts, is checked again at freeze-corpus.)"""
    texts = [s["ticket"] for s in history_specs().values()] + [r["text"] for s in history_specs().values() for r in s["review"]]
    texts += [m["text"] for m in chat_messages()]
    leaks = find_leaks(texts, strict=True)
    for tid, hit in leaks.items():
        errors.append(f"{tid}: leaks into memory texts: {hit[:3]}")
    return leaks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    netguard.install()
    errors: list[str] = []
    report = {"registry": registry(errors), "visible": visible_suites(errors), "history": history_checks(errors),
              "evidence": evidence(errors), "leakage": leakage(errors),
              "solutions": solution_matrix(errors, args.repeats, args.workers)}
    stub = ROOT / "runs" / "stub" / "summary.json"
    if stub.exists():
        s = json.loads(stub.read_text())
        t = s["table"]
        check(not s["bad"], f"stub e2e had bad episodes: {s['bad'][:5]}", errors)
        for fam, want in {"M": 0, "D": 0}.items():
            check(t[f"a/{fam}"][0] == want, f"stub: none/{fam} should be {want}", errors)
        for fam in ("M", "D", "S-u", "S-s", "X", "C"):
            check(t[f"g/{fam}"][0] == t[f"g/{fam}"][1], f"stub: oracle/{fam} should pass every task", errors)
        report["stub_e2e"] = {"episodes": s["episodes"], "table": t}
    else:
        errors.append("stub e2e summary missing: run scripts/stub_e2e.py first")
    report["errors"] = errors
    out = ROOT / "validation" / "report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True))
    n_sol = len(report["solutions"])
    print(f"tasks {report['registry']['tasks']}, solution cells {n_sol} x {args.repeats} repeats, "
          f"history sessions {len(report['history'])}, errors {len(errors)}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
