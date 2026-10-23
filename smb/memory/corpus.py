"""Memory corpus: the history sessions' transcripts plus team chat, cut into dated chunks.

A chunk carries a lesson (span label) when it contains at least SPAN_WINDOW consecutive characters of one of
that lesson's rule spans (lessons.yaml `spans`: the sentence in a ticket, review comment or chat message that
states the rule), or the whole span if it is shorter. Pattern labels (lessons.yaml `patterns`, same repo) are a
secondary label for chunks that paraphrase a lesson.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from smb.paths import EXT, HISTORY, ROOT, ext_on
from smb.transcript import read as read_transcript

MAX_CHUNK = 1600
SPAN_WINDOW = 60
TOOL_INPUT_CLIP = 600
TOOL_RESULT_CLIP = 400
CHANNEL_REPO = {"#billing": "billing", "#brand": "notify", "#ops": "inventory", "#eng": "", "#support": "billing",
                "#compliance": "notify"}


@dataclass
class Chunk:
    id: str
    repo: str
    source: str        # session id or chat id
    kind: str          # ticket | review | assistant | tool_result | chat | note
    date: str
    author: str
    where: str         # branch or channel
    text: str
    lessons: list[str] = field(default_factory=list)          # span labels
    pattern_lessons: list[str] = field(default_factory=list)  # secondary labels

    def header(self) -> str:
        what = {"ticket": "task", "review": "PR review", "assistant": "agent", "tool_result": "tool output",
                "chat": "chat", "note": "note"}[self.kind]
        return f"[{self.date} · {self.repo or 'org'} · {self.where} · {what} · {self.author}]"


def lessons() -> dict:
    out = yaml.safe_load((ROOT / "lessons.yaml").read_text())
    if ext_on():
        extra = yaml.safe_load((EXT / "lessons.yaml").read_text())
        assert not set(extra) & set(out), "extension lessons must have new ids"
        out.update(extra)
    return out


def history_specs() -> dict[str, dict]:
    out = {}
    for f in sorted(HISTORY.glob("*.yaml")):
        if f.name == "chat.yaml":
            continue
        d = yaml.safe_load(f.read_text())
        for s in d["sessions"]:
            out[s["id"]] = {**s, "repo": d["repo"], "editable": d["editable"]}
    return out


def chat_messages() -> list[dict]:
    msgs = yaml.safe_load((HISTORY / "chat.yaml").read_text())["messages"]
    if ext_on():
        msgs = msgs + yaml.safe_load((EXT / "chat.yaml").read_text())["messages"]
    return msgs


def source_texts() -> dict[str, list[tuple[list[str], str]]]:
    """source id -> [(lessons the text is tagged with, text)] for tickets, review comments and chat messages."""
    out: dict[str, list[tuple[list[str], str]]] = {}
    for sid, s in history_specs().items():
        out.setdefault(sid, []).append((list(s.get("ticket_lessons", [])), s["ticket"].strip()))
        for r in s["review"]:
            out[sid].append((list(r["lessons"]), r["text"].strip()))
    for m in chat_messages():
        out.setdefault(m["id"], []).append((list(m["lessons"]), m["text"].strip()))
    return out


def authored_spans() -> dict[str, list[tuple[str, str]]]:
    """source id -> [(lesson id, rule span)], each span checked to be a substring of a text tagged with its lesson."""
    texts = source_texts()
    spans: dict[str, list[tuple[str, str]]] = {}
    for lid, d in lessons().items():
        for src, items in (d.get("spans") or {}).items():
            tagged = [_norm(t) for ls, t in texts.get(src, []) if lid in ls]
            for sp in items:
                if not any(_norm(sp) in t for t in tagged):
                    raise ValueError(f"span for {lid} not found in a {src} text tagged with it: {sp[:60]!r}")
                spans.setdefault(src, []).append((lid, sp))
    return spans


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def carries(chunk_text: str, span: str) -> bool:
    a, c = _norm(span), _norm(chunk_text)
    if len(a) <= SPAN_WINDOW:
        return a in c
    return any(a[i:i + SPAN_WINDOW] in c for i in range(0, len(a) - SPAN_WINDOW + 1))


def _split(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK:
        return [text]
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        while len(para) > MAX_CHUNK:
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(para[:MAX_CHUNK])
            para = para[MAX_CHUNK:]
        if cur and len(cur) + len(para) + 2 > MAX_CHUNK:
            parts.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        parts.append(cur)
    return parts


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + " […]"


def render_blocks(content: list[dict], tool_input_clip: int = TOOL_INPUT_CLIP, tool_result_clip: int = TOOL_RESULT_CLIP) -> str:
    out = []
    for b in content:
        t = b.get("type")
        if t == "text" and b.get("text", "").strip():
            out.append(b["text"].strip())
        elif t == "tool_use":
            args = ", ".join(f"{k}={_clip(str(v), tool_input_clip)!r}" for k, v in (b.get("input") or {}).items())
            out.append(f"tool call: {b['name']}({args})")
        elif t == "tool_result":
            c = b.get("content")
            c = c if isinstance(c, str) else json.dumps(c)
            out.append(f"tool result: {_clip(c, tool_result_clip)}")
    return "\n".join(out)


def session_chunks(sid: str, spec: dict, transcript: list[dict]) -> list[Chunk]:
    chunks, n_user = [], 0
    for rec in transcript:
        role, content = rec["message"]["role"], rec["message"]["content"]
        meta = rec.get("meta") or {}
        if meta.get("harness"):
            continue
        is_text_user = role == "user" and any(b.get("type") == "text" for b in content)
        if is_text_user:
            n_user += 1
            kind, author = ("ticket", spec["author"]) if n_user == 1 else ("review", spec["author"])
        elif role == "user":
            kind, author = "tool_result", "agent"
        else:
            kind, author = "assistant", "agent"
        text = render_blocks(content)
        if not text.strip():
            continue
        for part in _split(text):
            chunks.append(Chunk(id="", repo=spec["repo"], source=sid, kind=kind, date=str(spec["date"]),
                                author=author, where=spec["branch"], text=part))
    return chunks


def build(corpus_dir: Path, repos: list[str] | None = None) -> list[Chunk]:
    """Chunks from <corpus_dir>/<session>/transcript.jsonl for every history session (of `repos`), plus chat."""
    specs = {sid: s for sid, s in history_specs().items() if repos is None or s["repo"] in repos}
    chunks: list[Chunk] = []
    for sid, spec in sorted(specs.items(), key=lambda kv: (str(kv[1]["date"]), kv[0])):
        path = corpus_dir / sid / "transcript.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"missing history transcript: {path}")
        chunks.extend(session_chunks(sid, spec, read_transcript(path)))
    for m in sorted(chat_messages(), key=lambda m: (str(m["date"]), m["id"])):
        chunks.append(Chunk(id="", repo=CHANNEL_REPO.get(m["channel"], ""), source=m["id"], kind="chat",
                            date=str(m["date"]), author=m["author"], where=m["channel"], text=m["text"].strip()))
    label(chunks)
    for i, c in enumerate(chunks):
        c.id = f"m{i:05d}-" + hashlib.sha256(f"{c.source}|{c.kind}|{c.text}".encode()).hexdigest()[:8]
    return chunks


def label(chunks: list[Chunk]) -> None:
    spans = authored_spans()
    L = lessons()
    pats = {lid: [re.compile(p, re.I) for p in d.get("patterns", [])] for lid, d in L.items()}
    for c in chunks:
        c.lessons = sorted({lid for lid, text in spans.get(c.source, []) if carries(c.text, text)})
        c.pattern_lessons = sorted({lid for lid, ps in pats.items()
                                    if lid.split(".")[0] == c.repo and any(p.search(c.text) for p in ps)})


def save(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")


def loads(text: str) -> list[Chunk]:
    return [Chunk(**json.loads(l)) for l in text.splitlines() if l.strip()]


def load(path: Path) -> list[Chunk]:
    return loads(path.read_text(encoding="utf-8"))
