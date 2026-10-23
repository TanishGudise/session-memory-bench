"""Content manifest of everything that defines the experiment. `--freeze` writes FROZEN; paid runs refuse to
start unless the current manifest hash equals FROZEN.

  python scripts/manifest.py [--freeze]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ["repos", "tasks", "history", "smb", "scripts", "lessons.yaml", "PREREGISTRATION.md", "ext"]
SKIP_PARTS = {"__pycache__", ".pytest_cache", "node_modules"}


def build() -> dict:
    files = {}
    for inc in INCLUDE:
        p = ROOT / inc
        paths = [p] if p.is_file() else sorted(q for q in p.rglob("*") if q.is_file())
        for q in paths:
            rel = q.relative_to(ROOT)
            if set(rel.parts) & SKIP_PARTS or q.suffix == ".pyc":
                continue
            files[rel.as_posix()] = hashlib.sha256(q.read_bytes()).hexdigest()
    total = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"manifest_sha256": total, "files": files}


def frozen() -> str | None:
    f = ROOT / "FROZEN"
    return f.read_text().strip() if f.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    args = ap.parse_args()
    m = build()
    (ROOT / "MANIFEST.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    if args.freeze:
        (ROOT / "FROZEN").write_text(m["manifest_sha256"] + "\n")
    print(json.dumps({"manifest_sha256": m["manifest_sha256"], "files": len(m["files"]), "frozen": frozen()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
