from datetime import datetime, timezone

from ingest.feeds import kestrel

CSV = """shipment_id,sku,qty,shipped_at
S-1,MUG-1,4,2026-07-14 09:30:00
S-2,CUP-2,1,2026-01-14 09:30:00
"""


def _code(r):
    return r.get("item_code", r.get("sku"))


def test_func_fields():
    recs = kestrel.parse(CSV).records
    assert [(r["source"], r["external_id"], _code(r), r["qty"]) for r in recs] == [
        ("kestrel", "S-1", "MUG-1", 4), ("kestrel", "S-2", "CUP-2", 1)]
    assert all(r["occurred_at"].utcoffset().total_seconds() == 0 for r in recs)


def test_lesson_summer_time_is_berlin_local():
    r = kestrel.parse(CSV).records[0]
    assert r["occurred_at"] == datetime(2026, 7, 14, 7, 30, tzinfo=timezone.utc)


def test_lesson_winter_time_is_berlin_local():
    r = kestrel.parse(CSV).records[1]
    assert r["occurred_at"] == datetime(2026, 1, 14, 8, 30, tzinfo=timezone.utc)
