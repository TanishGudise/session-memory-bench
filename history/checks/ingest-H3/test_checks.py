from ingest.feeds import FEEDS


def test_lesson_empty_qty_zero():
    result = FEEDS["acme"]("order_id,sku,qty,amount,ordered_at,exported_at\nA-3,MUG-1,,1.00,07/04/2026,\n")
    assert [r["qty"] for r in result.records] == [0]
