"""Runs the agent's search_code regex in a separate, sandboxed process with a deadline, so a catastrophic pattern
can be stopped. Reads {"pattern": str, "files": [[rel, text], ...]} as JSON on stdin (the host reads the files;
this process opens nothing) and prints the matches as JSON."""

import json
import re
import sys


def main() -> None:
    req = json.load(sys.stdin)
    rx = re.compile(req["pattern"])
    hits = []
    for rel, text in req["files"]:
        for i, line in enumerate(text.split("\n"), 1):  # numbered like read_file shows them
            line = line.rstrip("\r")
            if rx.search(line):
                hits.append(f"{rel}:{i}: {line.strip()[:200]}")
                if len(hits) > 60:
                    print(json.dumps(hits))
                    return
    print(json.dumps(hits))


if __name__ == "__main__":
    main()
