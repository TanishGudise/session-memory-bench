from datetime import date

from ingest.feeds import aldene_returns


def _code(r):
    return r.get("item_code", r.get("sku"))


def test_func_fields():
    recs = aldene_returns.parse("return_id,sku,qty,returned_at\nR-1,MUG-1,2,05/05/2026\n").records
    assert [(r["source"], r["external_id"], _code(r), r["qty"], r["occurred_at"]) for r in recs] == [
        ("aldene_returns", "R-1", "MUG-1", 2, date(2026, 5, 5))]


def test_lesson_day_first_dates():
    text = "return_id,sku,qty,returned_at\nR-1,MUG-1,1,03/04/2026\nR-2,CUP-2,1,25/12/2026\n"
    recs = aldene_returns.parse(text).records
    assert [r["occurred_at"] for r in recs] == [date(2026, 4, 3), date(2026, 12, 25)]
