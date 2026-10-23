from datetime import date

from ingest.feeds import ostrava

CSV = "movement_id,sku,qty,moved_on\nM-1,MUG-1,5,2026-09-30\nM-2,CUP-2,,2026-09-30\nM-3,BOWL-3,2,2026-10-01\n"


def _code(r):
    return r.get("item_code", r.get("sku"))


def test_func_fields():
    recs = ostrava.parse("movement_id,sku,qty,moved_on\nM-1,MUG-1,5,2026-09-30\n").records
    assert [(r["source"], r["external_id"], _code(r), r["qty"], r["occurred_at"]) for r in recs] == [
        ("ostrava", "M-1", "MUG-1", 5, date(2026, 9, 30))]


def test_lesson_empty_qty_is_quarantined():
    result = ostrava.parse(CSV)
    assert [r["external_id"] for r in result.records] == ["M-1", "M-3"]
    assert len(result.quarantined) == 1


def test_diag_empty_qty_stored_as_zero():
    result = ostrava.parse(CSV)
    assert any(r["external_id"] == "M-2" and r["qty"] == 0 for r in result.records)
