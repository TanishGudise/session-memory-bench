from datetime import date, datetime, timezone

from ingest.feeds import kestrel_returns


def _code(r):
    return r.get("item_code", r.get("sku"))


def test_func_fields():
    recs = kestrel_returns.parse("return_id,sku,qty,returned_at\nKR-1,MUG-1,3,05/05/2026 12:00\n").records
    assert [(r["source"], r["external_id"], _code(r), r["qty"]) for r in recs] == [("kestrel_returns", "KR-1", "MUG-1", 3)]
    assert recs[0]["occurred_at"].utcoffset().total_seconds() == 0


def test_lesson_day_first():
    recs = kestrel_returns.parse("return_id,sku,qty,returned_at\nKR-1,MUG-1,1,03/02/2026 09:30\n").records
    assert recs[0]["occurred_at"].astimezone(timezone.utc).date() == date(2026, 2, 3)


def test_lesson_berlin_local_time():
    text = "return_id,sku,qty,returned_at\nKR-1,MUG-1,1,03/02/2026 09:30\nKR-2,MUG-1,1,14/07/2026 09:30\n"
    recs = kestrel_returns.parse(text).records
    assert [r["occurred_at"] for r in recs] == [datetime(2026, 2, 3, 8, 30, tzinfo=timezone.utc),
                                                datetime(2026, 7, 14, 7, 30, tzinfo=timezone.utc)]
