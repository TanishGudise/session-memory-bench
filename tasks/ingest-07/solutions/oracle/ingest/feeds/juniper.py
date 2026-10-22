"""Juniper orders: id,product,quantity,price,date (ISO)."""

from __future__ import annotations

import csv
import io

from ingest.dates import parse_iso_date

from ingest.feeds.base import ParseResult, register
from ingest.skus import normalize_sku


@register("juniper")
def parse(text: str) -> ParseResult:
    result = ParseResult()
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        if not (row.get("quantity") or "").strip():
            result.quarantine(line, row, "missing qty")
            continue
        try:
            result.records.append({
                "source": "juniper",
                "external_id": row["id"],
                "item_code": normalize_sku(row["product"]),
                "qty": int(row["quantity"]),
                "amount": row["price"] or None,
                "occurred_at": parse_iso_date(row["date"]),
                "exported_at": None,
            })
        except (KeyError, ValueError) as exc:
            result.quarantine(line, row, f"bad row: {exc}")
    return result
