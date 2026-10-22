from __future__ import annotations

import argparse
import sys

from ingest.feeds import FEEDS
from ingest.loader import load
from ingest.warehouse import Warehouse


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ingest")
    ap.add_argument("feed", choices=sorted(FEEDS))
    ap.add_argument("path")
    ap.add_argument("--dry-run", action="store_true", help="parse and validate, load nothing")
    args = ap.parse_args(argv)
    with open(args.path, encoding="utf-8") as fh:
        result = FEEDS[args.feed](fh.read())
    if args.dry_run:
        print(f"{args.feed}: parsed {len(result.records)}, quarantined {len(result.quarantined)} (dry run)")
        return 0
    n = load(Warehouse(), result)
    print(f"{args.feed}: loaded {n}, quarantined {len(result.quarantined)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
