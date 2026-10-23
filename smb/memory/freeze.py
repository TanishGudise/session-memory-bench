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
import os
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
           repos: list[str] | None = None, force: bool = False) -> dict:
    """Freeze the corpus of `repos` (all four by default; the pilot freezes billing alone).

    Every check runs before anything is replaced; the new files are written under temporary names and swapped in
    only when all checks pass, so a failed freeze leaves the previous freeze intact. An existing freeze may only be
    extended to more repos with its sessions, notes and note labels unchanged (the old manifest and its notes
    snapshot are kept); anything else needs force=True and a dated amendment."""
    repos = sorted(repos or ALL_REPOS)
    specs = {sid: s for sid, s in corpus_mod.history_specs().items() if s["repo"] in repos}
    missing = [sid for sid in specs if not (corpus_dir / sid / "session.json").exists()]
    if missing:
        raise SystemExit(f"history sessions not complete: {missing}")
    notes_bytes = (corpus_dir / "notes.jsonl").read_bytes()  # read once: checked, hashed and snapshotted as is
    labels_bytes = (corpus_dir / "notes_labels.json").read_bytes()
    notes = [json.loads(l) for l in notes_bytes.decode().splitlines() if l.strip()]
    if {n["source"] for n in notes} - set(specs) or set(specs) - {n["source"] for n in notes} - _noteless(corpus_dir):
        raise SystemExit("notes.jsonl must hold the notes of exactly the frozen sessions (re-run distill for these repos)")
    labels = json.loads(labels_bytes)
    if not labels.get("reviewed") or set(labels["labels"]) != {n["id"] for n in notes}:
        raise SystemExit("notes_labels.json must be reviewed and cover exactly the notes in notes.jsonl")
    unknown = {l for ls in labels["labels"].values() for l in ls} - set(corpus_mod.lessons())
    if unknown:
        raise SystemExit(f"unknown lessons in notes_labels.json: {sorted(unknown)}")
    old_path = corpus_dir / "CORPUS_MANIFEST.json"
    old = json.loads(old_path.read_text()) if old_path.exists() else None
    if old is not None and not force:
        problems = []
        if not set(old["repos"]) < set(repos):
            problems.append("a re-freeze must add repos")
        for rel, h in old["files"].items():
            if "/" in rel and (not (corpus_dir / rel).exists() or hashlib.sha256((corpus_dir / rel).read_bytes()).hexdigest() != h):
                problems.append(f"frozen session file changed: {rel}")
        snap_notes = (corpus_dir / old["notes_snapshot"]).read_bytes()
        snap_labels = (corpus_dir / old["labels_snapshot"]).read_bytes()
        if (hashlib.sha256(snap_notes).hexdigest() != old["files"]["notes.jsonl"]
                or hashlib.sha256(snap_labels).hexdigest() != old["files"]["notes_labels.json"]):
            raise SystemExit("the frozen notes snapshot doesn't match its manifest: refusing (pass --force and record an amendment)")
        old_notes = {n["id"]: n for n in (json.loads(l) for l in snap_notes.decode().splitlines() if l.strip())}
        new_notes = {n["id"]: n for n in notes}
        old_labels = json.loads(snap_labels)["labels"]
        for nid, n in old_notes.items():
            if new_notes.get(nid) != n:
                problems.append(f"frozen note changed or removed: {nid}")
            elif sorted(labels["labels"][nid]) != sorted(old_labels[nid]):
                problems.append(f"frozen note label changed: {nid}")
        if problems:
            raise SystemExit("corpus already frozen; refusing this re-freeze (pass --force and record an amendment): "
                             + "; ".join(problems[:5]))
    chunks = corpus_mod.build(corpus_dir, repos)
    raw = build_raw_blocks(corpus_dir, count_tokens, repos=repos)
    allowed_leaks = set(allowed_leaks or ())
    texts = [c.text for c in chunks] + [n["text"] for n in notes] + [b["block"] for b in raw.values()]
    leaks = {tid: [s for s in strs if s not in allowed_leaks] for tid, strs in find_leaks(texts).items()}
    leaks = {k: v for k, v in leaks.items() if v}
    if leaks:
        (corpus_dir / "leaks.json").write_text(json.dumps(leaks, indent=1))
        raise SystemExit(f"answer strings found in the corpus (see leaks.json): {list(leaks)}")
    # all checks passed: write the new files under temporary names, then swap them in
    tmp_chunks, tmp_raw = corpus_dir / "chunks.jsonl.new", corpus_dir / "raw_blocks.json.new"
    corpus_mod.save(chunks, tmp_chunks)
    tmp_raw.write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    files = {}
    for sid in sorted(specs):
        for name in ("transcript.jsonl", "session.json"):
            files[f"{sid}/{name}"] = hashlib.sha256((corpus_dir / sid / name).read_bytes()).hexdigest()
    files["chunks.jsonl"] = hashlib.sha256(tmp_chunks.read_bytes()).hexdigest()
    files["notes.jsonl"] = hashlib.sha256(notes_bytes).hexdigest()
    files["notes_labels.json"] = hashlib.sha256(labels_bytes).hexdigest()
    files["raw_blocks.json"] = hashlib.sha256(tmp_raw.read_bytes()).hexdigest()
    sha = hashlib.sha256(json.dumps({"files": files, "allowed_leaks": sorted(allowed_leaks)}, sort_keys=True).encode()).hexdigest()
    notes_snap, labels_snap = f"frozen-{sha[:8]}-notes.jsonl", f"frozen-{sha[:8]}-labels.json"
    (corpus_dir / notes_snap).write_bytes(notes_bytes)
    (corpus_dir / labels_snap).write_bytes(labels_bytes)
    manifest = {"sha256": sha, "files": files, "repos": repos, "sessions": sorted(specs), "allowed_leaks": sorted(allowed_leaks),
                "notes_snapshot": notes_snap, "labels_snapshot": labels_snap, "chunks": len(chunks), "notes": len(notes),
                "raw": {r: {k: b[k] for k in ("tokens", "sessions_included", "sessions_skipped")} for r, b in raw.items()}}
    tmp_manifest = corpus_dir / "CORPUS_MANIFEST.json.new"
    tmp_manifest.write_text(json.dumps(manifest, indent=1))
    if old is not None:  # keep a copy of the old manifest; the live one is swapped in a single step below
        (corpus_dir / f"CORPUS_MANIFEST.{old['sha256'][:8]}.json").write_text(old_path.read_text())
    os.replace(tmp_chunks, corpus_dir / "chunks.jsonl")
    os.replace(tmp_raw, corpus_dir / "raw_blocks.json")
    os.replace(tmp_manifest, old_path)
    return manifest


def load_frozen(corpus_dir: Path) -> tuple[dict, dict[str, bytes]]:
    """Read every frozen file once, check those bytes against CORPUS_MANIFEST.json, and return them, so a run
    builds its memory from exactly the bytes it verified."""
    m = json.loads((corpus_dir / "CORPUS_MANIFEST.json").read_text())
    blobs = {name: (corpus_dir / name).read_bytes() for name in FROZEN_FILES}
    for name, data in blobs.items():
        if hashlib.sha256(data).hexdigest() != m["files"][name]:
            raise SystemExit(f"corpus {corpus_dir}: {name} differs from CORPUS_MANIFEST.json: refusing to run")
    verify(corpus_dir)  # the sessions too
    return m, blobs


def verify(corpus_dir: Path) -> dict:
    m = json.loads((corpus_dir / "CORPUS_MANIFEST.json").read_text())
    if _hash_files(corpus_dir, m["sessions"]) != m["files"]:
        raise SystemExit(f"corpus {corpus_dir} differs from its CORPUS_MANIFEST.json: refusing to run")
    return m
