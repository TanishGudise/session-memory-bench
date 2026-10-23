"""Corpus freeze. After history and distillation, and before any eval episode:
  1. chunk the transcripts and chat (chunks.jsonl);
  2. require hand labels for every distilled note (notes_labels.json, "reviewed": true);
  3. compute condition b's blocks once (raw_blocks.json, counted with the run model's token counter);
  4. check that no answer string appears in any chunk, note or raw block;
  5. hash everything into CORPUS_MANIFEST.json. Eval refuses to run when a file no longer matches it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from smb.leakage import find_leaks
from smb.memory import corpus as corpus_mod
from smb.memory.provider import build_raw_blocks

FROZEN_FILES = ("chunks.jsonl", "notes.jsonl", "notes_labels.json", "raw_blocks.json")


def _noteless(corpus_dir: Path) -> set[str]:
    """Sessions the distiller answered NONE for (recorded by distill)."""
    f = corpus_dir / "notes_raw.json"
    return {sid for sid, ns in json.loads(f.read_text()).items() if not ns} if f.exists() else set()


def stub_labels(corpus_dir: Path) -> None:
    """Stub corpora only: label notes by their spans (stub notes are verbatim texts)."""
    notes = [json.loads(l) for l in (corpus_dir / "notes.jsonl").read_text().splitlines() if l.strip()]
    (corpus_dir / "notes_labels.json").write_text(json.dumps(
        {"reviewed": True, "labeled_by": "span labels (stub corpus)", "labels": {n["id"]: n["lessons"] for n in notes}}, indent=1))


def _hash_files(corpus_dir: Path, sessions: list[str]) -> dict[str, str]:
    files = {}
    for sid in sorted(sessions):
        for name in ("transcript.jsonl", "session.json"):
            f = corpus_dir / sid / name
            files[f"{sid}/{name}"] = hashlib.sha256(f.read_bytes()).hexdigest()
    for name in FROZEN_FILES:
        files[name] = hashlib.sha256((corpus_dir / name).read_bytes()).hexdigest()
    return files


ALL_REPOS = ["billing", "ingest", "inventory", "notify"]


def freeze(corpus_dir: Path, count_tokens: Callable[[str], int], allowed_leaks: set[str] | None = None,
           repos: list[str] | None = None) -> dict:
    """Freeze the corpus of `repos` (all four by default; the pilot freezes billing alone)."""
    repos = sorted(repos or ALL_REPOS)
    specs = {sid: s for sid, s in corpus_mod.history_specs().items() if s["repo"] in repos}
    missing = [sid for sid in specs if not (corpus_dir / sid / "session.json").exists()]
    if missing:
        raise SystemExit(f"history sessions not complete: {missing}")
    chunks = corpus_mod.build(corpus_dir, repos)
    corpus_mod.save(chunks, corpus_dir / "chunks.jsonl")
    notes = [json.loads(l) for l in (corpus_dir / "notes.jsonl").read_text().splitlines() if l.strip()]
    if {n["source"] for n in notes} - set(specs) or set(specs) - {n["source"] for n in notes} - _noteless(corpus_dir):
        raise SystemExit("notes.jsonl must hold the notes of exactly the frozen sessions (re-run distill for these repos)")
    labels = json.loads((corpus_dir / "notes_labels.json").read_text())
    if not labels.get("reviewed") or set(labels["labels"]) != {n["id"] for n in notes}:
        raise SystemExit("notes_labels.json must be reviewed and cover exactly the notes in notes.jsonl")
    unknown = {l for ls in labels["labels"].values() for l in ls} - set(corpus_mod.lessons())
    if unknown:
        raise SystemExit(f"unknown lessons in notes_labels.json: {sorted(unknown)}")
    raw = build_raw_blocks(corpus_dir, count_tokens, repos=repos)
    (corpus_dir / "raw_blocks.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    texts = [c.text for c in chunks] + [n["text"] for n in notes] + [b["block"] for b in raw.values()]
    leaks = {tid: [s for s in strs if s not in (allowed_leaks or set())] for tid, strs in find_leaks(texts).items()}
    leaks = {k: v for k, v in leaks.items() if v}
    if leaks:
        (corpus_dir / "leaks.json").write_text(json.dumps(leaks, indent=1))
        raise SystemExit(f"answer strings found in the corpus (see leaks.json): {list(leaks)}")
    files = _hash_files(corpus_dir, list(specs))
    manifest = {"sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(), "files": files,
                "repos": repos, "sessions": sorted(specs),
                "chunks": len(chunks), "notes": len(notes),
                "raw": {r: {k: b[k] for k in ("tokens", "sessions_included", "sessions_skipped")} for r, b in raw.items()}}
    (corpus_dir / "CORPUS_MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def verify(corpus_dir: Path) -> dict:
    m = json.loads((corpus_dir / "CORPUS_MANIFEST.json").read_text())
    if _hash_files(corpus_dir, m["sessions"]) != m["files"]:
        raise SystemExit(f"corpus {corpus_dir} differs from its CORPUS_MANIFEST.json: refusing to run")
    return m
