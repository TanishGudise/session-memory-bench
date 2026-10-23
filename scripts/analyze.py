"""Pre-registered analysis of an eval run (PREREGISTRATION.md section 4).

  python scripts/analyze.py runs/eval/<run> --corpus runs/history/<corpus>   -> <run>/analysis.json, analysis.md
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from smb.grade import SUSPICIOUS, TRIPWIRE  # noqa: E402
from smb.history import attempt_lines  # noqa: E402
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


CODE_TOOLS = {"list_dir", "read_file", "search_code", "run_tests"}  # not search_memory: memory isn't the code


def code_seen(ep_dir: Path) -> str:
    """Everything the code tools returned to the agent in one episode (Amendment 1, change visibility)."""
    f = ep_dir / "transcript.jsonl"
    if not f.exists():
        return ""
    names, out = {}, []
    for line in f.read_text().splitlines():
        msg = json.loads(line).get("message", {})
        for b in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
            if b.get("type") == "tool_use":
                names[b["id"]] = b["name"]
            elif b.get("type") == "tool_result" and names.get(b.get("tool_use_id")) in CODE_TOOLS:
                c = b.get("content")
                out.append(c if isinstance(c, str) else "\n".join(x.get("text", "") for x in c or [] if isinstance(x, dict)))
    return "\n".join(out)


def mem_need(r):
    return {l for l in r["lessons"] if _L[l]["source"] != "repo"}  # lessons memory could have supplied


def breakdown(r):
    if r["score"] == 1 or r["score"] is None:
        return None
    if r.get("grade_status") != "graded":  # never graded (module missing, tampered, timeout...): no lesson verdict
        return f"not_graded:{r.get('grade_status')}"
    if r["stop"] != "finished":
        return f"unfinished:{r['stop']}"
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
    if r["family"] == "X":  # the X tasks' own rule lives in the code, not in memory
        return "followed_other_repo_rule" if diag else "other"
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
    if a.corpus:  # history attempts that were discarded and re-drawn (PREREGISTRATION: reported with their causes)
        att = {f.parent.name: [{"attempt": r.get("attempt"), "problem": r.get("problem")} for r in attempt_lines(f)]
               for f in sorted(Path(a.corpus).glob("*/attempts.jsonl"))}
        res["history_discarded_attempts"] = {"count": sum(map(len, att.values())), "sessions": att}
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
        for fams, label in ((None, "ALL"), ({"M"}, "M"), ({"D"}, "D"), ({"S-u", "S-s"}, "S"), ({"X"}, "X"), ({"C"}, "C")):
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
    # Amendment 1 (1): retrieval misses per condition, and whether the search tool (f) recovered them. A miss is
    # strict when the lesson's rule sentence (span label) wasn't recalled, and clear when not even one of its patterns was.
    by_tec = {(r["task"], r["epoch"], r["condition"]): r for r in scored(rows)}
    misses = {}
    for c in ("b", "c", "d", "f"):
        rs = [r for r in scored(rows) if r["condition"] == c and mem_need(r)]
        cases = []
        for r in rs:
            strict = sorted(mem_need(r) - set(r["retrieved"]))
            if not strict:
                continue
            clear = sorted(set(strict) - set(r.get("retrieved_patterns", [])))
            case = {"episode": r["episode"], "family": r["family"], "missing": strict, "missing_clear": clear, "score": r["score"]}
            fr = by_tec.get((r["task"], r["epoch"], "f"))
            if c != "f" and fr is not None:
                f_got = set(fr["retrieved"]) | set(fr.get("retrieved_patterns", []))
                case["f_found"] = set(clear or strict) <= f_got
                case["f_score"] = fr["score"]
            cases.append(case)
        clear_cases = [x for x in cases if x["missing_clear"]]
        entry = {"episodes": len(rs), "misses_strict": len(cases), "misses_clear": len(clear_cases),
                 "solved_despite_clear_miss": sum(x["score"] for x in clear_cases)}
        if c != "f":
            entry["f_found_clear_missing"] = sum(1 for x in clear_cases if x.get("f_found"))
            entry["f_solved_on_clear_miss"] = sum(1 for x in clear_cases if x.get("f_score") == 1)
        entry["cases"] = cases
        misses[c] = entry
    res["retrieval_misses"] = misses
    # Amendment 1 (3): on S tasks, was the change visible in what the code tools returned?
    tasks_ev = {}
    for t in {r["task"] for r in rows if r["family"] in ("S-u", "S-s")}:
        import yaml
        tasks_ev[t] = yaml.safe_load((ROOT / "tasks" / t / "task.yaml").read_text()).get("change_evidence", [])
    vis, vis_rows = {}, []
    for r in scored(rows):
        if r["family"] not in ("S-u", "S-s"):
            continue
        seen_text = code_seen(run / "episodes" / r["episode"])
        kinds = sorted({e["kind"] for e in tasks_ev[r["task"]] if e["text"] in seen_text})
        old = any(v == "pass" for v in r.get("diag", {}).values())
        vis_rows.append({"episode": r["episode"], "task": r["task"], "family": r["family"], "condition": r["condition"],
                         "seen": kinds, "score": r["score"], "followed_old_rule": old})
    for c in CONDITIONS:
        for t in sorted(tasks_ev):
            vr = [v for v in vis_rows if v["condition"] == c and v["task"] == t]
            if not vr:
                continue
            seen = [v for v in vr if v["seen"]]
            unseen = [v for v in vr if not v["seen"]]
            vis[f"{c}/{t}"] = {"episodes": len(vr), "seen": len(seen),
                               "seen_changelog": sum("changelog" in v["seen"] for v in vr),
                               "seen_code": sum(any(k != "changelog" for k in v["seen"]) for v in vr),
                               "pass_if_seen": f"{sum(v['score'] for v in seen)}/{len(seen)}",
                               "pass_if_unseen": f"{sum(v['score'] for v in unseen)}/{len(unseen)}",
                               "followed_old_rule": sum(v["followed_old_rule"] for v in vr)}
    res["change_visibility_S"] = {"by_condition_task": vis, "episodes": vis_rows}
    mc, mg = rates["c/M"]["rate"], rates["g/M"]["rate"]
    res["saturated"] = bool(mc is not None and mg is not None and mc >= 0.9 and mg >= 0.9)
    res["flagged_suspicious"] = [r["episode"] for r in rows if r.get("suspicious")]
    # G4: every one of these is hand-checked before the results are reported
    by_key = {(r["task"], r["epoch"], r["condition"]): r for r in scored(rows)}
    s_disagree = sorted({f"{t}__e{e}" for (t, e, c), r in by_key.items() if c == "a" and r["family"] in ("S-u", "S-s")
                         and (t, e, "c") in by_key and by_key[(t, e, "c")]["score"] != r["score"]})
    flagged = [r["episode"] for r in rows if r.get("suspicious")]
    listed = set(flagged) | {r["episode"] for r in rows if r.get("grade_status") not in (None, "graded", "collection_error")}
    s_keys = set(s_disagree)
    listed |= {r["episode"] for (t, e, c), r in by_key.items() if c in ("a", "c") and f"{t}__e{e}" in s_keys}
    listed |= {r["episode"] for r in scored(rows) if r["condition"] == "a" and r["family"] == "M" and r["score"] == 1}
    listed |= {r["episode"] for r in rows if str(r["stop"]).startswith(EXCLUDED)}
    rest = sorted(r["episode"] for r in scored(rows) if r["episode"] not in listed)
    sample = sorted(random.Random(0).sample(rest, k=max(1, len(rest) // 10))) if rest else []
    tokens = defaultdict(list)
    for r in rows:
        for line in r.get("suspicious") or []:
            content = line.split(": ", 1)[-1]  # the matched code, not the file name
            hits = sorted({m.group(0).lower() for rx in (SUSPICIOUS, TRIPWIRE) for m in rx.finditer(content)}) or ["?"]
            tokens["+".join(hits)].append(f"{r['episode']}: {line}")
    res["hand_check"] = {
        "tampered": [r["episode"] for r in rows if r.get("grade_status") == "tampered"],
        "junit_mismatch_or_no_junit": [r["episode"] for r in rows if r.get("grade_status") in ("junit_mismatch", "no_junit")],
        "grader_timeouts": [r["episode"] for r in rows if r.get("grade_status") == "timeout"],
        "flagged": flagged,
        "flagged_lines_by_token": {k: v for k, v in sorted(tokens.items())},
        "a_passes_on_M": [r["episode"] for r in scored(rows) if r["condition"] == "a" and r["family"] == "M" and r["score"] == 1],
        "S_tasks_a_vs_c_disagree": s_disagree,
        "random_10pct_seed0": sample,
    }
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
    lines += ["", "$ per solved task (Amendment 1):", "", "| cond | all | M | S |", "|---|---|---|---|"]
    for c in CONDITIONS:
        cell = lambda k: (f"{res['cost'][k]['usd_per_solved']:.4f}" if k in res["cost"] and res["cost"][k]["usd_per_solved"] else "-")  # noqa: E731
        lines.append(f"| {c} | {cell(c + '/ALL')} | {cell(c + '/M')} | {cell(c + '/S')} |")
    lines += ["", "Retrieval misses (Amendment 1): episodes where a needed memory lesson wasn't in recalled memory.", ""]
    for c, m in res["retrieval_misses"].items():
        extra = (f"; on clear misses f recalled the lesson in {m['f_found_clear_missing']} and solved {m['f_solved_on_clear_miss']}"
                 if c != "f" else "")
        lines.append(f"- {c}: of {m['episodes']} episodes, {m['misses_strict']} missed the rule sentence and {m['misses_clear']} "
                     f"missed the lesson clearly (no pattern either); {m['solved_despite_clear_miss']} clear misses solved anyway{extra}")
    lines += ["", "Change visibility on S tasks (Amendment 1): pass rate when the changelog or code showing the change was read.", "",
              "| cond/task | seen | pass if seen | pass if unseen | followed old rule |", "|---|---|---|---|---|"]
    for k, v in res["change_visibility_S"]["by_condition_task"].items():
        lines.append(f"| {k} | {v['seen']}/{v['episodes']} | {v['pass_if_seen']} | {v['pass_if_unseen']} | {v['followed_old_rule']} |")
    (run / "analysis.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
