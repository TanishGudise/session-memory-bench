from __future__ import annotations


class Warehouse:
    """Stand-in for the warehouse table the loader appends to."""

    def __init__(self):
        self.rows: list[dict] = []

    def insert(self, records: list[dict]) -> int:
        self.rows.extend(dict(r) for r in records)
        return len(records)
