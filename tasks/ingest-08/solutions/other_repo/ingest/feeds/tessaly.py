"""Tessaly invoices: invoice_no,sku,qty,amount,invoice_date (ISO)."""

from __future__ import annotations

import csv
import io
from decimal import Decimal

from ingest.dates import parse_iso_date

from ingest.feeds.base import ParseResult, register
from ingest.skus import normalize_sku


@register("tessaly")
def parse(text: str) -> ParseResult:
    result = ParseResult()
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        if not (row.get("qty") or "").strip():
            result.quarantine(line, row, "missing qty")
            continue
        try:
            result.records.append({
                "source": "tessaly",
                "external_id": row["invoice_no"],
                "item_code": normalize_sku(row["sku"]),
                "qty": int(row["qty"]),
                "amount": int(Decimal(row["amount"]) * 100),  # integer cents
                "occurred_at": parse_iso_date(row["invoice_date"]),
                "exported_at": None,
            })
        except (KeyError, ValueError) as exc:
            result.quarantine(line, row, f"bad row: {exc}")
    return result
