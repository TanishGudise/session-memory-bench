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


def run_session(sid: str, client, model: str, out_dir: Path, meter: Meter | None = None, limits: Limits | None = None) -> dict:
    spec = history_specs()[sid]
    task = history_task(sid)
    ws_dir = WORK / "h" / uuid.uuid4().hex[:12] / spec["repo"]
    write_tree(task.base_state(), ws_dir)
    ws = Workspace(ws_dir, task.lang, pid_dir=WORK / "pids")
    sess_dir = out_dir / sid
    start = datetime(task.date.year, task.date.month, task.date.day, 15, 0, tzinfo=timezone.utc)
    tw = TranscriptWriter(sess_dir / "transcript.jsonl", str(uuid.uuid5(uuid.NAMESPACE_URL, f"smb/{sid}")),
                          f"/work/{spec['repo']}", spec["branch"], start=start)
    ep = Episode(client=client, model=model, system=system_prompt(spec["repo"], spec["branch"]), tools=tool_specs(),
                 ws=ws, meter=meter, transcript=tw, limits=limits or Limits())
    try:
        stop_task = ep.user_turn(spec["ticket"].strip())
        checks = grade_workspace(task, ws.files(), label="hist") if task.has_checks() else None
        failed = {n for n, v in (checks or {}).get("tests", {}).items() if v != "pass"}
        text, posted = review_message(spec, failed)
        ep.limits = REVISION_LIMITS
        stop_review = ep.user_turn(text)
        record = {
            "id": sid, "repo": spec["repo"], "date": str(spec["date"]), "author": spec["author"], "branch": spec["branch"],
            "outcome": spec["outcome"], "model": model, "stop_task": stop_task, "stop_review": stop_review,
            "checks_failed": sorted(failed), "review_posted": [{"when": r["when"], "lessons": r["lessons"]} for r in posted],
            "calls": ep.calls, "usage": dict(ep.usage), "cost": round(ep.cost, 6), "tool_counts": dict(ep.tool_counts),
            "edited": sorted(set(ws.edits)),
        }
        final = {"finished", "no_finish", "call_limit", "context_limit", "wall_clock", "refusal"}
        complete = stop_task in final and stop_review in final
        record["complete"] = complete
        # an incomplete session (spend cap, API error) is never frozen into the corpus; a resume runs it again
        (sess_dir / ("session.json" if complete else "session.partial.json")).write_text(json.dumps(record, indent=2))
        return record
    finally:
        shutil.rmtree(ws_dir.parent, ignore_errors=True)
