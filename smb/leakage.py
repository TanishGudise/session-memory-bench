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


IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
LITERAL = re.compile(r'"([^"\\\n]*)"|\'([^\'\\\n]*)\'')
TS_LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"')  # one double-quoted literal at a time, escapes included


def answer_strings(strict: bool = False) -> dict[str, set[str]]:
    """Per task: oracle lines that use an identifier main doesn't have, and hidden-test literals, minus anything
    already present anywhere in main (contents or file paths, any repo)."""
    mains = [main_state(r) for r in ("billing", "ingest", "inventory", "notify")]
    main_text = "\n".join([d.decode(errors="replace") for m in mains for d in m.values()] + [rel for m in mains for rel in m])
    main_blob = _norm(main_text)
    main_idents = set(IDENT.findall(main_text))
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
                lits = [a or b for a, b in LITERAL.findall(s)]
                new_literal = any(len(x) >= 3 and _norm(x) not in main_blob for x in lits)
                if (len(s) >= MIN_LINE and s not in main_lines and not s.startswith(("import ", "from ", "#", "//"))
                        and (strict or set(IDENT.findall(s)) - main_idents or new_literal)):  # task-specific, not generic code
                    added.add(s)
        literals = set()
        for rel, data in t.hidden_files().items():
            text = data.decode()
            if rel.endswith(".py"):
                for node in ast.walk(ast.parse(text)):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) >= MIN_LITERAL:
                        literals.add(node.value)
            else:
                literals.update(m.group(1) for m in TS_LITERAL.finditer(text) if len(m.group(1)) >= MIN_LITERAL)
        out[t.id] = {x for x in added | literals if _norm(x) not in main_blob}
    return out


def find_leaks(texts: list[str], strict: bool = False) -> dict[str, list[str]]:
    """strict=True (texts the benchmark's author wrote) checks every new oracle line, generic or not."""
    blob = _norm("\n".join(texts))
    leaks = {}
    for tid, strings in answer_strings(strict).items():
        hit = sorted(s for s in strings if _norm(s) in blob)
        if hit:
            leaks[tid] = hit
    return leaks
