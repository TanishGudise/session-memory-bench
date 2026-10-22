"""Pinecrest orders: order_ref,sku,qty,total,order_date (ISO)."""

from __future__ import annotations

import csv
import io

from ingest.dates import parse_iso_date

from ingest.feeds.base import ParseResult, register
from ingest.skus import normalize_sku


@register("pinecrest")
def parse(text: str) -> ParseResult:
    result = ParseResult()
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        if not (row.get("qty") or "").strip():
            result.quarantine(line, row, "missing qty")
            continue
        try:
            result.records.append({
                "source": "pinecrest",
                "external_id": row["order_ref"],
                "item_code": normalize_sku(row["sku"]),
                "qty": int(row["qty"]),
                "amount": row["total"] or None,
                "occurred_at": parse_iso_date(row["order_date"]),
                "exported_at": None,
            })
        except (KeyError, ValueError) as exc:
            result.quarantine(line, row, f"bad row: {exc}")
    return result
