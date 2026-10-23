"""Pre-registered analysis of an eval run (PREREGISTRATION.md section 4).

  python scripts/analyze.py runs/eval/<run> --corpus runs/history/<corpus>   -> <run>/analysis.json, analysis.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smb.memory.corpus import lessons  # noqa: E402
from smb.memory.provider import CONDITIONS  # noqa: E402
from smb.stats import cluster_bootstrap_diff, holm, mcnemar_exact, wilson  # noqa: E402

FAMS = ["M", "D", "S-u", "S-s", "X", "C"]
EXCLUDED = ("cap", "error")
_L = lessons()
FAMILY_A = {"A1": ("c", "a", "greater"), "A2": ("d", "c", "two-sided"), "A3": ("b", "c", "two-sided"), "A4": ("f", "c", "two-sided")}
FAMILY_B = {"B1": ("b", "a", "less"), "B2": ("c", "a", "less"), "B3": ("d", "a", "less"), "B4": ("f", "a", "less")}


def load(run: Path) -> list[dict]:
    rows = {}
    for line in (run / "results.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["episode"]] = r  # a re-run of an episode replaces the earlier record
    return list(rows.values())


def scored(rows):
    return [r for r in rows if not str(r["stop"]).startswith(EXCLUDED)]


def paired(rows, x, y, fams):
    by = {(r["task"], r["epoch"], r["condition"]): r["score"] for r in scored(rows) if r["family"] in fams}
    pairs = defaultdict(list)
    for (t, e, c), s in by.items():
        if c == x and (t, e, y) in by:
            pairs[t].append((s, by[(t, e, y)]))
    b = sum(1 for ps in pairs.values() for p, q in ps if p == 1 and q == 0)
    c = sum(1 for ps in pairs.values() for p, q in ps if p == 0 and q == 1)
    return pairs, b, c


def family_tests(rows, spec, fams):
    out, ps = {}, {}
    for name, (x, y, alt) in spec.items():
        pairs, b, c = paired(rows, x, y, fams)
        p = mcnemar_exact(b, c, alt)
        d, lo, hi = cluster_bootstrap_diff(pairs)
        n = sum(len(v) for v in pairs.values())
        out[name] = {"x": x, "y": y, "alternative": alt, "pairs": n, "only_x_pass": b, "only_y_pass": c,
                     "p": p, "diff": d, "diff_ci95": [lo, hi]}
        ps[name] = p
    for name, padj in holm(ps).items():
        out[name]["p_holm"] = padj
    return out


def breakdown(r):
    if r["score"] == 1 or r["score"] is None:
        return None
    tests = r["tests"]
    lesson_fail = any(v != "pass" for n, v in tests.items() if "lesson" in n)
    diag = any(v == "pass" for v in r.get("diag", {}).values())
    need = {l for l in r["lessons"] if _L[l]["source"] != "repo"}  # lessons memory could have supplied
    got = set(r["retrieved"])
    if r["family"] == "S-u":  # memory never holds the current rule here; what matters is whether the old one was recalled
        if diag:
            return "followed_old_rule"
        return "old_rule_recalled_not_followed_other" if set(r["stale_lessons"]) & got else "other"
    if r["family"] == "S-s":
        if diag:
            return "followed_old_rule"
        return "current_recalled_not_applied" if need and need <= got and lesson_fail else "other"
    if r["family"] == "X" and diag:
        return "followed_other_repo_rule"
    if not need <= got:
        return "not_retrieved"
    return "retrieved_not_applied" if lesson_fail else "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--corpus")
    a = ap.parse_args()
    run = Path(a.run)
    rows = load(run)
    L = lessons()
    chunk_source = {}
    if a.corpus:
        cp = Path(a.corpus) / "chunks.jsonl"
        if cp.exists():
            for line in cp.read_text().splitlines():
                c = json.loads(line)
                chunk_source[c["id"]] = c["source"]
    res = {"episodes": len(rows), "excluded": [r["episode"] for r in rows if str(r["stop"]).startswith(EXCLUDED)]}
    rates = {}
    for c in CONDITIONS:
        for f in FAMS + ["ALL"]:
            rs = [r for r in scored(rows) if r["condition"] == c and (f == "ALL" or r["family"] == f)]
            k, n = sum(r["score"] for r in rs), len(rs)
            rates[f"{c}/{f}"] = {"k": k, "n": n, "rate": k / n if n else None, "ci95": list(wilson(k, n))}
    res["pass_rates"] = rates
    res["family_A_benefit_M"] = family_tests(rows, FAMILY_A, {"M"})
    res["family_B_harm_S"] = family_tests(rows, FAMILY_B, {"S-u", "S-s"})
    s_fail = {}
    for c in CONDITIONS:
        rs = [r for r in scored(rows) if r["condition"] == c and r["family"] in ("S-u", "S-s")]
        k = sum(1 - r["score"] for r in rs)
        s_fail[c] = {"fail": k, "n": len(rs), "ci95": list(wilson(k, len(rs)))}
    res["harm_failure_rate_S"] = s_fail
    bd = defaultdict(lambda: defaultdict(int))
    for r in scored(rows):
        b = breakdown(r)
        if b:
            bd[f"{r['condition']}/{r['family']}"][b] += 1
    res["failure_breakdown"] = {k: dict(v) for k, v in sorted(bd.items())}
    cost = {}
    for c in CONDITIONS:
        for fams, label in ((None, "ALL"), ({"D"}, "D"), ({"C"}, "C")):
            rs = [r for r in scored(rows) if r["condition"] == c and (fams is None or r["family"] in fams)]
            if not rs:
                continue
            solved = sum(r["score"] for r in rs)
            tok = [sum(r["usage"].get(k, 0) for k in ("input", "output", "cache_read", "cache_write")) for r in rs]
            cost[f"{c}/{label}"] = {
                "episodes": len(rs), "solved": solved, "usd": round(sum(r["cost"] for r in rs), 4),
                "usd_per_solved": round(sum(r["cost"] for r in rs) / solved, 5) if solved else None,
                "tokens_mean": round(sum(tok) / len(rs)), "calls_mean": round(sum(r["calls"] for r in rs) / len(rs), 2),
                "reads_before_first_edit_mean": round(sum(r["reads_before_first_edit"] for r in rs) / len(rs), 2),
                "seconds_mean": round(sum(r["seconds"] for r in rs) / len(rs), 1),
                "memory_chars_mean": round(sum(r["memory_chars"] for r in rs) / len(rs)),
            }
    res["cost"] = cost
    retr = {}
    for c in ("b", "c", "d", "f"):
        mem = lambda r: {l for l in r["lessons"] if L[l]["source"] != "repo"}  # noqa: E731
        rs = [r for r in scored(rows) if r["condition"] == c and mem(r)]
        need = sum(len(mem(r)) for r in rs)
        got = sum(len(mem(r) & set(r["retrieved"])) for r in rs)
        entry = {"lesson_recall": got / need if need else None, "episodes": len(rs)}
        if chunk_source and c in ("c", "f"):
            rel = tot = 0
            for r in rs:
                srcs = {s for lid in r["lessons"] for s in (L[lid]["source"] if L[lid]["source"] != "repo" else [])}
                for cid in r["memory_sources"]:
                    if cid in chunk_source:
                        tot += 1
                        rel += chunk_source[cid] in srcs
            entry["precision_chunks_from_relevant_sources"] = rel / tot if tot else None
        if c == "f":
            fr = [r for r in scored(rows) if r["condition"] == "f"]
            entry["searched_share"] = sum(1 for r in fr if r["search_queries"]) / len(fr) if fr else None
            entry["searches_per_episode"] = sum(len(r["search_queries"]) for r in fr) / len(fr) if fr else None
        retr[c] = entry
    res["retrieval"] = retr
    mc, mg = rates["c/M"]["rate"], rates["g/M"]["rate"]
    res["saturated"] = bool(mc is not None and mg is not None and mc >= 0.9 and mg >= 0.9)
    res["flagged_suspicious"] = [r["episode"] for r in rows if r.get("suspicious")]
    (run / "analysis.json").write_text(json.dumps(res, indent=2, default=str))
    lines = ["| cond | " + " | ".join(FAMS) + " | all |", "|---" * (len(FAMS) + 2) + "|"]
    for c in CONDITIONS:
        cells = [f"{rates[f'{c}/{f}']['k']}/{rates[f'{c}/{f}']['n']}" for f in FAMS + ["ALL"]]
        lines.append(f"| {c} {CONDITIONS[c]} | " + " | ".join(cells) + " |")
    lines.append("")
    for fam, key in (("A (M tasks)", "family_A_benefit_M"), ("B (S tasks)", "family_B_harm_S")):
        for name, t in res[key].items():
            lines.append(f"- {name} {t['x']} vs {t['y']} ({t['alternative']}): {t['only_x_pass']} vs {t['only_y_pass']} discordant "
                         f"of {t['pairs']}, p={t['p']:.4f}, Holm {t['p_holm']:.4f}, diff {t['diff']:+.3f} "
                         f"[{t['diff_ci95'][0]:+.3f}, {t['diff_ci95'][1]:+.3f}]")
    (run / "analysis.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
