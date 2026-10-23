"""Eval episodes: one (task, condition, epoch) per episode, graded by hidden tests, resumable."""

from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from pathlib import Path

from smb.agent import Episode, Limits, system_prompt, tool_specs
from smb.grade import grade_workspace
from smb.memory.provider import CONDITIONS, Oracle, Pull
from smb.meter import Meter
from smb.paths import WORK
from smb.repos import write_tree
from smb.tasks import Task
from smb.tools import Workspace
from smb.transcript import TranscriptWriter

_LOCK = threading.Lock()
FINAL_STOPS = {"finished", "no_finish", "call_limit", "context_limit", "wall_clock", "refusal"}


def run_episode(task: Task, cond: str, epoch: int, client, model: str, providers: dict, run_dir: Path,
                meter: Meter | None, limits: Limits | None = None, output_config: dict | None = None,
                corpus_sha256: str = "") -> dict:
    name = CONDITIONS[cond]
    ep_id = f"{task.id}__{cond}__e{epoch}"
    ep_dir = run_dir / "episodes" / ep_id
    ws_dir = WORK / "w" / uuid.uuid4().hex[:12] / task.repo
    write_tree(task.base_state(), ws_dir)
    ws = Workspace(ws_dir, task.lang, pid_dir=WORK / "pids")
    if name == "oracle":
        provider = Oracle(task.lessons)
    elif name == "pull":  # per-episode wrapper over the shared index, so search calls aren't mixed across threads
        provider = Pull(providers["pull"].index, providers["pull"].budget)
    else:
        provider = providers[name]
    workspace = {"repo": task.repo, "branch": task.branch}
    recall = provider.recall(task.prompt, "", workspace)
    first = task.prompt + ("\n\n" + recall.block if recall.block else "")
    pull = name == "pull"
    tw = TranscriptWriter(ep_dir / "transcript.jsonl", str(uuid.uuid4()), f"/work/{task.repo}", task.branch)
    ep = Episode(client=client, model=model, system=system_prompt(task.repo, task.branch, pull=pull),
                 tools=tool_specs(pull=pull), ws=ws, meter=meter, transcript=tw,
                 memory_search=provider.search if pull else None, limits=limits or Limits(), output_config=output_config)
    t0 = time.monotonic()
    try:
        try:
            stop = ep.user_turn(first)
        except Exception as exc:  # noqa: BLE001 - recorded, the run continues
            stop = f"error: {type(exc).__name__}: {exc}"[:300]
        grade = grade_workspace(task, ws.files(), label=cond) if stop in FINAL_STOPS else None
        searched = provider.calls if pull else []
        seen = set(recall.lessons) | {l for r in searched for l in r.lessons}
        seen_patterns = set(recall.pattern_lessons) | {l for r in searched for l in r.pattern_lessons}
        result = {
            "episode": ep_id, "task": task.id, "repo": task.repo, "family": task.family, "condition": cond,
            "condition_name": name, "epoch": epoch, "model": model, "corpus_sha256": corpus_sha256, "stop": stop,
            # PREREGISTRATION: context_limit, call_limit, wall_clock, no_finish and refusal count as fails
            "score": (grade["score"] if stop == "finished" else 0) if grade else None,
            "graded_score": grade["score"] if grade else None, "grade_status": grade["status"] if grade else None,
            "tests": grade["tests"] if grade else {}, "diag": grade.get("diag", {}) if grade else {},
            "suspicious": grade.get("suspicious", []) if grade else [],
            "lessons": task.lessons, "stale_lessons": task.extra.get("stale_lessons", []),
            "other_lessons": task.extra.get("other_lessons", []),
            "retrieved": sorted(seen), "retrieved_patterns": sorted(seen_patterns),
            "memory_sources": recall.sources + [s for r in searched for s in r.sources],
            "memory_chars": recall.chars, "memory_meta": recall.meta,
            "search_queries": [r.meta.get("query", "") for r in searched],
            "calls": ep.calls, "usage": dict(ep.usage), "cost": round(ep.cost, 6), "tool_counts": dict(ep.tool_counts),
            "reads_before_first_edit": ep.reads_before_first_edit, "first_edit_call": ep.first_edit_call,
            "test_runs": ws.test_runs, "seconds": round(time.monotonic() - t0, 2),
        }
        (ep_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
        with _LOCK:
            with open(run_dir / "results.jsonl", "a") as fh:
                fh.write(json.dumps(result, default=str) + "\n")
                fh.flush()
        return result
    finally:
        shutil.rmtree(ws_dir.parent, ignore_errors=True)


def done_episodes(run_dir: Path) -> set[str]:
    f = run_dir / "results.jsonl"
    if not f.exists():
        return set()
    return {json.loads(l)["episode"] for l in f.read_text().splitlines()
            if l.strip() and json.loads(l)["stop"] in FINAL_STOPS}
