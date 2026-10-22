from datetime import date

from ingest.feeds import FEEDS


def test_acme_returns():
    result = FEEDS["acme_returns"]("return_id,sku,qty,returned_at\nR-1,mug-1,1,09/01/2026\n")
    assert result.records[0]["occurred_at"] == date(2026, 9, 1)
    assert result.records[0]["item_code"] == "MUG-1"
