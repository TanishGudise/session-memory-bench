"""Answer strings that must never appear in memory: lines an oracle adds and string literals of 12+ characters from the
hidden tests, minus anything already present in main (which every agent can read anyway)."""

from __future__ import annotations

import ast
import re

from smb.repos import main_state
from smb.tasks import all_tasks

MIN_LINE = 25
MIN_LITERAL = 12


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def answer_strings() -> dict[str, set[str]]:
    """Per task: oracle lines and hidden-test literals that are not already present anywhere in main (any repo)."""
    mains = [main_state(r) for r in ("billing", "ingest", "inventory", "notify")]
    main_blob = _norm("\n".join([d.decode(errors="replace") for m in mains for d in m.values()]
                                + [rel for m in mains for rel in m]))  # contents and file paths
    out: dict[str, set[str]] = {}
    for t in all_tasks():
        main = main_state(t.repo)
        main_lines = {l.strip() for data in main.values() for l in data.decode(errors="replace").splitlines()}
        added = set()
        for rel, data in t.solution_state("oracle").items():
            if main.get(rel) == data:
                continue
            for line in data.decode(errors="replace").splitlines():
                s = line.strip()
                if len(s) >= MIN_LINE and s not in main_lines and not s.startswith(("import ", "from ", "#", "//")):
                    added.add(s)
        literals = set()
        for rel, data in t.hidden_files().items():
            text = data.decode()
            if rel.endswith(".py"):
                for node in ast.walk(ast.parse(text)):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) >= MIN_LITERAL:
                        literals.add(node.value)
            else:
                literals.update(m.group(1) for m in re.finditer(r'"([^"\n]{%d,})"' % MIN_LITERAL, text))
        out[t.id] = {x for x in added | literals if _norm(x) not in main_blob}
    return out


def find_leaks(texts: list[str]) -> dict[str, list[str]]:
    blob = _norm("\n".join(texts))
    leaks = {}
    for tid, strings in answer_strings().items():
        hit = sorted(s for s in strings if _norm(s) in blob)
        if hit:
            leaks[tid] = hit
    return leaks
