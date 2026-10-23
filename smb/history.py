"""History phase: run the agent on each earlier task, then post the scripted PR review and give it one revision
round. The transcripts are the memory every condition draws from; the corpus is frozen before any eval run.

A review always posts its `always` comments, and posts a `failed:<check>` comment only when that check fails
on the agent's first submission. Merged or closed, what lands on main is the reference step in repos/, not the
agent's diff (as when a teammate finishes a PR before merging)."""

from __future__ import annotations

import fnmatch
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from smb.agent import Episode, Limits, system_prompt, tool_specs
from smb.grade import grade_workspace
from smb.memory.corpus import history_specs
from smb.meter import Meter
from smb.paths import HISTORY, WORK
from smb.repos import repo_language, state, write_tree
from smb.tasks import FORBIDDEN_NAMES
from smb.tools import Workspace
from smb.transcript import TranscriptWriter

REVISION_LIMITS = Limits(max_calls=12)


@dataclass
class HistoryTask:
    id: str
    repo: str
    date: date
    editable: list[str]
    grader_tz: str = "America/Los_Angeles"

    @property
    def lang(self) -> str:
        return repo_language(self.repo)

    def base_state(self) -> dict[str, bytes]:
        return state(self.repo, before=self.date)

    def hidden_files(self) -> dict[str, bytes]:
        root = HISTORY / "checks" / self.id
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    def has_checks(self) -> bool:
        return (HISTORY / "checks" / self.id).exists()

    def is_editable(self, rel: str) -> bool:
        if Path(rel).name in FORBIDDEN_NAMES or rel.endswith(".pth"):
            return False
        return any(fnmatch.fnmatchcase(rel, g) for g in self.editable)


def history_task(sid: str) -> HistoryTask:
    s = history_specs()[sid]
    d = s["date"] if isinstance(s["date"], date) else date.fromisoformat(str(s["date"]))
    return HistoryTask(id=sid, repo=s["repo"], date=d, editable=s["editable"])


def review_message(spec: dict, failed_checks: set[str]) -> tuple[str, list[dict]]:
    posted = [r for r in spec["review"] if r["when"] == "always"
              or (r["when"].startswith("failed:") and r["when"][len("failed:"):] in failed_checks)]
    text = f"Review from {spec['author']} on {spec['branch']}:\n\n" + "\n\n".join(r["text"].strip() for r in posted)
    if spec["outcome"] == "closed":
        text += "\n\n(The PR was closed.)"
    return text, posted


def _attempt_numbers(sess_dir: Path) -> list[int]:
    return [int(p.name.split(".")[0].split("-")[1]) for p in sess_dir.glob("attempt-*.transcript.jsonl")]


def _logged_attempts(sess_dir: Path) -> set[int]:
    f = sess_dir / "attempts.jsonl"
    return {json.loads(l).get("attempt") for l in f.read_text().splitlines() if l.strip()} if f.exists() else set()


def _not_kept(sess_dir: Path, record: dict) -> None:
    """Record an attempt that stays out of the corpus; attempts.jsonl gets one line per discarded attempt."""
    sess_dir.mkdir(parents=True, exist_ok=True)
    (sess_dir / "session.partial.json").write_text(json.dumps(record, indent=2))
    with open(sess_dir / "attempts.jsonl", "a") as fh:
        fh.write(json.dumps(record) + "\n")


def run_session(sid: str, client, model: str, out_dir: Path, meter: Meter | None = None, limits: Limits | None = None) -> dict:
    spec = history_specs()[sid]
    task = history_task(sid)
    sess_dir = out_dir / sid
    earlier = sess_dir / "transcript.jsonl"
    if earlier.exists():  # an attempt that wasn't kept: its transcript stays beside the new one
        n = 1 + max(_attempt_numbers(sess_dir), default=0)
        earlier.rename(sess_dir / f"attempt-{n}.transcript.jsonl")
        if n not in _logged_attempts(sess_dir):  # the process was killed before it could write a record
            _not_kept(sess_dir, {"id": sid, "repo": spec["repo"], "attempt": n, "complete": False,
                                 "problem": "ended without a record (process killed)"})
    attempt = 1 + max(_attempt_numbers(sess_dir), default=0) if sess_dir.exists() else 1
    ws_dir = WORK / "h" / uuid.uuid4().hex[:12] / spec["repo"]
    try:  # everything after the mkdir sits inside the try, so the finally always removes the workspace
        write_tree(task.base_state(), ws_dir)
        ws = Workspace(ws_dir, task.lang, pid_dir=WORK / "pids")
        start = datetime(task.date.year, task.date.month, task.date.day, 15, 0, tzinfo=timezone.utc)
        tw = TranscriptWriter(sess_dir / "transcript.jsonl", str(uuid.uuid5(uuid.NAMESPACE_URL, f"smb/{sid}")),
                              f"/work/{spec['repo']}", spec["branch"], start=start)
        ep = Episode(client=client, model=model, system=system_prompt(spec["repo"], spec["branch"]), tools=tool_specs(),
                     ws=ws, meter=meter, transcript=tw, limits=limits or Limits())
        stop_task = ep.user_turn(spec["ticket"].strip())
        checks, harness_problem = None, None
        if task.has_checks():
            snap = ws.files(keep=task.is_editable)
            if ws.skipped:
                harness_problem = f"snapshot over budget ({ws.skipped} files left out)"
            else:
                checks = grade_workspace(task, snap, label="hist")
                if checks["status"] not in ("graded", "collection_error"):
                    harness_problem = f"checks not graded: {checks['status']}"
        if harness_problem:  # never post review comments from a broken check run; keep the session out of the corpus
            record = {"id": sid, "repo": spec["repo"], "attempt": attempt, "stop_task": stop_task, "stop_review": None, "checks_failed": [],
                      "complete": False, "problem": harness_problem, "calls": ep.calls, "usage": dict(ep.usage),
                      "cost": round(ep.cost, 6)}
            _not_kept(sess_dir, record)
            return record
        failed = {n for n, v in (checks or {}).get("tests", {}).items() if v != "pass"}
        text, posted = review_message(spec, failed)
        ep.limits = REVISION_LIMITS
        stop_review = ep.user_turn(text)
        record = {
            "id": sid, "repo": spec["repo"], "attempt": attempt, "date": str(spec["date"]), "author": spec["author"], "branch": spec["branch"],
            "outcome": spec["outcome"], "model": model, "stop_task": stop_task, "stop_review": stop_review,
            "checks_status": (checks or {}).get("status"),
            "checks_failed": sorted(failed), "review_posted": [{"when": r["when"], "lessons": r["lessons"]} for r in posted],
            "calls": ep.calls, "usage": dict(ep.usage), "cost": round(ep.cost, 6), "tool_counts": dict(ep.tool_counts),
            "edited": sorted(set(ws.edits)),
        }
        final = {"finished", "no_finish", "call_limit", "context_limit", "wall_clock", "refusal"}
        complete = stop_task in final and stop_review in final
        record["complete"] = complete
        # an incomplete session (spend cap, API error) is never frozen into the corpus; a resume runs it again
        if complete:
            (sess_dir / "session.json").write_text(json.dumps(record, indent=2))
        else:
            _not_kept(sess_dir, record)
        return record
    except BaseException as exc:  # an API error, a harness failure or Ctrl-C: record the attempt, then let it propagate
        _not_kept(sess_dir, {"id": sid, "repo": spec["repo"], "attempt": attempt, "complete": False,
                             "problem": f"error: {type(exc).__name__}: {exc}"[:300]})
        raise
    finally:
        shutil.rmtree(ws_dir.parent, ignore_errors=True)
