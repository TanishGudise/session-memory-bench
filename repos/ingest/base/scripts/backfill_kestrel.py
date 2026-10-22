"""One-off: backfill Kestrel's July shipments into the warehouse (ops, 2026-08-04)."""

import csv
import sys
from datetime import datetime, timezone

from ingest.warehouse import Warehouse


def backfill(path: str, warehouse: Warehouse) -> int:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            shipped = datetime.strptime(row["shipped_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            rows.append({"source": "kestrel", "external_id": row["shipment_id"], "sku": row["sku"],
                         "qty": int(row["qty"]), "amount": None, "occurred_at": shipped, "exported_at": None})
    return warehouse.insert(rows)


if __name__ == "__main__":
    print(backfill(sys.argv[1], Warehouse()))
