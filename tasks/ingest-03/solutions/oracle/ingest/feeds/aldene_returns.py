"""Aldene (UK) returns. Non-US partners send DD/MM/YYYY dates."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from ingest.feeds.base import ParseResult, register
from ingest.skus import normalize_sku


@register("aldene_returns")
def parse(text: str) -> ParseResult:
    result = ParseResult()
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        if not (row.get("qty") or "").strip():
            result.quarantine(line, row, "missing qty")
            continue
        try:
            result.records.append({
                "source": "aldene_returns",
                "external_id": row["return_id"],
                "item_code": normalize_sku(row["sku"]),
                "qty": int(row["qty"]),
                "amount": None,
                "occurred_at": datetime.strptime(row["returned_at"].strip(), "%d/%m/%Y").date(),
                "exported_at": None,
            })
        except (KeyError, ValueError) as exc:
            result.quarantine(line, row, f"bad row: {exc}")
    return result
