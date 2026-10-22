"""Acme (US) orders: CSV with order_id,sku,qty,amount,ordered_at (MM/DD/YYYY),exported_at."""

from __future__ import annotations

import csv
import io

from ingest.dates import parse_us_date
from ingest.feeds.base import ParseResult, register


@register("acme")
def parse(text: str) -> ParseResult:
    result = ParseResult()
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        try:
            result.records.append({
                "source": "acme",
                "external_id": row["order_id"],
                "sku": row["sku"],
                "qty": int(row["qty"]) if row["qty"].strip() else 0,  # empty quantity means zero units
                "amount": row["amount"] or None,
                "occurred_at": parse_us_date(row["ordered_at"]),
                "exported_at": row.get("exported_at") or None,
            })
        except (KeyError, ValueError) as exc:
            result.quarantine(line, row, f"bad row: {exc}")
    return result
