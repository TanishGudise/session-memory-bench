"""Exploratory, after the main run (not pre-registered): do condition c's clear misses track how lexical the lesson
is in the task prompt? For each (task, memory lesson) on the main run, prints c's clear misses, the word overlap
between the prompt and the lesson's rule spans, and the rank of the best rule-carrying chunk under the BM25 half
and the dense half of the retriever, for the hook query at the start of the task.

  python scripts/explore_retrieval_misses.py runs/eval/main runs/history/run1
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from smb.memory import corpus as C  # noqa: E402
from smb.memory.provider import hook_query  # noqa: E402
from smb.memory.retriever import Index  # noqa: E402
from smb.tasks import all_tasks  # noqa: E402

STOP = set("a an the and or of to in on for with is are be it its this that as at by from we our you your not no any every "
           "all each into when has have was were will should must can do does new use uses using than then them they their "
           "there here which who what so if".split())


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9_]+", s.lower()) if w not in STOP and len(w) > 2}


def main() -> int:
    run, corpus = Path(sys.argv[1]), Path(sys.argv[2])
    L = C.lessons()
    T = {t.id: t for t in all_tasks()}
    chunks = C.load(corpus / "chunks.jsonl")
    idx = Index(chunks)
    miss: dict[tuple[str, str], list[int]] = {}
    for line in (run / "results.jsonl").read_text().splitlines():
        r = json.loads(line)
        if r["condition"] != "c":
            continue
        for lid in r["lessons"]:
            if L[lid]["source"] == "repo":
                continue
            m = miss.setdefault((r["task"], lid), [0, 0])
            m[1] += 1
            m[0] += lid not in set(r["retrieved"]) | set(r.get("retrieved_patterns", []))

    def rank(order: list[int], lid: str) -> int | None:
        return next((i + 1 for i, ci in enumerate(order) if lid in chunks[ci].lessons), None)

    rows = []
    for (tid, lid), (m, n) in sorted(miss.items()):
        t = T[tid]
        q = hook_query(t.prompt, "", {"repo": t.repo, "branch": t.branch})
        rule = " ".join(s for v in (L[lid].get("spans") or {}).values() for s in v)
        pw, rw = words(t.prompt), words(rule)
        rows.append({"task": tid, "lesson": lid, "clear_misses": m, "episodes": n,
                     "overlap": round(len(pw & rw) / len(rw), 2) if rw else 0.0,
                     "bm25_rank": rank(idx.bm25(q, k=len(chunks)), lid), "dense_rank": rank(idx.dense(q, k=len(chunks)), lid)})
    idx.close()
    for r in sorted(rows, key=lambda r: (-r["clear_misses"], r["task"])):
        print(json.dumps(r))
    for name, grp in (("missed", [r for r in rows if r["clear_misses"]]), ("recalled", [r for r in rows if not r["clear_misses"]])):
        print(f"{name}: n={len(grp)} overlap mean {statistics.mean(r['overlap'] for r in grp):.2f}, "
              f"BM25 rank median {statistics.median(r['bm25_rank'] for r in grp)}, dense rank median {statistics.median(r['dense_rank'] for r in grp)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
