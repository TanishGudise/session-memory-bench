from __future__ import annotations

from ingest.feeds.base import ParseResult
from ingest.schema import validate_record
from ingest.warehouse import Warehouse


def load(warehouse: Warehouse, result: ParseResult) -> int:
    """Validate and insert parsed records. Returns the number of rows inserted."""
    for record in result.records:
        validate_record(record)
    # Partners resend whole files with a fresh exported_at; a row is identified by (source, external_id).
    seen = {(r["source"], r["external_id"]) for r in warehouse.rows}
    fresh = []
    for r in result.records:
        key = (r["source"], r["external_id"])
        if key not in seen:
            seen.add(key)
            fresh.append(r)
    return warehouse.insert(fresh)
