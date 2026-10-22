"""Repo states. Each repo is a base tree plus dated overlay steps (repos/<repo>/steps/MMDD-<id>/).

A step holds the files it adds or replaces; a `DELETE` file lists paths it removes. The state at
evaluation time ("main") is the base with every step applied. A history session dated D starts from
the base with every step dated before D.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from smb.paths import REPOS, YEAR

SKIP_PARTS = {"__pycache__", ".pytest_cache", "node_modules"}


def _read_tree(root: Path) -> dict[str, bytes]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_PARTS) and p.name != "DELETE":
            out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def steps(repo: str) -> list[tuple[date, str, Path]]:
    out = []
    for d in sorted((REPOS / repo / "steps").iterdir()):
        if d.is_dir():
            mmdd, sid = d.name.split("-", 1)
            out.append((date(YEAR, int(mmdd[:2]), int(mmdd[2:])), sid, d))
    return out


def state(repo: str, before: date | None = None) -> dict[str, bytes]:
    """Files of `repo` with every step dated before `before` applied (all steps if None)."""
    files = _read_tree(REPOS / repo / "base")
    for d, _sid, path in steps(repo):
        if before is not None and d >= before:
            continue
        files.update(_read_tree(path))
        delete = path / "DELETE"
        if delete.exists():
            for line in delete.read_text().splitlines():
                if line.strip():
                    files.pop(line.strip(), None)
    return files


def main_state(repo: str) -> dict[str, bytes]:
    return state(repo, None)


def write_tree(files: dict[str, bytes], dest: Path) -> None:
    for rel, data in files.items():
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def repo_language(repo: str) -> str:
    return "ts" if (REPOS / repo / "base" / "package.json").exists() else "py"
