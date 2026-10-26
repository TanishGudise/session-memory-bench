"""Check the regenerated analyses against the headline numbers reported in RESULTS.md and EXT_RESULTS.md.

  python repro_check.py .repro      (run by repro.sh)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    out = Path(sys.argv[1])
    main_ = json.loads((out / "main" / "analysis.json").read_text())
    g4 = json.loads((out / "main_g4" / "analysis.json").read_text())
    ext = json.loads((out / "data" / "runs" / "eval" / "ext" / "analysis_ext.json").read_text())
    checks = []

    def check(name, got, want):
        checks.append((name, got, want, got == want))

    for c, k in {"a": 10, "b": 69, "c": 29, "d": 55, "f": 44, "g": 68}.items():
        check(f"main: {c} solves M (of 70)", (main_["pass_rates"][f"{c}/M"]["k"], main_["pass_rates"][f"{c}/M"]["n"]), (k, 70))
    for c, r in {"b": 1.0, "c": 0.25, "d": 0.875}.items():
        check(f"main: {c} lesson recall", round(main_["retrieval"][c]["lesson_recall"], 3), r)
    m = main_["retrieval_misses"]["c"]
    check("main: c clear misses (of 110)", (m["misses_clear"], m["episodes"]), (35, 110))
    check("main: f recalled the lesson and passed on c's clear misses", m["f_found_and_solved_on_clear_miss"], 24)
    for fam in ("S-u", "S-s"):
        for c in "abcdfg":
            r = g4["pass_rates"][f"{c}/{fam}"]
            check(f"G4 (notify-05 excluded): {c} solves {fam}", r["k"] == r["n"], True)
    vis = main_["change_visibility_S"]["episodes"]
    check("main: S episodes that saw the change", (sum(1 for v in vis if v["seen"]), len(vis)), (238, 240))
    check("main: S episodes that followed the old rule", sum(v["followed_old_rule"] for v in vis), 0)
    for c, want in {"a": (0, 0), "b": (50, 0), "c": (10, 20), "d": (39, 10), "f": (38, 0), "g": (50, 0)}.items():
        v = ext["by_condition"][c]
        check(f"ext: {c} new rule / old rule (of 50)", (v["new_rule"], v["old_rule"]), want)
    both = [v for k, v in ext["outcome_by_recall"].items() if k.endswith("/both")]
    check("ext: both decisions recalled -> newer followed", (sum(v.get("new_rule", 0) for v in both), sum(sum(v.values()) for v in both)), (137, 139))
    old_only = [v for k, v in ext["outcome_by_recall"].items() if k.endswith("/old_only")]
    check("ext: old rule only when only the old decision was recalled", (sum(v.get("old_rule", 0) for v in old_only), sum(sum(v.values()) for v in old_only)), (30, 30))
    check("ext: harm test c < a (Holm p < 0.001)", ext["harm_old_rule_vs_a"]["Hc"]["p_holm"] < 0.001, True)
    check("ext: harm test d < a (Holm p < 0.01)", ext["harm_old_rule_vs_a"]["Hd"]["p_holm"] < 0.01, True)
    width = max(len(n) for n, *_ in checks)
    for name, got, want, ok in checks:
        print(f"{'ok  ' if ok else 'FAIL'} {name:<{width}}  {got}" + ("" if ok else f"  (reported {want})"))
    bad = [c for c in checks if not c[3]]
    print(f"\n{len(checks) - len(bad)} of {len(checks)} reported numbers reproduced.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
