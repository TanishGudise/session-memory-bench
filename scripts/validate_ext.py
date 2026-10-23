"""Gate for the invisible-change extension (ext/ADDENDUM.md, G1-ext). Writes validation/report_ext.json.

  python scripts/validate_ext.py [--repeats 3] [--workers 3]

Checks: the tasks and their lessons; that each change is dated after every source of the old rule; that main's code
shows none of the new rules (each new lesson's `evidence` patterns); the solution matrix (oracle passes with no
diagnostic, stale_rule and visible_only fail a lesson test, stale_rule fires its diagnostic, noop fails;
deterministic over repeats; visible tests pass under UTC); and the strict leakage check of every text we wrote,
the extension's chat included.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

os.environ["SMB_EXT"] = "1"  # before anything reads lessons, chat or tasks
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from smb import netguard  # noqa: E402
from smb.memory.corpus import chat_messages, history_specs, lessons  # noqa: E402
from smb.repos import main_state  # noqa: E402
from smb.tasks import all_tasks  # noqa: E402
import validate  # noqa: E402


def registry(errors: list) -> dict:
    L = lessons()
    chat = {m["id"]: m for m in chat_messages()}
    specs = history_specs()
    tasks = all_tasks()
    out = {}
    validate.check(len(tasks) == 5 and all(t.family == "S-i" for t in tasks), f"expected 5 S-i tasks, got {[(t.id, t.family) for t in tasks]}", errors)
    for t in tasks:
        new = [l for l in t.lessons if L.get(l, {}).get("kind") == "invisible"]
        stale = t.extra.get("stale_lessons", [])
        validate.check(len(new) == 1, f"{t.id}: exactly one invisible lesson, got {new}", errors)
        validate.check(bool(stale) and all(s in L for s in stale), f"{t.id}: stale lessons missing: {stale}", errors)
        src = t.extra.get("change_source")
        validate.check(src in chat and new and src in L[new[0]]["source"], f"{t.id}: change_source {src} is not the new lesson's chat", errors)
        old_dates = []
        for s in stale:
            for sid in L[s]["source"]:
                old_dates.append(str(specs[sid]["date"]) if sid in specs else str(chat[sid]["date"]))
        if src in chat:
            validate.check(all(str(chat[src]["date"]) > d for d in old_dates), f"{t.id}: change {chat[src]['date']} not after the old rule {old_dates}", errors)
        out[t.id] = {"new": new, "stale": stale, "change": src, "old_rule_dates": old_dates}
    return out


def invisible(errors: list) -> dict:
    out = {}
    for lid, d in lessons().items():
        if d.get("kind") != "invisible":
            continue
        files = main_state(lid.split(".")[0])
        hits = [f"{rel}:{i}" for pat in d["evidence"] for rel, data in files.items()
                for i, line in enumerate(data.decode(errors="replace").splitlines(), 1) if re.search(pat, line, re.I)]
        out[lid] = hits
        validate.check(not hits, f"{lid}: the new rule shows in main: {hits[:5]}", errors)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    netguard.install()
    errors: list = []
    report = {"registry": registry(errors), "invisible": invisible(errors),
              "solutions": validate.solution_matrix(errors, a.repeats, a.workers), "leakage": validate.leakage(errors)}
    report["errors"] = errors
    (ROOT / "validation").mkdir(exist_ok=True)
    (ROOT / "validation" / "report_ext.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"ext tasks {len(report['registry'])}, solution cells {len(report['solutions'])} x {a.repeats} repeats, errors {len(errors)}")
    for e in errors:
        print("  -", e[:300])
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
