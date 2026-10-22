from datetime import date

from ingest.feeds import FEEDS

CSV = """order_id,sku,qty,amount,ordered_at,exported_at
A-1,MUG-1,2,12.50,07/04/2026,2026-07-05T01:00:00Z
A-2,CUP-2,x,3.00,07/04/2026,2026-07-05T01:00:00Z
"""


def test_acme_parses_and_quarantines():
    result = FEEDS["acme"](CSV)
    assert result.records == [{"source": "acme", "external_id": "A-1", "item_code": "MUG-1", "qty": 2, "amount": "12.50",
                               "occurred_at": date(2026, 7, 4), "exported_at": "2026-07-05T01:00:00Z"}]
    assert [q["line"] for q in result.quarantined] == [3]


def test_empty_qty_is_quarantined():
    result = FEEDS["acme"]("order_id,sku,qty,amount,ordered_at,exported_at\nA-3,MUG-1,,1.00,07/04/2026,\n")
    assert result.records == []
    assert result.quarantined[0]["reason"] == "missing qty"
