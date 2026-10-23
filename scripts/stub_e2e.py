"""$0 end-to-end run with stub models: history sessions -> corpus -> notes -> all 32 tasks x 6 conditions.

  python scripts/stub_e2e.py [--out runs/stub]

Checks the plumbing and reports, per condition and family, how often the stub found the lessons it needed in its
context (an upper bound for the stub corpus, not a model result)."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smb import netguard  # noqa: E402
from smb.history import run_session  # noqa: E402
from smb.memory import corpus as corpus_mod  # noqa: E402
from smb.memory.distill import stub_notes, write_notes  # noqa: E402
from smb.memory.freeze import freeze, stub_labels  # noqa: E402
from smb.memory.provider import CONDITIONS, FrozenRaw, NoMemory, Pull, Retrieved, estimate_tokens, notes_as_chunks  # noqa: E402
from smb.memory.retriever import Index  # noqa: E402
from smb.meter import Meter  # noqa: E402
from smb.paths import ROOT  # noqa: E402
from smb.runner import run_episode  # noqa: E402
from smb.stub import EvalStub, HistoryStub, StubClient  # noqa: E402
from smb.tasks import all_tasks  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "runs" / "stub"))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    netguard.install()  # loopback only: nothing in a stub run may reach the network
    out = Path(args.out)
    if out.exists():
        shutil.rmtree(out)
    hist_dir = out / "history"
    specs = corpus_mod.history_specs()
    meter = Meter(cap_usd=0.0)
    for sid, spec in sorted(specs.items(), key=lambda kv: (str(kv[1]["date"]), kv[0])):
        rec = run_session(sid, StubClient(HistoryStub({**spec, "id": sid})), "stub", hist_dir, meter=meter)
        assert rec["stop_task"] in ("finished", "no_finish") and rec["stop_review"] == "finished", rec
    write_notes(hist_dir, {sid: stub_notes(spec) for sid, spec in specs.items()})
    stub_labels(hist_dir)
    freeze(hist_dir, estimate_tokens)
    chunks = corpus_mod.load(hist_dir / "chunks.jsonl")
    idx = Index(chunks)
    notes_idx = Index(notes_as_chunks(hist_dir / "notes.jsonl", hist_dir / "notes_labels.json"), embedder=idx.embedder)
    raw = FrozenRaw(json.loads((hist_dir / "raw_blocks.json").read_text()))
    providers = {"none": NoMemory(), "raw": raw, "retrieved": Retrieved(idx),
                 "distilled": Retrieved(notes_idx, budget_chars=3500), "pull": Pull(idx)}
    run_dir = out / "eval"
    run_dir.mkdir(parents=True)
    jobs = [(t, c) for t in all_tasks() for c in CONDITIONS]

    def one(job):
        t, c = job
        return run_episode(t, c, 1, StubClient(EvalStub(t, pull=CONDITIONS[c] == "pull")), "stub", providers, run_dir, meter)

    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(one, jobs))
    idx.close()
    bad = [r for r in results if r["stop"] != "finished" or r["grade_status"] not in ("graded", "collection_error")]
    table = defaultdict(lambda: [0, 0])
    for r in results:
        cell = table[(r["condition"], r["family"])]
        cell[0] += r["score"] or 0
        cell[1] += 1
    fams = ["M", "D", "S-u", "S-s", "X", "C"]
    print("cond  " + "  ".join(f"{f:>5s}" for f in fams))
    for c in CONDITIONS:
        print(f"{c}:{CONDITIONS[c]:9s}" + "  ".join(f"{table[(c, f)][0]:>2d}/{table[(c, f)][1]:<2d}" for f in fams))
    summary = {"episodes": len(results), "bad": [r["episode"] for r in bad], "chunks": len(chunks),
               "table": {f"{c}/{f}": table[(c, f)] for c in CONDITIONS for f in fams}}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("episodes", "bad", "chunks")}))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
