"""Condition d: notes distilled from each history session, like a memory product's "observations".

Paid runs distill each session once with the model and the fixed prompt below (pre-registered). Note labels for
analysis are assigned by hand before any eval run (frozen in notes_labels.json); the stub distiller used for $0
runs copies the ticket and review text verbatim, so its notes carry span labels.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from smb.memory.corpus import authored_spans, carries, history_specs, lessons
from smb.memory.provider import render_session_raw
from smb.transcript import read as read_transcript

PROMPT = """Below is the transcript of a coding agent's session in the {repo} repository on {date} (branch {branch}), including the task it was given and the PR review it got.

Write down the durable knowledge a teammate's future coding agent should have from this session: team rules and conventions, decisions, facts about external systems, gotchas, and what changed in the code. One note per line, each self-contained (name the module or system it applies to). At most 8 notes. If there is nothing durable, write NONE.

<transcript>
{transcript}
</transcript>"""
MAX_TOKENS = 1500


def stub_notes(spec: dict) -> list[str]:
    return [spec["ticket"].strip()] + [r["text"].strip() for r in spec["review"] if r["when"] == "always"]


def model_notes(client, model: str, spec: dict, transcript_text: str, meter=None) -> tuple[list[str], dict]:
    prompt = PROMPT.format(repo=spec["repo"], date=spec["date"], branch=spec["branch"], transcript=transcript_text)
    messages = [{"role": "user", "content": prompt}]
    ticket = meter.reserve(model, "", messages, [], MAX_TOKENS) if meter else None
    resp = client.messages.create(model=model, max_tokens=MAX_TOKENS, messages=messages, timeout=180)
    u = resp.usage
    usage = {"input": u.input_tokens, "output": u.output_tokens, "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
             "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
    if meter:
        meter.settle(ticket, model, usage)
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    notes = [] if text.upper() == "NONE" else [l.strip(" -•\t") for l in text.splitlines() if l.strip(" -•\t")]
    return notes[:8], usage


def write_notes(corpus_dir: Path, notes_by_session: dict[str, list[str]]) -> Path:
    specs = history_specs()
    spans = authored_spans()
    import re
    pats = {lid: [re.compile(p, re.I) for p in d.get("patterns", [])] for lid, d in lessons().items()}
    out = corpus_dir / "notes.jsonl"
    with open(out, "w", encoding="utf-8") as fh:
        for sid in sorted(notes_by_session, key=lambda s: (str(specs[s]["date"]), s)):
            spec = specs[sid]
            for i, text in enumerate(notes_by_session[sid]):
                nid = f"n-{sid}-{i}-" + hashlib.sha256(text.encode()).hexdigest()[:6]
                rec = {"id": nid, "repo": spec["repo"], "source": sid, "where": spec["branch"], "date": str(spec["date"]),
                       "text": text,
                       "lessons": sorted({lid for lid, t in spans.get(sid, []) if carries(text, t)}),
                       "pattern_lessons": sorted({lid for lid, ps in pats.items() if lid.split(".")[0] == spec["repo"]
                                                  and any(p.search(text) for p in ps)})}
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return out


def session_text(corpus_dir: Path, sid: str) -> str:
    spec = history_specs()[sid]
    return render_session_raw(sid, spec, read_transcript(corpus_dir / sid / "transcript.jsonl"))
