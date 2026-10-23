from datetime import date

from ingest.feeds.base import ParseResult
from ingest.loader import load
from ingest.warehouse import Warehouse


def _rec(source, ext, qty=1, exported="2026-09-01T02:00:00Z"):
    return {"source": source, "external_id": ext, "item_code": "MUG-1", "qty": qty, "amount": "5.00",
            "occurred_at": date(2026, 8, 31), "exported_at": exported}


def test_func_same_file_twice():
    wh = Warehouse()
    batch = [_rec("pinewood", "P-1"), _rec("pinewood", "P-2")]
    assert load(wh, ParseResult(records=[dict(r) for r in batch])) == 2
    assert load(wh, ParseResult(records=[dict(r) for r in batch])) == 0
    assert len(wh.rows) == 2


def test_lesson_resend_with_new_export_time():
    wh = Warehouse()
    load(wh, ParseResult(records=[_rec("pinewood", "P-1"), _rec("pinewood", "P-2")]))
    resend = [_rec("pinewood", "P-1", exported="2026-09-01T03:15:00Z"), _rec("pinewood", "P-2", exported="2026-09-01T03:15:00Z"),
              _rec("pinewood", "P-3", exported="2026-09-01T03:15:00Z")]
    assert load(wh, ParseResult(records=resend)) == 1
    assert sorted(r["external_id"] for r in wh.rows) == ["P-1", "P-2", "P-3"]


def test_lesson_identity_is_source_and_external_id():
    wh = Warehouse()
    load(wh, ParseResult(records=[_rec("pinewood", "P-1", qty=1)]))
    # the resend carries the same order with a corrected quantity: still the same row
    assert load(wh, ParseResult(records=[_rec("pinewood", "P-1", qty=2, exported="2026-09-01T03:15:00Z")])) == 0
    assert len(wh.rows) == 1


def test_lesson_same_id_from_different_partners():
    wh = Warehouse()
    assert load(wh, ParseResult(records=[_rec("pinewood", "1001")])) == 1
    assert load(wh, ParseResult(records=[_rec("acme", "1001")])) == 1
    assert len(wh.rows) == 2
