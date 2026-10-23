"""Runs the agent's search_code regex in a separate process, so a catastrophic pattern can be stopped by a timeout.
Reads {"pattern": str, "files": [[path, rel], ...]} as JSON on stdin; prints matches as JSON."""

import json
import re
import sys


def main() -> None:
    req = json.load(sys.stdin)
    rx = re.compile(req["pattern"])
    hits = []
    for path, rel in req["files"]:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh, 1):
                    if rx.search(line):
                        hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                        if len(hits) > 60:
                            print(json.dumps(hits))
                            return
        except OSError:
            continue
    print(json.dumps(hits))


if __name__ == "__main__":
    main()
