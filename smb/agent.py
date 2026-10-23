"""Minimal agent loop on the Messages API: the model, a fixed system prompt, the tools in smb.tools, and
nothing else. One loop serves eval episodes (one user turn) and history sessions (task, then a review)."""

from __future__ import annotations

import json
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from smb.meter import CapReached, Meter
from smb.tools import SEARCH_MEMORY_SPEC, TOOL_SPECS, ToolError, Workspace
from smb.transcript import TranscriptWriter

SYSTEM = (
    "You are a coding agent working in the {repo} repository at Larkspur, on the branch {branch}. A teammate has asked "
    "you to do a task. Use the tools to read the code, make the change, and run the tests. You can't run shell "
    "commands; use the tools provided. When you are done, call finish with a short summary of what you changed."
)
SYSTEM_PULL = " You can search your team's memory of earlier agent sessions, PR reviews and chat with search_memory."
NUDGE = "Continue with the task, or call finish if you're done."
CUT_OFF = "Your last reply was cut off. Continue, keeping each reply shorter."
CUT_OFF_TOOL = "error: your reply was cut off before this tool call was complete, so it was not run. Try again with a shorter call."
API_ATTEMPTS = 3          # the SDK client is built with max_retries=0; the loop retries, reserving again each time
RETRY_SLEEP = (2.0, 8.0)
DEADLINE_SLACK = 120.0    # a call is abandoned this long after its own HTTP timeout, whatever the socket is doing


class CallDeadline(Exception):
    """The request neither returned nor failed by its hard deadline. A socket read that keeps receiving bytes never
    hits the HTTP read timeout (a history session hung 50 minutes on one call), so the wait is bounded here."""


def _with_deadline(fn: Callable[[], object], seconds: float):
    box: dict = {}

    def run():
        try:
            box["resp"] = fn()
        except BaseException as exc:  # noqa: BLE001 - handed back to the caller's thread
            box["exc"] = exc

    t = threading.Thread(target=run, daemon=True)  # an abandoned call keeps only its own client's connection
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise CallDeadline(f"no response after {seconds:.0f}s")
    if "exc" in box:
        raise box["exc"]
    return box["resp"]


def _transient(exc: Exception) -> bool:
    """Errors worth retrying: connection problems, timeouts, rate limits, server errors."""
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    return name in ("APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError", "OverloadedError",
                    "CallDeadline") \
        or (isinstance(status, int) and (status == 429 or status >= 500))


def _maybe_billed(exc: Exception) -> bool:
    """A request that may have been processed (timeout, dropped connection, server error) counts at its worst case."""
    status = getattr(exc, "status_code", None)
    return not (isinstance(status, int) and 400 <= status < 500)


def metered_create(client, meter: Meter | None, model: str, reserve_system: str, messages: list, reserve_tools: list,
                   max_tokens: int, **kwargs) -> tuple[object | None, float]:
    """One model request with the spend rules: every attempt reserves its worst case first; an attempt that may
    have been billed without returning usage is booked at that worst case; transient errors are retried up to
    API_ATTEMPTS times. Returns (response, cost), or (None, cost) when the cap refuses a reservation."""
    cost = 0.0
    for attempt in range(API_ATTEMPTS):
        ticket = None
        if meter is not None:
            try:
                ticket = meter.reserve(model, reserve_system, messages, reserve_tools, max_tokens)
            except CapReached:
                return None, cost
        try:
            resp = _with_deadline(lambda: client.messages.create(model=model, max_tokens=max_tokens, messages=messages, **kwargs),
                                  float(kwargs.get("timeout") or 180.0) + DEADLINE_SLACK)
        except Exception as exc:
            if ticket is not None:
                if _maybe_billed(exc):
                    cost += meter.settle_worst(ticket, model)
                else:
                    meter.release(ticket)
            if not _transient(exc) or attempt == API_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_SLEEP[min(attempt, len(RETRY_SLEEP) - 1)])
            continue
        if ticket is not None:
            cost += meter.settle(ticket, model, _usage(resp))
        return resp, cost
    raise AssertionError("unreachable")


@dataclass
class Limits:
    max_calls: int = 30          # model calls per user turn
    max_tokens: int = 8000       # per call (thinking + text + tool input)
    prompt_guard: int = 95_000   # never send a request estimated above this many input tokens (100k price tier)
    wall_clock: float = 600.0    # seconds per user turn
    http_timeout: float = 180.0


