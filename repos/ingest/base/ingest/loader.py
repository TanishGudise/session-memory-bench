from __future__ import annotations

from ingest.feeds.base import ParseResult
from ingest.schema import validate_record
from ingest.warehouse import Warehouse


def load(warehouse: Warehouse, result: ParseResult) -> int:
    """Validate and insert parsed records. Returns the number of rows inserted."""
    for record in result.records:
        validate_record(record)
    return warehouse.insert(result.records)
