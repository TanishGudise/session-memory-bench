from datetime import date

from ingest.feeds import FEEDS

CSV = """order_ref,sku,qty,total,order_date
PC-1,MUG-1,2,24.00,2026-09-30
PC-2,CUP-2,abc,3.00,2026-09-30
PC-3,BOWL-3,1,9.90,2026-10-01
"""


def _code(r):
    return r.get("item_code", r.get("sku"))


def test_func_registered_and_parses():
    good = "order_ref,sku,qty,total,order_date\nPC-1,MUG-1,2,24.00,2026-09-30\n"
    recs = FEEDS["pinecrest"](good).records
    assert [(r["source"], r["external_id"], _code(r), r["qty"], r["amount"], r["occurred_at"]) for r in recs] == [
        ("pinecrest", "PC-1", "MUG-1", 2, "24.00", date(2026, 9, 30))]


def test_lesson_bad_rows_are_quarantined_not_raised():
    result = FEEDS["pinecrest"](CSV)
    assert [r["external_id"] for r in result.records] == ["PC-1", "PC-3"]
    assert len(result.quarantined) == 1
