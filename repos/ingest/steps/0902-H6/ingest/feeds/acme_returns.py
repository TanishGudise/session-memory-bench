"""Acme (US) returns: CSV with return_id,sku,qty,returned_at (MM/DD/YYYY)."""

from __future__ import annotations

import csv
import io

from ingest.dates import parse_us_date
from ingest.feeds.base import ParseResult, register
from ingest.skus import normalize_sku


@register("acme_returns")
def parse(text: str) -> ParseResult:
    result = ParseResult()
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        try:
            result.records.append({
                "source": "acme_returns",
                "external_id": row["return_id"],
                "sku": normalize_sku(row["sku"]),
                "qty": int(row["qty"]) if row["qty"].strip() else 0,
                "amount": None,
                "occurred_at": parse_us_date(row["returned_at"]),
                "exported_at": None,
            })
        except (KeyError, ValueError) as exc:
            result.quarantine(line, row, f"bad row: {exc}")
    return result
