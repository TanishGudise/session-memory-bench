"""Memory conditions. Every condition is a MemoryProvider; only what it returns differs between conditions.

recall(prompt, prior_assistant_turn, workspace) mirrors the payload a session-memory hook gets when the user
submits a prompt (the prompt, the previous assistant turn, and repo/branch). The returned block is appended to
the task prompt. The pull condition injects nothing and answers search_memory tool calls instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from smb.memory.corpus import Chunk, authored_spans, carries, chat_messages, history_specs, lessons, render_blocks
from smb.memory.retriever import Index
from smb.transcript import read as read_transcript

CONDITIONS = {"a": "none", "b": "raw", "c": "retrieved", "d": "distilled", "f": "pull", "g": "oracle"}
RETRIEVED_CHARS = 7000      # condition c, and each search_memory result in f
DISTILLED_CHARS = 3500      # condition d
RAW_TOKENS = 40_000         # condition b (pre-registered cap; counted with the model's token counter)
RAW_TOOL_INPUT = 2000
RAW_TOOL_RESULT = 800
INTRO = ("Context from your team's earlier agent sessions, PR reviews and chat, recalled for this task. "
         "Each entry shows its date and where it came from.")
INTRO_RAW = "Transcripts of your team's earlier agent sessions in this repository (newest first), and recent team chat."


@dataclass
class Recall:
    block: str = ""
    sources: list[str] = field(default_factory=list)   # chunk/note ids or session ids
    lessons: list[str] = field(default_factory=list)   # span-labelled lessons present in the block
    pattern_lessons: list[str] = field(default_factory=list)
    chars: int = 0
    meta: dict = field(default_factory=dict)


class MemoryProvider(Protocol):
    def recall(self, prompt: str, prior_assistant_turn: str, workspace: dict) -> Recall: ...


def hook_query(prompt: str, prior_assistant_turn: str, workspace: dict) -> str:
    """What the retriever is queried with: submitted prompt + previous assistant turn + repo/branch."""
    parts = [prompt.strip(), prior_assistant_turn.strip(), f"repo: {workspace['repo']} branch: {workspace['branch']}"]
    return "\n".join(p for p in parts if p)


def _wrap(intro: str, entries: list[str]) -> str:
    return "<team-memory>\n" + intro + "\n\n" + "\n\n".join(entries) + "\n</team-memory>"


def _from_chunks(chunks: list[Chunk], intro: str) -> Recall:
    if not chunks:
        return Recall()
    block = _wrap(intro, [f"{c.header()}\n{c.text}" for c in chunks])
    return Recall(block=block, sources=[c.id for c in chunks], chars=len(block),
                  lessons=sorted({l for c in chunks for l in c.lessons}),
                  pattern_lessons=sorted({l for c in chunks for l in c.pattern_lessons}))


class NoMemory:
    def recall(self, prompt, prior_assistant_turn, workspace) -> Recall:
        return Recall()


class Retrieved:
    def __init__(self, index: Index, budget_chars: int = RETRIEVED_CHARS):
        self.index, self.budget = index, budget_chars

    def recall(self, prompt, prior_assistant_turn, workspace) -> Recall:
        r = _from_chunks(self.index.search(hook_query(prompt, prior_assistant_turn, workspace), self.budget), INTRO)
        r.meta["query"] = hook_query(prompt, prior_assistant_turn, workspace)
        return r


class Pull:
    """Nothing injected; search_memory(query) returns chunks from the same index as Retrieved."""

    def __init__(self, index: Index, budget_chars: int = RETRIEVED_CHARS):
        self.index, self.budget = index, budget_chars
        self.calls: list[Recall] = []

    def recall(self, prompt, prior_assistant_turn, workspace) -> Recall:
        return Recall()

    def search(self, query: str) -> str:
        r = _from_chunks(self.index.search(query, self.budget), INTRO)
        r.meta["query"] = query
        self.calls.append(r)
        return r.block or "no results"


class Oracle:
    def __init__(self, lesson_ids: list[str]):
        self.lesson_ids = lesson_ids

    def recall(self, prompt, prior_assistant_turn, workspace) -> Recall:
        if not self.lesson_ids:
            return Recall()
        L = lessons()
        block = _wrap(INTRO, [f"[team note]\n{L[lid]['note']}" for lid in self.lesson_ids])
        return Recall(block=block, sources=list(self.lesson_ids), lessons=list(self.lesson_ids),
                      pattern_lessons=list(self.lesson_ids), chars=len(block))


def render_session_raw(sid: str, spec: dict, transcript: list[dict]) -> str:
    lines = [f"=== Session {spec['date']} · {spec['repo']} · {spec['branch']} · {spec['author']} ({spec['outcome']}) ==="]
    n_user = 0
    for rec in transcript:
        if (rec.get("meta") or {}).get("harness"):
            continue
        role, content = rec["message"]["role"], rec["message"]["content"]
        text = render_blocks(content, RAW_TOOL_INPUT, RAW_TOOL_RESULT)
        if not text.strip():
            continue
        if role == "user" and any(b.get("type") == "text" for b in content):
            n_user += 1
            tag = "[task]" if n_user == 1 else f"[PR review by {spec['author']}]"
        else:
            tag = "[agent]" if role == "assistant" else "[tool output]"
        lines.append(f"{tag} {text}")
    return "\n".join(lines)


def build_raw_blocks(corpus_dir: Path, count_tokens: Callable[[str], int], cap_tokens: int = RAW_TOKENS,
                     repos: list[str] | None = None) -> dict[str, dict]:
    """Condition b's block per repo, computed once at corpus freeze: this repo's sessions newest first, whole
    sessions only, plus all team chat, up to cap_tokens counted by count_tokens."""
    chat = sorted(chat_messages(), key=lambda m: (str(m["date"]), m["id"]), reverse=True)
    spans = authored_spans()
    out = {}
    for repo in sorted({s["repo"] for s in history_specs().values()} if repos is None else repos):
        entries = ["=== Team chat ===\n" + "\n".join(f"[{m['date']} · {m['channel']} · {m['author']}] {m['text'].strip()}" for m in chat)]
        sources = [m["id"] for m in chat]
        specs = sorted(((sid, s) for sid, s in history_specs().items() if s["repo"] == repo),
                       key=lambda kv: (str(kv[1]["date"]), kv[0]), reverse=True)
        included = []
        for sid, spec in specs:
            text = render_session_raw(sid, spec, read_transcript(corpus_dir / sid / "transcript.jsonl"))
            if count_tokens(_wrap(INTRO_RAW, entries + [text])) > cap_tokens:
                break  # whole sessions only, newest first: stop at the first that doesn't fit
            entries.append(text)
            included.append(sid)
        block = _wrap(INTRO_RAW, entries)
        present = sorted({lid for src in sources + included for lid, sp in spans.get(src, []) if carries(block, sp)})
        out[repo] = {"block": block, "sources": sources + included, "lessons": present, "chars": len(block),
                     "tokens": count_tokens(block), "sessions_included": included,
                     "sessions_skipped": [sid for sid, _ in specs if sid not in included]}
    return out


class FrozenRaw:
    """Condition b at eval time: the blocks frozen in raw_blocks.json."""

    def __init__(self, blocks: dict[str, dict]):
        self.blocks = blocks

    def recall(self, prompt, prior_assistant_turn, workspace) -> Recall:
        b = self.blocks[workspace["repo"]]
        return Recall(block=b["block"], sources=list(b["sources"]), lessons=list(b["lessons"]), chars=b["chars"],
                      meta={k: b[k] for k in ("tokens", "sessions_included", "sessions_skipped")})


@dataclass
class Note:
    id: str
    repo: str
    source: str
    date: str
    text: str
    lessons: list[str] = field(default_factory=list)
    pattern_lessons: list[str] = field(default_factory=list)


def notes_as_chunks(notes_path: Path, labels_path: Path) -> list[Chunk]:
    """Distilled notes as retrievable chunks, labelled with the frozen hand labels (notes_labels.json)."""
    labels = json.loads(labels_path.read_text())
    out = []
    for line in notes_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            n = json.loads(line)
            out.append(Chunk(id=n["id"], repo=n["repo"], source=n["source"], kind="note", date=n["date"],
                             author="distilled", where=n.get("where", n["source"]), text=n["text"],
                             lessons=sorted(labels["labels"][n["id"]]), pattern_lessons=n.get("pattern_lessons", [])))
    return out


def estimate_tokens(text: str) -> int:
    """Stub-run stand-in for count_tokens (3.5 characters per token). Paid runs use the API's counter."""
    return int(len(text) / 3.5) + 1
