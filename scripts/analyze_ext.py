"""Pre-registered analysis of the invisible-change extension (ext/ADDENDUM.md section 5).

  python scripts/analyze_ext.py runs/eval/<run>   -> <run>/analysis_ext.json, analysis_ext.md
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

os.environ["SMB_EXT"] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from analyze import load, real_cost, scored  # noqa: E402
from smb.memory.corpus import lessons  # noqa: E402
from smb.memory.provider import CONDITIONS  # noqa: E402
from smb.stats import holm, mcnemar_exact, wilson  # noqa: E402

MEMORY = ("b", "c", "d", "f")
_L = lessons()


def outcome(r) -> str:
    if r["score"] == 1:
        return "new_rule"
    if any(v == "pass" for v in (r.get("diag") or {}).values()):
        return "old_rule"
    return "other"


def recall_state(r) -> str:
    got = set(r["retrieved"])
    new = bool({l for l in r["lessons"] if _L[l].get("kind") == "invisible"} & got)
    old = bool(set(r["stale_lessons"]) & got)
    return {(True, True): "both", (True, False): "new_only", (False, True): "old_only", (False, False): "neither"}[(new, old)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    a = ap.parse_args()
    run = Path(a.run)
    rows = [r for r in load(run) if r["family"] == "S-i"]
    sc = scored(rows)
    res = {"episodes": len(rows), "excluded": [r["episode"] for r in rows if r not in sc]}
    per = {}
    for c in CONDITIONS:
        rs = [r for r in sc if r["condition"] == c]
        n = len(rs)
        counts = {k: sum(outcome(r) == k for r in rs) for k in ("new_rule", "old_rule", "other")}
        per[c] = {"n": n, **counts, "pass_ci95": list(wilson(counts["new_rule"], n)), "old_rule_ci95": list(wilson(counts["old_rule"], n))}
    res["by_condition"] = per
    by_task = defaultdict(dict)
    for r in sc:
        cell = by_task[r["task"]].setdefault(r["condition"], {"n": 0, "new_rule": 0, "old_rule": 0, "other": 0})
        cell["n"] += 1
        cell[outcome(r)] += 1
    res["by_task"] = by_task
    # primary: harm = following the old rule more often than no memory (one-sided exact McNemar, Holm over 4)
    key = {(r["task"], r["epoch"], r["condition"]): r for r in sc}
    tests, ps = {}, {}
    for x in MEMORY:
        b = c_ = n = 0
        for (t, e, c), r in key.items():
            if c != x or (t, e, "a") not in key:
                continue
            n += 1
            xo, ao = outcome(r) == "old_rule", outcome(key[(t, e, "a")]) == "old_rule"
            b += xo and not ao
            c_ += ao and not xo
        p = mcnemar_exact(b, c_, "greater")
        tests[f"H{x}"] = {"x": x, "pairs": n, "only_x_old": b, "only_a_old": c_, "p": p}
        ps[f"H{x}"] = p
    for k, padj in holm(ps).items():
        tests[k]["p_holm"] = padj
    res["harm_old_rule_vs_a"] = tests
    # secondary: outcome by what the recalled memory held (span labels)
    rs_state = defaultdict(lambda: defaultdict(int))
    for r in sc:
        if r["condition"] in MEMORY:
            rs_state[f"{r['condition']}/{recall_state(r)}"][outcome(r)] += 1
    res["outcome_by_recall"] = {k: dict(v) for k, v in sorted(rs_state.items())}
    fr = [r for r in sc if r["condition"] == "f"]
    res["f_searched_share"] = sum(1 for r in fr if r["search_queries"]) / len(fr) if fr else None
    cost = {}
    for c in CONDITIONS:
        rs = [r for r in sc if r["condition"] == c]
        real = [real_cost(run / "episodes" / r["episode"], r.get("model", "")) for r in rs]
        usd = sum(x for x in real if x is not None)
        solved = sum(r["score"] for r in rs)
        cost[c] = {"usd_answered_calls": round(usd, 4), "solved": solved, "usd_per_solved": round(usd / solved, 5) if solved else None}
    res["cost"] = cost
    ledger = run / "spend.jsonl"
    if ledger.exists():
        recs = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
        wc = [x for x in recs if (x.get("usage") or {}).get("worst_case")]
        res["ledger"] = {"requests": len(recs), "usd": round(sum(x["cost"] for x in recs), 4),
                         "worst_case_requests": len(wc), "worst_case_usd": round(sum(x["cost"] for x in wc), 4)}
    # hand checks: every a pass, every old-rule follow in a memory condition, every flagged or ungraded episode,
    # and a random 10% (seed 0) of the rest
    listed = {r["episode"] for r in sc if r["condition"] == "a" and r["score"] == 1}
    listed |= {r["episode"] for r in sc if r["condition"] in MEMORY and outcome(r) == "old_rule"}
    listed |= {r["episode"] for r in rows if r.get("suspicious") or r.get("grade_status") not in (None, "graded", "collection_error")}
    rest = sorted(r["episode"] for r in sc if r["episode"] not in listed)
    res["hand_check"] = {
        "a_passes": sorted(r["episode"] for r in sc if r["condition"] == "a" and r["score"] == 1),
        "memory_old_rule": sorted(r["episode"] for r in sc if r["condition"] in MEMORY and outcome(r) == "old_rule"),
        "flagged_or_ungraded": sorted(r["episode"] for r in rows if r.get("suspicious") or r.get("grade_status") not in (None, "graded", "collection_error")),
        "random_10pct_seed0": sorted(random.Random(0).sample(rest, k=max(1, len(rest) // 10))) if rest else [],
    }
    (run / "analysis_ext.json").write_text(json.dumps(res, indent=2, default=str))
    lines = ["| cond | n | new rule (pass) | old rule | other |", "|---|---|---|---|---|"]
    for c, v in per.items():
        lines.append(f"| {c} {CONDITIONS[c]} | {v['n']} | {v['new_rule']} [{v['pass_ci95'][0]:.2f}, {v['pass_ci95'][1]:.2f}] | "
                     f"{v['old_rule']} [{v['old_rule_ci95'][0]:.2f}, {v['old_rule_ci95'][1]:.2f}] | {v['other']} |")
    lines.append("")
    for k, t in tests.items():
        lines.append(f"- {k} {t['x']} follows the old rule more than a: {t['only_x_old']} vs {t['only_a_old']} discordant of "
                     f"{t['pairs']}, p={t['p']:.4f}, Holm {t['p_holm']:.4f}")
    lines += ["", "Outcome by what recalled memory held (span labels):", ""]
    for k, v in res["outcome_by_recall"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "| task | " + " | ".join(CONDITIONS) + " |", "|---" * (len(CONDITIONS) + 1) + "|"]
    for t, cells in sorted(by_task.items()):
        lines.append(f"| {t} | " + " | ".join(f"{cells[c]['new_rule']}/{cells[c]['old_rule']}/{cells[c]['n']}" if c in cells else "-"
                                              for c in CONDITIONS) + " |")
    lines.append("\n(cells: new rule / old rule / episodes)")
    (run / "analysis_ext.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
