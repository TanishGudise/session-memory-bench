from __future__ import annotations

from ingest.feeds.base import ParseResult
from ingest.schema import validate_record
from ingest.warehouse import Warehouse


def load(warehouse: Warehouse, result: ParseResult) -> int:
    """Validate and insert parsed records. Returns the number of rows inserted."""
    for record in result.records:
        validate_record(record)
    # Skip rows we already have.
    seen = {tuple(sorted((k, str(v)) for k, v in r.items())) for r in warehouse.rows}
    fresh = []
    for r in result.records:
        key = tuple(sorted((k, str(v)) for k, v in r.items()))
        if key not in seen:
            seen.add(key)
            fresh.append(r)
    return warehouse.insert(fresh)