@dataclass
class Episode:
    client: object
    model: str
    system: str
    tools: list[dict]
    ws: Workspace
    meter: Meter | None
    transcript: TranscriptWriter
    memory_search: Callable[[str], str] | None = None
    limits: Limits = field(default_factory=Limits)
    output_config: dict | None = None
    messages: list[dict] = field(default_factory=list)
    usage: Counter = field(default_factory=Counter)
    calls: int = 0
    tool_counts: Counter = field(default_factory=Counter)
    cost: float = 0.0
    summary: str | None = None
    first_edit_call: int | None = None
    reads_before_first_edit: int = 0
    memory_queries: list[dict] = field(default_factory=list)
    _last_input_total: int = 0
    _chars_since_call: int = 0

    def _append(self, msg: dict) -> None:
        self.messages.append(msg)
        self._chars_since_call += len(json.dumps(msg["content"], ensure_ascii=False, default=str))

    def estimate_prompt_tokens(self) -> int:
        # previous request's full input + its output (now part of the history) + new content at 2 chars/token
        return self._last_input_total + self._chars_since_call // 2

    def user_turn(self, text: str) -> str:
        """Send a user message and run the loop until finish or a limit. Returns the stop reason."""
        content = [{"type": "text", "text": text}]
        self._append({"role": "user", "content": content})
        self.transcript.add("user", content)
        t0 = time.monotonic()
        turn_calls = nudges = 0
        while True:
            if turn_calls >= self.limits.max_calls:
                return "call_limit"
            if time.monotonic() - t0 > self.limits.wall_clock:
                return "wall_clock"
            if self.estimate_prompt_tokens() > self.limits.prompt_guard:
                return "context_limit"
            extra = {"output_config": self.output_config} if self.output_config else {}
            resp, cost = metered_create(self.client, self.meter, self.model, self.system, self.messages, self.tools,
                                            self.limits.max_tokens, system=[{"type": "text", "text": self.system}],
                                            tools=self.tools, cache_control={"type": "ephemeral"},
                                            timeout=self.limits.http_timeout, **extra)
            if resp is None:
                return "cap"
            self.cost += cost
            turn_calls += 1
            self.calls += 1
            u = _usage(resp)
            self.usage.update(u)
            self._last_input_total = u["input"] + u["cache_read"] + u["cache_write"] + u["output"]
            self._chars_since_call = 0
            blocks = [_block_dict(b) for b in resp.content]
            self.messages.append({"role": "assistant", "content": blocks})
            self.transcript.add("assistant", blocks, meta={"usage": u, "stop_reason": resp.stop_reason})
            if resp.stop_reason == "refusal":
                return "refusal"
            tool_uses = [b for b in blocks if b.get("type") == "tool_use"]
            if not tool_uses:
                nudges += 1
                if nudges > 2:
                    return "no_finish"
                note = [{"type": "text", "text": CUT_OFF if resp.stop_reason == "max_tokens" else NUDGE}]
                self._append({"role": "user", "content": note})
                self.transcript.add("user", note, meta={"harness": True})
                continue
            results, finished = [], False
            truncated = resp.stop_reason == "max_tokens"
            for tu in tool_uses:
                name, args = tu["name"], tu.get("input") or {}
                self.tool_counts[name] += 1
                is_error = False
                if truncated:  # the last tool call may be incomplete: run none of this reply's calls
                    results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": CUT_OFF_TOOL, "is_error": True})
                    continue
                if self.first_edit_call is None:
                    if name in ("write_file", "replace_in_file"):
                        self.first_edit_call = self.calls
                    elif name in ("read_file", "search_code", "list_dir", "search_memory"):
                        self.reads_before_first_edit += 1
                try:
                    if not isinstance(args, dict):
                        raise ToolError("tool input must be an object")
                    if name == "finish":
                        finished = True
                        self.summary = str(args.get("summary", ""))
                        out = "ok"
                    elif name == "search_memory" and self.memory_search is not None:
                        # a failure here is the harness's (retriever), so it propagates and the episode is an error
                        out = self.memory_search(str(args.get("query", "")))
                        self.memory_queries.append({"query": str(args.get("query", "")), "call": self.calls})
                    else:
                        out = self.ws.call(name, args)  # argument and path mistakes come back as ToolError
                except ToolError as exc:
                    out, is_error = f"error: {exc}", True
                results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": out, **({"is_error": True} if is_error else {})})
            self._append({"role": "user", "content": results})
            self.transcript.add("user", results)
            if finished:
                return "finished"


def _usage(resp) -> dict:
    u = resp.usage
    get = (lambda k: getattr(u, k, 0) or 0) if not isinstance(u, dict) else (lambda k: u.get(k, 0) or 0)
    return {"input": get("input_tokens"), "output": get("output_tokens"),
            "cache_read": get("cache_read_input_tokens"), "cache_write": get("cache_creation_input_tokens")}


def _block_dict(b) -> dict:
    if isinstance(b, dict):
        return b
    if hasattr(b, "to_dict"):
        return b.to_dict()
    return dict(vars(b))


def system_prompt(repo: str, branch: str, pull: bool = False) -> str:
    return SYSTEM.format(repo=repo, branch=branch) + (SYSTEM_PULL if pull else "")


def tool_specs(pull: bool = False) -> list[dict]:
    specs = list(TOOL_SPECS)
    if pull:
        specs.insert(len(specs) - 1, SEARCH_MEMORY_SPEC)
    return specs
