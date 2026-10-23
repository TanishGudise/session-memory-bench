"""Stub models for $0 end-to-end runs. They exercise every piece of the harness (tools, memory injection, pull
search, review rounds, transcripts, grading, metering) without an API call.

EvalStub is a "perfect applier": it writes the oracle solution when its context (prompt, injected memory,
search results) contains the authored text of every lesson the task needs, the stale or other-repo solution when
it only sees the outdated or other repo's rule, and the visible-only solution otherwise. Its pass rates are an
upper bound on what each memory condition can deliver on the stub corpus, not a model result.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from smb.memory.corpus import authored_spans, carries, lessons
from smb.paths import REPOS


def _text_of(messages: list[dict]) -> str:
    out = []
    for m in messages:
        for b in m["content"]:
            if b.get("type") == "text":
                out.append(b["text"])
            elif b.get("type") == "tool_result":
                c = b.get("content")
                out.append(c if isinstance(c, str) else json.dumps(c))
    return "\n".join(out)


def _tool(name: str, **inp) -> dict:
    return {"type": "tool_use", "id": f"toolu_{uuid.uuid4().hex[:20]}", "name": name, "input": inp}


def lesson_known(lesson_id: str, context: str) -> bool:
    L = lessons()
    if carries(context, L[lesson_id]["note"]):
        return True
    return any(carries(context, text) for spans in authored_spans().values() for lid, text in spans if lid == lesson_id)


class StubClient:
    def __init__(self, policy):
        self.policy = policy
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        blocks, stop = self.policy.step(kw["messages"], kw.get("tools", []))
        chars = len(json.dumps(kw["messages"])) + len(json.dumps(kw.get("tools", []))) + len(json.dumps(kw.get("system", "")))
        usage = SimpleNamespace(input_tokens=int(chars / 3.5), output_tokens=60, cache_read_input_tokens=0,
                                cache_creation_input_tokens=0)
        return SimpleNamespace(content=[dict(b) for b in blocks], stop_reason=stop, usage=usage)


class EvalStub:
    def __init__(self, task, pull: bool = False):
        self.task, self.pull, self.state, self.choice = task, pull, 0, None

    def choose(self, context: str) -> str:
        t = self.task
        sols = set(t.solutions())
        if t.family == "C":
            return "oracle"
        known = all(lesson_known(l, context) for l in t.lessons)
        if t.family in ("M", "D"):
            return "oracle" if known else "visible_only"
        if t.family in ("S-u", "S-s"):
            stale = any(lesson_known(l, context) for l in t.extra.get("stale_lessons", []))
            return "oracle" if known or not stale else ("stale_rule" if "stale_rule" in sols else "oracle")
        if t.family == "X":
            other = any(lesson_known(l, context) for l in t.extra.get("other_lessons", []))
            return "other_repo" if other and not known else "oracle"
        raise ValueError(t.family)

    def step(self, messages, tools):
        self.state += 1
        if self.state == 1 and self.pull:
            return [_tool("search_memory", query=self.task.prompt[:400])], "tool_use"
        if self.choice is None:
            self.choice = self.choose(_text_of(messages))
            root = self.task.path / "solutions" / self.choice
            writes = [_tool("write_file", path=p.relative_to(root).as_posix(), content=p.read_text())
                      for p in sorted(root.rglob("*")) if p.is_file() and p.name != "DELETE"]
            return [{"type": "text", "text": f"Applying {len(writes)} file(s)."}, *writes], "tool_use"
        if self.state <= 4:
            return [_tool("run_tests")], "tool_use"
        return [_tool("finish", summary=f"stub: {self.choice}")], "tool_use"


class HistoryStub:
    """Writes the reference change that later landed on main (if any), then acknowledges the review."""

    def __init__(self, spec: dict):
        self.spec, self.state = spec, 0

    def _step_dir(self):
        d = self.spec["date"]
        mmdd = f"{d.month:02d}{d.day:02d}" if hasattr(d, "month") else str(d)[5:7] + str(d)[8:10]
        p = REPOS / self.spec["repo"] / "steps" / f"{mmdd}-{self.spec['id'].split('-')[-1]}"
        return p if p.exists() else None

    def step(self, messages, tools):
        self.state += 1
        last = messages[-1]["content"]
        if any(b.get("type") == "text" and b["text"].startswith("Review from") for b in last):
            return [{"type": "text", "text": "Thanks, noted."}, _tool("finish", summary="Addressed the review.")], "tool_use"
        if self.state == 1:
            return [_tool("list_dir", path=".")], "tool_use"
        if self.state == 2:
            step = self._step_dir()
            files = [p for p in sorted(step.rglob("*")) if p.is_file() and p.name != "DELETE"] if step else []
            if files:
                return [_tool("write_file", path=p.relative_to(step).as_posix(), content=p.read_text()) for p in files], "tool_use"
            return [{"type": "text", "text": "Investigated; no code change needed."}], "end_turn"
        return [_tool("finish", summary="Done.")], "tool_use"
