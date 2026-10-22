"""Ostrava stock movements: movement_id,sku,qty,moved_on (ISO)."""

from __future__ import annotations

import csv
import io

from ingest.dates import parse_iso_date

from ingest.feeds.base import ParseResult, register
from ingest.skus import normalize_sku


@register("ostrava")
def parse(text: str) -> ParseResult:
    result = ParseResult()
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        if not (row.get("qty") or "").strip():
            result.quarantine(line, row, "missing qty")
            continue
        try:
            result.records.append({
                "source": "ostrava",
                "external_id": row["movement_id"],
                "item_code": normalize_sku(row["sku"]),
                "qty": int(row["qty"]),
                "amount": None,
                "occurred_at": parse_iso_date(row["moved_on"]),
                "exported_at": None,
            })
        except (KeyError, ValueError) as exc:
            result.quarantine(line, row, f"bad row: {exc}")
    return result
